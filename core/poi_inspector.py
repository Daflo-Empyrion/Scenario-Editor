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

"""
Statistiques et agregation par faction des POI d'un playfield -- combien de
drones un joueur peut potentiellement affronter, repartition par faction,
etc. Porte uniquement sur 'POIs > Random' (find_random_poi_items()) : les
POI Fixed n'ont pas ces champs de comptage/probabilite (placements uniques,
pas generes aleatoirement -- confirme sur de vrais playfields).

Champs CountMinMax/DroneProb/DronesMinMax confirmes sur de vrais playfields :
CountMinMax/DronesMinMax sont des listes [min, max], DroneProb est une
fraction 0.0-1.0 (jamais un pourcentage 0-100).
"""
from dataclasses import dataclass, field
from typing import Dict, List

from .playfield_editor import find_random_poi_items, get_item_params, get_properties_value


@dataclass
class PoiStats:
    name: str
    faction: str
    count_min: int = 0
    count_max: int = 0
    drone_prob: float = 0.0
    drones_min: int = 0
    drones_max: int = 0
    regen_after: str = ""
    spawn_near: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def estimated_drones_min(self) -> int:
        return int(self.count_min * self.drone_prob * self.drones_min)

    @property
    def estimated_drones_max(self) -> int:
        return int(self.count_max * min(self.drone_prob, 1.0) * self.drones_max)


@dataclass
class FactionAggregation:
    faction: str
    poi_count: int = 0
    total_drones_min: int = 0
    total_drones_max: int = 0
    poi_names: List[str] = field(default_factory=list)


def _parse_int_or(value, default: int = 0) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _parse_float_or(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _parse_min_max(value) -> tuple:
    """Parse '[ min, max ]' -- confirme sur de vrais playfields pour
    CountMinMax/DronesMinMax."""
    if not value:
        return (0, 0)
    cleaned = value.strip().strip('[]')
    parts = [p.strip() for p in cleaned.split(',')]
    if len(parts) < 2:
        return (0, 0)
    return (_parse_int_or(parts[0]), _parse_int_or(parts[1]))


def compute_poi_stats(doc) -> List[PoiStats]:
    """Calcule les statistiques de chaque POI Random d'un playfield."""
    stats: List[PoiStats] = []
    for item in find_random_poi_items(doc):
        params = dict(get_item_params(item))
        name = params.get("GroupName") or item.value or "?"
        count_min, count_max = _parse_min_max(params.get("CountMinMax"))
        drones_min, drones_max = _parse_min_max(params.get("DronesMinMax"))
        stats.append(PoiStats(
            name=name,
            faction=params.get("Faction", "None"),
            count_min=count_min, count_max=count_max,
            drone_prob=_parse_float_or(params.get("DroneProb")),
            drones_min=drones_min, drones_max=drones_max,
            regen_after=get_properties_value(item, "RegenAfter") or "",
            spawn_near=params.get("SpawnPOINear", ""),
            extra=params,
        ))
    return stats


def aggregate_by_faction(stats: List[PoiStats]) -> Dict[str, FactionAggregation]:
    """Regroupe les statistiques par faction -- utile pour un apercu global
    (combien de drones au total pour chaque faction sur ce playfield)."""
    result: Dict[str, FactionAggregation] = {}
    for s in stats:
        agg = result.setdefault(s.faction, FactionAggregation(faction=s.faction))
        agg.poi_count += 1
        agg.total_drones_min += s.estimated_drones_min
        agg.total_drones_max += s.estimated_drones_max
        agg.poi_names.append(s.name)
    return result
