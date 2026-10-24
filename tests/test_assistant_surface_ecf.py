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

"""Surface ECF (pure) : cibles, outils de lecture, validation contre la
valeur vivante, application, bloc cree. Puis l'applier du widget (undo)."""
from pathlib import Path

from core.ai.assistant.changeset import Change
from core.ai.assistant.surfaces import ecf as surface
from core.ecf.model import block_identity
from core.ecf.parser import parse_ecf_file, parse_ecf_text

FIXTURE = Path(__file__).parent / "fixtures" / "sample.ecf"


def _set(target="[399] / HitPoints", old="600", new="900"):
    return Change(kind="ecf_set", target=target, old=old, new=new)


def test_parse_target_accepts_short_and_prefixed_forms():
    assert surface.parse_target("[399] / Count") == ("399", "Count")
    assert surface.parse_target("Blocks.ecf [399] / Count") == ("399", "Count")
    assert surface.parse_target("399 / Count") is None
    assert surface.parse_target("") is None


def test_validate_accepts_a_live_value():
    doc = parse_ecf_file(FIXTURE)
    assert surface.validate(doc, [_set()]) == []


def test_validate_refuses_a_stale_value():
    doc = parse_ecf_file(FIXTURE)
    assert surface.validate(doc, [_set(old="999")]) == ["ecf_value_changed"]


def test_validate_reports_target_and_lookup_problems():
    doc = parse_ecf_file(FIXTURE)
    assert surface.validate(doc, [_set(target="pas une cible")]) == [
        "ecf_target_invalid"]
    assert surface.validate(doc, [_set(target="[404] / HitPoints")]) == [
        "ecf_block_not_found"]
    assert surface.validate(doc, [_set(target="[399] / Inconnu")]) == [
        "ecf_key_missing"]
    assert surface.validate(doc, [Change(kind="yaml_set", target="[1] / x")]) == [
        "ecf_kind_unsupported"]


def test_validate_create_block():
    doc = parse_ecf_file(FIXTURE)
    change = Change(kind="ecf_create_block",
                    target="Block Id: 500, Name: TestBlock",
                    new="HitPoints: 10")
    assert surface.validate(doc, [change]) == []
    duplicate = Change(kind="ecf_create_block",
                       target="Block Id: 399, Name: Autre",
                       new="HitPoints: 10")
    assert surface.validate(doc, [duplicate]) == ["ecf_duplicate_identity"]
    no_identity = Change(kind="ecf_create_block", target="Block",
                         new="HitPoints: 10")
    assert surface.validate(doc, [no_identity]) == ["ecf_identity_missing"]
    broken = Change(kind="ecf_create_block",
                    target="Block Id: 501, Name: X", new="")
    assert surface.validate(doc, [broken]) == ["ecf_block_invalid"]


def test_apply_sets_the_value_and_the_old_value_then_mismatches():
    doc = parse_ecf_file(FIXTURE)
    change = _set()
    assert surface.validate(doc, [change]) == []
    assert surface.apply(doc, [change]) == 1
    assert "HitPoints: 900" in doc.render()
    assert surface.validate(doc, [change]) == ["ecf_value_changed"]


def test_apply_appends_a_new_block():
    doc = parse_ecf_file(FIXTURE)
    change = Change(kind="ecf_create_block",
                    target="Block Id: 500, Name: TestBlock",
                    new="HitPoints: 10")
    assert surface.apply(doc, [change]) == 1
    assert "TestBlock" in doc.render()
    assert surface.validate(doc, [change]) == ["ecf_duplicate_identity"]


def test_context_is_the_selected_block_only():
    doc = parse_ecf_file(FIXTURE)
    block = next(b for b in doc.iter_blocks() if block_identity(b) == "399")
    context = surface.context(doc, block, "Blocks.ecf")
    assert context.label == "Blocks.ecf [399] Block"
    assert "HitPoints: 600" in context.text
    assert surface.context(doc, None, "Blocks.ecf").text == ""


def test_tools_read_the_document():
    doc = parse_ecf_file(FIXTURE)
    tools = surface.registry(doc)
    assert tools.names("ecf") == ["ecf_find_property", "ecf_list_blocks",
                                  "ecf_read_block", "ecf_validate"]
    blocks = tools.call("ecf_list_blocks", {})
    assert blocks["ok"] and "ConcreteBlocks" in blocks["content"]
    text = tools.call("ecf_read_block", {"ident": "399"})
    assert "HitPoints: 600" in text["content"]
    found = tools.call("ecf_find_property", {"key": "param1"})
    assert '"0.6"' not in found["content"]
    assert "0.3" in found["content"] and "0.5" in found["content"]


def test_tools_accept_aliases_and_explain_failures():
    doc = parse_ecf_file(FIXTURE)
    tools = surface.registry(doc)
    assert "HitPoints: 600" in tools.call("ecf_read_block",
                                          {"name": "399"})["content"]
    assert "missing parameter 'ident'" in tools.call(
        "ecf_read_block", {})["content"]
    assert "missing parameter 'key'" in tools.call(
        "ecf_find_property", {})["content"]
    assert "no block has the property" in tools.call(
        "ecf_find_property", {"key": "Inconnu"})["content"]
    identity = tools.call("ecf_find_property", {"key": "Name"})["content"]
    assert '"editable": false' in identity
    assert "ConcreteBlocks" in identity


def test_validate_tool_reports_builtin_issues():
    doc = parse_ecf_text("\n".join([
        "{ Block Id: 7, Name: BadBlock",
        "  Count: 3,4",
        "}",
        ""]))
    tools = surface.registry(doc)
    result = tools.call("ecf_validate", {})["content"]
    assert '"code": "E004"' in result and "Virgule non protegee" in result
    clean = parse_ecf_text("\n".join([
        "{ Block Id: 8, Name: Ok",
        '  Count: "3,4"',
        "}",
        ""]))
    assert "no issue" in surface.registry(clean).call(
        "ecf_validate", {})["content"]


def test_widget_applies_then_undoes(qapp):
    from gui.ecf_edit_widget import EcfEditWidget
    widget = EcfEditWidget(FIXTURE)
    try:
        binding = widget.assistant_surface()
        ok, problem = binding.apply([_set()])
        assert (ok, problem) == (True, "")
        assert "HitPoints: 900" in widget.doc.render()
        assert widget._modified is True
        widget.undo()
        assert "HitPoints: 600" in widget.doc.render()
    finally:
        from PyQt6 import sip
        sip.delete(widget)


def test_widget_refuses_a_stale_value_without_touching_anything(qapp):
    from gui.ecf_edit_widget import EcfEditWidget
    widget = EcfEditWidget(FIXTURE)
    try:
        ok, problem = widget.assistant_surface().apply([_set(old="999")])
        assert (ok, problem) == (False, "ecf_value_changed")
        assert "HitPoints: 600" in widget.doc.render()
        assert widget._modified is False
    finally:
        from PyQt6 import sip
        sip.delete(widget)
