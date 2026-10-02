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

"""Fusion ECF PAR NOMS (core/name_merge.py, v1.14.0 — demande du
01/10/2026 « les creatures etc ») : pour les fichiers a blocs Name sans
Id que la fusion generique REFUSE des que le working contient des noms
dupliques (EGroupsConfig : AlienBugs01 x2 vecu). Ajout des blocs
absents, working jamais ecrase, idempotent."""
import pytest

from core.name_merge import analyze_name_merge, apply_name_merge

WORKING = """{ EGroup Name: ZiraxPatrol
  Faction: Zirax
}
{ EGroup Name: AlienBugs01
  Faction: None
}
{ EGroup Name: AlienBugs01
  Faction: Alien
}
"""

SOURCE = """{ EGroup Name: ZiraxPatrol
  Faction: Zirax
}
{ EGroup Name: AbyssalBattleGroupA
  Faction: Abyssal
  AbyssalWarrior: "2, 4"
}
{ EGroup Name: DF_DrillGuard
  Faction: Warlord
}
"""


@pytest.fixture
def pair(tmp_path):
    w, s = tmp_path / "work", tmp_path / "src"
    for root in (w, s):
        (root / "Content/Configuration").mkdir(parents=True)
    (w / "Content/Configuration/EGroupsConfig.ecf").write_text(
        WORKING, encoding="utf-8")
    (s / "Content/Configuration/EGroupsConfig.ecf").write_text(
        SOURCE, encoding="utf-8")
    return (w / "Content/Configuration/EGroupsConfig.ecf",
            s / "Content/Configuration/EGroupsConfig.ecf")


def test_analyze_adds_absent_ignores_working_dupes(pair):
    """Le working a un nom EN DOUBLE (AlienBugs01 x2) : la fusion
    generique refuserait ce fichier — la fusion par noms propose les
    blocs ABSENTS et n'effleure jamais les doublons internes."""
    wp, sp = pair
    plan = analyze_name_merge(wp, sp)
    assert plan.ok
    assert [b.name for b in plan.blocks_add] == \
        ["AbyssalBattleGroupA", "DF_DrillGuard"]
    assert plan.blocks_same == ["ZiraxPatrol"]
    assert plan.working_dupes == [("AlienBugs01", 1)]
    assert plan.source_dupes == []


def test_apply_appends_separator_bak_idempotent(pair):
    wp, sp = pair
    plan = analyze_name_merge(wp, sp)
    stats = apply_name_merge(plan, wp)
    assert stats["blocks"] == 2
    txt = wp.read_text(encoding="utf-8")
    assert "Fusion depuis source : blocs ajoutes" in txt
    assert "Name: AbyssalBattleGroupA" in txt
    assert "Name: DF_DrillGuard" in txt
    # working intact : les doublons internes restent en place
    assert txt.count("AlienBugs01") == 2
    bak = wp.with_suffix(".ecf.bak")
    assert bak.exists() and "AbyssalBattleGroupA" not in \
        bak.read_text(encoding="utf-8")
    # idempotence
    plan2 = analyze_name_merge(wp, sp)
    assert plan2.blocks_add == []
    assert apply_name_merge(plan2, wp)["blocks"] == 0


def test_apply_respects_unchecked_names(pair):
    wp, sp = pair
    plan = analyze_name_merge(wp, sp)
    apply_name_merge(plan, wp, names=["DF_DrillGuard"])
    txt = wp.read_text(encoding="utf-8")
    assert "DF_DrillGuard" in txt
    assert "AbyssalBattleGroupA" not in txt


def test_plan_error_on_unreadable(pair):
    wp, sp = pair
    sp.write_text("{ EGroup Name: broken\n", encoding="utf-8")
    plan = analyze_name_merge(wp, sp)
    assert isinstance(plan.errors, list)
