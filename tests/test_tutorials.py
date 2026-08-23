# Empyrion Scenario Editor
# Copyright (C) 2026  Daflo
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

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


def test_no_stale_2048_id_limit_reference():
    """Regression : la limite d'Id reelle du jeu est 8192 (confirme via les
    notes de mise a jour officielles Eleon v1.17), pas 2048 -- aucun tutoriel
    ne doit plus enseigner l'ancienne valeur perimee."""
    from core.tutorials import TUTORIALS
    for tut in TUTORIALS:
        for step in tut.steps:
            assert "2048" not in step.content_fr
            assert "2048" not in step.content_en


def test_id_limit_mentions_correct_value():
    from core.tutorials import TUTORIAL_CREATE_BLOCK
    all_content = "".join(s.content_fr + s.content_en for s in TUTORIAL_CREATE_BLOCK.steps)
    assert "8192" in all_content


def test_app_overview_mentions_newer_features():
    """Confirme que le tutoriel de prise en main mentionne bien les
    fonctionnalites ajoutees depuis (carte 2D, inspecteur de POI, carte de
    galaxie, politique de confidentialite, traduction en ligne)."""
    from core.tutorials import TUTORIAL_APP_OVERVIEW
    all_content = "".join(s.content_fr + s.content_en for s in TUTORIAL_APP_OVERVIEW.steps)
    assert "Carte 2D" in all_content or "2D Map" in all_content
    assert "Inspecteur de POI" in all_content or "POI Inspector" in all_content
    assert "galaxie" in all_content.lower() or "galaxy" in all_content.lower()
    assert "confidentialite" in all_content.lower() or "Privacy policy" in all_content
    assert "Traduction en ligne" in all_content or "Online translation" in all_content


def test_add_block_step_describes_new_wizard_not_old_flow():
    """Regression : l'ancien flux (bloc vide, tout a remplir manuellement) a
    ete completement refondu -- le tutoriel ne doit plus le decrire."""
    from core.tutorials import TUTORIAL_APP_OVERVIEW
    step = next(s for s in TUTORIAL_APP_OVERVIEW.steps
                if "ajouter un bloc" in s.title_fr or "adding a block" in s.title_en)
    assert "entierement vide" not in step.content_fr
    assert "entirely empty" not in step.content_en
    assert "Template" in step.content_fr


def test_all_tutorial_html_parses_without_error(qapp):
    """Verifie que chaque etape des deux tutoriels s'affiche reellement dans
    le vrai widget QTextBrowser sans lever d'exception -- pas seulement que le
    HTML est syntaxiquement plausible."""
    from gui.theme import apply_theme
    from gui.main_window import TutorialDialog
    apply_theme(qapp)
    dialog = TutorialDialog()
    for tut_idx in range(dialog.list_widget.count()):
        dialog.list_widget.setCurrentRow(tut_idx)
        tut = dialog.tutorials[tut_idx]
        for _ in range(len(tut.steps)):
            dialog.btn_next.click()
        assert dialog.content_browser.toPlainText() != ""
