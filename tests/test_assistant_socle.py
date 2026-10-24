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

"""Socle assistant : session (plafond, persistance), garde-fous, jeu de
changements, prompts."""
import json

import pytest

from core.ai.assistant import changeset, guards, prompts
from core.ai.assistant.session import Session


def test_session_fit_keeps_recent_turns_and_flags_truncation():
    session = Session(system="S", max_chars=120)
    for word in ("un", "deux", "trois"):
        session.add_user(word)
    messages, truncated = session.fit()
    assert truncated is True
    assert [m["content"] for m in messages] == ["deux", "trois"]
    # Le systeme n'est jamais dans les messages retournes (l'appelant l'ajoute).
    assert all(m["role"] != "system" for m in messages)


def test_session_fit_under_budget_keeps_everything():
    session = Session(max_chars=10_000)
    session.add_user("question")
    session.add_assistant("reponse")
    messages, truncated = session.fit()
    assert truncated is False
    assert len(messages) == 2


def test_session_fit_never_starts_with_an_orphan_tool_message():
    session = Session(max_chars=60)
    session.messages.append({"role": "tool", "tool_call_id": "1",
                             "name": "t", "content": "vieux"})
    session.add_user("question")
    messages, _ = session.fit()
    assert messages[0]["role"] == "user"


def test_session_save_load_roundtrip(tmp_path):
    path = tmp_path / "assistant.json"
    session = Session(scenario="RE2", system="S", max_chars=500)
    session.add_user("bonjour")
    session.add_assistant("", [{"id": "1", "type": "function",
                                "function": {"name": "t", "arguments": "{}"}}])
    session.save(path)
    loaded = Session.load(path)
    assert loaded.scenario == "RE2"
    assert loaded.max_chars == 500
    assert loaded.messages == session.messages


def test_session_load_unreadable_file_is_empty_session(tmp_path):
    path = tmp_path / "assistant.json"
    path.write_text("{pas du json", encoding="utf-8")
    assert Session.load(path).messages == []


def test_session_load_drops_native_tool_markup_from_old_history(tmp_path):
    """Un historique ecrit avant le repli DSML ne doit pas re-apprendre au
    modele a ecrire le balisage (vecu 22/10)."""
    path = tmp_path / "assistant.json"
    path.write_text(json.dumps({"messages": [
        {"role": "user", "content": "q"},
        {"role": "assistant",
         "content": "Je verifie.\n<｜｜DSML｜｜ calls>"
                    "<｜｜DSML｜｜ invoke name=\"file_read\">"
                    "</｜｜DSML｜｜ invoke></｜｜DSML｜｜ calls>"},
    ]}, ensure_ascii=False), encoding="utf-8")
    messages = Session.load(path).messages
    assert messages[1]["content"] == "Je verifie."


def test_redact_secrets_masks_known_shapes():
    text = ("cle sk-or-v1-abcdefghijklmnop et gsk_abcdefghijklmnopqrstu "
            "password=hunter2 https://user:secret@example.test/x")
    cleaned, hidden = guards.redact_secrets(text)
    assert hidden == 4
    for secret in ("abcdefghijklmnop", "hunter2", "secret@"):
        assert secret not in cleaned
    assert "sk-***" in cleaned and "gsk_***" in cleaned


def test_redact_secrets_leaves_normal_text_alone():
    text = "Le bloc [399] ConcreteBlocks a Count: 3,4."
    assert guards.redact_secrets(text) == (text, 0)


def test_writable_refuses_modified_document():
    assert guards.writable(False) == (True, "")
    ok, key = guards.writable(True)
    assert ok is False and key == guards.UNSAVED_KEY


def test_action_rejects_unknown_class():
    from core.ai.assistant.actions import Action
    with pytest.raises(ValueError):
        Action(id="x", surface="ecf", min_class="brutal")


def test_prompt_carries_language_tone_and_invariants():
    prompt = prompts.system_prompt("fr", tone="militaire", extra="Surface ECF")
    assert "French" in prompt
    assert "militaire" in prompt
    assert "Never say a change was applied" in prompt
    assert "Surface ECF" in prompt


def test_changeset_validate_accepts_a_clean_proposal():
    proposal = changeset.ChangeSet(changes=[
        changeset.Change(kind="ecf_set", target="Blocks.ecf [399] / Count",
                         old="3,4", new="6,8", reason="double")])
    assert proposal.validate() == []


def test_changeset_validate_reports_every_problem():
    proposal = changeset.ChangeSet(changes=[
        changeset.Change(kind="inconnu", target="", old="1", new="1")])
    assert proposal.validate() == ["changement_sans_effet", "cible_vide",
                                   "kind_inconnu"]


def test_changeset_empty_is_refused():
    assert changeset.ChangeSet().validate() == ["changeset_vide"]


def test_parse_change_set_reads_the_last_fenced_block():
    text = ("Voici le detail.\n```json\n{\"changes\": []}\n```\n"
            "```json\n{\"summary\": \"ok\", \"changes\": [{\"kind\": "
            "\"ecf_set\", \"target\": \"A / Count\", \"old\": \"1\", "
            "\"new\": \"2\"}]}\n```")
    proposal, problems = changeset.parse_change_set(text)
    assert problems == []
    assert proposal.summary == "ok"
    assert proposal.changes[0].new == "2"


def test_parse_change_set_without_block_reports_absence():
    assert changeset.parse_change_set("aucun JSON ici") == (
        None, ["changeset_absent"])


def test_parse_change_set_invalid_json_is_absence():
    assert changeset.parse_change_set('```json\n{"changes": [}\n```')[1] == [
        "changeset_absent"]


def test_parse_change_set_keeps_the_unresolved_report(tmp_path):
    text = ('```json\n'
            '{"summary": "s", "changes": [{"kind": "scenario_import",'
            ' "target": "b:Blocks.ecf#X", "old": "absent", "new": "recipe"}],'
            ' "report": [{"type": "techtree", "reference": "AsgardTech",'
            ' "from": "Blocks.ecf#X", "reason": "not found"}]}\n'
            '```')
    proposal, problems = changeset.parse_change_set(text)
    assert problems == []
    assert proposal.report[0]["reference"] == "AsgardTech"
    path = tmp_path / "report.csv"
    assert proposal.write_report_csv(path) == 1
    content = path.read_text(encoding="utf-8-sig")
    assert content.splitlines()[0] == "type,reference,from,reason"
    assert "AsgardTech" in content
