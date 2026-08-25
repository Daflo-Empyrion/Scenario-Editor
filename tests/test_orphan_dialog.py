"""
Tests du dialogue de jetons non utilises (gui/orphan_dialog.py) et de son
integration dans le menu Verification.
"""
import shutil
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QFileDialog, QMessageBox

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "orphan_scenario"


@pytest.fixture
def window_with_orphan_scenario(qapp, tmp_path):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from core.scanner import scan_scenario
    from core.workspace import Workspace

    apply_theme(qapp)
    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    for f in FIXTURE_DIR.glob("*.ecf"):
        shutil.copy(f, config_dir / f.name)

    scenario = scan_scenario(tmp_path)
    window = MainWindow()
    window.workspace = Workspace(source_a=scenario, source_a_root=tmp_path,
                                  working=scenario, working_root=tmp_path)
    return window


def test_menu_action_shows_info_when_no_workspace(qapp, monkeypatch):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    apply_theme(qapp)
    window = MainWindow()
    window.workspace = None

    called = []
    monkeypatch.setattr(QMessageBox, "information",
                         staticmethod(lambda *a, **k: called.append(True)))
    window._open_orphan_dialog()
    assert called == [True]


def test_dialog_finds_the_one_unused_token(window_with_orphan_scenario):
    window_with_orphan_scenario._open_orphan_dialog()
    dialog = window_with_orphan_scenario._orphan_dialog
    assert dialog.results_list.count() == 1
    assert "UnusedToken" in dialog.results_list.item(0).text()
    dialog.close()


def test_dialog_is_non_modal(window_with_orphan_scenario):
    window_with_orphan_scenario._open_orphan_dialog()
    dialog = window_with_orphan_scenario._orphan_dialog
    assert dialog.isVisible() is True
    assert dialog.isModal() is False
    dialog.close()


def test_refresh_recomputes_results(window_with_orphan_scenario):
    window_with_orphan_scenario._open_orphan_dialog()
    dialog = window_with_orphan_scenario._orphan_dialog
    dialog.refresh()
    assert dialog.results_list.count() == 1
    dialog.close()


def test_export_writes_all_orphans(window_with_orphan_scenario, monkeypatch, tmp_path):
    window_with_orphan_scenario._open_orphan_dialog()
    dialog = window_with_orphan_scenario._orphan_dialog

    export_path = tmp_path / "export.txt"
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                         staticmethod(lambda *a, **k: (str(export_path), "")))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    dialog._export()

    content = export_path.read_text(encoding="utf-8")
    assert "UnusedToken" in content
    dialog.close()


def test_summary_shows_all_used_when_none_found(qapp, tmp_path):
    from gui.theme import apply_theme
    from gui.orphan_dialog import OrphanDialog
    from core.i18n import t
    apply_theme(qapp)
    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    dialog = OrphanDialog([], parent=None)
    assert dialog.summary_label.text() == t("orphan.all_used")
    dialog.close()
