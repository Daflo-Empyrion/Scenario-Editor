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

"""Recettes de craft coherentes (gui/recipe_balance_dialog.py) :
construction et chemin CONNECTE scan -> table -> tout cocher ->
application (ecriture reelle + re-scan). Boites patchees, async
synchrone (regle du 11/10)."""

from pathlib import Path

from gui.recipe_balance_dialog import RecipeBalanceDialog

BLOCKS = """{ Block Id: 1, Name: GenA
  Class: Generator
  Category: Devices
  TechTreeNames: "Small Vessel"
  EnergyOut: 100
  UnlockLevel: 1
  TemplateRoot: GenA
}
{ Block Id: 2, Name: GenB
  Class: Generator
  Category: Devices
  TechTreeNames: "Small Vessel"
  EnergyOut: 200
  UnlockLevel: 2
  TemplateRoot: GenB
}
"""

ITEMS = """{ Item Id: 10, Name: CompA
  MarketPrice: 10
}
{ Item Id: 11, Name: CompB
  MarketPrice: 5
}
"""

TEMPLATES = """{ Template Name: GenA
  CraftTime: 5
  { Child Inputs
    CompA: 5
  }
}
{ Template Name: GenB
  CraftTime: 5
  { Child Inputs
    CompA: 3
  }
}
"""

VANILLA_TEMPLATES = """{ Template Name: GenA
  CraftTime: 4
  { Child Inputs
    CompA: 2
    CompB: 1
  }
}
"""

VANILLA_BLOCKS = """{ Block Id: 1, Name: GenA
  Class: Generator
  Category: Devices
}
"""


def _scenario(tmp_path: Path):
    cdir = tmp_path / "Content" / "Configuration"
    cdir.mkdir(parents=True)
    (cdir / "BlocksConfig.ecf").write_text(BLOCKS, encoding="utf-8")
    (cdir / "ItemsConfig.ecf").write_text(ITEMS, encoding="utf-8")
    (cdir / "Templates.ecf").write_text(TEMPLATES, encoding="utf-8")
    vdir = tmp_path / "vanilla" / "Configuration"
    vdir.mkdir(parents=True)
    (vdir / "BlocksConfig.ecf").write_text(VANILLA_BLOCKS, encoding="utf-8")
    (vdir / "ItemsConfig.ecf").write_text(ITEMS, encoding="utf-8")
    (vdir / "Templates.ecf").write_text(VANILLA_TEMPLATES, encoding="utf-8")
    return tmp_path, tmp_path / "vanilla"


def test_dialog_builds(qapp):
    dlg = RecipeBalanceDialog(None)
    assert dlg.table.columnCount() == 11
    assert dlg.btn_apply.isEnabled() is False
    assert dlg.chk_changed.isChecked() is True


def test_full_flow_scan_check_apply(qapp, tmp_path, monkeypatch):
    root, vanilla = _scenario(tmp_path)
    dlg = RecipeBalanceDialog(None, str(root))
    monkeypatch.setattr("gui.recipe_balance_dialog.get_vanilla_content_path",
                        lambda: str(vanilla))
    monkeypatch.setattr("gui.recipe_balance_dialog.async_call",
                        lambda owner, fn, on_done, on_fail=None, name="":
                        on_done(fn()))
    seen = []
    monkeypatch.setattr("gui.recipe_balance_dialog.info",
                        lambda *a, **k: seen.append(a))
    monkeypatch.setattr("gui.recipe_balance_dialog.ask_yes_no",
                        lambda *a, **k: True)
    dlg._analyze()
    assert dlg.table.rowCount() == 2
    assert dlg._checked_names() == set()          # rien de precoche
    dlg._check_all()
    assert dlg._checked_names() == {"GenA", "GenB"}
    dlg._apply()
    text = (root / "Content/Configuration/Templates.ecf").read_text(
        encoding="utf-8")
    assert "CompB: 2" in text                     # composition vanille GenA
    assert "CompA: 4" in text                     # GenB remonte
    assert seen, "confirmation affichee"
    # re-scan automatique : les deux recettes sont maintenant alignees
    assert [p for p in dlg._proposals if p.changed] == []
