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

"""Export CSV des tableaux du Codex — convention des autres modules du
projet : point-virgule, UTF-8 avec BOM (ouvrable directement dans Excel),
nom horodate."""
from __future__ import annotations

import csv
import datetime
from pathlib import Path
from typing import Iterable, List, Sequence

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog, QTableWidget

from core.i18n import t


def table_rows(table: QTableWidget, skip_columns: Sequence[int] = ()
               ) -> List[List[str]]:
    """Lignes VISIBLES du tableau, en texte. Une case a cocher s'exporte en
    « x » / vide ; les colonnes de `skip_columns` sont omises."""
    keep = [col for col in range(table.columnCount()) if col not in skip_columns]
    rows: List[List[str]] = []
    for row in range(table.rowCount()):
        if table.isRowHidden(row):
            continue
        values = []
        for col in keep:
            item = table.item(row, col)
            if item is None:
                values.append("")
            elif item.data(Qt.ItemDataRole.CheckStateRole) is not None:
                # Vraie case a cocher (un QTableWidgetItem porte le drapeau
                # ItemIsUserCheckable par defaut : tester le drapeau ferait
                # passer TOUTE cellule pour une case et perdrait les textes).
                values.append("x" if item.checkState() == Qt.CheckState.Checked else "")
            else:
                values.append(item.text())
        rows.append(values)
    return rows


def headers_of(table: QTableWidget, skip_columns: Sequence[int] = ()) -> List[str]:
    return [table.horizontalHeaderItem(col).text()
            for col in range(table.columnCount()) if col not in skip_columns]


def export_rows(parent, headers: Sequence[str], rows: Iterable[Sequence[str]],
                default_name: str) -> Path | None:
    """Ecrit le CSV et retourne son chemin (None si l'utilisateur annule)."""
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    out, _ = QFileDialog.getSaveFileName(
        parent, t("codex.export"), f"{default_name}_{stamp}.csv", "CSV (*.csv)")
    if not out:
        return None
    with open(out, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(list(headers))
        writer.writerows([list(row) for row in rows])
    return Path(out)
