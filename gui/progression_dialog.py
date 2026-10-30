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

"""Tableau de bord « danger & progression » (LECTURE SEULE) : danger des
playfields, recompenses des chapitres PDA, cout des attaques de faction,
chacun face a la mediane de son groupe (core/progression_balance.py).
Aucune ecriture de scenario ici : les corrections se font dans les modules
dedies (Ondes de spawn, Defenses de faction, editeur PDA)."""
from __future__ import annotations

import datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog,
                             QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                             QPushButton, QTabWidget, QTableWidget,
                             QTableWidgetItem, QVBoxLayout)

from core.i18n import t
from gui.module_info import add_info_button
from core.progression_balance import export_csv, scan
from gui.ewa_async import async_call
from gui.msgboxes import info
from gui.window_geometry import track


class ProgressionDialog(QDialog):
    def __init__(self, parent, working_root: str = ""):
        super().__init__(parent)
        self.setWindowTitle(t("prog.title"))
        self._running = False
        self._report = None

        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel(t("yamlcheck.scenario")))
        self.path_edit = QLineEdit(working_root)
        self.path_edit.setPlaceholderText(t("yamlcheck.scenario_hint"))
        row.addWidget(self.path_edit, 1)
        self.btn_browse = QPushButton(t("yamlcheck.browse"))
        self.btn_browse.clicked.connect(self._pick_folder)
        row.addWidget(self.btn_browse)
        self.btn_scan = QPushButton(t("prog.scan"))
        self.btn_scan.clicked.connect(self._analyze)
        row.addWidget(self.btn_scan)
        lay.addLayout(row)

        self.stats_label = QLabel("")
        self.stats_label.setWordWrap(True)
        lay.addWidget(self.stats_label)

        self.tabs = QTabWidget()
        self.table_pf = self._make_table([
            t("prog.col_playfield"), t("sw.col_type"), t("prog.col_min"),
            t("prog.col_max"), t("prog.col_status")])
        self.table_ch = self._make_table([
            t("prog.col_chapter"), t("pda.chapter.category"), "XP", "UP",
            t("prog.col_reputation"), t("prog.col_status")])
        self.table_at = self._make_table([
            t("prog.col_faction"), t("prog.col_lvl1"), t("prog.col_lvl10"),
            t("prog.col_sd"), t("prog.col_status")])
        self.tabs.addTab(self.table_pf, t("prog.tab_playfields"))
        self.tabs.addTab(self.table_ch, t("prog.tab_chapters"))
        self.tabs.addTab(self.table_at, t("prog.tab_attacks"))
        lay.addWidget(self.tabs, 1)

        buttons = QHBoxLayout()
        self.btn_export = QPushButton(t("prog.export"))
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._export)
        buttons.addWidget(self.btn_export)
        buttons.addWidget(QLabel(t("prog.readonly")))
        add_info_button(buttons, "progression.info_html")
        buttons.addStretch(1)
        lay.addLayout(buttons)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        box.rejected.connect(self.reject)
        lay.addWidget(box)
        track(self, "progression", (1180, 720))

    def _make_table(self, headers) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSortingEnabled(True)
        return table

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
            self.stats_label.setText(t("yamlcheck.need_scenario"))
            return
        self._running = True
        self.btn_scan.setEnabled(False)
        self.stats_label.setText(t("taudit.running"))

        def work():
            return scan(Path(root))

        async_call(self, work, on_done=self._on_scanned,
                   on_fail=self._on_fail, name="progression")

    def _on_fail(self, exc: Exception):
        self._running = False
        self.btn_scan.setEnabled(True)
        self.stats_label.setText(f"{t('yamlcheck.failed')}  ({exc})")

    def _on_scanned(self, report):
        self._running = False
        self.btn_scan.setEnabled(True)
        self._report = report
        self.btn_export.setEnabled(True)
        self.stats_label.setText(t(
            "prog.stats", playfields=len(report.playfields),
            outliers=sum(1 for p in report.playfields if p.status == "outlier"),
            chapters=len(report.chapters),
            below=sum(1 for c in report.chapters if c.status == "below"),
            above=sum(1 for c in report.chapters if c.status == "above"),
            attacks=len(report.attacks)))
        self._fill()

    def _fill(self):
        report = self._report
        # playfields
        self._fill_rows(self.table_pf, [
            (p.playfield, p.pf_type, str(p.danger_min), str(p.danger_max),
             t("prog.status_" + p.status)) for p in report.playfields])
        # chapitres
        self._fill_rows(self.table_ch, [
            (c.title, c.category, str(c.xp), str(c.up), str(c.reputation),
             t("prog.status_" + c.status)) for c in report.chapters])
        # attaques
        self._fill_rows(self.table_at, [
            (a.faction,
             "" if a.lvl1_min is None else f"{a.lvl1_min:g}",
             "" if a.lvl10_max is None else f"{a.lvl10_max:g}",
             a.sd_group or "—",
             t("prog.status_" + a.status)) for a in report.attacks])

    def _fill_rows(self, table: QTableWidget, rows):
        table.setSortingEnabled(False)
        table.setUpdatesEnabled(False)
        table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            for col, text in enumerate(row):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                if col >= 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                          | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(index, col, item)
        table.setUpdatesEnabled(True)
        table.setSortingEnabled(True)

    # -------------------------------------------------------------- export

    def _export(self):
        if self._report is None:
            return
        base = self.path_edit.text().strip() or str(Path.home())
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
        out, _ = QFileDialog.getSaveFileName(
            self, t("prog.export"),
            str(Path(base) / f"danger_progression_{stamp}.csv"), "CSV (*.csv)")
        if not out:
            return
        export_csv(self._report, Path(out))
        info(self, t("prog.title"), t("prog.exported", path=out))
