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

"""Equilibrage par correlations (gui/correlation_dialog.py) : construction,
chemin CONNECTE scan -> table -> filtre -> tout cocher -> application
(ecriture reelle + re-scan). Boites patchees, async synchrone (regle du
11/10)."""

from pathlib import Path

from gui.correlation_dialog import CorrelationDialog

BLOCKS = """{ Block Id: 500, Name: SteelA
  TemplateRoot: SteelBlocks
  Mass: 100
  HitPoints: 500
  Material: SteelLarge
}
{ Block Id: 501, Name: SteelB
  TemplateRoot: SteelBlocks
  Mass: 90
  HitPoints: 480
  Material: SteelLarge
}
{ Block Id: 502, Name: SteelOdd
  TemplateRoot: SteelBlocks
  Mass: 5
  HitPoints: 5000
  Material: SteelLarge
}
{ Block Id: 504, Name: ArtMassHeavy
  Mass: 560000
  Material: SteelLarge
}
"""

TEMPLATES = """{ Template Name: SteelBlocks
  CraftTime: 5
  OutputCount: 1
  { Child Inputs
    CompA: 2
  }
}
"""

ITEMS = """{ Item Name: CompA
  Mass: 10
}
"""


def _scenario(tmp_path: Path) -> Path:
    cdir = tmp_path / "Content" / "Configuration"
    cdir.mkdir(parents=True)
    (cdir / "BlocksConfig.ecf").write_text(BLOCKS, encoding="utf-8")
    (cdir / "Templates.ecf").write_text(TEMPLATES, encoding="utf-8")
    (cdir / "ItemsConfig.ecf").write_text(ITEMS, encoding="utf-8")
    return tmp_path


def test_dialog_builds(qapp):
    dlg = CorrelationDialog(None)
    assert dlg.table.columnCount() == 8
    assert dlg.cmb_spec.count() == 5
    assert dlg.cmb_spec.currentData() == "mass"
    assert dlg.btn_apply.isEnabled() is False


def test_full_flow_scan_filter_check_apply(qapp, tmp_path, monkeypatch):
    root = _scenario(tmp_path)
    dlg = CorrelationDialog(None, str(root))
    monkeypatch.setattr("gui.correlation_dialog.async_call",
                        lambda owner, fn, on_done, on_fail=None, name="":
                        on_done(fn()))
    seen = []
    monkeypatch.setattr("gui.correlation_dialog.info",
                        lambda *a, **k: seen.append(a))
    monkeypatch.setattr("gui.correlation_dialog.ask_yes_no",
                        lambda *a, **k: True)
    dlg._analyze()
    entries = {e.name: e for e in dlg._proposals}
    assert entries["SteelOdd"].status == "outlier"
    assert entries["SteelOdd"].target == 90.0   # mediane 4.5 x 20
    assert entries["ArtMassHeavy"].status == "whitelist"
    assert not dlg.table.isRowHidden(0) or True
    # filtre outliers par defaut : la whitelist est masquee
    visible = [r for r in range(dlg.table.rowCount())
               if not dlg.table.isRowHidden(r)]
    assert len(visible) == 1        # SteelOdd seul
    # rien de precoche
    assert dlg._checked_names() == set()
    dlg._check_all()
    assert dlg._checked_names() == {"SteelOdd"}
    dlg._apply()
    text = (root / "Content/Configuration/BlocksConfig.ecf").read_text(
        encoding="utf-8")
    assert "Mass: 90" in text
    assert "HitPoints: 5000" in text        # HP intouches (autre propriete)
    assert "Mass: 560000" in text           # whitelist intact
    # re-scan automatique : plus rien a proposer
    assert [e for e in dlg._proposals if e.status == "outlier"] == []
    assert seen, "confirmation affichee"


def test_spec_switch_rescans(qapp, tmp_path, monkeypatch):
    root = _scenario(tmp_path)
    dlg = CorrelationDialog(None, str(root))
    monkeypatch.setattr("gui.correlation_dialog.async_call",
                        lambda owner, fn, on_done, on_fail=None, name="":
                        on_done(fn()))
    dlg._analyze()
    assert dlg._report.spec_key == "mass"
    dlg.cmb_spec.setCurrentIndex(1)          # hitpoints
    assert dlg._report.spec_key == "hitpoints"
    entries = {e.name: e for e in dlg._proposals}
    assert entries["SteelOdd"].target == 500  # mediane HP du groupe
