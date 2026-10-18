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

"""Equilibrage par correlations : chaque propriete (Mass, HitPoints,
Damage, ShieldCapacity) comparee a la MEDIANE DE SON GROUPE (template
effectif, famille x tier, classe x tier) — le design par famille est
preserve, seules les incoherences internes sont proposees, COCHABLES.
Whitelist design volontaire (lest, effets, decor) : badge, jamais
propose. Rien n'est precoche ; application avec backup central puis
re-scan (les medianes bougent apres ecriture)."""
from __future__ import annotations

import csv
import datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QComboBox, QDialog, QFileDialog, QHBoxLayout,
                             QHeaderView, QLabel, QLineEdit, QPushButton,
                             QTableWidget, QTableWidgetItem, QVBoxLayout)

from core.correlation_balance import (OK, OUTLIER, SPECS, WHITELIST,
                                      analyze_correlations, apply_changes,
                                      make_changes)
from core.i18n import t
from gui.ewa_async import async_call
from gui.msgboxes import ask_yes_no, info
from gui.window_geometry import track

_COLS = 8   # case, nom, type, groupe, statut, valeur, reference, cible


class _CkItem(QTableWidgetItem):
    def __init__(self, idx: int, checkable: bool):
        super().__init__()
        self.prop_idx = idx
        if checkable:
            self.setFlags(Qt.ItemFlag.ItemIsUserCheckable
                          | Qt.ItemFlag.ItemIsEnabled)
            self.setCheckState(Qt.CheckState.Unchecked)
        else:
            self.setFlags(Qt.ItemFlag.ItemIsEnabled)


