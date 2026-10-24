# Empyrion Scenario Editor
# Copyright (C) 2026  Daflo
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Resolution RECURSIVE des dependances d'un bloc/item ECF d'un scenario
source (A ou B), en vue d'un import vers la copie de travail.

Empyrion ne type pas ses references : `Ref`, la recette
du meme nom (Templates.ecf), les ingredients d'un Template, les Blocks
d'un BlockGroup, les Item_N d'un LootGroup, une icone ou une cle de
localisation. Ce module construit un catalogue du scenario source, suit
ces references en profondeur (anti-cycle, borne) et separe :

  - `imports` : entites/fichiers ABSENTS de la copie de travail, a importer ;
  - `present` : deja la (sondees quand meme, pour trouver les manquants) ;
  - `unresolved` : reference introuvable ou ambigue, ou asset absent --
    detaillee pour l'export CSV.

Lecture seule : aucune ecriture ici.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .model import (EcfBlock, EcfDocument, EcfProperty, block_identity,
                    normalized_kind)
from .parser import parse_ecf_file

CONFIG_DIR = "Content/Configuration"
LOCALIZATION_CSV = "Extras/Localization.csv"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".dds", ".tga", ".bmp"}
MAX_NODES = 300

_IDENTIFIABLE = ("Ref",)
_TEMPLATE_KINDS = ("template", "+template")
# L'ARBRE TECHNOLOGIQUE N'EST PAS UNE DEPENDANCE (decision 22/10) :
# TechTreeParent / TechTreeNames sont des liens d'affichage. Les suivre
# embarquait 65 cibles au lieu de ~10 et ne change rien au bloc importe.
_ENTITY_KINDS = ("block", "item", "template", "blockgroup", "lootgroup",
                 "container", "egroup")


@dataclass(frozen=True)
class Entity:
    rel: str                 # fichier relatif a la racine source
    ident: str               # Name (ou Id) du bloc
    kind: str
    name: str


@dataclass
class Unresolved:
    kind: str                # entity / icon / localization
    ref: str
    from_rel: str
    from_ident: str
    reason: str


@dataclass
class Resolution:
    imports: List[dict] = field(default_factory=list)   # {target, reason}
    present: List[dict] = field(default_factory=list)
    unresolved: List[Unresolved] = field(default_factory=list)
    # Arbre technologique RENCONTRE mais NON importe (decision 22/10) :
    # l'application doit avertir l'utilisateur qu'il reste a le raccorder.
    techtree: List[dict] = field(default_factory=list)   # {from, parent, tabs}
    truncated: bool = False


def _norm(value) -> str:
    return str(value or "").strip().strip('"').strip("'").casefold()


def _first_token(value) -> str:
    """Premier champ d'une valeur Empyrion ('Nom, 5, 0, 0' -> 'Nom')."""
    return str(value or "").strip().strip('"').split(",")[0].strip()


def _lines(block: EcfBlock):
    """(cle, valeur) de la ligne d'ouverture PUIS du corps, dans l'ordre."""
    for name, value in block.pairs:
        yield name, value
    for child in block.children:
        if isinstance(child, EcfProperty):
            for name, value in child.pairs:
                yield name, value


def _property_lines(block: EcfBlock):
    """Les groupes de paires D'UNE MEME LIGNE (une EcfProperty = une ligne)."""
    if block.pairs:
        yield block.pairs
    for child in block.children:
        if isinstance(child, EcfProperty):
            yield child.pairs


def _line_value(pairs, key: str) -> Optional[str]:
    """Valeur d'une cle, en recollant les elements SANS cle qui la suivent :
    `TechTreeNames: Base,AsgardTech` est parse en ('TechTreeNames','Base')
    + (None,'AsgardTech')."""
    for index, (name, value) in enumerate(pairs):
        if name != key:
            continue
        parts = [value]
        for next_name, next_value in pairs[index + 1:]:
            if next_name is not None:
                break
            parts.append(next_value)
        return ",".join(part for part in parts if part is not None)
    return None


def _prop(block: EcfBlock, key: str) -> Optional[str]:
    """Valeur d'une propriete du CORPS (les proprietes de config sont des
    EcfProperty enfants, pas la ligne d'ouverture : `block.get` ne voit que
    Id/Name/Ref)."""
    for pairs in _property_lines(block):
        value = _line_value(pairs, key)
        if value is not None:
            return value
    return None


