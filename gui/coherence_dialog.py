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

"""Contrôle de cohérence GLOBAL : lance tous les moteurs d'analyse en
lecture seule (bilan F5, marchands, prix marché, recettes, UnlockCost,
corrélations, spawns, progression) et présente les constatations en une
table : domaine, sévérité, nombre, exemples, module de correction conseillé.
Lecture seule — les corrections restent dans les modules dédiés
(moteur : core/coherence_audit.py)."""
from __future__ import annotations

import csv
import datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QHeaderView,
                             QLabel, QLineEdit, QPushButton, QTableWidget,
                             QTableWidgetItem, QVBoxLayout)

from core.coherence_audit import run_coherence_audit
from core.i18n import t
from gui.ewa_async import async_call
from gui.window_geometry import track

_COLS = 5   # domaine, severite, nombre, exemples, module conseille

_SEV_KEY = {"error": "coh.sev_error", "warning": "coh.sev_warning",
            "info": "coh.sev_info"}


class CoherenceDialog(QDialog):
    def __init__(self, parent, working_root: str = ""):
        super().__init__(parent)
        self.setWindowTitle(t("coh.title"))
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
        lay.addLayout(row)

        buttons = QHBoxLayout()
        self.btn_run = QPushButton(t("coh.analyze"))
        self.btn_run.setToolTip(t("coh.analyze.tip"))
        self.btn_run.clicked.connect(self._analyze)
        buttons.addWidget(self.btn_run)
        self.btn_export = QPushButton(t("market.export"))
        self.btn_export.clicked.connect(self._export_csv)
        self.btn_export.setEnabled(False)
        buttons.addWidget(self.btn_export)
        buttons.addStretch(1)
        lay.addLayout(buttons)

        self.status_label = QLabel(t("coh.hint"))
        self.status_label.setWordWrap(True)
        lay.addWidget(self.status_label)

        self.table = QTableWidget(0, _COLS)
        self.table.setHorizontalHeaderLabels([
            t("coh.col_domain"), t("coh.col_severity"), t("coh.col_count"),
            t("coh.col_examples"), t("coh.col_module")])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(
            self.table.editTriggers() & ~self.table.EditTrigger.DoubleClicked)
        lay.addWidget(self.table, 1)

        track(self, "coherence", (1080, 640))

    def _pick_folder(self):
        from PyQt6.QtWidgets import QFileDialog
        path = QFileDialog.getExistingDirectory(
            self, t("yamlcheck.scenario"), self.path_edit.text() or ".")
        if path:
            self.path_edit.setText(path)

    def _analyze(self):
        if self._running:
            return
        root = self.path_edit.text().strip()
        if not root:
            self.status_label.setText(t("yamlcheck.need_scenario"))
            return
        self._running = True
        self.btn_run.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.status_label.setText(t("coh.running"))
        vanilla = ""
        try:
            from core.settings import get_vanilla_content_path
            vanilla = get_vanilla_content_path()
        except Exception:                        # noqa: BLE001 - optionnel
            pass

        def work():
            return run_coherence_audit(root, vanilla)

        async_call(self, work, on_done=self._done, on_fail=self._on_fail,
                   name="coherence")

    def _on_fail(self, exc: Exception):
        self._running = False
        self.btn_run.setEnabled(True)
        self.status_label.setText(f"{t('yamlcheck.failed')} ({exc})")

    def _done(self, rep):
        self._running = False
        self.btn_run.setEnabled(True)
        self.btn_export.setEnabled(True)
        self._report = rep
        sev_key = {"error": "coh.sev_error", "warning": "coh.sev_warning",
                   "info": "coh.sev_info"}
        order = {"error": 0, "warning": 1, "info": 2}
        rows = sorted(rep.findings, key=lambda f: order[f.severity])
        self.table.setRowCount(len(rows))
        for r, f in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(t(f.section)))
            sev = QTableWidgetItem(t(sev_key[f.severity]))
            if f.severity == "error":
                sev.setForeground(self.palette().color(
                    self.palette().ColorRole.BrightText))
            self.table.setItem(r, 1, sev)
            n = QTableWidgetItem(str(f.count))
            n.setTextAlignment(Qt.AlignmentFlag.AlignRight
                               | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(r, 2, n)
            self.table.setItem(r, 3, QTableWidgetItem(f.detail[:300]))
            self.table.setItem(r, 4, QTableWidgetItem(t(f.fix_tool)))
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch)
        self.status_label.setText(
            t("coh.done", e=rep.errors, w=rep.warnings,
              s=f"{rep.seconds:.0f}"))

    def _export_csv(self):
        if not self._report:
            return
        base_dir = self.path_edit.text().strip() or str(Path.home())
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
        out, _ = QFileDialog.getSaveFileName(
            self, t("market.export"),
            str(Path(base_dir) / f"coherence_{stamp}.csv"), "CSV (*.csv)")
        if not out:
            return
        with open(out, "w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh, delimiter=";")
            writer.writerow([t("coh.col_domain"), t("coh.col_severity"),
                             t("coh.col_count"), t("coh.col_examples"),
                             t("coh.col_module")])
            for f in self._report.findings:
                writer.writerow([t(f.section), t(_SEV_KEY[f.severity]),
                                 f.count, " ; ".join(f.items[:12]),
                                 t(f.fix_tool)])
        self.status_label.setText(t("market.csv_done", path=out))
