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
from pathlib import Path
from typing import List, Optional, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QCheckBox, QMessageBox, QHeaderView, QRadioButton,
    QButtonGroup, QWidget,
)

from core.i18n import t
from core.ecf.block_creation import scan_kind_frequency, scan_properties_for_kind, find_file_by_name
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
                 craftable_names_players_only: Optional[List[str]] = None,
                 window_title_key: str = "addblock.table_title", parent=None,
                 tech_tree_source: Optional[str] = None, working_root: Optional[Path] = None,
                 sibling_ecf_files: Optional[List[Path]] = None,
                 prechecked_properties: Optional[List[Tuple[str, str]]] = None,
                 prefill_ingredients: Optional[List[Tuple[str, str]]] = None,
                 common_quantities: Optional[List[str]] = None):
        """`prechecked_properties` : [(cle, valeur)] a COCHER d'office avec
        cette valeur -- utilise pour pre-remplir le Template associe avec les
        proprietes les plus courantes du fichier (depuis le 30/08/2026 :
        TOUTES les proprietes observees sur les autres Templates, pas
        seulement CraftTime/Target -- voir scan_template_defaults).
        `prefill_ingredients` : [(ingredient, quantite)] pre-remplis dans la
        table des ingredients (creation d'un Template sans source).
        `common_quantities` : quantites d'ingredients observees dans le
        fichier -- liste deroulante (editable) de la colonne quantite
        (demande du 30/08/2026 : liste deroulante PARTOUT ou c'est
        possible)."""
        super().__init__(parent)
        self.doc = doc
        self.id_mode = id_mode
        self.existing_ids = existing_ids
        self.craftable_names = craftable_names or []
        self.craftable_names_players_only = craftable_names_players_only or []
        self._prechecked = {k: v for k, v in (prechecked_properties or [])}
        self._prefill_ingredients = list(prefill_ingredients or [])
        self._common_quantities = list(common_quantities or [])
        self._properties_by_key = {}
        self._all_rows: List[Tuple[QCheckBox, str, QTableWidgetItem]] = []
        # Previsualisation dans l'arbre technologique (voir
        # gui/tech_tree_preview_dialog.py) -- tech_tree_source ('block' ou
        # 'item') n'est fourni QUE lors de la creation d'un vrai bloc/item
        # (jamais pour un Template, qui n'a pas ce concept) ; le bouton
        # reste cache si les fichiers BlocksConfig.ecf/ItemsConfig.ecf sont
        # introuvables parmi sibling_ecf_files.
        self._tech_tree_source = tech_tree_source
        self._working_root = working_root
        self._tech_blocks_path = find_file_by_name(sibling_ecf_files or [], "BlocksConfig.ecf")
        self._tech_items_path = find_file_by_name(sibling_ecf_files or [], "ItemsConfig.ecf")
        self._tech_tree_pending_values: Optional[Tuple[int, int, List[str], Optional[str]]] = None

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
        self.ingredients_players_only_check = None
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

            self.ingredients_players_only_check = None
            if self.craftable_names_players_only:
                self.ingredients_players_only_check = QCheckBox(t("ecf.players_only_checkbox"))
                self.ingredients_players_only_check.setToolTip(t("ecf.tooltip_players_only"))
                layout.addWidget(self.ingredients_players_only_check)

            # Ingredients pre-remplis (valeurs les plus courantes du fichier,
            # voir core.ecf.block_creation.scan_template_defaults) -- modifiables
            # ensuite ligne par ligne, avec ajout/suppression.
            for ingredient_name, quantity in self._prefill_ingredients:
                self._add_ingredient_row(ingredient_name, quantity)

        # --- Controle avant validation (les 4 obligations de creation, lues
        # dans les vrais fichiers du scenario -- voir core/ecf/creation_check.py).
        # Rafraichi a chaque frappe (contexte de reference mis en cache) ; les
        # erreurs rouges BLOQUENT la validation dans _on_validate().
        from gui.creation_check_panel import CreationCheckPanel
        self.check_panel = CreationCheckPanel(
            doc, sibling_ecf_files, working_root,
            get_values=self._current_check_values,
            check_template_collision=not enable_ingredients,  # cible = Templates.ecf : le controle Name suffit
            check_techtree_hint=tech_tree_source is not None,
            parent=self)
        layout.addWidget(self.check_panel)
        self.edit_id.textChanged.connect(lambda _: self.check_panel.refresh())
        self.edit_name.textChanged.connect(lambda _: self.check_panel.refresh())
        self.combo_kind.currentTextChanged.connect(lambda _: self.check_panel.refresh())

        # --- Boutons ---
        buttons = QHBoxLayout()
        if self._tech_tree_source is not None and (self._tech_blocks_path or self._tech_items_path):
            btn_preview_tech_tree = QPushButton(t("techtree.preview_button"))
            btn_preview_tech_tree.clicked.connect(self._open_tech_tree_preview)
            buttons.addWidget(btn_preview_tech_tree)
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
        self._refresh_check_panel()

    def _current_check_values(self):
        """Valeurs ACTUELLEMENT saisies, pour le panneau de controle
        (voir gui/creation_check_panel.py)."""
        kind = self.combo_kind.currentText().strip()
        id_text = self.edit_id.text().strip()
        name_text = self.edit_name.text().strip()
        properties = []
        for checkbox, key, value_combo in self._all_rows:
            if checkbox.isChecked():
                properties.append((key, value_combo.currentText()))
        return kind, id_text, name_text, properties

    def _refresh_check_panel(self):
        if getattr(self, 'check_panel', None) is not None:
            self.check_panel.refresh()

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
            # Le panneau de controle re-verifie en direct (ex: Material saisi,
            # UnlockLevel coche changent ses avertissements).
            checkbox.toggled.connect(lambda _checked: self._refresh_check_panel())
            value_combo.currentTextChanged.connect(lambda _text: self._refresh_check_panel())

            # Pre-remplissage "valeurs les plus courantes" (creation d'un
            # Template sans source -- demande du 30/08/2026) : les cles
            # proposees par l'appelant arrivent COCHEES avec leur valeur.
            if key in self._prechecked:
                checkbox.setChecked(True)
                value_combo.setCurrentText(self._prechecked[key])

            self._all_rows.append((checkbox, key, value_combo))
        self.table.resizeColumnsToContents()

    def _apply_filter(self, text: str):
        text_lower = text.strip().lower()
        for row, (_, key, _) in enumerate(self._all_rows):
            self.table.setRowHidden(row, text_lower not in key.lower())

    def _find_row(self, key: str):
        for checkbox, k, value_combo in self._all_rows:
            if k == key:
                return checkbox, value_combo
        return None, None

    def _apply_row_value(self, key: str, value: str) -> None:
        """Coche la ligne `key` du tableau et lui affecte `value` -- utilise
        par _open_tech_tree_preview() pour reporter le choix fait dans la
        previsualisation. Ne fait rien silencieusement si la propriete
        n'apparait pas parmi celles scannees pour ce genre (cas marginal :
        UnlockLevel/UnlockCost/TechTreeNames sont quasi-universelles sur de
        vrais Blocks/Items reels, mais un genre tres rare pourrait ne pas en
        avoir d'exemple dans le fichier de travail)."""
        checkbox, value_combo = self._find_row(key)
        if checkbox is None:
            return
        checkbox.setChecked(True)
        value_combo.setCurrentText(value)

    def _open_tech_tree_preview(self) -> None:
        """Ouvre la previsualisation de position dans l'arbre technologique
        (voir gui/tech_tree_preview_dialog.py) a partir des valeurs
        ACTUELLEMENT saisies (si cochees) pour UnlockLevel/UnlockCost/
        TechTreeNames/TechTreeParent, et reporte le resultat dans le tableau
        si l'utilisateur valide."""
        from core.tech_tree import _parse_list_value

        def _int_or(key: str, default: int) -> int:
            checkbox, combo = self._find_row(key)
            if checkbox is not None and checkbox.isChecked():
                try:
                    return int(combo.currentText().strip())
                except ValueError:
                    pass
            return default

        categories: List[str] = []
        checkbox, combo = self._find_row('TechTreeNames')
        if checkbox is not None and checkbox.isChecked():
            categories = _parse_list_value(combo.currentText().strip())

        parent_name: Optional[str] = None
        checkbox, combo = self._find_row('TechTreeParent')
        if checkbox is not None and checkbox.isChecked():
            parent_name = combo.currentText().strip().strip('"') or None

        from gui.tech_tree_preview_dialog import TechTreePreviewDialog
        dlg = TechTreePreviewDialog(
            self._tech_blocks_path, self._tech_items_path, self._working_root,
            source=self._tech_tree_source, initial_level=_int_or('UnlockLevel', 1),
            initial_cost=_int_or('UnlockCost', 0), initial_categories=categories,
            initial_parent=parent_name, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        level, cost, chosen_categories, chosen_parent = dlg.result_values()
        self._apply_row_value('UnlockLevel', str(level))
        self._apply_row_value('UnlockCost', str(cost))
        if chosen_categories:
            names_value = chosen_categories[0] if len(chosen_categories) == 1 \
                else '"' + ','.join(chosen_categories) + '"'
            self._apply_row_value('TechTreeNames', names_value)
        if chosen_parent:
            self._apply_row_value('TechTreeParent', chosen_parent)
        self._refresh_check_panel()

    def _add_ingredient_row(self, name: str = "", quantity: str = "1"):
        row = self.ingredients_table.rowCount()
        self.ingredients_table.insertRow(row)
        combo = QComboBox()
        combo.setEditable(True)
        use_players_only = bool(self.ingredients_players_only_check
                                 and self.ingredients_players_only_check.isChecked())
        combo.addItems(self.craftable_names_players_only if use_players_only else self.craftable_names)
        if name:
            combo.setCurrentText(name)
        self.ingredients_table.setCellWidget(row, 0, combo)
        # Quantite en liste deroulante EDITABLE des quantites courantes
        # observees dans le fichier (saisie libre toujours permise) --
        # demande du 30/08/2026 : liste deroulante PARTOUT ou c'est possible.
        qty_combo = QComboBox()
        qty_combo.setEditable(True)
        qty_combo.addItems(self._common_quantities)
        qty_combo.setCurrentText(quantity or "1")
        self.ingredients_table.setCellWidget(row, 1, qty_combo)

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

        # Controle final AVANT validation : re-rafraichi (pour capter les
        # dernieres saisies) puis refuse si au moins une erreur bloquante --
        # les 4 obligations de creation sont verifiees dans les vrais fichiers
        # (voir core/ecf/creation_check.py).
        self.check_panel.refresh()
        if self.check_panel.has_blocking_errors():
            from core.ecf.creation_check import format_blocking
            blocking = format_blocking(self.check_panel.issues)
            QMessageBox.warning(self, t("createcheck.blocked_title"),
                                t("createcheck.blocked_msg", issues=blocking))
            return

        properties = []
        for row, (checkbox, key, value_combo) in enumerate(self._all_rows):
            if checkbox.isChecked():
                properties.append((key, value_combo.currentText()))

        ingredients = []
        if self.ingredients_table is not None:
            for row in range(self.ingredients_table.rowCount()):
                combo = self.ingredients_table.cellWidget(row, 0)
                qty_combo = self.ingredients_table.cellWidget(row, 1)
                ing_name = combo.currentText().strip() if combo else ""
                qty = qty_combo.currentText().strip() if qty_combo else ""
                if ing_name and qty:
                    ingredients.append((ing_name, qty))

        self.result_kind = kind
        self.result_id = id_text if self.id_mode == IdentityModeDialog.MODE_ID_AND_NAME else None
        self.result_name = name_text or None
        self.result_properties = properties
        self.result_ingredients = ingredients
        self.accept()
