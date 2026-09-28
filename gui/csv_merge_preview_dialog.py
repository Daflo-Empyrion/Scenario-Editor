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

"""Apercu MODIFIABLE d'une fusion CSV avant ecriture (demande 26/09/2026 :
la fusion CSV etait aveugle, lignes ajoutees et cellules completees sans
fenetre). Le plan (core.csv_handler.plan_csv_merge) liste chaque ligne
ajoutee ou completee par la source ; l'utilisateur coche ce qui passe, la
copie de travail reste prioritaire (jamais d'ecrasement)."""
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton,
                             QTableWidget, QTableWidgetItem, QVBoxLayout)

from core.i18n import t
from gui.window_geometry import track


class CsvMergePreviewDialog(QDialog):
    """Changements CSV cocheables. N'applique RIEN : l'appelant lit
    `selected_changes()` et gere ecriture + undo."""

    COL_CHECK, COL_ACTION, COL_KEY, COL_INFO = range(4)

    def __init__(self, dest_csv: Path, source_csv: Path,
                 source_label: str, parent=None):
        super().__init__(parent)
        self.dest_csv = Path(dest_csv)
        self.source_csv = Path(source_csv)
        self.source_label = source_label
        self.setWindowTitle(t("csvmerge.title", file=source_csv.name))
        track(self, "csv_merge_preview", (720, 480))

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(t("csvmerge.intro",
                                  source=self.source_label)))

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([
            t("mergeplan.col_apply"), t("csvmerge.col_action"),
            t("csvmerge.col_key"), t("mergeplan.col_info")])
        self.table.setColumnWidth(0, 70)
        self.table.setColumnWidth(1, 190)
        self.table.setColumnWidth(2, 220)
        layout.addWidget(self.table)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        buttons = QHBoxLayout()
        btn_all = QPushButton(t("trans.check_all"))
        btn_all.clicked.connect(lambda: self._set_all_checks(True))
        buttons.addWidget(btn_all)
        btn_none = QPushButton(t("trans.uncheck_all"))
        btn_none.clicked.connect(lambda: self._set_all_checks(False))
        buttons.addWidget(btn_none)
        buttons.addStretch()
        self.btn_apply = QPushButton(t("mergepreview.btn_apply"))
        self.btn_apply.setObjectName("primaryButton")
        self.btn_apply.clicked.connect(self.accept)
        buttons.addWidget(self.btn_apply)
        btn_cancel = QPushButton(t("btn.cancel"))
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_cancel)
        layout.addLayout(buttons)

        from gui.busy import run_long
        from core.workspace import plan_csv_merge_file
        self.changes = run_long(
            self, lambda: plan_csv_merge_file(self.dest_csv,
                                              self.source_csv))
        self._fill()

    def _fill(self):
        for change in self.changes:
            r = self.table.rowCount()
            self.table.insertRow(r)
            action = t("csvmerge.action_added") \
                if change.action == "added" \
                else t("csvmerge.action_completed")
            items = [QTableWidgetItem(""), QTableWidgetItem(action),
                     QTableWidgetItem(change.key),
                     QTableWidgetItem(change.detail)]
            items[0].setFlags(items[0].flags() | Qt.ItemFlag.ItemIsUserCheckable)
            items[0].setCheckState(Qt.CheckState.Checked)
            for c, it in enumerate(items):
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(r, c, it)
        self.status_label.setText(t("csvmerge.summary", n=len(self.changes),
                                    name=self.source_csv.name))
        self._refresh_buttons()

    def _refresh_buttons(self):
        self.btn_apply.setText(t("csvmerge.btn_apply_n",
                                 n=len(self.selected_changes())))

    def _set_all_checks(self, state: bool):
        cs = Qt.CheckState.Checked if state else Qt.CheckState.Unchecked
        for r in range(self.table.rowCount()):
            self.table.item(r, self.COL_CHECK).setCheckState(cs)
        self._refresh_buttons()

    def selected_changes(self):
        out = []
        for r in range(self.table.rowCount()):
            if self.table.item(r, self.COL_CHECK).checkState() \
                    == Qt.CheckState.Checked:
                out.append(self.changes[r])
        return out
