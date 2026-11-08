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

"""Codex — onglet Objets : grille filtrable (objets, blocs, jetons), fiche
detail (stats, recette directe ou aplatie, cout materiaux, marchands) et
comparateur a colonnes (epochage de 4 maximum)."""
from __future__ import annotations

from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox,
                             QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                             QPushButton, QSplitter, QTableWidget,
                             QTableWidgetItem, QTextBrowser, QVBoxLayout,
                             QWidget)

from core.codex import KIND_BLOCK, KIND_ITEM, KIND_TOKEN, CodexEntry
from core.i18n import t
from core.propriete_glossary import find_explanation as find_glossary_explanation
from gui.codex_export import headers_of, table_rows

MAX_PINNED = 4
_STAT_PROPS = {"Mass", "Volume", "StackSize", "Durability", "UnlockLevel",
               "MarketPrice", "Category", "Material", "HitPoints", "HP"}
DIFF_COLOR = QColor(255, 243, 205)

# Cases de placement : code ECF -> cle i18n du libelle.
PLACE_FILTERS = (("B", "codex.filter.base"), ("MS", "codex.filter.cv"),
                 ("SS", "codex.filter.sv"), ("GV", "codex.filter.hv"))
_KIND_LABEL = {KIND_ITEM: "codex.kind.item", KIND_BLOCK: "codex.kind.block",
               KIND_TOKEN: "codex.kind.token"}


class NumItem(QTableWidgetItem):
    """Cellule numerique : tri par VALEUR (le tri texte mettrait 999 > 1000)."""

    def __lt__(self, other):
        a = self.data(Qt.ItemDataRole.UserRole)
        b = other.data(Qt.ItemDataRole.UserRole)
        if a is None:
            return True
        if b is None:
            return False
        return a < b


def num_cell(value: Optional[float], text: str = "") -> QTableWidgetItem:
    item = NumItem(text or ("" if value is None else f"{value:g}"))
    item.setData(Qt.ItemDataRole.UserRole, value)
    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return item


def fmt(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value:,.0f}".replace(",", " ") if float(value).is_integer() \
        else f"{value:,.2f}".replace(",", " ")


def _cell(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text or "")
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


class _CkItem(QTableWidgetItem):
    """Case a cocher de la colonne « Comparer » : elle porte l'entree Codex,
    donc l'etat suit la ligne meme apres un tri de la grille."""

    def __init__(self, entry: CodexEntry, checked: bool):
        super().__init__()
        self.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        self.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self.setData(Qt.ItemDataRole.UserRole, entry)


