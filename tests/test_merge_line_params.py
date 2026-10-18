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

"""Fusion ECF : param1/param2 sont des parametres PAR LIGNE des structures
repetitives (Child Items Name_N/Group_N, LootGroups Item_N...) -- le garde
anti-doublons de cles (vecu 27/09 : type/display dupliques) ne doit JAMAIS
les filtrer des lignes importees. Vecu 18/10 : fusion d'un container
Atlantis, param1 perdu sur toutes les lignes importees sauf la premiere."""
from core.ecf.merge import _merge_properties
from core.ecf.model import EcfBlock, property_lines
from core.ecf.parser import parse_ecf_text


def _first_block(text):
    doc = parse_ecf_text(text)
    return next(n for n in doc.nodes if isinstance(n, EcfBlock))


def test_merge_keeps_param_on_imported_repeating_lines():
    base = _first_block(
        "{ +Container Id: 323\n"
        "  { Child Items\n"
        "    Group_0: empty, param1: 0.1\n"
        "  }\n"
        "}\n")
    incoming = _first_block(
        "{ +Container Id: 323\n"
        "  { Child Items\n"
        "    Group_0: AtlantisEdenImplant, param1: 0.10\n"
        "    Group_1: AtlantisOptronics, param1: 0.10\n"
        "    Group_2: AtlantisIgnots, param1: 0.05\n"
        "  }\n"
        "}\n")
    merged, overrides = _merge_properties([("travail", base), ("source", incoming)])
    child = next(c for c in merged.children
                 if isinstance(c, EcfBlock) and c.kind == "Child Items")
    lines = property_lines(child)
    assert lines["Group_0"] == [("Group_0", "empty"), ("param1", "0.1")]
    assert lines["Group_1"] == [("Group_1", "AtlantisOptronics"), ("param1", "0.10")]
    assert lines["Group_2"] == [("Group_2", "AtlantisIgnots"), ("param1", "0.05")]


def test_merge_still_filters_block_unique_duplicate_keys():
    # Le garde du 27/09 reste actif pour les cles VRAIMENT uniques de bloc.
    base = _first_block(
        "{ +Block Id: 1\n"
        "  Count: 3\n"
        "  Mass: 10\n"
        "  display: true\n"
        "}\n")
    incoming = _first_block(
        "{ +Block Id: 1\n"
        "  Count: 9\n"
        "  Size: \"1,1\"\n"
        "  Hardness: 0.5, display: false\n"
        "}\n")
    merged, _ = _merge_properties([("travail", base), ("source", incoming)])
    lines = property_lines(merged)
    assert lines["Count"] == [("Count", "3")]              # priorite travail
    assert lines["Size"] == [("Size", '"1,1"')]            # importee
    assert lines["Hardness"] == [("Hardness", "0.5")]      # importee SANS display
    assert lines["display"] == [("display", "true")]       # doublon filtre, valeur travail
