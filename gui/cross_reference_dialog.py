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
Dialogue "Verifier les references croisees" -- complement a la verification
Ref classique (menu Verification > Verifier les references), qui ne regarde
qu'un seul type de lien au sein des fichiers ECF. Ici, plusieurs verifications
independantes et activables/desactivables (voir
core/ecf/cross_reference_check.py, CROSS_REFERENCE_CHECKS) : items/blocs
references, jetons, POI de playfield.
"""
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox,
)
from PyQt6.QtCore import Qt

from core.i18n import t
from core.ecf.cross_reference_check import (
    CROSS_REFERENCE_CHECKS, CrossRefContext, CrossRefIssue, run_checks,
)


class CrossReferenceDialog(QDialog):
    def __init__(self, workspace, main_window, parent=None):
        super().__init__(parent)
        self.workspace = workspace
        self.main_window = main_window

        self.setWindowTitle(t("crossref.title"))
        self.setMinimumSize(680, 520)
        layout = QVBoxLayout(self)

        intro = QLabel(t("crossref.intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        layout.addWidget(QLabel(t("crossref.checks_label")))
        self.checkboxes = {}
        for check in CROSS_REFERENCE_CHECKS:
            box = QCheckBox(check.label_fr if _current_lang() == "fr" else check.label_en)
            box.setChecked(check.enabled_by_default)
            box.setToolTip(check.description_fr if _current_lang() == "fr" else check.description_en)
            layout.addWidget(box)
            self.checkboxes[check.id] = box

        btn_run = QPushButton(t("crossref.btn_run"))
        btn_run.setObjectName("primaryButton")
        btn_run.clicked.connect(self._do_run)
        layout.addWidget(btn_run)

        layout.addWidget(QLabel(t("crossref.results_label")))
        self.results_list = QListWidget()
        self.results_list.itemDoubleClicked.connect(self._navigate_to_issue)
        layout.addWidget(self.results_list, 1)

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        btn_close = QPushButton(t("btn.close"))
        btn_close.setObjectName("secondaryButton")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def _do_run(self):
        selected_ids = [cid for cid, box in self.checkboxes.items() if box.isChecked()]
        if not selected_ids:
            QMessageBox.information(self, t("crossref.title"), t("crossref.no_check_selected"))
            return

        ecf_files = [f.path for f in self.workspace.working.configuration if f.extension == '.ecf']

        ctx = CrossRefContext(
            ecf_files=ecf_files, yaml_files=[],
            scenario_root=self.workspace.working_root,
        )

        self.results_list.clear()
        try:
            issues = run_checks(ctx, selected_ids)
        except Exception as e:
            QMessageBox.critical(self, t("err.title"), f"{t('check.verification_error')} :\n{e}")
            return

        if not issues:
            self.summary_label.setText(t("crossref.all_ok"))
            return

        for issue in issues[:500]:
            item = QListWidgetItem(issue.label())
            item.setData(Qt.ItemDataRole.UserRole, issue)
            self.results_list.addItem(item)
        more = ""
        if len(issues) > 500:
            more = t("crossref.more_issues", n=len(issues) - 500)
        self.summary_label.setText(t("crossref.issues_found", n=len(issues)) + more)

    def _navigate_to_issue(self, item: QListWidgetItem):
        """Ouvre (ou active) l'onglet du fichier concerne par ce resultat, puis
        navigue directement jusqu'au bloc/sous-bloc et, si possible, jusqu'a la
        cellule exacte -- evite d'avoir a chercher soi-meme ou se trouve le
        probleme signale, notamment pour les playfields ou plusieurs fichiers
        portent le meme nom (voir CrossRefIssue.display_path)."""
        issue: CrossRefIssue = item.data(Qt.ItemDataRole.UserRole)
        if issue is None:
            return

        widget = self.main_window.open_working_file_tab(issue.source_file)
        if widget is None:
            return

        # CompareWidget (fichiers .ecf) expose le vrai widget editable via
        # .edit_widget -- les autres types de fichiers sont directement le bon
        # widget (voir open_working_file_tab() dans main_window.py).
        edit_widget = getattr(widget, "edit_widget", widget)

        ext = issue.source_file.suffix.lower()
        if ext == ".ecf" and hasattr(edit_widget, "select_block_by_identity"):
            edit_widget.select_block_by_identity(
                issue.source_identity, prop_key=issue.ref_key, prop_value=issue.ref_value)
        elif ext in (".yaml", ".yml") and hasattr(edit_widget, "select_entry_by_key_value"):
            edit_widget.select_entry_by_key_value(issue.ref_key, issue.ref_value)


def _current_lang() -> str:
    from core import i18n
    return i18n.get_language()
