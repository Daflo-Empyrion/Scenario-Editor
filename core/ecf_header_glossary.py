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
Glossaire clarifie (en francais) des commentaires d'en-tete techniques trouves au debut
des fichiers ECF (BlocksConfig.ecf en particulier -- le plus dense). Ce n'est PAS une
traduction mot a mot : le texte original est souvent tres technique/condense, donc
chaque entree est reformulee pour rester claire, tout en gardant le sens exact.

Organise en sections (categorie -> liste de (terme, explication)) dans le meme ordre
que l'en-tete original, pour rester facile a comparer avec le fichier source.
"""

from core.resource_loading import load_json_data

# Charge depuis data/ecf_header_glossary.json (voir core/resource_loading.py).
_GLOSSARY_DATA = load_json_data("ecf_header_glossary.json")

BLOCKS_CONFIG_GLOSSARY = _GLOSSARY_DATA["BLOCKS_CONFIG_GLOSSARY"]
GALAXY_CONFIG_GLOSSARY = _GLOSSARY_DATA["GALAXY_CONFIG_GLOSSARY"]
ITEMS_CONFIG_GLOSSARY = _GLOSSARY_DATA["ITEMS_CONFIG_GLOSSARY"]
GLOBALDEFS_CONFIG_GLOSSARY = _GLOSSARY_DATA["GLOBALDEFS_CONFIG_GLOSSARY"]
LOOT_GROUPS_GLOSSARY = _GLOSSARY_DATA["LOOT_GROUPS_GLOSSARY"]
MATERIAL_CONFIG_GLOSSARY = _GLOSSARY_DATA["MATERIAL_CONFIG_GLOSSARY"]
STATUS_EFFECTS_GLOSSARY = _GLOSSARY_DATA["STATUS_EFFECTS_GLOSSARY"]
TEMPLATES_GLOSSARY = _GLOSSARY_DATA["TEMPLATES_GLOSSARY"]
TOKEN_CONFIG_GLOSSARY = _GLOSSARY_DATA["TOKEN_CONFIG_GLOSSARY"]
TRADER_NPC_CONFIG_GLOSSARY = _GLOSSARY_DATA["TRADER_NPC_CONFIG_GLOSSARY"]
BLOCK_GROUPS_CONFIG_GLOSSARY = _GLOSSARY_DATA["BLOCK_GROUPS_CONFIG_GLOSSARY"]
CONTAINERS_GLOSSARY = _GLOSSARY_DATA["CONTAINERS_GLOSSARY"]
DAMAGE_MULTIPLIER_CONFIG_GLOSSARY = _GLOSSARY_DATA["DAMAGE_MULTIPLIER_CONFIG_GLOSSARY"]
DEF_REPUTATION_GLOSSARY = _GLOSSARY_DATA["DEF_REPUTATION_GLOSSARY"]
EGROUPS_CONFIG_GLOSSARY = _GLOSSARY_DATA["EGROUPS_CONFIG_GLOSSARY"]
FACTIONS_GLOSSARY = _GLOSSARY_DATA["FACTIONS_GLOSSARY"]
FACTION_WARFARE_GLOSSARY = _GLOSSARY_DATA["FACTION_WARFARE_GLOSSARY"]


GLOSSARY_BY_FILE = {
    "BlocksConfig.ecf": BLOCKS_CONFIG_GLOSSARY,
    "GalaxyConfig.ecf": GALAXY_CONFIG_GLOSSARY,
    "ItemsConfig.ecf": ITEMS_CONFIG_GLOSSARY,
    "GlobalDefsConfig.ecf": GLOBALDEFS_CONFIG_GLOSSARY,
    "LootGroups.ecf": LOOT_GROUPS_GLOSSARY,
    "MaterialConfig.ecf": MATERIAL_CONFIG_GLOSSARY,
    "StatusEffects.ecf": STATUS_EFFECTS_GLOSSARY,
    "Templates.ecf": TEMPLATES_GLOSSARY,
    "TokenConfig.ecf": TOKEN_CONFIG_GLOSSARY,
    "TraderNPCConfig.ecf": TRADER_NPC_CONFIG_GLOSSARY,
    "BlockGroupsConfig.ecf": BLOCK_GROUPS_CONFIG_GLOSSARY,
    "Containers.ecf": CONTAINERS_GLOSSARY,
    "DamageMultiplierConfig.ecf": DAMAGE_MULTIPLIER_CONFIG_GLOSSARY,
    "DefReputation.ecf": DEF_REPUTATION_GLOSSARY,
    "EGroupsConfig.ecf": EGROUPS_CONFIG_GLOSSARY,
    "Factions.ecf": FACTIONS_GLOSSARY,
    "FactionWarfare.ecf": FACTION_WARFARE_GLOSSARY,
}


def find_term_explanation(filename: str, term: str) -> "str | None":
    """Cherche l'explication d'un terme precis (typiquement un nom de
    propriete/colonne, ex: 'AllowPlacingAt', 'EnergyIn') dans le glossaire
    du fichier concerne -- utilise pour les infobulles d'en-tete de
    colonne (mode tableau) et de cle de propriete (mode liste), toujours
    coherent avec le VRAI fichier ouvert puisque le glossaire est indexe
    par nom de fichier.

    Comparaison insensible a la casse. Gere aussi les entrees groupees
    comme 'EnergyIn / EnergyOut' (le terme cherche peut correspondre a
    l'un des deux membres separes par '/'). Retourne None si aucune
    correspondance -- l'appelant doit alors se rabattre sur d'autres
    sources (commentaire du fichier lui-meme, ou aucune infobulle)."""
    glossary = GLOSSARY_BY_FILE.get(filename)
    if not glossary:
        return None
    term_lower = term.strip().lower()
    for _section_title, entries in glossary:
        for entry_term, explanation in entries:
            # Un terme de glossaire peut grouper plusieurs cles reelles,
            # ex: "EnergyIn / EnergyOut" ou "Texture" seul.
            candidates = [c.strip().lower() for c in entry_term.split('/')]
            if term_lower in candidates:
                return explanation
    return None
