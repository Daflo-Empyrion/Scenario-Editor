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
: liste des paires terme source -> traduction imposee PAR LANGUE CIBLE
(v1.10.0), activees/desactivables, ajout et suppression manuels. Une entree
n'est appliquee QUE pour les traductions vers sa langue ; le meme terme peut
avoir une traduction imposee differente par langue. Les termes actifs sont
proteges par jetons avant l'envoi au moteur, la traduction du glossaire est
reinjectee ensuite.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout,
)

from core.i18n import t
from core import glossary
from core.translation import COMMON_LANGUAGES
from gui.theme import icon, icon_size

COL_ON, COL_SRC, COL_LANG, COL_DST = 0, 1, 2, 3

_LANG_LABELS = {code: label for label, code in COMMON_LANGUAGES}


def _lang_label(code: str) -> str:
    """Libelle affichable d'un code de langue (code brut si inconnu)."""
    return _LANG_LABELS.get((code or "").strip(), (code or "").strip())


class GlossaryDialog(QDialog):
    """Liste editable du glossaire : case d'activation, terme source,
    langue cible, traduction imposee. Chaque changement est persiste
    immediatement."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("glossary.title"))
        self.resize(720, 480)
        from gui.window_geometry import track
        track(self, "glossary")

        layout = QVBoxLayout(self)
        intro = QLabel(t("glossary.intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        add_row = QHBoxLayout()
        self.src_edit = QLineEdit()
        self.src_edit.setPlaceholderText(t("glossary.src_placeholder"))
        add_row.addWidget(self.src_edit)
        self.lang_combo = QComboBox()
        self.lang_combo.setEditable(True)
        for _label, code in COMMON_LANGUAGES:
            self.lang_combo.addItem(_label, code)
        if self.lang_combo.findData("fr") >= 0:
            self.lang_combo.setCurrentIndex(self.lang_combo.findData("fr"))
        self.lang_combo.setToolTip(t("glossary.lang_tip"))
        add_row.addWidget(self.lang_combo)
        self.dst_edit = QLineEdit()
        self.dst_edit.setPlaceholderText(t("glossary.dst_placeholder"))
        add_row.addWidget(self.dst_edit)
        self.btn_add = QPushButton(icon("fa5s.plus", "#ffffff"), t("glossary.add"))
        self.btn_add.clicked.connect(self._add_entry)
        add_row.addWidget(self.btn_add)
        layout.addLayout(add_row)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([
            t("glossary.col_on"), t("glossary.col_src"),
            t("glossary.col_lang"), t("glossary.col_dst")])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_ON, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_SRC, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_LANG, QHeaderView.ResizeMode.ResizeToContents)
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
        entries.sort(key=lambda e: (_lang_label(e.get("target", "fr")).lower(),
                                    e["src"].lower()))
        self.table.setRowCount(len(entries))
        for r, entry in enumerate(entries):
            target = entry.get("target", "fr")
            check = QCheckBox()
            check.setChecked(entry.get("on", True))
            check.toggled.connect(
                lambda checked, src=entry["src"], tgt=target:
                glossary.set_enabled(src, checked, tgt))
            self.table.setCellWidget(r, COL_ON, check)
            self.table.setItem(r, COL_SRC, QTableWidgetItem(entry["src"]))
            self.table.setItem(r, COL_LANG, QTableWidgetItem(_lang_label(target)))
            self.table.setItem(r, COL_DST, QTableWidgetItem(entry["dst"]))

    def _add_entry(self) -> None:
        src = self.src_edit.text().strip()
        dst = self.dst_edit.text().strip()
        target = (self.lang_combo.currentData()
                  or self.lang_combo.currentText().strip() or "fr")
        if not src or not dst:
            QMessageBox.warning(self, t("glossary.title"), t("glossary.need_both"))
            return
        if not glossary.add_entry(src, dst, target=target):
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
            src_item = self.table.item(r, COL_SRC)
            lang_item = self.table.item(r, COL_LANG)
            if src_item is not None:
                # retrouver le CODE de langue (la case affiche le libelle)
                target = None
                for label, code in COMMON_LANGUAGES:
                    if lang_item is not None and label == lang_item.text():
                        target = code
                        break
                if target is None:
                    target = lang_item.text() if lang_item is not None else "fr"
                glossary.remove_entry(src_item.text(), target)
        self._reload()
