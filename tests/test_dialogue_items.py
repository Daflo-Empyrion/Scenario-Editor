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

"""Autocompletion des items dans les scripts de dialogue (v1.9.0, backlog
"Dialogues.ecf : autocompletion des items give/take") : detection du token
d'Id sous le curseur (core/dialogue_items.py -- formes relevees sur le
vrai Dialogues.ecf vanille : AddItem('Id', n), RemoveItem, HasItem) et
branchement du completer dans le delegate de valeurs de l'editeur ECF."""

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCompleter
from core.dialogue_items import quoted_item_token, script_value_key


def _own_completer(line_edit):
    """Le completer installe PAR NOUS (taggue 'dialogue_item_completer') --
    le combo editable de Qt a aussi son completer interne."""
    return line_edit.findChild(QCompleter, "dialogue_item_completer")


def test_quoted_item_token_partial_id():
    text = "AddItem('Tok"
    assert quoted_item_token(text, len(text)) == "Tok"


def test_quoted_item_token_at_start_of_id():
    text = 'Execute: "AddItem(\''
    assert quoted_item_token(text, len(text)) == ""


def test_quoted_item_token_closed_id_gives_none():
    # Id deja ferme : les arguments suivants sont des nombres, rien a completer
    text = "AddItem('Token'"
    assert quoted_item_token(text, len(text)) is None


def test_quoted_item_token_second_argument_gives_none():
    text = "AddItem('Token', 1, 8)"
    assert quoted_item_token(text, len(text)) is None


def test_quoted_item_token_inside_before_cursor():
    text = "if (!HasItem('DF_MeleeSw"
    assert quoted_item_token(text, len(text)) == "DF_MeleeSw"


def test_quoted_item_token_after_close_but_before_cursor():
    # curseur AVANT l'apostrophe fermante : le token partiel est complet
    text = "AddItem('Token', 1)"
    assert quoted_item_token(text, 14) == "Token"


def test_quoted_item_token_not_a_command():
    assert quoted_item_token("SetGlobalVar name 'x", 20) is None
    assert quoted_item_token("", 0) is None
    assert quoted_item_token("OpenTraderWindow()", 18) is None


def test_quoted_item_token_remove_item():
    text = "OptionExecute_2: \"RemoveItem('Tok"
    assert quoted_item_token(text, len(text)) == "Tok"


def test_script_value_keys():
    assert script_value_key("Execute")
    assert script_value_key("Execute_1")
    assert script_value_key("OptionIf_2")
    assert script_value_key("OptionExecute_12")
    assert script_value_key("NextIf")
    assert not script_value_key("Output")
    assert not script_value_key("NPCName")
    assert not script_value_key("Option_1")
    assert not script_value_key("")


def test_delegate_installs_completer_for_dialogue_scripts(qapp):
    """Le delegate de valeurs de l'editeur ECF branche le completer sur
    l'editeur d'une cle script quand des noms d'items sont fournis."""
    from PyQt6.QtWidgets import QComboBox, QTableWidget, QTableWidgetItem
    from gui.ecf_edit_widget import _PropertyValueDelegate

    table = QTableWidget(1, 2)
    node = object()  # noeud factice : seule la cle est lue par le delegate
    it0 = QTableWidgetItem("Execute_1")
    it0.setData(Qt.ItemDataRole.UserRole, (node, "Execute_1"))
    it1 = QTableWidgetItem("AddItem('Tok")
    it1.setData(Qt.ItemDataRole.UserRole, (node, "Execute_1"))
    table.setItem(0, 0, it0)
    table.setItem(0, 1, it1)
    index = table.model().index(0, 1)

    delegate = _PropertyValueDelegate({}, script_items=["Token", "FusionCell"])
    editor = delegate.createEditor(table, None, index)
    try:
        combo = editor if isinstance(editor, QComboBox) else editor.findChild(QComboBox)
        assert combo is not None
        assert _own_completer(combo.lineEdit()) is not None
    finally:
        editor.deleteLater()


def test_delegate_no_completer_for_plain_keys(qapp):
    from gui.ecf_edit_widget import _PropertyValueDelegate
    from PyQt6.QtWidgets import QComboBox, QTableWidget, QTableWidgetItem

    table = QTableWidget(1, 2)
    node = object()
    it0 = QTableWidgetItem("Output")
    it0.setData(Qt.ItemDataRole.UserRole, (node, "Output"))
    it1 = QTableWidgetItem("du texte")
    it1.setData(Qt.ItemDataRole.UserRole, (node, "Output"))
    table.setItem(0, 0, it0)
    table.setItem(0, 1, it1)
    index = table.model().index(0, 1)

    delegate = _PropertyValueDelegate({}, script_items=["Token"])
    editor = delegate.createEditor(table, None, index)
    try:
        combo = editor if isinstance(editor, QComboBox) else editor.findChild(QComboBox)
        assert _own_completer(combo.lineEdit()) is None
    finally:
        editor.deleteLater()
