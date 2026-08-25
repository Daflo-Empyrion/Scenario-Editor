"""
Tests du widget navigateur de dialogues (gui/dialogue_browser_widget.py) --
bases sur la fixture reelle de la chaine TC_*.
"""
from pathlib import Path

import pytest

from core.ecf.parser import parse_ecf_file

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "dialogue_scenario" / "Dialogues.ecf"


@pytest.fixture
def dialogue_doc():
    return parse_ecf_file(FIXTURE_PATH)


def test_widget_indexes_all_dialogues(qapp, dialogue_doc):
    from gui.theme import apply_theme
    from gui.dialogue_browser_widget import DialogueBrowserWidget
    apply_theme(qapp)
    widget = DialogueBrowserWidget(dialogue_doc)
    assert len(widget.dialogue_index) == 8
    assert widget.name_list.count() == 8


def test_selecting_name_renders_detail(qapp, dialogue_doc):
    from gui.theme import apply_theme
    from gui.dialogue_browser_widget import DialogueBrowserWidget
    apply_theme(qapp)
    widget = DialogueBrowserWidget(dialogue_doc)
    widget._select_name("TC_Start")
    assert widget._current_name == "TC_Start"
    assert widget.detail_layout.count() > 1


def test_navigate_changes_current_selection(qapp, dialogue_doc):
    from gui.theme import apply_theme
    from gui.dialogue_browser_widget import DialogueBrowserWidget
    apply_theme(qapp)
    widget = DialogueBrowserWidget(dialogue_doc)
    widget._select_name("TC_Start")
    widget._navigate("TC_HasHolyStatus")
    assert widget._current_name == "TC_HasHolyStatus"


def test_navigate_to_unknown_name_does_nothing(qapp, dialogue_doc):
    from gui.theme import apply_theme
    from gui.dialogue_browser_widget import DialogueBrowserWidget
    apply_theme(qapp)
    widget = DialogueBrowserWidget(dialogue_doc)
    widget._select_name("TC_Start")
    widget._navigate("NonExistentDialogue")
    assert widget._current_name == "TC_Start"  # inchange


def test_search_filter_hides_non_matching_entries(qapp, dialogue_doc):
    from gui.theme import apply_theme
    from gui.dialogue_browser_widget import DialogueBrowserWidget
    apply_theme(qapp)
    widget = DialogueBrowserWidget(dialogue_doc)
    widget.search_edit.setText("Holy")
    visible = [widget.name_list.item(i).text() for i in range(widget.name_list.count())
               if not widget.name_list.item(i).isHidden()]
    assert set(visible) == {"TC_HasHolyStatus", "TC_GiveHolyStatue"}


def test_refresh_preserves_current_selection(qapp, dialogue_doc):
    from gui.theme import apply_theme
    from gui.dialogue_browser_widget import DialogueBrowserWidget
    apply_theme(qapp)
    widget = DialogueBrowserWidget(dialogue_doc)
    widget._select_name("TC_HasHolyStatus")
    widget.refresh()
    assert widget._current_name == "TC_HasHolyStatus"


def test_clickable_label_greys_out_sentinel():
    from gui.dialogue_browser_widget import _ClickableLabel
    from core.ecf.cross_reference_check import _DIALOGUE_REF_SENTINELS
    label = _ClickableLabel("End", lambda n: None, exists=True)
    assert "<a href" not in label.text()


def test_clickable_label_shows_broken_link_in_red():
    from gui.dialogue_browser_widget import _ClickableLabel
    label = _ClickableLabel("DialogueQuiNexistePas", lambda n: None, exists=False)
    assert "#c62828" in label.text()


def test_clickable_label_is_a_real_link_when_target_exists():
    from gui.dialogue_browser_widget import _ClickableLabel
    label = _ClickableLabel("TC_Start", lambda n: None, exists=True)
    assert "<a href" in label.text()


def test_widget_handles_full_real_file_reasonably_fast(qapp):
    """Non-regression de performance sur le vrai fichier complet (5417 blocs,
    48601 lignes) -- confirme sous la seconde lors du developpement, ce test
    utilise un plafond large pour rester robuste face aux variations de
    machine, tout en detectant une regression grossiere (ex: parcours en
    O(n^2) introduit par erreur)."""
    import time
    from pathlib import Path
    from gui.theme import apply_theme
    from core.ecf.parser import parse_ecf_file
    from gui.dialogue_browser_widget import DialogueBrowserWidget

    real_file = Path("/mnt/user-data/uploads/Dialogues.ecf")
    if not real_file.exists():
        import pytest
        pytest.skip("Fichier reel non disponible dans cet environnement")

    apply_theme(qapp)
    doc = parse_ecf_file(real_file)
    t0 = time.time()
    widget = DialogueBrowserWidget(doc)
    widget._select_name("TC_Start")
    elapsed = time.time() - t0
    assert elapsed < 10.0
    assert len(widget.dialogue_index) > 5000