class CorrelationDialog(QDialog):
    def __init__(self, parent, working_root: str = ""):
        super().__init__(parent)
        self.setWindowTitle(t("corr.title"))
        self._running = False
        self._idx = None
        self._report = None
        self._proposals: list = []
        self._pinned = None       # medianes epinglenees (anti-ratchet)

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

        params = QHBoxLayout()
        params.addWidget(QLabel(t("corr.property")))
        self.cmb_spec = QComboBox()
        for key in SPECS:
            self.cmb_spec.addItem(t(f"corr.spec_{key}"), key)
        self.cmb_spec.currentIndexChanged.connect(self._spec_changed)
        params.addWidget(self.cmb_spec)
        params.addStretch(1)
        self.btn_run = QPushButton(t("corr.analyze"))
        self.btn_run.clicked.connect(self._analyze)
        params.addWidget(self.btn_run)
        lay.addLayout(params)

        self.stats_label = QLabel("")
        self.stats_label.setWordWrap(True)
        lay.addWidget(self.stats_label)

        filters = QHBoxLayout()
        self.cmb_status = QComboBox()
        self.cmb_status.addItem(t("corr.filter_outliers"), OUTLIER)
        self.cmb_status.addItem(t("corr.filter_all"), "__all__")
        for st in (OK, WHITELIST):
            self.cmb_status.addItem(t(f"corr.status_{st}"), st)
        self.cmb_status.currentIndexChanged.connect(self._refilter)
        filters.addWidget(self.cmb_status)
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText(t("taudit.filter_name"))
        self.edit_name.textChanged.connect(self._refilter)
        filters.addWidget(self.edit_name, 1)
        lay.addLayout(filters)

        self.table = QTableWidget(0, _COLS)
        self.table.setHorizontalHeaderLabels([
            "", t("corr.col_name"), t("market.col_type"),
            t("corr.col_group"), t("taudit.col_problem"),
            t("corr.col_value"), t("corr.col_reference"),
            t("market.col_target")])
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 34)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        lay.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        self.btn_all = QPushButton(t("market.check_all"))
        self.btn_all.setToolTip(t("market.check_all.tip"))
        self.btn_all.clicked.connect(self._check_all)
        self.btn_all.setEnabled(False)
        buttons.addWidget(self.btn_all)
        self.btn_none = QPushButton(t("market.uncheck_all"))
        self.btn_none.clicked.connect(self._uncheck_all)
        self.btn_none.setEnabled(False)
        buttons.addWidget(self.btn_none)
        self.btn_export = QPushButton(t("market.export"))
        self.btn_export.clicked.connect(self._export_csv)
        self.btn_export.setEnabled(False)
        buttons.addWidget(self.btn_export)
        buttons.addStretch(1)
        self.btn_apply = QPushButton(t("market.apply"))
        self.btn_apply.clicked.connect(self._apply)
        self.btn_apply.setEnabled(False)
        buttons.addWidget(self.btn_apply)
        lay.addLayout(buttons)

        self.status_label = QLabel("")
        lay.addWidget(self.status_label)
        track(self, "correlation", (1280, 720))

    # ----------------------------------------------------------- scan

    def _pick_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, t("yamlcheck.scenario"), self.path_edit.text() or ".")
        if path:
            self.path_edit.setText(path)

    def _spec_changed(self):
        if self._report is not None:
            self._analyze()      # propriete changee -> nouvelle analyse

    def _analyze(self, fresh: bool = True):
        """fresh=True (bouton, changement de propriete) : medianes
        recalculees. fresh=False (re-scan APRES application) : medianes
        EPINGLEES de l'analyse en cours — sinon l'application partielle
        deplacerait la mediane et creerait de nouvelles propositions sur
        les membres non appliques (ratchet vecu 17/10)."""
        if self._running:
            return
        root = self.path_edit.text().strip()
        if not root:
            self.status_label.setText(t("yamlcheck.need_scenario"))
            return
        if fresh:
            self._pinned = None
        self._running = True
        self.btn_run.setEnabled(False)
        self.status_label.setText(t("taudit.running"))
        spec = self.cmb_spec.currentData()
        pinned = dict(self._pinned) if self._pinned else None

        def work():
            return analyze_correlations(root, spec, pinned_medians=pinned)

        async_call(self, work,
                   on_done=lambda res: self._on_analyzed(*res),
                   on_fail=self._on_fail, name="correlation")

    def _on_fail(self, exc: Exception):
        self._running = False
        self.btn_run.setEnabled(True)
        self.status_label.setText(f"{t('yamlcheck.failed')}  ({exc})")

    def _on_analyzed(self, idx, report):
        self._running = False
        self.btn_run.setEnabled(True)
        self._idx = idx
        self._report = report
        self._proposals = report.entries
        if self._pinned is None:       # premiere analyse : on epingle
            self._pinned = dict(report.groups)
        self._fill_table()
        c = report.counts
        self.stats_label.setText(t(
            "corr.stats", prop=t(f"corr.spec_{report.spec_key}"),
            groups=len(report.groups), ok=c.get(OK, 0),
            out=c.get(OUTLIER, 0), wl=c.get(WHITELIST, 0)))
        for b in (self.btn_all, self.btn_none, self.btn_export,
                  self.btn_apply):
            b.setEnabled(True)

    # ---------------------------------------------------------- table

    def _fill_table(self):
        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(len(self._proposals))
        for row, e in enumerate(self._proposals):
            checkable = e.status == OUTLIER and e.target is not None \
                and (e.value is None or abs(e.value - e.target) > 1e-9)
            self.table.setItem(row, 0, _CkItem(row, checkable))
            self._txt(row, 1, e.name)
            self._txt(row, 2, t("market.type_block") if e.kind == "block"
                      else t("market.type_item"))
            self._txt(row, 3, e.group or "—")
            status_item = QTableWidgetItem(t(f"corr.status_{e.status}"))
            status_item.setToolTip(e.detail or status_item.text())
            self.table.setItem(row, 4, status_item)
            self._txt(row, 5, "—" if e.value is None else f"{e.value:g}")
            self._txt(row, 6, "—" if e.reference is None
                      else f"{e.reference:g}")
            self._txt(row, 7, "—" if e.target is None else f"{e.target:g}")
        self.table.setUpdatesEnabled(True)
        self.table.setSortingEnabled(True)
        self._refilter()

    def _txt(self, row: int, col: int, text: str):
        it = QTableWidgetItem(text)
        it.setToolTip(text)
        self.table.setItem(row, col, it)

    def _refilter(self):
        if self._report is None:
            return
        want = self.cmb_status.currentData()
        needle = self.edit_name.text().strip().lower()
        visible = 0
        for row in range(self.table.rowCount()):
            ck = self.table.item(row, 0)
            e = self._proposals[ck.prop_idx]
            show = ((want == "__all__" or e.status == want)
                    and (not needle or needle in e.name.lower()))
            self.table.setRowHidden(row, not show)
            visible += show
        self.status_label.setText(t("market.visible", n=visible))

    # ------------------------------------------------------ actions

    def _checked_names(self) -> set:
        out = set()
        for row in range(self.table.rowCount()):
            if self.table.isRowHidden(row):
                continue
            it = self.table.item(row, 0)
            if (isinstance(it, _CkItem)
                    and it.flags() & Qt.ItemFlag.ItemIsUserCheckable
                    and it.checkState() == Qt.CheckState.Checked):
                out.add(self._proposals[it.prop_idx].name)
        return out

    def _check_all(self):
        n = 0
        for row in range(self.table.rowCount()):
            if self.table.isRowHidden(row):
                continue
            it = self.table.item(row, 0)
            if it is not None and it.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                it.setCheckState(Qt.CheckState.Checked)
                n += 1
        self.status_label.setText(t("market.checked_all", n=n))

    def _uncheck_all(self):
        for row in range(self.table.rowCount()):
            it = self.table.item(row, 0)
            if it is not None:
                it.setCheckState(Qt.CheckState.Unchecked)

    def _apply(self):
        if self._running or self._report is None or self._idx is None:
            return
        names = self._checked_names()
        if not names:
            info(self, t("corr.title"), t("market.apply_none"))
            return
        if not ask_yes_no(self, t("corr.title"),
                          t("taudit.apply_confirm", n=len(names))):
            return
        self._running = True
        self.btn_apply.setEnabled(False)
        idx, report = self._idx, self._report

        def work():
            changes = make_changes(idx, report, names)
            return apply_changes(changes, fmt_int=report.fmt_int), len(changes)

        def _done(res):
            self._running = False
            self.btn_apply.setEnabled(True)
            info(self, t("corr.title"), t("market.applied", n=res[1]))
            # re-scan avec les medianes EPINGLEES : les membres corriges
            # atterrissent exactement sur la cible, zero proposal fantome
            self._analyze(fresh=False)

        async_call(self, work, on_done=_done, on_fail=self._on_fail,
                   name="correlation-apply")

    def _export_csv(self):
        if not self._report:
            return
        base_dir = self.path_edit.text().strip() or str(Path.home())
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
        out, _ = QFileDialog.getSaveFileName(
            self, t("market.export"),
            str(Path(base_dir) / f"correlations_{stamp}.csv"), "CSV (*.csv)")
        if not out:
            return
        with open(out, "w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh, delimiter=";")
            writer.writerow(t("corr.csv_headers").split(";"))
            for e in sorted(self._proposals, key=lambda x: x.name):
                writer.writerow([
                    e.name, e.kind, e.group or "",
                    t(f"corr.status_{e.status}"), e.detail,
                    "" if e.value is None else f"{e.value:g}",
                    "" if e.reference is None else f"{e.reference:g}",
                    "" if e.target is None else f"{e.target:g}"])
        self.status_label.setText(t("market.csv_done", path=out))
