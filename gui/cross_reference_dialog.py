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

from gui.busy import busy_guard
from core.i18n import t
from core.ecf.cross_reference_check import (
    CROSS_REFERENCE_CHECKS, CrossRefContext, CrossRefIssue, run_checks,
)
from gui.results_window_helpers import export_text_to_file
from gui.theme import icon, icon_size


class CrossReferenceDialog(QDialog):
    def __init__(self, workspace, main_window, parent=None, only_check_ids=None):
        """only_check_ids : si fourni, seules ces verifications demarrent
        cochees (les autres restent decochees par defaut) -- utilise par
        l'ancien menu "Verifier les references" (check_references_dialog dans
        main_window.py) pour reutiliser cette meme fenetre (export,
        actualisation, navigation) en ne montrant que la verification
        d'heritage Ref, plutot que de dupliquer toute cette logique."""
        super().__init__(parent)
        self.workspace = workspace
        self.main_window = main_window
        self._last_issues = []

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
            checked = check.id in only_check_ids if only_check_ids is not None else check.enabled_by_default
            box.setChecked(checked)
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

        bottom_row = QHBoxLayout()
        btn_refresh = QPushButton(icon("fa5s.sync-alt", "#4a7dfc"), t("results_window.btn_refresh"))
        btn_refresh.setIconSize(icon_size())
        btn_refresh.setObjectName("secondaryButton")
        btn_refresh.clicked.connect(self._do_run)
        bottom_row.addWidget(btn_refresh)

        btn_export = QPushButton(icon("fa5s.file-export", "#4a7dfc"), t("results_window.btn_export"))
        btn_export.setIconSize(icon_size())
        btn_export.setObjectName("secondaryButton")
        btn_export.clicked.connect(self._export_results)
        bottom_row.addWidget(btn_export)

        bottom_row.addStretch()
        btn_close = QPushButton(t("btn.close"))
        btn_close.setObjectName("secondaryButton")
        btn_close.clicked.connect(self.close)
        bottom_row.addWidget(btn_close)
        layout.addLayout(bottom_row)

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
        # Retour utilisateur 30/08/2026 : l'analyse peut etre longue sur un
        # gros scenario -- curseur d'attente + boite "en cours" modale a la
        # fenetre (voir gui/busy.py), sinon l'application semblait bloquee.
        try:
            with busy_guard(self):
                issues = run_checks(ctx, selected_ids)
        except Exception as e:
            QMessageBox.critical(self, t("err.title"), f"{t('check.verification_error')} :\n{e}")
            return

        self._last_issues = issues
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

    def _export_results(self):
        """Exporte la liste complete des resultats (pas seulement les 500
        premiers affiches) vers un fichier texte -- utile pour garder une trace
        ou travailler hors de l'application. Relance la verification d'abord si
        elle n'a jamais ete lancee, pour ne jamais exporter un fichier vide par
        erreur d'usage."""
        if not self._last_issues and self.results_list.count() == 0 and not self.summary_label.text():
            self._do_run()
        lines = [t("crossref.title"), "=" * len(t("crossref.title")), ""]
        if not self._last_issues:
            lines.append(t("crossref.all_ok"))
        else:
            for issue in self._last_issues:
                lines.append(issue.label())
        export_text_to_file(self, "references_croisees.txt", "\n".join(lines))

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
