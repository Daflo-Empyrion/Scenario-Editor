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

"""Ondes de spawn : vue TRANSVERSALE des spawns du scenario (un resume par
playfield : POIs aleatoires, garnisons, vaisseaux spatiaux, drones de
patrouille, zones de taux) et edition GROUPEE des densites (CountMinMax/
DronesMinMax) avec apercu modifiable avant ecriture.

Repose entierement sur les parseurs de core/playfield_editor.py et les stats
de core/poi_inspector.py (Pois Random, DroneBaseSetup planete/espace,
DroneSpawning, SpawnRateZones -- sections confirmees sur de vrais
playfields). NOTE : il n'existe PAS de fichier 'SpaceSpawner.yaml' dans le
jeu ; tout le controle des spawns vit dans les playfields.

Un meme playfield peut repartir ses sections entre plusieurs yaml
(playfield_static + playfield_dynamic) ou n'avoir qu'un space_dynamic.yaml :
tous les *.yaml du dossier sont analises, les totaux sont additionnes.

PERFORMANCE : scan() analyse chaque fichier UNE fois et produit resume +
entrees editables + issues. Sur RE2-ATL-PRO (552 playfields) : ~15 s -- la
boite de dialogue l'appelle hors du thread GUI (gui.ewa_async.async_call)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

from core.ecf.validation import ValidationIssue
from core.parsers_utils import parse_min_max
from core.playfield_editor import (
    find_drone_spawning_items,
    find_drone_stock_items,
    find_fixed_poi_items,
    find_fixed_player_start_items,
    find_free_drones_items,
    find_random_poi_items,
    find_space_vessels_items,
    find_spawn_rate_zones_items,
    get_item_params,
    set_item_param,
)
from core.poi_inspector import compute_poi_stats
from core.yamllite.model import YamlDocument, YamlEntry
from core.yamllite.parser import parse_yaml_file

# types de groupes editables (cles de tableau de la boite de dialogue)
KIND_POI = "poi"              # POIs > Random : CountMinMax (+ garnison DronesMinMax)
KIND_VESSEL = "vessel"        # DroneBaseSetup > SpaceVessels : CountMinMax
KIND_FREEDRONE = "freedrone"  # DroneBaseSetup > FreeDrones : Count
KIND_PATROL = "patrol"        # DroneSpawning > Random : DronesMinMax

_KIND_LABELS = {KIND_POI: "sw.kind.poi", KIND_VESSEL: "sw.kind.vessel",
                KIND_FREEDRONE: "sw.kind.freedrone", KIND_PATROL: "sw.kind.patrol"}


def kind_label_key(kind: str) -> str:
    return _KIND_LABELS[kind]


@dataclass
class PlayfieldSpawnSummary:
    playfield: str
    files: List[Path] = field(default_factory=list)
    pf_type: str = ""
    poi_min: int = 0
    poi_max: int = 0
    drones_min: int = 0            # garnisons POI (estimation poi_inspector)
    drones_max: int = 0
    vessels_min: int = 0
    vessels_max: int = 0
    freedrones_min: int = 0
    freedrones_max: int = 0
    patrol_zones: int = 0          # nombre d'entrees DroneSpawning > Random
    patrol_min: int = 0
    patrol_max: int = 0
    rate_zones: int = 0            # nombre d'entrees SpawnRateZones

    @property
    def total_min(self) -> int:
        return self.poi_min + self.vessels_min + self.freedrones_min + self.patrol_min

    @property
    def total_max(self) -> int:
        return self.poi_max + self.vessels_max + self.freedrones_max + self.patrol_max


@dataclass
class SpawnGroupEntry:
    """Un groupe d'ondes editable : l'entree YAML source reste vivante
    (item/doc), l'ecriture passe par set_item_param."""
    playfield: str
    path: Path
    kind: str
    name: str
    faction: str
    count_min: int
    count_max: int
    probability: float             # 1.0 par defaut (vessels : 'Probability')
    count_key: str                 # 'CountMinMax', 'Count' ou 'DronesMinMax'
    item: YamlEntry
    doc: YamlDocument
    count_is_value: bool = False   # True : le [min,max] est la VALEUR de
                                   # l'item (patrouilles), pas un enfant


@dataclass
class SpawnScanResult:
    summaries: List[PlayfieldSpawnSummary] = field(default_factory=list)
    entries: List[SpawnGroupEntry] = field(default_factory=list)
    issues: List[ValidationIssue] = field(default_factory=list)


def _iter_playfield_yamls(root: Path):
    base = root / "Playfields"
    if not base.is_dir():
        return
    for pf_dir in sorted(base.iterdir()):
        if not pf_dir.is_dir():
            continue
        for yaml_path in sorted(pf_dir.glob("*.yaml")):
            yield pf_dir.name, yaml_path


