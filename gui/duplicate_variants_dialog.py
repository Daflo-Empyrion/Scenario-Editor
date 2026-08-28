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
Dialogue de duplication -- soit une copie unique (comme le dialogue
historique gui.main_window.DuplicateBlockDialog), soit plusieurs variantes
nommees automatiquement {Nom}T1, {Nom}T2 ... {Nom}TN avec une variation en
pourcentage sur des champs numeriques choisis (voir core/ecf/variants.py).

Reutilisable dans deux contextes :
- Duplication d'un bloc ECF entier (Id + Name en mode simple).
- Duplication d'une ligne de structure repetitive en mode tableau (pas
  d'Id, juste un nom -- via `show_id_field=False`).
"""
from typing import List, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QCheckBox,
    QPushButton, QSpinBox, QDoubleSpinBox, QListWidget, QListWidgetItem,
    QMessageBox, QWidget,
)
from PyQt6.QtCore import Qt

from core.i18n import t


class DuplicateVariantsDialog(QDialog):
    """Voir le docstring du module. `current_id`/`current_name` decrivent
    l'element source (Id optionnel). `id_suggestions` (mode simple
    uniquement) : Ids libres suggeres. `numeric_fields` : champs
    detectes automatiquement comme candidats a la variation (voir
    core.ecf.variants.detect_numeric_fields_block/_row) -- pre-remplissent
    la liste a cocher, l'utilisateur peut en ajouter d'autres manuellement.
    `show_id_field` : False pour une ligne de mode tableau (pas d'Id)."""

    def __init__(self, current_id: Optional[str], current_name: Optional[str],
                 id_suggestions: List[str], numeric_fields: List[str],
                 parent=None, show_id_field: bool = True):
        super().__init__(parent)
        self.setWindowTitle(t("dup.title"))
        self.setMinimumWidth(480)
        self._current_id = current_id
        self._current_name = current_name

        layout = QVBoxLayout(self)
        none_placeholder = t("dup.none_placeholder")
        if show_id_field:
            header_text = t("dup.current_block", id=current_id or none_placeholder,
                             name=current_name or none_placeholder)
        else:
            header_text = t("dup.current_row", name=current_name or none_placeholder)
        layout.addWidget(QLabel(header_text))

        self.multi_checkbox = QCheckBox(t("dup.multi_variant_toggle"))
        layout.addWidget(self.multi_checkbox)

        # ---------------- Mode simple (une seule copie) ----------------
        self.simple_group = QWidget()
        simple_layout = QVBoxLayout(self.simple_group)
        simple_layout.setContentsMargins(0, 6, 0, 0)

        self.id_edit = None
        if show_id_field:
            id_row = QHBoxLayout()
            id_row.addWidget(QLabel(t("dup.new_id")))
            self.id_edit = QLineEdit(str(id_suggestions[0]) if current_id and id_suggestions else "")
            id_row.addWidget(self.id_edit)
            simple_layout.addLayout(id_row)
            if id_suggestions:
                sugg_label = QLabel(t("dup.suggestions_label", ids=', '.join(str(s) for s in id_suggestions)))
                sugg_label.setStyleSheet("color: gray; font-size: 11px;")
                simple_layout.addWidget(sugg_label)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel(t("dup.new_name") if show_id_field else t("dup.new_row_name")))
        self.name_edit = QLineEdit(current_name or "")
        name_row.addWidget(self.name_edit)
        simple_layout.addLayout(name_row)

        self.remove_id_checkbox = None
        if show_id_field and current_id:
            self.remove_id_checkbox = QCheckBox(t("dup.remove_id"))
            simple_layout.addWidget(self.remove_id_checkbox)

        # ---- Variation en pourcentage (optionnelle) sur la copie unique ----
        self.simple_percent_checkbox = QCheckBox(t("dup.simple_percent_toggle"))
        simple_layout.addWidget(self.simple_percent_checkbox)

        self.simple_percent_group = QWidget()
        simple_percent_layout = QVBoxLayout(self.simple_percent_group)
        simple_percent_layout.setContentsMargins(0, 4, 0, 0)

        simple_percent_row = QHBoxLayout()
        simple_percent_row.addWidget(QLabel(t("dup.simple_percent_label")))
        self.simple_percent_spin = QDoubleSpinBox()
        self.simple_percent_spin.setRange(-500.0, 500.0)
        self.simple_percent_spin.setValue(20.0)
        self.simple_percent_spin.setSuffix(" %")
        simple_percent_row.addWidget(self.simple_percent_spin)
        simple_percent_layout.addLayout(simple_percent_row)

        simple_percent_layout.addWidget(QLabel(t("dup.fields_to_vary")))
        self.simple_fields_list = QListWidget()
        self.simple_fields_list.setMaximumHeight(120)
        for field_name in numeric_fields:
            item = QListWidgetItem(field_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.simple_fields_list.addItem(item)
        simple_percent_layout.addWidget(self.simple_fields_list)

        simple_manual_row = QHBoxLayout()
        self.simple_manual_field_edit = QLineEdit()
        self.simple_manual_field_edit.setPlaceholderText(t("dup.manual_field_placeholder"))
        simple_manual_row.addWidget(self.simple_manual_field_edit)
        simple_add_field_btn = QPushButton(t("dup.add_field_btn"))
        simple_add_field_btn.clicked.connect(self._add_manual_field_simple)
        simple_manual_row.addWidget(simple_add_field_btn)
        simple_percent_layout.addLayout(simple_manual_row)

        simple_layout.addWidget(self.simple_percent_group)
        self.simple_percent_group.setVisible(False)
        self.simple_percent_checkbox.toggled.connect(self.simple_percent_group.setVisible)

        layout.addWidget(self.simple_group)

        # ---------------- Mode multi-variantes ----------------
        self.multi_group = QWidget()
        multi_layout = QVBoxLayout(self.multi_group)
        multi_layout.setContentsMargins(0, 6, 0, 0)

        count_row = QHBoxLayout()
        count_row.addWidget(QLabel(t("dup.variant_count")))
        self.count_spin = QSpinBox()
        self.count_spin.setRange(2, 50)
        self.count_spin.setValue(3)
        self.count_spin.valueChanged.connect(self._update_naming_hint)
        count_row.addWidget(self.count_spin)
        multi_layout.addLayout(count_row)

        self.naming_hint = QLabel()
        self.naming_hint.setStyleSheet("color: gray; font-size: 11px;")
        multi_layout.addWidget(self.naming_hint)
        self._update_naming_hint()

        self.first_original_checkbox = QCheckBox(t("dup.first_is_original"))
        self.first_original_checkbox.setChecked(True)
        multi_layout.addWidget(self.first_original_checkbox)

        percent_row = QHBoxLayout()
        percent_row.addWidget(QLabel(t("dup.total_percent")))
        self.percent_spin = QDoubleSpinBox()
        self.percent_spin.setRange(-500.0, 500.0)
        self.percent_spin.setValue(20.0)
        self.percent_spin.setSuffix(" %")
        percent_row.addWidget(self.percent_spin)
        multi_layout.addLayout(percent_row)

        multi_layout.addWidget(QLabel(t("dup.fields_to_vary")))
        self.fields_list = QListWidget()
        self.fields_list.setMaximumHeight(120)
        for field_name in numeric_fields:
            item = QListWidgetItem(field_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.fields_list.addItem(item)
        multi_layout.addWidget(self.fields_list)

        manual_row = QHBoxLayout()
        self.manual_field_edit = QLineEdit()
        self.manual_field_edit.setPlaceholderText(t("dup.manual_field_placeholder"))
        manual_row.addWidget(self.manual_field_edit)
        add_field_btn = QPushButton(t("dup.add_field_btn"))
        add_field_btn.clicked.connect(self._add_manual_field)
        manual_row.addWidget(add_field_btn)
        multi_layout.addLayout(manual_row)

        layout.addWidget(self.multi_group)
        self.multi_group.setVisible(False)
        self.multi_checkbox.toggled.connect(self._on_mode_toggled)

        buttons = QHBoxLayout()
        btn_ok = QPushButton(t("dup.duplicate"))
        btn_ok.clicked.connect(self._on_accept)
        buttons.addWidget(btn_ok)
        btn_cancel = QPushButton(t("btn.cancel"))
        btn_cancel.setObjectName("secondaryButton")
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_cancel)
        layout.addLayout(buttons)

        # Resultats -- mode simple (compat avec l'ancien DuplicateBlockDialog)
        self.result_new_id: Optional[str] = None
        self.result_new_name: Optional[str] = None
        self.result_remove_id: bool = False
        # Resultats -- variation en pourcentage optionnelle du mode simple
        # (None/vide si la case "dup.simple_percent_toggle" n'est pas cochee)
        self.result_simple_percent: Optional[float] = None
        self.result_simple_fields: List[str] = []
        # Resultat -- mode multi-variantes (None si mode simple choisi)
        self.result_multi: Optional[dict] = None

    def _update_naming_hint(self):
        base = self._current_name or "Nom"
        count = self.count_spin.value()
        shown = min(count, 3)
        names = ", ".join(f"{base}T{i + 1}" for i in range(shown))
        if count > shown:
            names += ", ..."
        self.naming_hint.setText(names)

    def _on_mode_toggled(self, checked: bool):
        self.simple_group.setVisible(not checked)
        self.multi_group.setVisible(checked)

    @staticmethod
    def _add_manual_field_to(list_widget: QListWidget, line_edit: QLineEdit):
        """Ajoute (ou coche si deja present) le champ tape manuellement
        dans `list_widget` -- factorise entre la liste du mode simple et
        celle du mode multi-variantes, qui partagent la meme logique."""
        name = line_edit.text().strip()
        if not name:
            return
        for i in range(list_widget.count()):
            if list_widget.item(i).text() == name:
                list_widget.item(i).setCheckState(Qt.CheckState.Checked)
                line_edit.clear()
                return
        item = QListWidgetItem(name)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked)
        list_widget.addItem(item)
        line_edit.clear()

    def _add_manual_field(self):
        self._add_manual_field_to(self.fields_list, self.manual_field_edit)

    def _add_manual_field_simple(self):
        self._add_manual_field_to(self.simple_fields_list, self.simple_manual_field_edit)

    def _on_accept(self):
        if self.multi_checkbox.isChecked():
            if not self._current_name:
                QMessageBox.warning(self, t("dup.name_required"), t("dup.name_required_msg"))
                return
            fields = [self.fields_list.item(i).text() for i in range(self.fields_list.count())
                      if self.fields_list.item(i).checkState() == Qt.CheckState.Checked]
            self.result_multi = {
                'num_variants': self.count_spin.value(),
                'varying_fields': fields,
                'total_percent': self.percent_spin.value(),
                'first_is_original': self.first_original_checkbox.isChecked(),
            }
            self.accept()
            return

        # Mode simple -- comportement identique a l'ancien DuplicateBlockDialog.
        new_id = self.id_edit.text().strip() if self.id_edit else None
        new_id = new_id or None
        new_name = self.name_edit.text().strip() or None
        remove_id = self.remove_id_checkbox.isChecked() if self.remove_id_checkbox else False

        if remove_id and not new_name:
            QMessageBox.warning(self, t("dup.name_required"), t("dup.name_required_msg"))
            return

        id_changed = new_id is not None and new_id != self._current_id
        name_changed = new_name is not None and new_name != self._current_name
        if not remove_id and not id_changed and not name_changed:
            QMessageBox.warning(self, t("dup.no_change"), t("dup.no_change_msg"))
            return

        self.result_new_id = new_id
        self.result_new_name = new_name
        self.result_remove_id = remove_id
        if self.simple_percent_checkbox.isChecked():
            fields = [self.simple_fields_list.item(i).text() for i in range(self.simple_fields_list.count())
                      if self.simple_fields_list.item(i).checkState() == Qt.CheckState.Checked]
            if fields:
                self.result_simple_percent = self.simple_percent_spin.value()
                self.result_simple_fields = fields
        self.accept()
