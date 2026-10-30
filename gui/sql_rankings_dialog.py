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

"""Classements du PDA (SqlQueries.txt) : etat, boites, apercu SQL, titre
editable, et les deux seules actions sures — desactiver (fichier vide de
requetes) ou revenir aux classements par defaut du jeu (suppression du
fichier du scenario, avec copie de secours). Moteur : core/sql_rankings.py."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog,
                             QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                             QPlainTextEdit, QPushButton, QSplitter,
                             QTableWidget, QTableWidgetItem, QVBoxLayout,
                             QWidget)
from PyQt6.QtCore import Qt

from core.i18n import t
from gui.module_info import add_info_button
from core.sql_rankings import (QUERY_KINDS, disable_rankings, restore_default_rankings,
                               scan, set_box_title)
from gui.ewa_async import async_call
from gui.msgboxes import ask_yes_no, info
from gui.window_geometry import track

_COLS = 6      # positions, nom, titre, requetes, cache, etat


class SqlRankingsDialog(QDialog):
    def __init__(self, parent, working_root: str = ""):
        super().__init__(parent)
        self.setWindowTitle(t("rankings.title"))
        self._running = False
        self._result = None

        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel(t("yamlcheck.scenario")))
        self.path_edit = QLineEdit(working_root)
        self.path_edit.setPlaceholderText(t("yamlcheck.scenario_hint"))
        row.addWidget(self.path_edit, 1)
        self.btn_browse = QPushButton(t("yamlcheck.browse"))
        self.btn_browse.clicked.connect(self._pick_folder)
        row.addWidget(self.btn_browse)
        self.btn_scan = QPushButton(t("rankings.scan"))
        self.btn_scan.clicked.connect(self._analyze)
        row.addWidget(self.btn_scan)
        lay.addLayout(row)

        self.state_label = QLabel("")
        self.state_label.setWordWrap(True)
        lay.addWidget(self.state_label)

        split = QSplitter(Qt.Orientation.Vertical)
        self.table = QTableWidget(0, _COLS)
        self.table.setHorizontalHeaderLabels([
            t("rankings.col_position"), t("rankings.col_box"),
            t("rankings.col_title"), t("rankings.col_queries"),
            t("rankings.col_cache"), t("rankings.col_state")])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive)
        self.table.itemSelectionChanged.connect(self._show_sql)
        split.addWidget(self.table)

        self.sql_view = QPlainTextEdit()
        self.sql_view.setReadOnly(True)
        self.sql_view.setPlaceholderText(t("rankings.sql_hint"))
        split.addWidget(self.sql_view)
        lay.addWidget(split, 1)

        actions = QHBoxLayout()
        self.edit_title = QLineEdit()
        self.edit_title.setPlaceholderText(t("rankings.title_hint"))
        actions.addWidget(self.edit_title, 1)
        self.btn_title = QPushButton(t("rankings.apply_title"))
        self.btn_title.clicked.connect(self._apply_title)
        self.btn_title.setEnabled(False)
        actions.addWidget(self.btn_title)
        lay.addLayout(actions)

        toggles = QHBoxLayout()
        self.btn_disable = QPushButton(t("rankings.disable"))
        self.btn_disable.clicked.connect(self._disable)
        self.btn_disable.setEnabled(False)
        toggles.addWidget(self.btn_disable)
        self.btn_restore = QPushButton(t("rankings.restore"))
        self.btn_restore.setToolTip(t("rankings.restore.tip"))
        self.btn_restore.clicked.connect(self._restore)
        self.btn_restore.setEnabled(False)
        toggles.addWidget(self.btn_restore)
        add_info_button(toggles, "sqlrank.info_html")
        toggles.addStretch(1)
        lay.addLayout(toggles)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        box.rejected.connect(self.reject)
        lay.addWidget(box)
        track(self, "sql_rankings", (1120, 700))

    # ---------------------------------------------------------------- scan

    def _pick_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, t("yamlcheck.scenario"), self.path_edit.text() or ".")
        if path:
            self.path_edit.setText(path)

    def _analyze(self):
        if self._running:
            return
        root = self.path_edit.text().strip()
        if not root:
            self.state_label.setText(t("yamlcheck.need_scenario"))
            return
        self._running = True
        self.btn_scan.setEnabled(False)
        self.state_label.setText(t("taudit.running"))

        def work():
            return scan(Path(root))

        async_call(self, work, on_done=self._on_scanned,
                   on_fail=self._on_fail, name="sql-rankings")

    def _on_fail(self, exc: Exception):
        self._running = False
        self.btn_scan.setEnabled(True)
        self.state_label.setText(f"{t('yamlcheck.failed')}  ({exc})")

    def _on_scanned(self, result):
        self._running = False
        self.btn_scan.setEnabled(True)
        self._result = result
        self.btn_disable.setEnabled(True)
        self.btn_restore.setEnabled(result.path is not None)
        self.btn_title.setEnabled(bool(result.boxes))
        if result.path is None:
            self.state_label.setText(t("rankings.absent"))
        elif result.active:
            self.state_label.setText(t(
                "rankings.active", n=len(result.boxes),
                issues=len(result.issues)))
        else:
            self.state_label.setText(t("rankings.disabled",
                                       n=len(result.boxes),
                                       issues=len(result.issues)))
        self._fill()

    def _fill(self):
        boxes = self._result.boxes if self._result else []
        self.table.setRowCount(len(boxes))
        for row, box in enumerate(boxes):
            filled = sum(1 for k in QUERY_KINDS if box.queries.get(k, "").strip())
            cells = (", ".join(box.positions), box.name, box.title,
                     f"{filled}/{len(QUERY_KINDS)}", box.cache_time,
                     t("rankings.state_on") if box.has_query
                     else t("rankings.state_off"))
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                self.table.setItem(row, col, item)
        self.sql_view.setPlainText("")

    def _current_box(self):
        if self._result is None:
            return None
        row = self.table.currentRow()
        if row < 0 or row >= len(self._result.boxes):
            return None
        return self._result.boxes[row]

    def _show_sql(self):
        box = self._current_box()
        if box is None:
            self.sql_view.setPlainText("")
            self.edit_title.setText("")
            return
        self.edit_title.setText(box.title)
        chunks = []
        for kind in QUERY_KINDS:
            query = box.queries.get(kind, "")
            chunks.append(f"--- {kind} ---\n{query or t('rankings.empty_query')}")
        self.sql_view.setPlainText("\n\n".join(chunks))

    # ------------------------------------------------------------- actions

    def _apply_title(self):
        box = self._current_box()
        if box is None or self._result is None:
            return
        title = self.edit_title.text().strip()
        if not set_box_title(self._result, box, title):
            info(self, t("rankings.title"), t("rankings.title_missing"))
            return
        self._fill()
        self.state_label.setText(t("rankings.title_saved", box=box.name))

    def _disable(self):
        if self._result is None:
            return
        if not ask_yes_no(self, t("rankings.title"), t("rankings.disable_confirm")):
            return
        path = disable_rankings(Path(self.path_edit.text().strip()))
        info(self, t("rankings.title"), t("rankings.disabled_done", path=str(path)))
        self._analyze()

    def _restore(self):
        if self._result is None:
            return
        if not ask_yes_no(self, t("rankings.title"), t("rankings.restore_confirm")):
            return
        backup = restore_default_rankings(Path(self.path_edit.text().strip()))
        if backup is None:
            info(self, t("rankings.title"), t("rankings.absent"))
            return
        info(self, t("rankings.title"), t("rankings.restored", path=str(backup)))
        self._analyze()
