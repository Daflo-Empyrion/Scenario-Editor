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

"""Jetons de quete (TokenConfig.ecf) : table editable des jetons du scenario
avec leur nombre d'usages reels, creation d'un jeton a Id libre, et
enregistrement avec backup central. Moteur : core/token_config.py.

Tri du tableau volontairement DESACTIVE : les lignes portent l'index de
l'entree et un tri les desolidariserait (piege deja vecu)."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog,
                             QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                             QMessageBox, QPushButton, QTableWidget,
                             QTableWidgetItem, QVBoxLayout)

from core.i18n import t
from gui.module_info import add_info_button
from core.token_config import (create_token, next_free_id, save, scan,
                               set_field, set_flag)
from gui.ewa_async import async_call
from gui.msgboxes import ask_yes_no, info
from gui.window_geometry import track

_COLS = 7      # Id, Nom, Description, Icone, RemoveOnUse, DropOnDeath, Usages
_COL_NAME, _COL_DESC, _COL_ICON = 1, 2, 3
_COL_REMOVE, _COL_DROP = 4, 5


def _flag_item(checked: bool) -> QTableWidgetItem:
    it = QTableWidgetItem()
    it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
    it.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
    return it


class TokenConfigDialog(QDialog):
    def __init__(self, parent, working_root: str = ""):
        super().__init__(parent)
        self.setWindowTitle(t("tokens.title"))
        self._running = False
        self._filling = False
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
        self.btn_scan = QPushButton(t("tokens.scan"))
        self.btn_scan.clicked.connect(self._analyze)
        row.addWidget(self.btn_scan)
        lay.addLayout(row)

        self.stats_label = QLabel("")
        self.stats_label.setWordWrap(True)
        lay.addWidget(self.stats_label)

        filters = QHBoxLayout()
        self.edit_filter = QLineEdit()
        self.edit_filter.setPlaceholderText(t("taudit.filter_name"))
        self.edit_filter.textChanged.connect(self._refilter)
        filters.addWidget(self.edit_filter, 1)
        self.btn_new = QPushButton(t("tokens.new"))
        self.btn_new.clicked.connect(self._create)
        self.btn_new.setEnabled(False)
        filters.addWidget(self.btn_new)
        lay.addLayout(filters)

        self.table = QTableWidget(0, _COLS)
        self.table.setHorizontalHeaderLabels([
            "Id", t("tokens.col_name"), t("tokens.col_description"),
            t("tokens.col_icon"), t("tokens.col_remove_on_use"),
            t("tokens.col_drop_on_death"), t("tokens.col_usages")])
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 60)
        self.table.setColumnWidth(2, 380)
        self.table.itemChanged.connect(self._on_item_changed)
        lay.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        self.btn_save = QPushButton(t("tokens.save"))
        self.btn_save.clicked.connect(self._save)
        self.btn_save.setEnabled(False)
        buttons.addWidget(self.btn_save)
        add_info_button(buttons, "tokens.info_html")
        buttons.addStretch(1)
        lay.addLayout(buttons)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        box.rejected.connect(self.reject)
        lay.addWidget(box)
        track(self, "token_config", (1180, 640))

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
            from pathlib import Path
            return scan(Path(root))

        async_call(self, work, on_done=self._on_scanned,
                   on_fail=self._on_fail, name="token-config")

    def _on_fail(self, exc: Exception):
        self._running = False
        self.btn_scan.setEnabled(True)
        self.stats_label.setText(f"{t('yamlcheck.failed')}  ({exc})")

    def _on_scanned(self, result):
        self._running = False
        self.btn_scan.setEnabled(True)
        self._result = result
        if result.path is None:
            self.stats_label.setText(t("tokens.missing"))
            self.btn_new.setEnabled(False)
            self.btn_save.setEnabled(False)
            self.table.setRowCount(0)
            return
        unused = sum(1 for e in result.entries if e.usages == 0)
        self.stats_label.setText(t(
            "tokens.stats", n=len(result.entries), unused=unused,
            issues=len(result.issues)))
        self.btn_new.setEnabled(True)
        self.btn_save.setEnabled(True)
        self._fill()

    # --------------------------------------------------------------- table

    def _fill(self):
        self._filling = True
        self.table.setRowCount(len(self._result.entries))
        for row, e in enumerate(self._result.entries):
            id_item = QTableWidgetItem(str(e.token_id))
            id_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            id_item.setData(Qt.ItemDataRole.UserRole, row)
            self.table.setItem(row, 0, id_item)
            for col, value in ((_COL_NAME, e.name),
                               (_COL_DESC, e.description),
                               (_COL_ICON, e.custom_icon)):
                it = QTableWidgetItem(value)
                it.setToolTip(value)
                self.table.setItem(row, col, it)
            self.table.setItem(row, _COL_REMOVE, _flag_item(e.remove_on_use))
            self.table.setItem(row, _COL_DROP, _flag_item(e.drop_on_death))
            usage = QTableWidgetItem(str(e.usages))
            usage.setFlags(Qt.ItemFlag.ItemIsEnabled)
            usage.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                   | Qt.AlignmentFlag.AlignVCenter)
            if e.usages == 0:
                usage.setForeground(Qt.GlobalColor.darkYellow)
            self.table.setItem(row, 6, usage)
        self._filling = False
        self._refilter()

    def _entry_at(self, row: int):
        it = self.table.item(row, 0)
        if it is None:
            return None
        idx = it.data(Qt.ItemDataRole.UserRole)
        if idx is None or idx >= len(self._result.entries):
            return None
        return self._result.entries[idx]

    def _on_item_changed(self, item: QTableWidgetItem):
        if self._filling or self._result is None or item.column() == 0:
            return
        entry = self._entry_at(item.row())
        if entry is None:
            return
        col = item.column()
        if col == _COL_NAME:
            set_field(entry, "Name", item.text().strip())
        elif col == _COL_DESC:
            set_field(entry, "Description", item.text().strip())
        elif col == _COL_ICON:
            set_field(entry, "CustomIcon", item.text().strip())
        elif col == _COL_REMOVE:
            set_flag(entry, "RemoveOnUse",
                     item.checkState() == Qt.CheckState.Checked)
        elif col == _COL_DROP:
            set_flag(entry, "DropOnDeath",
                     item.checkState() == Qt.CheckState.Checked)

    def _refilter(self):
        if self._result is None:
            return
        needle = self.edit_filter.text().strip().lower()
        visible = 0
        for row in range(self.table.rowCount()):
            e = self._entry_at(row)
            if e is None:
                continue
            show = (not needle or needle in e.name.lower()
                    or needle in str(e.token_id) or needle in e.description.lower())
            self.table.setRowHidden(row, not show)
            visible += show

    # ------------------------------------------------------------- actions

    def _create(self):
        if self._result is None or not self._result.editable:
            return
        try:
            token_id = next_free_id(self._result.entries)
        except ValueError as exc:
            info(self, t("tokens.title"), str(exc))
            return
        entry = create_token(self._result.doc, self._result.path, token_id,
                             t("tokens.new_name"))
        self._result.entries.append(entry)
        self.btn_save.setEnabled(True)
        self._fill()
        # amene la ligne nouvelle a l'ecran et ouvre l'edition du nom
        needle = t("tokens.new_name").lower()
        self.edit_filter.setText(needle)
        for row in range(self.table.rowCount()):
            self.table.setRowHidden(row, False)
        if self.table.rowCount():
            self.table.scrollToBottom()
            self.table.editItem(self.table.item(self.table.rowCount() - 1, _COL_NAME))

    def _save(self):
        if self._result is None or not self._result.editable:
            return
        if not ask_yes_no(self, t("tokens.title"),
                          t("tokens.save_confirm", n=len(self._result.entries))):
            return
        try:
            save(self._result)
        except Exception as exc:                  # noqa: BLE001 - remonte a l'UI
            QMessageBox.critical(self, t("tokens.title"), str(exc))
            return
        info(self, t("tokens.title"), t("tokens.saved", path=str(self._result.path)))
        self._analyze()
