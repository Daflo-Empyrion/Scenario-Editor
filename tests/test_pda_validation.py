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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  Aucune garantie.
#
# Tests de la validation PDA (core/pda/validation.py, paquet A du backlog
# 12/09/2026) -- regles tirees du guide officiel de creation de missions.
# Documents synthetiques en memoire (meme principe que test_pda_model.py).
import pytest

from core.csv_handler import parse_csv_text
from core.pda.model import PdaModel
from core.pda.validation import (TITLE_LIMITS, validate_action,
                                 validate_csv_tokens, validate_model,
                                 visible_len)
from core.yamllite.parser import parse_yaml_text

GOOD_YAML = """Chapters:
  - ChapterTitle: pda_Aa1Bb2C
    Category: SoloMission
    Visibility: Always
    PlayerLevel: 5
    CompletedMessage: pda_Mm1Nn2O
    Tasks:
      - TaskTitle: pda_Gg7Hh8I
        Actions:
          - ActionTitle: pda_Jj9Kk0L
            Description: pda_Jj9Kk0L
            Check: SubjectKilled
            Names:
              - ZiraxTrooper
            Amount: 10
            CompletedMessage: pda_Jj9Kk0L
"""

GOOD_CSV = """KEY,English,Français
pda_Aa1Bb2C,First chapter,Premier chapitre
pda_Gg7Hh8I,Task one,Tache une
pda_Jj9Kk0L,Kill them,Tuez-les
pda_Mm1Nn2O,Done,Termine
"""


@pytest.fixture
def good_model():
    return PdaModel(parse_yaml_text(GOOD_YAML), parse_csv_text(GOOD_CSV))


def _chapters(model):
    return model.chapters()


def _first_action(model):
    chapter = model.chapters()[0]
    task = model.tasks(chapter)[0]
    return chapter, task, model.actions(task)[0]


# ------------------------------------------------------------------ sain

def test_healthy_scenario_has_no_issue(good_model):
    assert validate_model(good_model) == []


def test_visible_len_strips_bbcode():
    assert visible_len("[c][ffffff]Kill them[-]") == len("Kill them")
    assert visible_len("Sans balise") == len("Sans balise")


# ------------------------------------------------------------------ A1

def test_title_over_limit_not_flagged_as_issue(good_model):
    """Decision du 12/09/2026 : les limites 26/24 sont des recommandations
    COSMETIQUES du guide (repli de ligne dans le HUD), ignorees par le
    contenu officiel lui-meme (841 titres > 24 sur RE2 EVO). Le compteur
    informatif reste dans l'UI, mais la validation n'emmet plus PDA-A1."""
    long_title = "pda_XXxXxX"
    chapter = good_model.chapters()[0]
    task = good_model.tasks(chapter)[0]
    action = good_model.actions(task)[0]
    good_model.set_csv_text(long_title, "T" * 30)
    action.set_own_value(long_title)
    assert [i for i in validate_model(good_model) if i.code == "PDA-A1"] == []


def test_a2_warnings_aggregated_when_numerous(good_model):
    """12/09/2026 : 862 actions sans CompletedMessage sur la VANILLE —
    au-dela de 3, les avertissements identiques sont aggregates en UNE
    ligne resume pour ne pas noyer la liste."""
    from core.pda.model import PdaModel as M
    from core.yamllite.parser import parse_yaml_text as Y
    from core.csv_handler import parse_csv_text as C

    actions = []
    for n in range(5):
        actions.append(
            "          - ActionTitle: pda_TtTtTt%d\n"
            "            Check: SubjectKilled\n"
            "            Names:\n"
            "              - ZiraxTrooper\n"
            "            Amount: 1\n" % n)
    five_no_cm = GOOD_YAML.replace(
        "          - ActionTitle: pda_Jj9Kk0L\n"
        "            Description: pda_Jj9Kk0L\n"
        "            Check: SubjectKilled\n"
        "            Names:\n"
        "              - ZiraxTrooper\n"
        "            Amount: 10\n"
        "            CompletedMessage: pda_Jj9Kk0L\n",
        "".join(actions))
    model = M(Y(five_no_cm), C(GOOD_CSV))
    issues = validate_model(model)
    a2 = [i for i in issues if i.code == "PDA-A2"]
    assert len(a2) == 1 and a2[0].entry is None   # ligne unique agregee
    assert "5" in a2[0].message


