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

"""Palette de l'assistant (Ctrl+K) : taper une question, Entree.

Le catalogue d'actions par surface viendra s'ajouter ici (chaque entree
porte son identifiant en UserRole) : la palette ne fait que CHOISIR, c'est
la fenetre d'assistant qui execute.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QLineEdit, QListWidget,
                             QListWidgetItem, QVBoxLayout)

from core.i18n import t


class AssistantPalette(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("assistant.palette_title"))
        self.setMinimumWidth(560)
        self._kind = ""
        self._text = ""

        layout = QVBoxLayout(self)
        self.line = QLineEdit()
        self.line.setPlaceholderText(t("assistant.palette_placeholder"))
        self.line.returnPressed.connect(self._accept)
        layout.addWidget(self.line)

        self.choices = QListWidget()
        item = QListWidgetItem(t("assistant.palette_ask"))
        item.setData(Qt.ItemDataRole.UserRole, "ask")
        self.choices.addItem(item)
        self.choices.setCurrentRow(0)
        self.choices.itemActivated.connect(lambda _item: self._accept())
        layout.addWidget(self.choices, 1)

    def _accept(self) -> None:
        item = self.choices.currentItem()
        self._kind = item.data(Qt.ItemDataRole.UserRole) if item else "ask"
        self._text = self.line.text().strip()
        self.accept()

    def choice(self) -> tuple:
        return self._kind, self._text
