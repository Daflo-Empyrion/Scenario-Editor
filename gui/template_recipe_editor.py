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
Editeur d'UN Template individuel -- champs scalaires (CraftTime, Target...)
ET ingredients (quantite editable + AJOUT d'un nouvel ingredient via liste
deroulante de blocs/items valides) -- demande explicite de l'utilisateur
(session du 29/08/2026) : pouvoir modifier chaque Template cree
INDIVIDUELLEMENT (pas une valeur uniforme appliquee a tous, contrairement au
tableau de proprietes du bloc lui-meme), et pouvoir AJOUTER un nouvel
ingredient a la recette, pas seulement ajuster la quantite d'un existant."""
from typing import Dict, List, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QLineEdit,
)

from core.i18n import t
from gui.property_edit_table import PropertyEditTable


class TemplateRecipeEditor(QWidget):
    def __init__(self, scalar_fields: List[Tuple[str, str]], ingredients: List[Tuple[str, str]],
                 craftable_names: List[str], parent=None):
        super().__init__(parent)
        self._original_ingredients: Dict[str, str] = dict(ingredients)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(t("dup.template_scalar_fields_label")))
        self.scalar_table = PropertyEditTable(scalar_fields)
        self.scalar_table.setMaximumHeight(120)
        layout.addWidget(self.scalar_table)

        layout.addWidget(QLabel(t("dup.template_ingredients_label")))
        self.ingredients_table = QTableWidget()
        self.ingredients_table.setColumnCount(2)
        self.ingredients_table.setHorizontalHeaderLabels(
            [t("dup.preview_col_property"), t("dup.preview_col_value")])
        self.ingredients_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.ingredients_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.ingredients_table.verticalHeader().setVisible(False)
        self.ingredients_table.setMaximumHeight(140)
        self.ingredients_table.setRowCount(len(ingredients))
        for row, (name, qty) in enumerate(ingredients):
            name_item = QTableWidgetItem(name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.ingredients_table.setItem(row, 0, name_item)
            self.ingredients_table.setItem(row, 1, QTableWidgetItem(qty))
        layout.addWidget(self.ingredients_table)

        add_row = QHBoxLayout()
        self.ingredient_combo = QComboBox()
        self.ingredient_combo.setEditable(True)  # recherche/filtre au clavier
        self.ingredient_combo.addItems(craftable_names)
        self.ingredient_combo.setCurrentText("")
        add_row.addWidget(self.ingredient_combo, 1)
        self.quantity_edit = QLineEdit("1")
        self.quantity_edit.setMaximumWidth(60)
        add_row.addWidget(self.quantity_edit)
        btn_add = QPushButton(t("dup.add_ingredient_btn"))
        btn_add.clicked.connect(self._on_add_ingredient)
        add_row.addWidget(btn_add)
        # Retirer l'ingredient selectionne -- demande explicite de
        # l'utilisateur du 30/08/2026 : AJOUTER ET SUPPRIMER des ingredients
        # dans tous les modes (creation, duplication, fusion).
        btn_remove = QPushButton(t("dup.remove_ingredient_btn"))
        btn_remove.clicked.connect(self._on_remove_ingredient)
        add_row.addWidget(btn_remove)
        layout.addLayout(add_row)

    def _on_add_ingredient(self) -> None:
        name = self.ingredient_combo.currentText().strip()
        qty = self.quantity_edit.text().strip()
        if not name or not qty:
            return
        for row in range(self.ingredients_table.rowCount()):
            if self.ingredients_table.item(row, 0).text() == name:
                self.ingredients_table.item(row, 1).setText(qty)
                return
        row = self.ingredients_table.rowCount()
        self.ingredients_table.insertRow(row)
        name_item = QTableWidgetItem(name)
        name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.ingredients_table.setItem(row, 0, name_item)
        self.ingredients_table.setItem(row, 1, QTableWidgetItem(qty))
        self.quantity_edit.setText("1")
        self.ingredient_combo.setCurrentText("")

    def _on_remove_ingredient(self) -> None:
        row = self.ingredients_table.currentRow()
        if row >= 0:
            self.ingredients_table.removeRow(row)

    def get_scalar_overrides(self) -> Dict[str, str]:
        return self.scalar_table.get_changed_values()

    def get_removed_ingredients(self) -> List[str]:
        """Ingredients d'ORIGINE dont la ligne a ete retiree par
        l'utilisateur (les ajoutes ne peuvent pas etre 'retires' ici : ils
        n'existeraient que s'ils sont encore affiches)."""
        remaining = {self.ingredients_table.item(r, 0).text()
                     for r in range(self.ingredients_table.rowCount())}
        return [name for name in self._original_ingredients if name not in remaining]

    def get_changed_or_added_ingredients(self) -> Dict[str, str]:
        """Ingredients dont la quantite differe de l'original, PLUS tout
        ingredient AJOUTE (jamais present a l'origine, donc sans 'valeur
        d'origine' a comparer -- toujours inclus)."""
        result: Dict[str, str] = {}
        for row in range(self.ingredients_table.rowCount()):
            name = self.ingredients_table.item(row, 0).text()
            qty = self.ingredients_table.item(row, 1).text()
            if name not in self._original_ingredients or qty != self._original_ingredients[name]:
                result[name] = qty
        return result
