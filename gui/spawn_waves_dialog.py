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

"""Ondes de spawn : vue transversale (onglet Synthese) et edition groupee
des densites (onglet Groupes : filtre par type/nom, RIEN de precoche, facteur
x, apercu MODIFIABLE (colonnes nouveaux min/max editables) puis application
avec backup central et re-scan automatique). Moteur : core/spawn_waves.py --
meme architecture que CorrelationDialog (scan async, boites patchables)."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog,
                             QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                             QPushButton, QSpinBox, QTabWidget, QTableWidget,
                             QTableWidgetItem, QVBoxLayout, QWidget)

from core.i18n import t
from gui.module_info import add_info_button
from core.spawn_waves import (KIND_FREEDRONE, KIND_PATROL, KIND_POI,
                              KIND_VESSEL, apply_changes, apply_count,
                              kind_label_key, scale_count, scan)
from gui.ewa_async import async_call
from gui.msgboxes import ask_yes_no, info
from gui.window_geometry import track

_COL_SUMMARY = 9
_COL_GROUPS = 9          # case, type, playfield, groupe, faction, min, max, nmin, nmax


class _CkItem(QTableWidgetItem):
    def __init__(self, prop_idx: int):
        super().__init__()
        self.prop_idx = prop_idx
        self.setFlags(Qt.ItemFlag.ItemIsEnabled
                      | Qt.ItemFlag.ItemIsUserCheckable)
        self.setCheckState(Qt.CheckState.Unchecked)


class SpawnWavesDialog(QDialog):
    def __init__(self, parent, working_root: str = ""):
        super().__init__(parent)
        self.setWindowTitle(t("sw.title"))
        self._running = False
        self._result = None          # SpawnScanResult
        self._entries: list = []

        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel(t("yamlcheck.scenario")))
        self.path_edit = QLineEdit(working_root)
        self.path_edit.setPlaceholderText(t("yamlcheck.scenario_hint"))
        row.addWidget(self.path_edit, 1)
        self.btn_browse = QPushButton(t("yamlcheck.browse"))
        self.btn_browse.clicked.connect(self._pick_folder)
        row.addWidget(self.btn_browse)
        self.btn_scan = QPushButton(t("sw.scan"))
        self.btn_scan.clicked.connect(self._analyze)
        row.addWidget(self.btn_scan)
        lay.addLayout(row)

        self.stats_label = QLabel("")
        self.stats_label.setWordWrap(True)
        lay.addWidget(self.stats_label)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_summary_tab(), t("sw.tab_summary"))
        self.tabs.addTab(self._build_groups_tab(), t("sw.tab_groups"))
        lay.addWidget(self.tabs, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        track(self, "spawn_waves", (1280, 760))

    # ------------------------------------------------------------ tabs

    def _build_summary_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        filters = QHBoxLayout()
        self.cmb_type = QComboBox()
        self.cmb_type.addItem(t("sw.filter_all"), "__all__")
        for value in ("Planet", "Space"):
            self.cmb_type.addItem(value, value)
        self.cmb_type.currentIndexChanged.connect(self._refilter_summary)
        filters.addWidget(self.cmb_type)
        self.edit_pf = QLineEdit()
        self.edit_pf.setPlaceholderText(t("taudit.filter_name"))
        self.edit_pf.textChanged.connect(self._refilter_summary)
        filters.addWidget(self.edit_pf, 1)
        lay.addLayout(filters)

        self.table_summary = QTableWidget(0, _COL_SUMMARY)
        self.table_summary.setHorizontalHeaderLabels([
            t("sw.col_playfield"), t("sw.col_type"), t("sw.col_pois"),
            t("sw.col_drones"), t("sw.col_vessels"), t("sw.col_freedrones"),
            t("sw.col_patrols"), t("sw.col_zones"), t("sw.col_total")])
        self.table_summary.verticalHeader().setVisible(False)
        self.table_summary.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive)
        self.table_summary.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self.table_summary.setSortingEnabled(True)
        lay.addWidget(self.table_summary)
        return w

    def _build_groups_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        tools = QHBoxLayout()
        self.cmb_kind = QComboBox()
        self.cmb_kind.addItem(t("sw.filter_all"), "__all__")
        for kind in (KIND_POI, KIND_VESSEL, KIND_FREEDRONE, KIND_PATROL):
            self.cmb_kind.addItem(t(kind_label_key(kind)), kind)
        self.cmb_kind.currentIndexChanged.connect(self._refilter_groups)
        tools.addWidget(self.cmb_kind)
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText(t("taudit.filter_name"))
        self.edit_name.textChanged.connect(self._refilter_groups)
        tools.addWidget(self.edit_name, 1)
        tools.addWidget(QLabel(t("sw.factor")))
        self.spin_factor = QSpinBox()
        self.spin_factor.setRange(10, 1000)          # x0.1 a x10.0 (0.1 pas)
        self.spin_factor.setSingleStep(5)
        self.spin_factor.setValue(100)
        self.spin_factor.setToolTip(t("sw.factor.tip"))
        tools.addWidget(self.spin_factor)
        self.btn_preview = QPushButton(t("sw.preview"))
        self.btn_preview.clicked.connect(self._preview)
        self.btn_preview.setEnabled(False)
        tools.addWidget(self.btn_preview)
        lay.addLayout(tools)

        self.table_groups = QTableWidget(0, _COL_GROUPS)
        self.table_groups.setHorizontalHeaderLabels([
            "", t("sw.col_kind"), t("sw.col_playfield"), t("sw.col_group"),
            t("sw.col_faction"), t("sw.col_min"), t("sw.col_max"),
            t("sw.col_new_min"), t("sw.col_new_max")])
        self.table_groups.verticalHeader().setVisible(False)
        header = self.table_groups.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table_groups.setColumnWidth(0, 34)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        lay.addWidget(self.table_groups, 1)

        buttons = QHBoxLayout()
        self.btn_all = QPushButton(t("market.check_all"))
        self.btn_all.clicked.connect(self._check_all)
        self.btn_all.setEnabled(False)
        buttons.addWidget(self.btn_all)
        self.btn_none = QPushButton(t("market.uncheck_all"))
        self.btn_none.clicked.connect(self._uncheck_all)
        self.btn_none.setEnabled(False)
        buttons.addWidget(self.btn_none)
        buttons.addStretch(1)
        self.btn_apply = QPushButton(t("market.apply"))
        self.btn_apply.clicked.connect(self._apply)
        self.btn_apply.setEnabled(False)
        buttons.addWidget(self.btn_apply)
        add_info_button(buttons, "spawns.info_html")
        lay.addLayout(buttons)
        return w

    # ------------------------------------------------------------ scan

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

        async_call(self, work, on_done=self._on_analyzed,
                   on_fail=self._on_fail, name="spawn-waves")

    def _on_fail(self, exc: Exception):
        self._running = False
        self.btn_scan.setEnabled(True)
        self.stats_label.setText(f"{t('yamlcheck.failed')}  ({exc})")

    def _on_analyzed(self, result):
        self._running = False
        self.btn_scan.setEnabled(True)
        self._result = result
        self._entries = result.entries
        counts = {"poi": 0, "vessel": 0, "freedrone": 0, "patrol": 0}
        for e in self._entries:
            counts[e.kind] += 1
        self.stats_label.setText(t(
            "sw.stats", pfs=len(result.summaries), pois=counts["poi"],
            vessels=counts["vessel"], freedrones=counts["freedrone"],
            patrols=counts["patrol"], issues=len(result.issues)))
        self._fill_summary()
        self._fill_groups()
        for b in (self.btn_all, self.btn_none, self.btn_preview,
                  self.btn_apply):
            b.setEnabled(True)

    # ------------------------------------------------------- synthese

    def _fill_summary(self):
        table = self.table_summary
        table.setSortingEnabled(False)
        table.setUpdatesEnabled(False)
        table.setRowCount(len(self._result.summaries))
        for row, s in enumerate(self._result.summaries):
            vals = [
                s.playfield, s.pf_type or "—",
                f"{s.poi_min} – {s.poi_max}", f"{s.drones_min} – {s.drones_max}",
                f"{s.vessels_min} – {s.vessels_max}",
                f"{s.freedrones_min} – {s.freedrones_max}",
                str(s.patrol_zones), str(s.rate_zones),
                f"{s.total_min} – {s.total_max}"]
            for col, text in enumerate(vals):
                it = QTableWidgetItem(text)
                it.setToolTip(text)
                it.setData(Qt.ItemDataRole.UserRole, row)
                table.setItem(row, col, it)
        table.setUpdatesEnabled(True)
        table.setSortingEnabled(True)
        self._refilter_summary()

    def _refilter_summary(self):
        if self._result is None:
            return
        want = self.cmb_type.currentData()
        needle = self.edit_pf.text().strip().lower()
        for row in range(self.table_summary.rowCount()):
            it = self.table_summary.item(row, 0)
            if it is None:
                continue
            s = self._result.summaries[it.data(Qt.ItemDataRole.UserRole)]
            show = ((want == "__all__" or s.pf_type == want)
                    and (not needle or needle in s.playfield.lower()))
            self.table_summary.setRowHidden(row, not show)

    # -------------------------------------------------------- groupes

    def _fill_groups(self):
        table = self.table_groups
        table.setSortingEnabled(False)
        table.setUpdatesEnabled(False)
        table.setRowCount(len(self._entries))
        for row, e in enumerate(self._entries):
            table.setItem(row, 0, _CkItem(row))
            self._txt(row, 1, t(kind_label_key(e.kind)))
            self._txt(row, 2, e.playfield)
            self._txt(row, 3, e.name)
            self._txt(row, 4, e.faction or "—")
            self._num(row, 5, e.count_min)
            self._num(row, 6, e.count_max)
            new_min = QTableWidgetItem("—")
            new_max = QTableWidgetItem("—")
            table.setItem(row, 7, new_min)
            table.setItem(row, 8, new_max)
        table.setUpdatesEnabled(True)
        table.setSortingEnabled(True)
        self._refilter_groups()

    def _txt(self, row: int, col: int, text: str):
        it = QTableWidgetItem(text)
        it.setToolTip(text)
        self.table_groups.setItem(row, col, it)

    def _num(self, row: int, col: int, value: int):
        it = QTableWidgetItem(str(value))
        it.setTextAlignment(Qt.AlignmentFlag.AlignRight
                            | Qt.AlignmentFlag.AlignVCenter)
        self.table_groups.setItem(row, col, it)

    def _refilter_groups(self):
        if self._result is None:
            return
        want = self.cmb_kind.currentData()
        needle = self.edit_name.text().strip().lower()
        visible = 0
        for row in range(self.table_groups.rowCount()):
            ck = self.table_groups.item(row, 0)
            if not isinstance(ck, _CkItem):
                continue
            e = self._entries[ck.prop_idx]
            show = ((want == "__all__" or e.kind == want)
                    and (not needle or needle in e.name.lower()
                         or needle in e.playfield.lower()))
            self.table_groups.setRowHidden(row, not show)
            visible += show

    def _checked_rows(self) -> list:
        """Paires (index d'entree, ligne visuelle) des lignes cochees et
        affichees -- le tri du tableau deplace les lignes : jamais confondre
        index d'entree et ligne du tableau."""
        rows = []
        for row in range(self.table_groups.rowCount()):
            if self.table_groups.isRowHidden(row):
                continue
            it = self.table_groups.item(row, 0)
            if (isinstance(it, _CkItem)
                    and it.flags() & Qt.ItemFlag.ItemIsUserCheckable
                    and it.checkState() == Qt.CheckState.Checked):
                rows.append((it.prop_idx, row))
        return rows

    def _check_all(self):
        n = 0
        for row in range(self.table_groups.rowCount()):
            if self.table_groups.isRowHidden(row):
                continue
            it = self.table_groups.item(row, 0)
            if it is not None and it.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                it.setCheckState(Qt.CheckState.Checked)
                n += 1

    def _uncheck_all(self):
        for row in range(self.table_groups.rowCount()):
            it = self.table_groups.item(row, 0)
            if it is not None:
                it.setCheckState(Qt.CheckState.Unchecked)

    # --------------------------------------------------- apercu/apply

    def _preview(self):
        """Remplit les colonnes 'nouveaux min/max' des lignes cochees AVEC le
        facteur -- cellules EDITABLES : l'utilisateur peut corriger chaque
        valeur avant application (apercu modifiable)."""
        rows = self._checked_rows()
        if not rows:
            info(self, t("sw.title"), t("sw.preview_none"))
            return
        factor = self.spin_factor.value() / 100.0
        for prop_idx, row in rows:
            cmin, cmax = scale_count(self._entries[prop_idx], factor)
            for col, value in ((7, cmin), (8, cmax)):
                it = self.table_groups.item(row, col)
                it.setText(str(value))
                it.setFlags(it.flags() | Qt.ItemFlag.ItemIsEditable)
                it.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                    | Qt.AlignmentFlag.AlignVCenter)

    def _cell_int(self, row: int, col: int) -> int | None:
        text = self.table_groups.item(row, col).text().strip()
        try:
            return int(text)
        except ValueError:
            return None

    def _apply(self):
        if self._running or self._result is None:
            return
        rows = self._checked_rows()
        if not rows:
            info(self, t("sw.title"), t("market.apply_none"))
            return
        planned = []
        for prop_idx, row in rows:
            cmin = self._cell_int(row, 7)
            cmax = self._cell_int(row, 8)
            if cmin is None or cmax is None:
                info(self, t("sw.title"), t("sw.preview_none"))
                return
            planned.append((self._entries[prop_idx], cmin, cmax))
        if not ask_yes_no(self, t("sw.title"),
                          t("taudit.apply_confirm", n=len(planned))):
            return
        self._running = True
        self.btn_apply.setEnabled(False)

        def work():
            for entry, cmin, cmax in planned:
                apply_count(entry, cmin, cmax)
            return apply_changes([e for e, _, _ in planned]), len(planned)

        def _done(res):
            self._running = False
            self.btn_apply.setEnabled(True)
            info(self, t("sw.title"), t("market.applied", n=res[1]))
            self._analyze()          # re-scan automatique

        async_call(self, work, on_done=_done, on_fail=self._on_fail,
                   name="spawn-waves-apply")