class ItemsTab(QWidget):
    """Grille + fiche detail ; la colonne de cases alimente l'onglet Comparer."""

    pinsChanged = pyqtSignal()          # liste des epingles modifiee
    pinFull = pyqtSignal()              # 5e coche refusee

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = None
        self._pinned: List[str] = []
        self._rows: List[CodexEntry] = []
        self._current: Optional[CodexEntry] = None

        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText(t("codex.search"))
        self.edit_search.setClearButtonEnabled(True)
        self.edit_search.textChanged.connect(self._refilter)
        top.addWidget(self.edit_search, 2)
        self.combo_kind = QComboBox()
        self.combo_kind.addItem(t("codex.kind.all"), "")
        self.combo_kind.addItem(t("codex.kind.item"), KIND_ITEM)
        self.combo_kind.addItem(t("codex.kind.block"), KIND_BLOCK)
        self.combo_kind.addItem(t("codex.kind.token"), KIND_TOKEN)
        self.combo_kind.currentIndexChanged.connect(self._refilter)
        top.addWidget(self.combo_kind)
        self.checks = {}
        for code, key in PLACE_FILTERS:
            box = QCheckBox(t(key))
            box.toggled.connect(self._refilter)
            self.checks[code] = box
            top.addWidget(box)
        self.chk_price = QCheckBox(t("codex.hide_no_price"))
        self.chk_price.toggled.connect(self._refilter)
        top.addWidget(self.chk_price)
        self.lbl_count = QLabel("")
        top.addWidget(self.lbl_count)
        lay.addLayout(top)

        split = QSplitter(Qt.Orientation.Horizontal)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            t("codex.col.pin"), t("codex.col.name"), t("codex.col.kind"),
            t("codex.col.id"), t("codex.col.category"), t("codex.col.mass"),
            t("codex.col.volume"), t("codex.col.price")])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in range(2, 8):          # nombres au plus juste, nom etire
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._show_current)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.doubleClicked.connect(self._toggle_row)
        split.addWidget(self.table)

        side = QWidget()
        side_lay = QVBoxLayout(side)
        side_lay.setContentsMargins(0, 0, 0, 0)
        self.detail = QTextBrowser()
        side_lay.addWidget(self.detail, 1)
        bottom = QHBoxLayout()
        self.chk_flat = QCheckBox(t("codex.detail.flatten"))
        self.chk_flat.toggled.connect(self._show_current)
        bottom.addWidget(self.chk_flat)
        bottom.addStretch(1)
        side_lay.addLayout(bottom)
        split.addWidget(side)
        split.setSizes([720, 460])
        lay.addWidget(split, 1)

    # ------------------------------------------------------------- donnees

    def set_data(self, data) -> None:
        self.data = data
        self._refilter()

    def pinned(self) -> List[CodexEntry]:
        if self.data is None:
            return []
        return [e for name in self._pinned if (e := self.data.entry(name)) is not None]

    def toggle_pin(self, entry: CodexEntry) -> bool:
        """Ajoute/retire un epochage ; False si la liste est pleine."""
        if entry.name in self._pinned:
            self._pinned.remove(entry.name)
            return True
        if len(self._pinned) >= MAX_PINNED:
            return False
        self._pinned.append(entry.name)
        return True

    # ------------------------------------------------------------- filtres

    def _matches(self, entry: CodexEntry) -> bool:
        kind = self.combo_kind.currentData()
        if kind and entry.kind != kind:
            return False
        wanted = {code for code, box in self.checks.items() if box.isChecked()}
        if wanted and not wanted.intersection(entry.allow_placing_at):
            return False
        if self.chk_price.isChecked() and self.data.market_price(entry.name) is None:
            return False
        text = self.edit_search.text().strip().lower()
        if not text:
            return True
        name = self.data.display_name(entry.name).lower()
        info = self.data.display_name(entry.label_key).lower()
        return text in name or text in info or text in entry.name.lower()

    def _refilter(self) -> None:
        if self.data is None:
            return
        rows = [e for e in self.data.entries() if self._matches(e)]
        rows.sort(key=lambda e: self.data.display_name(e.name).lower())
        self._rows = rows
        self._fill(rows)

    def _fill(self, rows: List[CodexEntry]) -> None:
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for row, entry in enumerate(rows):
            price = self.data.market_price(entry.name)
            self.table.setItem(row, 0, _CkItem(entry, entry.name in self._pinned))
            self.table.setItem(row, 1, _cell(self.data.display_name(entry.name)))
            self.table.setItem(row, 2, _cell(t(_KIND_LABEL[entry.kind])))
            self.table.setItem(row, 3, num_cell(entry.id))
            self.table.setItem(row, 4, _cell(entry.category))
            self.table.setItem(row, 5, num_cell(entry.mass))
            self.table.setItem(row, 6, num_cell(entry.volume))
            self.table.setItem(row, 7, num_cell(price))
        self.table.setSortingEnabled(True)
        self.table.blockSignals(False)
        self.lbl_count.setText(t("codex.count", shown=len(rows)))
        if rows:
            self.table.selectRow(0)
        # Toujours redessiner la fiche : si la ligne 0 reste selectionnee,
        # itemSelectionChanged ne part pas et la fiche garderait l'objet
        # precedent (vecu : rechercher « Triple Railguns » affichait « Zyme
        # Vial », l'objet selectionne avant le filtre).
        self._show_current()

    def _selected(self) -> Optional[CodexEntry]:
        row = self.table.currentRow()
        if row < 0 or not self.table.selectionModel().hasSelection():
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def _toggle_row(self, _index=None) -> None:
        """Double-clic : bascule la case de la ligne courante."""
        item = self.table.item(self.table.currentRow(), 0)
        if item is None:
            return
        checked = item.checkState() == Qt.CheckState.Checked
        item.setCheckState(Qt.CheckState.Unchecked if checked else Qt.CheckState.Checked)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        """Coche/decoche une ligne = ajoute/retire du comparateur."""
        if item.column() != 0:
            return
        entry = item.data(Qt.ItemDataRole.UserRole)
        if entry is None:
            return
        checked = item.checkState() == Qt.CheckState.Checked
        if checked == (entry.name in self._pinned):
            return                      # rien ne change (re-remplissage)
        if not self.toggle_pin(entry):
            # 5e coche : la limite du comparateur refuse, on remet la case
            self.table.blockSignals(True)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.table.blockSignals(False)
            self.pinFull.emit()
            return
        self.pinsChanged.emit()

    def export_payload(self):
        """Grille telle qu'affichee (filtres compris), pour le CSV."""
        rows = table_rows(self.table)
        return (headers_of(self.table), rows) if rows else None

    def _show_current(self) -> None:
        entry = self._selected()
        self._current = entry
        if entry is None:
            self.detail.setHtml(t("codex.empty"))
            return
        self.detail.setHtml(self.detail_html(entry, self.chk_flat.isChecked()))

    # -------------------------------------------------------------- fiche

    def detail_html(self, entry: CodexEntry, flatten: bool = False) -> str:
        data = self.data
        rows = [("codex.detail.type", t(_KIND_LABEL[entry.kind])),
                ("codex.col.category", entry.category),
                ("codex.col.id", "" if entry.id is None else str(entry.id)),
                ("codex.col.mass", fmt(entry.mass)),
                ("codex.col.volume", fmt(entry.volume)),
                ("codex.col.stack", fmt(entry.stack)),
                ("codex.col.durability", fmt(entry.durability)),
                ("codex.col.unlock", fmt(entry.unlock_level)),
                ("codex.col.material", entry.material),
                ("codex.col.hp", fmt(entry.hp))]
        if entry.allow_placing_at:
            rows.append(("codex.col.place", ", ".join(entry.allow_placing_at)))
        html = [f"<h3>{data.display_html(entry.name)}</h3>"]
        info = data.display_html(entry.label_key)
        if info and entry.label_key != entry.name:
            html.append(f"<p><i>{info}</i></p>")
        html.append(_table([(t(key), value) for key, value in rows if value]))

        price = data.market_price(entry.name)
        cost, partial = data.materials_cost(entry.name)
        html.append("<h4>" + t("codex.detail.price") + "</h4>")
        html.append(_table([
            (t("codex.col.price"), fmt(price)),
            (t("codex.detail.cost"), ("~" if partial else "") + fmt(cost)),
        ]))
        html.append(self._recipe_html(entry, flatten))
        html.append(self._trade_html(entry))
        html.append(self._props_html(entry))
        return "".join(html)

    def _recipe_html(self, entry: CodexEntry, flatten: bool) -> str:
        template = self.data.template_for(entry.name)
        if template is None:
            return "<h4>" + t("codex.detail.recipe") + "</h4><p>" + t("codex.detail.no_recipe") + "</p>"
        if flatten:
            totals, craft = self.data.flatten_ingredients(entry.name)
            inputs = sorted(totals.items(), key=lambda pair: -pair[1])
            title = t("codex.detail.flat")
        else:
            inputs = list(template.inputs)
            craft = template.craft_time
            title = t("codex.detail.recipe")
        body = _table([(t("codex.detail.station"), ", ".join(template.targets)),
                        (t("codex.detail.time"), f"{craft:.1f} s"),
                        (t("codex.detail.output"), str(template.output_count))])
        rows = [(self.data.display_name(name), f"{qty:g}") for name, qty in inputs]
        return f"<h4>{title}</h4>{body}{_table(rows)}"

    def _trade_html(self, entry: CodexEntry) -> str:
        deals = self.data.traders_for(entry.name)
        if not deals:
            return ""
        rows = []
        for trader, item in deals:
            price = self.data.market_price(item.name)
            if trader.sells(item):
                lo, hi = self.data.estimate_range(item.sell_price, price) or (None, None)
                rows.append((t("codex.traders.sell"), self.data.display_name(trader.name),
                             _range(lo, hi), _range(*_spec(item.sell_stock))))
            if trader.buys(item):
                lo, hi = self.data.estimate_range(item.buy_price, price) or (None, None)
                rows.append((t("codex.traders.buy"), self.data.display_name(trader.name),
                             _range(lo, hi), _range(*_spec(item.buy_max_stock))))
        header = [t("codex.traders.direction"), t("codex.traders.name"),
                  t("codex.col.price"), t("codex.traders.qty")]
        return "<h4>" + t("codex.detail.trade") + "</h4>" + _table(rows, header)

    def _props_html(self, entry: CodexEntry) -> str:
        if not entry.props:
            return ""
        rows = sorted((key, value) for key, value in entry.props.items())
        return "<h4>" + t("codex.detail.props") + "</h4>" + _table(rows)


