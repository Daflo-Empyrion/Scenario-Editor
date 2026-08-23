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
Fenetre de statistiques des POI d'un playfield -- combien de drones un
joueur peut potentiellement affronter, repartition par faction. Voir
core/poi_inspector.py pour le calcul (uniquement les POI Random, les POI
Fixed n'ont pas ces champs de comptage/probabilite).

Fenetre NON MODALE (voir gui/results_window_helpers.py et le raisonnement
deja applique aux dialogues de verification) -- reste ouverte pendant qu'on
ajuste des valeurs dans l'editeur."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QTabWidget, QWidget,
)

from core.i18n import t
from core.poi_inspector import compute_poi_stats, aggregate_by_faction
from gui.theme import icon, icon_size
from gui.results_window_helpers import export_text_to_file


class PoiInspectorDialog(QDialog):
    def __init__(self, doc, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.setWindowTitle(t("poi_inspector.title"))
        self.setMinimumSize(760, 560)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        self.detail_table = QTableWidget()
        self.tabs.addTab(self.detail_table, t("poi_inspector.tab_detail"))

        self.faction_table = QTableWidget()
        self.tabs.addTab(self.faction_table, t("poi_inspector.tab_by_faction"))

        bottom_row = QHBoxLayout()
        self.summary_label = QLabel("")
        self.summary_label.setObjectName("mutedLabel")
        bottom_row.addWidget(self.summary_label)
        bottom_row.addStretch()

        btn_refresh = QPushButton(icon("fa5s.sync-alt", "#4a7dfc"), t("results_window.btn_refresh"))
        btn_refresh.setIconSize(icon_size())
        btn_refresh.setObjectName("secondaryButton")
        btn_refresh.clicked.connect(self.refresh)
        bottom_row.addWidget(btn_refresh)

        btn_export = QPushButton(icon("fa5s.file-export", "#4a7dfc"), t("results_window.btn_export"))
        btn_export.setIconSize(icon_size())
        btn_export.setObjectName("secondaryButton")
        btn_export.clicked.connect(self._export)
        bottom_row.addWidget(btn_export)

        btn_close = QPushButton(t("validation.close"))
        btn_close.setObjectName("secondaryButton")
        btn_close.clicked.connect(self.close)
        bottom_row.addWidget(btn_close)
        layout.addLayout(bottom_row)

        self.stats = []
        self.refresh()

    def refresh(self):
        self.stats = compute_poi_stats(self.doc)
        self._populate_detail_table()
        self._populate_faction_table()
        self.summary_label.setText(t("poi_inspector.n_pois", n=len(self.stats)))

    def _populate_detail_table(self):
        headers = [
            t("poi_inspector.col_name"), t("poi_inspector.col_faction"),
            t("poi_inspector.col_count"), t("poi_inspector.col_drones_est"),
        ]
        self.detail_table.setColumnCount(len(headers))
        self.detail_table.setHorizontalHeaderLabels(headers)
        self.detail_table.setRowCount(len(self.stats))
        for row, s in enumerate(self.stats):
            self.detail_table.setItem(row, 0, QTableWidgetItem(s.name))
            self.detail_table.setItem(row, 1, QTableWidgetItem(s.faction))
            self.detail_table.setItem(row, 2, QTableWidgetItem(f"{s.count_min}-{s.count_max}"))
            self.detail_table.setItem(
                row, 3, QTableWidgetItem(f"{s.estimated_drones_min}-{s.estimated_drones_max}"))
        self.detail_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.detail_table.resizeColumnsToContents()

    def _populate_faction_table(self):
        by_faction = aggregate_by_faction(self.stats)
        headers = [
            t("poi_inspector.col_faction"), t("poi_inspector.col_poi_count"),
            t("poi_inspector.col_drones_est"),
        ]
        self.faction_table.setColumnCount(len(headers))
        self.faction_table.setHorizontalHeaderLabels(headers)
        sorted_factions = sorted(by_faction.values(), key=lambda a: -a.total_drones_max)
        self.faction_table.setRowCount(len(sorted_factions))
        for row, agg in enumerate(sorted_factions):
            self.faction_table.setItem(row, 0, QTableWidgetItem(agg.faction))
            self.faction_table.setItem(row, 1, QTableWidgetItem(str(agg.poi_count)))
            self.faction_table.setItem(
                row, 2, QTableWidgetItem(f"{agg.total_drones_min}-{agg.total_drones_max}"))
        self.faction_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.faction_table.resizeColumnsToContents()

    def _export(self):
        lines = [t("poi_inspector.title"), "=" * len(t("poi_inspector.title")), ""]
        for s in self.stats:
            lines.append(f"{s.name} ({s.faction}) : {s.count_min}-{s.count_max}x, "
                          f"drones estimes {s.estimated_drones_min}-{s.estimated_drones_max}")
        lines.append("")
        lines.append(t("poi_inspector.tab_by_faction") + " :")
        for agg in sorted(aggregate_by_faction(self.stats).values(), key=lambda a: -a.total_drones_max):
            lines.append(f"{agg.faction} : {agg.poi_count} POI, "
                          f"drones estimes {agg.total_drones_min}-{agg.total_drones_max}")
        export_text_to_file(self, "poi_inspector.txt", "\n".join(lines))
