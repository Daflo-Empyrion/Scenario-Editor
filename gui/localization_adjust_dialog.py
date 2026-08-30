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
Dialogue d'ajustement du nom AFFICHE (Localization.csv) du/des bloc(s)/item(s)
nouvellement duplique(s) -- demande explicite de l'utilisateur (session du
29/08/2026) : le nom technique (Name) d'un duplicata n'a, par definition,
JAMAIS d'entree dans Localization.csv -- sans cette etape, le nouveau bloc
s'affiche en jeu avec sa cle technique brute plutot qu'un titre lisible.

CONTRAIREMENT au tableau d'ajustement des proprietes du bloc/Template (voir
gui/property_edit_table.py, applique UNIFORMEMENT a toutes les variantes),
CHAQUE variante a ICI SA PROPRE ligne editable -- un nom affiche identique
pour TeleporterBAT1 et TeleporterBAT2 serait trompeur, contrairement a par
exemple partager le meme Material.

Pre-rempli avec la traduction du bloc SOURCE (bonne base de depart : la
plupart du temps, seul un suffixe change), jamais ecrit tel quel sans
validation explicite de l'utilisateur (bouton Appliquer)."""
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
)

from core.i18n import t


class LocalizationAdjustDialog(QDialog):
    """`new_names` : noms techniques (Name) des blocs/items nouvellement
    crees. `source_translations` : (français, anglais) du bloc SOURCE,
    utilise comme valeur de depart pre-remplie pour CHAQUE ligne."""

    def __init__(self, new_names: List[str], source_translations: "tuple[str, str]", parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("dup.adjust_localization_title"))
        self.setMinimumWidth(560)
        self._new_names = new_names
        source_fr, source_en = source_translations

        layout = QVBoxLayout(self)
        hint = QLabel(t("dup.adjust_localization_hint"))
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels([
            t("dup.preview_col_property"), t("dup.loc_col_french"), t("dup.loc_col_english")])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setRowCount(len(new_names))
        for row, name in enumerate(new_names):
            name_item = QTableWidgetItem(name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(source_fr))
            self.table.setItem(row, 2, QTableWidgetItem(source_en))
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        btn_ok = QPushButton(t("transform.btn_apply"))
        btn_ok.clicked.connect(self.accept)
        buttons.addWidget(btn_ok)
        btn_cancel = QPushButton(t("btn.cancel"))
        btn_cancel.setObjectName("secondaryButton")
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_cancel)
        layout.addLayout(buttons)

    def get_entries(self) -> Dict[str, Dict[str, str]]:
        """Retourne {nom_technique: {'Français': ..., 'English': ...}} --
        UNIQUEMENT pour les lignes ou au moins une des deux traductions
        n'est pas vide (une ligne totalement videe par l'utilisateur est
        consideree comme 'je ne veux pas d'entree pour celle-ci')."""
        entries: Dict[str, Dict[str, str]] = {}
        for row, name in enumerate(self._new_names):
            fr = self.table.item(row, 1).text() if self.table.item(row, 1) else ""
            en = self.table.item(row, 2).text() if self.table.item(row, 2) else ""
            if fr.strip() or en.strip():
                entries[name] = {"Français": fr, "English": en}
        return entries
