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

"""Reglage du danger du scenario : un PALIER = une table de coefficients par
domaine, appliquee en APERCU MODIFIABLE a tout le scenario.

Formats reels (verifies sur RE2 + vanilla) :
- spawns    : playfield_static `POIs > Random` -> CountMinMax, et la
              garnison DronesMinMax quand elle existe (DroneProb est une
              CHANCE, jamais une quantite : non multipliee) ;
- patrols   : `DroneSpawning` (valeur de l'item), `DroneBaseSetup >
              SpaceVessels` (CountMinMax) et `FreeDrones` (Count),
              `SpawnRateZones` (RateMultiplyer, jamais ceux a 0 = zones de
              securite volontaires) ;
- resources : asteroid espace `Resources > CountMinMax`, et densites de
              minerai de planete, ecrites en listes flow dans les blocs de
              biome : `- [RockResourceIron, 0.002, Free]` (2e champ) ;
- loot      : `LootGroups` (quantite = param1, entier ou "a,b") et
              `Containers` (quantite = param2 "a,b" ; sans param2 la quantite
              vaut 1 et n'est pas touchee) ;
- reputation: `DefReputation` (valeur par faction ; les 0 restent a 0).

GARDE-FOUS (demandes explicitement) :
- bornes dures : jamais < 0, plafond x3 par entree, min <= max ;
- un POI `IsImportant: True` garde au moins 1 ; les POI rattaches a START
  (zone de depart) ne sont JAMAIS touches ;
- un palier qui amenerait TOUT un domaine a zero est REFUSE ;
- rien n'est applique sans apercu : les entrees naissent decochees.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.ecf.model import EcfBlock, EcfProperty
from core.ecf.parser import parse_ecf_file
from core.parsers_utils import parse_min_max
from core.playfield_editor import (find_drone_spawning_items,
                                   find_free_drones_items,
                                   find_space_vessels_items,
                                   find_spawn_rate_zones_items,
                                   get_item_params)
from core.poi_inspector import compute_poi_stats
from core.yamllite.model import YamlEntry
from core.yamllite.parser import parse_yaml_file

DOMAIN_SPAWNS = "spawns"
DOMAIN_PATROLS = "patrols"
DOMAIN_RESOURCES = "resources"
DOMAIN_LOOT = "loot"
DOMAIN_REPUTATION = "reputation"

DOMAINS = (DOMAIN_SPAWNS, DOMAIN_PATROLS, DOMAIN_RESOURCES, DOMAIN_LOOT,
           DOMAIN_REPUTATION)

MAX_FACTOR = 3.0        # plafond par entree, en plus ou en moins

# Un palier = politique coherente : plus dur = plus de dangers, moins de
# ressources et de butin. 'normal' ne change rien (coefficients a 1).
PRESETS: Dict[str, Dict[str, float]] = {
    "tres_facile": {DOMAIN_SPAWNS: 0.5, DOMAIN_PATROLS: 0.5,
                    DOMAIN_RESOURCES: 1.5, DOMAIN_LOOT: 1.5,
                    DOMAIN_REPUTATION: 1.0},
    "facile": {DOMAIN_SPAWNS: 0.75, DOMAIN_PATROLS: 0.75,
               DOMAIN_RESOURCES: 1.25, DOMAIN_LOOT: 1.25,
               DOMAIN_REPUTATION: 1.0},
    "normal": {domain: 1.0 for domain in DOMAINS},
    "difficile": {DOMAIN_SPAWNS: 1.35, DOMAIN_PATROLS: 1.35,
                  DOMAIN_RESOURCES: 0.8, DOMAIN_LOOT: 0.8,
                  DOMAIN_REPUTATION: 1.0},
    "cauchemar": {DOMAIN_SPAWNS: 1.8, DOMAIN_PATROLS: 1.8,
                  DOMAIN_RESOURCES: 0.6, DOMAIN_LOOT: 0.6,
                  DOMAIN_REPUTATION: 1.0},
}

PRESET_ORDER = ("tres_facile", "facile", "normal", "difficile", "cauchemar")


@dataclass
class TuneEntry:
    """Une valeur reglable, avec son ancienne et sa nouvelle valeur."""
    domain: str
    path: Path
    target: str                  # 'playfield / groupe', 'fichier / bloc'
    kind: str                    # minmax | item_value | flow_density | ecf_param
    old_value: float
    new_value: float
    old_min_raw: int = 0
    old_max_raw: int = 0
    new_min_raw: int = 0
    new_max_raw: int = 0
    # objet vivant selon le kind
    item: Optional[YamlEntry] = None
    key: str = ""
    value_is_item: bool = False
    flow_index: int = 0
    prop: Optional[EcfProperty] = None
    pair_key: str = ""
    is_range: bool = False
    doc: object = None
    blocked: str = ""            # raison de non-modification (garde-fou)
    checked: bool = False        # rien de precoche

    @property
    def editable(self) -> bool:
        return not self.blocked

    def label_value(self, value: float) -> str:
        if self.is_range or self.kind == "minmax":
            return f"{int(round(value))}"
        if self.kind == "flow_density":
            return f"{value:.6g}"      # densites ~1e-4 : 'g' seul tronque
        return f"{value:g}"


@dataclass
class TunePlan:
    entries: List[TuneEntry] = field(default_factory=list)
    refusals: List[str] = field(default_factory=list)
    files: Dict[Path, object] = field(default_factory=dict)


def _clamp(entry: TuneEntry, value: float) -> Tuple[float, str]:
    """Bornes dures : >= 0, <= ancien x MAX_FACTOR (et symetriquement pour
    une baisse : >= ancien / MAX_FACTOR quand l'ancien est > 0)."""
    if value < 0:
        return 0.0, "borne basse 0"
    if entry.old_value > 0 and value > entry.old_value * MAX_FACTOR:
        return entry.old_value * MAX_FACTOR, f"plafond x{MAX_FACTOR:g}"
    if entry.old_value > 0 and value < entry.old_value / MAX_FACTOR:
        return entry.old_value / MAX_FACTOR, f"plancher /{MAX_FACTOR:g}"
    return value, ""


def _min_max_text(cmin: int, cmax: int) -> str:
    return f"[{cmin}, {cmax}]"


def _int_or(value, default=0) -> int:
    try:
        return int(round(float(str(value).strip().strip('"')))) 
    except (TypeError, ValueError):
        return default


def _range_values(text: str) -> Optional[Tuple[int, int]]:
    """'1' -> (1,1) ; '"2,3"' -> (2,3) ; sinon None."""
    raw = str(text or "").strip().strip('"')
    if not raw:
        return None
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if len(parts) == 1:
        value = _int_or(parts[0], -1)
        return (value, value) if value >= 0 else None
    if len(parts) >= 2:
        low, high = _int_or(parts[0], -1), _int_or(parts[1], -1)
        if low >= 0 and high >= 0:
            return (min(low, high), max(low, high))
    return None


def _iter_playfield_yamls(root: Path):
    base = Path(root) / "Playfields"
    if not base.is_dir():
        return
    for pf_dir in sorted(base.iterdir()):
        if not pf_dir.is_dir():
            continue
        for yaml_path in sorted(pf_dir.glob("*.yaml")):
            yield pf_dir.name, yaml_path


# ============================================================================
# Collecte par domaine
# ============================================================================

def _collect_spawns(name: str, path: Path, doc, plan: TunePlan,
                    coeff: float) -> None:
    for stats in compute_poi_stats(doc):
        if stats.item is None:
            continue
        params = dict(get_item_params(stats.item))
        label = f"{name} / {stats.name}"
        near_start = "START" in (params.get("SpawnPOINear") or "")
        important = (params.get("IsImportant") or "").strip().lower() in (
            "true", "1", "yes")
        for key in ("CountMinMax", "DronesMinMax"):
            old_min, old_max = parse_min_max(params.get(key))
            if key not in params or (old_min == 0 and old_max == 0):
                continue
            entry = TuneEntry(
                domain=DOMAIN_SPAWNS, path=path, target=f"{label} {key}",
                kind="minmax", old_value=float(old_max), new_value=0.0,
                item=stats.item, key=key, doc=doc)
            if near_start:
                entry.blocked = "zone START (jamais touchee)"
            elif important and key == "CountMinMax":
                entry.blocked = "POI IsImportant (garde au moins 1)"
            _finish(entry, old_min, old_max, coeff)
            plan.entries.append(entry)


def _collect_patrols(name: str, path: Path, doc, plan: TunePlan,
                     coeff: float) -> None:
    for index, item in enumerate(find_drone_spawning_items(doc), 1):
        old_min, old_max = parse_min_max(item.value)
        if old_min == old_max == 0:
            continue                  # zone de securite volontaire
        entry = TuneEntry(
            domain=DOMAIN_PATROLS, path=path,
            target=f"{name} / patrouille {index} ({_center(item)})",
            kind="item_value", old_value=float(old_max), new_value=0.0,
            item=item, doc=doc)
        _finish(entry, old_min, old_max, coeff)
        plan.entries.append(entry)
    for item in find_space_vessels_items(doc):
        params = dict(get_item_params(item))
        old_min, old_max = parse_min_max(params.get("CountMinMax"))
        if "CountMinMax" not in params:
            continue
        entry = TuneEntry(
            domain=DOMAIN_PATROLS, path=path,
            target=f"{name} / vaisseau {params.get('Name', '?')}",
            kind="minmax", old_value=float(old_max), new_value=0.0,
            item=item, key="CountMinMax", doc=doc)
        _finish(entry, old_min, old_max, coeff)
        plan.entries.append(entry)
    for item in find_free_drones_items(doc):
        params = dict(get_item_params(item))
        old_min, old_max = parse_min_max(params.get("Count"))
        if "Count" not in params:
            continue
        entry = TuneEntry(
            domain=DOMAIN_PATROLS, path=path,
            target=f"{name} / drone libre {params.get('Name', '?')}",
            kind="minmax", old_value=float(old_max), new_value=0.0,
            item=item, key="Count", doc=doc)
        _finish(entry, old_min, old_max, coeff)
        plan.entries.append(entry)
    for item in find_spawn_rate_zones_items(doc):
        params = dict(get_item_params(item))
        for key in ("RateMultiplyerCenter", "RateMultiplyerEdge"):
            if key not in params:
                continue
            old = float(params.get(key) or 0)
            if old <= 0:
                continue              # 0 = zone de securite volontaire
            entry = TuneEntry(
                domain=DOMAIN_PATROLS, path=path,
                target=f"{name} / taux {key}",
                kind="item_value", old_value=old, new_value=0.0,
                item=item, key=key, doc=doc)
            entry.old_min_raw = entry.old_max_raw = int(round(old))
            entry.new_value, note = _clamp(entry, old * coeff)
            entry.new_min_raw = entry.new_max_raw = int(round(entry.new_value))
            if note:
                entry.blocked = note
            plan.entries.append(entry)


def _center(item: YamlEntry) -> str:
    params = dict(get_item_params(item))
    value = (params.get("CenterX") or params.get("CenterY")
             or params.get("CenterZ") or "").strip()
    return f"Center {value}" if value else "zone"


def _collect_resources(name: str, path: Path, doc, plan: TunePlan,
                       coeff: float) -> None:
    # asteroides : reperes par le prefixe stable 'AsteroidVoxel' de leur Nom +
    # un CountMinMax — le rattachement a la section 'Resources:' n'est pas
    # fiable (sequence au niveau 0 : le parseur la detache selon les fichiers)
    for item in _asteroid_items(doc):
        params = dict(get_item_params(item))
        old_min, old_max = parse_min_max(params.get("CountMinMax"))
        entry = TuneEntry(
            domain=DOMAIN_RESOURCES, path=path,
            target=f"{name} / ressource {_resource_label(params, item)}",
            kind="minmax", old_value=float(old_max), new_value=0.0,
            item=item, key="CountMinMax", doc=doc)
        _finish(entry, old_min, old_max, coeff)
        plan.entries.append(entry)
    # densites de planete : listes flow [RockResourceX, densite, type]
    for item in _flow_resource_items(doc):
        parts = _split_flow(item.value)
        if len(parts) < 2:
            continue
        try:
            old = float(parts[1])
        except ValueError:
            continue
        entry = TuneEntry(
            domain=DOMAIN_RESOURCES, path=path,
            target=f"{name} / densite {parts[0]}",
            kind="flow_density", old_value=old, new_value=0.0,
            item=item, flow_index=1, doc=doc)
        entry.new_value, note = _clamp(entry, old * coeff)
        if note:
            entry.blocked = note
        plan.entries.append(entry)


def _asteroid_items(doc) -> List[YamlEntry]:
    found: List[YamlEntry] = []

    def walk(nodes):
        for node in nodes:
            if not isinstance(node, YamlEntry):
                continue
            if (node.key == "Name" and "AsteroidVoxel" in (node.value or "")
                    and node.get("CountMinMax") is not None):
                found.append(node)
            walk(node.children)

    walk(getattr(doc, "nodes", []))
    return found


def _resource_label(params: dict, item=None) -> str:
    label = params.get("DisplayName") or params.get("Name")
    if not label and item is not None:
        label = item.value          # 'Name' est la CLE d'item des asteroides
    return str(label or "?")


def _flow_resource_items(doc) -> List[YamlEntry]:
    found: List[YamlEntry] = []

    def walk(nodes):
        for node in nodes:
            if not isinstance(node, YamlEntry):
                continue
            value = (node.value or "").strip()
            if (node.key is None and value.startswith("[")
                    and "Resource" in value):
                found.append(node)
            walk(node.children)

    walk(getattr(doc, "nodes", []))
    return found


def _split_flow(text: str) -> List[str]:
    body = (text or "").strip()
    if body.startswith("["):
        body = body[1:]
    if body.endswith("]"):
        body = body[:-1]
    return [part.strip() for part in body.split(",") if part.strip()]


def _finish(entry: TuneEntry, old_min: int, old_max: int,
            coeff: float) -> None:
    entry.old_min_raw, entry.old_max_raw = old_min, old_max
    entry.new_min_raw, entry.new_max_raw = old_min, old_max
    if entry.blocked:
        entry.new_value = float(old_max)
        return
    entry.new_min_raw = max(0, int(round(old_min * coeff)))
    new_max = max(0, int(round(old_max * coeff)))
    if entry.kind == "minmax" and entry.blocked == "":
        new_max = max(new_max, entry.new_min_raw)
    if entry.old_value > 0 and new_max > entry.old_value * MAX_FACTOR:
        # le plafond s'applique sans bloquer (ce n'est pas une erreur)
        new_max = int(round(entry.old_value * MAX_FACTOR))
    entry.new_max_raw = new_max
    entry.new_min_raw = min(entry.new_min_raw, new_max)
    entry.new_value = float(new_max)


# --- butin / reputation (ECF) ----------------------------------------------

def _collect_loot(root: Path, plan: TunePlan, coeff: float) -> None:
    config = Path(root) / "Content" / "Configuration"
    for filename, pair_key, has_range in (("LootGroups.ecf", "param1", True),
                                          ("Containers.ecf", "param2", True)):
        path = config / filename
        if not path.is_file():
            continue
        try:
            doc = parse_ecf_file(path)
        except Exception:                       # noqa: BLE001
            continue
        plan.files[path] = doc
        for block in doc.iter_blocks():
            for prop in block.children:
                if not isinstance(prop, EcfProperty):
                    continue
                _loot_line(prop, pair_key, path, doc, plan, coeff, filename)


def _loot_line(prop: EcfProperty, pair_key: str, path: Path, doc,
               plan: TunePlan, coeff: float, filename: str) -> None:
    pairs = dict(prop.pairs)
    identity = pairs.get("Name_0") or pairs.get("Item_0")         or pairs.get("Group_0") or next(iter(pairs.values()), "")
    raw = pairs.get(pair_key)
    if raw is None:
        return
    values = _range_values(raw)
    if values is None:
        return
    old_min, old_max = values
    if old_min == old_max == 0:
        return
    entry = TuneEntry(
        domain=DOMAIN_LOOT, path=path,
        target=f"{filename} / {identity or '?'}",
        kind="ecf_param", old_value=float(old_max), new_value=0.0,
        prop=prop, pair_key=pair_key, is_range=(old_min != old_max), doc=doc)
    new_min = max(0, int(round(old_min * coeff)))
    new_max = max(0, int(round(old_max * coeff)))
    new_max = max(new_max, new_min)
    entry.old_min_raw, entry.old_max_raw = old_min, old_max
    entry.new_min_raw, entry.new_max_raw = new_min, new_max
    entry.new_value = float(new_max)
    plan.entries.append(entry)


def _collect_reputation(root: Path, plan: TunePlan, coeff: float) -> None:
    path = Path(root) / "Content" / "Configuration" / "DefReputation.ecf"
    if not path.is_file():
        return
    try:
        doc = parse_ecf_file(path)
    except Exception:                           # noqa: BLE001
        return
    plan.files[path] = doc
    for block in doc.iter_blocks():
        for prop in block.children:
            if not isinstance(prop, EcfProperty):
                continue
            for key, value in list(prop.pairs):
                old = _int_or(value, 0)
                if old <= 0:
                    continue                  # 0 = hostilite par defaut
                entry = TuneEntry(
                    domain=DOMAIN_REPUTATION, path=path,
                    target=f"reputation / {key}", kind="ecf_param",
                    old_value=float(old), new_value=0.0,
                    prop=prop, pair_key=key, doc=doc)
                entry.old_min_raw = entry.old_max_raw = old
                entry.new_min_raw = entry.new_max_raw = max(
                    0, int(round(old * coeff)))
                entry.new_value = float(entry.new_max_raw)
                plan.entries.append(entry)


# ============================================================================
# Plan
# ============================================================================

def build_plan(root: Path, coefficients: Dict[str, float]) -> TunePlan:
    """Collecte toutes les valeurs reglables et calcule les nouvelles selon
    les coefficients (un coefficient non fourni vaut 1 = domaine inchange)."""
    plan = TunePlan()
    coeffs = {domain: float(coefficients.get(domain, 1.0))
              for domain in DOMAINS}
    for name, path in _iter_playfield_yamls(root):
        try:
            doc = parse_yaml_file(path)
        except Exception:                       # noqa: BLE001 - illisible
            continue
        plan.files[path] = doc
        _collect_spawns(name, path, doc, plan, coeffs[DOMAIN_SPAWNS])
        _collect_patrols(name, path, doc, plan, coeffs[DOMAIN_PATROLS])
        _collect_resources(name, path, doc, plan, coeffs[DOMAIN_RESOURCES])
    _collect_loot(root, plan, coeffs[DOMAIN_LOOT])
    _collect_reputation(root, plan, coeffs[DOMAIN_REPUTATION])
    # une entree qui ne change RIEN (arrondi, coefficient 1) n'a pas sa place
    # dans un apercu de plusieurs milliers de lignes
    changed = {domain for domain, coeff in coeffs.items() if coeff != 1.0}
    plan.entries = [
        e for e in plan.entries
        # une entree BLOQUEE n'apparait que si son domaine est reellement
        # regle : l'apercu montre alors ce que les garde-fous protegent
        if (e.blocked and e.domain in changed)
        or (e.new_min_raw, e.new_max_raw) != (e.old_min_raw, e.old_max_raw)
        or abs(e.new_value - e.old_value) > 1e-12]
    _detect_destructive(plan, coeffs)
    return plan


def _detect_destructive(plan: TunePlan, coeffs: Dict[str, float]) -> None:
    """Refuse un palier qui viderait un domaine : un coefficient nul, ou
    toutes les valeurs d'un domaine ramenees a zero."""
    for domain in DOMAINS:
        if coeffs.get(domain, 1.0) <= 0:
            plan.refusals.append(
                f"coefficient nul pour '{domain}' : domaine vide")
            continue
        if coeffs.get(domain, 1.0) == 1.0:
            continue
        editable = [e for e in plan.entries
                    if e.domain == domain and not e.blocked]
        if domain in (DOMAIN_SPAWNS, DOMAIN_PATROLS) and editable and \
                all(e.new_value <= 0 for e in editable):
            plan.refusals.append(
                f"'{domain}' : toutes les valeurs tomberaient a zero")


def apply_entries(entries: List[TuneEntry]) -> Dict[Path, int]:
    """Ecrit les entrees retenues : backup central par fichier, ecriture
    atomique du document rendu. Retourne le nombre d'entrees par fichier."""
    from core.fsutil import atomic_write_text, central_backup
    by_path: Dict[Path, List[TuneEntry]] = {}
    for entry in entries:
        by_path.setdefault(entry.path, []).append(entry)
    done: Dict[Path, int] = {}
    for path, items in by_path.items():
        for entry in items:
            _write_one(entry)
        central_backup(path, "difficulty")
        doc = items[0].doc
        atomic_write_text(path, doc.render())
        done[path] = len(items)
    return done


def _write_one(entry: TuneEntry) -> None:
    if entry.kind == "minmax":
        text = _min_max_text(int(entry.new_min_raw),
                             int(entry.new_max_raw))
        entry.item.set(entry.key, text)
    elif entry.kind == "item_value":
        if entry.item.key is None:
            entry.item.set_own_value(_min_max_text(int(entry.new_min_raw),
                                                   int(entry.new_max_raw)))
        else:
            entry.item.set(entry.key, f"{entry.new_value:g}")
    elif entry.kind == "flow_density":
        parts = _split_flow(entry.item.value)
        parts[entry.flow_index] = f"{entry.new_value:.10g}"
        entry.item.set_own_value("[" + ", ".join(parts) + "]")
    elif entry.kind == "ecf_param":
        if entry.is_range:
            low, high = int(entry.new_min_raw), int(entry.new_max_raw)
            entry.prop.set(entry.pair_key, f'"{low},{high}"')
        else:
            entry.prop.set(entry.pair_key, f"{int(entry.new_value)}")


# ---------------------------------------------------------------------------
# Annulation DURABLE : l'etat AVANT application est archive sur disque —
# vecu 29/10/2026 : _undo en memoire seule = retour impossible apres
# fermeture du dialogue, l'utilisateur restait coince sur une passe trop
# dure (200 % POI/vaisseaux, 10 % ressources).
# ---------------------------------------------------------------------------

def undo_backup_root() -> Path:
    return Path.home() / ".empyrion_editor" / "backups" / "difficulty"


def save_undo_snapshot(before: Dict[Path, str]) -> Optional[Path]:
    """Archive l'etat AVANT application dans un dossier horodate (cumul)
    + manifest.json des chemins d'origine. Retourne le dossier, None si
    rien a archiver."""
    if not before:
        return None
    import json
    from core.fsutil import atomic_write_text
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snap = undo_backup_root() / f"application_{stamp}"
    snap.mkdir(parents=True, exist_ok=True)
    manifest = []
    for i, (path, text) in enumerate(sorted(before.items())):
        fname = f"f{i:03d}{''.join(path.suffixes)}"
        atomic_write_text(snap / fname, text)
        manifest.append({"path": str(path), "file": fname})
    atomic_write_text(snap / "manifest.json",
                      json.dumps(manifest, ensure_ascii=False))
    return snap


def list_undo_snapshots() -> List[Path]:
    root = undo_backup_root()
    if not root.is_dir():
        return []
    return [p for p in sorted(root.iterdir())
            if p.is_dir() and (p / "manifest.json").is_file()]


def restore_undo_snapshot(snap: Path) -> Tuple[int, str]:
    """Remonte une application : chaque fichier actuel est archive
    d'abord (central_backup), puis le contenu d'origine est reecrit ; les
    caches .bin des yaml playfields sont invalides. Retourne
    (nb restaures, repertoire d'archive — '' si aucun)."""
    import json
    from core.fsutil import atomic_write_text, central_backup
    manifest = json.loads((snap / "manifest.json").read_text(
        encoding="utf-8"))
    restored = 0
    safety_dir = ""
    for item in manifest:
        p = Path(item["path"])
        if not p.is_file():
            continue
        safety = central_backup(p, "difficulty")
        safety_dir = str(safety.parent)
        atomic_write_text(p, (snap / item["file"]).read_text(
            encoding="utf-8"))
        if p.suffix.lower() == ".yaml":
            cache = Path(str(p) + ".bin")
            if cache.exists():
                cache.unlink()
        restored += 1
    return restored, safety_dir