def _parse_type(doc: YamlDocument, current: str) -> str:
    for node in doc.nodes:
        if isinstance(node, YamlEntry) and node.key == "PlayfieldType":
            return (node.value or "").strip()
    return current


def _min_max_text(cmin: int, cmax: int) -> str:
    if cmax < cmin:
        cmax = cmin
    return f"[{cmin}, {cmax}]"


def _item_min_max(item: YamlEntry, key: str) -> Tuple[int, int]:
    """[min, max] d'un item de liste : la cle peut etre un parametre ENFANT
    (CountMinMax d'un POI/vaisseau) ou la VALEUR de l'item lui-meme
    (DronesMinMax est la cle d'item de find_drone_spawning_items)."""
    params = dict(get_item_params(item))
    return parse_min_max(params.get(key) or item.value)


def scan(root: Path) -> SpawnScanResult:
    """Un SEUL passage par fichier : resume par playfield + entrees editables
    + controles de coherence."""
    result = SpawnScanResult()
    for pf_name, yaml_path in _iter_playfield_yamls(root):
        try:
            doc = parse_yaml_file(yaml_path)
        except Exception:
            continue
        summary = next((s for s in result.summaries if s.playfield == pf_name), None)
        if summary is None:
            summary = PlayfieldSpawnSummary(playfield=pf_name)
            result.summaries.append(summary)
        summary.files.append(yaml_path)
        summary.pf_type = _parse_type(doc, summary.pf_type)

        for stats in compute_poi_stats(doc):
            summary.poi_min += stats.count_min
            summary.poi_max += stats.count_max
            summary.drones_min += stats.estimated_drones_min
            summary.drones_max += stats.estimated_drones_max
            if stats.item is not None:
                result.entries.append(SpawnGroupEntry(
                    playfield=pf_name, path=yaml_path, kind=KIND_POI,
                    name=stats.name, faction=stats.faction,
                    count_min=stats.count_min, count_max=stats.count_max,
                    probability=stats.drone_prob, count_key="CountMinMax",
                    item=stats.item, doc=doc))

        for item in find_space_vessels_items(doc):
            params = dict(get_item_params(item))
            cmin, cmax = parse_min_max(params.get("CountMinMax"))
            prob = float(params.get("Probability") or 1.0)
            summary.vessels_min += int(cmin * prob)
            summary.vessels_max += int(cmax * min(prob, 1.0))
            result.entries.append(SpawnGroupEntry(
                playfield=pf_name, path=yaml_path, kind=KIND_VESSEL,
                name=params.get("Name") or "?", faction=params.get("Faction", ""),
                count_min=cmin, count_max=cmax, probability=prob,
                count_key="CountMinMax", item=item, doc=doc))

        for item in find_free_drones_items(doc):
            params = dict(get_item_params(item))
            cmin, cmax = parse_min_max(params.get("Count"))
            summary.freedrones_min += cmin
            summary.freedrones_max += cmax
            result.entries.append(SpawnGroupEntry(
                playfield=pf_name, path=yaml_path, kind=KIND_FREEDRONE,
                name=params.get("Name") or "?", faction=params.get("Faction", ""),
                count_min=cmin, count_max=cmax, probability=1.0,
                count_key="Count", item=item, doc=doc))

        for item in find_drone_spawning_items(doc):
            cmin, cmax = _item_min_max(item, "DronesMinMax")
            summary.patrol_zones += 1
            summary.patrol_min += cmin
            summary.patrol_max += cmax
            center = (dict(get_item_params(item)).get("CenterX")
                      or dict(get_item_params(item)).get("CenterY")
                      or dict(get_item_params(item)).get("CenterZ") or "")
            result.entries.append(SpawnGroupEntry(
                playfield=pf_name, path=yaml_path, kind=KIND_PATROL,
                name=f"Center {center.strip()}" if center else "?", faction="",
                count_min=cmin, count_max=cmax, probability=1.0,
                count_key="DronesMinMax", count_is_value=True,
                item=item, doc=doc))

        summary.rate_zones += len(find_spawn_rate_zones_items(doc))
        _check_one_playfield(pf_name, yaml_path, doc, result.issues)
    return result


def scale_count(entry: SpawnGroupEntry, factor: float) -> Tuple[int, int]:
    """Nouveau [min, max] apres application du facteur (arrondi, max >= min,
    plancher 0) -- SANS toucher l'entree : le resultat sert d'apercu."""
    cmin = max(0, int(round(entry.count_min * factor)))
    cmax = max(0, int(round(entry.count_max * factor)))
    return (min(cmin, cmax), max(cmin, cmax))


