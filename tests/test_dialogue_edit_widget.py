"""
Tests d'integration du conteneur DialogueEditWidget (gui/dialogue_edit_widget.py)
et de son routage automatique pour Dialogues.ecf dans
main_window.open_working_file_tab().
"""
import shutil
from pathlib import Path

import pytest

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "dialogue_scenario" / "Dialogues.ecf"


@pytest.fixture
def window_with_scenario(qapp, tmp_path):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from core.scanner import scan_scenario
    from core.workspace import Workspace

    apply_theme(qapp)
    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    shutil.copy(FIXTURE_PATH, config_dir / "Dialogues.ecf")

    scenario = scan_scenario(tmp_path)
    window = MainWindow()
    window.workspace = Workspace(source_a=scenario, source_a_root=tmp_path,
                                  working=scenario, working_root=tmp_path)
    return window, config_dir


def test_dialogues_ecf_routes_to_dialogue_edit_widget(window_with_scenario):
    from gui.dialogue_edit_widget import DialogueEditWidget
    window, config_dir = window_with_scenario
    widget = window.open_working_file_tab(config_dir / "Dialogues.ecf")
    assert isinstance(widget, DialogueEditWidget)


def test_other_ecf_files_not_affected(window_with_scenario):
    """Regression : seul Dialogues.ecf doit etre route vers ce conteneur --
    tout autre fichier .ecf garde le comportement standard."""
    from gui.dialogue_edit_widget import DialogueEditWidget
    window, config_dir = window_with_scenario
    other_ecf = config_dir / "BlocksConfig.ecf"
    other_ecf.write_text("{ Block Id: 1, Name: Test\r\n}\r\n", encoding="utf-8", newline="")
    widget = window.open_working_file_tab(other_ecf)
    assert not isinstance(widget, DialogueEditWidget)


def test_widget_has_two_inner_tabs(window_with_scenario):
    window, config_dir = window_with_scenario
    widget = window.open_working_file_tab(config_dir / "Dialogues.ecf")
    assert widget.tab_widget.count() == 2


def test_path_and_edit_widget_flattened_correctly(window_with_scenario):
    """Regression cle : self.edit_widget doit pointer vers l'EcfEditWidget le
    plus interne (aplati), pas le CompareWidget -- sinon
    getattr(widget, 'edit_widget', widget).path casse partout ailleurs dans
    l'application (titre d'onglet, recherche globale, sauvegarde
    automatique)."""
    from gui.ecf_edit_widget import EcfEditWidget
    window, config_dir = window_with_scenario
    widget = window.open_working_file_tab(config_dir / "Dialogues.ecf")
    assert isinstance(widget.edit_widget, EcfEditWidget)
    assert widget.path == config_dir / "Dialogues.ecf"
    assert widget.edit_widget.path == config_dir / "Dialogues.ecf"


def test_tab_title_updates_correctly(window_with_scenario):
    window, config_dir = window_with_scenario
    widget = window.open_working_file_tab(config_dir / "Dialogues.ecf")
    assert window.tabs.tabText(0) == "✎ Dialogues.ecf"
    widget.edit_widget._set_modified(True)
    assert window.tabs.tabText(0) == "✎ * Dialogues.ecf"


def test_modification_via_ecf_tab_reflects_in_browser_after_save(window_with_scenario):
    from core.ecf.model import EcfProperty
    window, config_dir = window_with_scenario
    widget = window.open_working_file_tab(config_dir / "Dialogues.ecf")

    block = next(b for b in widget.edit_widget.doc.iter_blocks() if b.get_property("Name") == "TC_CameBack")
    output_prop = next(c for c in block.children if isinstance(c, EcfProperty) and c.pairs
                        and c.pairs[0][0] == "Output")
    output_prop.set("Output", '"Changed"')
    widget.edit_widget._set_modified(True)
    widget.save()

    widget.browser_widget._select_name("TC_CameBack")
    assert widget.browser_widget.dialogue_index["TC_CameBack"].output == '"Changed"'
    assert "Changed" in (config_dir / "Dialogues.ecf").read_text()


def test_switching_to_browser_tab_refreshes_it(window_with_scenario):
    window, config_dir = window_with_scenario
    widget = window.open_working_file_tab(config_dir / "Dialogues.ecf")
    widget.tab_widget.setCurrentIndex(1)  # Edition ECF
    widget.tab_widget.setCurrentIndex(0)  # retour au navigateur -- doit se rafraichir
    assert len(widget.browser_widget.dialogue_index) == 8


def test_get_content_for_autosave_delegates_correctly(window_with_scenario):
    window, config_dir = window_with_scenario
    widget = window.open_working_file_tab(config_dir / "Dialogues.ecf")
    content = widget._get_content_for_autosave()
    assert "TC_Start" in content