def _csv_has_key(path, key) -> bool:
    needle = _norm(key)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return any(_norm(line.split(",", 1)[0]) == needle
                       for line in handle)
    except OSError:
        return False


def _split_list(value) -> List[str]:
    return [token.strip().strip('"').strip("'")
            for token in str(value or "").split(",") if token.strip()]


class Catalog:
    """Index des entites ECF d'un scenario source, par Name et par Id."""

    def __init__(self, root):
        self.root = Path(root)
        self.by_name: Dict[str, List[Entity]] = {}
        self.by_ident: Dict[str, List[Entity]] = {}
        self.recipes: Dict[str, Entity] = {}
        self._docs: Dict[str, EcfDocument] = {}
        self._working_docs: Dict[str, Optional[EcfDocument]] = {}
        self._icons: Optional[Dict[str, str]] = None
        self._loc_keys: Optional[set] = None
        self._load()

    def _load(self) -> None:
        config = self.root / CONFIG_DIR
        if not config.is_dir():
            return
        for path in sorted(config.glob("*.ecf")):
            if path.name.startswith("+") or "backup" in path.name.lower():
                continue                     # copie de secours, pas du contenu
            rel = path.relative_to(self.root).as_posix()
            try:
                doc = parse_ecf_file(path)
            except Exception:  # noqa: BLE001 -- un ECF illisible n'arrete pas l'index
                continue
            for block in doc.iter_blocks():
                kind = normalized_kind(block.kind).lower()
                if kind not in _ENTITY_KINDS:
                    continue
                name = str(block.get("Name") or "").strip()
                ident = block_identity(block) or name
                if not name and not ident:
                    continue
                entity = Entity(rel=rel, ident=name or ident, kind=kind,
                                name=name)
                if name:
                    self.by_name.setdefault(_norm(name), []).append(entity)
                if ident:
                    self.by_ident.setdefault(_norm(ident), []).append(entity)
                if kind in _TEMPLATE_KINDS and name:
                    self.recipes[_norm(name)] = entity

    def entity(self, rel: str, ident: str) -> Optional[Entity]:
        for entity in self.by_name.get(_norm(ident), []) + \
                self.by_ident.get(_norm(ident), []):
            if _norm(entity.rel) == _norm(rel):
                return entity
        return None

    def find(self, name: str, kinds: Tuple[str, ...] = ()
             ) -> Tuple[Optional[Entity], str]:
        """(entite, probleme). Un nom partage par plusieurs entites de kinds
        differents est ambigu : mieux vaut le signaler que deviner."""
        wanted = _norm(name)
        candidates = self.by_name.get(wanted, [])
        if kinds:
            filtered = [e for e in candidates if e.kind in kinds]
            if filtered:
                candidates = filtered
        if not candidates:
            candidates = self.by_ident.get(wanted, [])
            if kinds:
                filtered = [e for e in candidates if e.kind in kinds]
                if filtered:
                    candidates = filtered
        if not candidates:
            return None, "not found"
        if len(candidates) > 1 and len({e.kind for e in candidates}) > 1:
            return None, ("ambiguous ("
                          + ", ".join(sorted({e.kind for e in candidates}))
                          + ")")
        return candidates[0], ""

    def block(self, entity: Entity) -> Optional[EcfBlock]:
        doc = self._docs.get(entity.rel)
        if doc is None:
            path = self.root / entity.rel
            try:
                doc = parse_ecf_file(path)
            except Exception:  # noqa: BLE001
                return None
            self._docs[entity.rel] = doc
        wanted = _norm(entity.ident)
        for block in doc.iter_blocks():
            if _norm(block.get("Name")) == wanted or \
                    _norm(block_identity(block)) == wanted:
                return block
        return None

    def inside_working(self, working_root, entity: Entity) -> bool:
        if working_root is None:
            return False
        key = str(Path(working_root).resolve()) + "|" + entity.rel
        if key not in self._working_docs:
            path = Path(working_root) / entity.rel
            doc = None
            if path.is_file():
                try:
                    doc = parse_ecf_file(path)
                except Exception:  # noqa: BLE001
                    doc = None
            self._working_docs[key] = doc
        doc = self._working_docs[key]
        if doc is None:
            return False
        wanted = _norm(entity.ident)
        return any(_norm(b.get("Name")) == wanted or
                   _norm(block_identity(b)) == wanted
                   for b in doc.iter_blocks())

    def icon(self, name: str) -> Optional[str]:
        """Chemin relatif d'un fichier image dont le STEM est ce nom."""
        if self._icons is None:
            self._icons = {}
            for base in ("SharedData", "Content"):
                root = self.root / base
                if not root.is_dir():
                    continue
                for path in root.rglob("*"):
                    if path.suffix.lower() in IMAGE_SUFFIXES:
                        self._icons.setdefault(_norm(path.stem),
                                               path.relative_to(
                                                   self.root).as_posix())
        return self._icons.get(_norm(name))

    def localization_has(self, key: str) -> bool:
        if self._loc_keys is None:
            self._loc_keys = set()
            path = self.root / LOCALIZATION_CSV
            if path.is_file():
                try:
                    with open(path, "r", encoding="utf-8",
                              errors="replace") as handle:
                        for line in handle:
                            self._loc_keys.add(
                                _norm(line.split(",", 1)[0]))
                except OSError:
                    pass
        return _norm(key) in self._loc_keys


