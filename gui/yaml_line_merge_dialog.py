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
"""Fenetre de DIFF FIN ligne a ligne d'une unite 'modified' (demande
07/10 : SolarSystemConfig fusionnait en aveugle, aucune vue des
differences). Arbre indente = structure du bloc ; chaque ligne porte
[coche] etat | AVANT (copie de travail) | APRES (source) :
  - identique : grisee, jamais appliquee ;
  - modifiee : DECOCHÉE (copie de travail prioritaire), cochee = la
    source remplace ;
  - ajoutée par la source : COCHÉE (rien ne se perd) ;
  - présente working seul (miroir) : décochée (suppression jamais
    implicite).
L'application reste dans apply_yaml_units : cette fenetre ne fait
qu'editer les flags `checked` des YamlLineRow de l'unite."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QPushButton, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout,
)

from core.i18n import t
from gui.module_info import add_info_button
from core.yaml_merge import YamlLineRow
from gui.theme import icon
from gui.window_geometry import track

_STATE_KEYS = {"same": "yamlmerge.row.same",
               "changed": "yamlmerge.row.changed",
               "add": "yamlmerge.row.add",
               "remove": "yamlmerge.row.remove"}


def _segment_label(seg: tuple) -> str:
    """Libelle lisible d'un segment de navigation ('key',k)/(item,k,v)/
    ('index', i) pour les lignes de contexte de l'arbre."""
    if seg[0] == "key":
        return str(seg[1])
    if seg[0] == "item":
        return str(seg[2])
    return f"[{seg[1]}]"


