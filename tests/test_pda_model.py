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

"""Tests du NOUVEAU module PDA (core/pda/) -- documents synthetiques en
memoire, aucune dependance aux fichiers de reference locaux (PdaScriptDoc/,
non suivi git). Les formes attendues y reproduisent ce qui est CONFIRME sur
les 3 vrais fichiers (vanille/Atlantis/RE2, cartographie du 31/08/2026)."""
import pytest

from core.csv_handler import parse_csv_text
from core.pda.model import (CHAPTER_REQUIRED_DEFAULTS, PdaModel, RewardEntry,
                            generate_token)
from core.pda.schema import (CHECKS, CATEGORIES, VISIBILITY, action_fields,
                             check_spec)
from core.yamllite.parser import parse_yaml_text
from core.yamllite.model import YamlEntry

MINI_YAML = """# mini PDA de test
Chapters:
  - ChapterTitle: pda_Aa1Bb2C
    Category: SoloMission
    NoSkip: 'true'
    Activatable: Always
    Visibility: Always
    PlayerLevel: 5
    Description: pda_Dd4Ee5F
    Tasks:
      - TaskTitle: pda_Gg7Hh8I
        Actions:
          - ActionTitle: pda_Jj9Kk0L
            Description: pda_Jj9Kk0L
            Check: SubjectKilled
            Names:
              - ZiraxTrooper
              - XenuMainRG
            Amount: 10
            AllowManualCompletion: 'true'
          - ActionTitle: pda_Mm1Nn2O
            Description: pda_Mm1Nn2O
            Check: NearPoi
            Names:
              - AlienOutpost1
            TriggerDistance: 50
            GuidingDistance: -1
Creator: "Test"
"""

MINI_CSV = """KEY,English,Français
pda_Aa1Bb2C,First chapter,Premier chapitre
pda_Dd4Ee5F,Description FR? no EN,Description FR
pda_Gg7Hh8I,Task one,Tache une
pda_Jj9Kk0L,Kill them,Tuez-les
pda_Mm1Nn2O,Go there,Allez-y
"""


@pytest.fixture
def model():
    ydoc = parse_yaml_text(MINI_YAML)
    csv_doc = parse_csv_text(MINI_CSV)
    return PdaModel(ydoc, csv_doc)


# ---------------------------------------------------------------------------
# Lecture / round-trip
# ---------------------------------------------------------------------------
def test_roundtrip_without_mutation():
    assert parse_yaml_text(MINI_YAML).render() == MINI_YAML


def test_read_chapters_and_texts(model):
    chapters = model.chapters()
    assert len(chapters) == 1
    ch = chapters[0]
    assert model.chapter_title_token(ch) == "pda_Aa1Bb2C"
    assert model.scalar(ch, "Category") == "SoloMission"
    assert model.scalar(ch, "PlayerLevel") == "5"
    assert model.csv_text("pda_Aa1Bb2C", "English") == "First chapter"
    assert model.csv_text("pda_Aa1Bb2C", "Français") == "Premier chapitre"
    assert model.csv_languages() == ["English", "Français"]


def test_read_tasks_actions(model):
    ch = model.chapters()[0]
    tasks = model.tasks(ch)
    assert len(tasks) == 1
    actions = model.actions(tasks[0])
    assert len(actions) == 2
    assert model.action_check(actions[0]) == "SubjectKilled"
    assert model.get_list(actions[0], "Names") == ["ZiraxTrooper", "XenuMainRG"]
    assert model.scalar(actions[0], "Amount") == "10"
    assert model.action_check(actions[1]) == "NearPoi"


# ---------------------------------------------------------------------------
# Mutations scalaires
# ---------------------------------------------------------------------------
def test_set_scalar_add_update_remove(model):
    ch = model.chapters()[0]
    model.set_scalar(ch, "StartMessage", "pda_NEW1")
    assert model.scalar(ch, "StartMessage") == "pda_NEW1"
    model.set_scalar(ch, "StartMessage", "pda_NEW2")
    assert model.scalar(ch, "StartMessage") == "pda_NEW2"
    assert sum(1 for c in ch.children if c.key == "StartMessage") == 1
    model.set_scalar(ch, "StartMessage", "")
    assert model.scalar(ch, "StartMessage") == ""


def test_set_scalar_required_default(model):
    ch = model.chapters()[0]
    model.set_scalar(ch, "PlayerLevel", "", CHAPTER_REQUIRED_DEFAULTS)
    assert model.scalar(ch, "PlayerLevel") == "1"


