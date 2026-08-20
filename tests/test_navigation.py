"""
Tests de la navigation "cliquer pour aller directement au bon endroit" -- ajoutee
suite au dialogue "References croisees" (gui/cross_reference_dialog.py), mais les
methodes testees ici sont reutilisables par tout futur appelant.
"""
import shutil
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "sample.ecf"


@pytest.fixture
def ecf_widget(qapp, tmp_path):
    from gui.ecf_edit_widget import EcfEditWidget
    working_copy = tmp_path / "sample.ecf"
    shutil.copy(FIXTURE, working_copy)
    return EcfEditWidget(working_copy)


@pytest.fixture
def yaml_widget(qapp, tmp_path):
    from gui.yaml_edit_widget import YamlEditWidget
    path = tmp_path / "test.yaml"
    path.write_text("POIs:\n  - Prefab: MissingPOI\n  - Prefab: OtherPOI\n", encoding="utf-8")
    return YamlEditWidget(path)


def test_select_block_by_identity_top_level(ecf_widget):
    found = ecf_widget.select_block_by_identity("399")
    assert found is True
    assert ecf_widget.tree.currentItem().text(0) == "Block [399]  - ConcreteBlocks"


def test_select_block_by_identity_not_found(ecf_widget):
    found = ecf_widget.select_block_by_identity("nonexistent-id-xyz")
    assert found is False


def test_select_block_by_identity_descends_into_nested_subblock(ecf_widget):
    found = ecf_widget.select_block_by_identity("5", prop_key="Name_0", prop_value="IronOre")
    assert found is True
    # Doit avoir navigue jusqu'au sous-bloc "Child Items", pas etre reste sur la
    # racine "+Container [5]" ou cette valeur n'est pas visible dans le tableau.
    assert ecf_widget.tree.currentItem().text(0) == "Child Items"
    assert ecf_widget.props_table.currentItem().text() == "IronOre"


def test_select_block_by_identity_falls_back_to_root_when_prop_not_found(ecf_widget):
    # La propriete demandee n'existe nulle part -- doit quand meme selectionner le
    # bloc racine plutot que d'echouer completement.
    found = ecf_widget.select_block_by_identity("399", prop_key="Name_0", prop_value="DoesNotExist")
    assert found is True
    assert ecf_widget.tree.currentItem().text(0) == "Block [399]  - ConcreteBlocks"


def test_select_entry_by_key_value_found(yaml_widget):
    found = yaml_widget.select_entry_by_key_value("Prefab", "MissingPOI")
    assert found is True
    assert yaml_widget.tree.currentItem().text(0) == "Prefab"
    assert yaml_widget.tree.currentItem().text(1) == "MissingPOI"


def test_select_entry_by_key_value_not_found(yaml_widget):
    found = yaml_widget.select_entry_by_key_value("Prefab", "NoSuchValue")
    assert found is False


def test_select_entry_by_key_value_distinguishes_same_key_different_value(yaml_widget):
    found_first = yaml_widget.select_entry_by_key_value("Prefab", "MissingPOI")
    assert found_first is True
    first_selection = yaml_widget.tree.currentItem()

    found_second = yaml_widget.select_entry_by_key_value("Prefab", "OtherPOI")
    assert found_second is True
    second_selection = yaml_widget.tree.currentItem()

    assert first_selection is not second_selection


@pytest.fixture
def workspace_with_scenario(tmp_path):
    from core.scanner import scan_scenario
    from core.workspace import Workspace

    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    shutil.copy(
        Path(__file__).parent / "fixtures" / "cross_ref_scenario" / "Containers.ecf",
        config_dir / "Containers.ecf")
    shutil.copy(
        Path(__file__).parent / "fixtures" / "cross_ref_scenario" / "TokenConfig.ecf",
        config_dir / "TokenConfig.ecf")

    scenario = scan_scenario(tmp_path)
    return Workspace(source_a=scenario, source_a_root=tmp_path, working=scenario, working_root=tmp_path)


def test_dialog_navigate_opens_and_selects_correct_cell(qapp, workspace_with_scenario):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from gui.cross_reference_dialog import CrossReferenceDialog

    apply_theme(qapp)
    window = MainWindow()
    window.workspace = workspace_with_scenario

    dialog = CrossReferenceDialog(workspace_with_scenario, window, parent=window)
    dialog._do_run()
    assert dialog.results_list.count() >= 1

    dialog._navigate_to_issue(dialog.results_list.item(0))

    assert window.tabs.count() == 1
    widget = window.tabs.currentWidget()
    edit_widget = getattr(widget, "edit_widget", widget)
    assert edit_widget.path.name == "Containers.ecf"


def test_dialog_navigate_reuses_existing_tab_instead_of_duplicating(qapp, workspace_with_scenario):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from gui.cross_reference_dialog import CrossReferenceDialog

    apply_theme(qapp)
    window = MainWindow()
    window.workspace = workspace_with_scenario

    dialog = CrossReferenceDialog(workspace_with_scenario, window, parent=window)
    dialog._do_run()
    assert dialog.results_list.count() >= 2  # NonExistentItem + Token:9999, meme fichier

    dialog._navigate_to_issue(dialog.results_list.item(0))
    dialog._navigate_to_issue(dialog.results_list.item(1))

    assert window.tabs.count() == 1  # meme fichier -> reactive l'onglet, n'en cree pas un second