def references(block: EcfBlock, catalog: Catalog, rel: str = ""
               ) -> List[Tuple[str, str, str, Tuple[str, ...]]]:
    """(type, reference, raison, kinds attendus) des dependances d'un bloc.
    'type' vaut entity / icon / localization."""
    kind = normalized_kind(block.kind).lower()
    out: List[Tuple[str, str, str, Tuple[str, ...]]] = []
    name = str(_prop(block, "Name") or block_identity(block) or "?").strip()
    own = (("item",) if kind == "item"
           else ("block",) if kind == "block" else ())
    for key in _IDENTIFIABLE:
        value = _first_token(_prop(block, key))
        if value:
            out.append(("entity", value, f"inherited from {name}", own))
    if kind in ("block", "item"):
        recipe = catalog.recipes.get(_norm(_prop(block, "Name")))
        if recipe is not None and recipe.rel != rel:
            out.append(("entity", recipe.ident, f"recipe of {name}",
                        ("template",)))
    if kind in _TEMPLATE_KINDS:
        for child in block.children:
            if not isinstance(child, EcfBlock):
                continue
            for line in child.children:
                if not isinstance(line, EcfProperty):
                    continue
                for key, _value in line.pairs:
                    if key:
                        out.append(("entity", str(key),
                                    f"{child.kind} of {name}",
                                    ("item", "block")))
    if kind == "blockgroup":
        for token in _split_list(_prop(block, "Blocks")):
            out.append(("entity", token, f"member of BlockGroup {name}",
                        ("block",)))
    if kind == "lootgroup":
        for key, value in _lines(block):
            if key and key.lower().startswith("item"):
                out.append(("entity", _first_token(value),
                            f"{key} of LootGroup {name}", ("item",)))
    if kind in ("block", "item"):
        for key in ("CustomIcon", "Icon"):
            icon = str(_prop(block, key) or "").strip()
            if icon:
                out.append(("icon", icon, f"{key} of {name}", ()))
                break
        info = str(_prop(block, "Info") or "").strip()
        if info:
            out.append(("localization", info,
                        f"localization of {name}", ()))
    return out


_CACHE: Dict[tuple, "Resolution"] = {}


def clear_cache() -> None:
    """A appeler apres un import : la working a change, les statuts
    'present/absent' du cache ne sont plus vrais."""
    _CACHE.clear()


def resolve(root, rel: str, ident: str, working_root=None,
            max_nodes: int = MAX_NODES) -> Resolution:
    """Suit les dependances depuis (rel, ident) dans le scenario `root`.
    Memoise la derniere resolution : le plan l'a deja calculee quand la
    revue la redemande (3-4 s d'indexation du catalogue sinon)."""
    key = (str(Path(root).resolve()), _norm(rel), _norm(ident),
           str(Path(working_root).resolve()) if working_root else "")
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    result = _resolve(root, rel, ident, working_root, max_nodes)
    if len(_CACHE) > 8:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = result
    return result


