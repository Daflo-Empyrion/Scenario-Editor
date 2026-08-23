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
Extraction des entites d'un playfield pour affichage sur un canvas 2D
top-down (axe X horizontal, axe Z vertical -- axe Y/hauteur ignore pour la
2D mais conserve dans les donnees pour une restitution fidele lors des
modifications).

Reutilise systematiquement les fonctions deja verifiees de
core/playfield_editor.py plutot que de reimplementer une extraction --
trois structures ont ete confirmees FAUSSES lors de l'analyse d'un patch
propose (voir l'historique du projet), toutes corrigees ici :
- 'POIs > Fixed' 'fuit' au niveau racine du document a cause du meme piege de
  commentaires a indentation zero que 'Random' -- gere via
  find_fixed_poi_items()/find_random_poi_items()/find_fixed_player_start_items(),
  qui utilisent la technique robuste par plage d'indices + suivi de
  sous-section (meme principe que FreeDrones/SpaceVessels).
- 'RadialInfo' des ressources spatiales (playfields espace) n'est PAS une
  position cartesienne X,Y,Z directe -- confirme sur un vrai
  space_dynamic.yaml : les 3 premieres valeurs sont TOUJOURS a zero
  ([0, 0, 0, 100, 2, 4] partout), ce qui empilerait toutes les ressources au
  meme point. Position volontairement laissee a None pour ces entrees plutot
  que d'afficher une position fausse -- a elucider avec une source fiable
  avant d'etre exploitee.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .yamllite.model import YamlEntry
from .playfield_editor import (
    find_fixed_poi_items, find_random_poi_items, find_fixed_player_start_items,
    find_drone_spawning_items, find_spawn_zones_items, find_spawn_rate_zones_items,
    find_space_resource_items, get_space_resource_display_name,
    get_item_params,
)


FACTION_COLORS = {
    "Zirax": "#d32f2f",
    "Talon": "#388e3c",
    "Polaris": "#1976d2",
    "Alien": "#7b1fa2",
    "Eden_Drone": "#616161",
    "Eden_DroneHome": "#424242",
    "Eden_Abandoned": "#5d4037",
    "Colonists": "#fbc02d",
    "Civilian": "#ffb74d",
    "Trader": "#00897b",
    "Prey": "#8bc34a",
    "Admin": "#000000",
    "None": "#9e9e9e",
}


@dataclass
class CanvasEntity:
    """Une entite a afficher sur le canvas."""
    kind: str
    name: str
    position: Optional[Tuple[float, float, float]] = None
    radius: Optional[float] = None
    faction: str = "None"
    extra: dict = field(default_factory=dict)
    source_item: Optional[YamlEntry] = None
    # Nom de la propriete du YAML source qui porte la position absolue (ex:
    # 'Pos') -- necessaire pour ecrire une nouvelle position lors d'un
    # deplacement, None si l'entite n'a pas de position modifiable
    # directement (ex: position resolue indirectement via un autre POI).
    pos_property_key: Optional[str] = None


def _parse_pos(value: Optional[str]) -> Optional[Tuple[float, float, float]]:
    """Parse 'Pos: [ x, y, z ]' -- confirme sur de vrais playfields (Fixed
    POI, FixedPlayerStart)."""
    if not value:
        return None
    cleaned = value.strip().strip('[]')
    parts = [p.strip() for p in cleaned.split(',')]
    if len(parts) < 2:
        return None
    try:
        coords = [float(p) for p in parts[:3]]
        while len(coords) < 3:
            coords.append(0.0)
        return (coords[0], coords[1], coords[2])
    except ValueError:
        return None


def _parse_list_value(value: Optional[str]) -> List[str]:
    if not value:
        return []
    cleaned = value.strip().strip('[]')
    return [p.strip() for p in cleaned.split(',') if p.strip()]


def _parse_float_or_none(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def extract_canvas_entities(doc) -> List[CanvasEntity]:
    """Extrait toutes les entites affichables d'un playfield, en reutilisant
    exclusivement les fonctions de core/playfield_editor.py deja verifiees
    contre de vrais fichiers plutot que de reimplementer une extraction."""
    entities: List[CanvasEntity] = []

    fixed_positions: Dict[str, Tuple[float, float, float]] = {}
    for item in find_fixed_poi_items(doc):
        params = dict(get_item_params(item))
        pos = _parse_pos(params.get("Pos"))
        name = params.get("Name") or item.value or "?"
        faction = params.get("Faction", "None")
        if pos:
            fixed_positions[name] = pos
        entities.append(CanvasEntity(
            kind="poi_fixed", name=name, position=pos, faction=faction,
            extra=params, source_item=item, pos_property_key="Pos",
        ))

    for item in find_random_poi_items(doc):
        params = dict(get_item_params(item))
        name = params.get("GroupName") or item.value or "?"
        faction = params.get("Faction", "None")
        # Tente de resoudre une position approximative via SpawnPOINear, s'il
        # reference un POI Fixed connu -- reste souvent non resolu sur un
        # scenario reel (les Random referencent le plus souvent d'autres
        # Random, pas des Fixed), c'est un cas attendu, pas une erreur :
        # l'entite est alors simplement non affichee (position=None).
        center = None
        radius = None
        spawn_near = params.get("SpawnPOINear")
        if spawn_near:
            for ref in _parse_list_value(spawn_near):
                if ref in fixed_positions:
                    center = fixed_positions[ref]
                    break
        spawn_range = params.get("SpawnPOINearRange")
        if spawn_range and center:
            rng = _parse_list_value(spawn_range)
            if len(rng) >= 2:
                lo = _parse_float_or_none(rng[0])
                hi = _parse_float_or_none(rng[1])
                if lo is not None and hi is not None:
                    radius = (lo + hi) / 2.0
        entities.append(CanvasEntity(
            kind="poi_random", name=name, position=center, radius=radius,
            faction=faction, extra=params, source_item=item,
        ))

    for item in find_fixed_player_start_items(doc):
        params = dict(get_item_params(item))
        pos = _parse_pos(params.get("Pos"))
        entities.append(CanvasEntity(
            kind="player_start", name=f"Start ({item.value})", position=pos,
            faction="Admin", extra=params, source_item=item, pos_property_key="Pos",
        ))

    for item in find_space_resource_items(doc):
        # Position volontairement None -- voir le commentaire de tete de
        # module sur RadialInfo.
        entities.append(CanvasEntity(
            kind="resource", name=get_space_resource_display_name(item),
            position=None, faction="None", extra=dict(get_item_params(item)),
            source_item=item,
        ))

    for item in find_spawn_zones_items(doc):
        params = dict(get_item_params(item))
        radius = _parse_float_or_none(params.get("Radius"))
        spawn_at = params.get("SpawnAt") or "?"
        entities.append(CanvasEntity(
            kind="spawn_zone", name=f"Zone @ {spawn_at}", position=None,
            radius=radius, faction="None", extra=params, source_item=item,
        ))

    for item in find_spawn_rate_zones_items(doc):
        params = dict(get_item_params(item))
        radius = _parse_float_or_none(params.get("Radius"))
        spawn_at = params.get("SpawnAt") or "?"
        entities.append(CanvasEntity(
            kind="spawn_rate_zone", name=f"Rate @ {spawn_at}", position=None,
            radius=radius, faction="None", extra=params, source_item=item,
        ))

    for item in find_drone_spawning_items(doc):
        params = dict(get_item_params(item))
        cx = _parse_float_or_none(params.get("CenterX"))
        cz = _parse_float_or_none(params.get("CenterZ"))
        center = (cx, 0.0, cz) if cx is not None and cz is not None else None
        entities.append(CanvasEntity(
            kind="drone_spawning", name=f"Drones @ {params.get('DronesMinMax', '?')}",
            position=center, faction="Zirax", extra=params, source_item=item,
        ))

    return entities


def update_entity_position(entity: CanvasEntity, new_x: float, new_z: float) -> bool:
    """Met a jour la position (X, Z) d'une entite dans le YAML source -- l'axe
    Y (hauteur) est conserve tel quel. Retourne False si cette entite n'a pas
    de propriete de position modifiable directement (ex: position resolue
    indirectement pour un POI Random -- deplacer visuellement n'a alors pas de
    sens, il faudrait modifier le POI Fixed reference a la place)."""
    if entity.pos_property_key is None or entity.position is None or entity.source_item is None:
        return False
    _, y, _ = entity.position
    new_pos = f"[ {new_x:g}, {y:g}, {new_z:g} ]"
    if not entity.source_item.set(entity.pos_property_key, new_pos):
        return False
    entity.position = (new_x, y, new_z)
    return True


def compute_bounding_box(entities: List[CanvasEntity]) -> Tuple[float, float, float, float]:
    """Retourne (min_x, max_x, min_z, max_z) englobant toutes les entites
    positionnees. Valeurs de repli raisonnables si aucune entite n'a de
    position exploitable (ex: playfield sans aucune donnee resolue)."""
    xs, zs = [], []
    for e in entities:
        if e.position is not None:
            xs.append(e.position[0])
            zs.append(e.position[2])
            if e.radius is not None:
                xs.append(e.position[0] - e.radius)
                xs.append(e.position[0] + e.radius)
                zs.append(e.position[2] - e.radius)
                zs.append(e.position[2] + e.radius)
    if not xs or not zs:
        return (-1000.0, 1000.0, -1000.0, 1000.0)
    return (min(xs), max(xs), min(zs), max(zs))
