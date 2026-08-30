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

"""Structure des cas du protocole de test manuel (tools/protocole_cas.py) --
garantit que les enrichissements restent valides (comme test_tutorials pour
les tutoriels) : ids uniques, categories connues, champs remplis, rev coherent."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from protocole_cas import CASES, CATEGORIES, cases_by_category


def test_at_least_180_cases():
    # Garde-fou anti-suppression accidentelle : le protocole doit rester exhaustif.
    assert len(CASES) >= 180


def test_case_ids_unique():
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids))


def test_case_ids_match_known_prefix():
    # FICHE est une sous-famille legitime de la categorie TECH
    # (fiche d'information, tests 13.x) -- prefixes autorises explicites.
    codes = {code for code, _ in CATEGORIES} | {"FICHE"}
    for case in CASES:
        prefix = case["id"].split("-")[0]
        assert prefix in codes, f"{case['id']} : prefixe hors familles"


def test_every_case_in_known_category():
    codes = {code for code, _ in CATEGORIES}
    for case in CASES:
        assert case["cat"] in codes, f"{case['id']} : categorie inconnue {case['cat']}"


def test_every_category_has_cases():
    grouped = cases_by_category()
    for code, _label in CATEGORIES:
        assert grouped[code], f"Categorie vide : {code}"


def test_case_fields_complete():
    for case in CASES:
        assert case["titre"].strip(), case["id"]
        assert isinstance(case["etapes"], list) and case["etapes"], case["id"]
        assert all(etape.strip() for etape in case["etapes"]), case["id"]
        assert case["attendu"].strip(), case["id"]


def test_case_rev_is_positive_int():
    for case in CASES:
        rev = case.get("rev", 1)
        assert isinstance(rev, int) and rev >= 1, case["id"]


def test_numbering_is_continuous_within_categories():
    # Chaque serie (PROJ-001, PROJ-002...) doit rester continue : evite les
    # trous de numerotation lors des enrichissements.
    seen = {}
    for case in CASES:
        prefix, num = case["id"].rsplit("-", 1)
        seen.setdefault(prefix, []).append(int(num))
    for prefix, nums in seen.items():
        assert nums == list(range(1, len(nums) + 1)), \
            f"{prefix} : numerotation non continue {nums}"
