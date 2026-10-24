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

"""Registre d'outils : schemas par surface, sortie bornee, erreurs remontees
au modele (jamais au thread appelant), interdiction des outils d'ecriture."""
import pytest

from core.ai.assistant.tools import FORBIDDEN_TOOLS, Tool, ToolRegistry


def _tool(name="read_block", surface="ecf", handler=None, max_chars=50):
    return Tool(name=name, description="lit un bloc",
                parameters={"properties": {"id": {"type": "string"}},
                            "required": ["id"]},
                handler=handler or (lambda args: {"id": args.get("id")}),
                surface=surface, max_chars=max_chars)


def test_schemas_are_grouped_by_surface():
    registry = ToolRegistry()
    registry.add(_tool("read_block", "ecf"))
    registry.add(_tool("read_playfield", "playfield"))
    assert registry.names() == ["read_block", "read_playfield"]
    assert registry.names("ecf") == ["read_block"]
    schema = registry.schemas("ecf")[0]
    assert schema["type"] == "function"
    assert schema["function"]["parameters"]["type"] == "object"
    assert registry.schemas("inconnue") == []


def test_unknown_tool_returns_an_error_result():
    outcome = ToolRegistry().call("nope", {})
    assert outcome["ok"] is False and "Outil inconnu" in outcome["content"]


def test_handler_exception_becomes_a_result():
    def boom(args):
        raise RuntimeError("disque absent")

    registry = ToolRegistry()
    registry.add(_tool(handler=boom))
    outcome = registry.call("read_block", {})
    assert outcome["ok"] is False
    assert "RuntimeError" in outcome["content"] and "disque absent" in outcome["content"]


def test_long_output_is_truncated_and_flagged():
    registry = ToolRegistry()
    registry.add(_tool(handler=lambda args: "x" * 500, max_chars=50))
    outcome = registry.call("read_block", {})
    assert outcome["truncated"] is True
    assert "tronquee" in outcome["content"]
    assert len(outcome["content"]) < 100


def test_non_string_result_is_json_encoded():
    registry = ToolRegistry()
    registry.add(_tool(handler=lambda args: {"blocks": [1, 2]}))
    assert registry.call("read_block", {})["content"] == '{"blocks": [1, 2]}'


def test_write_or_server_tools_are_refused():
    registry = ToolRegistry()
    for name in FORBIDDEN_TOOLS:
        with pytest.raises(ValueError):
            registry.add(_tool(name=name))


def test_duplicate_and_invalid_names_are_refused():
    registry = ToolRegistry()
    registry.add(_tool())
    with pytest.raises(ValueError):
        registry.add(_tool())
    with pytest.raises(ValueError):
        registry.add(_tool(name="Bad Name"))