def test_set_list_replace(model):
    ch = model.chapters()[0]
    action = model.actions(model.tasks(ch)[0])[0]
    model.set_list(action, "Names", ["NewTarget"])
    assert model.get_list(action, "Names") == ["NewTarget"]
    model.set_list(action, "Names", [])
    assert model.get_list(action, "Names") == []


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
def test_create_chapter_task_action(model):
    n0 = len(model.chapters())
    ch = model.create_chapter()
    assert len(model.chapters()) == n0 + 1
    assert model.scalar(ch, "Category") == "SoloMission"
    assert model.scalar(ch, "NoSkip") == "true"
    assert ch.value.startswith("pda_") and ch.value not in (
        "pda_Aa1Bb2C", "pda_Dd4Ee5F", "pda_Gg7Hh8I", "pda_Jj9Kk0L", "pda_Mm1Nn2O")
    task = model.create_task(ch)
    action = model.create_action(task, "NearPoi")
    assert model.action_check(action) == "NearPoi"
    assert model.scalar(action, "Description").startswith("pda_")
    # relecture apres re-parse
    m2 = PdaModel(parse_yaml_text(model.yaml_doc.render()), model.csv_doc)
    ch2 = m2.chapters()[-1]
    assert m2.scalar(ch2, "Category") == "SoloMission"
    assert m2.action_check(m2.actions(m2.tasks(ch2)[0])[0]) == "NearPoi"


def test_create_chapter_without_root():
    ydoc = parse_yaml_text("# vide\n")
    m = PdaModel(ydoc, parse_csv_text(MINI_CSV))
    ch = m.create_chapter()
    assert m.chapters() == [ch]
    assert parse_yaml_text(ydoc.render()).render() == ydoc.render()


def test_duplicate_chapter_retokenizes(model):
    ch = model.chapters()[0]
    clone = model.duplicate_chapter(ch)
    assert clone is not None and clone.value != model.chapter_title_token(ch)
    # chaque jeton du clone est neuf et present dans le CSV
    tokens = model.collect_all_tokens()
    for entry in [clone] + [c for c in _walk(clone) if c.value.startswith("pda_")]:
        assert entry.value in tokens
    model.delete_entry(clone)


def test_duplicate_unknown_entry_returns_none(model):
    assert model.duplicate_chapter(object()) is None


def test_move_and_delete(model):
    ch = model.chapters()[0]
    action = model.actions(model.tasks(ch)[0])[0]
    assert model.move_entry(action, -1) is False  # deja en tete
    second = model.create_action(model.tasks(ch)[0], "WaitAction")
    assert model.move_entry(second, -1) is True
    assert model.actions(model.tasks(ch)[0])[1] is second
    model.delete_entry(second)
    assert second not in model.actions(model.tasks(ch)[0])


# ---------------------------------------------------------------------------
# Recompenses / repetition / activations
# ---------------------------------------------------------------------------
def test_rewards_roundtrip(model):
    ch = model.chapters()[0]
    rewards = [RewardEntry(kind="Type", name="XP", count=5000),
               RewardEntry(kind="Item", name="MoneyCard", count=1000, meta="32"),
               RewardEntry(kind="Type", name="Reputation", count=5, faction="Talon")]
    model.set_rewards(ch, rewards)
    assert model.rewards(ch) == rewards
    doc2 = parse_yaml_text(model.yaml_doc.render())
    m2 = PdaModel(doc2, model.csv_doc)
    assert m2.rewards(m2.chapters()[0]) == rewards
    m2.set_rewards(m2.chapters()[0], [])
    assert m2.rewards(m2.chapters()[0]) == []
    assert "Rewards" not in [c.key for c in m2.chapters()[0].children]


def test_repeat_fields(model):
    ch = model.chapters()[0]
    model.set_repeat_field(ch, "NumRepeats", "3")
    model.set_repeat_field(ch, "NoReminder", "true")
    assert model.repeat_fields(ch) == {"NumRepeats": "3", "NoReminder": "true"}
    doc2 = parse_yaml_text(model.yaml_doc.render())
    m2 = PdaModel(doc2, model.csv_doc)
    assert m2.repeat_fields(m2.chapters()[0]) == {"NumRepeats": "3", "NoReminder": "true"}
    # effacement complet : le noeud disparait
    m2.set_repeat_field(m2.chapters()[0], "NumRepeats", "")
    m2.set_repeat_field(m2.chapters()[0], "NoReminder", "")
    assert m2.repeat_fields(m2.chapters()[0]) == {}


