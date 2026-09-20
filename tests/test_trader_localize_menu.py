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

"""Menu contextuel "Localiser cette valeur" sur SellingText
(TraderNPCConfig.ecf, v1.10.0) : reproduction offscreen du parcours reel
(ouverture de l'onglet, selection du bloc, clic droit capture) pour
verifier que l'entree est bien presente et que le declenchement
localise la valeur (cle generee + ligne Localization.csv)."""

import shutil

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMenu

TRADER_TEXT = """{ Trader Name: QuantumSTAR
  SellingText: "Hi, I am trader <NAME>."
  SellingGoods: "trwFood"
}
"""


@pytest.fixture
def trader_scenario(qapp, tmp_path, monkeypatch):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from core.scanner import scan_scenario
    from core.workspace import Workspace

    apply_theme(qapp)
    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    (config_dir / "TraderNPCConfig.ecf").write_text(
        TRADER_TEXT, encoding="utf-8")

    scenario = scan_scenario(tmp_path)
    window = MainWindow()
    window.workspace = Workspace(source_a=scenario, source_a_root=tmp_path,
                                 working=scenario, working_root=tmp_path)
    widget = window.open_working_file_tab(config_dir / "TraderNPCConfig.ecf")
    edit_widget = widget.edit_widget

    # selectionner le bloc Trader dans l'arbre (remplit la table de props)
    it = edit_widget.tree.topLevelItem(0)
    edit_widget._on_block_selected(it, 0)
    return window, edit_widget, tmp_path


def _selling_row(edit_widget):
    table = edit_widget.props_table
    for r in range(table.rowCount()):
        key_item = table.item(r, 0)
        if key_item is not None and key_item.text() == "SellingText":
            return r, key_item, table.item(r, 1)
    return None, None, None


def _capture_menu(monkeypatch):
    """Remplace QMenu.exec : capture le menu, simule le clic sur l'action
    'Localiser cette valeur' si presente, sinon renvoie None."""
    captured = {"menu": None}
    real_addAction = QMenu.addAction

    def fake_exec(self, pos, *a, **k):
        captured["menu"] = self
        for action in self.actions():
            if action.text() and "Localiser" in action.text():
                return action
        return None
    monkeypatch.setattr(QMenu, "exec", fake_exec)
    return captured


def test_context_menu_shows_and_runs_localize(trader_scenario, monkeypatch,
                                              tmp_path_factory):
    window, edit_widget, tmp_path = trader_scenario
    row, key_item, value_item = _selling_row(edit_widget)
    assert row is not None, "ligne SellingText absente de la table"

    captured = _capture_menu(monkeypatch)
    localize_results = []
    monkeypatch.setattr(edit_widget, "_localize_selling_text",
                        lambda item: localize_results.append(item.text()))

    rect = edit_widget.props_table.visualItemRect(value_item)
    edit_widget._show_table_context_menu(rect.center())

    menu = captured["menu"]
    assert menu is not None
    texts = [a.text() for a in menu.actions() if a.text()]
    localize_actions = [t for t in texts if "Localiser" in t]
    print("ACTIONS DU MENU :", texts)
    print("PAIR_KEY ligne SellingText :",
          value_item.data(Qt.ItemDataRole.UserRole))
    assert localize_actions, f"entree absente du menu : {texts}"
    assert localize_results, "l'action n'a pas declenche la localisation"


def test_localize_generates_key_and_localization_row(trader_scenario,
                                                     monkeypatch):
    window, edit_widget, tmp_path = trader_scenario
    row, key_item, value_item = _selling_row(edit_widget)
    # neutraliser la confirmation modale
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "information", staticmethod(
        lambda *a, **k: None))
    edit_widget._localize_selling_text(value_item)

    assert value_item.text() == '"scn_Selling_QuantumSTAR"'
    loc = tmp_path / "Content" / "Extras" / "Localization.csv"
    # pas de fichier racine Extras dans ce scenario de test : Content/Extras
    assert loc.exists() or (tmp_path / "Extras" / "Localization.csv").exists()
