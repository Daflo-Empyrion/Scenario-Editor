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

"""Audit economique des marchands : analyse TraderNPCConfig face aux
MarketPrice et propose, cochable, l'uniformisation des lignes (mf= vente /
rachat reglables), les rachats manquants et les MarketPrice absents.
Tableau de bord : boucles d'argent (avec clamp moteur) et disparites.
RIEN n'est precoche ; l'application sauvegarde (backup central) puis
re-scanne automatiquement. Marche sur n'importe quel scenario."""
from __future__ import annotations

import csv
import datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox,
                             QFileDialog, QHBoxLayout, QHeaderView, QLabel,
                             QLineEdit, QPushButton, QSpinBox, QTableWidget,
                             QTableWidgetItem, QVBoxLayout)

from core.i18n import t
from core.trader_audit import (BROKEN, MF_NO_PRICE, NO_BUY, UNIFORM, ZERO,
                               TraderConfigDoc, analyze_traders, apply_traders)
from gui.ewa_async import async_call
from gui.msgboxes import ask_yes_no, info
from gui.window_geometry import track

_COLS = 6          # case, marchand, ligne, item, probleme, proposition


class _CkItem(QTableWidgetItem):
    """Case a cocher d'une ligne : porte l'index de la proposition."""

    def __init__(self, idx: int, checkable: bool):
        super().__init__()
        self.prop_idx = idx
        if checkable:
            self.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            self.setCheckState(Qt.CheckState.Unchecked)
        else:
            self.setFlags(Qt.ItemFlag.ItemIsEnabled)


