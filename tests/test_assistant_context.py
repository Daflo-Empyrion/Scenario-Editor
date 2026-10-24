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

"""Contexte joint : masquage THEN troncature, bloc balise, contrat de
surface (assistant_context) et repli sur la selection."""
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QPlainTextEdit, QWidget

from core.ai.assistant.context import TabContext, build
from gui.assistant_context import tab_context


def test_build_redacts_before_truncating():
    context = build("A", "x" * 20 + " password=hunter2", max_chars=20)
    assert context.truncated is True
    assert context.redacted == 1
    assert "hunter2" not in context.text


def test_build_under_the_cap_keeps_everything():
    context = build("Blocks.ecf", "Count: 3")
    assert (context.text, context.chars, context.truncated,
            context.redacted) == ("Count: 3", 8, False, 0)


def test_prompt_block_is_empty_without_text():
    assert TabContext("Blocks.ecf", "").prompt_block() == ""


def test_prompt_block_wraps_the_context():
    block = build("Blocks.ecf", "Count: 3").prompt_block()
    assert block.startswith("[Contexte joint : Blocks.ecf]")
    assert block.endswith("[/Contexte joint]")


def test_tab_context_prefers_a_surface_adapter(qapp):
    widget = QWidget()
    widget.assistant_context = lambda: ("Blocks.ecf [399]", "Count: 3")
    context = tab_context(widget, "onglet")
    assert context.label == "Blocks.ecf [399]"
    assert context.text == "Count: 3"


def test_tab_context_falls_back_to_the_selection(qapp):
    widget = QWidget()
    editor = QPlainTextEdit(widget)
    editor.setPlainText("bonjour")
    cursor = editor.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    editor.setTextCursor(cursor)
    context = tab_context(widget, "notes.txt")
    assert context.label == "notes.txt"
    assert context.text == "bonjour"


def test_tab_context_without_selection_is_empty(qapp):
    widget = QWidget()
    QPlainTextEdit(widget)
    assert tab_context(widget, "notes.txt").text == ""
