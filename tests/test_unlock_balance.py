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

"""Equilibrage des UnlockCost (core/unlock_balance.py) : perimetre de
l'arbre, zeros remplis, plafond 1000 ramene, monotonie niveau/puissance,
idempotence du re-scan et ecriture dans les deux fichiers."""

from pathlib import Path

from core.unlock_balance import analyze, apply_proposals

BLOCKS = """{ Block Id: 1, Name: GenWeak
  Class: Generator
  Category: Devices
  TechTreeNames: "Small Vessel"
  UnlockLevel: 5
  UnlockCost: 20
  EnergyOut: 100
}
{ Block Id: 2, Name: GenStrong
  Class: Generator
  Category: Devices
  TechTreeNames: "Small Vessel"
  UnlockLevel: 5
  UnlockCost: 1
  EnergyOut: 400
}
{ Block Id: 3, Name: GenZero
  Class: Generator
  Category: Devices
  TechTreeNames: "Small Vessel"
  UnlockLevel: 5
  UnlockCost: 0
  EnergyOut: 100
}
{ Block Id: 4, Name: GenCap
  Class: Generator
  Category: Devices
  TechTreeNames: "Small Vessel"
  UnlockLevel: 2
  UnlockCost: 1000
  EnergyOut: 100
}
{ Block Id: 5, Name: GenMissing
  Class: Generator
  Category: Devices
  TechTreeNames: "Small Vessel"
  UnlockLevel: 3
  EnergyOut: 100
}
{ Block Id: 6, Name: HiddenOnly
  Class: Generator
  Category: Devices
  TechTreeNames: Hidden
  UnlockLevel: 5
  UnlockCost: 0
  EnergyOut: 100
}
{ Block Id: 7, Name: NoTree
  Class: Generator
  Category: Devices
  UnlockLevel: 5
  UnlockCost: 0
  EnergyOut: 100
}
{ Block Id: 8, Name: GenLvl1
  Class: Generator
  Category: Devices
  TechTreeNames: "Small Vessel"
  UnlockLevel: 1
  UnlockCost: 0
  EnergyOut: 100
}
"""

ITEMS = """{ Item Id: 10, Name: ToolA
  Category: Tools
  TechTreeNames: "Tools"
  UnlockLevel: 3
  UnlockCost: 0
  MarketPrice: 10
}
{ Item Id: 11, Name: ToolMixed
  Category: Tools
  TechTreeNames: "Hidden, Tools"
  UnlockLevel: 3
  UnlockCost: 0
  MarketPrice: 10
}
"""


def _scenario(tmp_path: Path) -> Path:
    cdir = tmp_path / "Content" / "Configuration"
    cdir.mkdir(parents=True)
    (cdir / "BlocksConfig.ecf").write_text(BLOCKS, encoding="utf-8")
    (cdir / "ItemsConfig.ecf").write_text(ITEMS, encoding="utf-8")
    (cdir / "Templates.ecf").write_text("", encoding="utf-8")
    return tmp_path


def test_scope_is_the_visible_tech_tree(tmp_path):
    root = _scenario(tmp_path)
    by_name = {p.name: p for p in analyze(root)}
    assert "HiddenOnly" not in by_name       # tout Hidden = jamais affiche
    assert "NoTree" not in by_name           # aucune categorie
    assert "ToolA" in by_name
    assert "ToolMixed" in by_name            # Hidden + Tools = affiche


def test_zeros_filled_and_cap_lowered(tmp_path):
    root = _scenario(tmp_path)
    by_name = {p.name: p for p in analyze(root)}
    assert by_name["GenLvl1"].new_cost >= 1
    assert by_name["GenZero"].new_cost > 0
    assert by_name["GenMissing"].new_cost > 0
    assert by_name["GenCap"].new_cost < 1000


def test_level_and_power_are_monotonic(tmp_path):
    root = _scenario(tmp_path)
    by_name = {p.name: p for p in analyze(root)}
    # meme niveau : le plus puissant ne coute pas moins cher
    assert by_name["GenStrong"].new_cost >= by_name["GenWeak"].new_cost
    # niveau croissant : la cible ne decroit pas
    assert by_name["GenCap"].new_cost <= by_name["GenMissing"].new_cost
    assert by_name["GenMissing"].new_cost <= by_name["GenWeak"].new_cost


def test_rescan_is_idempotent(tmp_path):
    root = _scenario(tmp_path)
    first = [p for p in analyze(root) if p.changed]
    assert first
    apply_proposals(first)
    assert [p for p in analyze(root) if p.changed] == []


def test_per_level_bounds_clamp(tmp_path):
    root = _scenario(tmp_path)
    by_name = {p.name: p for p in
               analyze(root, per_level={5: (3, 8)})}
    # niveau 5 : tout compris entre 3 et 8
    for name in ("GenWeak", "GenStrong", "GenZero"):
        assert 3 <= by_name[name].new_cost <= 8, name
    # les autres niveaux ne sont pas bornes par la ligne
    assert by_name["GenCap"].new_cost >= 1
    assert by_name["GenCap"].new_cost < 1000


def test_global_bounds_clamp(tmp_path):
    root = _scenario(tmp_path)
    capped = analyze(root, max_cost=4)
    assert all(p.new_cost <= 4 for p in capped)
    floored = analyze(root, min_cost=3)
    assert all(p.new_cost >= 3 for p in floored)
    # idempotence avec bornes
    apply_proposals([p for p in floored if p.changed])
    again = analyze(root, min_cost=3)
    assert [p for p in again if p.changed] == []


def test_apply_writes_missing_property_in_both_files(tmp_path):
    root = _scenario(tmp_path)
    apply_proposals([p for p in analyze(root) if p.changed])
    blocks = (root / "Content/Configuration/BlocksConfig.ecf").read_text(
        encoding="utf-8")
    items = (root / "Content/Configuration/ItemsConfig.ecf").read_text(
        encoding="utf-8")
    assert "UnlockCost: 1" in blocks          # GenLvl1 rempli
    assert "UnlockCost: 2" in blocks          # GenCap ramene
    assert "UnlockCost: 3" in blocks          # GenMissing AJOUTE
    assert "HiddenOnly" in blocks             # jamais modifie
    assert "UnlockCost: 3" in items           # ToolA rempli
