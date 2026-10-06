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

"""Fusion STRUCTURELLE GENERIQUE des YAML (demande 26/09/2026 : un
PDA.yaml existant etait ecrase ou copie en aveugle, seule la fusion
dediee de Sectors.yaml (core/sectors_merge.py) insérait sans ecraser).

Principe identique a sectors_merge, generalise a tout fichier YAML :
on propose UNITE PAR UNITE ce que la source apporte et qui manque a la
copie de travail --
  - une CLE RACINE absente (branche entiere inseree) ;
  - un ELEMENT d'une liste de blocs sous une cle commune aux deux
    fichiers (chapitre PDA identifie par son Id, bloc identifie par son
    Name...) -- identite = premiere cle renseignee parmi
    Id/Name/IndexName/Index/Key chez les ENFANTS de l'element ;
  - une SOUS-CLE (liste) absente d'un bloc present (YAML-009 : visible
    et cochenable, plus de skip silencieux) ;
  - les elements des SOUS-LISTES d'un bloc present des deux cotes
    (complement recursif : taches, actions, POIs... ajoutes chez la
    source dans un bloc deja connu).
Les blocs presents ne sont jamais REECRITS : seuls des ajouts y sont
inseres, et seulement si coches ; le rendu yamllite preserve commentaires
et mise en forme."""
import copy
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from core.yamllite.model import YamlBlank, YamlEntry
from core.yamllite.parser import parse_yaml_file

_IDENTITY_KEYS = ("Id", "Name", "GroupName", "ChapterTitle", "IndexName",
                  "Index", "Key")
_DETAIL_KEYS = ("Title", "Category", "Description", "Name")
_MAX_DEPTH = 12        # garde-fou anti-boucle sur des imbrications pathologiques


@dataclass
class YamlUnit:
    """Une unite fusionnable : cle racine entiere, element d'une liste de
    blocs, ou sous-cle absente d'un bloc present (YAML-009)."""
    kind: str            # 'key' | 'item' | 'subkey'
    root: str            # '' pour une cle top-level, sinon le chemin lisible
                         # qui porte la liste ('POIs/Random',
                         # 'Chapters/MaMission/Tasks')
    name: str            # cle (kind='key'/'subkey') ou identite de
                         # l'element (kind='item')
    detail: str = ""     # info complementaire (titre, categorie...)
    idkey: str = ""      # cle d'identite de l'element ('Id', 'ChapterTitle'...)
                         # pour un appariement exact a l'application
    path: tuple = None   # segments de navigation exacts a l'application :
                         # ('key', cle) | ('item', cle_identite, valeur) —
                         # None = derive de root (compat anciens appels)


def _top_entries(doc) -> List[YamlEntry]:
    return [n for n in doc.nodes if isinstance(n, YamlEntry)]


def _child_entries(entry: YamlEntry) -> List[YamlEntry]:
    return [c for c in entry.children if isinstance(c, YamlEntry)]


def _seq_items(entry: YamlEntry) -> List[YamlEntry]:
    return [c for c in _child_entries(entry) if c.is_sequence_item]


def _scalar(entry: YamlEntry, key: str) -> str:
    for c in _child_entries(entry):
        if c.key == key and c.value:
            return c.value.strip().strip("'\"")
    return ""


def _identity(entry: YamlEntry) -> Optional[Tuple[str, str]]:
    """(cle, valeur) d'identite d'un element de liste, ou None. Convention
    yamllite : '- ChapterTitle: tok' porte la cle sur l'item LUI-MEME
    (key/value), ses suites sont des enfants. Genericite (vecu 26/09 : les
    chapitres RE2 du PDA.yaml commencent par ChapterTitle, sans Id) :
    TOUTE item '- Cle: valeur' est identifiable par sa propre premiere
    cle ; la boucle _IDENTITY_KEYS ne sert qu'aux rares listes dont
    l'identite est une SOUS-cle de l'item."""
    if entry.is_sequence_item and entry.key and entry.value:
        return entry.key, entry.value.strip().strip("'\"")
    for k in _IDENTITY_KEYS:
        v = _scalar(entry, k)
        if v:
            return k, v
    return None


def _detail(entry: YamlEntry) -> str:
    for k in _DETAIL_KEYS:
        v = entry.value.strip().strip("'\"") \
            if (entry.is_sequence_item and entry.key == k and entry.value) \
            else _scalar(entry, k)
        if v:
            return v
    for c in _child_entries(entry):
        if c.key and c.value:
            return f"{c.key}: {_strip_quotes(c.value)}"
    return entry.value.strip() if entry.value else ""


_LIST_SUMMARY_LIMIT = 5


def _list_summary(entry: YamlEntry) -> str:
    """Tous les noms des elements d'une liste de blocs (ex : presets d'un
    playfield : 'Empty, GrsDnse_04 …'), plafonnee -- permet de voir d'un
    coup d'oeil si la cle n'apporte que le preset 'off' ou de la vraie
    configuration, sans ouvrir le fichier."""
    names = [_strip_quotes(ident[1]) for ident in
             (_identity(item) for item in _seq_items(entry))
             if ident is not None]
    if not names:
        return ""
    shown = ", ".join(names[:_LIST_SUMMARY_LIMIT])
    if len(names) > _LIST_SUMMARY_LIMIT:
        shown += f" … (+{len(names) - _LIST_SUMMARY_LIMIT})"
    return shown


