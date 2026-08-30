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
Recherche a travers TOUS les fichiers de la copie de travail (ECF, YAML,
CSV) -- voir core/scenario_search.py. Reutilise le mecanisme de navigation
precise deja construit pour les fenetres de verification
(select_block_by_identity/select_entry_by_key_value, voir
gui/cross_reference_dialog.py). Pas de recherche "en direct" -- bouton
explicite (ou touche Entree), pour eviter de re-parcourir tout le scenario a
chaque frappe sur un gros projet.

Fenetre NON MODALE (meme motif que les autres fenetres de resultats)."""
import re

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QCheckBox, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox,
)

from core.i18n import t
from gui.busy import busy_guard
from core.scenario_search import search_scenario, SearchResult


class ScenarioSearchDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.workspace = main_window.workspace
        self.setWindowTitle(t("search.title"))
        self.setMinimumSize(680, 480)

        layout = QVBoxLayout(self)

        search_row = QHBoxLayout()
        self.query_edit = QLineEdit()
        self.query_edit.setPlaceholderText(t("search.placeholder"))
        self.query_edit.returnPressed.connect(self._run_search)
        search_row.addWidget(self.query_edit, 1)
        self.case_sensitive_check = QCheckBox(t("search.case_sensitive"))
        search_row.addWidget(self.case_sensitive_check)
        self.regex_check = QCheckBox(t("search.use_regex"))
        self.regex_check.setToolTip(t("search.use_regex_tooltip"))
        search_row.addWidget(self.regex_check)
        btn_search = QPushButton(t("search.btn_search"))
        btn_search.setObjectName("primaryButton")
        btn_search.clicked.connect(self._run_search)
        search_row.addWidget(btn_search)
        layout.addLayout(search_row)

        note = QLabel(t("search.csv_limitation_note"))
        note.setWordWrap(True)
        note.setObjectName("mutedLabel")
        layout.addWidget(note)

        self.results_list = QListWidget()
        self.results_list.itemDoubleClicked.connect(self._navigate_to_result)
        layout.addWidget(self.results_list, 1)

        bottom_row = QHBoxLayout()
        self.summary_label = QLabel("")
        self.summary_label.setObjectName("mutedLabel")
        bottom_row.addWidget(self.summary_label)
        bottom_row.addStretch()
        btn_close = QPushButton(t("validation.close"))
        btn_close.setObjectName("secondaryButton")
        btn_close.clicked.connect(self.close)
        bottom_row.addWidget(btn_close)
        layout.addLayout(bottom_row)

    def _gather_files(self):
        ecf_files = [f.path for f in self.workspace.working.configuration if f.extension == '.ecf']
        csv_files = [f.path for f in self.workspace.working.configuration if f.extension == '.csv']
        yaml_files = []
        for pf in self.workspace.working.playfields.values():
            for role, path in pf.role_files.items():
                if path.suffix.lower() in ('.yaml', '.yml'):
                    yaml_files.append(path)
        yaml_files.extend(f.path for f in self.workspace.working.sectors if f.path.suffix.lower() in ('.yaml', '.yml'))
        yaml_files.extend(f.path for f in self.workspace.working.random_presets
                           if f.path.suffix.lower() in ('.yaml', '.yml'))
        return ecf_files, yaml_files, csv_files

    def _run_search(self):
        query = self.query_edit.text()
        if not query.strip():
            self.results_list.clear()
            self.summary_label.setText("")
            return
        ecf_files, yaml_files, csv_files = self._gather_files()
        try:
            with busy_guard(self):
                results = search_scenario(
                    ecf_files, yaml_files, csv_files, query,
                    case_sensitive=self.case_sensitive_check.isChecked(),
                    use_regex=self.regex_check.isChecked())
        except re.error as e:
            # Motif regex invalide : signale AVANT toute recherche, la liste
            # precedente reste affichee (pas de resultats vides trompeurs).
            QMessageBox.warning(self, t("search.title"),
                                t("search.invalid_regex", error=str(e)))
            return
        self.results_list.clear()
        for r in results:
            item = QListWidgetItem(f"[{r.file_kind.upper()}] {r.file_path.name} -- {r.match_context}")
            item.setData(Qt.ItemDataRole.UserRole, r)
            self.results_list.addItem(item)
        self.summary_label.setText(t("search.n_results", n=len(results)))

    def _navigate_to_result(self, item: QListWidgetItem):
        result: SearchResult = item.data(Qt.ItemDataRole.UserRole)
        if result is None:
            return
        widget = self.main_window.open_working_file_tab(result.file_path)
        if widget is None:
            return
        edit_widget = getattr(widget, "edit_widget", widget)
        if result.file_kind == "ecf" and hasattr(edit_widget, "select_block_by_identity"):
            edit_widget.select_block_by_identity(
                result.identity, prop_key=result.prop_key, prop_value=result.prop_value)
        elif result.file_kind == "yaml" and hasattr(edit_widget, "select_entry_by_key_value"):
            edit_widget.select_entry_by_key_value(result.entry_key, result.entry_value)
        # csv : pas de navigation precise -- l'ouverture du fichier suffit deja
        # a orienter l'utilisateur (voir docstring de tete de module).