def _range(lo: Optional[float], hi: Optional[float]) -> str:
    if lo is None:
        return "—"
    return fmt(lo) if lo == hi else f"{fmt(lo)} – {fmt(hi)}"


def _spec(spec) -> tuple:
    return (None, None) if spec is None else (spec.lo_f, spec.hi_f)


def _table(rows, header=None) -> str:
    """Table HTML simple — la fiche est un QTextBrowser, pas une grille Qt.
    Deux a N colonnes, premiere cellule en gras."""
    parts = ["<table cellspacing='0' cellpadding='3' width='100%'>"]
    if header:
        parts.append("<tr>" + "".join(f"<th align='left'>{h}</th>" for h in header) + "</tr>")
    for row in rows:
        parts.append(f"<tr><td><b>{row[0]}</b></td>"
                     + "".join(f"<td>{value}</td>" for value in row[1:]) + "</tr>")
    parts.append("</table>")
    return "".join(parts)


def _norm(value: str) -> str:
    """Cle de comparaison : '1.50' et '1.5' sont la MEME valeur, et l'absence
    ('') est une valeur a part entiere — une propriete presente d'un seul
    cote est une difference, pas un detail a masquer."""
    text = (value or "").strip()
    if not text:
        return ""
    try:
        return f"{float(text.replace(',', '.')):.6g}"
    except ValueError:
        return text


