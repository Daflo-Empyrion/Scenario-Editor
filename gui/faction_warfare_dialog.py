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

"""Defenses de faction (FactionWarfare.ecf) : reglages globaux, grille de
prix par niveau de faction (min/max Lvl1/Lvl5/Lvl10 + renforts de defense
spatiale), et vue en lecture seule des unites et scenarios d'attaque.
Moteur : core/faction_warfare.py (chaque prix est ecrit dans la forme
d'origine de la faction : a plat ou dans BaseAttack_ScenarioPrice)."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox,
                             QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QSpinBox, QTabWidget,
                             QTableWidget, QTableWidgetItem, QVBoxLayout,
                             QWidget)

from core.faction_warfare import (LEVELS, save, scan, set_global, set_price,
                                  set_sd)
from core.i18n import t
from gui.module_info import add_info_button
from gui.ewa_async import async_call
from gui.msgboxes import ask_yes_no, info
from gui.window_geometry import track

# colonnes faction : 0 nom, 1 groupe, 2..7 prix (min,max par niveau), 8..11 SD
_COLS = 12
_PRICE_COLS = [(2, 3, 1), (4, 5, 5), (6, 7, 10)]   # (col min, col max, niveau)
_SD_COLS = {"sd_prob_min": 8, "sd_prob_max": 9,
            "sd_price_min": 10, "sd_price_max": 11}


class FactionWarfareDialog(QDialog):
    def __init__(self, parent, working_root: str = ""):
        super().__init__(parent)
        self.setWindowTitle(t("warfare.title"))
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
        self.btn_scan = QPushButton(t("warfare.scan"))
        self.btn_scan.clicked.connect(self._analyze)
        row.addWidget(self.btn_scan)
        lay.addLayout(row)

        self.stats_label = QLabel("")
        self.stats_label.setWordWrap(True)
        lay.addWidget(self.stats_label)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_globals_tab(), t("warfare.tab_globals"))
        self.tabs.addTab(self._build_factions_tab(), t("warfare.tab_factions"))
        self.tabs.addTab(self._build_view_tab(), t("warfare.tab_units"))
        lay.addWidget(self.tabs, 1)

        buttons = QHBoxLayout()
        self.btn_save = QPushButton(t("warfare.save"))
        self.btn_save.clicked.connect(self._save)
        self.btn_save.setEnabled(False)
        buttons.addWidget(self.btn_save)
        add_info_button(buttons, "factionwar.info_html")
        buttons.addStretch(1)
        lay.addLayout(buttons)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        box.rejected.connect(self.reject)
        lay.addWidget(box)
        track(self, "faction_warfare", (1240, 700))

    # ------------------------------------------------------------- onglets

    def _build_globals_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.chk_enabled = QCheckBox(t("warfare.enable"))
        self.chk_enabled.setToolTip(t("warfare.enable.tip"))
        self.chk_log = QCheckBox(t("warfare.enable_log"))
        lay.addWidget(self.chk_enabled)
        lay.addWidget(self.chk_log)
        form = QFormLayout()
        self.spin_pf = QSpinBox()
        self.spin_pf.setRange(0, 9999)
        form.addRow(t("warfare.cap_frequency"), self.spin_pf)
        self.spin_poi = QSpinBox()
        self.spin_poi.setRange(0, 9999)
        form.addRow(t("warfare.cap_poi"), self.spin_poi)
        lay.addLayout(form)
        lay.addWidget(QLabel(t("warfare.globals_hint")))
        lay.addStretch(1)
        return w

    def _build_factions_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.table = QTableWidget(0, _COLS)
        heads = [t("warfare.col_faction"), t("warfare.col_group")]
        for _col_min, _col_max, level in _PRICE_COLS:
            heads += [t("warfare.col_min", level=level),
                      t("warfare.col_max", level=level)]
        heads += [t("warfare.col_sd_prob_min"), t("warfare.col_sd_prob_max"),
                  t("warfare.col_sd_price_min"), t("warfare.col_sd_price_max")]
        self.table.setHorizontalHeaderLabels(heads)
        self.table.verticalHeader().setVisible(False)
        lay.addWidget(self.table)
        lay.addWidget(QLabel(t("warfare.factions_hint")))
        return w

    def _build_view_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel(t("warfare.units_label")))
        self.table_units = QTableWidget(0, 5)
        self.table_units.setHorizontalHeaderLabels([
            t("warfare.col_faction"), t("warfare.col_class"),
            t("warfare.col_category"), t("warfare.col_cp1"),
            t("warfare.col_cp_level")])
        self.table_units.verticalHeader().setVisible(False)
        lay.addWidget(self.table_units, 1)
        lay.addWidget(QLabel(t("warfare.scenarios_label")))
        self.table_scen = QTableWidget(0, 4)
        self.table_scen.setHorizontalHeaderLabels([
            t("warfare.col_scenario"), "ID", t("warfare.col_group"),
            t("warfare.col_units")])
        self.table_scen.verticalHeader().setVisible(False)
        lay.addWidget(self.table_scen, 1)
        return w

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
                   on_fail=self._on_fail, name="faction-warfare")

    def _on_fail(self, exc: Exception):
        self._running = False
        self.btn_scan.setEnabled(True)
        self.stats_label.setText(f"{t('yamlcheck.failed')}  ({exc})")

    def _on_scanned(self, result):
        self._running = False
        self.btn_scan.setEnabled(True)
        self._result = result
        if result.path is None:
            self.stats_label.setText(t("warfare.missing"))
            self.btn_save.setEnabled(False)
            self._clear_tables()
            return
        self.btn_save.setEnabled(True)
        self.stats_label.setText(t(
            "warfare.stats", factions=len(result.factions),
            units=len(result.units), scenarios=len(result.scenarios),
            issues=len(result.issues)))
        self._fill_globals()
        self._fill_factions()
        self._fill_views()

    def _clear_tables(self):
        for table in (self.table, self.table_units, self.table_scen):
            table.setRowCount(0)

    def _fill_globals(self):
        values = self._result.globals_values
        self.chk_enabled.setChecked(
            values.get("EnableSpaceDefense", "").lower() in ("true", "1"))
        self.chk_log.setChecked(
            values.get("EnableSpaceDefenseLog", "").lower() in ("true", "1"))
        self.spin_pf.setValue(_as_int(values.get(
            "PlayerAttackMaxCountFrequencySpawned")))
        self.spin_poi.setValue(_as_int(values.get(
            "PlayerAttackMaxCountPOISpawned")))

    def _fill_factions(self):
        rows = self._result.factions
        self.table.setRowCount(len(rows))
        for row, entry in enumerate(rows):
            name = QTableWidgetItem(entry.faction)
            name.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(row, 0, name)
            group = QTableWidgetItem(entry.scenario_group)
            group.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(row, 1, group)
            for col_min, col_max, level in _PRICE_COLS:
                self._num_item(row, col_min, entry.price(level, "min"))
                self._num_item(row, col_max, entry.price(level, "max"))
            for slot, col in _SD_COLS.items():
                value = entry.values.get(slot)
                self._num_item(row, col, value if isinstance(value, (int, float))
                               else None)

    def _num_item(self, row: int, col: int, value):
        item = QTableWidgetItem("" if value is None else _fmt(value))
        item.setTextAlignment(Qt.AlignmentFlag.AlignRight
                              | Qt.AlignmentFlag.AlignVCenter)
        self.table.setItem(row, col, item)

    def _fill_views(self):
        units = self._result.units
        self.table_units.setRowCount(len(units))
        for row, unit in enumerate(units):
            for col, text in enumerate((unit.faction, unit.class_name,
                                        unit.category,
                                        _fmt(unit.cp_lvl1),
                                        _fmt(unit.cp_per_level))):
                self.table_units.setItem(row, col, QTableWidgetItem(text))
        scenarios = self._result.scenarios
        self.table_scen.setRowCount(len(scenarios))
        for row, scen in enumerate(scenarios):
            cells = (scen.name, scen.sid, scen.groups,
                     ", ".join(u[0] or "?" for u in scen.units))
            for col, text in enumerate(cells):
                self.table_scen.setItem(row, col, QTableWidgetItem(text))

    # --------------------------------------------------------------- save

    def _save(self):
        if self._result is None or not self._result.editable:
            return
        saved = 0
        for row, entry in enumerate(self._result.factions):
            for col_min, col_max, level in _PRICE_COLS:
                for col, which in ((col_min, "min"), (col_max, "max")):
                    value = self._cell_num(row, col)
                    if value is not None and \
                            set_price(entry, level, which, value):
                        saved += 1
            for slot, col in _SD_COLS.items():
                value = self._cell_num(row, col)
                if value is not None and set_sd(entry, slot, value):
                    saved += 1
        for key, widget in (("EnableSpaceDefense", self.chk_enabled),
                            ("EnableSpaceDefenseLog", self.chk_log)):
            if set_global(self._result, key, widget.isChecked()):
                saved += 1
        for key, spin in (("PlayerAttackMaxCountFrequencySpawned", self.spin_pf),
                          ("PlayerAttackMaxCountPOISpawned", self.spin_poi)):
            if set_global(self._result, key, spin.value()):
                saved += 1
        if not saved:
            info(self, t("warfare.title"), t("warfare.nothing"))
            return
        if not ask_yes_no(self, t("warfare.title"),
                          t("warfare.save_confirm", n=saved)):
            return
        try:
            save(self._result)
        except Exception as exc:                  # noqa: BLE001 - remonte a l'UI
            info(self, t("warfare.title"), str(exc))
            return
        info(self, t("warfare.title"), t("warfare.saved", path=str(self._result.path)))
        self._analyze()

    def _cell_num(self, row: int, col: int):
        item = self.table.item(row, col)
        if item is None:
            return None
        text = item.text().strip().replace(",", ".")
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None


def _fmt(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return str(int(number)) if number.is_integer() else f"{number:g}"


def _as_int(value) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 0
