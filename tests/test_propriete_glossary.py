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

"""Tests du glossaire general des proprietes (core/propriete_glossary.py).

Gardes-fous :
- data/propriete_glossary.json (FR) genere depuis docs/glossaire_proprietes.md
  -> desynchro = suite rougie (relancer tools/build_propriete_glossary.py) ;
- data/propriete_glossary.en.json : MEME nombre d'entrees que le FR, aucune
  explication vide (le EN est redige a la main : toute evolution du FR doit
  etre suivie d'une traduction) ;
- lookup : cles connues trouvees dans le bon scope, ambiguite non resolue
  -> None, cle inconnue -> None (mieux vaut pas d'infobulle qu'invente)."""
import json
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.propriete_glossary import (  # noqa: E402
    _PROPS, find_explanation, file_description, scope_for_file,
)
from tools.build_propriete_glossary import build  # noqa: E402


def _load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def test_fr_data_in_sync_with_markdown():
    """data/propriete_glossary.json == regeneration depuis le markdown."""
    committed = _load("propriete_glossary.json")
    rebuilt = build()
    assert committed == rebuilt


def test_en_data_in_sync_with_fr():
    fr = _load("propriete_glossary.json")
    en = _load("propriete_glossary.en.json")
    assert len(en["props"]) == len(fr["props"]), \
        "EN/FR desynchronises : traduire les nouvelles entrees"
    for i, (f_entry, e_entry) in enumerate(zip(fr["props"], en["props"])):
        assert f_entry["name"] == e_entry["name"], f"index {i} : nom different"
        assert e_entry["exp"].strip(), f"exp EN vide pour {e_entry['name']} (#{i})"
    for k in fr["file_descriptions"]:
        assert k in en["file_descriptions"], f"description EN manquante : {k}"


def test_find_explanation_known_keys():
    # cle homonyme dans plusieurs sections : le contexte (section racine du
    # path, fourni par les appelants GUI) tranche
    assert "base de drones défende le gisement" in find_explanation(
        "DroneProb", scope="yaml", context="RandomResources")
    assert "renfort de drones" in find_explanation(
        "DroneProb", scope="yaml", context="POIs")
    assert "PAR STRUCTURE" in find_explanation("MaxCount", file="BlocksConfig.ecf")
    assert find_explanation("FlattenTerrain", scope="epb")
    assert "fabrication" in find_explanation("CraftTime", file="Templates.ecf")
    # ambigu non resolu -> None ; resolu par contexte -> bonne entree
    assert find_explanation("Name", scope="yaml") is None
    assert "nom du biome" in find_explanation(
        "Name", scope="yaml", context="Biomes").lower()


def test_find_explanation_unknown_and_empty():
    assert find_explanation("") is None
    assert find_explanation("ZzzCleInexistante") is None
    # decorations de rendu tolerees (backticks) -- avec contexte
    assert find_explanation("`DroneProb`", scope="yaml", context="POIs")


def test_scope_for_file():
    assert scope_for_file("playfield_static.yaml") == "yaml"
    assert scope_for_file("Sectors.yaml") == "sector"
    assert scope_for_file("gameoptions.yaml") == "gameoptions"
    assert scope_for_file("PDA.yaml") == "pda"
    assert scope_for_file("BlocksConfig.ecf") == "ecf"
    assert scope_for_file("terrain.ecf") == "ecf"


def test_file_description_known_files():
    assert file_description("terrain.ecf")
    assert file_description("playfield.yaml")
    assert file_description("Sectors.yaml")
    assert file_description("FichierInconnu.ecf") is None
    assert file_description("") is None


def test_entries_for_file_non_empty_for_ecf():
    for filename in ("BlocksConfig.ecf", "ItemsConfig.ecf", "EClassConfig.ecf"):
        assert entries_count(filename) > 0, filename


def entries_count(filename):
    from core.propriete_glossary import entries_for_file
    return len(entries_for_file(filename))


def test_props_have_required_fields():
    for entry in _PROPS[:50]:
        assert entry["name"] and entry["exp"]
        assert entry["scope"] in ("yaml", "ecf", "epb", "pda", "sector",
                                  "gameoptions", "general")
