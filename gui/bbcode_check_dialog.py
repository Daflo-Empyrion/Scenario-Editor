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

"""Controle des balises BBCode du CSV ouvert (bouton « Balises BBCode »).

Tableau : ligne, colonne, anomalies constatees, texte avant, texte apres.
La colonne « Apres » est EDITABLE (double-clic) : l'utilisateur peut
retoucher ou ecrire lui-meme une correction, y compris sur une ligne que le
moteur n'a pas su reparer. Les lignes cochees sont ecrites dans la table de
l'editeur, puis le fichier est enregistre apres une copie de securite
`<fichier>.bak`. Logique pure : core/bbcode_check.py.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QComboBox, QDialog, QHBoxLayout,
                             QHeaderView, QLabel, QPushButton, QTableWidget,
                             QTableWidgetItem, QVBoxLayout)

from core.bbcode_check import check_table, language_columns, source_column
from core.fsutil import central_backup
from core.i18n import t
from gui.msgboxes import info
from gui.window_geometry import track

_KIND_KEYS = {
    "unclosed": "bbcheck.issue.unclosed",
    "orphan": "bbcheck.issue.orphan",
    "nesting": "bbcheck.issue.nesting",
    "invalid": "bbcheck.issue.invalid",
    "extra": "bbcheck.issue.extra",
    "missing": "bbcheck.issue.missing",
    "token": "bbcheck.issue.token",
}
_TOKEN_KEYS = {
    "newline": "bbcheck.token.newline",
    "placeholder": "bbcheck.token.placeholder",
    "percent": "bbcheck.token.percent",
    "macro": "bbcheck.token.macro",
}


class BbcodeCheckDialog(QDialog):
    def __init__(self, widget, parent=None):
        super().__init__(parent)
        self.widget = widget
        self.setWindowTitle(t("bbcheck.title"))
        track(self, "bbcode_check", (1100, 620))
        self._rows: list[tuple[int, int, object]] = []   # (ligne table, colonne, rapport)

        lay = QVBoxLayout(self)
        header = widget.doc.header or []

        # choix de la colonne controlee : toutes, ou une seule langue
        scope_row = QHBoxLayout()
        scope_row.addWidget(QLabel(t("bbcheck.scope_label")))
        self.scope = QComboBox()
        self.scope.addItem(t("bbcheck.scope_all"), None)
        cols = language_columns(header)
        source = source_column(header, cols)
        for c in cols:
            if c != source:                    # l'anglais est la reference
                self.scope.addItem(header[c] if c < len(header) else str(c), c)
        current = widget.table.currentColumn()
        preset = self.scope.findData(current)
        if preset > 0:                          # celle que l'utilisateur edite
            self.scope.setCurrentIndex(preset)
        self.scope.currentIndexChanged.connect(lambda _i: self._run())
        scope_row.addWidget(self.scope)
        scope_row.addStretch(1)
        lay.addLayout(scope_row)

        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        lay.addWidget(self.summary)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            t("bbcheck.col_line"), t("bbcheck.col_column"),
            t("bbcheck.col_problem"), t("bbcheck.col_source"),
            t("bbcheck.col_before"), t("bbcheck.col_after")])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        # une ligne par anomalie : la hauteur des lignes n'est pas recalculee
        # sur 5 000 entrees, un texte replie serait coupe verticalement.
        # Lire tout le texte = elargir la colonne (Interactive + ElideNone).
        self.table.setWordWrap(False)
        # seule la colonne « Apres » est editable, et seulement au double-clic
        # explicite (programmatic editItem) : les autres colonnes restent en
        # lecture seule malgre leurs flags par defaut.
        self.table.itemDoubleClicked.connect(self._edit_proposal)
        self.table.itemChanged.connect(self._on_item_changed)
        hh = self.table.horizontalHeader()
        # largeurs REGLABLES : le texte long ne doit jamais etre tronque sans
        # recours ; double-clic sur une separation = ajuster au contenu (Qt).
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setStretchLastSection(False)
        hh.setToolTip(t("bbcheck.columns_tooltip"))
        # ElideNone dessine le texte AU-DELA de la cellule et les colonnes se
        # superposent (constate 31/10/2026) : on garde l'elision, et le texte
        # complet se lit dans l'infobulle ou en elargissant la colonne.
        self.table.setTextElideMode(Qt.TextElideMode.ElideRight)
        for col, width in enumerate((70, 120, 220, 380, 380, 380)):
            self.table.setColumnWidth(col, width)
        lay.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        self.btn_select = QPushButton(t("bbcheck.select_all"))
        self.btn_select.clicked.connect(self._select_all)
        buttons.addWidget(self.btn_select)
        self.btn_apply = QPushButton(t("bbcheck.apply"))
        self.btn_apply.clicked.connect(self._apply)
        buttons.addWidget(self.btn_apply)
        buttons.addStretch(1)
        btn_close = QPushButton(t("bbcheck.close"))
        btn_close.clicked.connect(self.reject)
        buttons.addWidget(btn_close)
        lay.addLayout(buttons)

        self._run()

    # ------------------------------------------------------------------
    def _run(self):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self._fill()
        finally:
            QApplication.restoreOverrideCursor()

    def _fill(self):
        self._rows = []
        self.table.setRowCount(0)
        rows = self.widget._snapshot_table()
        header = self.widget.doc.header or [str(i) for i in range(len(rows[0]) if rows else 0)]
        only = self.scope.currentData()
        reports, source, _cols = check_table(
            rows, header, only=[only] if only is not None else None)
        self._source = source
        self._snapshot = rows
        # reparable d'abord : c'est ce sur quoi l'utilisateur peut agir
        reports.sort(key=lambda item: (not item[2].repairable, item[0], item[1]))
        self._rows = reports
        self.table.blockSignals(True)
        self.table.setRowCount(len(reports))
        for i, (r, c, report) in enumerate(reports):
            line_item = QTableWidgetItem(str(r + 2))   # +1 entete, +1 base 1
            line_item.setFlags((line_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                               & ~Qt.ItemFlag.ItemIsEditable)
            if report.repairable:
                line_item.setCheckState(Qt.CheckState.Checked)
            else:
                line_item.setFlags(line_item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                line_item.setToolTip(t("bbcheck.not_repairable"))
                line_item.setForeground(Qt.GlobalColor.gray)
            self.table.setItem(i, 0, line_item)
            col_item = QTableWidgetItem(header[c] if c < len(header) else str(c))
            col_item.setFlags(col_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 1, col_item)
            names = ", ".join(t(_KIND_KEYS[k]) for k in report.kinds)
            # la cellule reste courte et lisible ; le detail des balises est
            # dans l'infobulle (la colonne est trop etroite pour tout afficher)
            prob_item = QTableWidgetItem(names)
            prob_item.setToolTip(f"{names} : {report.details}")
            prob_item.setFlags(prob_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 2, prob_item)
            source_text = rows[r][source] if source < len(rows[r]) else ""
            src_item = QTableWidgetItem(source_text)
            src_item.setFlags(src_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            src_item.setToolTip(source_text or t("bbcheck.source_tooltip"))
            self.table.setItem(i, 3, src_item)
            before_item = QTableWidgetItem(report.before)
            before_item.setFlags(before_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            before_item.setToolTip(report.before)
            self.table.setItem(i, 4, before_item)
            after_item = QTableWidgetItem(report.after)
            after_item.setToolTip(report.after or t("bbcheck.after_tooltip"))
            self.table.setItem(i, 5, after_item)
        self.table.blockSignals(False)

        repairable = sum(1 for _r, _c, rep in reports if rep.repairable)
        self.summary.setText(t("bbcheck.found", n=len(reports), fixable=repairable))
        self.btn_apply.setEnabled(repairable > 0)

    # ------------------------------------------------------------------
    def _edit_proposal(self, item):
        """Double-clic sur la colonne « Apres » : ouvre l'edition. Les autres
        colonnes restent en lecture seule (pas d'ItemIsEditable)."""
        if item is not None and item.column() == 5:
            self.table.editItem(item)

    def _on_item_changed(self, item):
        """Une proposition modifiee a la main devient applicable : la ligne
        est cochee (et redevient decochable) comme une correction calculee."""
        if item is None or item.column() != 5:
            return
        i = item.row()
        r, c, report = self._rows[i]
        line_item = self.table.item(i, 0)
        text = item.text()
        changed = text.strip() and text != report.before
        line_item.setFlags((line_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                           if changed
                           else (line_item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable))
        line_item.setCheckState(Qt.CheckState.Checked if changed
                                else Qt.CheckState.Unchecked)
        if changed:
            line_item.setForeground(Qt.GlobalColor.black)
            line_item.setToolTip("")
        self.btn_apply.setEnabled(bool(self._checked()))

    def _checked(self) -> list[tuple[int, int, str]]:
        fixes = []
        for i, (r, c, report) in enumerate(self._rows):
            item = self.table.item(i, 0)
            after = self.table.item(i, 5)
            if item is None or after is None:
                continue
            if item.checkState() != Qt.CheckState.Checked:
                continue
            text = after.text()
            if not text.strip() or text == report.before:
                continue          # aucune correction a ecrire
            fixes.append((r, c, text))
        return fixes

    def _select_all(self):
        for i, (_r, _c, report) in enumerate(self._rows):
            line_item = self.table.item(i, 0)
            after = self.table.item(i, 5)
            if line_item is None or after is None:
                continue
            if after.text().strip() and after.text() != report.before:
                line_item.setFlags(line_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                line_item.setCheckState(Qt.CheckState.Checked)

    def _apply(self):
        fixes = self._checked()
        if not fixes:
            info(self, t("bbcheck.title"), t("bbcheck.nothing_selected"))
            return
        path = Path(self.widget.path)
        try:
            # sauvegarde CENTRALISEE : jamais un .bak a cote du fichier, il
            # partirait dans l'archive Workshop du scenario
            backup = central_backup(path, kind="localization") if path.exists() else None
            self.widget.apply_bbcode_fixes(fixes)
        except OSError as e:
            info(self, t("bbcheck.title"), t("bbcheck.error", error=str(e)))
            return
        self.accept()
        info(self, t("bbcheck.title"),
             t("bbcheck.applied", n=len(fixes),
               backup=backup.name if backup else "-"))
