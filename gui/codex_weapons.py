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

"""Codex — onglet Degats : matrice armes x categories de materiaux (paliers
empiriques du Codex) et recherche inverse « quelles armes percent ce bloc »."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout,
                             QHeaderView, QLabel, QTableWidget,
                             QTableWidgetItem, QTabWidget, QVBoxLayout,
                             QWidget)

from core.codex import tier_of
from core.i18n import t
from gui.codex_export import headers_of, table_rows
from gui.codex_items import fmt

# palier -> (symbole, couleur de fond ou None, cle i18n du libelle)
TIERS = {
    "none":          ("—", None, "codex.tier.none"),
    "default":       ("·", None, "codex.tier.default"),
    "ineffective":   ("▼", QColor(248, 215, 218), "codex.tier.ineffective"),
    "normal":        ("=", None, "codex.tier.normal"),
    "effective":     ("▲", QColor(212, 237, 218), "codex.tier.effective"),
    "very_effective": ("▲▲", QColor(155, 219, 170), "codex.tier.very"),
}


def _item(text: str, tip: str = "", background=None, center: bool = False):
    item = QTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    if tip:
        item.setToolTip(tip)
    if background is not None:
        item.setBackground(background)
    if center:
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    return item


class MatrixView(QWidget):
    """Une ligne par arme, une colonne par categorie de materiaux."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = None
        lay = QVBoxLayout(self)
        self.lbl_legend = QLabel(t("codex.weapons.legend"))
        self.lbl_legend.setWordWrap(True)
        lay.addWidget(self.lbl_legend)
        self.table = QTableWidget(0, 1)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents)
        lay.addWidget(self.table, 1)
        self.lbl_thresholds = QLabel("")
        self.lbl_thresholds.setWordWrap(True)
        lay.addWidget(self.lbl_thresholds)

    def set_data(self, data) -> None:
        self.data = data
        matrix = data.damage_matrix()
        self.table.clear()
        self.table.setColumnCount(len(matrix.columns) + 1)
        self.table.setRowCount(len(matrix.rows))
        self.table.setHorizontalHeaderLabels([t("codex.weapons.weapon")] + list(matrix.columns))
        for row, weapon in enumerate(matrix.rows):
            self.table.setItem(row, 0, _item(data.display_name(weapon.block),
                                             weapon.item))
            for idx, value in enumerate(weapon.cells):
                tier = weapon.tiers[idx]
                symbol, background, label = TIERS[tier]
                self.table.setItem(row, idx + 1, _item(
                    symbol, f"{fmt(value)} — {t(label)}", background, center=True))
        self.table.resizeColumnsToContents()
        parts = []
        for idx, column in enumerate(matrix.columns):
            thresholds = matrix.thresholds[idx]
            if not thresholds:
                continue
            parts.append(
                f"<b>{column}</b> : ▼ &lt; {thresholds['ineffective']:.3g} · "
                f"= ≤ {thresholds['normal']:.3g} · ▲ ≤ {thresholds['effective']:.3g}")
        self.lbl_thresholds.setText(t("codex.weapons.thresholds") + "<br>" +
                                    "<br>".join(parts[:12]))


    def export_payload(self):
        rows = table_rows(self.table)
        return (headers_of(self.table), rows) if rows else None


class LookupView(QWidget):
    """Recherche inverse : choisir une categorie de materiau, voir les armes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = None
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel(t("codex.weapons.category")))
        self.combo = QComboBox()
        self.combo.currentIndexChanged.connect(self._fill)
        top.addWidget(self.combo, 1)
        lay.addLayout(top)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels([
            t("codex.weapons.weapon"), t("codex.weapons.multiplier"),
            t("codex.weapons.tier")])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.table, 1)
        self.lbl_count = QLabel("")
        lay.addWidget(self.lbl_count)

    def set_data(self, data) -> None:
        self.data = data
        self.combo.blockSignals(True)
        self.combo.clear()
        for category in sorted(data.blocks_by_damage_category()):
            self.combo.addItem(category, category)
        self.combo.blockSignals(False)
        self._fill()

    def _fill(self) -> None:
        if self.data is None:
            return
        category = self.combo.currentData()
        rows = self.data.weapons_against(category) if category else []
        self.table.setRowCount(len(rows))
        for row, (name, value, tier) in enumerate(rows):
            symbol, background, label = TIERS[tier]
            self.table.setItem(row, 0, _item(self.data.display_name(name)))
            self.table.setItem(row, 1, _item(fmt(value)))
            self.table.setItem(row, 2, _item(f"{symbol} {t(label)}", background=background))
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self.lbl_count.setText(t("codex.count", shown=len(rows)))


    def export_payload(self):
        rows = table_rows(self.table)
        return (headers_of(self.table), rows) if rows else None


class WeaponsTab(QWidget):
    """Matrice + recherche inverse dans un meme onglet."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.matrix = MatrixView()
        self.lookup = LookupView()
        self.tabs.addTab(self.matrix, t("codex.weapons.tab_matrix"))
        self.tabs.addTab(self.lookup, t("codex.weapons.tab_lookup"))
        lay.addWidget(self.tabs, 1)

    def set_data(self, data) -> None:
        self.matrix.set_data(data)
        self.lookup.set_data(data)

    def export_payload(self):
        view = self.tabs.currentWidget()
        return view.export_payload() if hasattr(view, "export_payload") else None


def tier_label(tier: str) -> str:
    return t(TIERS[tier][2])


__all__ = ["WeaponsTab", "TIERS", "tier_of", "tier_label"]
