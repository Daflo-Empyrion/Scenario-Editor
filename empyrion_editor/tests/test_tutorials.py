# Tests du module core.tutorials -- garantit que la structure reste coherente
# meme quand de nouveaux tutoriels sont ajoutes par la suite, dans les DEUX langues.
from core.tutorials import TUTORIALS, Tutorial, TutorialStep


def test_at_least_one_tutorial_registered():
    assert len(TUTORIALS) >= 1


def test_all_tutorials_have_unique_ids():
    ids = [t.id for t in TUTORIALS]
    assert len(ids) == len(set(ids))


def test_all_tutorials_have_title_and_summary_both_languages():
    for tut in TUTORIALS:
        assert tut.title_fr.strip()
        assert tut.title_en.strip()
        assert tut.summary_fr.strip()
        assert tut.summary_en.strip()
        assert tut.title("fr") == tut.title_fr
        assert tut.title("en") == tut.title_en


def test_all_tutorials_have_at_least_one_step():
    for tut in TUTORIALS:
        assert len(tut.steps) >= 1


def test_all_steps_have_title_and_content_both_languages():
    for tut in TUTORIALS:
        for step in tut.steps:
            assert step.title_fr.strip()
            assert step.title_en.strip()
            assert step.content_fr.strip()
            assert step.content_en.strip()
            assert step.title("fr") == step.title_fr
            assert step.title("en") == step.title_en
            assert step.content_html("fr") == step.content_fr
            assert step.content_html("en") == step.content_en


def test_create_block_tutorial_present():
    ids = [t.id for t in TUTORIALS]
    assert "create_block" in ids


def test_app_overview_tutorial_present():
    ids = [t.id for t in TUTORIALS]
    assert "app_overview" in ids
