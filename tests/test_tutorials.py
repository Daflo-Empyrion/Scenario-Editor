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
