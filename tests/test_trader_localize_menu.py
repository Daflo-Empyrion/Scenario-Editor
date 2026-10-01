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
            if action.text() and "localisation" in action.text().lower():
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
    monkeypatch.setattr(edit_widget, "_create_localization",
                        lambda item: localize_results.append(item.text()))

    rect = edit_widget.props_table.visualItemRect(value_item)
    edit_widget._show_table_context_menu(rect.center())

    menu = captured["menu"]
    assert menu is not None
    texts = [a.text() for a in menu.actions() if a.text()]
    localize_actions = [t for t in texts if "localisation" in t.lower()]
    print("ACTIONS DU MENU :", texts)
    print("PAIR_KEY ligne SellingText :",
          value_item.data(Qt.ItemDataRole.UserRole))
    assert localize_actions, f"entree absente du menu : {texts}"
    assert localize_results, "l'action n'a pas declenche la localisation"


def _accept_dialog_automatically(monkeypatch, forced_en=None):
    """Le vrai dialogue avec exec() -> True (champs pre-remplis par le
    flux, texte English complete si fourni). Retourne la liste des
    instances ouvertes pour inspecter les pre-remplissages."""
    from gui import ecf_edit_widget as mod
    opened = []

    class FakeDlg(mod.LocalizationEntryDialog):
        def __init__(self, key, english_text, replaces_cell, loc_path,
                     parent=None):
            super().__init__(key, english_text, replaces_cell, loc_path,
                             parent)
            if forced_en is not None and not self.en_edit.text():
                self.en_edit.setText(forced_en)
            opened.append(self)

        def exec(self):
            return True
    monkeypatch.setattr(mod, "LocalizationEntryDialog", FakeDlg)
    return opened


def test_localize_generates_key_and_localization_row(trader_scenario,
                                                     monkeypatch):
    window, edit_widget, tmp_path = trader_scenario
    row, key_item, value_item = _selling_row(edit_widget)
    # neutraliser la confirmation modale
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "information", staticmethod(
        lambda *a, **k: None))
    opened = _accept_dialog_automatically(monkeypatch, forced_en="Hi")
    edit_widget._create_localization(value_item)

    # pre-remplissage historique : cle scn_Selling_<Nom> + texte libre
    assert opened[0].key_edit.text() == "scn_Selling_QuantumSTAR"
    assert opened[0]._replaces_cell is True
    assert value_item.text() == '"scn_Selling_QuantumSTAR"'
    loc = tmp_path / "Content" / "Extras" / "Localization.csv"
    # pas de fichier racine Extras dans ce scenario de test : Content/Extras
    assert loc.exists() or (tmp_path / "Extras" / "Localization.csv").exists()


def test_menu_dismiss_triggers_nothing_on_other_cells(trader_scenario,
                                                      monkeypatch):
    """Vecu 20/09 : fermer le menu (clic a cote) renvoie None de
    menu.exec ; l'action Localiser valait None aussi sur les cellules non
    SellingText -> None == None declenchait la localisation. Toute
    fermeture sans choix ne doit RIEN faire (idem partout dans l'appli)."""
    window, edit_widget, tmp_path = trader_scenario
    monkeypatch.setattr(QMenu, "exec",
                        lambda self, pos, *a, **k: None)
    localize_calls = []
    duplicate_calls = []
    monkeypatch.setattr(edit_widget, "_create_localization",
                        lambda item: localize_calls.append(item))
    monkeypatch.setattr(edit_widget, "_duplicate_row_action",
                        lambda prop: duplicate_calls.append(prop))

    table = edit_widget.props_table
    fired = False
    for r in range(table.rowCount()):
        key_item = table.item(r, 0)
        # toute cellule SAUT la valeur SellingText : autres valeurs + cles
        if key_item is None or key_item.text() != "SellingText":
            for c in (0, 1):
                it = table.item(r, c)
                if it is None:
                    continue
                rect = table.visualItemRect(it)
                edit_widget._show_table_context_menu(rect.center())
                fired = True
    assert fired, "aucune cellule non-SellingText a tester"
    assert not localize_calls, "la localisation s'est declenchee au clic droit"
    assert not duplicate_calls, "la duplication s'est declenchee au clic droit"
    assert not (tmp_path / "Content" / "Extras" / "Localization.csv").exists()


def test_localize_offered_on_every_body_cell(trader_scenario, monkeypatch):
    """Generalisation 30/09 : l'action est proposee sur TOUTES les
    proprietes de corps (plus seulement SellingText de TraderNPCConfig).
    Une valeur deja-cle (SellingGoods: trwFood) pre-remplit CETTE cle et
    ne touche PAS a la cellule ; seule la ligne CSV est ajoutee."""
    from PyQt6.QtWidgets import QMessageBox
    window, edit_widget, tmp_path = trader_scenario
    monkeypatch.setattr(QMessageBox, "information", staticmethod(
        lambda *a, **k: None))
    table = edit_widget.props_table
    row, key_item, value_item = _selling_row(edit_widget)
    goods_row = None
    for r in range(table.rowCount()):
        ki = table.item(r, 0)
        if ki is not None and ki.text() == "SellingGoods":
            goods_row = r
    assert goods_row is not None, "SellingGoods absente du fixture"
    opened = _accept_dialog_automatically(monkeypatch, forced_en="Food")
    edit_widget._create_localization(table.item(goods_row, 1))

    assert opened[0].key_edit.text() == "trwFood"     # valeur deja une cle
    assert opened[0]._replaces_cell is False
    assert table.item(goods_row, 1).text().strip('"') == "trwFood"
    loc = tmp_path / "Content" / "Extras" / "Localization.csv"
    # creation a la racine du scenario en priorite (convention scanner),
    # comme le flux historique SellingText
    if not loc.exists():
        loc = tmp_path / "Extras" / "Localization.csv"
    assert loc.exists(), "la ligne trwFood devait etre creee"
    content = loc.read_text(encoding="utf-8")
    assert "trwFood" in content and "Food" in content
