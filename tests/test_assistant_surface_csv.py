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

"""Surface CSV (pure) : cibles, outils, validation, application, puis
l'applier du widget (table vivante + undo)."""
from core.ai.assistant.changeset import Change
from core.ai.assistant.surfaces import csv as surface

HEADER = ["Key", "Text", "Notes"]


def _rows():
    return [["A", "Hello", ""], ["B", "World", "x"]]


def _set(target="[2] / Text", old="World", new="Monde"):
    return Change(kind="csv_set", target=target, old=old, new=new)


def test_parse_target():
    assert surface.parse_target("[12] / Description") == (12, "Description")
    assert surface.parse_target("PDA.csv [12] / Description") == (
        12, "Description")
    assert surface.parse_target("ligne 12 / Description") is None


def test_validate_and_apply():
    rows = _rows()
    assert surface.validate(HEADER, rows, [_set()]) == []
    assert surface.apply(HEADER, rows, [_set()]) == 1
    assert rows[1][1] == "Monde"
    assert surface.validate(HEADER, rows, [_set()]) == ["csv_value_changed"]


def test_validate_reports_bounds_and_columns():
    assert surface.validate(HEADER, _rows(), [_set(target="[9] / Text")]) == [
        "csv_row_out"]
    assert surface.validate(HEADER, _rows(), [_set(target="[1] / Inconnu")]) == [
        "csv_column_unknown"]
    assert surface.validate(HEADER, _rows(), [
        Change(kind="ecf_set", target="[1] / Text")]) == [
        "csv_kind_unsupported"]


def test_apply_pads_a_short_row():
    rows = [["A"]]
    assert surface.apply(["Key", "Text"], rows, [
        Change(kind="csv_set", target="[1] / Text", old="", new="v")]) == 1
    assert rows[0] == ["A", "v"]


def test_tools_read_and_find_rows():
    tools = surface.registry(HEADER, _rows())
    assert tools.names("csv") == ["csv_find", "csv_read_rows"]
    read = tools.call("csv_read_rows", {"start": 2, "count": 1})
    assert read["ok"] and "total_lines" in read["content"]
    found = tools.call("csv_find", {"text": "world"})
    assert '"line": 2' in found["content"]
    assert "unknown column" in tools.call(
        "csv_find", {"text": "x", "column": "Nope"})["content"]
    assert "missing parameter 'text'" in tools.call("csv_find", {})["content"]
    assert '"line": 2' in tools.call("csv_find", {"query": "world"})["content"]


def test_context_is_the_current_row():
    context = surface.context("PDA.csv", HEADER, _rows(), 1, 1)
    assert context.label == "PDA.csv ligne 2 / Text"
    assert "Text = World" in context.text
    assert surface.context("PDA.csv", HEADER, _rows(), -1, -1).text == ""


def test_widget_applies_then_undoes(qapp, tmp_path):
    from gui.csv_edit_widget import CsvEditWidget
    path = tmp_path / "Dialogues.csv"
    path.write_text('Key,Text\nA,Hello\nB,World\n', encoding="utf-8")
    widget = CsvEditWidget(path)
    try:
        assert widget.doc.header == ["Key", "Text"]
        binding = widget.assistant_surface()
        ok, problem = binding.apply([_set()])
        assert (ok, problem) == (True, "")
        assert widget.doc.rows[1][1] == "Monde"
        assert widget.table.item(1, 1).text() == "Monde"
        widget.undo()
        assert widget.doc.rows[1][1] == "Monde"  # la table fait foi, pas doc
        assert widget.table.item(1, 1).text() == "World"
    finally:
        from PyQt6 import sip
        sip.delete(widget)


def test_readonly_widget_has_no_surface(qapp, tmp_path):
    from gui.csv_edit_widget import CsvEditWidget
    path = tmp_path / "PDA.csv"
    path.write_text('Key,Text\nA,Hello\n', encoding="utf-8")
    widget = CsvEditWidget(path, editable=False)
    try:
        assert widget.assistant_surface() is None
    finally:
        from PyQt6 import sip
        sip.delete(widget)
