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

"""
Revue de la reparation du glossaire (21/10/2026) : propositions issues de
core/glossary_repair.analyze_local() (tri terminology/phrases SANS IA,
localisation officielle prioritaire), RIEN de precoche, application apres
confirmation avec sauvegarde horodatee.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFileDialog, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from core import glossary_repair as repair
from core.i18n import t
from gui.theme import icon

COL_CHECK, COL_ACTION, COL_KIND, COL_SRC, COL_OLD, COL_NEW, COL_REASON = range(7)


class GlossaryRepairDialog(QDialog):
    """Table cochable des corrections proposees pour le glossaire."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("glossary_repair.title"))
        self.resize(1080, 700)
        from gui.window_geometry import track
        track(self, "glossary_repair")
        self._items = []

        layout = QVBoxLayout(self)
        intro = QLabel(t("glossary_repair.intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        top = QHBoxLayout()
        self.btn_analyze = QPushButton(icon("fa5s.magic", "#ffffff"),
                                       t("glossary_repair.analyze"))
        self.btn_analyze.clicked.connect(self._analyze)
        top.addWidget(self.btn_analyze)
        self.progress_label = QLabel("")
        top.addWidget(self.progress_label, 1)
        self.btn_check_all = QPushButton(t("glossary_repair.check_all"))
        self.btn_check_all.setObjectName("secondaryButton")
        self.btn_check_all.clicked.connect(lambda: self._set_all(True))
        top.addWidget(self.btn_check_all)
        self.btn_uncheck = QPushButton(t("glossary_repair.uncheck_all"))
        self.btn_uncheck.setObjectName("secondaryButton")
        self.btn_uncheck.clicked.connect(lambda: self._set_all(False))
        top.addWidget(self.btn_uncheck)
        layout.addLayout(top)

        filters = QHBoxLayout()
        self.filter_combo = QComboBox()
        for label, value in (
                (t("glossary_repair.filter_all"), "all"),
                (t("glossary_repair.filter_translate"), "translate"),
                (t("glossary_repair.filter_disable"), "disable"),
                (t("glossary_repair.filter_remove"), "remove")):
            self.filter_combo.addItem(label, value)
        self.filter_combo.currentIndexChanged.connect(self._apply_filters)
        filters.addWidget(self.filter_combo)
        self.search = QLineEdit()
        self.search.setPlaceholderText(t("glossary_repair.search"))
        self.search.textChanged.connect(self._apply_filters)
        filters.addWidget(self.search, 1)
        layout.addLayout(filters)
        self.count_label = QLabel("")
        layout.addWidget(self.count_label)

        self.stats_label = QLabel("")
        self.stats_label.setWordWrap(True)
        layout.addWidget(self.stats_label)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "", t("glossary_repair.col_action"),
            t("glossary_repair.col_kind"), t("glossary_repair.col_src"),
            t("glossary_repair.col_old"), t("glossary_repair.col_new"),
            t("glossary_repair.col_reason")])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_CHECK, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_ACTION, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_KIND, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_SRC, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_OLD, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_NEW, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_REASON, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        self.btn_apply = QPushButton(icon("fa5s.check", "#ffffff"),
                                     t("glossary_repair.apply"))
        self.btn_apply.clicked.connect(self._apply)
        bottom.addWidget(self.btn_apply)
        self.btn_export = QPushButton(t("glossary_repair.export"))
        self.btn_export.setObjectName("secondaryButton")
        self.btn_export.clicked.connect(self._export)
        bottom.addWidget(self.btn_export)
        bottom.addStretch()
        btn_close = QPushButton(t("btn.close"))
        btn_close.setObjectName("secondaryButton")
        btn_close.clicked.connect(self.close)
        bottom.addWidget(btn_close)
        layout.addLayout(bottom)

        self._load_cache()

    # -- donnees -----------------------------------------------------------
    def _load_cache(self) -> None:
        data = repair.load_proposal()
        if data:
            self._populate(data)
            self.btn_analyze.setText(t("glossary_repair.relaunch"))
        else:
            self._items = []
            self.table.setRowCount(0)
            self.stats_label.setText(t("glossary_repair.empty"))

    def _populate(self, data: dict) -> None:
        self._items = list(data.get("items") or [])
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            check = QTableWidgetItem("")
            check.setFlags(Qt.ItemFlag.ItemIsUserCheckable
                           | Qt.ItemFlag.ItemIsEnabled
                           | Qt.ItemFlag.ItemIsSelectable)
            check.setCheckState(Qt.CheckState.Unchecked)
            check.setData(Qt.ItemDataRole.UserRole, item)
            self.table.setItem(row, COL_CHECK, check)
            self.table.setItem(row, COL_ACTION, QTableWidgetItem(
                self._action_label(item.get("action"))))
            self.table.setItem(row, COL_KIND, QTableWidgetItem(
                t("glossary_repair.kind_term")
                if item.get("kind") == "term"
                else t("glossary_repair.kind_phrase")))
            self.table.setItem(row, COL_SRC, QTableWidgetItem(
                item.get("src") or ""))
            self.table.setItem(row, COL_OLD, QTableWidgetItem(
                item.get("old") or ""))
            self.table.setItem(row, COL_NEW, QTableWidgetItem(
                item.get("new") or ""))
            self.table.setItem(row, COL_REASON, QTableWidgetItem(
                self._reason_label(item.get("reason"))))
        self.table.setUpdatesEnabled(True)
        self._update_stats(data)
        self._apply_filters()

    def _action_label(self, action: str) -> str:
        return {"translate": t("glossary_repair.action_translate"),
                "disable": t("glossary_repair.action_disable"),
                "remove": t("glossary_repair.action_remove")}.get(
                    action, action or "")

    def _reason_label(self, reason: str) -> str:
        reason = reason or ""
        if reason.startswith("ai_error"):
            return t("glossary_repair.reason_ai_error")
        labels = {
            "official": "reason_official", "wrong": "reason_wrong",
            "ordinary": "reason_ordinary", "proper_noun": "reason_proper",
            "technical": "reason_technical", "duplicate": "reason_duplicate",
            "target": "reason_target", "src=dst": "reason_src_dst",
            "empty": "reason_empty", "correct": "reason_correct",
            "manual": "reason_manual",
        }
        key = labels.get(reason)
        return t("glossary_repair." + key) if key else reason

    def _update_stats(self, data: dict) -> None:
        stats = data.get("stats") or {}
        self.stats_label.setText(t(
            "glossary_repair.stats", count=len(self._items),
            translate=stats.get("translate", 0),
            disable=stats.get("disable", 0),
            remove=stats.get("remove", 0),
            cost=f"{data.get('cost') or 0.0:.2f}"))

    # -- actions -----------------------------------------------------------
    def _analyze(self) -> None:
        self.btn_analyze.setEnabled(False)
        self.btn_apply.setEnabled(False)
        self.progress_label.setText(t("glossary_repair.analyzing"))
        try:
            repair.analyze_local()
        except Exception as exc:
            QMessageBox.warning(self, t("glossary_repair.title"),
                                t("glossary_repair.error", error=exc))
        finally:
            self.progress_label.setText("")
            self.btn_analyze.setEnabled(True)
            self.btn_apply.setEnabled(True)
        self._load_cache()

    def _set_all(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self.table.rowCount()):
            if self.table.isRowHidden(row):
                continue
            item = self.table.item(row, COL_CHECK)
            if item is not None:
                item.setCheckState(state)

    def _apply_filters(self) -> None:
        action = self.filter_combo.currentData()
        query = self.search.text().strip().lower()
        visible = 0
        for row in range(self.table.rowCount()):
            item = self.table.item(row, COL_CHECK)
            data = item.data(Qt.ItemDataRole.UserRole) if item else {}
            ok = action == "all" or data.get("action") == action
            if ok and query:
                haystack = " ".join(
                    str(data.get(key) or "") for key in ("src", "old", "new"))
                ok = query in haystack.lower()
            self.table.setRowHidden(row, not ok)
            visible += int(ok)
        self.count_label.setText(t("glossary_repair.visible",
                                   visible=visible, total=len(self._items)))

    def _selected(self) -> list:
        out = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, COL_CHECK)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                out.append(item.data(Qt.ItemDataRole.UserRole))
        return [item for item in out if item]

    def _apply(self) -> None:
        items = self._selected()
        if not items:
            QMessageBox.information(self, t("glossary_repair.title"),
                                    t("glossary_repair.nothing_checked"))
            return
        answer = QMessageBox.question(
            self, t("glossary_repair.title"),
            t("glossary_repair.confirm_apply", count=len(items)))
        if answer != QMessageBox.StandardButton.Yes:
            return
        result = repair.apply(items)
        QMessageBox.information(self, t("glossary_repair.title"), t(
            "glossary_repair.applied", updated=result["updated"],
            disabled=result["disabled"], removed=result["removed"],
            skipped=result["skipped"], backup=result["backup"]))
        self._load_cache()

    def _export(self) -> None:
        if not self._items:
            QMessageBox.information(self, t("glossary_repair.title"),
                                    t("glossary_repair.empty"))
            return
        path, _filter = QFileDialog.getSaveFileName(
            self, t("glossary_repair.export"), "glossaire_corrections.csv",
            "CSV (*.csv)")
        if not path:
            return
        count = repair.export_csv(self._items, path)
        QMessageBox.information(self, t("glossary_repair.title"),
                                t("glossary_repair.exported", count=count,
                                  path=path))