class TraderAuditDialog(QDialog):
    """Controle des marchands : analyse + corrections cochables."""

    def __init__(self, parent, working_root: str = ""):
        super().__init__(parent)
        self.setWindowTitle(t("taudit.title"))
        self._running = False
        self._doc: TraderConfigDoc | None = None
        self._report = None
        self._proposals: list = []

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

        # ------------------------------------------------ parametres
        params = QHBoxLayout()
        params.addWidget(QLabel(t("taudit.sell")))
        self.spin_sell_lo = self._spin(0.1, 10.0, 1.0, 2)
        self.spin_sell_hi = self._spin(0.1, 10.0, 1.25, 2)
        params.addWidget(self.spin_sell_lo)
        params.addWidget(QLabel("–"))
        params.addWidget(self.spin_sell_hi)
        params.addSpacing(10)
        params.addWidget(QLabel(t("taudit.buy")))
        self.spin_buy_lo = self._spin(0.1, 5.0, 0.5, 2)
        self.spin_buy_hi = self._spin(0.1, 5.0, 0.75, 2)
        params.addWidget(self.spin_buy_lo)
        params.addWidget(QLabel("–"))
        params.addWidget(self.spin_buy_hi)
        params.addSpacing(10)
        params.addWidget(QLabel(t("taudit.fallback")))
        self.spin_fallback = QSpinBox()
        self.spin_fallback.setRange(1, 1_000_000)
        self.spin_fallback.setValue(100)
        self.spin_fallback.setToolTip(t("taudit.fallback.tip"))
        params.addWidget(self.spin_fallback)
        params.addStretch(1)
        self.btn_run = QPushButton(t("taudit.analyze"))
        self.btn_run.clicked.connect(self._analyze)
        params.addWidget(self.btn_run)
        lay.addLayout(params)

        self.stats_label = QLabel("")
        self.stats_label.setWordWrap(True)
        lay.addWidget(self.stats_label)

        # -------------------------------------------------- filtres
        filters = QHBoxLayout()
        self.cmb_kind = QComboBox()
        self.cmb_kind.addItem(t("taudit.filter_all"), "__all__")
        for k, label in ((UNIFORM, "taudit.kind_uniform"),
                         (NO_BUY, "taudit.kind_no_buy"),
                         (ZERO, "taudit.kind_zero"),
                         (MF_NO_PRICE, "taudit.kind_mf_no_price"),
                         (BROKEN, "taudit.kind_broken")):
            self.cmb_kind.addItem(t(label), k)
        self.cmb_kind.currentIndexChanged.connect(self._refilter)
        filters.addWidget(self.cmb_kind)
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText(t("taudit.filter_name"))
        self.edit_name.textChanged.connect(self._refilter)
        filters.addWidget(self.edit_name, 1)
        lay.addLayout(filters)

        # ---------------------------------------------------- table
        self.table = QTableWidget(0, _COLS)
        self.table.setHorizontalHeaderLabels([
            "", t("taudit.col_trader"), t("taudit.col_line"),
            t("taudit.col_item"), t("taudit.col_problem"),
            t("taudit.col_proposal")])
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 34)
        for col in (1, 3):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
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
        self.btn_apply = QPushButton(t("taudit.apply"))
        self.btn_apply.clicked.connect(self._apply)
        self.btn_apply.setEnabled(False)
        buttons.addWidget(self.btn_apply)
        lay.addLayout(buttons)

        self.status_label = QLabel("")
        lay.addWidget(self.status_label)

        # un parametre bouge : re-analyse async avec les nouvelles bornes
        for spin in (self.spin_sell_lo, self.spin_sell_hi,
                     self.spin_buy_lo, self.spin_buy_hi, self.spin_fallback):
            spin.valueChanged.connect(self._params_changed)
        track(self, "trader_audit", (1200, 700))

    @staticmethod
    def _spin(lo: float, hi: float, val: float, dec: int) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setDecimals(dec)
        s.setSingleStep(0.05)
        s.setValue(val)
        return s

    # ----------------------------------------------------------- scan

    def _pick_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, t("yamlcheck.scenario"), self.path_edit.text() or ".")
        if path:
            self.path_edit.setText(path)

    def _params_changed(self):
        if self._report is None:
            return
        if self._running:
            self._dirty = True      # relance a la fin de l'analyse en cours
        else:
            self._analyze()          # bornes nouvelles -> nouvelles unif.

    def _analyze(self):
        if self._running:
            return
        root = self.path_edit.text().strip()
        if not root:
            self.status_label.setText(t("yamlcheck.need_scenario"))
            return
        self._running = True
        self.btn_run.setEnabled(False)
        self.status_label.setText(t("taudit.running"))
        sell = (self.spin_sell_lo.text().replace(",", "."),
                self.spin_sell_hi.text().replace(",", "."))
        buy = (self.spin_buy_lo.text().replace(",", "."),
               self.spin_buy_hi.text().replace(",", "."))

        def work():
            return analyze_traders(root, sell=sell, buy=buy,
                                   fallback_price=self.spin_fallback.value())

        async_call(self, work,
                   on_done=lambda res: self._on_analyzed(*res),
                   on_fail=self._on_fail, name="trader-audit")

    def _on_fail(self, exc: Exception):
        self._running = False
        self.btn_run.setEnabled(True)
        self.status_label.setText(f"{t('yamlcheck.failed')}  ({exc})")

    def _on_analyzed(self, doc, _idx, report):
        self._running = False
        self.btn_run.setEnabled(True)
        self._doc = doc
        self._report = report
        self._proposals = report.proposals
        self._fill_table()
        d = report.dashboard
        n_fix = sum(1 for p in self._proposals if p.new_line or p.new_price)
        self.stats_label.setText(t(
            "taudit.stats", traders=d.n_traders, lines=d.n_lines,
            tokens=d.n_tokens, cur=d.n_currency, fixes=n_fix,
            arb=len(d.arbitrages), disp=f"{d.max_disparity:.1f}"))
        tip = "\n".join(d.arbitrages[:8] + d.disparities[:8])
        if tip:
            self.stats_label.setToolTip(tip)
        for b in (self.btn_all, self.btn_none, self.btn_export, self.btn_apply):
            b.setEnabled(True)
        if getattr(self, "_dirty", False):
            self._dirty = False
            self._analyze()          # parametres changes pendant l'analyse

    # ---------------------------------------------------------- table

    def _fill_table(self):
        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(len(self._proposals))
        for row, p in enumerate(self._proposals):
            checkable = p.new_line is not None or p.new_price is not None
            self.table.setItem(row, 0, _CkItem(row, checkable))
            self._txt(row, 1, p.trader)
            self._txt(row, 2, p.item_key or "—")
            self._txt(row, 3, p.item)
            self._txt(row, 4, f"{t(f'taudit.kind_{p.kind}')} — {p.detail}")
            proposal = (p.new_line.render(quote=False) if p.new_line
                        else (f"MarketPrice: {p.new_price}"
                              if p.new_price else "—"))
            self._txt(row, 5, proposal)
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
        want = self.cmb_kind.currentData()
        needle = self.edit_name.text().strip().lower()
        visible = 0
        for row in range(self.table.rowCount()):
            ck = self.table.item(row, 0)
            p = self._proposals[ck.prop_idx]
            show = ((want == "__all__" or p.kind == want)
                    and (not needle or needle in p.trader.lower()
                         or needle in p.item.lower()))
            self.table.setRowHidden(row, not show)
            visible += show
        self.status_label.setText(t("market.visible", n=visible))

    # ------------------------------------------------------ actions

    def _checked(self) -> list:
        out = []
        for row in range(self.table.rowCount()):
            if self.table.isRowHidden(row):
                continue
            it = self.table.item(row, 0)
            if (isinstance(it, _CkItem) and it.flags() & Qt.ItemFlag.ItemIsUserCheckable
                    and it.checkState() == Qt.CheckState.Checked):
                out.append(self._proposals[it.prop_idx])
        return out

    def _check_all(self):
        """Coche les lignes VISIBLES cochables (filtres = selection ciblee)."""
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
        if self._running or self._report is None or self._doc is None:
            return
        checked = self._checked()
        if not checked:
            info(self, t("taudit.title"), t("market.apply_none"))
            return
        if not ask_yes_no(self, t("taudit.title"),
                          t("taudit.apply_confirm", n=len(checked))):
            return
        self._running = True
        self.btn_apply.setEnabled(False)
        root = self.path_edit.text().strip()
        doc, report, sell, buy = (self._doc, self._report,
                                  (self.spin_sell_lo.text().replace(",", "."),
                                   self.spin_sell_hi.text().replace(",", ".")),
                                  (self.spin_buy_lo.text().replace(",", "."),
                                   self.spin_buy_hi.text().replace(",", ".")))

        def work():
            return apply_traders(root, doc, report, checked,
                                 sell=sell, buy=buy)

        def _done(res):
            self._running = False
            self.btn_apply.setEnabled(True)
            info(self, t("taudit.title"),
                 t("taudit.applied", n=sum(res.values())))
            self._analyze()          # re-scan : convergence des cascades

        async_call(self, work, on_done=_done, on_fail=self._on_fail,
                   name="trader-apply")

    def _export_csv(self):
        """Export CSV point-virgule UTF-8 BOM (comme le bilan lancement)."""
        if not self._report:
            return
        base_dir = self.path_edit.text().strip() or str(Path.home())
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
        out, _ = QFileDialog.getSaveFileName(
            self, t("market.export"),
            str(Path(base_dir) / f"audit_marchands_{stamp}.csv"), "CSV (*.csv)")
        if not out:
            return
        with open(out, "w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh, delimiter=";")
            writer.writerow(t("taudit.csv_headers").split(";"))
            for p in self._proposals:
                proposal = (p.new_line.render(quote=False) if p.new_line
                            else (f"MarketPrice: {p.new_price}"
                                  if p.new_price else ""))
                writer.writerow([p.trader, p.item_key, p.item,
                                 t(f"taudit.kind_{p.kind}"), p.detail,
                                 p.current, proposal])
        self.status_label.setText(t("market.csv_done", path=out))
