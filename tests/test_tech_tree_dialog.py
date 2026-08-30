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

from core.scanner import scan_scenario
from core.workspace import Workspace
from core.tech_tree import load_tech_tree

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "tech_tree_scenario"


@pytest.fixture
def dialog_factory(qapp, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: None)

    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    shutil.copy(FIXTURE_DIR / "BlocksConfig.ecf", config_dir / "BlocksConfig.ecf")
    shutil.copy(FIXTURE_DIR / "ItemsConfig.ecf", config_dir / "ItemsConfig.ecf")

    scenario = scan_scenario(tmp_path)
    ws = Workspace(source_a=scenario, source_a_root=tmp_path, working=scenario, working_root=tmp_path)

    def _make(push_undo=None, is_path_modified=None, reload_path=None):
        from gui.tech_tree_dialog import TechTreeDialog
        return TechTreeDialog(ws, push_undo=push_undo, is_path_modified=is_path_modified, reload_path=reload_path)

    return ws, config_dir, _make


def test_dialog_finds_both_config_files(dialog_factory):
    ws, config_dir, make_dialog = dialog_factory
    dlg = make_dialog()
    assert dlg.blocks_path == config_dir / "BlocksConfig.ecf"
    assert dlg.items_path == config_dir / "ItemsConfig.ecf"


def test_dialog_creates_one_tab_per_category(dialog_factory):
    ws, config_dir, make_dialog = dialog_factory
    dlg = make_dialog()
    tree = load_tech_tree(config_dir / "BlocksConfig.ecf", config_dir / "ItemsConfig.ecf")
    assert dlg.tabs.count() == len(tree.categories())


def test_level_change_writes_to_disk_and_pushes_undo(dialog_factory):
    ws, config_dir, make_dialog = dialog_factory
    pushed = []
    dlg = make_dialog(push_undo=lambda action: pushed.append(action))

    dlg._on_level_changed("FuelTankMSLarge", 12)

    assert len(pushed) == 1
    reloaded = load_tech_tree(config_dir / "BlocksConfig.ecf", config_dir / "ItemsConfig.ecf")
    assert reloaded.get("FuelTankMSLarge").unlock_level == 12
    assert dlg.tech_tree.get("FuelTankMSLarge").unlock_level == 12


def test_cost_change_writes_to_disk(dialog_factory):
    ws, config_dir, make_dialog = dialog_factory
    dlg = make_dialog()
    dlg._on_cost_changed("FuelTankMSLarge", 25)
    reloaded = load_tech_tree(config_dir / "BlocksConfig.ecf", config_dir / "ItemsConfig.ecf")
    assert reloaded.get("FuelTankMSLarge").unlock_cost == 25


def test_category_change_moves_node_between_tabs(dialog_factory):
    ws, config_dir, make_dialog = dialog_factory
    dlg = make_dialog()

    assert "FuelTankMSLarge" in dlg._views["Base"]._items_by_name
    assert "FuelTankMSLarge" not in dlg._views["Weapons"]._items_by_name

    dlg._on_category_changed("FuelTankMSLarge", "Weapons")

    assert "FuelTankMSLarge" not in dlg._views["Base"]._items_by_name
    assert "FuelTankMSLarge" in dlg._views["Weapons"]._items_by_name
    reloaded = load_tech_tree(config_dir / "BlocksConfig.ecf", config_dir / "ItemsConfig.ecf")
    assert reloaded.get("FuelTankMSLarge").categories == ["Weapons"]


def test_write_refused_when_file_modified(dialog_factory, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)

    ws, config_dir, make_dialog = dialog_factory
    dlg = make_dialog(is_path_modified=lambda path: True)

    dlg._on_level_changed("FuelTankMSLarge", 12)

    reloaded = load_tech_tree(config_dir / "BlocksConfig.ecf", config_dir / "ItemsConfig.ecf")
    assert reloaded.get("FuelTankMSLarge").unlock_level == 10  # inchange


def test_dialog_has_no_player_level_spinner(dialog_factory):
    """Simplification demandee explicitement (29/08/2026) : le niveau de
    joueur simule n'a plus de sens dans un editeur (utile uniquement en
    jeu)."""
    ws, config_dir, make_dialog = dialog_factory
    dlg = make_dialog()
    assert not hasattr(dlg, "level_spin")


def test_parent_pick_started_shows_banner(dialog_factory):
    ws, config_dir, make_dialog = dialog_factory
    dlg = make_dialog()
    view = dlg._views["Base"]

    view.parent_pick_started.emit("FuelTankMSLarge")

    assert dlg.parent_pick_banner.isHidden() is False
    assert "FuelTankMSLarge" in dlg.parent_pick_label.text()
    assert dlg._active_pick_view is view


def test_parent_pick_finished_hides_banner(dialog_factory):
    ws, config_dir, make_dialog = dialog_factory
    dlg = make_dialog()
    view = dlg._views["Base"]
    view.parent_pick_started.emit("FuelTankMSLarge")

    view.parent_pick_finished.emit()

    assert dlg.parent_pick_banner.isVisible() is False
    assert dlg._active_pick_view is None


def test_parent_changed_writes_to_disk_and_pushes_undo(dialog_factory):
    ws, config_dir, make_dialog = dialog_factory
    pushed = []
    dlg = make_dialog(push_undo=lambda action: pushed.append(action))

    dlg._on_parent_changed("OxygenTankSmallMS", "FuelTankMSSmall")

    assert len(pushed) == 1
    reloaded = load_tech_tree(config_dir / "BlocksConfig.ecf", config_dir / "ItemsConfig.ecf")
    assert reloaded.get("OxygenTankSmallMS").parent_name == "FuelTankMSSmall"
    assert dlg.tech_tree.get("OxygenTankSmallMS").parent_name == "FuelTankMSSmall"


def test_parent_changed_empty_string_removes_parent(dialog_factory):
    ws, config_dir, make_dialog = dialog_factory
    dlg = make_dialog()
    dlg._on_parent_changed("FuelTankMSLarge", "")

    reloaded = load_tech_tree(config_dir / "BlocksConfig.ecf", config_dir / "ItemsConfig.ecf")
    assert reloaded.get("FuelTankMSLarge").parent_name is None


def test_no_parent_button_routes_to_active_view(dialog_factory):
    ws, config_dir, make_dialog = dialog_factory
    dlg = make_dialog()
    view = dlg._views["Base"]
    view.start_parent_pick("FuelTankMSLarge")
    dlg._active_pick_view = view

    received = []
    view.parent_changed.connect(lambda name, parent: received.append((name, parent)))

    dlg._on_no_parent_clicked()

    assert received == [("FuelTankMSLarge", "")]


def test_cancel_pick_button_routes_to_active_view(dialog_factory):
    ws, config_dir, make_dialog = dialog_factory
    dlg = make_dialog()
    view = dlg._views["Base"]
    view.start_parent_pick("FuelTankMSLarge")
    dlg._active_pick_view = view

    dlg._on_cancel_parent_pick_clicked()

    assert view._pending_parent_pick_for is None
