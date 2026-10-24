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

"""Revue d'une proposition de l'assistant (Q16) : rien ne s'applique sans
un clic humain.

Meme principe que TransformDialog : une ligne par changement, une case pour
l'inclure, une colonne « Apres » librement modifiable (un cas particulier
peut s'ecarter de la regle generale). L'application passe par le callback de
la surface, qui revalide contre le document vivant (valeur `old`) et prend
son propre snapshot undo -- la fenetre ne touche jamais un fichier.
"""
from dataclasses import replace

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel,
                             QMessageBox, QPushButton, QTableWidget,
                             QTableWidgetItem, QVBoxLayout)

from core.ai.assistant.changeset import ChangeSet
from core.ai.assistant.surfaces.base import problem_text
from core.i18n import t


class ChangeReviewDialog(QDialog):
    def __init__(self, changeset: ChangeSet, apply_callback, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("assistant.review_title"))
        self.setMinimumSize(720, 420)
        self._changes = list(changeset.changes)
        self._changeset = changeset
        self._apply = apply_callback

        layout = QVBoxLayout(self)
        summary = (changeset.summary or "").strip()
        if summary:
            label = QLabel(summary)
            label.setWordWrap(True)
            layout.addWidget(label)

        self.table = QTableWidget(len(self._changes), 5)
        self.table.setHorizontalHeaderLabels([
            "", t("assistant.review_target"), t("assistant.review_before"),
            t("assistant.review_after"), t("assistant.review_reason")])
        self.table.setColumnWidth(0, 30)
        self.table.setColumnWidth(1, 220)
        self.table.setColumnWidth(2, 140)
        self.table.setColumnWidth(3, 180)
        self.table.horizontalHeader().setStretchLastSection(True)
        for row, change in enumerate(self._changes):
            check = QTableWidgetItem("")
            flags = check.flags() | Qt.ItemFlag.ItemIsUserCheckable
            flags &= ~Qt.ItemFlag.ItemIsEditable
            check.setFlags(flags)
            check.setCheckState(Qt.CheckState.Checked)
            self.table.setItem(row, 0, check)
            self.table.setItem(row, 1, QTableWidgetItem(change.target))
            self.table.setItem(row, 2, QTableWidgetItem(change.old))
            self.table.setItem(row, 3, QTableWidgetItem(change.new))
            self.table.setItem(row, 4, QTableWidgetItem(change.reason))
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked
            | QTableWidget.EditTrigger.EditKeyPressed)
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        btn_all = QPushButton(t("trans.check_all"))
        btn_all.setObjectName("secondaryButton")
        btn_all.clicked.connect(lambda: self._set_all(True))
        buttons.addWidget(btn_all)
        btn_none = QPushButton(t("trans.uncheck_all"))
        btn_none.setObjectName("secondaryButton")
        btn_none.clicked.connect(lambda: self._set_all(False))
        buttons.addWidget(btn_none)
        buttons.addStretch()
        if self._changeset.report:
            btn_export = QPushButton(t("assistant.report_export"))
            btn_export.setObjectName("secondaryButton")
            btn_export.setToolTip(t("assistant.report_export_tip"))
            btn_export.clicked.connect(self._export_report)
            buttons.addWidget(btn_export)
        btn_cancel = QPushButton(t("btn.close"))
        btn_cancel.setObjectName("secondaryButton")
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_cancel)
        self.btn_apply = QPushButton(t("assistant.review_apply"))
        self.btn_apply.setObjectName("primaryButton")
        self.btn_apply.clicked.connect(self._do_apply)
        buttons.addWidget(self.btn_apply)
        layout.addLayout(buttons)

    def _set_all(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setCheckState(state)

    def selected_changes(self) -> list:
        out = []
        for row, change in enumerate(self._changes):
            if self.table.item(row, 0).checkState() != Qt.CheckState.Checked:
                continue
            out.append(replace(change, new=self.table.item(row, 3).text()))
        return out

    def _export_report(self) -> None:
        """Dependances non importables : CSV a cote de la revue."""
        path, _filter = QFileDialog.getSaveFileName(
            self, t("assistant.report_export_title"),
            "dependances_non_importees.csv", "CSV (*.csv)")
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            count = self._changeset.write_report_csv(path)
        except OSError as e:
            QMessageBox.warning(self, t("assistant.report_export_title"),
                                t("assistant.report_export_error",
                                  message=str(e)))
            return
        QMessageBox.information(
            self, t("assistant.report_export_title"),
            t("assistant.report_export_done", count=count, path=path))

    def _do_apply(self) -> None:
        changes: list = self.selected_changes()
        if not changes:
            QMessageBox.information(self, t("assistant.review_title"),
                                    t("assistant.review_nothing"))
            return
        ok, problem = self._apply(changes)
        if not ok:
            QMessageBox.warning(
                self, t("assistant.review_title"),
                t("assistant.review_refused", reason=problem_text(problem)))
            return
        QMessageBox.information(
            self, t("assistant.review_title"),
            t("assistant.review_applied", count=len(changes)))
        self.accept()


def review_changeset(changeset: ChangeSet, apply_callback, parent=None) -> bool:
    """Ouvre la revue ; True si au moins une ligne a ete appliquee."""
    dialog = ChangeReviewDialog(changeset, apply_callback, parent)
    try:
        return dialog.exec() == QDialog.DialogCode.Accepted
    finally:
        dialog.deleteLater()
