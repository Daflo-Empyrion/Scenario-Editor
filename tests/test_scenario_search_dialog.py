"""
Tests du dialogue de recherche globale (gui/scenario_search_dialog.py) --
verifie la collecte des fichiers a travers les 3 categories (ECF, YAML
playfield, CSV) et la navigation au double-clic, qui reutilise les memes
mecanismes que gui/cross_reference_dialog.py (select_block_by_identity /
select_entry_by_key_value).

IMPORTANT -- Playfields/ vit A LA RACINE du scenario, PAS sous Content/
(contrairement a Configuration) -- confirme dans docs/wiki_empyrion_fr.md.
"""
import shutil
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QMessageBox

ITEMS_CONFIG = Path(__file__).parent / "fixtures" / "search_scenario" / "ItemsConfig.ecf"
PLAYFIELD_FIXTURE = Path(__file__).parent / "fixtures" / "playfield_scenario" / "playfield_akua.yaml"


@pytest.fixture
def window_with_scenario(qapp, tmp_path):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from core.scanner import scan_scenario
    from core.workspace import Workspace

    apply_theme(qapp)
    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    shutil.copy(ITEMS_CONFIG, config_dir / "ItemsConfig.ecf")

    playfield_dir = tmp_path / "Playfields" / "Akua"
    playfield_dir.mkdir(parents=True)
    shutil.copy(PLAYFIELD_FIXTURE, playfield_dir / "playfield_dynamic.yaml")

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
    window._open_search_dialog()
    assert called == [True]


def test_dialog_is_non_modal(window_with_scenario):
    window_with_scenario._open_search_dialog()
    dialog = window_with_scenario._search_dialog
    assert dialog.isVisible() is True
    assert dialog.isModal() is False
    dialog.close()


def test_gather_files_finds_ecf_and_playfield_yaml(window_with_scenario):
    """Regression cle : Playfields/ vit a la racine du scenario, pas sous
    Content/ -- confirme que _gather_files() le trouve correctement."""
    window_with_scenario._open_search_dialog()
    dialog = window_with_scenario._search_dialog
    ecf_files, yaml_files, csv_files = dialog._gather_files()
    assert len(ecf_files) == 1
    assert len(yaml_files) == 1
    dialog.close()


def test_search_ecf_result_and_navigate(window_with_scenario):
    window_with_scenario._open_search_dialog()
    dialog = window_with_scenario._search_dialog
    dialog.query_edit.setText("IronOre")
    dialog._run_search()
    assert dialog.results_list.count() == 1  # un seul bloc IronOre dans cette fixture reduite

    item = dialog.results_list.item(0)
    dialog._navigate_to_result(item)
    assert window_with_scenario.tabs.count() == 1
    dialog.close()


def test_search_yaml_result_opens_playfield_editor(window_with_scenario):
    window_with_scenario._open_search_dialog()
    dialog = window_with_scenario._search_dialog
    dialog.query_edit.setText("Reforged Creative Library")
    dialog._run_search()
    assert dialog.results_list.count() == 1

    item = dialog.results_list.item(0)
    dialog._navigate_to_result(item)
    from gui.playfield_edit_widget import PlayfieldEditWidget
    assert isinstance(window_with_scenario.tabs.widget(0), PlayfieldEditWidget)
    dialog.close()


def test_empty_query_clears_results(window_with_scenario):
    window_with_scenario._open_search_dialog()
    dialog = window_with_scenario._search_dialog
    dialog.query_edit.setText("IronOre")
    dialog._run_search()
    assert dialog.results_list.count() > 0

    dialog.query_edit.setText("")
    dialog._run_search()
    assert dialog.results_list.count() == 0
    dialog.close()


def test_case_sensitive_checkbox_affects_results(window_with_scenario):
    window_with_scenario._open_search_dialog()
    dialog = window_with_scenario._search_dialog
    dialog.query_edit.setText("ironore")
    dialog.case_sensitive_check.setChecked(True)
    dialog._run_search()
    assert dialog.results_list.count() == 0
    dialog.close()


# ---------------------------------------------------------------------------
# Mode expression reguliere (ajoute apres l'audit du 30/08/2026)
# ---------------------------------------------------------------------------

def test_search_with_regex_checkbox_finds_pattern(window_with_scenario):
    from gui.scenario_search_dialog import ScenarioSearchDialog
    dialog = ScenarioSearchDialog(window_with_scenario)
    dialog.regex_check.setChecked(True)
    dialog.query_edit.setText(r"Iron.*Ore")
    dialog._run_search()
    assert dialog.results_list.count() >= 1
    dialog.close()


def test_search_with_invalid_regex_shows_warning_and_keeps_results(
        window_with_scenario, monkeypatch):
    """Motif regex invalide : avertissement affiche, AUCUN vidage de la liste
    (les resultats d'une recherche precedente restent visibles), pas d'exception."""
    from gui.scenario_search_dialog import ScenarioSearchDialog
    dialog = ScenarioSearchDialog(window_with_scenario)
    # Une recherche normale d'abord pour peupler la liste
    dialog.query_edit.setText("IronOre")
    dialog._run_search()
    assert dialog.results_list.count() >= 1

    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning",
        lambda *a, **k: warnings.append(k.get("text") or a[-1]))
    dialog.regex_check.setChecked(True)
    dialog.query_edit.setText("Iron([unclosed")
    dialog._run_search()

    assert len(warnings) == 1
    assert dialog.results_list.count() >= 1  # resultats precedents conserves
    dialog.close()
