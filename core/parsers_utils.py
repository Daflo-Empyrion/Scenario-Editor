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
Fonctions d'analyse des valeurs numeriques et listees des fichiers de
scenario (listes YAML entre crochets des playfields/galaxies, valeurs
ECF), partagees par plusieurs modules (poi_inspector, playfield_canvas,
galaxy_viewer, tech_tree). Regroupees ici apres audit du 30/08/2026 :
quatre modules portaient des copies legerement differentes des memes
concepts, avec un risque de divergence a chaque correction.

Deux parseurs de listes coexistent VOLONTAIREMENT, semantiques distinctes :
- parse_bracketed_list : liste YAML entre crochets ('[ a, b ]' -> ['a', 'b'])
- parse_quoted_list    : valeur ECF deguillemetee ('"a,b"' -> ['a', 'b'])
Ne pas les fusionner : les formats sources ne sont pas les memes.

Comportements figes par de vrais fichiers du jeu (voir les docstrings des
modules appelants) : CountMinMax/DronesMinMax des POI, Pos des Fixed POI,
Coordinates des systemes de galaxie, TechTreeNames des blocs.
"""
from typing import List, Optional, Tuple


def parse_int_or(value, default: int = 0) -> int:
    """Convertit value en int ; retourne default si absent ou illisible."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def parse_float_or(value, default=0.0) -> float:
    """Convertit value en float ; retourne default si absent ou illisible.
    default=None reproduit le comportement de l'ancien
    playfield_canvas._parse_float_or_none (None si la propriete optionnelle
    est absente, ex: Radius), a passer EXPLICITEMENT a chaque appel."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def parse_bracketed_list(value: Optional[str]) -> List[str]:
    """Decoupe une liste YAML entre crochets ('[ a, b ]' -> ['a', 'b']).
    Retourne [] si value est None ou vide."""
    if not value:
        return []
    cleaned = value.strip().strip('[]')
    return [p.strip() for p in cleaned.split(',') if p.strip()]


def parse_quoted_list(raw: Optional[str]) -> List[str]:
    """Deguillemette et scinde une valeur de propriete ECF potentiellement
    listee (ex: '"Base,Capital Vessel"' -> ['Base', 'Capital Vessel']).
    Chaque element est nettoye des espaces residuels. Retourne [] si raw
    est None ou vide apres nettoyage."""
    if raw is None:
        return []
    value = raw.strip()
    if value.startswith('"') and value.endswith('"') and len(value) >= 2:
        value = value[1:-1]
    parts = [p.strip() for p in value.split(',')]
    return [p for p in parts if p]


def parse_min_max(value) -> Tuple[int, int]:
    """Parse '[ min, max ]' en couple d'entiers -- confirme sur de vrais
    playfields pour CountMinMax/DronesMinMax."""
    if not value:
        return (0, 0)
    cleaned = value.strip().strip('[]')
    parts = [p.strip() for p in cleaned.split(',')]
    if len(parts) < 2:
        return (0, 0)
    return (parse_int_or(parts[0]), parse_int_or(parts[1]))


def parse_pos_3d(value: Optional[str], min_parts: int = 2) -> Optional[Tuple[float, float, float]]:
    """Parse '[ x, y, z ]' en triplet de floats. Accepte au moins min_parts
    parties et complete par des zeros (Position sans Z dans de vrais
    playfields) ; min_parts=3 reproduit l'ancien
    galaxy_viewer._parse_coordinates (Coordinates de galaxie toujours
    complet, sinon illisible). Retourne None si value est None/vide ou si
    une partie n'est pas numerique."""
    if not value:
        return None
    cleaned = value.strip().strip('[]')
    parts = [p.strip() for p in cleaned.split(',')]
    if len(parts) < min_parts:
        return None
    try:
        coords = [float(p) for p in parts[:3]]
        while len(coords) < 3:
            coords.append(0.0)
        return (coords[0], coords[1], coords[2])
    except ValueError:
        return None