def _resolve(root, rel: str, ident: str, working_root=None,
             max_nodes: int = MAX_NODES) -> Resolution:
    catalog = Catalog(root)
    working = Path(working_root) if working_root else None
    result = Resolution()
    start = catalog.entity(rel, ident)
    if start is None:
        start_block = None
        path = Path(root) / rel
        try:
            doc = parse_ecf_file(path)
        except Exception:  # noqa: BLE001
            doc = None
        if doc is not None:
            wanted = _norm(ident)
            for block in doc.iter_blocks():
                if _norm(block.get("Name")) == wanted or \
                        _norm(block_identity(block)) == wanted:
                    start_block = block
                    break
        if start_block is None:
            result.unresolved.append(Unresolved(
                kind="entity", ref=ident, from_rel=rel, from_ident=ident,
                reason="root block not found"))
            return result
        start = Entity(rel=rel, ident=ident,
                       kind=normalized_kind(start_block.kind).lower(),
                       name=str(start_block.get("Name") or ident))

    seen = set()
    queue: List[Tuple[Entity, str]] = [(start, "requested block")]
    while queue:
        entity, reason = queue.pop(0)
        key = (_norm(entity.rel), _norm(entity.ident))
        if key in seen:
            continue
        seen.add(key)
        if len(seen) > max_nodes:
            result.truncated = True
            break
        entry = {"target": f"{entity.rel}#{entity.ident}",
                 "reason": reason, "kind": entity.kind,
                 "name": entity.name}
        if catalog.inside_working(working, entity):
            result.present.append(entry)
        else:
            result.imports.append(entry)
        block = catalog.block(entity)
        if block is None:
            result.unresolved.append(Unresolved(
                kind="entity", ref=entity.ident, from_rel=entity.rel,
                from_ident=entity.ident, reason="block could not be re-read"))
            continue
        parent = _first_token(_prop(block, "TechTreeParent"))
        tabs = _split_list(_prop(block, "TechTreeNames"))
        if parent or tabs:
            result.techtree.append({
                "from": f"{entity.rel}#{entity.ident}",
                "parent": parent, "tabs": tabs})
        for ref_kind, value, why, kinds in references(block, catalog,
                                                    entity.rel):
            if ref_kind == "entity":
                target, problem = catalog.find(value, kinds)
                if target is None:
                    result.unresolved.append(Unresolved(
                        kind="entity", ref=value, from_rel=entity.rel,
                        from_ident=entity.ident,
                        reason=f"{why}: {problem}"))
                else:
                    queue.append((target, why))
            elif ref_kind == "icon":
                icon = catalog.icon(value)
                if icon is None:
                    result.unresolved.append(Unresolved(
                        kind="icon", ref=value, from_rel=entity.rel,
                        from_ident=entity.ident,
                        reason=f"{why}: no image file"))
                else:
                    entry = {"target": icon, "reason": why, "kind": "image",
                             "name": value}
                    if working is not None and (working / icon).is_file():
                        result.present.append(entry)
                    else:
                        result.imports.append(entry)
            elif ref_kind == "localization":
                if not catalog.localization_has(value):
                    result.unresolved.append(Unresolved(
                        kind="localization", ref=value, from_rel=entity.rel,
                        from_ident=entity.ident,
                        reason=f"{why}: key missing"))
                else:
                    entry = {"target": LOCALIZATION_CSV,
                             "reason": f"localization key {value}",
                             "kind": "csv", "name": value}
                    dest_csv = (working / LOCALIZATION_CSV
                                if working is not None else None)
                    if dest_csv is not None and _csv_has_key(dest_csv, value):
                        if entry not in result.present:
                            result.present.append(entry)
                    elif entry not in result.imports:
                        result.imports.append(entry)
    unique = {}
    for item in result.unresolved:
        unique.setdefault((item.kind, item.ref, item.reason), item)
    result.unresolved = list(unique.values())
    result.imports = _merge_file_entries(result.imports)
    result.present = _merge_file_entries(result.present)
    return result


def _merge_file_entries(entries: List[dict]) -> List[dict]:
    """Un seul import par FICHIER (la localisation revient pour chaque cle) :
    les cles sont regroupees dans la raison, l'ordre d'apparition est garde."""
    merged: Dict[str, dict] = {}
    order: List[str] = []
    for entry in entries:
        target = entry["target"]
        existing = merged.get(target)
        if existing is None:
            merged[target] = dict(entry)
            order.append(target)
        elif existing.get("kind") == "csv" and entry.get("name"):
            existing["reason"] = (existing["reason"] + ", "
                                  + str(entry["name"]))
    return [merged[target] for target in order]
