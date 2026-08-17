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
Extraction de toutes les proprietes (cles) reellement utilisees a travers les fichiers
ECF d'un scenario -- base pour des outils ulterieurs (glossaire exhaustif avec
description et valeur cible, verification de coherence, etc.).

Parcourt recursivement chaque bloc/sous-bloc de chaque fichier .ecf du dossier donne,
et pour chaque cle de propriete rencontree, memorise : dans quel(s) fichier(s) elle
apparait, combien de fois, et quelques exemples de valeurs vues (pour comprendre le
format attendu sans avoir a rouvrir les fichiers un par un).

Les cles numerotees (Name_0, Name_1, Item_23... -- tres frequentes dans les structures
repetitives type Child Items/LootGroups, voir aussi le mode tableau de l'editeur ECF)
sont regroupees sous une seule entree generique 'Name_N' plutot que de creer des
milliers de quasi-doublons qui noieraient le reste."""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set

from .ecf.parser import parse_ecf_file
from .ecf.model import EcfBlock, EcfProperty

MAX_EXAMPLE_VALUES = 5
_NUMBERED_KEY_RE = re.compile(r'^([A-Za-z]+)_(\d+)$')


@dataclass
class PropertyUsage:
    name: str
    files: Set[str] = field(default_factory=set)
    count: int = 0
    example_values: List[str] = field(default_factory=list)

    def record(self, filename: str, value: str) -> None:
        self.files.add(filename)
        self.count += 1
        if value and value not in self.example_values and len(self.example_values) < MAX_EXAMPLE_VALUES:
            self.example_values.append(value)


def _normalize_key(key: str) -> str:
    """Regroupe les cles numerotees (Name_0, Item_23...) sous un nom generique
    'Prefixe_N' -- garde les cles normales (Mass, HitPoints...) telles quelles."""
    m = _NUMBERED_KEY_RE.match(key)
    return f"{m.group(1)}_N" if m else key


def _walk_block(block: EcfBlock, filename: str, usages: Dict[str, PropertyUsage]) -> None:
    """Enregistre les proprietes d'en-tete du bloc (Id, Name, Ref...) et toutes ses
    lignes de propriete enfants, puis descend recursivement dans ses sous-blocs."""
    for k, v in block.pairs:
        if not k:
            continue
        norm = _normalize_key(k)
        usages.setdefault(norm, PropertyUsage(name=norm)).record(filename, v)

    for child in block.children:
        if isinstance(child, EcfProperty):
            for k, v in child.pairs:
                if not k:
                    continue
                norm = _normalize_key(k)
                usages.setdefault(norm, PropertyUsage(name=norm)).record(filename, v)
        elif isinstance(child, EcfBlock):
            _walk_block(child, filename, usages)


def extract_properties(scenario_root: Path) -> List[PropertyUsage]:
    """Parcourt tous les fichiers .ecf sous `scenario_root` (recursif) et retourne la
    liste des proprietes rencontrees, triee par nombre d'occurrences decroissant (les
    plus frequentes -- donc les plus structurantes pour le scenario -- en premier)."""
    usages: Dict[str, PropertyUsage] = {}
    for ecf_path in sorted(scenario_root.rglob("*.ecf")):
        try:
            doc = parse_ecf_file(ecf_path)
        except Exception:
            continue  # fichier illisible/corrompu -- ignore plutot que d'interrompre toute l'extraction
        filename = ecf_path.name
        for node in doc.nodes:
            if isinstance(node, EcfBlock):
                _walk_block(node, filename, usages)

    return sorted(usages.values(), key=lambda u: u.count, reverse=True)


def _flat_glossary() -> Dict[str, str]:
    """Aplati les glossaires ECF (core/ecf_header_glossary.py) en un dictionnaire
    terme -> explication, pour pre-remplir automatiquement la colonne Description de
    l'export quand le terme est reconnu SANS AMBIGUITE.

    Deux precautions pour eviter une description trompeuse (pire qu'une case vide) :
    - Les entrees composees ('Class: Container', 'Place: NoRotation'...) decrivent une
      VALEUR precise d'une propriete, pas la propriete elle-meme -- jamais utilisees
      pour pre-remplir la cle generique seule ('Class', 'Place').
    - Une petite liste noire de termes generiques omnipresents (Name, Id, Class...)
      dont le sens depend entierement du contexte (nom de bloc ? d'etoile ? de
      faction ?) -- jamais auto-rempli meme si un terme identique existe par ailleurs
      dans un glossaire pour un contexte precis."""
    from .ecf_header_glossary import GLOSSARY_BY_FILE
    AMBIGUOUS_TERMS = {"Name", "Id", "Class", "Type", "Value", "Description", "Model", "Place"}
    flat: Dict[str, str] = {}
    for sections in GLOSSARY_BY_FILE.values():
        for _title, entries in sections:
            for term, explanation in entries:
                if ':' in term or '/' in term or term in AMBIGUOUS_TERMS:
                    continue
                flat.setdefault(term, explanation)
    return flat


def build_property_rows(usages: List[PropertyUsage]) -> List[List[str]]:
    """Construit les lignes du tableau exporte (glossaire pre-rempli quand la
    propriete est reconnue) -- retourne une liste de listes de chaines, prete pour
    core.csv_handler ou tout autre export. Colonnes :
    Propriete, Nb occurrences, Fichier(s), Exemples de valeurs, Description, Valeur cible."""
    glossary = _flat_glossary()
    rows = []
    for u in usages:
        description = glossary.get(u.name, "")
        rows.append([
            u.name,
            str(u.count),
            ", ".join(sorted(u.files)),
            " | ".join(u.example_values),
            description,
            "",  # Valeur cible -- laissee vide, a remplir par l'utilisateur
        ])
    return rows


PROPERTY_EXPORT_HEADER = [
    "Propriete", "Nb occurrences", "Fichier(s)", "Exemples de valeurs", "Description", "Valeur cible",
]
