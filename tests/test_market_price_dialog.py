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

"""Prix marche (gui/market_price_dialog.py) : construction, chemin CONNECTÉ
scan -> table -> filtres -> cocher hors bornes -> retarget -> application
(vecu 11/10 : un slot direct avec un tuple ne marche pas — les slots sont
appeles individuellement, les boites sont patchees, async_call moque)."""

from pathlib import Path

from PyQt6.QtCore import Qt

from gui.market_price_dialog import MarketPriceDialog

ECF = {
 "ItemsConfig.ecf": """{ Item Name: RockDust
  MarketPrice: 2
}
{ Item Name: IronIngot
  MarketPrice: 4
}
{ Item Name: CheapThing
  MarketPrice: 3
}
{ Item Name: AnchoredThing
  MarketPrice: 77
}
{ Item Name: NoPrice
  StackSize: 50
}
""",
 "Templates.ecf": """{ Template Name: IronIngot
  CraftTime: 10
  OutputCount: 2
  { Child Inputs
    RockDust: 10
  }
}
{ Template Name: CheapThing
  CraftTime: 5
  { Child Inputs
    RockDust: 10
  }
}
""",
 "BlocksConfig.ecf": """{ Block Id: 500, Name: Pillar
  MarketPrice: 5000
}
""",
}


def _scenario(tmp_path: Path) -> Path:
    cdir = tmp_path / "Content" / "Configuration"
    cdir.mkdir(parents=True)
    for name, text in ECF.items():
        (cdir / name).write_text(text, encoding="utf-8")
    return tmp_path


def _row(dlg, name):
    for row in range(dlg.table.rowCount()):
        if dlg._name_at(row) == name:
            return row
    return -1


def test_dialog_builds(qapp):
    dlg = MarketPriceDialog(None)
    assert dlg.table.columnCount() == 9
    assert dlg.spin_margin.value() == 1.0
    assert dlg.spin_fab.value() == 0.0
    assert dlg.btn_apply.isEnabled() is False


def test_cost_display_keeps_decimals():
    """Vecu 28/10 : une munition a un cout unitaire de 0.42 — l'ancien
    arrondi entier affichait « 0 » en colonne cout."""
    from gui.market_price_dialog import _fmt_cost
    assert _fmt_cost(0.416) == "0.42"
    assert _fmt_cost(0.0) == "0"
    assert _fmt_cost(12.5) == "12.5"
    assert _fmt_cost(1234.0) == "1 234"


def test_full_flow_scan_filter_check_apply(qapp, tmp_path, monkeypatch):
    root = _scenario(tmp_path)
    dlg = MarketPriceDialog(None, str(root))
    # async synchrone : le scan et l'application sont executes immédiatement
    monkeypatch.setattr("gui.market_price_dialog.async_call",
                        lambda owner, fn, on_done, on_fail=None, name="":
                        on_done(fn()))
    msgs = []
    monkeypatch.setattr("gui.market_price_dialog.info",
                        lambda *a, **k: msgs.append(a))
    monkeypatch.setattr("gui.market_price_dialog.ask_yes_no",
                        lambda *a, **k: True)
    dlg._analyze()
    assert not dlg._running
    assert dlg._report is not None
    # RockDust feuille ; IronIngot cout 10 (10x2 / 2) ; CheapThing cout 20
    # (10x2) ; AnchoredThing ancrage ; NoPrice non vendable masquee par defaut
    assert dlg._by_name["IronIngot"].cost == 10.0
    assert dlg._by_name["AnchoredThing"].status == "ancrage"
    assert dlg.table.isRowHidden(_row(dlg, "NoPrice"))
    assert not dlg.table.isRowHidden(_row(dlg, "RockDust"))
    # rien de precoche
    assert dlg._checked_names() == set()
    # bornes defaut 0.80-1.25 : IronIngot 4/10=0.4 et CheapThing 3/20=0.15
    # hors bornes ; RockDust 1.0 dedans ; Pillar ancrage jamais coche
    dlg._check_outofbounds()
    assert dlg._checked_names() == {"IronIngot", "CheapThing"}
    # retarget : marge x2 double les cibles sans re-parse ni perte de coche
    dlg.spin_margin.setValue(2.0)
    assert dlg._by_name["IronIngot"].target == 20
    assert dlg._checked_names() == {"IronIngot", "CheapThing"}
    dlg.spin_margin.setValue(1.0)
    # filtre nom
    dlg.edit_name.setText("iron")
    assert dlg.table.isRowHidden(_row(dlg, "CheapThing"))
    assert not dlg.table.isRowHidden(_row(dlg, "IronIngot"))
    dlg.edit_name.setText("")
    # decheck CheapThing : on n'applique que IronIngot 4 -> 10
    dlg.table.item(_row(dlg, "CheapThing"), 0).setCheckState(
        Qt.CheckState.Unchecked)
    assert dlg._checked_names() == {"IronIngot"}
    # tout cocher respecte les FILTRES : seules les lignes visibles
    dlg.edit_name.setText("cheapthing")
    dlg._check_all()
    assert dlg._checked_names() == {"CheapThing"}
    dlg.edit_name.setText("")
    dlg._uncheck_all()
    dlg._check_outofbounds()
    dlg.table.item(_row(dlg, "CheapThing"), 0).setCheckState(
        Qt.CheckState.Unchecked)
    assert dlg._checked_names() == {"IronIngot"}
    dlg._apply()
    text = (root / "Content/Configuration/ItemsConfig.ecf").read_text(
        encoding="utf-8")
    assert "MarketPrice: 10" in text
    assert msgs, "confirmation d'application affichee"