def test_title_limits_match_game_guide():
    assert TITLE_LIMITS == {"TaskTitle": 26, "ActionTitle": 24}


# ------------------------------------------------------------------ A2

def test_missing_completed_message_is_warning(good_model):
    chapter, task, action = _first_action(good_model)
    node = [c for c in action.children if c.key == "CompletedMessage"][0]
    action.children.remove(node)
    issues = [i for i in validate_action(good_model, chapter, task, action)
              if i.code == "PDA-A2"]
    # avertissement (et non erreur) : la vanille elle-meme en est depourvue
    assert issues and issues[0].severity == "warning"


def test_check_without_names_is_warning(good_model):
    chapter, task, action = _first_action(good_model)
    node = [c for c in action.children if c.key == "Names"][0]
    action.children.remove(node)
    issues = [i for i in validate_action(good_model, chapter, task, action)
              if i.code == "PDA-A2"]
    # avertissement : le contenu officiel contient des actions avec Check
    # sans Names/Types (16 ItemsPickedUp) qui fonctionnent
    assert issues and issues[0].severity == "warning"


# ------------------------------------------------------------------ A3

def test_reward_count_never_flagged(good_model):
    """Correction du 12/09/2026 : la pile maximale depend des ITEMS DU
    SCENARIO (souvent >> 999) et le jeu DECOMPOSE automatiquement les
    recompenses en plusieurs piles -- une quantite elevee n'est jamais
    une erreur (retour utilisateur : MoneyCard pile 50000, recompense
    100000 -> deux piles de 50000)."""
    chapter = good_model.chapters()[0]
    from core.pda.model import RewardEntry
    good_model.set_rewards(chapter, [RewardEntry(kind="Item", name="MoneyCard",
                                                 count=100000)])
    assert [i for i in validate_model(good_model) if i.code == "PDA-A3"] == []


# ------------------------------------------------------------------ A4

def test_when_rewarded_on_first_chapter_is_error():
    bad = GOOD_YAML.replace("Visibility: Always", "Visibility: WhenRewarded")
    model = PdaModel(parse_yaml_text(bad), parse_csv_text(GOOD_CSV))
    issues = [i for i in validate_model(model) if i.code == "PDA-A4"]
    assert issues and issues[0].severity == "error"


# ------------------------------------------------------------------ A5

def test_chain_target_missing_is_error(good_model):
    chapter = good_model.chapters()[0]
    good_model.set_scalar(chapter, "ActivateChapterOnCompletion",
                          "pda_ZZ9Yy8X")
    issues = [i for i in validate_model(good_model) if i.code == "PDA-A5"]
    assert issues and "pda_ZZ9Yy8X" in issues[0].message


def test_chain_target_existing_is_clean(good_model):
    chapter = good_model.chapters()[0]
    good_model.set_scalar(chapter, "ActivateChapterOnCompletion",
                          "pda_Aa1Bb2C")   # lui-meme : existe
    assert [i for i in validate_model(good_model) if i.code == "PDA-A5"] == []


# ------------------------------------------------------------------ A6

def test_yaml_token_missing_from_csv_is_warning(good_model):
    chapter = good_model.chapters()[0]
    good_model.set_scalar(chapter, "PictureFile", "pda_NoNo9Q")  # hors CSV
    issues = [i for i in validate_csv_tokens(good_model)
              if i.severity == "warning"]
    assert issues and issues[0].message.endswith("pda_NoNo9Q")


def test_orphan_csv_token_is_warning(good_model):
    model = PdaModel(good_model.yaml_doc, parse_csv_text(
        GOOD_CSV + "pda_OrPh4nN,Orphelin,Orphelin\n"))
    issues = [i for i in validate_csv_tokens(model) if i.severity == "warning"]
    assert issues and "pda_OrPh4nN" in issues[0].message


# ------------------------------------------------------------------ A7

def test_types_on_check_without_types_is_warning(good_model):
    chapter, task, action = _first_action(good_model)
    # SubjectKilled : NAMES uniquement -- un Types residu doit alerter
    good_model.set_list(action, "Types", ["MedPack"])
    issues = [i for i in validate_action(good_model, chapter, task, action)
              if i.code == "PDA-A7"]
    assert issues and issues[0].severity == "warning"