class YamlLineMergeDialog(QDialog):
    """Detail ligne a ligne d'une unite 'modified' -- edite unit.rows
    en place ; l'appelant applique via apply_yaml_units comme pour les
    autres unites."""

    COL_CHECK, COL_STATE, COL_BEFORE, COL_AFTER = range(4)

    def __init__(self, unit, working_yaml, source_yaml, parent=None):
        super().__init__(parent)
        self.unit = unit
        self._items: list = []          # (QTreeWidgetItem, YamlLineRow)
        self.setWindowTitle(t("yamlmerge.lines.title", name=unit.name))
        self.resize(980, 640)
        track(self, "yaml_line_merge")

        layout = QVBoxLayout(self)
        self.intro_label = QLabel(t("yamlmerge.lines.intro",
                                    name=unit.name, root=unit.root))
        self.intro_label.setWordWrap(True)
        layout.addWidget(self.intro_label)

        self.hide_same = QCheckBox(t("yamlmerge.lines.hide_same"))
        self.hide_same.toggled.connect(self._apply_filter)
        layout.addWidget(self.hide_same)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([
            t("mergeplan.col_apply"), t("yamlmerge.lines.col_state"),
            t("yamlmerge.lines.col_before"), t("yamlmerge.lines.col_after")])
        self.tree.setColumnWidth(self.COL_CHECK, 70)
        self.tree.setColumnWidth(self.COL_STATE, 110)
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.tree.setFont(mono)
        self.tree.itemChanged.connect(self._on_item_changed)
        # vecu 07/10 : QTreeWidgetItem est EDITABLE par defaut -- le
        # double-clic ouvrait un editeur de texte au lieu de cocher.
        # Editable retire partout ; double-clic sur la ligne = toggle.
        self.tree.itemDoubleClicked.connect(self._on_double_clicked)
        layout.addWidget(self.tree, 1)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        row = QHBoxLayout()
        self.btn_all = QPushButton(t("trans.check_all"))
        self.btn_all.clicked.connect(lambda: self._set_all(True))
        row.addWidget(self.btn_all)
        self.btn_none = QPushButton(t("trans.uncheck_all"))
        self.btn_none.clicked.connect(lambda: self._set_all(False))
        row.addWidget(self.btn_none)
        add_info_button(row, "linemerge.info_html")
        row.addStretch()
        self.btn_ok = QPushButton(icon("fa5s.check", "#ffffff"),
                                  t("mergepreview.btn_apply"))
        self.btn_ok.setObjectName("primaryButton")
        self.btn_ok.clicked.connect(self.accept)
        row.addWidget(self.btn_ok)
        self.btn_cancel = QPushButton(t("btn.cancel"))
        self.btn_cancel.setObjectName("secondaryButton")
        self.btn_cancel.clicked.connect(self.reject)
        row.addWidget(self.btn_cancel)
        layout.addLayout(row)

        self._context_items: dict = {}
        self._fill()
        self.tree.itemChanged.disconnect(self._on_item_changed)
        self._refresh_status()
        self.tree.itemChanged.connect(self._on_item_changed)

    # ------------------------------------------------------------------ vue

    def _context_item(self, segments: tuple):
        """Item de CONTEXTE (non cochable) pour un chemin structurel --
        l'indentation montre la hierarchie du bloc."""
        if not segments:
            return self.tree.invisibleRootItem()
        item = self._context_items.get(segments)
        if item is not None:
            return item
        parent = self._context_item(segments[:-1])
        item = QTreeWidgetItem(["", "", _segment_label(segments[-1]), ""])
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable
                      & ~Qt.ItemFlag.ItemIsEditable)
        font = item.font(self.COL_STATE)
        font.setItalic(True)
        item.setFont(self.COL_STATE, font)
        parent.addChild(item)
        self._context_items[segments] = item
        return item

    def _fill(self) -> None:
        for row in self.unit.rows:
            parent = self._context_item(row.path[:-1])
            state_label = t(_STATE_KEYS.get(row.state, row.state))
            item = QTreeWidgetItem(["", state_label, row.before, row.after])
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if row.state == "same":
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                font = item.font(self.COL_STATE)
                font.setItalic(True)
                item.setFont(self.COL_STATE, font)
            else:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(
                    self.COL_CHECK,
                    Qt.CheckState.Checked if row.checked
                    else Qt.CheckState.Unchecked)
            if row.replace_subtree:
                item.setToolTip(self.COL_AFTER, t("yamlmerge.lines.subtree"))
            item.setData(self.COL_CHECK, Qt.ItemDataRole.UserRole, row)
            self._items.append((item, row))
            parent.addChild(item)
        self._apply_filter(self.hide_same.isChecked())

    def _apply_filter(self, hidden: bool) -> None:
        for item, row in self._items:
            item.setHidden(hidden and row.state == "same")
        self.tree.expandAll()

    # ------------------------------------------------------------- coches

    def _on_item_changed(self, item, _column) -> None:
        row = item.data(self.COL_CHECK, Qt.ItemDataRole.UserRole)
        if not isinstance(row, YamlLineRow):
            return
        row.checked = item.checkState(self.COL_CHECK) \
            == Qt.CheckState.Checked
        self._refresh_status()

    def _on_double_clicked(self, item, column) -> None:
        """Double-clic sur la ligne (hors colonne de la case) = cocher /
        decocher -- la case elle-meme reste cliable ; l'edition de texte
        est desactivee (vecu 07/10 : le double-clic ouvrait un editeur)."""
        if column == self.COL_CHECK:
            return
        row = item.data(self.COL_CHECK, Qt.ItemDataRole.UserRole)
        if not isinstance(row, YamlLineRow) or row.state == "same":
            return
        item.setCheckState(self.COL_CHECK,
                           Qt.CheckState.Unchecked if row.checked
                           else Qt.CheckState.Checked)

    def _set_all(self, state: bool) -> None:
        cs = Qt.CheckState.Checked if state else Qt.CheckState.Unchecked
        self.tree.itemChanged.disconnect(self._on_item_changed)
        for item, row in self._items:
            if row.state != "same":
                item.setCheckState(self.COL_CHECK, cs)
                row.checked = state
        self.tree.itemChanged.connect(self._on_item_changed)
        self._refresh_status()

    def _refresh_status(self) -> None:
        rows = [r for r in self.unit.rows if r.state != "same"]
        picked = [r for r in rows if r.checked]
        counts = t("yamlmerge.lines.status",
                   chg=sum(1 for r in picked if r.state == "changed"),
                   add=sum(1 for r in picked if r.state == "add"),
                   rem=sum(1 for r in picked if r.state == "remove"))
        self.status_label.setText(counts)

    def selected_count(self) -> int:
        return sum(1 for r in self.unit.rows
                   if r.checked and r.state != "same")

    def removal_count(self) -> int:
        return sum(1 for r in self.unit.rows
                   if r.checked and r.state == "remove")