def test_activation_primary_key_swaps(model):
    ch = model.chapters()[0]
    entry = model.create_activation(ch)
    assert entry.key == "Names"
    model.set_activation_names(entry, ["AlienOutpost1"])
    model.set_activation_field(entry, "NoSkip", "true")
    # bascule vers Check : le scalaire enfant homonyme est absorbe inline
    model.set_activation_primary_key(entry, "Check")
    model.set_activation_field(entry, "Check", "DialogOption")
    assert model.activation_names(entry) == ["AlienOutpost1"]
    assert model.activation_field(entry, "Check") == "DialogOption"
    out = model.yaml_doc.render()
    m2 = PdaModel(parse_yaml_text(out), model.csv_doc)
    e2 = m2.activations(m2.chapters()[0])[0]
    assert e2.key == "Check"
    assert m2.activation_names(e2) == ["AlienOutpost1"]
    assert m2.activation_field(e2, "Check") == "DialogOption"
    assert m2.activation_field(e2, "NoSkip") == "true"
    # retour Check -> Names : contenu preserve a la generation suivante
    m2.set_activation_primary_key(e2, "Names")
    m3 = PdaModel(parse_yaml_text(m2.yaml_doc.render()), model.csv_doc)
    e3 = m3.activations(m3.chapters()[0])[0]
    assert e3.key == "Names"
    assert m3.activation_names(e3) == ["AlienOutpost1"]
    assert m3.activation_field(e3, "Check") == "DialogOption"


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------
def test_csv_set_creates_row_and_pads(model):
    token = "pda_ZZ9Yy8X"
    created = model.set_csv_text(token, "Hello", "English")
    assert created is True
    assert model.csv_text(token, "English") == "Hello"
    assert model.csv_text(token, "Français") == ""
    # 2e ecriture : mise a jour, pas de doublon
    assert model.set_csv_text(token, "Bonjour", "Français") is False
    rows = [r for r in model.csv_doc.rows if r[0] == token]
    assert len(rows) == 1
    assert rows[0][0] == token and "Hello" in rows[0] and "Bonjour" in rows[0]


def test_tokens_unique(model):
    used = model.collect_all_tokens()
    assert generate_token(used) not in used


# ---------------------------------------------------------------------------
# Prefixes de format ('mbox;20|pda_XXX') et textes bruts -- confirmes sur les
# vrais fichiers (StartMessage: mbox;20|pda_mKuKK, NotifyMessage:
# high;30|eden_pda_a0SeOOO...)
# ---------------------------------------------------------------------------
def test_split_token_value():
    from core.pda.model import split_token_value
    assert split_token_value("mbox;20|pda_KaOsQr") == ("mbox;20", "pda_KaOsQr")
    assert split_token_value("norm;20|pda_44CuO") == ("norm;20", "pda_44CuO")
    assert split_token_value("high;30|eden_pda_a0SeOOO") == ("high;30", "eden_pda_a0SeOOO")
    assert split_token_value("pda_pure") == ("", "pda_pure")
    # un '|' sans jeton valide apres = texte brut entier
    assert split_token_value("choix A | choix B") == ("", "choix A | choix B")
    assert split_token_value("") == ("", "")
    assert split_token_value(None) == ("", "")


def test_collect_all_tokens_with_prefixed_values():
    ydoc = parse_yaml_text(
        "Chapters:\n"
        "  - ChapterTitle: pda_Aa1Bb2C\n"
        "    StartMessage: mbox;20|pda_Pref1X\n"
        "    Description: high;30|eden_pda_Pref2Y\n"
        "    SkipMessage: texte libre sans jeton\n")
    m = PdaModel(ydoc, parse_csv_text(MINI_CSV))
    tokens = m.collect_all_tokens()
    assert "pda_Aa1Bb2C" in tokens
    assert "pda_Pref1X" in tokens
    assert "eden_pda_Pref2Y" in tokens


def test_duplicate_preserves_prefixes_and_copies_csv(model):
    ch = model.chapters()[0]
    model.set_scalar(ch, "StartMessage", "mbox;20|pda_Pref9Z")
    model.set_csv_text("pda_Pref9Z", "Hello prefix", "English")
    clone = model.duplicate_chapter(ch)
    assert clone.get("StartMessage").startswith("mbox;20|")
    new_token = clone.get("StartMessage").split("|", 1)[1]
    assert new_token != "pda_Pref9Z"
    assert model.csv_text(new_token, "English") == "Hello prefix"
    model.delete_entry(clone)


def _walk(entry):
    yield entry
    for c in entry.children:
        if isinstance(c, YamlEntry):
            yield from _walk(c)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
def test_schema_covers_confirmed_checks():
    for check in ("WaitAction", "NearPoi", "NearUnit", "DialogOption", "Signal",
                  "SubjectKilled", "BlockDestroyed", "ResourceDiscovered",
                  "StarClassEntered", "PlayfieldTypeEntered", "InventoryContains",
                  "StructureSpawned", "BiomeChanged", "ToolbarContains",
                  "WindowOpened", "PlantHarvested", "MainPowerSwitched"):
        assert check in CHECKS, check
    spec = check_spec("")
    assert spec.check == ""  # actions purement informatives (1144 occurrences)
    unknown = check_spec("UnCheckInvente")
    assert unknown.check == "UnCheckInvente"  # editable, pas interdit


def test_action_fields_always_start_with_description():
    for check in CHECKS:
        fields = action_fields(check)
        assert fields[0].key == "Description"
        assert any(f.key == "CompletedMessage" for f in fields)


def test_schema_enums_match_reference_files():
    assert set(CATEGORIES) >= {"SoloMission", "FactionMission", "Tutorial", "FAQ"}
    assert "ByReputation" in VISIBILITY and "WhenChecked" in VISIBILITY
