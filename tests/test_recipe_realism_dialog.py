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

"""Recettes realistes (gui/recipe_realism_dialog.py) : construction, chemin
CONNECTE scan -> table -> tout cocher -> application, et re-scan sans
proposition (idempotence). Boites patchees, async synchrone."""

from pathlib import Path

from gui.recipe_realism_dialog import RecipeRealismDialog

BLOCKS = """{ Block Id: 1, Name: GenA
  IndexName: Generator
  Category: Devices
  Mass: 500, type: float, formatter: Kilogram
  TemplateRoot: GenA
}
"""

ITEMS = """{ Item Id: 217, Name: SteelPlate
  Mass: 11.8, type: float, formatter: Kilogram
}
{ Item Id: 219, Name: Motor
  Mass: 24.28, type: float, formatter: Kilogram
}
{ Item Id: 220, Name: Electronics
  Mass: 2.86, type: float, formatter: Kilogram
}
{ Item Id: 221, Name: MechanicalComponents
  Mass: 0.65, type: float, formatter: Kilogram
}
{ Item Id: 222, Name: FluxCoil
  Mass: 39.1, type: float, formatter: Kilogram
}
"""

TEMPLATES = """{ Template Name: GenA
  CraftTime: 5
  OutputCount: 2
  Target: "BaseC"
  { Child Inputs
    SteelPlate: 16
  }
}
{ Template Name: PlatinumOre
  BaseItem: true
  CraftTime: 5
  Target: "BaseC"
  { Child Inputs
    SteelPlate: 1
  }
}
"""


def _scenario(tmp_path: Path) -> Path:
    cdir = tmp_path / "Content" / "Configuration"
    cdir.mkdir(parents=True)
    (cdir / "BlocksConfig.ecf").write_text(BLOCKS, encoding="utf-8")
    (cdir / "ItemsConfig.ecf").write_text(ITEMS, encoding="utf-8")
    (cdir / "Templates.ecf").write_text(TEMPLATES, encoding="utf-8")
    return tmp_path


def _wire(monkeypatch):
    """async synchrone + boites muettes (regle des tests de dialogue)."""
    monkeypatch.setattr("gui.recipe_realism_dialog.async_call",
                        lambda owner, fn, on_done, on_fail=None, name="":
                        on_done(fn()))
    seen = []
    monkeypatch.setattr("gui.recipe_realism_dialog.info",
                        lambda *a, **k: seen.append(a))
    monkeypatch.setattr("gui.recipe_realism_dialog.ask_yes_no",
                        lambda *a, **k: True)
    monkeypatch.setattr("gui.recipe_realism_dialog.get_vanilla_content_path",
                        lambda: "")
    return seen


def test_dialog_builds(qapp):
    dlg = RecipeRealismDialog(None)
    assert dlg.table.columnCount() == 10
    assert dlg.btn_apply.isEnabled() is False
    assert dlg.chk_changed.isChecked() is True


def test_full_flow_scan_check_apply(qapp, tmp_path, monkeypatch):
    root = _scenario(tmp_path)
    dlg = RecipeRealismDialog(None, str(root))
    seen = _wire(monkeypatch)
    dlg._analyze()
    assert dlg.table.rowCount() == 1              # une seule recette traitable
    assert dlg._checked_names() == set()          # RIEN de precoche
    assert "PlatinumOre" in dlg._report.skipped   # ecartee avec motif
    dlg._check_all()
    assert dlg._checked_names() == {"GenA"}
    dlg._apply()
    text = (root / "Content/Configuration/Templates.ecf").read_text(
        encoding="utf-8")
    assert "SteelPlate: 16" not in text           # ancienne recette remplacee
    assert "Electronics:" in text                 # matiere reelle ajoutee
    assert "OutputCount: 2" in text               # conserve
    assert seen, "confirmation affichee"
    # re-scan automatique : plus rien a ecrire (idempotence)
    assert [p for p in dlg._proposals if p.changed] == []
