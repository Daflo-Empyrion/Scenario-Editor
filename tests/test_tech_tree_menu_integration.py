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

"""
Tests d'integration de l'action menu 'Arbre technologique' (voir
gui/main_window.py::_open_tech_tree_dialog) -- verifie que le menu ouvre bien
la fenetre attendue avec le bon workspace, et gere proprement l'absence de
BlocksConfig.ecf/ItemsConfig.ecf.
"""
import shutil
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "tech_tree_scenario"


@pytest.fixture
def window_with_scenario(qapp, tmp_path):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from core.scanner import scan_scenario
    from core.workspace import Workspace

    apply_theme(qapp)
    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    shutil.copy(FIXTURE_DIR / "BlocksConfig.ecf", config_dir / "BlocksConfig.ecf")
    shutil.copy(FIXTURE_DIR / "ItemsConfig.ecf", config_dir / "ItemsConfig.ecf")

    scenario = scan_scenario(tmp_path)
    window = MainWindow()
    window.workspace = Workspace(source_a=scenario, source_a_root=tmp_path,
                                  working=scenario, working_root=tmp_path)
    return window, config_dir


def test_menu_action_exists(window_with_scenario):
    window, config_dir = window_with_scenario
    assert window.action_tech_tree is not None


def test_open_tech_tree_dialog_creates_dialog(window_with_scenario):
    window, config_dir = window_with_scenario
    window._open_tech_tree_dialog()
    assert window._tech_tree_dialog is not None
    assert window._tech_tree_dialog.blocks_path == config_dir / "BlocksConfig.ecf"


def test_open_tech_tree_dialog_without_workspace_shows_message(qapp, monkeypatch):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from PyQt6.QtWidgets import QMessageBox

    apply_theme(qapp)
    called = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: called.append(a))
    window = MainWindow()
    window.workspace = None

    window._open_tech_tree_dialog()

    assert len(called) == 1


def test_open_tech_tree_dialog_without_config_files_shows_message(qapp, tmp_path, monkeypatch):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from core.scanner import scan_scenario
    from core.workspace import Workspace
    from PyQt6.QtWidgets import QMessageBox

    apply_theme(qapp)
    called = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: called.append(a))
    scenario = scan_scenario(tmp_path)
    window = MainWindow()
    window.workspace = Workspace(source_a=scenario, source_a_root=tmp_path,
                                  working=scenario, working_root=tmp_path)

    window._open_tech_tree_dialog()

    assert len(called) == 1


def test_is_path_modified_false_for_unmodified_open_tab(window_with_scenario):
    """Un onglet ouvert SANS modification n'empeche PLUS l'ecriture de
    l'arbre technologique (voir _reload_tab_if_open_and_unmodified, qui
    resynchronise cet onglet ensuite) -- demande explicite de l'utilisateur
    (session du 29/08/2026) : pouvoir observer les changements EN DIRECT
    dans un onglet deja ouvert."""
    window, config_dir = window_with_scenario
    blocks_path = config_dir / "BlocksConfig.ecf"
    window.open_working_file_tab(blocks_path)

    assert window._is_path_modified(blocks_path) is False


def test_is_path_modified_true_for_modified_open_tab(window_with_scenario):
    """Un onglet AVEC des modifications non enregistrees continue de
    bloquer l'ecriture -- ne jamais ecraser un travail en cours."""
    window, config_dir = window_with_scenario
    blocks_path = config_dir / "BlocksConfig.ecf"
    widget = window.open_working_file_tab(blocks_path)
    edit_widget = getattr(widget, 'edit_widget', widget)
    edit_widget._set_modified(True)

    assert window._is_path_modified(blocks_path) is True


def test_is_path_modified_false_when_not_open(window_with_scenario):
    window, config_dir = window_with_scenario
    blocks_path = config_dir / "BlocksConfig.ecf"
    assert window._is_path_modified(blocks_path) is False


def test_reload_tab_if_open_and_unmodified_reloads_content(window_with_scenario):
    """Demande explicite de l'utilisateur (29/08/2026) : voir la valeur
    changer EN DIRECT dans l'onglet deja ouvert apres une ecriture externe
    (ici simulee par une modification directe du fichier sur disque)."""
    window, config_dir = window_with_scenario
    blocks_path = config_dir / "BlocksConfig.ecf"
    widget = window.open_working_file_tab(blocks_path)
    edit_widget = getattr(widget, 'edit_widget', widget)
    original_doc_id = id(edit_widget.doc)

    # Simule une ecriture externe (ce que fait TechTreeDialog._reload_path
    # apres avoir modifie le fichier).
    from core.tech_tree import set_unlock_level
    set_unlock_level(blocks_path, "FuelTankMSLarge", 12)

    window._reload_tab_if_open_and_unmodified(blocks_path)

    assert id(edit_widget.doc) != original_doc_id  # doc reellement recharge
    reloaded_block = next(b for b in edit_widget.doc.iter_blocks() if b.get('Name') == 'FuelTankMSLarge')
    assert reloaded_block.get_property('UnlockLevel') == '12'


def test_reload_tab_if_open_and_unmodified_skips_if_modified(window_with_scenario):
    """Ne doit JAMAIS ecraser un travail en cours -- si l'onglet a des
    modifications non enregistrees, le rechargement est ignore."""
    window, config_dir = window_with_scenario
    blocks_path = config_dir / "BlocksConfig.ecf"
    widget = window.open_working_file_tab(blocks_path)
    edit_widget = getattr(widget, 'edit_widget', widget)
    edit_widget._set_modified(True)
    original_doc = edit_widget.doc

    window._reload_tab_if_open_and_unmodified(blocks_path)

    assert edit_widget.doc is original_doc  # inchange


def test_reload_tab_if_open_and_unmodified_noop_when_not_open(window_with_scenario):
    window, config_dir = window_with_scenario
    blocks_path = config_dir / "BlocksConfig.ecf"
    window._reload_tab_if_open_and_unmodified(blocks_path)  # ne doit pas lever
