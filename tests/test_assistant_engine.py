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

"""Boucle d'assistant avec un faux routeur : appels d'outils, capacites
transmises, ChangeSet seulement quand l'action le demande, bornage."""
import types

from core.ai.assistant import engine
from core.ai.assistant.actions import Action
from core.ai.assistant.session import Session
from core.ai.assistant.tools import Tool, ToolRegistry

LINK = types.SimpleNamespace(label="P / m")


def _tool(surface="ecf", handler=None):
    return Tool(name="read_block", description="lit un bloc",
                parameters={}, surface=surface,
                handler=handler or (lambda args: {"Count": "3"}))


def _call(name="read_block", arguments='{"id": "399"}'):
    return {"id": "1", "type": "function",
            "function": {"name": name, "arguments": arguments}}


def _fake_router(monkeypatch, answers):
    """Installe un faux chat_with_link ; retourne la liste des appels."""
    calls = []

    def fake(messages, **kwargs):
        calls.append(([dict(m) for m in messages], kwargs))
        return answers.pop(0), LINK

    monkeypatch.setattr(engine.router, "chat_with_link", fake)
    return calls


def _session():
    session = Session(system="S")
    session.add_user("combien de ConcreteBlocks ?")
    return session


def test_tool_result_is_fed_back_and_final_text_returned(monkeypatch):
    calls = _fake_router(monkeypatch, [
        {"content": "", "tool_calls": [_call()]},
        {"content": "Count vaut 3", "tool_calls": []},
    ])
    registry = ToolRegistry()
    registry.add(_tool())
    answer = engine.ask(_session(), Action(id="explain", surface="ecf",
                                           needs_tools=True), registry)

    assert answer.text == "Count vaut 3"
    assert answer.rounds == 2
    assert answer.link == "P / m"
    assert calls[0][1]["tools"][0]["function"]["name"] == "read_block"
    # Le second appel contient la reponse de l'outil, adressee au bon appel.
    tool_messages = [m for m in calls[1][0] if m["role"] == "tool"]
    assert tool_messages[0]["tool_call_id"] == "1"
    assert '{"Count": "3"}' in tool_messages[0]["content"]


def test_invalid_tool_arguments_are_reported_not_raised(monkeypatch):
    calls = _fake_router(monkeypatch, [
        {"content": "", "tool_calls": [_call(arguments="{pas du json")]},
        {"content": "ok", "tool_calls": []},
    ])
    registry = ToolRegistry()
    registry.add(_tool())
    engine.ask(_session(), Action(id="explain", surface="ecf",
                                  needs_tools=True), registry)
    tool_messages = [m for m in calls[1][0] if m["role"] == "tool"]
    assert "Invalid JSON arguments" in tool_messages[0]["content"]


def test_capability_and_purpose_are_passed_to_the_router(monkeypatch):
    calls = _fake_router(monkeypatch, [{"content": "ok", "tool_calls": []}])
    registry = ToolRegistry()
    registry.add(_tool())
    engine.ask(_session(), Action(id="generate", surface="ecf",
                                  min_class="strong", needs_tools=True),
               registry)
    kwargs = calls[0][1]
    assert kwargs["min_class"] == "strong"
    assert kwargs["require_tools"] is True
    assert kwargs["purpose"] == "generate"


def test_changeset_is_parsed_only_when_the_action_declares_it(monkeypatch):
    text = ('```json\n{"changes": [{"kind": "ecf_set", "target": '
            '"A / Count", "old": "1", "new": "2"}]}\n```')
    _fake_router(monkeypatch, [{"content": text, "tool_calls": []}])
    action = Action(id="transform", surface="ecf", produces_changeset=True)
    answer = engine.ask(_session(), action, ToolRegistry())
    assert answer.changeset is not None
    assert answer.problems == []
    assert answer.changeset_problems == []


def test_prose_answer_yields_no_changeset(monkeypatch):
    _fake_router(monkeypatch, [{"content": "Count vaut 3", "tool_calls": []}])
    answer = engine.ask(_session(), Action(id="explain", surface="ecf"),
                        ToolRegistry())
    assert answer.changeset is None


