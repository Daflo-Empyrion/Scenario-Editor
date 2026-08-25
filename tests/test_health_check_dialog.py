"""
Tests du tableau de bord "bilan de sante" (gui/health_check_dialog.py) --
verifie qu'il agrege correctement les 4 verifications existantes SANS
reimplementer leur affichage detaille (chaque bouton "Voir le detail" doit
ouvrir la VRAIE fenetre correspondante).
"""
import shutil
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QMessageBox

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "orphan_scenario"


@pytest.fixture
def window_with_scenario(qapp, tmp_path):
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
    window._open_health_check_dialog()
    assert called == [True]


def test_dialog_is_non_modal(window_with_scenario):
    window_with_scenario._open_health_check_dialog()
    dialog = window_with_scenario._health_check_dialog
    assert dialog.isVisible() is True
    assert dialog.isModal() is False
    dialog.close()


def test_orphan_category_detects_the_unused_token(window_with_scenario):
    """La fixture orphan_scenario a exactement 1 jeton non utilise -- doit se
    refleter dans le tableau de bord."""
    window_with_scenario._open_health_check_dialog()
    dialog = window_with_scenario._health_check_dialog
    assert "1" in dialog.row_orphans.status_label.text()
    assert dialog.row_orphans.btn_detail.isEnabled() is True
    dialog.close()


def test_clean_categories_show_ok_and_disabled_button(window_with_scenario):
    """references/regles metier/blocs en attente sont propres sur cette
    fixture -- doivent afficher 'aucun probleme' et desactiver le bouton
    detail."""
    window_with_scenario._open_health_check_dialog()
    dialog = window_with_scenario._health_check_dialog
    for row in (dialog.row_refs, dialog.row_validation, dialog.row_pending):
        assert row.btn_detail.isEnabled() is False
    dialog.close()


def test_clicking_detail_button_opens_the_real_orphan_dialog(window_with_scenario):
    window_with_scenario._open_health_check_dialog()
    dialog = window_with_scenario._health_check_dialog
    dialog.row_orphans.btn_detail.click()
    assert hasattr(window_with_scenario, "_orphan_dialog")
    assert window_with_scenario._orphan_dialog.isVisible() is True
    dialog.close()
    window_with_scenario._orphan_dialog.close()


def test_refresh_recomputes_all_categories(window_with_scenario):
    window_with_scenario._open_health_check_dialog()
    dialog = window_with_scenario._health_check_dialog
    dialog.refresh()
    assert "1" in dialog.row_orphans.status_label.text()
    dialog.close()


def test_overall_summary_reflects_orphan_count_but_not_as_error(window_with_scenario):
    """Les jetons non utilises sont purement informatifs -- ne doivent pas
    etre comptes dans le total de 'problemes' du resume general (coherent
    avec orphan_check.py, jamais une erreur)."""
    window_with_scenario._open_health_check_dialog()
    dialog = window_with_scenario._health_check_dialog
    assert "aucun probleme" in dialog.summary_label.text().lower() or \
           "no issues" in dialog.summary_label.text().lower()
    dialog.close()