def _differs(values) -> bool:
    return len({_norm(value) for value in values}) > 1


class CompareTab(QWidget):
    """Comparateur : une colonne par objet epingle, lignes alignees, les
    differences surlignees (case « differences seules »)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = None
        self._entries: List[CodexEntry] = []
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.chk_diff = QCheckBox(t("codex.compare.only_diff"))
        self.chk_diff.toggled.connect(self._fill)
        top.addWidget(self.chk_diff)
        self.lbl_hint = QLabel(t("codex.compare.hint"))
        top.addWidget(self.lbl_hint, 1)
        lay.addLayout(top)
        self.table = QTableWidget(0, 1)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.table, 1)

    def set_data(self, data) -> None:
        self.data = data

    def set_items(self, entries: List[CodexEntry]) -> None:
        self._entries = entries
        self._fill()

    def export_payload(self):
        rows = table_rows(self.table)
        return (headers_of(self.table), rows) if rows else None

    def _values(self, entry: CodexEntry) -> Dict[str, str]:
        data = self.data
        cost, partial = data.materials_cost(entry.name)
        template = data.template_for(entry.name)
        totals, craft = data.flatten_ingredients(entry.name)
        values = {
            t("codex.detail.type"): t(_KIND_LABEL[entry.kind]),
            t("codex.col.category"): entry.category,
            t("codex.col.mass"): fmt(entry.mass),
            t("codex.col.volume"): fmt(entry.volume),
            t("codex.col.stack"): fmt(entry.stack),
            t("codex.col.durability"): fmt(entry.durability),
            t("codex.col.hp"): fmt(entry.hp),
            t("codex.col.unlock"): fmt(entry.unlock_level),
            t("codex.col.price"): fmt(data.market_price(entry.name)),
            t("codex.detail.cost"): ("~" if partial else "") + fmt(cost),
            t("codex.detail.time"): f"{craft:.1f} s" if totals else
                                    (f"{template.craft_time:.1f} s" if template else "—"),
        }
        for name, qty in (totals.items() if totals else (template.inputs if template else ())):
            values[data.display_name(name)] = f"{qty:g}"
        for key, value in entry.props.items():
            if key not in _STAT_PROPS:      # deja affiche traduit au-dessus
                values.setdefault(key, value)
        return values

    def _fill(self) -> None:
        if self.data is None or not self._entries:
            self.table.setRowCount(0)
            self.table.setColumnCount(1)
            self.table.setHorizontalHeaderLabels([t("codex.compare.empty")])
            return
        cols = [self.data.display_name(e.name) for e in self._entries]
        maps = [self._values(e) for e in self._entries]
        keys: List[str] = []
        for mapping in maps:
            for key in mapping:
                if key not in keys:
                    keys.append(key)
        rows = []
        for key in keys:
            vals = [mapping.get(key, "") for mapping in maps]
            diff = _differs(vals)
            if self.chk_diff.isChecked() and not diff:
                continue
            rows.append((key, vals, diff))
        self.table.clear()
        self.table.setColumnCount(len(cols) + 1)
        self.table.setHorizontalHeaderLabels([t("codex.compare.property")] + cols)
        self.table.setRowCount(len(rows))
        for row, (key, vals, diff) in enumerate(rows):
            first_cell = _cell(key)
            explanation = find_glossary_explanation(key, scope="ecf")
            if explanation:
                first_cell.setToolTip(f"<b>{key}</b><br>{explanation}")
            self.table.setItem(row, 0, first_cell)
            for col, value in enumerate(vals, start=1):
                item = _cell(value)
                if diff:
                    item.setBackground(DIFF_COLOR)
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()
