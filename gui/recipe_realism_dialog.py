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

"""Recettes réalistes : la composition de chaque template vient du réel et
les quantités de la masse de l'objet (moteur core/recipe_realism.py). Table
triable et cochable — RIEN n'est précoché ; application confirmée, backup
central, puis re-scan (l'idempotence garantit qu'il ne reste rien)."""
from __future__ import annotations

import csv
import datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QTableWidget, QTableWidgetItem, QVBoxLayout)

from core.i18n import t
from core.recipe_realism import (RealismProposal, analyze, apply_proposals,
                                 summary)
from core.settings import get_vanilla_content_path
from gui.ewa_async import async_call
from gui.module_info import add_info_button
from gui.msgboxes import ask_yes_no, info
# item numérique du module frère : même tri par valeur, une seule définition
from gui.recipe_balance_dialog import _NumItem
from gui.window_geometry import track

_COLS = 10   # case, template, classe, source, masse objet, masse cible,
             # écart, ingrédients avant -> après, craft, notes


def _fmt_inputs(rows) -> str:
    return ", ".join(f"{name}x{qty:g}" for name, qty in rows) or "-"


class RecipeRealismDialog(QDialog):
    """Composition des recettes alignée sur le réel."""

    def __init__(self, parent, working_root: str = ""):
        super().__init__(parent)
        self.setWindowTitle(t("realism.title"))
        self._running = False
        self._report = None
        self._proposals: list[RealismProposal] = []
        self._by_name: dict[str, RealismProposal] = {}

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

        row2 = QHBoxLayout()
        row2.addWidget(QLabel(t("realism.base")))
        self.base_edit = QLineEdit()
        self.base_edit.setPlaceholderText(t("realism.base_hint"))
        row2.addWidget(self.base_edit, 1)
        self.btn_base = QPushButton(t("yamlcheck.browse"))
        self.btn_base.clicked.connect(self._pick_base)
        row2.addWidget(self.btn_base)
        lay.addLayout(row2)

        params = QHBoxLayout()
        add_info_button(params, "realism.info_html")
        params.addStretch(1)
        self.btn_run = QPushButton(t("realism.analyze"))
        self.btn_run.clicked.connect(lambda: self._analyze())
        params.addWidget(self.btn_run)
        lay.addLayout(params)

        self.stats_label = QLabel("")
        self.stats_label.setWordWrap(True)
        lay.addWidget(self.stats_label)

        filters = QHBoxLayout()
        self.chk_changed = QCheckBox(t("realism.only_changed"))
        self.chk_changed.setChecked(True)
        self.chk_changed.toggled.connect(self._refilter)
        filters.addWidget(self.chk_changed)
        filters.addWidget(QLabel(t("realism.filter_class")))
        self.cmb_class = QComboBox()
        self.cmb_class.addItem(t("realism.class_all"), "__all__")
        self.cmb_class.currentIndexChanged.connect(self._refilter)
        filters.addWidget(self.cmb_class, 1)
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText(t("realism.filter_name"))
        self.edit_name.textChanged.connect(self._refilter)
        filters.addWidget(self.edit_name, 1)
        lay.addLayout(filters)

        self.table = QTableWidget(0, _COLS)
        self.table.setHorizontalHeaderLabels([
            "", t("realism.col_template"), t("realism.col_class"),
            t("realism.col_source"), t("realism.col_obj_mass"),
            t("realism.col_target_mass"), t("realism.col_coverage"),
            t("realism.col_inputs"), t("realism.col_craft"),
            t("realism.col_notes")])
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        lay.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        self.btn_all = QPushButton(t("realism.check_all"))
        self.btn_all.clicked.connect(self._check_all)
        buttons.addWidget(self.btn_all)
        self.btn_none = QPushButton(t("realism.uncheck_all"))
        self.btn_none.clicked.connect(self._uncheck_all)
        buttons.addWidget(self.btn_none)
        buttons.addStretch(1)
        self.btn_export = QPushButton(t("realism.export"))
        self.btn_export.clicked.connect(self._export_csv)
        buttons.addWidget(self.btn_export)
        self.btn_apply = QPushButton(t("realism.apply"))
        self.btn_apply.clicked.connect(self._apply)
        buttons.addWidget(self.btn_apply)
        lay.addLayout(buttons)
        for btn in (self.btn_all, self.btn_none, self.btn_export,
                    self.btn_apply):
            btn.setEnabled(False)

        self.status_label = QLabel("")
        lay.addWidget(self.status_label)
        track(self, "recipe_realism", (1360, 760))

    # ------------------------------------------------------------- scan

    def _pick_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, t("yamlcheck.scenario"), self.path_edit.text() or ".")
        if path:
            self.path_edit.setText(path)

    def _pick_base(self):
        path = QFileDialog.getExistingDirectory(
            self, t("realism.base"), self.base_edit.text() or ".")
        if path:
            self.base_edit.setText(path)

    def _analyze(self):
        if self._running:
            return
        root = self.path_edit.text().strip()
        if not root:
            self.status_label.setText(t("yamlcheck.need_scenario"))
            return
        self._running = True
        self.btn_run.setEnabled(False)
        self.status_label.setText(t("realism.running"))
        vanilla = get_vanilla_content_path() or ""
        base = self.base_edit.text().strip()
        async_call(self, lambda: analyze(root, vanilla, base),
                   on_done=self._on_analyzed, on_fail=self._on_fail,
                   name="recipe-realism")

    def _on_fail(self, exc: Exception):
        self._running = False
        self.btn_run.setEnabled(True)
        self.status_label.setText(f"{t('yamlcheck.failed')}  ({exc})")

    def _on_analyzed(self, report):
        self._running = False
        self.btn_run.setEnabled(True)
        self._report = report
        self._proposals = report.proposals
        self._by_name = {p.name: p for p in self._proposals}
        self._fill_classes()
        self._fill_table()
        changed = sum(1 for p in self._proposals if p.changed)
        self.status_label.setText(t("realism.done", n=len(self._proposals),
                                    c=changed, s=len(report.skipped)))
        for btn in (self.btn_all, self.btn_none, self.btn_export,
                    self.btn_apply):
            btn.setEnabled(True)

    # ------------------------------------------------------------ table

    def _fill_classes(self):
        self.cmb_class.blockSignals(True)
        self.cmb_class.clear()
        self.cmb_class.addItem(t("realism.class_all"), "__all__")
        for code in sorted({p.klass for p in self._proposals}):
            self.cmb_class.addItem(code, code)
        self.cmb_class.blockSignals(False)

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

    def _set_row(self, row: int, p: RealismProposal):
        table = self.table
        check = QTableWidgetItem()
        if p.changed:
            check.setFlags(Qt.ItemFlag.ItemIsUserCheckable
                           | Qt.ItemFlag.ItemIsEnabled)
            check.setCheckState(Qt.CheckState.Unchecked)
        else:
            check.setFlags(Qt.ItemFlag.ItemIsEnabled)
        table.setItem(row, 0, check)
        notes = " ; ".join(p.notes)
        name = QTableWidgetItem(p.name)
        name.setToolTip(notes)
        table.setItem(row, 1, name)
        table.setItem(row, 2, QTableWidgetItem(p.klass))
        table.setItem(row, 3, QTableWidgetItem(t(f"realism.src_{p.src}")))
        self._num(row, 4, round(p.obj_mass))
        self._num(row, 5, round(p.target_mass))
        self._num(row, 6, round(p.coverage * 100))
        inputs = QTableWidgetItem(f"{_fmt_inputs(p.old_inputs)}  ->  "
                                  f"{_fmt_inputs(p.new_inputs)}")
        inputs.setToolTip(notes)
        table.setItem(row, 7, inputs)
        craft = (f"{p.craft_old:g} -> {p.craft_new}"
                 if p.craft_new != p.craft_old else f"{p.craft_old:g}")
        table.setItem(row, 8, QTableWidgetItem(craft))
        table.setItem(row, 9, QTableWidgetItem(notes))

    def _num(self, row: int, col: int, value, fmt=None):
        item = _NumItem()
        if value is None:
            item.setText("-")
        else:
            item.setData(Qt.ItemDataRole.UserRole, float(value))
            item.setText(fmt(value) if fmt else
                         f"{value:,.0f}".replace(",", " "))
        self.table.setItem(row, col, item)

    def _refilter(self):
        if not self._proposals:
            return
        only_changed = self.chk_changed.isChecked()
        code = self.cmb_class.currentData()
        needle = self.edit_name.text().strip().lower()
        hidden = 0
        for row in range(self.table.rowCount()):
            name = self._name_at(row)
            proposal = self._by_name.get(name)
            if proposal is None:
                continue
            show = ((not only_changed or proposal.changed)
                    and (code == "__all__" or proposal.klass == code)
                    and (not needle or needle in name.lower()
                         or needle in proposal.klass.lower()))
            self.table.setRowHidden(row, not show)
            hidden += not show
        self.status_label.setText(t("realism.visible",
                                    n=self.table.rowCount() - hidden))

    # ---------------------------------------------------------- actions

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
        self.status_label.setText(t("realism.checked_all", n=count))

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
            info(self, t("realism.title"), t("realism.apply_none"))
            return
        selected = [self._by_name[name] for name in names
                    if name in self._by_name]
        if not ask_yes_no(self, t("realism.title"),
                          t("realism.apply_confirm", n=len(selected))):
            return
        self._running = True
        self.btn_apply.setEnabled(False)

        def _done(result):
            self._running = False
            self.btn_apply.setEnabled(True)
            info(self, t("realism.title"),
                 t("realism.applied", n=sum(result.values())))
            self._analyze()          # idempotent : les lignes cochées restent

        async_call(self, lambda: apply_proposals(selected), on_done=_done,
                   on_fail=self._on_fail, name="recipe-realism-apply")

    def _export_csv(self):
        if not self._proposals:
            return
        base_dir = self.path_edit.text().strip() or str(Path.home())
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
        out, _ = QFileDialog.getSaveFileName(
            self, t("realism.export"),
            str(Path(base_dir) / f"recettes_realistes_{stamp}.csv"),
            "CSV (*.csv)")
        if not out:
            return
        with open(out, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle, delimiter=";")
            writer.writerow(t("realism.csv_headers").split(";"))
            for p in sorted(self._proposals, key=lambda x: x.name):
                writer.writerow([
                    p.name, p.klass, t(f"realism.src_{p.src}"),
                    round(p.target_mass, 2), _fmt_inputs(p.old_inputs),
                    _fmt_inputs(p.new_inputs), f"{p.coverage:.2f}",
                    p.craft_old, p.craft_new, " ; ".join(p.notes)])
            for name, reason in sorted(self._report.skipped.items()):
                writer.writerow([name, "", "", "", "", "", "", "", "",
                                 reason])
        self.status_label.setText(t("realism.csv_done", path=out))

    def summary_lines(self) -> list[str]:
        """Synthèse lisible (tests et info-bulle du bouton Analyser)."""
        return summary(self._report) if self._report else []
