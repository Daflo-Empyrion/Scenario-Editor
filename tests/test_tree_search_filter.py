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

"""Tests du filtrage en direct des arbres de fichiers (SearchLineEdit
au-dessus de chaque panneau, retour de l'audit rendu du 09/09/2026) :
masquage des non-correspondants, parents d'un resultat conserves et
deployes, restauration de l'expansion d'avant filtrage, re-application
apres repeuplage."""

import core.settings as settings
import gui.fluent_pilot as fluent_pilot
import pytest
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QLineEdit


@pytest.fixture()
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")


@pytest.fixture()
def fresh_window(qapp, isolated_settings):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    fluent_pilot.set_enabled(True)
    apply_theme(qapp, "classic")
    win = MainWindow()
    win.show()
    try:
        yield win
    finally:
        win.close()
        fluent_pilot.set_enabled(False)


def _make_tree() -> QTreeWidget:
    tree = QTreeWidget()
    root = QTreeWidgetItem(["RE2 EVO"])
    tree.addTopLevelItem(root)
    content = QTreeWidgetItem(["Content"])
    config = QTreeWidgetItem(["Configuration"])
    blocks = QTreeWidgetItem(["BlocksConfig.ecf"])
    faction = QTreeWidgetItem(["FactionWarfare.ecf"])
    config.addChild(blocks)
    config.addChild(faction)
    content.addChild(config)
    extras = QTreeWidgetItem(["Extras"])
    extras.addChild(QTreeWidgetItem(["Localization.csv"]))
    root.addChild(content)
    root.addChild(extras)
    root.setExpanded(True)
    content.setExpanded(True)   # Configuration reste fermee, Extras aussi
    return tree


def test_window_has_three_search_boxes(fresh_window):
    win = fresh_window
    assert set(win._tree_search_boxes.keys()) == {win.tree_a, win.tree_working, win.tree_b}
    from qfluentwidgets import SearchLineEdit
    for box in win._tree_search_boxes.values():
        assert isinstance(box, SearchLineEdit)
        assert box.placeholderText() != ""


def test_search_boxes_vanilla_when_pilot_off(qapp, isolated_settings):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    fluent_pilot.set_enabled(False)
    apply_theme(qapp, "classic")
    win = MainWindow()
    try:
        for box in win._tree_search_boxes.values():
            assert type(box) is QLineEdit
    finally:
        win.close()


def test_filter_keeps_matches_and_parents(fresh_window):
    win = fresh_window
    tree = _make_tree()
    win._filter_tree(tree, "faction")
    faction = tree.topLevelItem(0).child(0).child(0).child(1)
    blocks = tree.topLevelItem(0).child(0).child(0).child(0)
    extras = tree.topLevelItem(0).child(1)
    assert faction.isHidden() is False
    assert blocks.isHidden() is True
    assert extras.isHidden() is True
    # parents du resultat visibles ET deployes
    content = tree.topLevelItem(0).child(0)
    config = content.child(0)
    assert content.isHidden() is False and content.isExpanded()
    assert config.isHidden() is False and config.isExpanded()


def test_filter_case_insensitive_and_prefixes(fresh_window):
    win = fresh_window
    tree = _make_tree()
    win._filter_tree(tree, "BLOCKS")
    blocks = tree.topLevelItem(0).child(0).child(0).child(0)
    assert blocks.isHidden() is False


def test_clearing_filter_restores_visibility_and_expansion(fresh_window):
    win = fresh_window
    tree = _make_tree()
    config = tree.topLevelItem(0).child(0).child(0)
    extras = tree.topLevelItem(0).child(1)
    assert config.isExpanded() is False  # fermee avant filtrage
    win._filter_tree(tree, "faction")    # le filtre la deploie
    assert config.isExpanded() is True
    win._filter_tree(tree, "")
    # tout est re-visible et l'expansion d'AVANT filtrage est restituee
    for i in range(tree.topLevelItemCount()):
        item = tree.topLevelItem(i)
        assert item.isHidden() is False
        for j in range(item.childCount()):
            assert item.child(j).isHidden() is False
    assert config.isExpanded() is False  # etat d'origine restitue
    assert extras.isExpanded() is False
    assert tree.topLevelItem(0).isExpanded() is True


def test_search_box_wiring_triggers_filter(fresh_window):
    win = fresh_window
    tree = _make_tree()
    win.tree_a.clear()
    win.tree_a.addTopLevelItem(tree.topLevelItem(0).clone())
    win._tree_search_boxes[win.tree_a].setText("faction")
    loc = win.tree_a.topLevelItem(0).child(1).child(0)
    assert loc.isHidden() is True  # "Localization.csv" ne correspond pas
    win._tree_search_boxes[win.tree_a].clear()
    assert loc.isHidden() is False


def test_populate_reapplies_active_filter(fresh_window, tmp_path):
    from core.models import Scenario
    win = fresh_window
    (tmp_path / "Content" / "Configuration").mkdir(parents=True)
    (tmp_path / "Content" / "Configuration" / "BlocksConfig.ecf").write_text("", encoding="utf-8")
    (tmp_path / "Content" / "Configuration" / "FactionWarfare.ecf").write_text("", encoding="utf-8")
    win._tree_search_boxes[win.tree_working].setText("faction")
    win._populate_tree(win.tree_working, Scenario(root_path=tmp_path))
    config = win.tree_working.topLevelItem(0).child(0).child(0)
    faction = config.child(1)
    blocks = config.child(0)
    assert faction.isHidden() is False
    assert blocks.isHidden() is True
    # champ vide -> le repeuplage laisse tout visible (re-lecture OBLIGATOIRE
    # des items : le premier repeuplage a detruit les references ci-dessus)
    win._tree_search_boxes[win.tree_working].clear()
    win._populate_tree(win.tree_working, Scenario(root_path=tmp_path))
    config2 = win.tree_working.topLevelItem(0).child(0).child(0)
    assert config2.child(0).isHidden() is False
