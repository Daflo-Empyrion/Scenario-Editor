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

"""Prix marche : met chaque MarketPrice en face du cout de fabrication de
l'objet (moteur : core/market_balance.py). Table triable et cochable —
RIEN n'est précoché ; le bouton « hors bornes » coche les FABRIQUABLES
seuls (les statuts de repli — template de groupe, cousin, materiau — ne
s'appliquent qu'a la main, un par un). Application avec backup central,
re-scan automatique pour converger."""
from __future__ import annotations

import csv
import datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
                             QFileDialog, QHBoxLayout, QHeaderView, QLabel,
                             QLineEdit, QPushButton, QTableWidget,
                             QTableWidgetItem, QTextBrowser,
                             QVBoxLayout)
from gui.theme import icon

from core.i18n import t
from core.market_balance import (FABRIQUABLE, NON_VENDABLE, MarketIndex,
                                 MarketReport, apply_recipes, apply_changes,
                                 build_report, load_index, make_changes,
                                 plan_recipes, retarget,
                                 single_input_suspects)
from core.settings import get_vanilla_content_path
from gui.ewa_async import async_call
from gui.theme import icon
from gui.msgboxes import ask_yes_no, info
from gui.window_geometry import track

_COLS = 9          # case, nom, type, statut, prix, cout, ratio, cible, delta


def _fmt_cost(v: float) -> str:
    """Cout avec 2 decimales utiles (0.42, 12.5, 1 234) — jamais ecrase a 0."""
    text = f"{v:,.2f}".replace(",", " ")
    return text.rstrip("0").rstrip(".") or "0"


class _NumItem(QTableWidgetItem):
    """Item numerique : tri par VALEUR (le tri texte mettrait 999 > 1000)."""

    def __lt__(self, other):
        a = self.data(Qt.ItemDataRole.UserRole)
        b = other.data(Qt.ItemDataRole.UserRole)
        if a is None:
            return True
        if b is None:
            return False
        return a < b


