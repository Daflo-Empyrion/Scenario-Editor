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
Creation guidee d'un nouveau bloc/item, avec suggestion des proprietes
issues du fichier de travail lui-meme (voir core/ecf/block_creation.py) et,
pour les Templates, des ingredients de craft (Child Inputs) via liste
deroulante plutot que saisie libre.

Flux : choix Id+Name / Name seul -> tableau des proprietes (case a cocher +
valeur editable, triees par frequence d'usage reelle dans le fichier) ->
creation -> proposition de creer le Template associe (si le fichier courant
n'est pas deja Templates.ecf) -> meme tableau, avec Name pre-rempli et une
section Ingredients en plus.
"""
from typing import List, Optional, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QCheckBox, QMessageBox, QHeaderView, QRadioButton,
    QButtonGroup, QWidget,
)

from core.i18n import t
from core.ecf.block_creation import scan_kind_frequency, scan_properties_for_kind
from core.ecf.validation import MAX_BLOCK_ID


class IdentityModeDialog(QDialog):
    """Premiere etape : Id+Name ou Name seul -- certains blocs (ex:
    LegacyForcefield) n'ont volontairement pas d'Id, confirme sur de vrais
    fichiers du jeu."""

    MODE_ID_AND_NAME = "id_and_name"
    MODE_NAME_ONLY = "name_only"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("addblock.identity_title"))
        self.chosen_mode: Optional[str] = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(t("addblock.identity_intro")))

        self.group = QButtonGroup(self)
        self.radio_id_name = QRadioButton(t("addblock.identity_id_and_name"))
        self.radio_id_name.setChecked(True)
        self.group.addButton(self.radio_id_name)
        layout.addWidget(self.radio_id_name)

        self.radio_name_only = QRadioButton(t("addblock.identity_name_only"))
        self.group.addButton(self.radio_name_only)
        layout.addWidget(self.radio_name_only)

        buttons = QHBoxLayout()
        buttons.addStretch()
        btn_cancel = QPushButton(t("btn.cancel"))
        btn_cancel.setObjectName("secondaryButton")
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_cancel)
        btn_next = QPushButton(t("addblock.btn_next"))
        btn_next.setObjectName("primaryButton")
        btn_next.clicked.connect(self._on_next)
        buttons.addWidget(btn_next)
        layout.addLayout(buttons)

    def _on_next(self):
        self.chosen_mode = (self.MODE_ID_AND_NAME if self.radio_id_name.isChecked()
                             else self.MODE_NAME_ONLY)
        self.accept()


class PropertyTableDialog(QDialog):
    """Deuxieme etape (et reutilisee telle quelle pour le Template) : genre,
    Id/Name, tableau des proprietes cochables issues du fichier de travail, et
    optionnellement une section Ingredients (Child Inputs, uniquement pour la
    creation d'un Template)."""

    def __init__(self, doc, id_mode: str, existing_ids: set, default_kind: str = "",
                 name_prefill: str = "", name_readonly: bool = False,
                 enable_ingredients: bool = False, craftable_names: Optional[List[str]] = None,
                 window_title_key: str = "addblock.table_title", parent=None):
        super().__init__(parent)
        self.doc = doc
        self.id_mode = id_mode
        self.existing_ids = existing_ids
        self.craftable_names = craftable_names or []
        self._properties_by_key = {}
        self._all_rows: List[Tuple[QCheckBox, str, QTableWidgetItem]] = []

        self.result_kind: Optional[str] = None
        self.result_id: Optional[str] = None
        self.result_name: Optional[str] = None
        self.result_properties: List[Tuple[str, str]] = []
        self.result_ingredients: List[Tuple[str, str]] = []

        self.setWindowTitle(t(window_title_key))
        self.setMinimumSize(760, 620)
        layout = QVBoxLayout(self)

        # --- Genre, Id, Name ---
        top_form = QHBoxLayout()
        top_form.addWidget(QLabel(t("addblock.kind_label")))
        self.combo_kind = QComboBox()
        self.combo_kind.setEditable(True)
        kind_counts = scan_kind_frequency(doc)
        sorted_kinds = [k for k, _ in kind_counts.most_common()]
        self.combo_kind.addItems(sorted_kinds)
        if default_kind and default_kind in sorted_kinds:
            self.combo_kind.setCurrentText(default_kind)
        elif default_kind:
            self.combo_kind.setCurrentText(default_kind)
        self.combo_kind.currentTextChanged.connect(self._on_kind_changed)
        top_form.addWidget(self.combo_kind, 1)
        layout.addLayout(top_form)

        id_name_row = QHBoxLayout()
        self.edit_id = QLineEdit()
        self.edit_id.setPlaceholderText(t("addblock.id_placeholder", max=MAX_BLOCK_ID))
        if id_mode == IdentityModeDialog.MODE_ID_AND_NAME:
            id_name_row.addWidget(QLabel(t("ecf.id_label")))
            id_name_row.addWidget(self.edit_id)
        self.edit_name = QLineEdit(name_prefill)
        self.edit_name.setReadOnly(name_readonly)
        id_name_row.addWidget(QLabel(t("addblock.name_label")))
        id_name_row.addWidget(self.edit_name)
        layout.addLayout(id_name_row)

        self.id_warning_label = QLabel("")
        self.id_warning_label.setStyleSheet("color: #cc3333;")
        layout.addWidget(self.id_warning_label)
        self.edit_id.textChanged.connect(self._validate_id_live)

        # --- Filtre + tableau des proprietes ---
        layout.addWidget(QLabel(t("addblock.properties_label")))
        filter_row = QHBoxLayout()
        self.edit_filter = QLineEdit()
        self.edit_filter.setPlaceholderText(t("addblock.filter_placeholder"))
        self.edit_filter.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self.edit_filter)
        layout.addLayout(filter_row)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(
            ["", t("addblock.col_property"), t("addblock.col_value")])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

        # --- Ingredients (Template uniquement) ---
        self.ingredients_table = None
        if enable_ingredients:
            layout.addWidget(QLabel(t("addblock.ingredients_label")))
            self.ingredients_table = QTableWidget(0, 2)
            self.ingredients_table.setHorizontalHeaderLabels(
                [t("addblock.col_ingredient"), t("addblock.col_quantity")])
            self.ingredients_table.horizontalHeader().setSectionResizeMode(
                0, QHeaderView.ResizeMode.Stretch)
            layout.addWidget(self.ingredients_table)

            ing_buttons = QHBoxLayout()
            btn_add_ingredient = QPushButton(t("addblock.btn_add_ingredient"))
            btn_add_ingredient.clicked.connect(self._add_ingredient_row)
            ing_buttons.addWidget(btn_add_ingredient)
            btn_remove_ingredient = QPushButton(t("addblock.btn_remove_ingredient"))
            btn_remove_ingredient.clicked.connect(self._remove_ingredient_row)
            ing_buttons.addWidget(btn_remove_ingredient)
            ing_buttons.addStretch()
            layout.addLayout(ing_buttons)

        # --- Boutons ---
        buttons = QHBoxLayout()
        buttons.addStretch()
        btn_cancel = QPushButton(t("btn.cancel"))
        btn_cancel.setObjectName("secondaryButton")
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_cancel)
        btn_validate = QPushButton(t("addblock.btn_validate"))
        btn_validate.setObjectName("primaryButton")
        btn_validate.clicked.connect(self._on_validate)
        buttons.addWidget(btn_validate)
        layout.addLayout(buttons)

        self._on_kind_changed(self.combo_kind.currentText())

    def _on_kind_changed(self, kind: str):
        self._properties_by_key = scan_properties_for_kind(self.doc, kind)
        self._populate_table()

    def _populate_table(self):
        self.table.setRowCount(0)
        self._all_rows = []
        sorted_keys = sorted(self._properties_by_key.keys(),
                              key=lambda k: -sum(self._properties_by_key[k].values()))
        for key in sorted_keys:
            row = self.table.rowCount()
            self.table.insertRow(row)
            checkbox = QCheckBox()
            cell_widget = QWidget()
            cell_layout = QHBoxLayout(cell_widget)
            cell_layout.addWidget(checkbox)
            cell_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 0, cell_widget)

            key_item = QTableWidgetItem(key)
            key_item.setFlags(key_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 1, key_item)

            # Menu deroulant EDITABLE (pas juste la valeur la plus frequente en
            # texte libre) -- propose toutes les valeurs reellement observees
            # pour cette propriete dans le fichier de travail, triees par
            # frequence, tout en restant modifiable si aucune ne convient.
            value_combo = QComboBox()
            value_combo.setEditable(True)
            counter = self._properties_by_key[key]
            distinct_values = [v for v, _ in counter.most_common()]
            value_combo.addItems(distinct_values)
            if distinct_values:
                value_combo.setCurrentText(distinct_values[0])
            self.table.setCellWidget(row, 2, value_combo)

            self._all_rows.append((checkbox, key, value_combo))
        self.table.resizeColumnsToContents()

    def _apply_filter(self, text: str):
        text_lower = text.strip().lower()
        for row, (_, key, _) in enumerate(self._all_rows):
            self.table.setRowHidden(row, text_lower not in key.lower())

    def _add_ingredient_row(self):
        row = self.ingredients_table.rowCount()
        self.ingredients_table.insertRow(row)
        combo = QComboBox()
        combo.setEditable(True)
        combo.addItems(self.craftable_names)
        self.ingredients_table.setCellWidget(row, 0, combo)
        self.ingredients_table.setItem(row, 1, QTableWidgetItem("1"))

    def _remove_ingredient_row(self):
        row = self.ingredients_table.currentRow()
        if row >= 0:
            self.ingredients_table.removeRow(row)

    def _validate_id_live(self, text: str):
        text = text.strip()
        if not text:
            self.id_warning_label.setText("")
            return
        try:
            id_num = int(text)
        except ValueError:
            self.id_warning_label.setText(t("addblock.id_not_numeric"))
            return
        if id_num >= MAX_BLOCK_ID:
            self.id_warning_label.setText(t("addblock.id_too_high", max=MAX_BLOCK_ID))
            return
        if text in self.existing_ids:
            self.id_warning_label.setText(t("addblock.id_duplicate"))
            return
        self.id_warning_label.setText("")

    def _on_validate(self):
        kind = self.combo_kind.currentText().strip()
        id_text = self.edit_id.text().strip()
        name_text = self.edit_name.text().strip()

        if not kind:
            QMessageBox.warning(self, t("addblock.table_title"), t("addblock.err_kind_required"))
            return

        if self.id_mode == IdentityModeDialog.MODE_ID_AND_NAME:
            if not id_text:
                QMessageBox.warning(self, t("addblock.table_title"), t("addblock.err_id_required"))
                return
            try:
                id_num = int(id_text)
            except ValueError:
                QMessageBox.warning(self, t("addblock.table_title"), t("addblock.id_not_numeric"))
                return
            if id_num >= MAX_BLOCK_ID:
                QMessageBox.warning(self, t("addblock.table_title"), t("addblock.id_too_high", max=MAX_BLOCK_ID))
                return
            if id_text in self.existing_ids:
                QMessageBox.warning(self, t("addblock.table_title"), t("addblock.id_duplicate"))
                return

        if not name_text:
            QMessageBox.warning(self, t("addblock.table_title"), t("addblock.err_name_required"))
            return

        properties = []
        for row, (checkbox, key, value_combo) in enumerate(self._all_rows):
            if checkbox.isChecked():
                properties.append((key, value_combo.currentText()))

        ingredients = []
        if self.ingredients_table is not None:
            for row in range(self.ingredients_table.rowCount()):
                combo = self.ingredients_table.cellWidget(row, 0)
                qty_item = self.ingredients_table.item(row, 1)
                ing_name = combo.currentText().strip() if combo else ""
                qty = qty_item.text().strip() if qty_item else ""
                if ing_name and qty:
                    ingredients.append((ing_name, qty))

        self.result_kind = kind
        self.result_id = id_text if self.id_mode == IdentityModeDialog.MODE_ID_AND_NAME else None
        self.result_name = name_text or None
        self.result_properties = properties
        self.result_ingredients = ingredients
        self.accept()
