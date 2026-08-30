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
ET ingredients (quantite editable) -- demande explicite de l'utilisateur
(session du 29/08/2026) : pouvoir modifier chaque Template cree
INDIVIDUELLEMENT (pas une valeur uniforme appliquee a tous, contrairement au
tableau de proprietes du bloc lui-meme).

Etendu le 30/08/2026 (demande explicite, apres constat que le Template de
base pre-rempli ne couvrait que CraftTime/Target) :
  - AJOUT d'une propriete scalaire via liste deroulante des noms observes
    sur les autres Templates du fichier (`property_pool`), PAS de saisie
    libre non guidee ;
  - VALEURS proposees en liste deroulante (editable) : celles reellement
    observees pour la propriete choisie, triees par frequence
    (`values_by_key`) -- y compris dans le tableau des proprietes existantes
    et pour les quantites d'ingredients (`common_quantities`) ;
  - SUPPRESSION de la propriete selectionnee (bouton dedie) et d'un
    ingredient (bouton dedie) : le Template de base etant pre-rempli avec
    TOUTES les proprietes des autres Templates, on doit pouvoir en retirer ;
    la liste deroulante est utilisee PARTOUT ou c'est possible.
"""
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QLineEdit,
)

from core.i18n import t


class TemplateRecipeEditor(QWidget):
    """`scalar_fields`/`ingredients` : etat de depart de CET onglet (copie du
    Template source ou valeurs les plus courantes du fichier).
    `craftable_names` : pool de la liste deroulante d'ajout d'ingredient.
    `property_pool` : noms de proprietes observes DANS LE FICHIER
    Templates.ecf (liste deroulante d'AJOUT de propriete scalaire, triee
    par frequence) -- JAMAIS d'autres fichiers (proprietes de blocs/items
    exclus, demande explicite du 30/08/2026). Vide quand le Template de
    base possede deja toutes les proprietes du fichier : le placeholder de
    la liste l'explique. `values_by_key` : {cle: valeurs observees triees
    par frequence} pour les listes deroulantes de valeurs SCALAIRES.
    `common_quantities` : quantites d'ingredients observees (liste
    deroulante des quantites du formulaire d'ajout). `ingredient_values_
    by_key` : quantites observees PER-INGREDIENT pour la colonne quantite.
    SEPARATION stricte (demande du 30/08/2026) : `values_by_key` ne contient
    JAMAIS de noms d'ingredients et les quantites ne contiennent JAMAIS de
    proprietes scalaires -- chaque section reste dans la sienne."""

    def __init__(self, scalar_fields: List[Tuple[str, str]], ingredients: List[Tuple[str, str]],
                 craftable_names: List[str], property_pool: Optional[List[str]] = None,
                 values_by_key: Optional[Dict[str, List[str]]] = None,
                 common_quantities: Optional[List[str]] = None,
                 ingredient_values_by_key: Optional[Dict[str, List[str]]] = None, parent=None):
        super().__init__(parent)
        self._original_scalars: Dict[str, str] = dict(scalar_fields)
        self._original_ingredients: Dict[str, str] = dict(ingredients)
        self._values_by_key: Dict[str, List[str]] = dict(values_by_key or {})
        self._ingredient_values_by_key: Dict[str, List[str]] = dict(ingredient_values_by_key or {})
        self._common_quantities: List[str] = list(common_quantities or [])

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(t("dup.template_scalar_fields_label")))

        # --- Tableau des proprietes scalaires (editable, supprimable) ---
        self.scalar_table = QTableWidget()
        self.scalar_table.setColumnCount(2)
        self.scalar_table.setHorizontalHeaderLabels(
            [t("dup.preview_col_property"), t("dup.preview_col_value")])
        self.scalar_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.scalar_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.scalar_table.verticalHeader().setVisible(False)
        self.scalar_table.setMaximumHeight(160)
        for key, value in scalar_fields:
            self._add_scalar_row(key, value)
        layout.addWidget(self.scalar_table)

        scalar_buttons = QHBoxLayout()
        btn_remove_scalar = QPushButton(t("dup.remove_property_btn"))
        btn_remove_scalar.clicked.connect(self._on_remove_scalar)
        scalar_buttons.addWidget(btn_remove_scalar)
        scalar_buttons.addStretch()
        layout.addLayout(scalar_buttons)

        # --- AJOUT d'une propriete : liste deroulante des noms observes dans
        # le FICHIER Templates.ecf uniquement (jamais les proprietes des
        # autres fichiers -- demande explicite du 30/08/2026) + liste
        # deroulante des valeurs courantes de la propriete choisie ---
        add_prop_row = QHBoxLayout()
        self.property_combo = QComboBox()
        self.property_combo.setEditable(True)  # recherche/filtre au clavier
        self._fill_property_combo(property_pool)
        add_prop_row.addWidget(self.property_combo, 2)
        self.new_value_combo = QComboBox()
        self.new_value_combo.setEditable(True)
        self.new_value_combo.setCurrentText("")
        add_prop_row.addWidget(self.new_value_combo, 3)
        btn_add_scalar = QPushButton(t("dup.add_property_btn"))
        btn_add_scalar.clicked.connect(self._on_add_scalar)
        add_prop_row.addWidget(btn_add_scalar)
        layout.addLayout(add_prop_row)
        # La liste des valeurs suit la propriete choisie (meme tapee a la main)
        self.property_combo.currentTextChanged.connect(self._refresh_new_value_combo)
        self._refresh_new_value_combo(self.property_combo.currentText())

        layout.addWidget(QLabel(t("dup.template_ingredients_label")))
        self.ingredients_table = QTableWidget()
        self.ingredients_table.setColumnCount(2)
        self.ingredients_table.setHorizontalHeaderLabels(
            [t("dup.preview_col_property"), t("dup.preview_col_value")])
        self.ingredients_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.ingredients_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.ingredients_table.verticalHeader().setVisible(False)
        self.ingredients_table.setMaximumHeight(140)
        for name, qty in ingredients:
            self._add_ingredient_row(name, qty)
        layout.addWidget(self.ingredients_table)

        add_row = QHBoxLayout()
        self.ingredient_combo = QComboBox()
        self.ingredient_combo.setEditable(True)  # recherche/filtre au clavier
        self.ingredient_combo.addItems(craftable_names)
        self.ingredient_combo.setCurrentText("")
        add_row.addWidget(self.ingredient_combo, 1)
        # Quantite en liste deroulante EDITABLE des quantites courantes
        # observees dans le fichier (demande du 30/08/2026 : liste deroulante
        # PARTOUT ou c'est possible), saisie libre toujours permise.
        self.quantity_combo = QComboBox()
        self.quantity_combo.setEditable(True)
        self.quantity_combo.addItems(list(common_quantities or []))
        self.quantity_combo.setCurrentText("1")
        self.quantity_combo.setMaximumWidth(90)
        add_row.addWidget(self.quantity_combo)
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

    def _fill_property_combo(self, property_pool: Optional[List[str]]) -> None:
        """Remplit la liste deroulante d'ajout avec les proprietes observees
        DANS LE FICHIER Templates.ecf (frequences decroissantes, voir
        scan_template_defaults), sans celles deja presentes dans le tableau.
        Pool vide = toutes les proprietes du fichier sont deja affichees sur
        ce Template : le placeholder l'explique explicitement (jamais une
        liste vide sans explication -- retour utilisateur du 30/08/2026)."""
        pool = list(property_pool) if property_pool else []
        pool_keys = [k for k in dict.fromkeys(pool) if k not in self._original_scalars]
        self.property_combo.clear()
        self.property_combo.addItems(pool_keys)
        self._refresh_property_combo_placeholder()

    def _refresh_property_combo_placeholder(self) -> None:
        if self.property_combo.count() > 0:
            self.property_combo.setPlaceholderText(t("dup.property_add_placeholder"))
        else:
            self.property_combo.setPlaceholderText(t("dup.property_add_empty"))

    # ------------------------------------------------------------ scalaires
    def _make_value_combo(self, key: str, current: str) -> QComboBox:
        """Combo EDITABLE pre-rempli avec les valeurs observees pour `key`
        (tri frequence) -- la saisie libre reste possible pour une valeur
        nouvelle ; si la cle est inconnue, la combo reste vide mais editable."""
        combo = QComboBox()
        combo.setEditable(True)
        combo.addItems(self._values_by_key.get(key, []))
        combo.setCurrentText(current)
        return combo

    def _add_scalar_row(self, key: str, value: str) -> None:
        row = self.scalar_table.rowCount()
        self.scalar_table.insertRow(row)
        name_item = QTableWidgetItem(key)
        name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.scalar_table.setItem(row, 0, name_item)
        self.scalar_table.setCellWidget(row, 1, self._make_value_combo(key, value))

    def _refresh_new_value_combo(self, key: str) -> None:
        """Repeuple la liste deroulante de valeurs de la ligne d'ajout avec
        les valeurs observees pour la propriete choisie (ne change PAS le
        texte deja tape -- editable, la liste ne fait que proposer)."""
        combo = self.new_value_combo
        text = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(self._values_by_key.get(key.strip(), []))
        combo.setCurrentText(text)
        combo.blockSignals(False)

    def _on_add_scalar(self) -> None:
        key = self.property_combo.currentText().strip()
        value = self.new_value_combo.currentText().strip()
        if not key or not value:
            return
        # Propriete DEJA presente : met a jour sa valeur au lieu de dupliquer
        # la ligne (meme principe que pour les ingredients).
        for row in range(self.scalar_table.rowCount()):
            if self.scalar_table.item(row, 0).text() == key:
                self.scalar_table.cellWidget(row, 1).setCurrentText(value)
                return
        self._add_scalar_row(key, value)
        self.property_combo.removeItem(self.property_combo.findText(key))
        self.property_combo.setCurrentText("")
        self._refresh_property_combo_placeholder()
        self.new_value_combo.setCurrentText("")

    def _on_remove_scalar(self) -> None:
        row = self.scalar_table.currentRow()
        if row >= 0:
            key = self.scalar_table.item(row, 0).text()
            self.scalar_table.removeRow(row)
            # La propriete retiree retourne dans la liste d'ajout (elle
            # existe dans le fichier : on doit pouvoir revenir en arriere).
            if self.property_combo.findText(key) < 0:
                self.property_combo.addItem(key)
            self.property_combo.setCurrentText("")
            self._refresh_property_combo_placeholder()

    # ----------------------------------------------------------- ingredients
    def _add_ingredient_row(self, name: str, qty: str) -> None:
        row = self.ingredients_table.rowCount()
        self.ingredients_table.insertRow(row)
        name_item = QTableWidgetItem(name)
        name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.ingredients_table.setItem(row, 0, name_item)
        # Liste deroulante des quantites observees pour CET ingredient
        # (ingredient_values_by_key), en repli les quantites courantes
        # globales -- jamais les valeurs des proprietes scalaires du
        # Template : le contenu Child Inputs reste dans SA section
        # (separation demandee par l'utilisateur le 30/08/2026).
        combo = QComboBox()
        combo.setEditable(True)
        combo.addItems(self._ingredient_values_by_key.get(name) or self._common_quantities)
        combo.setCurrentText(qty)
        self.ingredients_table.setCellWidget(row, 1, combo)

    def _on_add_ingredient(self) -> None:
        name = self.ingredient_combo.currentText().strip()
        qty = self.quantity_combo.currentText().strip()
        if not name or not qty:
            return
        for row in range(self.ingredients_table.rowCount()):
            if self.ingredients_table.item(row, 0).text() == name:
                self.ingredients_table.cellWidget(row, 1).setCurrentText(qty)
                return
        self._add_ingredient_row(name, qty)
        self.quantity_combo.setCurrentText("1")
        self.ingredient_combo.setCurrentText("")

    def _on_remove_ingredient(self) -> None:
        row = self.ingredients_table.currentRow()
        if row >= 0:
            self.ingredients_table.removeRow(row)

    # -------------------------------------------------------------- resultats
    def get_scalar_overrides(self) -> Dict[str, str]:
        """Valeurs MODIFIEES des proprietes d'origine PLUS toute propriete
        AJOUTEE (jamais presente a l'origine, donc toujours incluse) -- les
        lignes retirees ne sont PAS ici, voir get_removed_scalars."""
        result: Dict[str, str] = {}
        for row in range(self.scalar_table.rowCount()):
            key = self.scalar_table.item(row, 0).text()
            value = self.scalar_table.cellWidget(row, 1).currentText()
            if key not in self._original_scalars or value != self._original_scalars[key]:
                result[key] = value
        return result

    def get_removed_scalars(self) -> List[str]:
        """Proprietes SCALAIRES d'ORIGINE dont la ligne a ete retiree par
        l'utilisateur (les ajoutees ne peuvent pas etre 'retirees' ici :
        elles n'existeraient que si elles sont encore affichees)."""
        remaining = {self.scalar_table.item(r, 0).text()
                     for r in range(self.scalar_table.rowCount())}
        return [key for key in self._original_scalars if key not in remaining]

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
            qty = self.ingredients_table.cellWidget(row, 1).currentText()
            if name not in self._original_ingredients or qty != self._original_ingredients[name]:
                result[name] = qty
        return result
