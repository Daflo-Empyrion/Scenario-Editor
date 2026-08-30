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
Tests du bouton "Previsualiser dans l'arbre technologique..." de
PropertyTableDialog (voir gui/add_block_dialog.py) -- verifie la detection du
fichier (Blocks/Items/ni-l-un-ni-l'autre), la lecture des valeurs de depart
depuis le tableau de proprietes, et le report du resultat de la
previsualisation dans ce meme tableau.
"""
import shutil
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QDialog

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "tech_tree_scenario"

PENDING = "\x00__pending_preview__"


@pytest.fixture
def working_files(qapp, tmp_path):
    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    shutil.copy(FIXTURE_DIR / "BlocksConfig.ecf", config_dir / "BlocksConfig.ecf")
    shutil.copy(FIXTURE_DIR / "ItemsConfig.ecf", config_dir / "ItemsConfig.ecf")
    return tmp_path, config_dir


def _make_widget(config_dir, tmp_path, filename="BlocksConfig.ecf"):
    from gui.ecf_edit_widget import EcfEditWidget
    return EcfEditWidget(
        config_dir / filename,
        sibling_ecf_files=[config_dir / "BlocksConfig.ecf", config_dir / "ItemsConfig.ecf"],
        working_root=tmp_path)


def test_tech_tree_source_detected_for_blocks_config(working_files):
    tmp_path, config_dir = working_files
    widget = _make_widget(config_dir, tmp_path, "BlocksConfig.ecf")
    assert widget._tech_tree_source_for_current_file() == "block"


def test_tech_tree_source_detected_for_items_config(working_files):
    tmp_path, config_dir = working_files
    widget = _make_widget(config_dir, tmp_path, "ItemsConfig.ecf")
    assert widget._tech_tree_source_for_current_file() == "item"


def test_tech_tree_source_none_for_other_files(qapp, tmp_path):
    from gui.ecf_edit_widget import EcfEditWidget
    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    (config_dir / "LootGroups.ecf").write_text("{ LootGroup Name: X\n}\n", encoding="utf-8")
    widget = EcfEditWidget(config_dir / "LootGroups.ecf")
    assert widget._tech_tree_source_for_current_file() is None


def _make_property_table_dialog(working_files, filename="BlocksConfig.ecf"):
    from gui.add_block_dialog import PropertyTableDialog, IdentityModeDialog
    tmp_path, config_dir = working_files
    widget = _make_widget(config_dir, tmp_path, filename)
    existing_ids = {b.get('Id') for b in widget.doc.iter_blocks() if b.get('Id')}
    source = widget._tech_tree_source_for_current_file()
    return PropertyTableDialog(
        widget.doc, IdentityModeDialog.MODE_ID_AND_NAME, existing_ids, default_kind="Block",
        tech_tree_source=source, working_root=widget.working_root,
        sibling_ecf_files=widget.sibling_ecf_files)


def test_preview_button_finds_both_config_paths(working_files):
    dlg = _make_property_table_dialog(working_files)
    assert dlg._tech_blocks_path == working_files[1] / "BlocksConfig.ecf"
    assert dlg._tech_items_path == working_files[1] / "ItemsConfig.ecf"


def test_apply_row_value_checks_and_sets_existing_row(working_files):
    dlg = _make_property_table_dialog(working_files)
    checkbox, combo = dlg._find_row("UnlockLevel")
    assert checkbox is not None  # UnlockLevel est une propriete reelle du fichier
    assert checkbox.isChecked() is False

    dlg._apply_row_value("UnlockLevel", "15")

    assert checkbox.isChecked() is True
    assert combo.currentText() == "15"


def test_apply_row_value_silently_ignores_unknown_key(working_files):
    dlg = _make_property_table_dialog(working_files)
    # Ne doit pas lever d'exception pour une cle absente du tableau.
    dlg._apply_row_value("SomePropertyThatDoesNotExist", "42")


def test_open_tech_tree_preview_writes_back_result(working_files, monkeypatch):
    from gui.tech_tree_preview_dialog import TechTreePreviewDialog

    dlg = _make_property_table_dialog(working_files)

    def fake_exec(self):
        self._on_level_changed(PENDING, 20)
        self._on_cost_changed(PENDING, 30)
        self._on_category_changed(PENDING, "Weapons")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(TechTreePreviewDialog, "exec", fake_exec)

    dlg._open_tech_tree_preview()

    level_checkbox, level_combo = dlg._find_row("UnlockLevel")
    cost_checkbox, cost_combo = dlg._find_row("UnlockCost")
    names_checkbox, names_combo = dlg._find_row("TechTreeNames")

    assert level_checkbox.isChecked() and level_combo.currentText() == "20"
    assert cost_checkbox.isChecked() and cost_combo.currentText() == "30"
    assert names_checkbox.isChecked() and names_combo.currentText() == "Weapons"


def test_open_tech_tree_preview_does_nothing_when_cancelled(working_files, monkeypatch):
    from gui.tech_tree_preview_dialog import TechTreePreviewDialog

    dlg = _make_property_table_dialog(working_files)
    monkeypatch.setattr(TechTreePreviewDialog, "exec", lambda self: QDialog.DialogCode.Rejected)

    dlg._open_tech_tree_preview()

    level_checkbox, _ = dlg._find_row("UnlockLevel")
    assert level_checkbox.isChecked() is False


def test_preview_reads_current_checked_values_as_starting_point(working_files, monkeypatch):
    """Si UnlockLevel est deja coche a 10 dans le tableau, la
    previsualisation doit s'ouvrir avec ce niveau comme point de depart."""
    from gui.tech_tree_preview_dialog import TechTreePreviewDialog

    dlg = _make_property_table_dialog(working_files)
    checkbox, combo = dlg._find_row("UnlockLevel")
    checkbox.setChecked(True)
    combo.setCurrentText("10")

    captured = {}

    def fake_exec(self):
        captured['initial_level'] = self.pending_node.unlock_level
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(TechTreePreviewDialog, "exec", fake_exec)
    dlg._open_tech_tree_preview()

    assert captured['initial_level'] == 10
