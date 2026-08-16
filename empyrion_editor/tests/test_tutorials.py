# Tests du module core.tutorials -- garantit que la structure reste coherente
# meme quand de nouveaux tutoriels sont ajoutes par la suite.
from core.tutorials import TUTORIALS, Tutorial, TutorialStep


def test_at_least_one_tutorial_registered():
    assert len(TUTORIALS) >= 1


def test_all_tutorials_have_unique_ids():
    ids = [t.id for t in TUTORIALS]
    assert len(ids) == len(set(ids))


def test_all_tutorials_have_title_and_summary():
    for tut in TUTORIALS:
        assert tut.title.strip()
        assert tut.summary.strip()


def test_all_tutorials_have_at_least_one_step():
    for tut in TUTORIALS:
        assert len(tut.steps) >= 1


def test_all_steps_have_title_and_content():
    for tut in TUTORIALS:
        for step in tut.steps:
            assert step.title.strip()
            assert step.content_html.strip()


def test_create_block_tutorial_present():
    ids = [t.id for t in TUTORIALS]
    assert "create_block" in ids
