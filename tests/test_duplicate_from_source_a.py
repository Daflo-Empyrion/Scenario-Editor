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
Tests de non-regression pour la duplication depuis Scenario A vers la copie
de travail (voir gui/main_window.py::_duplicate_ecf_block_dialog) -- retour
utilisateur (29/08/2026) : ce flux ne doit PRESENTER AUCUN CHANGEMENT --
en particulier, PAS de section d'ajustement des proprietes (contrairement a
la duplication au sein de la copie de travail, voir
tests/test_duplicate_variants_widget.py) -- un ajout par erreur avait ete
fait puis retire.
"""
import shutil
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "block_creation_scenario"


@pytest.fixture
def window_with_separate_source_a(qapp, tmp_path):
    """Scenario A et copie de travail dans des dossiers VRAIMENT separes
    (contrairement a window_with_scenario de test_tech_tree_menu_integration,
    qui partage le meme dossier pour les deux) -- necessaire pour tester
    reellement le flux 'copier depuis A vers la copie de travail'."""
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from core.scanner import scan_scenario
    from core.workspace import Workspace

    apply_theme(qapp)

    source_root = tmp_path / "source_a"
    working_root = tmp_path / "working"
    for root in (source_root, working_root):
        config_dir = root / "Content" / "Configuration"
        config_dir.mkdir(parents=True)
        shutil.copy(FIXTURE_DIR / "BlocksConfig.ecf", config_dir / "BlocksConfig.ecf")

    source_scenario = scan_scenario(source_root)
    working_scenario = scan_scenario(working_root)
    window = MainWindow()
    window.workspace = Workspace(source_a=source_scenario, source_a_root=source_root,
                                  working=working_scenario, working_root=working_root)
    return window, source_root, working_root


def _find_block(scenario_root: Path, name: str):
    from core.ecf.parser import parse_ecf_file
    doc = parse_ecf_file(scenario_root / "Content" / "Configuration" / "BlocksConfig.ecf")
    for b in doc.iter_blocks():
        if b.get_property("Name") == name:
            return b
    raise AssertionError(f"bloc {name} introuvable")


def test_duplicate_from_source_a_dialog_has_no_property_table(window_with_separate_source_a):
    """Le dialogue de duplication depuis Scenario A ne doit JAMAIS afficher
    la section d'ajustement des proprietes -- comportement reserve a la
    duplication au sein de la copie de travail (voir
    gui/ecf_edit_widget.py::_duplicate_block_action)."""
    from gui.duplicate_variants_dialog import DuplicateVariantsDialog
    from core.ecf.variants import detect_numeric_fields_block

    window, source_root, working_root = window_with_separate_source_a
    block = _find_block(source_root, "IronResource")

    dialog = DuplicateVariantsDialog(
        block.get('Id'), block.get_property('Name'), ["999"],
        detect_numeric_fields_block(block), parent=window, show_id_field=True)
    assert dialog.property_table is None
    assert not hasattr(dialog, "adjust_properties_checkbox")


def test_duplicate_from_source_a_simple_still_inserts_block(window_with_separate_source_a, monkeypatch):
    """Non-regression fonctionnelle : dupliquer depuis Scenario A vers la
    copie de travail doit toujours fonctionner normalement."""
    from gui.duplicate_variants_dialog import DuplicateVariantsDialog
    from PyQt6.QtWidgets import QDialog, QMessageBox

    window, source_root, working_root = window_with_separate_source_a
    block = _find_block(source_root, "IronResource")

    def fake_exec(self):
        self.result_new_id = None
        self.result_new_name = "IronResourceFromA"
        self.result_remove_id = True
        self.result_multi = None
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(DuplicateVariantsDialog, "exec", fake_exec)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)

    rel = Path("Content") / "Configuration" / "BlocksConfig.ecf"
    window._duplicate_ecf_block_dialog(block, [], source_root / rel, source_root, "Scenario A")

    from core.ecf.parser import parse_ecf_file
    working_doc = parse_ecf_file(working_root / rel)
    names = [b.get_property("Name") for b in working_doc.iter_blocks()]
    assert "IronResourceFromA" in names


def test_duplicate_from_source_a_never_mutates_source_block(window_with_separate_source_a, monkeypatch):
    """Le bloc du scenario SOURCE ne doit jamais etre modifie par cette
    operation, quel que soit le chemin emprunte (bug potentiel evite lors
    du retrait de la section d'ajustement -- voir docstring du module)."""
    from gui.duplicate_variants_dialog import DuplicateVariantsDialog
    from PyQt6.QtWidgets import QDialog, QMessageBox

    window, source_root, working_root = window_with_separate_source_a
    block = _find_block(source_root, "IronResource")
    original_xpfactor = block.get_property("XpFactor")

    def fake_exec(self):
        self.result_new_id = None
        self.result_new_name = "IronResourceFromA2"
        self.result_remove_id = True
        self.result_multi = None
        self.result_simple_percent = 50.0
        self.result_simple_fields = ["XpFactor"]
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(DuplicateVariantsDialog, "exec", fake_exec)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)

    rel = Path("Content") / "Configuration" / "BlocksConfig.ecf"
    window._duplicate_ecf_block_dialog(block, [], source_root / rel, source_root, "Scenario A")

    reloaded_source_block = _find_block(source_root, "IronResource")
    assert reloaded_source_block.get_property("XpFactor") == original_xpfactor