def test_invalid_changeset_keeps_the_text_and_reports_problems(monkeypatch):
    text = '```json\n{"changes": [{"kind": "inconnu", "target": "A"}]}\n```'
    _fake_router(monkeypatch, [{"content": text, "tool_calls": []}])
    answer = engine.ask(_session(), Action(id="transform", surface="ecf",
                                           produces_changeset=True),
                        ToolRegistry())
    assert answer.text == text
    assert "kind_inconnu" in answer.changeset_problems


def test_a_looping_model_is_forced_to_answer_without_tools(monkeypatch):
    calls = _fake_router(monkeypatch, [
        {"content": "", "tool_calls": [_call()]},
        {"content": "Voici la reponse", "tool_calls": []},
    ])
    registry = ToolRegistry()
    registry.add(_tool())
    answer = engine.ask(_session(), Action(id="explain", surface="ecf",
                                           needs_tools=True), registry,
                        max_rounds=1)
    assert answer.text == "Voici la reponse"
    assert answer.problems == []
    assert calls[1][1]["tools"] is None
    assert calls[1][1].get("require_tools") is None


def test_forced_answer_still_empty_reports_the_loop(monkeypatch):
    _fake_router(monkeypatch, [
        {"content": "", "tool_calls": [_call()]},
        {"content": "", "tool_calls": []},
    ])
    registry = ToolRegistry()
    registry.add(_tool())
    answer = engine.ask(_session(), Action(id="explain", surface="ecf",
                                           needs_tools=True), registry,
                        max_rounds=1)
    assert answer.problems == ["boucle_outils_interrompue"]
    assert answer.rounds == 2


def test_tool_calls_are_logged(monkeypatch):
    _fake_router(monkeypatch, [
        {"content": "", "tool_calls": [_call()]},
        {"content": "ok", "tool_calls": []},
    ])
    registry = ToolRegistry()
    registry.add(_tool())
    answer = engine.ask(_session(), Action(id="explain", surface="ecf",
                                           needs_tools=True), registry)
    assert answer.tool_log and answer.tool_log[0].startswith("read_block(")


def test_action_needing_tools_without_tools_never_calls_the_router(monkeypatch):
    calls = _fake_router(monkeypatch, [])
    answer = engine.ask(_session(), Action(id="explain", surface="ecf",
                                           needs_tools=True), ToolRegistry())
    assert answer.problems == ["outils_indisponibles"]
    assert calls == []


def test_action_instruction_reaches_the_system_message(monkeypatch):
    calls = _fake_router(monkeypatch, [{"content": "ok", "tool_calls": []}])
    action = Action(id="chat", surface="ecf",
                    instruction="TARGET FORMAT: [id] / key")
    engine.ask(_session(), action, ToolRegistry())
    system = calls[0][0][0]
    assert system["role"] == "system"
    assert "TARGET FORMAT: [id] / key" in system["content"]


def test_empty_history_is_refused(monkeypatch):
    calls = _fake_router(monkeypatch, [])
    answer = engine.ask(Session(), Action(id="explain", surface="ecf"),
                        ToolRegistry())
    assert answer.problems == ["aucune_question"]
    assert calls == []


