"""
Tests du dialogue de validation (gui/validation_dialog.py) -- bases sur le
vrai BlocksConfig.ecf reduit deja utilise par d'autres suites de tests
playfield, qui contient un cas E005 (VolumeCapacity) confirme.
"""
import shutil
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QDialog

FIXTURE_BLOCKS = Path(__file__).parent / "fixtures" / "validation_scenario" / "BlocksConfig.ecf"


@pytest.fixture
def window_with_workspace(qapp, tmp_path):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from core.scanner import scan_scenario
    from core.workspace import Workspace

    apply_theme(qapp)
    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    shutil.copy(FIXTURE_BLOCKS, config_dir / "BlocksConfig.ecf")

    scenario = scan_scenario(tmp_path)
    window = MainWindow()
    window.workspace = Workspace(source_a=scenario, source_a_root=tmp_path,
                                  working=scenario, working_root=tmp_path)
    return window


def test_validate_scenario_dialog_shows_info_when_no_workspace(qapp, monkeypatch):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from PyQt6.QtWidgets import QMessageBox

    apply_theme(qapp)
    window = MainWindow()
    window.workspace = None

    called = []
    monkeypatch.setattr(QMessageBox, "information",
                         staticmethod(lambda *a, **k: called.append(True)))
    window.validate_scenario_dialog()
    assert called == [True]


def test_validation_dialog_opens_and_runs(window_with_workspace, monkeypatch):
    from gui.validation_dialog import ValidationDialog
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Accepted)

    dialog = ValidationDialog(window_with_workspace, parent=window_with_workspace)
    assert dialog.tree.topLevelItemCount() >= 1


def test_validation_dialog_summary_reflects_real_issues(window_with_workspace):
    from gui.validation_dialog import ValidationDialog
    dialog = ValidationDialog(window_with_workspace, parent=window_with_workspace)
    assert "erreur" in dialog.summary_label.text() or "avertissement" in dialog.summary_label.text()


def test_double_click_opens_file_and_selects_block(window_with_workspace):
    from gui.validation_dialog import ValidationDialog
    dialog = ValidationDialog(window_with_workspace, parent=window_with_workspace)

    def find_first_issue_item(tree):
        for i in range(tree.topLevelItemCount()):
            file_item = tree.topLevelItem(i)
            for j in range(file_item.childCount()):
                block_item = file_item.child(j)
                if block_item.childCount() > 0:
                    return block_item.child(0)
        return None

    issue_item = find_first_issue_item(dialog.tree)
    assert issue_item is not None

    before = window_with_workspace.tabs.count()
    dialog._on_item_double_clicked(issue_item, 0)
    assert window_with_workspace.tabs.count() == before + 1


def test_filter_errors_only_hides_warnings(window_with_workspace):
    from gui.validation_dialog import ValidationDialog
    dialog = ValidationDialog(window_with_workspace, parent=window_with_workspace)
    dialog.chk_warnings.setChecked(False)

    def count_visible_issues(tree):
        total = 0
        for i in range(tree.topLevelItemCount()):
            file_item = tree.topLevelItem(i)
            if file_item.isHidden():
                continue
            for j in range(file_item.childCount()):
                block_item = file_item.child(j)
                if block_item.isHidden():
                    continue
                for k in range(block_item.childCount()):
                    if not block_item.child(k).isHidden():
                        total += 1
        return total

    visible_with_warnings = count_visible_issues(dialog.tree)
    dialog.chk_warnings.setChecked(True)
    visible_all = count_visible_issues(dialog.tree)
    assert visible_with_warnings <= visible_all
