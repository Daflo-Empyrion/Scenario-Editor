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

"""
Completion des Ids d'items DANS les scripts de dialogue (v1.9.0, voir
core/dialogue_items.py) : QCompleter a prefixe manuel recalcule depuis la
position du curseur -- QCompleter ne sait pas nativement completer au
MILIEU d'un texte, la recette standard est de reposer setCompletionPrefix
sur le token courant (entre les apostrophes de AddItem/RemoveItem/HasItem)
a chaque frappe ; a la selection, QCompleter remplace lui-meme le prefixe
saisi a la position du curseur.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCompleter, QLineEdit

from core.dialogue_items import quoted_item_token


def install_script_item_completer(line_edit: QLineEdit, item_names) -> QCompleter:
    """Branche la completion des Ids d'items sur l'editeur (QLineEdit du
    combo de valeurs). Retourne le QCompleter (parente au line edit : sa
    duree de vie suit celle de l'editeur)."""
    completer = QCompleter(sorted(item_names), line_edit)
    # Tag pour les tests / le debogage : distingue notre completer du
    # completer interne du QComboBox editable.
    completer.setObjectName("dialogue_item_completer")
    completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
    completer.setFilterMode(Qt.MatchFlag.MatchContains)
    completer.setWidget(line_edit)

    def _update():
        token = quoted_item_token(line_edit.text(), line_edit.cursorPosition())
        if not token:
            completer.popup().hide()
            return
        completer.setCompletionPrefix(token)
        completer.complete()

    line_edit.textEdited.connect(_update)
    line_edit.cursorPositionChanged.connect(_update)
    return completer
