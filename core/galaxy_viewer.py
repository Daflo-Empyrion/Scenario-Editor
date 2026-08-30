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
Extraction des systemes solaires de Sectors/Sectors.yaml pour affichage sur
une carte 2D -- structure ENTIEREMENT REVUE par rapport a une premiere
proposition, dont les hypotheses etaient fausses a presque tous les niveaux
une fois verifiees contre un vrai Sectors.yaml (82 systemes, 817 playfields) :

- Cle racine reelle : 'SolarSystems' (liste), PAS 'Sectors' -- 'Sectors:'
  existe bien a la racine du fichier, mais c'est une liste VIDE sans rapport,
  reutilisee avec un sens DIFFERENT (grille de secteurs locaux) a l'interieur
  de chaque systeme.
- Position : 'Coordinates', pas 'Position'.
- 'StarClass' (pas 'StarType') melange de vraies classes spectrales (A3,
  K2V...) ET de roles de systeme (Gate, Anomaly, ZiraxHomeSystem, Beacon...)
  -- vocabulaire bien plus riche qu'une simple lettre O/B/A/F/G/K/M.
- AUCUNE donnee de connexion/route de warp entre systemes n'existe dans ce
  fichier (recherche exhaustive, rien trouve) -- ces routes sont
  probablement calculees par le moteur du jeu a partir de la proximite,
  jamais declarees ici. Impossible de tracer un graphe de connexions avec
  les donnees disponibles ; seule une carte spatiale (position reelle) est
  proposee ici.
- Meme piege des commentaires a indentation zero que pour les POI de
  playfield (ce fichier est truffe de bannieres decoratives a indentation
  zero) -- affecte a la fois la liste des systemes eux-memes ET les secteurs
  locaux imbriques dans chaque systeme. Gere via la technique robuste par
  plage d'indices, plus un suivi par VALEUR (pas par nom de cle comme
  ailleurs, puisque le "nom de sous-section" ici est la valeur du champ
  Name, pas une cle litterale) pour rattacher chaque secteur local a son
  vrai systeme parent.
- Le detail complet de chaque entree individuelle du tableau 'Playfields'
  (position locale, template, parametres de spawn de faction) n'est PAS
  extrait ici -- format positionnel a longueur variable, pas assez
  confirme pour etre restitue de facon fiable. Seul le NOMBRE de secteurs
  locaux par systeme est expose, comme indicateur de "richesse" du systeme.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .parsers_utils import parse_pos_3d
from .yamllite.model import YamlEntry
from .playfield_editor import _section_index_range, _find_items_in_range


# Categorise StarClass en "role special" (Gate/Anomaly/HomeSystem/Beacon...)
# ou "classe spectrale reelle" (A/B/K/M/etc avec ou sans suffixe numerique/de
# luminosite) -- confirme sur les 27 valeurs distinctes reellement observees
# dans un vrai Sectors.yaml.
_SPECIAL_ROLE_PREFIXES = (
    "Gate", "Anomaly", "Beacon", "Creative", "Tranquil",
    "StartingSystem",  # suffixe, verifie ci-dessous plutot qu'en prefixe
)


def classify_star_class(star_class: str) -> str:
    """Retourne 'role' pour un role de systeme special (Gate, Anomaly,
    HomeSystem...) ou 'spectral' pour une vraie classe spectrale d'etoile
    (A, K2V, M2...). Heuristique fondee sur les 27 valeurs reelles observees,
    pas une liste exhaustive garantie face a un scenario totalement
    personnalise."""
    if not star_class:
        return "spectral"
    if star_class.endswith("StartingSystem") or star_class.endswith("HomeSystem"):
        return "role"
    for prefix in ("Gate", "Anomaly", "Beacon", "Creative", "Tranquil"):
        if star_class.startswith(prefix):
            return "role"
    return "spectral"


@dataclass
class SolarSystem:
    name: str
    coordinates: Optional[Tuple[float, float, float]]
    star_class: str
    sector_count: int = 0
    source_item: Optional[YamlEntry] = None


def _count_local_sectors_per_system(doc, start: int, end: int, system_names: List[str]) -> dict:
    """Compte les 'Coordinates:' locales de chaque systeme (secteurs a
    l'interieur du systeme), en suivant la DERNIERE VALEUR de 'Name:' vue
    dans l'ordre du texte -- PAS un suivi par nom de cle comme
    _find_items_with_subsection_tracking() (voir docstring de tete de
    module). La toute premiere 'Coordinates:' de chaque systeme est celle du
    systeme lui-meme (sa position galactique), pas un secteur local -- elle
    est donc exclue du compte (soustraction de 1 par systeme trouve)."""
    raw_counts: dict = {}
    current = [None]

    def walk(nodes):
        for node in nodes:
            if isinstance(node, YamlEntry):
                if node.key == "Name" and node.is_sequence_item and node.value in system_names:
                    current[0] = node.value
                if node.key == "Coordinates" and node.is_sequence_item and current[0] is not None:
                    raw_counts[current[0]] = raw_counts.get(current[0], 0) + 1
                walk(node.children)

    walk(doc.nodes[start:end])
    return {name: max(0, count - 1) for name, count in raw_counts.items()}


def extract_solar_systems(doc) -> List[SolarSystem]:
    """Extrait tous les systemes solaires de Sectors.yaml. Retourne une liste
    vide si le fichier n'a pas de section SolarSystems (ex: fichier different
    ouvert par erreur)."""
    rng = _section_index_range(doc, "SolarSystems")
    if rng is None:
        return []

    name_items = _find_items_in_range(doc, rng[0], rng[1], "Name")
    system_names = [item.value for item in name_items]
    sector_counts = _count_local_sectors_per_system(doc, rng[0], rng[1], system_names)

    systems: List[SolarSystem] = []
    for item in name_items:
        coords_prop = next((c for c in item.children if isinstance(c, YamlEntry) and c.key == "Coordinates"), None)
        star_class_prop = next((c for c in item.children if isinstance(c, YamlEntry) and c.key == "StarClass"), None)
        systems.append(SolarSystem(
            name=item.value,
            coordinates=parse_pos_3d(coords_prop.value if coords_prop else None, min_parts=3),
            star_class=star_class_prop.value if star_class_prop else "",
            sector_count=sector_counts.get(item.value, 0),
            source_item=item,
        ))
    return systems


def compute_bounding_box(systems: List[SolarSystem]) -> Tuple[float, float, float, float]:
    """Retourne (min_x, max_x, min_z, max_z) englobant tous les systemes
    positionnes (axe X et Z -- l'axe Y/hauteur galactique est ignore pour une
    carte 2D top-down, coherent avec core/playfield_canvas.py)."""
    xs = [s.coordinates[0] for s in systems if s.coordinates]
    zs = [s.coordinates[2] for s in systems if s.coordinates]
    if not xs or not zs:
        return (-200.0, 200.0, -200.0, 200.0)
    return (min(xs), max(xs), min(zs), max(zs))
