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
Gestion du glossaire terminologique (menu Options > Glossaire de traduction)
: liste des paires terme source -> traduction imposee, activees/desactivables,
ajout et suppression manuels. Le glossaire est applique a TOUTES les
traductions (Argos, Google...) : les termes actifs sont proteges par jetons
avant l'envoi au moteur, la traduction du glossaire est reinjectee ensuite.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout,
)

from core.i18n import t
from core import glossary
from gui.theme import icon, icon_size

COL_ON, COL_SRC, COL_DST = 0, 1, 2


class GlossaryDialog(QDialog):
    """Liste editable du glossaire : case d'activation, terme source,
    traduction imposee. Chaque changement est persiste immediatement."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("glossary.title"))
        self.resize(640, 480)

        layout = QVBoxLayout(self)
        intro = QLabel(t("glossary.intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        add_row = QHBoxLayout()
        self.src_edit = QLineEdit()
        self.src_edit.setPlaceholderText(t("glossary.src_placeholder"))
        add_row.addWidget(self.src_edit)
        self.dst_edit = QLineEdit()
        self.dst_edit.setPlaceholderText(t("glossary.dst_placeholder"))
        add_row.addWidget(self.dst_edit)
        self.btn_add = QPushButton(icon("fa5s.plus", "#ffffff"), t("glossary.add"))
        self.btn_add.clicked.connect(self._add_entry)
        add_row.addWidget(self.btn_add)
        layout.addLayout(add_row)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels([
            t("glossary.col_on"), t("glossary.col_src"), t("glossary.col_dst")])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_ON, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_SRC, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_DST, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        btn_remove = QPushButton(icon("fa5s.trash-alt", "#ffffff"), t("glossary.remove"))
        btn_remove.clicked.connect(self._remove_selected)
        btn_row.addWidget(btn_remove)
        btn_row.addStretch()
        btn_close = QPushButton(t("btn.close"))
        btn_close.setObjectName("secondaryButton")
        btn_close.clicked.connect(self.close)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

        self._reload()

    def _reload(self) -> None:
        entries = glossary.entries()
        self.table.setRowCount(len(entries))
        for r, entry in enumerate(entries):
            check = QCheckBox()
            check.setChecked(entry.get("on", True))
            check.toggled.connect(
                lambda checked, src=entry["src"]: glossary.set_enabled(src, checked))
            self.table.setCellWidget(r, COL_ON, check)
            self.table.setItem(r, COL_SRC, QTableWidgetItem(entry["src"]))
            self.table.setItem(r, COL_DST, QTableWidgetItem(entry["dst"]))

    def _add_entry(self) -> None:
        src = self.src_edit.text().strip()
        dst = self.dst_edit.text().strip()
        if not src or not dst:
            QMessageBox.warning(self, t("glossary.title"), t("glossary.need_both"))
            return
        if not glossary.add_entry(src, dst):
            QMessageBox.warning(self, t("glossary.title"), t("glossary.forbidden_chars"))
            self.src_edit.clear()
            self.dst_edit.clear()
            return
        self.src_edit.clear()
        self.dst_edit.clear()
        self._reload()

    def _remove_selected(self) -> None:
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            item = self.table.item(r, COL_SRC)
            if item is not None:
                glossary.remove_entry(item.text())
        self._reload()