def test_sort_keeps_rows_consistent(qapp, tmp_path, monkeypatch):
    """Le tri deplace les lignes : le nom doit rester lu depuis la table
    (self._row_names serait desynchronise)."""
    root = _scenario(tmp_path)
    dlg = MarketPriceDialog(None, str(root))
    monkeypatch.setattr("gui.market_price_dialog.async_call",
                        lambda owner, fn, on_done, on_fail=None, name="":
                        on_done(fn()))
    dlg._analyze()
    dlg.table.sortItems(4)          # tri par prix decroissant/croissant
    assert dlg._by_name[dlg._name_at(_row(dlg, "Pillar"))].price == 5000


def test_generation_flow(qapp, tmp_path, monkeypatch):
    """Famille -> bouton Generer actif -> confirmation -> recette ecrite
    dans Templates.ecf -> re-scan : l'item passe fabriquable."""
    from test_market_balance import FAM_ITEMS, FAM_TEMPLATES
    cdir = tmp_path / "Content" / "Configuration"
    cdir.mkdir(parents=True)
    (cdir / "ItemsConfig.ecf").write_text(FAM_ITEMS, encoding="utf-8")
    (cdir / "Templates.ecf").write_text(FAM_TEMPLATES, encoding="utf-8")
    (cdir / "BlocksConfig.ecf").write_text(
        "{ Block Id: 500, Name: Pillar\n  MarketPrice: 40\n}\n",
        encoding="utf-8")
    monkeypatch.setattr("gui.market_price_dialog.async_call",
                        lambda owner, fn, on_done, on_fail=None, name="":
                        on_done(fn()))
    monkeypatch.setattr("gui.market_price_dialog.ask_yes_no",
                        lambda *a, **k: True)
    msgs = []
    monkeypatch.setattr("gui.market_price_dialog.info",
                        lambda parent, title, text: msgs.append(text))

    dlg = MarketPriceDialog(None, str(tmp_path))
    assert dlg.cmb_status.findData("famille") >= 0
    assert dlg.btn_gen.isEnabled() is False
    dlg._analyze()
    assert dlg.btn_gen.isEnabled() is True        # OldPistol generable
    row = _row(dlg, "OldPistol")
    assert dlg._by_name["OldPistol"].status == "famille"

    dlg.btn_gen.click()
    tpath = tmp_path / "Content" / "Configuration" / "Templates.ecf"
    assert "+Template Name: OldPistol" in tpath.read_text(encoding="utf-8")
    assert msgs and "générée" in msgs[0]
    # re-scan automatique : OldPistol est maintenant fabriquable
    assert dlg._by_name["OldPistol"].status == "fabriquable"
    assert dlg.btn_gen.isEnabled() is False       # plus rien a generer


def test_status_filter_famille(qapp, tmp_path, monkeypatch):
    from test_market_balance import FAM_ITEMS, FAM_TEMPLATES
    cdir = tmp_path / "Content" / "Configuration"
    cdir.mkdir(parents=True)
    (cdir / "ItemsConfig.ecf").write_text(FAM_ITEMS, encoding="utf-8")
    (cdir / "Templates.ecf").write_text(FAM_TEMPLATES, encoding="utf-8")
    (cdir / "BlocksConfig.ecf").write_text(
        "{ Block Id: 500, Name: Pillar\n  MarketPrice: 40\n}\n",
        encoding="utf-8")
    monkeypatch.setattr("gui.market_price_dialog.async_call",
                        lambda owner, fn, on_done, on_fail=None, name="":
                        on_done(fn()))
    dlg = MarketPriceDialog(None, str(tmp_path))
    dlg._analyze()
    dlg.cmb_status.setCurrentIndex(dlg.cmb_status.findData("famille"))
    assert not dlg.table.isRowHidden(_row(dlg, "OldPistol"))
    assert dlg.table.isRowHidden(_row(dlg, "PistolA"))


def test_info_button_consequences_follow_spins(qapp, tmp_path):
    """Le bouton info construit une fenetre dont le texte reflète les
    VALEURS CHOISIES : multiplicateur, %/palier, derive 5 niveaux, et le
    cas marge 1.0 = zero boucle."""
    from PyQt6.QtWidgets import QTextBrowser
    root = _scenario(tmp_path)
    dlg = MarketPriceDialog(None, str(root))
    assert dlg.btn_info.isEnabled()

    dlg.spin_margin.setValue(1.10)
    dlg.spin_fab.setValue(10.0)
    info = dlg._build_info_dialog()
    html = info._html
    assert "1.21" in html                      # 1.10 x 1.10
    assert "21" in html                        # +21 %/palier
    assert "2.59" in html                      # derive 5 niveaux (1.21^5)
    tb = info.findChild(QTextBrowser)
    assert tb is not None and tb.toHtml()      # rendu HTML present

    dlg.spin_margin.setValue(1.0)
    dlg.spin_fab.setValue(0.0)
    zero = dlg._build_info_dialog()
    assert "1" in zero._html and "2.59" not in zero._html
    assert "zéro boucle" in zero._html