class MarketPriceDialog(QDialog):
    """Equilibrage des MarketPrice par le cout de fabrication."""

    def __init__(self, parent, working_root: str = ""):
        super().__init__(parent)
        self.setWindowTitle(t("market.title"))
        self._running = False
        self._idx: MarketIndex | None = None
        self._report: MarketReport | None = None
        self._by_name: dict = {}

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
        params.addWidget(QLabel(t("market.margin")))
        self.spin_margin = QDoubleSpinBox()
        self.spin_margin.setRange(0.1, 10.0)
        self.spin_margin.setDecimals(2)
        self.spin_margin.setSingleStep(0.05)
        self.spin_margin.setValue(1.0)
        self.spin_margin.setToolTip(t("market.margin.tip"))
        params.addWidget(self.spin_margin)
        params.addWidget(QLabel(t("market.fab")))
        self.spin_fab = QDoubleSpinBox()
        self.spin_fab.setRange(0.0, 500.0)
        self.spin_fab.setDecimals(0)
        self.spin_fab.setSingleStep(5.0)
        self.spin_fab.setSuffix(" %")
        self.spin_fab.setValue(0.0)
        self.spin_fab.setToolTip(t("market.fab.tip"))
        params.addWidget(self.spin_fab)
        params.addSpacing(12)
        params.addWidget(QLabel(t("market.bounds")))
        self.spin_bmin = QDoubleSpinBox()
        self.spin_bmin.setRange(0.1, 1.0)
        self.spin_bmin.setDecimals(2)
        self.spin_bmin.setSingleStep(0.05)
        self.spin_bmin.setValue(0.80)
        self.spin_bmin.setToolTip(t("market.bound.tip"))
        params.addWidget(self.spin_bmin)
        self.spin_bmax = QDoubleSpinBox()
        self.spin_bmax.setRange(1.0, 10.0)
        self.spin_bmax.setDecimals(2)
        self.spin_bmax.setSingleStep(0.05)
        self.spin_bmax.setValue(1.25)
        self.spin_bmax.setToolTip(t("market.bound.tip"))
        params.addWidget(self.spin_bmax)
        params.addStretch(1)
        self.btn_run = QPushButton(t("market.analyze"))
        self.btn_run.clicked.connect(self._analyze)
        params.addWidget(self.btn_run)
        self.btn_info = QPushButton(icon("fa5s.question-circle", "#4a7dfc"),
                                    t("market.info"))
        self.btn_info.setToolTip(t("market.info.tip"))
        self.btn_info.setObjectName("secondaryButton")
        self.btn_info.clicked.connect(self._show_info)
        params.addWidget(self.btn_info)
        lay.addLayout(params)

        # -------------------------------------------------- filtres
        filters = QHBoxLayout()
        self.cmb_status = QComboBox()
        self.cmb_status.addItem(t("market.filter_priced"), "__priced__")
        for s in ("fabriquable", "groupe", "cousin", "materiau", "famille",
                  "ancrage", "non_vendable"):
            self.cmb_status.addItem(t(f"market.status.{s}"), s)
        self.cmb_status.addItem(t("market.filter_all"), "__all__")
        self.cmb_status.currentIndexChanged.connect(self._refilter)
        filters.addWidget(self.cmb_status)
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText(t("market.filter_name"))
        self.edit_name.textChanged.connect(self._refilter)
        filters.addWidget(self.edit_name, 1)
        self.chk_oob = QCheckBox(t("market.outofbounds_only"))
        self.chk_oob.toggled.connect(self._refilter)
        filters.addWidget(self.chk_oob)
        lay.addLayout(filters)

        # ---------------------------------------------------- table
        self.table = QTableWidget(0, _COLS)
        self.table.setHorizontalHeaderLabels([
            "", t("market.col_name"), t("market.col_type"),
            t("market.col_status"), t("market.col_price"),
            t("market.col_cost"), t("market.col_ratio"),
            t("market.col_target"), t("market.col_delta")])
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 34)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        lay.addWidget(self.table, 1)

        # -------------------------------------------------- boutons
        buttons = QHBoxLayout()
        self.btn_oob = QPushButton(t("market.check_outofbounds"))
        self.btn_oob.setToolTip(t("market.check_outofbounds.tip"))
        self.btn_oob.clicked.connect(self._check_outofbounds)
        self.btn_oob.setEnabled(False)
        buttons.addWidget(self.btn_oob)
        self.btn_check_all = QPushButton(t("market.check_all"))
        self.btn_check_all.setToolTip(t("market.check_all.tip"))
        self.btn_check_all.clicked.connect(self._check_all)
        self.btn_check_all.setEnabled(False)
        buttons.addWidget(self.btn_check_all)
        self.btn_uncheck = QPushButton(t("market.uncheck_all"))
        self.btn_uncheck.clicked.connect(self._uncheck_all)
        self.btn_uncheck.setEnabled(False)
        buttons.addWidget(self.btn_uncheck)
        self.btn_export = QPushButton(t("market.export"))
        self.btn_export.clicked.connect(self._export_csv)
        self.btn_export.setEnabled(False)
        buttons.addWidget(self.btn_export)
        self.btn_gen = QPushButton(t("market.gen"))
        self.btn_gen.setToolTip(t("market.gen.tip"))
        self.btn_gen.clicked.connect(self._generate)
        self.btn_gen.setEnabled(False)
        buttons.addWidget(self.btn_gen)
        buttons.addStretch(1)
        self.btn_apply = QPushButton(t("market.apply"))
        self.btn_apply.clicked.connect(self._apply)
        self.btn_apply.setEnabled(False)
        buttons.addWidget(self.btn_apply)
        lay.addLayout(buttons)

        self.status_label = QLabel("")
        lay.addWidget(self.status_label)
        self._plans = []

        for spin in (self.spin_margin, self.spin_fab):
            spin.valueChanged.connect(self._retarget)
        for spin in (self.spin_bmin, self.spin_bmax):
            spin.valueChanged.connect(self._refilter)
        track(self, "market_price", (1280, 720))

    # ------------------------------------------------------- infos

    def _build_info_dialog(self) -> QDialog:
        """Fenetre de comprehension : consequences DES VALEURS CHOISIES
        (marge/fabrication des spins) + regles du module."""
        margin = self.spin_margin.value()
        fab = self.spin_fab.value()
        mult = margin * (1.0 + fab / 100.0)
        zero = abs(mult - 1.0) < 1e-9
        drift5 = f"{mult ** 5:.2f}".rstrip("0").rstrip(".")
        html = t("market.info_html",
                 margin=f"{margin:g}", fab=f"{fab:g}",
                 mult=f"{mult:.2f}".rstrip("0").rstrip("."),
                 profit=f"{round((mult - 1) * 100, 2):g}", drift5=drift5,
                 loop=(t("market.info_zero") if zero
                       else t("market.info_loop")),
                 drift=(t("market.info_drift_zero", drift5=drift5) if zero
                        else t("market.info_drift", drift5=drift5)))
        dlg = QDialog(self)
        dlg.setWindowTitle(t("market.info"))
        lay = QVBoxLayout(dlg)
        tb = QTextBrowser()
        tb.setHtml(html)
        dlg._html = html
        lay.addWidget(tb)
        btn = QPushButton(t("btn.close"))
        btn.clicked.connect(dlg.accept)
        lay.addWidget(btn)
        track(dlg, "market_info", (780, 660))
        return dlg

    def _show_info(self):
        self._build_info_dialog().exec()

    # ----------------------------------------------------------- scan

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
            self.status_label.setText(t("yamlcheck.need_scenario"))
            return
        self._running = True
        self.btn_run.setEnabled(False)
        self.status_label.setText(t("market.running"))
        vanilla = get_vanilla_content_path() or ""
        margin, fab = self.spin_margin.value(), self.spin_fab.value()

        def work():
            idx, van = load_index(root, vanilla)
            return idx, van, build_report(idx, van, margin=margin,
                                          fab_pct=fab)

        async_call(self, work,
                   on_done=lambda res: self._on_analyzed(*res),
                   on_fail=self._on_fail, name="market-price")

    def _on_fail(self, exc: Exception):
        self._running = False
        self.btn_run.setEnabled(True)
        self.status_label.setText(f"{t('yamlcheck.failed')}  ({exc})")

    def _on_analyzed(self, idx: MarketIndex, _van, report: MarketReport):
        self._running = False
        self.btn_run.setEnabled(True)
        self._idx = idx
        self._report = report
        self._by_name = {e.name: e for e in report.entries}
        self._fill_table()
        n_changes = sum(1 for e in report.entries
                        if e.target is not None and e.price != e.target)
        self._plans, skipped = plan_recipes(idx, report)
        n_sus = len(single_input_suspects(idx, report))
        self.status_label.setText(t(
            "market.done", n=len(report.entries),
            f=sum(1 for e in report.entries if e.price is not None),
            c=report.counts.get(FABRIQUABLE, 0), k=n_changes)
            + " " + t("market.suspects_note", n=n_sus)
            + " " + t("market.gen_count", n=len(self._plans),
                      s=len(skipped)))
        for b in (self.btn_oob, self.btn_check_all, self.btn_uncheck,
                  self.btn_export, self.btn_apply):
            b.setEnabled(True)
        self.btn_gen.setEnabled(bool(self._plans))

    # ---------------------------------------------------------- table

    def _fill_table(self):
        rep = self._report
        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(len(rep.entries))
        for row, e in enumerate(rep.entries):
            self._set_row(row, e)
        self.table.setUpdatesEnabled(True)
        self.table.setSortingEnabled(True)
        self._refilter()

    def _name_at(self, row: int) -> str:
        """Nom de la ligne lu depuis la table — reste exact meme apres un
        tri (les lignes se deplacent, self._row_names serait desynchronise)."""
        it = self.table.item(row, 1)
        return it.text() if it else ""

    def _set_row(self, row: int, e):
        """(Re)ecrit une ligne depuis l'entree — aussi utilisee par le
        retarget (maj cible/delta sans re-parse)."""
        t_ = self.table
        checkable = (e.target is not None and e.target != e.price
                     and e.status != NON_VENDABLE)
        old = t_.item(row, 0)
        prev_state = (old.checkState() if old is not None and
                      (old.flags() & Qt.ItemFlag.ItemIsUserCheckable)
                      else None)
        it = QTableWidgetItem()
        if checkable:
            it.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            # un retarget reecrit la ligne : ne jamais perdre les cochages
            it.setCheckState(prev_state or Qt.CheckState.Unchecked)
        else:
            it.setFlags(Qt.ItemFlag.ItemIsEnabled)
        t_.setItem(row, 0, it)
        t_.setItem(row, 1, QTableWidgetItem(e.name))
        typ = t("market.type_block") if e.kind == "block" else t("market.type_item")
        t_.setItem(row, 2, QTableWidgetItem(typ))
        status_item = QTableWidgetItem(t(f"market.status.{e.status}"))
        status_item.setToolTip(e.detail or status_item.text())
        t_.setItem(row, 3, status_item)
        self._num(row, 4, e.price)
        # cout affiche avec 2 decimales significatives : une munition a un
        # cout unitaire de 0.42 — l'arrondi entier affichait "0"
        self._num(row, 5, e.cost, fmt=_fmt_cost)
        ratio = (e.price / e.cost) if (e.price and e.cost) else None
        self._num(row, 6, round(ratio, 2) if ratio is not None else None,
                  fmt=lambda v: f"{v:g}")
        self._num(row, 7, e.target)
        delta = (None if (e.target is None or not e.price)
                 else round((e.target - e.price) / e.price * 100))
        self._num(row, 8, delta, fmt=lambda v: f"{v:+d}%")

    def _num(self, row: int, col: int, value, fmt=None):
        it = _NumItem()
        if value is None:
            it.setText("—")
        else:
            it.setData(Qt.ItemDataRole.UserRole, float(value))
            it.setText(fmt(value) if fmt else f"{value:,.0f}".replace(",", " "))
        self.table.setItem(row, col, it)

    def _refilter(self):
        """Masque les lignes selon filtres — jamais de re-fill (4364 lignes)."""
        if self._report is None:
            return
        want = self.cmb_status.currentData()
        needle = self.edit_name.text().strip().lower()
        oob_only = self.chk_oob.isChecked()
        bmin, bmax = self.spin_bmin.value(), self.spin_bmax.value()
        total = self.table.rowCount()
        hidden = 0
        for row in range(total):
            name = self._name_at(row)
            e = self._by_name.get(name)
            if e is None:
                continue
            ratio = (e.price / e.cost) if (e.price and e.cost) else None
            show = ((want == "__all__" or (want == "__priced__"
                    and e.status != NON_VENDABLE) or e.status == want)
                    and (not needle or needle in name.lower())
                    and (not oob_only or (ratio is not None
                                          and not bmin <= ratio <= bmax)))
            self.table.setRowHidden(row, not show)
            hidden += not show
        self.status_label.setText(t("market.visible", n=total - hidden))

    # ------------------------------------------------------ actions

    def _checked_names(self) -> set:
        names = set()
        for row in range(self.table.rowCount()):
            if self.table.isRowHidden(row):
                continue
            it = self.table.item(row, 0)
            if (it is not None and it.flags() & Qt.ItemFlag.ItemIsUserCheckable
                    and it.checkState() == Qt.CheckState.Checked):
                name = self._name_at(row)
                if name:
                    names.add(name)
        return names

    def _check_outofbounds(self):
        """Coche les FABRIQUABLES hors bornes — les statuts de repli
        (groupe, cousin, materiau) restent a cocher a la main."""
        bmin, bmax = self.spin_bmin.value(), self.spin_bmax.value()
        n = 0
        for row in range(self.table.rowCount()):
            it = self.table.item(row, 0)
            e = self._by_name.get(self._name_at(row))
            if (e is None or e.status != FABRIQUABLE or it is None
                    or e.price is None or e.cost is None):
                continue
            if not bmin <= e.price / e.cost <= bmax:
                it.setCheckState(Qt.CheckState.Checked)
                n += 1
        self.status_label.setText(t("market.checked_oob", n=n))

    def _check_all(self):
        """Coche toutes les lignes VISIBLES cochables — les filtres actifs
        (statut, nom, hors bornes) delimitent donc la selection en masse."""
        n = 0
        for row in range(self.table.rowCount()):
            if self.table.isRowHidden(row):
                continue
            it = self.table.item(row, 0)
            if (it is not None
                    and it.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                it.setCheckState(Qt.CheckState.Checked)
                n += 1
        self.status_label.setText(t("market.checked_all", n=n))

    def _uncheck_all(self):
        for row in range(self.table.rowCount()):
            it = self.table.item(row, 0)
            if it is not None:
                it.setCheckState(Qt.CheckState.Unchecked)

    def _retarget(self):
        """Un parametre bouge : nouvelles cibles SANS re-parse (CPU pur)."""
        if self._report is None or self._idx is None:
            return
        retarget(self._report, self._idx, margin=self.spin_margin.value(),
                 fab_pct=self.spin_fab.value())
        self.table.setUpdatesEnabled(False)
        for row in range(self.table.rowCount()):
            name = self._name_at(row)
            e = self._by_name.get(name)
            if e is not None:
                self._set_row(row, e)
        self.table.setUpdatesEnabled(True)

    def _apply(self):
        if self._running or self._report is None or self._idx is None:
            return
        names = self._checked_names()
        if not names:
            info(self, t("market.title"), t("market.apply_none"))
            return
        if not ask_yes_no(self, t("market.title"),
                          t("market.apply_confirm", n=len(names))):
            return
        self._running = True
        self.btn_apply.setEnabled(False)
        idx, report = self._idx, self._report

        def work():
            changes = make_changes(idx, report, names)
            return apply_changes(changes), len(changes)

        def _done(res):
            self._running = False
            self.btn_apply.setEnabled(True)
            info(self, t("market.title"),
                 t("market.applied", n=res[1]))
            self._analyze()          # re-scan : convergence des cascades

        async_call(self, work, on_done=_done, on_fail=self._on_fail,
                   name="market-apply")

    def _generate(self):
        """Ecrit les recettes generees (matieres de famille dosees pour
        atteindre la cible de prix) dans Templates.ecf."""
        if self._running or not self._plans:
            return
        if not ask_yes_no(self, t("market.title"),
                          t("market.gen_confirm", n=len(self._plans))):
            return
        self._running = True
        self.btn_gen.setEnabled(False)
        plans, root = self._plans, self.path_edit.text().strip()

        def work():
            return apply_recipes(plans, root)

        def _done(res):
            self._running = False
            self.btn_gen.setEnabled(True)
            info(self, t("market.title"),
                 t("market.gen_done", n=res[1], path=res[0]))
            self._analyze()

        async_call(self, work, on_done=_done, on_fail=self._on_fail,
                   name="market-gen")

    def _export_csv(self):
        """Export CSV point-virgule UTF-8 BOM (comme le bilan lancement)."""
        if not self._report:
            return
        base_dir = self.path_edit.text().strip() or str(Path.home())
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
        out, _ = QFileDialog.getSaveFileName(
            self, t("market.export"),
            str(Path(base_dir) / f"prix_marche_{stamp}.csv"), "CSV (*.csv)")
        if not out:
            return
        with open(out, "w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh, delimiter=";")
            writer.writerow(t("market.csv_headers").split(";"))
            for e in sorted(self._report.entries, key=lambda x: x.name):
                ratio = (round(e.price / e.cost, 3)
                         if (e.price and e.cost) else "")
                writer.writerow([e.name, e.kind,
                                 t(f"market.status.{e.status}"),
                                 e.price if e.price is not None else "",
                                 round(e.cost, 2) if e.cost is not None else "",
                                 ratio,
                                 e.target if e.target is not None else "",
                                 e.detail])
            for s in single_input_suspects(self._idx, self._report):
                writer.writerow(["#SUSPECT", s["template"], s["input"],
                                 s["qty"], s["input_price"], s["output"]])
        self.status_label.setText(t("market.csv_done", path=out))
