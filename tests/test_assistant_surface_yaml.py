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

"""Surface YAML : cibles pointees, contexte de l'entree, validation contre la
valeur vivante, application, puis l'applier du widget (arbre + undo)."""
from pathlib import Path

import pytest

from core.ai.assistant.changeset import Change
from core.ai.assistant.surfaces import yaml_surface as surface
from core.yamllite.parser import parse_yaml_text

TEXT = "\n".join([
    "Playfield:",
    "  Name: SectorA",
    "  PlanetType: Temperate",
    '  Coordinates: "0,0,0"',
    "",
])


def _doc():
    return parse_yaml_text(TEXT)


def _set(target="Playfield.Name", old="SectorA", new="SectorB"):
    return Change(kind="yaml_set", target=target, old=old, new=new)


def test_parse_target():
    assert surface.parse_target("Playfield.Name") == ["Playfield", "Name"]
    assert surface.parse_target("Playfield/Name") == ["Playfield", "Name"]
    assert surface.parse_target("") is None


def test_resolve_reports_missing_keys():
    doc = _doc()
    entry, code = surface.resolve(doc, ["Playfield", "Name"])
    assert entry is not None and code == ""
    assert surface.resolve(doc, ["Playfield", "Nope"]) == (
        None, "yaml_key_not_found")


def test_validate_accepts_live_value_and_refuses_stale_one():
    doc = _doc()
    assert surface.validate(doc, [_set()]) == []
    assert surface.validate(doc, [_set(old="X")]) == ["yaml_value_changed"]
    assert surface.validate(doc, [_set(target="Playfield.Nope")]) == [
        "yaml_key_not_found"]
    assert surface.validate(doc, [Change(kind="ecf_set", target="a")]) == [
        "yaml_kind_unsupported"]


def test_apply_sets_the_value_then_the_old_value_mismatches():
    doc = _doc()
    assert surface.apply(doc, [_set()]) == 1
    assert "Name: SectorB" in doc.render()
    assert surface.validate(doc, [_set()]) == ["yaml_value_changed"]


def test_context_for_a_leaf_and_a_mapping():
    doc = _doc()
    leaf, _ = surface.resolve(doc, ["Playfield", "Name"])
    context = surface.context(doc, leaf, "SectorA.yaml")
    assert context.label == "SectorA.yaml Playfield.Name"
    assert context.text == "SectorA"

    parent, _ = surface.resolve(doc, ["Playfield"])
    context = surface.context(doc, parent, "SectorA.yaml")
    assert "Name: SectorA" in context.text
    assert "PlanetType: Temperate" in context.text


def test_context_without_selection_is_empty():
    assert surface.context(_doc(), None, "SectorA.yaml").text == ""


def test_active_entries_tool_reads_the_live_document():
    doc = _doc()
    tools = surface.registry(doc)
    result = tools.call("yaml_active_entries", {"limit": 3})["content"]
    assert "Playfield.Name" in result and "SectorA" in result
    assert '"truncated": true' in result


def test_widget_applies_then_undoes(qapp, tmp_path):
    from gui.yaml_edit_widget import YamlEditWidget
    path = tmp_path / "SectorA.yaml"
    path.write_text(TEXT, encoding="utf-8")
    widget = YamlEditWidget(path)
    try:
        binding = widget.assistant_surface()
        ok, problem = binding.apply([_set()])
        assert (ok, problem) == (True, "")
        assert "Name: SectorB" in widget.doc.render()
        assert widget._modified is True
        widget.undo()
        assert "Name: SectorA" in widget.doc.render()
    finally:
        from PyQt6 import sip
        sip.delete(widget)


def test_readonly_widget_has_no_surface(qapp, tmp_path):
    from gui.yaml_edit_widget import YamlEditWidget
    path = tmp_path / "SectorA.yaml"
    path.write_text(TEXT, encoding="utf-8")
    widget = YamlEditWidget(path, editable=False)
    try:
        assert widget.assistant_surface() is None
    finally:
        from PyQt6 import sip
        sip.delete(widget)
