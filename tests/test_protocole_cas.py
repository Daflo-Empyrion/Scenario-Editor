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
        for etape in case["etapes"]:
            # une etape est une chaine OU {"txt": ..., "cmd": copiable(s)}
            if isinstance(etape, dict):
                assert etape.get("txt", "").strip(), case["id"]
                cmds = etape.get("cmd") or []
                cmds = [cmds] if isinstance(cmds, str) else cmds
                assert cmds and all(str(c).strip() for c in cmds), case["id"]
            else:
                assert etape.strip(), case["id"]
        assert case["attendu"].strip(), case["id"]


def test_every_case_has_english_mirror():
    from core.test_protocol_en import EN
    missing = [c["id"] for c in CASES if c["id"] not in EN]
    extra = [k for k in EN if k not in {c["id"] for c in CASES}]
    assert not missing, f"cas sans miroir EN : {missing}"
    assert not extra, f"cles EN sans cas FR : {extra}"


def test_english_mirror_matches_shape():
    from core.test_protocol_en import EN
    for case in CASES:
        en = EN[case["id"]]
        assert en.get("titre", "").strip(), case["id"]
        assert en.get("attendu", "").strip(), case["id"]
        # "pre" : present des deux cotes ou absent des deux
        assert bool(case.get("pre")) == bool(en.get("pre")), case["id"]
        assert len(en["etapes"]) == len(case["etapes"]), case["id"]
        for i, (fr_step, en_step) in enumerate(zip(case["etapes"], en["etapes"])):
            if isinstance(fr_step, dict):
                assert isinstance(en_step, dict), f"{case['id']} etape {i}"
                assert en_step.get("txt", "").strip(), f"{case['id']} etape {i}"
            else:
                assert isinstance(en_step, str), f"{case['id']} etape {i}"
                assert en_step.strip(), f"{case['id']} etape {i}"


def test_localized_case_normalizes_steps_and_localizes():
    from core import test_protocol as tp
    fr = tp.localized_case(tp.CASES[0], lang="fr")
    assert all(isinstance(row, dict) and "txt" in row and "cmds" in row
               for row in fr["etapes"])
    en = tp.localized_case(tp.CASES[0], lang="en")
    assert en["titre"] != tp.CASES[0]["titre"], "le miroir EN doit différer du FR"
    # les commandes copiables restent celles du FR (pas de traduction)
    for fr_row, en_row in zip(fr["etapes"], en["etapes"]):
        assert fr_row["cmds"] == en_row["cmds"]
    # categorie localisee
    assert tp.category_label("PROJ", "en") != tp.category_label("PROJ", "fr")


def test_protocol_has_commands_to_copy():
    # L'attendu utilisateur : les commandes console/chemins doivent etre
    # copiables (boutons dans le runner et le dialogue).
    from core.test_protocol import localized_case
    with_cmd = [c["id"] for c in CASES
                if any(row["cmds"] for row in localized_case(c)["etapes"])]
    assert len(with_cmd) >= 15, "trop peu de cas avec commandes copiables"
    for required in ("ECF-004", "YAML-005", "CSV-012", "CLI-001", "SAUV-007",
                     "ROBU-007", "OPT-010"):
        assert required in with_cmd, f"{required} devrait avoir une commande copiable"


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