def test_dsml_native_calls_are_converted_and_fed_back(monkeypatch):
    """Vecu 22/10 : DeepSeek rend ses appels en balises DSML dans le contenu
    au lieu de tool_calls -> sans repli, les outils ne tournent jamais et le
    chat affiche le balisage."""
    dsml = ('Je vérifie.\n'
            '<｜｜DSML｜｜ calls>\n'
            '<｜｜DSML｜｜ invoke name="catalog_search">\n'
            '<｜｜DSML｜｜ parameter name="query" string="true">'
            'NaqahdahPlate</｜｜DSML｜｜ parameter>\n'
            '</｜｜DSML｜｜ invoke>\n'
            '</｜｜DSML｜｜ calls>')
    calls = _fake_router(monkeypatch, [
        {"content": dsml, "tool_calls": []},
        {"content": "Trouvé.", "tool_calls": []},
    ])
    registry = ToolRegistry()
    seen = []
    registry.add(Tool(name="catalog_search", description="catalogue",
                      parameters={}, surface="ecf",
                      handler=lambda args: seen.append(args) or {"ok": 1}))
    answer = engine.ask(_session(), Action(id="chat", surface="ecf",
                                           needs_tools=True), registry)
    assert answer.text == "Trouvé."
    assert seen == [{"query": "NaqahdahPlate"}]
    # le balisage n'est jamais envoye au tour suivant ni affiche
    sent = calls[1][0]
    assert not any("DSML" in str(m.get("content") or "") for m in sent)
    assert sent[-1]["role"] == "tool"


def test_dsml_without_any_invoke_leaves_no_markup():
    from core.ai.assistant.dsml import strip, tool_calls
    text, calls = tool_calls("avant <｜｜DSML｜｜ calls> après")
    assert text == "avant" and calls == []
    # balise orpheline (bloc tronque) : rien ne doit rester a l'ecran
    assert strip("fin </｜｜DSML｜｜ invoke>") == "fin"
    assert strip("rien a nettoyer") == "rien a nettoyer"


def test_dsml_attributes_single_quoted_are_read():
    from core.ai.assistant.dsml import tool_calls
    text, calls = tool_calls(
        "<｜｜DSML｜｜ invoke name='file_read'>"
        "<｜｜DSML｜｜ parameter name='path' string='true'>Sectors/Sectors.yaml"
        "</｜｜DSML｜｜ parameter></｜｜DSML｜｜ invoke>")
    assert text == ""
    assert calls[0]["function"]["name"] == "file_read"
    assert '"path": "Sectors/Sectors.yaml"' in calls[0]["function"]["arguments"]


def test_forced_answer_is_nudged_and_cleaned_of_native_markup(monkeypatch):
    """Vecu 22/10 : au plafond de tours, le modele force en texte re-emet son
    balisage d'appel -> il s'affichait brut dans le chat."""
    calls = _fake_router(monkeypatch, [
        {"content": "", "tool_calls": [_call()]},
        {"content": ("Les noms de playfields different.\n"
                     "<｜｜DSML｜｜ calls>\n"
                     "<｜｜DSML｜｜ invoke name=\"scenario_list_files\">\n"
                     "<｜｜DSML｜｜ parameter name=\"pattern\" string=\"true\">"
                     "EdenStarterBeginner</｜｜DSML｜｜ parameter>\n"
                     "</｜｜DSML｜｜ invoke>\n</｜｜DSML｜｜ calls>"),
         "tool_calls": []},
    ])
    registry = ToolRegistry()
    registry.add(_tool())
    answer = engine.ask(_session(), Action(id="explain", surface="ecf",
                                           needs_tools=True), registry,
                        max_rounds=1)
    assert answer.text == "Les noms de playfields different."
    assert "DSML" not in answer.text
    # la consigne empeche le modele de repartir en appels d'outils
    assert calls[1][0][-1]["role"] == "user"
    assert "do not call any tool" in calls[1][0][-1]["content"]


def test_forced_answer_made_only_of_markup_still_reports_the_loop(monkeypatch):
    _fake_router(monkeypatch, [
        {"content": "", "tool_calls": [_call()]},
        {"content": "<｜｜DSML｜｜ calls>"
                    "<｜｜DSML｜｜ invoke name=\"read_block\">"
                    "</｜｜DSML｜｜ invoke></｜｜DSML｜｜ calls>",
         "tool_calls": []},
    ])
    registry = ToolRegistry()
    registry.add(_tool())
    answer = engine.ask(_session(), Action(id="explain", surface="ecf",
                                           needs_tools=True), registry,
                        max_rounds=1)
    assert answer.text == ""
    assert answer.problems == ["boucle_outils_interrompue"]
