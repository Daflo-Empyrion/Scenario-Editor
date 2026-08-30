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

import shutil
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "tech_tree_scenario"
PENDING = "\x00__pending_preview__"


@pytest.fixture
def config_files(tmp_path):
    blocks = tmp_path / "BlocksConfig.ecf"
    items = tmp_path / "ItemsConfig.ecf"
    shutil.copy(FIXTURE_DIR / "BlocksConfig.ecf", blocks)
    shutil.copy(FIXTURE_DIR / "ItemsConfig.ecf", items)
    return blocks, items


def test_preview_does_not_write_to_disk(qapp, config_files):
    from gui.tech_tree_preview_dialog import TechTreePreviewDialog

    blocks, items = config_files
    original = blocks.read_bytes()
    dlg = TechTreePreviewDialog(blocks, items, None, source="block",
                                 initial_level=1, initial_categories=["Base"])
    dlg._on_level_changed(PENDING, 25)
    dlg._on_category_changed(PENDING, "Weapons")

    assert blocks.read_bytes() == original


def test_pending_node_appears_only_in_starting_category(qapp, config_files):
    from gui.tech_tree_preview_dialog import TechTreePreviewDialog

    blocks, items = config_files
    dlg = TechTreePreviewDialog(blocks, items, None, source="item",
                                 initial_level=1, initial_categories=["Weapons"])
    assert PENDING in dlg._views["Weapons"]._items_by_name
    assert PENDING not in dlg._views["Base"]._items_by_name


def test_level_change_updates_pending_node_only(qapp, config_files):
    from gui.tech_tree_preview_dialog import TechTreePreviewDialog

    blocks, items = config_files
    dlg = TechTreePreviewDialog(blocks, items, None, source="block",
                                 initial_level=1, initial_categories=["Base"])
    real_node_level_before = dlg.tech_tree.get("FuelTankMSLarge").unlock_level

    dlg._on_level_changed(PENDING, 15)

    assert dlg.pending_node.unlock_level == 15
    assert dlg.tech_tree.get("FuelTankMSLarge").unlock_level == real_node_level_before


def test_category_change_moves_pending_node_between_tabs(qapp, config_files):
    from gui.tech_tree_preview_dialog import TechTreePreviewDialog

    blocks, items = config_files
    dlg = TechTreePreviewDialog(blocks, items, None, source="block",
                                 initial_level=1, initial_categories=["Base"])

    dlg._on_category_changed(PENDING, "Weapons")

    assert PENDING not in dlg._views["Base"]._items_by_name
    assert PENDING in dlg._views["Weapons"]._items_by_name
    assert dlg.tabs.currentWidget().category == "Weapons"


def test_result_values_reflects_all_changes(qapp, config_files):
    from gui.tech_tree_preview_dialog import TechTreePreviewDialog

    blocks, items = config_files
    dlg = TechTreePreviewDialog(blocks, items, None, source="item",
                                 initial_level=1, initial_cost=0, initial_categories=["Base"])
    dlg._on_level_changed(PENDING, 20)
    dlg._on_cost_changed(PENDING, 30)
    dlg._on_category_changed(PENDING, "Tools")

    level, cost, categories, parent_name = dlg.result_values()
    assert level == 20
    assert cost == 30
    assert categories == ["Tools"]
    assert parent_name is None


def test_real_nodes_are_not_editable_in_preview(qapp, config_files):
    """Seul le noeud en attente doit etre deplacable -- les noeuds reels
    restent des reperes visuels statiques (voir editable_node_name)."""
    from gui.tech_tree_preview_dialog import TechTreePreviewDialog

    blocks, items = config_files
    dlg = TechTreePreviewDialog(blocks, items, None, source="block",
                                 initial_level=1, initial_categories=["Base"])
    real_item = dlg._views["Base"]._items_by_name["FuelTankMSLarge"]
    pending_item = dlg._views["Base"]._items_by_name[PENDING]
    assert real_item._editable is False
    assert pending_item._editable is True
    assert pending_item._highlighted is True
    assert real_item._highlighted is False
