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

"""Comparaison de deux bundles Unity de scenarios (menu Outils) : liste
les ajouts / retraits / types differents entre les containers, export
CSV. Les bundles ne se fusionnent pas en binaire : cet outil sert a
decider AVANT une fusion de dossier (voir core/unity_bundles.py)."""
import csv
from pathlib import Path

from PyQt6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QTreeWidget,
                             QTreeWidgetItem, QVBoxLayout)

from core.i18n import t
from gui.window_geometry import track


class BundlesDialog(QDialog):
    """Deux chemins (fichiers bundles, ou dossiers), un diff."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("bundles.title"))
        self._diff = None
        track(self, "bundles", (860, 560))
        self._build_ui()

    # ------------------------------------------------------------- interface

    def _build_ui(self):
        from PyQt6.QtWidgets import QAbstractItemView
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(t("bundles.intro")))

        self.edits = {}
        for key in ("a", "b"):
            row = QHBoxLayout()
            row.addWidget(QLabel(t(f"bundles.path_{key}")))
            edit = QLineEdit()
            edit.setPlaceholderText(t("bundles.path_hint"))
            row.addWidget(edit, 1)
            btn = QPushButton(t("bundles.browse"))
            btn.clicked.connect(lambda _=False, e=edit: self._browse(e))
            row.addWidget(btn)
            lay.addLayout(row)
            self.edits[key] = edit

        self.btn_compare = QPushButton(t("bundles.compare"))
        self.btn_compare.setObjectName("primaryButton")
        self.btn_compare.clicked.connect(self._compare)
        lay.addWidget(self.btn_compare)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([t("bundles.col_status"),
                                   t("bundles.col_path"),
                                   t("bundles.col_type_a"),
                                   t("bundles.col_type_b")])
        self.tree.setColumnWidth(0, 140)
        self.tree.setColumnWidth(1, 420)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSortingEnabled(True)
        self.tree.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection)
        lay.addWidget(self.tree, 1)

        self.status_label = QLabel("")
        lay.addWidget(self.status_label)

        bottom = QHBoxLayout()
        self.btn_export = QPushButton(t("bundles.export"))
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._export_csv)
        bottom.addWidget(self.btn_export, 1)
        self.btn_close = QPushButton(t("btn.close"))
        self.btn_close.clicked.connect(self.reject)
        bottom.addWidget(self.btn_close)
        lay.addLayout(bottom)

    def _browse(self, edit: QLineEdit):
        path, _ = QFileDialog.getOpenFileName(
            self, t("bundles.browse"), edit.text() or ".",
            t("bundles.filter"))
        if path:
            edit.setText(path)

    # ------------------------------------------------------------- analyse

    def _compute(self, pa: str, pb: str):
        """Hors thread GUI, NE LEVE JAMAIS (relancer dans un slot PyQt6.11
        = crash natif) : retourne (BundleDiff | None, message erreur)."""
        from core.unity_bundles import compare_bundles
        try:
            return compare_bundles(pa, pb), ""
        except ValueError as e:
            if str(e) == "UnityPy":
                return None, "UnityPy"
            return None, str(e)
        except Exception as e:  # noqa: BLE001 - affiche et continue
            return None, str(e)

    def _compare(self):
        from gui.busy import run_long
        pa, pb = self.edits["a"].text().strip(), self.edits["b"].text().strip()
        if not pa or not pb:
            self.status_label.setText(t("bundles.need_paths"))
            return
        self.tree.clear()
        self._diff = None
        self.btn_export.setEnabled(False)
        diff, err = run_long(self, lambda: self._compute(pa, pb))
        if err:
            self.status_label.setText(
                t("bundles.need_unitypy") if err == "UnityPy"
                else t("bundles.err_read", err=err))
            return
        self._diff = diff
        rows = ([(t("bundles.added"), p, "", ty)
                 for p, ty in sorted(diff.added.items())]
                + [(t("bundles.removed"), p, ty, "")
                   for p, ty in sorted(diff.removed.items())]
                + [(t("bundles.changed"), p, ta, tb)
                   for p, (ta, tb) in sorted(diff.changed.items())])
        for status, p, ta, tb in rows:
            self.tree.addTopLevelItem(QTreeWidgetItem([status, p, ta, tb]))
        self.btn_export.setEnabled(bool(rows))
        # UnityPy ne leve PAS sur un non-bundle : il rend un container vide
        summary = t("bundles.summary", na=diff.na, nb=diff.nb,
                    added=len(diff.added), removed=len(diff.removed),
                    changed=len(diff.changed), same=diff.same)
        if diff.na == 0 or diff.nb == 0:
            summary = t("bundles.empty") + " " + summary
        self.status_label.setText(summary)

    # ------------------------------------------------------------- export

    def _export_csv(self):
        if not self._diff:
            return
        default = Path(self.edits["a"].text().strip()).stem or "bundle"
        path, _ = QFileDialog.getSaveFileName(
            self, t("bundles.export"), f"{default}_diff.csv", "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow([t("bundles.col_status"), t("bundles.col_path"),
                        t("bundles.col_type_a"), t("bundles.col_type_b")])
            for i in range(self.tree.topLevelItemCount()):
                it = self.tree.topLevelItem(i)
                w.writerow([it.text(0), it.text(1), it.text(2), it.text(3)])
        self.status_label.setText(t("bundles.exported", path=path))
