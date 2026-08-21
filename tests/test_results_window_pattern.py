"""
Tests du motif "fenetre de resultats non modale, actualisable, exportable"
applique aux dialogues de verification (cross_reference_dialog.py,
validation_dialog.py) et a l'ancien menu "Verifier les references"
(check_references_dialog, qui reutilise desormais CrossReferenceDialog).
"""
import shutil
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QFileDialog, QMessageBox

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "cross_ref_scenario"


@pytest.fixture
def window_with_workspace(qapp, tmp_path):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from core.scanner import scan_scenario
    from core.workspace import Workspace

    apply_theme(qapp)
    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    for ecf in FIXTURE_DIR.glob("*.ecf"):
        shutil.copy(ecf, config_dir / ecf.name)

    scenario = scan_scenario(tmp_path)
    window = MainWindow()
    window.workspace = Workspace(source_a=scenario, source_a_root=tmp_path,
                                  working=scenario, working_root=tmp_path)
    return window


def test_check_references_dialog_only_checks_ref_inheritance(window_with_workspace):
    """L'ancien menu 'Verifier les references' doit ouvrir CrossReferenceDialog
    avec SEULEMENT ref_inheritance coche -- pas les 3 autres verifications."""
    window_with_workspace.check_references_dialog()
    dialog = window_with_workspace._ref_dialog
    assert dialog.checkboxes["ref_inheritance"].isChecked() is True
    assert dialog.checkboxes["item_block_pool"].isChecked() is False
    assert dialog.checkboxes["token_refs"].isChecked() is False
    assert dialog.checkboxes["dialogue_refs"].isChecked() is False
    dialog.close()


def test_cross_reference_dialog_all_checked_by_default(window_with_workspace):
    window_with_workspace.check_cross_references_dialog()
    dialog = window_with_workspace._cross_ref_dialog
    assert all(box.isChecked() for box in dialog.checkboxes.values())
    dialog.close()


def test_cross_reference_dialog_is_non_modal(window_with_workspace):
    """Utilise .show() et non .exec() -- doit rester visible et utilisable
    sans bloquer le reste de l'application."""
    window_with_workspace.check_cross_references_dialog()
    dialog = window_with_workspace._cross_ref_dialog
    assert dialog.isVisible() is True
    assert dialog.isModal() is False
    dialog.close()


def test_cross_reference_dialog_survives_garbage_collection(window_with_workspace):
    """La reference doit etre conservee sur main_window (self._cross_ref_dialog)
    -- sans ca, Python detruirait le dialogue des la fin de la methode qui l'a
    cree, puisque .show() ne bloque pas comme .exec()."""
    import gc
    window_with_workspace.check_cross_references_dialog()
    gc.collect()
    assert window_with_workspace._cross_ref_dialog is not None
    assert window_with_workspace._cross_ref_dialog.isVisible() is True
    window_with_workspace._cross_ref_dialog.close()


def test_validation_dialog_is_non_modal(window_with_workspace):
    window_with_workspace.validate_scenario_dialog()
    dialog = window_with_workspace._validation_dialog
    assert dialog.isVisible() is True
    assert dialog.isModal() is False
    dialog.close()


def test_compare_dialog_is_non_modal(qapp):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    apply_theme(qapp)
    window = MainWindow()
    window._open_compare_dialog()
    dialog = window._compare_dialog
    assert dialog.isVisible() is True
    assert dialog.isModal() is False
    dialog.close()


def test_cross_reference_refresh_button_reruns_check(window_with_workspace):
    window_with_workspace.check_cross_references_dialog()
    dialog = window_with_workspace._cross_ref_dialog
    dialog.results_list.clear()
    dialog._do_run()  # simule le clic sur "Actualiser"
    assert dialog.results_list.count() > 0
    dialog.close()


def test_cross_reference_export_writes_all_issues(window_with_workspace, monkeypatch, tmp_path):
    window_with_workspace.check_cross_references_dialog()
    dialog = window_with_workspace._cross_ref_dialog
    dialog._do_run()

    export_path = tmp_path / "export.txt"
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                         staticmethod(lambda *a, **k: (str(export_path), "")))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    dialog._export_results()

    content = export_path.read_text(encoding="utf-8")
    assert len(dialog._last_issues) > 0
    for issue in dialog._last_issues:
        assert issue.ref_value in content
    dialog.close()


def test_validation_export_writes_all_issues(window_with_workspace, monkeypatch, tmp_path):
    window_with_workspace.validate_scenario_dialog()
    dialog = window_with_workspace._validation_dialog

    export_path = tmp_path / "export.txt"
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                         staticmethod(lambda *a, **k: (str(export_path), "")))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    dialog._export_results()

    assert export_path.exists()
    dialog.close()