def _strip_quotes(v: str) -> str:
    return v.strip().strip("'\"")


def yaml_files_identical(working_yaml: Path, source_yaml: Path) -> bool:
    try:
        a = Path(working_yaml).read_bytes()
        b = Path(source_yaml).read_bytes()
    except OSError:
        return False
    return a == b


def analyze_yaml_merge(working_yaml: Path,
                       source_yaml: Path) -> List[YamlUnit]:
    """Unites du YAML SOURCE absentes du YAML de la copie de travail :
    cles racines entieres + elements absents des listes de blocs sous une
    cle commune. Fichiers identiques ou illisibles -> []."""
    working_yaml, source_yaml = Path(working_yaml), Path(source_yaml)
    if yaml_files_identical(working_yaml, source_yaml):
        return []
    try:
        working_doc = parse_yaml_file(working_yaml)
        source_doc = parse_yaml_file(source_yaml)
    except Exception:                        # noqa: BLE001 - yaml illisible
        return []
    working_top = _top_entries(working_doc)
    source_top = _top_entries(source_doc)

    def _usable(entries: List[YamlEntry]) -> bool:
        # une ligne binaire/illisible donne une pseudo-entree key=None
        # (fallback du parseur) : pas de fusion structurelle fiable,
        # l'appelant proposera le remplacement explicite
        return any(e.key is not None or e.is_sequence_item for e in entries)

    if not _usable(working_top) or not _usable(source_top):
        return []
    units: List[YamlUnit] = []
    working_keys = {e.key: e for e in working_top if not e.is_sequence_item}
    source_keys = {e.key: e for e in source_top if not e.is_sequence_item}

    def _scan_list(root_label: str, wlist: Optional[YamlEntry],
                   slist: YamlEntry, path: tuple, depth: int) -> None:
        """Elements absents d'une liste de blocs -> unites 'item' ; un
        element PRESENT des deux cotes est explore recursivement (taches,
        actions... ajoutees chez la source, vecu 06/10 : mission PDA
        completee invisible)."""
        if wlist is None or depth > _MAX_DEPTH:
            return
        working_ids = {_identity(c) for c in _seq_items(wlist)}
        # listes a identites NON uniques dans la source (ex : plusieurs
        # items commencant par la meme '- Cle: valeur') : rien a proposer
        # pour ces items, l'appariement a l'application ne serait pas fiable
        source_counts = {}
        for c in _seq_items(slist):
            ident = _identity(c)
            if ident is not None:
                source_counts[ident] = source_counts.get(ident, 0) + 1
        for item in _seq_items(slist):
            ident = _identity(item)
            if ident is None or source_counts[ident] > 1:
                continue
            if ident not in working_ids:
                units.append(YamlUnit(kind="item", root=root_label,
                                      name=ident[1], detail=_detail(item),
                                      idkey=ident[0], path=path))
                continue
            w_item = next((c for c in _seq_items(wlist)
                           if _identity(c) == ident), None)
            if w_item is None:
                continue
            _scan_children(f"{root_label}/{ident[1]}", w_item, item,
                           path + (("item", ident[0], ident[1]),),
                           depth + 1)

    def _scan_children(root_label: str, w_entry: YamlEntry,
                       s_entry: YamlEntry, path: tuple, depth: int) -> None:
        """Sous-listes d'un bloc : absentes de la working -> unite
        'subkey' VISIBLE et cochenable (YAML-009 — avant : skip
        silencieux « convention de l'hote ») ; presentes -> _scan_list."""
        if depth > _MAX_DEPTH:
            return
        for sub in _child_entries(s_entry):
            if sub.is_sequence_item or sub.key is None:
                continue
            if not _seq_items(sub):
                continue
            w_sub = next((c for c in _child_entries(w_entry)
                          if not c.is_sequence_item and c.key == sub.key),
                         None)
            if w_sub is None:
                units.append(YamlUnit(kind="subkey", root=root_label,
                                      name=sub.key,
                                      detail=_list_summary(sub),
                                      path=path))
                continue
            _scan_list(f"{root_label}/{sub.key}", w_sub, sub,
                       path + (("key", sub.key),), depth + 1)

    for key, s_entry in source_keys.items():
        w_entry = working_keys.get(key)
        if w_entry is None:
            units.append(YamlUnit(kind="key", root="", name=key,
                                  detail=_list_summary(s_entry)
                                  or _detail(s_entry)))
            continue
        _scan_list(key, w_entry, s_entry, (("key", key),), 0)
        _scan_children(key, w_entry, s_entry, (("key", key),), 0)
    # document racine = liste de blocs (pas de mappings top-level) : meme
    # comparaison au niveau du document
    source_items = [e for e in source_top if e.is_sequence_item]
    working_items = [e for e in working_top if e.is_sequence_item]
    if source_items and (working_items or not source_keys):
        working_ids = {_identity(c) for c in working_items}
        for item in source_items:
            ident = _identity(item)
            if ident is None:
                continue
            if ident in working_ids:
                w_item = next((c for c in working_items
                               if _identity(c) == ident), None)
                _scan_children(ident[1], w_item, item,
                               (("item", ident[0], ident[1]),), 0)
                continue
            if working_items:
                units.append(YamlUnit(kind="item", root="", name=ident[1],
                                      detail=_detail(item)))
    return units


