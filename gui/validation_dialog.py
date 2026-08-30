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
Fenetre de resultats de la validation des regles metier ECF d'un scenario --
complementaire a check_references_dialog() (heritage Ref) et
check_cross_references_dialog() (references entre fichiers) : celle-ci
verifie des VALEURS et des doublons, voir core/ecf/validation.py pour le
detail et les sources de chaque regle.

Affiche les problemes dans un arbre Fichier > Bloc > Probleme, avec filtres
par niveau et double-clic pour ouvrir le fichier concerne au bon endroit.
"""
from pathlib import Path
from typing import Dict, List

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem,
    QCheckBox, QPushButton, QHeaderView,
)

from gui.busy import busy_guard
from core.i18n import t
from core.ecf.validation import ValidationIssue, validate_scenario
from gui.theme import icon, icon_size
from gui import theme as _theme
from gui.results_window_helpers import export_text_to_file


class ValidationDialog(QDialog):
    """Fenetre NON MODALE affichant les resultats de validation d'un scenario
    -- reste ouverte pendant qu'on corrige les problemes dans l'editeur."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.scenario_root = main_window.workspace.working_root
        self.setWindowTitle(t("validation.dialog_title"))
        self.setMinimumSize(900, 600)

        self.issues_by_file: Dict[Path, List[ValidationIssue]] = {}

        self._build_ui()
        self._run_validation()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel(t("validation.header", root=self.scenario_root.name))
        header.setStyleSheet(f"font-weight: 700; color: {_theme.PRIMARY_DARK}; padding: 4px 0;")
        layout.addWidget(header)

        filter_row = QHBoxLayout()
        self.chk_errors = QCheckBox(t("validation.filter_errors"))
        self.chk_errors.setChecked(True)
        self.chk_errors.stateChanged.connect(self._apply_filters)
        filter_row.addWidget(self.chk_errors)

        self.chk_warnings = QCheckBox(t("validation.filter_warnings"))
        self.chk_warnings.setChecked(True)
        self.chk_warnings.stateChanged.connect(self._apply_filters)
        filter_row.addWidget(self.chk_warnings)

        filter_row.addStretch()
        layout.addLayout(filter_row)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([
            t("validation.col_element"), t("validation.col_code"), t("validation.col_message"),
        ])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.tree)

        bottom_row = QHBoxLayout()
        self.summary_label = QLabel("")
        self.summary_label.setObjectName("mutedLabel")
        bottom_row.addWidget(self.summary_label)
        bottom_row.addStretch()

        btn_refresh = QPushButton(icon("fa5s.sync-alt", "#4a7dfc"), t("results_window.btn_refresh"))
        btn_refresh.setIconSize(icon_size())
        btn_refresh.setObjectName("secondaryButton")
        btn_refresh.clicked.connect(self._run_validation)
        bottom_row.addWidget(btn_refresh)

        btn_export = QPushButton(icon("fa5s.file-export", "#4a7dfc"), t("results_window.btn_export"))
        btn_export.setIconSize(icon_size())
        btn_export.setObjectName("secondaryButton")
        btn_export.clicked.connect(self._export_results)
        bottom_row.addWidget(btn_export)

        btn_close = QPushButton(t("validation.close"))
        btn_close.setObjectName("secondaryButton")
        btn_close.clicked.connect(self.close)
        bottom_row.addWidget(btn_close)
        layout.addLayout(bottom_row)

    def _run_validation(self):
        # Retour utilisateur 30/08/2026 : la validation peut prendre du temps
        # sur un gros scenario -- curseur + boite "en cours" imm�diates.
        with busy_guard(self):
            self.issues_by_file = validate_scenario(self.scenario_root)
            self._populate_tree()
            self._update_summary()

    def _populate_tree(self):
        self.tree.clear()
        for file_path, issues in sorted(self.issues_by_file.items()):
            file_item = QTreeWidgetItem([file_path.name, "", t("validation.n_issues", n=len(issues))])
            file_item.setData(0, Qt.ItemDataRole.UserRole, file_path)
            self.tree.addTopLevelItem(file_item)

            by_block = {}
            for issue in issues:
                block_key = issue.block.kind + " " + (issue.block.get('Id') or issue.block.get_property('Name') or '') \
                    if issue.block is not None else ""
                by_block.setdefault(block_key.strip(), []).append(issue)

            for block_key, block_issues in by_block.items():
                block_item = QTreeWidgetItem([block_key, "", ""])
                file_item.addChild(block_item)
                for issue in block_issues:
                    issue_item = QTreeWidgetItem([issue.property_key or "", issue.code, issue.message])
                    issue_item.setData(0, Qt.ItemDataRole.UserRole, file_path)
                    issue_item.setData(0, Qt.ItemDataRole.UserRole + 1, issue)
                    self._colorize_item(issue_item, issue.level)
                    block_item.addChild(issue_item)
                block_item.setExpanded(True)
            file_item.setExpanded(True)

    def _colorize_item(self, item: QTreeWidgetItem, level: str):
        color = _theme.RED if level == 'error' else _theme.ORANGE
        for col in range(3):
            item.setForeground(col, Qt.GlobalColor.red if level == 'error' else Qt.GlobalColor.darkYellow)

    def _update_summary(self):
        errors = sum(1 for issues in self.issues_by_file.values() for i in issues if i.level == 'error')
        warnings = sum(1 for issues in self.issues_by_file.values() for i in issues if i.level == 'warning')
        if errors == 0 and warnings == 0:
            self.summary_label.setText(t("validation.all_ok"))
        else:
            self.summary_label.setText(t("validation.summary", errors=errors, warnings=warnings))
        self._apply_filters()

    def _apply_filters(self):
        show_errors = self.chk_errors.isChecked()
        show_warnings = self.chk_warnings.isChecked()

        for i in range(self.tree.topLevelItemCount()):
            file_item = self.tree.topLevelItem(i)
            file_visible_children = 0
            for j in range(file_item.childCount()):
                block_item = file_item.child(j)
                block_visible_children = 0
                for k in range(block_item.childCount()):
                    issue_item = block_item.child(k)
                    level = issue_item.text(1)[0] if issue_item.text(1) else ''
                    visible = (level == 'E' and show_errors) or (level == 'W' and show_warnings)
                    issue_item.setHidden(not visible)
                    if visible:
                        block_visible_children += 1
                block_item.setHidden(block_visible_children == 0)
                if block_visible_children > 0:
                    file_visible_children += 1
            file_item.setHidden(file_visible_children == 0)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Ouvre le fichier concerne dans l'editeur (memes mecanismes que le
        double-clic sur un resultat de references croisees)."""
        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        issue = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if not file_path or not isinstance(file_path, Path) or not file_path.exists():
            return
        widget = self.main_window.open_working_file_tab(file_path)
        if widget is None or issue is None or issue.block is None:
            return
        edit_widget = getattr(widget, "edit_widget", widget)
        if hasattr(edit_widget, "select_block_by_identity"):
            identity = issue.block.get('Id') or issue.block.get_property('Name') or ""
            edit_widget.select_block_by_identity(identity)

    def _export_results(self):
        """Exporte l'integralite des resultats (tous fichiers, tous niveaux --
        pas seulement ce qui est actuellement visible avec les filtres) vers un
        fichier texte."""
        lines = [t("validation.dialog_title"), "=" * len(t("validation.dialog_title")), ""]
        if not self.issues_by_file:
            lines.append(t("validation.all_ok"))
        else:
            for file_path, issues in sorted(self.issues_by_file.items()):
                lines.append(f"--- {file_path.name} ---")
                for issue in issues:
                    lines.append(issue.label())
                lines.append("")
        export_text_to_file(self, "validation_scenario.txt", "\n".join(lines))
