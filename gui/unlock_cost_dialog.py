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

"""Couts de deblocage : equilibre les UnlockCost de l'arbre technologique
(moteur core/unlock_balance.py). Table triable et cochable — RIEN n'est
precode ; application confirmee avec backup central puis re-scan (la
cible est idempotente, le re-scan ne doit rien reproposer)."""
from __future__ import annotations

import csv
import datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog,
                             QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                             QPushButton, QSpinBox, QTableWidget,
                             QTableWidgetItem, QVBoxLayout)

from core.i18n import t
from gui.module_info import add_info_button
from core.settings import get_vanilla_content_path
from core.unlock_balance import UnlockProposal, analyze, apply_proposals
from gui.ewa_async import async_call
from gui.msgboxes import ask_yes_no, info
from gui.window_geometry import track

_COLS = 10   # case, nom, type, famille, niveau, puissance, cout actuel,
             # cible, cout apres, detail


class _NumItem(QTableWidgetItem):
    def __lt__(self, other):
        a = self.data(Qt.ItemDataRole.UserRole)
        b = other.data(Qt.ItemDataRole.UserRole)
        if a is None:
            return True
        if b is None:
            return False
        return a < b


class UnlockCostDialog(QDialog):
    """Equilibrage des UnlockCost de l'arbre technologique."""

    def __init__(self, parent, working_root: str = ""):
        super().__init__(parent)
        self.setWindowTitle(t("unlock.title"))
        self._running = False
        self._proposals: list[UnlockProposal] = []
        self._by_name: dict[str, UnlockProposal] = {}

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
        params.addWidget(QLabel(t("unlock.mini")))
        self.spin_min = QSpinBox()
        self.spin_min.setRange(0, 100_000)
        self.spin_min.setValue(1)
        self.spin_min.setToolTip(t("unlock.mini.tip"))
        params.addWidget(self.spin_min)
        params.addWidget(QLabel(t("unlock.maxi")))
        self.spin_max = QSpinBox()
        self.spin_max.setRange(0, 100_000)
        self.spin_max.setValue(0)
        self.spin_max.setToolTip(t("unlock.maxi.tip"))
        params.addWidget(self.spin_max)
        add_info_button(params, "unlock.info_html")
        params.addStretch(1)
        self.btn_run = QPushButton(t("unlock.analyze"))
        self.btn_run.clicked.connect(lambda: self._analyze())
        params.addWidget(self.btn_run)
        lay.addLayout(params)

        # bornes modifiables par niveau (remplies au premier scan ; une
        # cellule vide herite de la borne globale correspondante)
        self.bounds_label = QLabel(t("unlock.bounds"))
        lay.addWidget(self.bounds_label)
        self.bounds_table = QTableWidget(1, 3)
        self.bounds_table.setHorizontalHeaderLabels([
            t("recipe.col_level"), t("unlock.mini"), t("unlock.maxi")])
        self.bounds_table.verticalHeader().setVisible(False)
        self.bounds_table.setMaximumHeight(150)
        self.bounds_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self._set_bounds_row(0, t("unlock.default_row"), "", "")
        lay.addWidget(self.bounds_table)

        self.stats_label = QLabel("")
        self.stats_label.setWordWrap(True)
        lay.addWidget(self.stats_label)

        filters = QHBoxLayout()
        self.chk_changed = QCheckBox(t("recipe.only_changed"))
        self.chk_changed.setChecked(True)
        self.chk_changed.toggled.connect(self._refilter)
        filters.addWidget(self.chk_changed)
        filters.addWidget(QLabel(t("recipe.filter_family")))
        self.cmb_family = QComboBox()
        self.cmb_family.addItem(t("recipe.family_all"), "__all__")
        self.cmb_family.currentIndexChanged.connect(self._refilter)
        filters.addWidget(self.cmb_family, 1)
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText(t("market.filter_name"))
        self.edit_name.textChanged.connect(self._refilter)
        filters.addWidget(self.edit_name, 1)
        lay.addLayout(filters)

        self.table = QTableWidget(0, _COLS)
        self.table.setHorizontalHeaderLabels([
            "", t("unlock.col_name"), t("market.col_type"),
            t("recipe.col_family"), t("recipe.col_level"),
            t("recipe.col_power"), t("recipe.col_old_cost"),
            t("recipe.col_target"), t("recipe.col_new_cost"),
            t("unlock.col_status")])
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 34)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)
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
        track(self, "unlock_cost", (1200, 700))

    # ----------------------------------------------------------- scan

    def _set_bounds_row(self, row: int, level: str, lo: str, hi: str):
        level_item = QTableWidgetItem(level)
        if row == 0:
            level_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.bounds_table.setItem(row, 0, level_item)
        self.bounds_table.setItem(row, 1, QTableWidgetItem(lo))
        self.bounds_table.setItem(row, 2, QTableWidgetItem(hi))

    def _cell_int(self, row: int, col: int) -> "int | None":
        item = self.bounds_table.item(row, col)
        text = item.text().strip() if item else ""
        if not text:
            return None
        try:
            return int(float(text))
        except ValueError:
            return None

    def _collect_bounds(self):
        """Lit la table des bornes : (min_cost, max_cost, per_level).
        La ligne Defaut ajuste les globales ; une ligne par niveau avec au
        moins une cellule remplie devient une entree per_level."""
        min_cost = self.spin_min.value()
        max_cost = self.spin_max.value() or None
        default_lo = self._cell_int(0, 1)
        default_hi = self._cell_int(0, 2)
        if default_lo is not None:
            min_cost = default_lo
        if default_hi is not None:
            max_cost = default_hi or None
        per_level: dict[int, tuple] = {}
        for row in range(1, self.bounds_table.rowCount()):
            level = self._cell_int(row, 0)
            if level is None:
                continue
            lo = self._cell_int(row, 1)
            hi = self._cell_int(row, 2)
            if lo is None and hi is None:
                continue
            per_level[level] = (lo, hi)
        return min_cost, max_cost, per_level

    def _ensure_bound_rows(self, levels):
        """Ajoute les niveaux manquants a la table (jamais d'ecrasement :
        les valeurs saisies par l'utilisateur sont conservees)."""
        known = set()
        for row in range(1, self.bounds_table.rowCount()):
            level = self._cell_int(row, 0)
            if level is not None:
                known.add(level)
        for level in sorted(set(levels) - known):
            row = self.bounds_table.rowCount()
            self.bounds_table.insertRow(row)
            self._set_bounds_row(row, str(level), "", "")

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
        self.status_label.setText(t("unlock.running"))
        vanilla = get_vanilla_content_path() or ""
        min_cost, max_cost, per_level = self._collect_bounds()

        async_call(
            self,
            lambda: analyze(root, vanilla, min_cost=min_cost,
                            max_cost=max_cost, per_level=per_level),
            on_done=self._on_analyzed, on_fail=self._on_fail,
            name="unlock-cost")

    def _on_fail(self, exc: Exception):
        self._running = False
        self.btn_run.setEnabled(True)
        self.status_label.setText(f"{t('yamlcheck.failed')}  ({exc})")

    def _on_analyzed(self, proposals: list[UnlockProposal]):
        self._running = False
        self.btn_run.setEnabled(True)
        self._proposals = proposals
        self._by_name = {p.name: p for p in proposals}
        self._ensure_bound_rows({int(p.level) for p in proposals})
        self._fill_families()
        self._fill_table()
        changed = sum(1 for p in proposals if p.changed)
        families = len({p.family for p in proposals})
        self.status_label.setText(t(
            "unlock.done", n=len(proposals), c=changed, f=families))
        for btn in (self.btn_all, self.btn_none, self.btn_export,
                    self.btn_apply):
            btn.setEnabled(True)

    # ---------------------------------------------------------- table

    def _fill_families(self):
        self.cmb_family.blockSignals(True)
        self.cmb_family.clear()
        self.cmb_family.addItem(t("recipe.family_all"), "__all__")
        for family in sorted({p.family for p in self._proposals}):
            self.cmb_family.addItem(family, family)
        self.cmb_family.blockSignals(False)

    def _fill_table(self):
        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(len(self._proposals))
        for index, proposal in enumerate(self._proposals):
            self._set_row(index, proposal)
        self.table.setUpdatesEnabled(True)
        self.table.setSortingEnabled(True)
        self._refilter()

    def _name_at(self, row: int) -> str:
        item = self.table.item(row, 1)
        return item.text() if item else ""

    def _set_row(self, row: int, p: UnlockProposal):
        table = self.table
        check = QTableWidgetItem()
        if p.changed:
            check.setFlags(Qt.ItemFlag.ItemIsUserCheckable
                           | Qt.ItemFlag.ItemIsEnabled)
            check.setCheckState(Qt.CheckState.Unchecked)
        else:
            check.setFlags(Qt.ItemFlag.ItemIsEnabled)
        table.setItem(row, 0, check)
        name = QTableWidgetItem(p.name)
        name.setToolTip(p.detail)
        table.setItem(row, 1, name)
        kind = (t("market.type_block") if p.kind == "block"
                else t("market.type_item"))
        table.setItem(row, 2, QTableWidgetItem(kind))
        table.setItem(row, 3, QTableWidgetItem(p.family))
        self._num(row, 4, p.level)
        self._num(row, 5, p.power, fmt=lambda v: f"{v:,.0f}".replace(",", " "))
        self._num(row, 6, p.old_cost)
        self._num(row, 7, p.target)
        self._num(row, 8, p.new_cost)
        status = QTableWidgetItem(p.detail)
        status.setToolTip(p.detail)
        table.setItem(row, 9, status)

    def _num(self, row: int, col: int, value, fmt=None):
        item = _NumItem()
        if value is None:
            item.setText("-")
        else:
            item.setData(Qt.ItemDataRole.UserRole, float(value))
            item.setText(fmt(value) if fmt else f"{value:,.0f}".replace(",", " "))
        self.table.setItem(row, col, item)

    def _refilter(self):
        if not self._proposals:
            return
        only_changed = self.chk_changed.isChecked()
        family = self.cmb_family.currentData()
        needle = self.edit_name.text().strip().lower()
        hidden = 0
        for row in range(self.table.rowCount()):
            name = self._name_at(row)
            proposal = self._by_name.get(name)
            if proposal is None:
                continue
            show = ((not only_changed or proposal.changed)
                    and (family == "__all__" or proposal.family == family)
                    and (not needle or needle in name.lower()
                         or needle in proposal.family.lower()))
            self.table.setRowHidden(row, not show)
            hidden += not show
        self.status_label.setText(t("recipe.visible",
                                    n=self.table.rowCount() - hidden))

    # ------------------------------------------------------ actions

    def _checked_names(self) -> set:
        names = set()
        for row in range(self.table.rowCount()):
            if self.table.isRowHidden(row):
                continue
            item = self.table.item(row, 0)
            if (item is not None
                    and item.flags() & Qt.ItemFlag.ItemIsUserCheckable
                    and item.checkState() == Qt.CheckState.Checked):
                name = self._name_at(row)
                if name:
                    names.add(name)
        return names

    def _check_all(self):
        count = 0
        for row in range(self.table.rowCount()):
            if self.table.isRowHidden(row):
                continue
            item = self.table.item(row, 0)
            if (item is not None
                    and item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                item.setCheckState(Qt.CheckState.Checked)
                count += 1
        self.status_label.setText(t("market.checked_all", n=count))

    def _uncheck_all(self):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None:
                item.setCheckState(Qt.CheckState.Unchecked)

    def _apply(self):
        if self._running:
            return
        names = self._checked_names()
        if not names:
            info(self, t("unlock.title"), t("unlock.apply_none"))
            return
        selected = [self._by_name[name] for name in names
                    if name in self._by_name]
        if not ask_yes_no(self, t("unlock.title"),
                          t("unlock.apply_confirm", n=len(selected))):
            return
        self._running = True
        self.btn_apply.setEnabled(False)

        def _done(result):
            self._running = False
            self.btn_apply.setEnabled(True)
            total = sum(result.values())
            info(self, t("unlock.title"), t("unlock.applied", n=total))
            self._analyze()          # idempotent : ne doit rien reproposer

        async_call(self, lambda: apply_proposals(selected),
                   on_done=_done, on_fail=self._on_fail,
                   name="unlock-apply")

    def _export_csv(self):
        if not self._proposals:
            return
        base_dir = self.path_edit.text().strip() or str(Path.home())
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
        out, _ = QFileDialog.getSaveFileName(
            self, t("market.export"),
            str(Path(base_dir) / f"unlockcost_{stamp}.csv"), "CSV (*.csv)")
        if not out:
            return
        with open(out, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle, delimiter=";")
            writer.writerow(t("unlock.csv_headers").split(";"))
            for p in sorted(self._proposals, key=lambda x: x.name):
                writer.writerow([
                    p.name, p.kind, p.family, p.level,
                    round(p.power, 2) if p.power else "",
                    p.old_cost if p.old_cost is not None else "",
                    p.target, p.new_cost, p.detail])
        self.status_label.setText(t("market.csv_done", path=out))