def _same_identity(ident: Optional[Tuple[str, str]], idkey: str,
                   name: str) -> bool:
    if ident is None:
        return False
    if idkey and ident[0] != idkey:
        return False
    return _strip_quotes(ident[1]).casefold() == name.casefold()


def _eol_of(entries: List[YamlEntry]) -> str:
    for e in entries:
        if e.eol:
            return e.eol
    return "\r\n"


def _ensure_blank_before(children: List, eol: str) -> None:
    if children and not isinstance(children[-1], YamlBlank):
        children.append(YamlBlank(raw=eol))


def _copy_entry(entry: YamlEntry) -> YamlEntry:
    return copy.deepcopy(entry)


def _segments(unit: YamlUnit) -> tuple:
    """Segments de navigation d'une unite : son path exact, ou derive de
    root (cles uniquement) pour les unites sans path (compat)."""
    if unit.path is not None:
        return unit.path
    return tuple(("key", s) for s in unit.root.split("/") if s)


def _walk(entries: List[YamlEntry], segments: tuple) -> Optional[YamlEntry]:
    """Descend des segments ('key', cle) / ('item', cle_identite, valeur)
    depuis des entrees top-level ; retourne l'entree atteinte ou None."""
    cur_list = entries
    cur = None
    for seg in segments:
        if seg[0] == "key":
            cur = next((e for e in cur_list
                        if not e.is_sequence_item and e.key == seg[1]), None)
        else:
            cur = next((e for e in cur_list
                        if e.is_sequence_item
                        and _same_identity(_identity(e), seg[1], seg[2])),
                       None)
        if cur is None:
            return None
        cur_list = _child_entries(cur)
    return cur


def apply_yaml_units(working_yaml: Path, source_yaml: Path,
                     units: List[YamlUnit]) -> int:
    """Insere les unites cochees dans le YAML de la copie de travail
    (rendu yamllite : commentaires preserves) et ecrit en atomique ;
    retourne le nombre d'unites reellement inserees. Idempotent : une
    identite deja presente est ignoree. L'appelant gere backup et undo
    (capture_file AVANT l'appel)."""
    if not units:
        return 0
    working_doc = parse_yaml_file(working_yaml)
    source_doc = parse_yaml_file(source_yaml)
    working_top = _top_entries(working_doc)
    source_top = _top_entries(source_doc)
    eol = _eol_of(working_top)
    applied = 0
    for unit in units:
        if unit.kind == "key":
            src = next((e for e in source_top
                        if not e.is_sequence_item and e.key == unit.name),
                       None)
            already = any(not e.is_sequence_item and e.key == unit.name
                          for e in working_top)
            if src is None or already:
                continue
            clone = _copy_entry(src)
            _ensure_blank_before(working_doc.nodes, eol)
            working_doc.nodes.append(clone)
            working_top.append(clone)
            applied += 1
            continue
        if unit.kind == "subkey":
            # sous-liste absente d'un bloc present (YAML-009) : le path
            # designe le bloc PARENT, on y clone la sous-cle entiere
            w_parent = _walk(working_top, _segments(unit))
            s_parent = _walk(source_top, _segments(unit))
            if w_parent is None or s_parent is None:
                continue
            already = any(not c.is_sequence_item and c.key == unit.name
                          for c in _child_entries(w_parent))
            if already:
                continue
            src = next((c for c in _child_entries(s_parent)
                        if not c.is_sequence_item and c.key == unit.name),
                       None)
            if src is None:
                continue
            clone = _copy_entry(src)
            _ensure_blank_before(w_parent.children, eol)
            w_parent.children.append(clone)
            applied += 1
            continue
        if unit.root == "" and unit.path is None:
            w_items = [e for e in working_top if e.is_sequence_item]
            s_items = [e for e in source_top if e.is_sequence_item]
            attach = working_doc.nodes
        else:
            w_list = _walk(working_top, _segments(unit))
            s_list = _walk(source_top, _segments(unit))
            w_items = _seq_items(w_list) if w_list is not None else []
            s_items = _seq_items(s_list) if s_list is not None else []
            attach = w_list.children if w_list is not None else None
        if not s_items or attach is None:
            continue
        src = next((c for c in s_items
                    if _same_identity(_identity(c), unit.idkey, unit.name)),
                   None)
        if src is None:
            continue
        already = any(_same_identity(_identity(c), unit.idkey, unit.name)
                      for c in w_items)
        if already:
            continue
        clone = _copy_entry(src)
        _ensure_blank_before(attach, eol)
        attach.append(clone)
        applied += 1
    if applied:
        from core.fsutil import atomic_write_text
        atomic_write_text(working_yaml, working_doc.render())
    return applied