def apply_count(entry: SpawnGroupEntry, cmin: int, cmax: int) -> bool:
    """Ecrit le nouveau [min, max] sur l'entree vivante (pas de fichier --
    apply_changes se charge de l'ecriture disque)."""
    text = _min_max_text(cmin, cmax)
    if entry.count_is_value:
        entry.item.set_own_value(text)
        entry.count_min, entry.count_max = cmin, cmax
        return True
    if not set_item_param(entry.item, entry.count_key, text):
        return False
    entry.count_min, entry.count_max = cmin, cmax
    return True


def apply_changes(entries: List[SpawnGroupEntry]) -> Dict[Path, int]:
    """Ecrit un fichier par groupe de chemin : backup central puis ecriture
    atomique du rendu YAML (commentaires et mise en forme preserves)."""
    from core.fsutil import atomic_write_text, central_backup  # local : monkeypatch conftest
    by_path: Dict[Path, List[SpawnGroupEntry]] = {}
    for entry in entries:
        by_path.setdefault(entry.path, []).append(entry)
    done: Dict[Path, int] = {}
    for path, items in by_path.items():
        central_backup(path, "spawn_waves")
        atomic_write_text(path, items[0].doc.render())
        done[path] = len(items)
    return done


# ============================================================================
# Controles de coherence (issues pour la vue ; integrables au bilan)
# ============================================================================

def check_spawn_consistency(root: Path) -> List[ValidationIssue]:
    """Raccourci bilan : scan reduit aux issues uniquement."""
    return scan(root).issues


def _check_one_playfield(pf_name: str, yaml_path: Path, doc: YamlDocument,
                         issues: List[ValidationIssue]) -> None:
    """Deux regles a faible risque de faux positifs (calibrees sur la vanilla
    Eden / RE2 : les geantes gazeuses ont des patrouilles DronesMinMax [0, 0]
    VOLONTAIRES -- jamais alertees) :
    - patrouilles de drones planetaires ACTIVES (min ou max > 0) sans AUCUNE
      base de drones (Stock du DroneBaseSetup absent) : le jeu ne lance les
      patrouilles que depuis une base -- playfield inerte ;
    - SpawnRateZones > SpawnAt designant un POI/plage inconnu du playfield
      (zone de suppression/amplification jamais appliquee). 'START' et les
      modes de FixedPlayerStart sont exclus."""
    patrols = find_drone_spawning_items(doc)
    active = [p for p in patrols if max(_item_min_max(p, "DronesMinMax")) > 0]
    if active and not find_drone_stock_items(doc):
        issues.append(ValidationIssue(
            code="W310", level="warning",
            message=f"{pf_name}: {len(active)} zone(s) de patrouille de drones "
                    f"active(s) mais aucune base de drones (DroneBaseSetup > "
                    f"Stock) -- patrouilles inertes",
            file_path=yaml_path))

    known = _spawnable_names(doc)
    for item in find_spawn_rate_zones_items(doc):
        # SpawnAt est la CLE D'ITEM de la section : sa valeur est sur
        # l'item lui-meme, pas parmi les enfants.
        spawn_at = dict(get_item_params(item)).get("SpawnAt") or item.value
        names = [n for n in _bracket_list(spawn_at) if n]
        # Une liste mixte (noms valides + POI desactives/commentes) reste
        # appliquee pour ses noms valides : n'alerter que si AUCUN nom ne
        # designe un POI du playfield (vecu AlienLegacy : zones survivantes
        # de POIs passes en commentaire, qui gardent aussi des noms valides).
        if names and not any(n in known for n in names):
            issues.append(ValidationIssue(
                code="W311", level="warning",
                message=f"{pf_name}: SpawnRateZones > SpawnAt: [{', '.join(names)}] "
                        f"ne designe aucun POI du playfield -- zone jamais "
                        f"appliquee",
                file_path=yaml_path))


def _bracket_list(value) -> List[str]:
    if not value:
        return []
    return [p.strip().strip('"\'') for p in value.strip().strip("[]").split(",") if p.strip()]


def _spawnable_names(doc: YamlDocument) -> set:
    names = {"START"}
    for item in find_random_poi_items(doc) + find_fixed_poi_items(doc):
        params = dict(get_item_params(item))
        if params.get("GroupName"):
            names.add(params["GroupName"].strip())
        elif item.value:
            names.add(str(item.value).strip())
    for item in find_fixed_player_start_items(doc):
        params = dict(get_item_params(item))
        if params.get("Mode"):
            names.add(params["Mode"].strip())
    return names
