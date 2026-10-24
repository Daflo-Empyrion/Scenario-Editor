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

"""Couts de deblocage (gui/unlock_cost_dialog.py) : construction et chemin
CONNECTE scan -> table -> tout cocher -> application (ecriture reelle +
re-scan idempotent). Boites patchees, async synchrone."""

from pathlib import Path

from gui.unlock_cost_dialog import UnlockCostDialog

BLOCKS = """{ Block Id: 1, Name: GenLvl1
  Class: Generator
  Category: Devices
  TechTreeNames: "Small Vessel"
  UnlockLevel: 1
  UnlockCost: 0
  EnergyOut: 100
}
{ Block Id: 2, Name: GenCap
  Class: Generator
  Category: Devices
  TechTreeNames: "Small Vessel"
  UnlockLevel: 2
  UnlockCost: 1000
  EnergyOut: 100
}
{ Block Id: 3, Name: GenWeak
  Class: Generator
  Category: Devices
  TechTreeNames: "Small Vessel"
  UnlockLevel: 5
  UnlockCost: 20
  EnergyOut: 100
}
{ Block Id: 4, Name: GenStrong
  Class: Generator
  Category: Devices
  TechTreeNames: "Small Vessel"
  UnlockLevel: 5
  UnlockCost: 1
  EnergyOut: 400
}
{ Block Id: 5, Name: HiddenOnly
  Class: Generator
  Category: Devices
  TechTreeNames: Hidden
  UnlockLevel: 5
  UnlockCost: 0
  EnergyOut: 100
}
{ Block Id: 6, Name: NoTree
  Class: Generator
  Category: Devices
  UnlockLevel: 5
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
"""


def _scenario(tmp_path: Path) -> Path:
    cdir = tmp_path / "Content" / "Configuration"
    cdir.mkdir(parents=True)
    (cdir / "BlocksConfig.ecf").write_text(BLOCKS, encoding="utf-8")
    (cdir / "ItemsConfig.ecf").write_text(ITEMS, encoding="utf-8")
    (cdir / "Templates.ecf").write_text("", encoding="utf-8")
    return tmp_path


def test_dialog_builds(qapp):
    dlg = UnlockCostDialog(None)
    assert dlg.table.columnCount() == 10
    assert dlg.bounds_table.rowCount() == 1   # ligne Defaut seule
    assert dlg.btn_apply.isEnabled() is False
    assert dlg.chk_changed.isChecked() is True


def test_full_flow_scan_check_apply(qapp, tmp_path, monkeypatch):
    root = _scenario(tmp_path)
    dlg = UnlockCostDialog(None, str(root))
    monkeypatch.setattr("gui.unlock_cost_dialog.get_vanilla_content_path",
                        lambda: "")
    monkeypatch.setattr("gui.unlock_cost_dialog.async_call",
                        lambda owner, fn, on_done, on_fail=None, name="":
                        on_done(fn()))
    seen = []
    monkeypatch.setattr("gui.unlock_cost_dialog.info",
                        lambda *a, **k: seen.append(a))
    monkeypatch.setattr("gui.unlock_cost_dialog.ask_yes_no",
                        lambda *a, **k: True)
    dlg._analyze()
    assert dlg.table.rowCount() == 5        # Hidden et hors arbre exclus
    assert dlg._checked_names() == set()    # rien de precoche
    dlg._check_all()
    assert dlg._checked_names() == {
        "GenLvl1", "GenCap", "GenWeak", "GenStrong", "ToolA"}
    dlg._apply()
    text = (root / "Content/Configuration/BlocksConfig.ecf").read_text(
        encoding="utf-8")
    assert "UnlockCost: 1\n  EnergyOut: 100" in text     # GenLvl1 rempli
    assert "UnlockCost: 2\n  EnergyOut: 100" in text     # GenCap ramene
    assert seen, "confirmation affichee"
    # re-scan idempotent
    assert [p for p in dlg._proposals if p.changed] == []


def test_bounds_table_feeds_analysis(qapp, tmp_path, monkeypatch):
    root = _scenario(tmp_path)
    dlg = UnlockCostDialog(None, str(root))
    monkeypatch.setattr("gui.unlock_cost_dialog.get_vanilla_content_path",
                        lambda: "")
    monkeypatch.setattr("gui.unlock_cost_dialog.async_call",
                        lambda owner, fn, on_done, on_fail=None, name="":
                        on_done(fn()))
    dlg._analyze()
    # la table des bornes est remplie avec les niveaux du scenario
    levels = {dlg._cell_int(r, 0) for r in range(1, dlg.bounds_table.rowCount())}
    assert {1, 2, 3, 5} <= levels
    # plafonne le niveau 5 a 2, puis re-analyse
    for row in range(1, dlg.bounds_table.rowCount()):
        if dlg._cell_int(row, 0) == 5:
            dlg.bounds_table.item(row, 2).setText("2")
    dlg._analyze()
    by_name = {p.name: p for p in dlg._proposals}
    assert by_name["GenWeak"].new_cost <= 2
    assert by_name["GenStrong"].new_cost <= 2
    # GenZero etait resté dans la bande a la passe 1, donc deja <= 2 :
    # il n'apparait plus comme changement mais sa valeur respecte la borne
    assert "GenZero" not in by_name or by_name["GenZero"].new_cost <= 2
    # le niveau 3 (ToolA) n'est pas concerne par la ligne du niveau 5
    assert by_name["ToolA"].new_cost >= 1
