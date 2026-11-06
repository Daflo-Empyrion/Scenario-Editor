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

"""Codex — onglet Marchands : fiche negociant, opportunites de trade, lieux
(croisement par les prefabs, voir `core/codex_places.py`) et routes de
commerce. Lieux et routes sont des donnees de TRAVAIL : elles vivent dans
~/.empyrion_editor/codex/<scenario>/ (jamais dans le scenario)."""
from __future__ import annotations

import copy
import datetime
from typing import Dict, List, Optional, Sequence, Tuple

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QAbstractItemView, QComboBox, QDoubleSpinBox,
                             QGroupBox, QHBoxLayout, QHeaderView,
                             QInputDialog, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QPushButton, QSplitter,
                             QTableWidget, QTableWidgetItem, QTabWidget,
                             QTextBrowser, QVBoxLayout, QWidget)

from core.codex import (CodexData, Opportunity, load_store, route_net,
                        save_store)
from core.codex_places import (PlacesIndex, TraderPlace, build_places_index,
                               cached_places, pois_of_playfield)
from core.i18n import t
from gui.busy import run_long
from gui.codex_export import export_rows, headers_of, table_rows
from gui.codex_items import _cell, _range, fmt, num_cell

# Types d'etape d'une route (code stocke -> cle i18n du libelle).
STOP_KINDS = (("planete", "codex.route.kind.planet"),
              ("orbite", "codex.route.kind.orbit"),
              ("systeme", "codex.route.kind.system"),
              ("poi", "codex.route.kind.poi"))
_KIND_LABEL = {code: key for code, key in STOP_KINDS}


def _editable(text: str = "") -> QTableWidgetItem:
    return QTableWidgetItem(text or "")


def _qty(spec) -> Tuple[Optional[float], Optional[float]]:
    return (None, None) if spec is None else (spec.lo_f, spec.hi_f)


def _table(rows, header=None) -> str:
    parts = ["<table cellspacing='0' cellpadding='3' width='100%'>"]
    if header:
        parts.append("<tr>" + "".join(f"<th align='left'>{h}</th>" for h in header) + "</tr>")
    for row in rows:
        parts.append("<tr>" + "".join(f"<td>{value}</td>" for value in row) + "</tr>")
    parts.append("</table>")
    return "".join(parts)


def _place_label(instances, type_name: str) -> str:
    """« Instance  [type] », ou juste le nom quand les deux coincident."""
    instance = instances[0].instance if instances else type_name
    if not instance or instance == type_name:
        return type_name
    return f"{instance}  [{type_name}]"


class TradersPane(QWidget):
    """Liste des marchands + fiche detail (ventes / rachats)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data: Optional[CodexData] = None
        self._trader = None
        lay = QHBoxLayout(self)
        split = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        left_lay = QVBoxLayout(left)
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText(t("codex.traders.search"))
        self.edit_search.setClearButtonEnabled(True)
        self.edit_search.textChanged.connect(self._refilter)
        left_lay.addWidget(self.edit_search)
        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._show_current)
        left_lay.addWidget(self.list, 1)
        split.addWidget(left)
        self.detail = QTextBrowser()
        split.addWidget(self.detail)
        split.setSizes([320, 700])
        lay.addWidget(split)

    def set_data(self, data: CodexData) -> None:
        self.data = data
        self._refilter()

    def _refilter(self) -> None:
        if self.data is None:
            return
        text = self.edit_search.text().strip().lower()
        self.list.clear()
        for trader in sorted(self.data.traders, key=lambda tr: tr.name.lower()):
            label = self.data.display_name(trader.name)
            if text and text not in label.lower() and text not in trader.name.lower():
                continue
            item = QListWidgetItem(f"{label}  ({len(trader.items)})")
            item.setData(Qt.ItemDataRole.UserRole, trader.name)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)
        else:
            self.detail.setHtml(t("codex.empty"))

    def _show_current(self, *_args) -> None:
        item = self.list.currentItem()
        if item is None or self.data is None:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        trader = next((tr for tr in self.data.traders if tr.name == name), None)
        if trader is None:
            return
        self._trader = trader
        self.detail.setHtml(self._html(trader))

    def _html(self, trader) -> str:
        data = self.data
        parts = [f"<h3>{data.display_html(trader.name)}</h3>"]
        info = [("codex.traders.discount", trader.discount or "—"),
                ("codex.traders.items", str(len(trader.items)))]
        parts.append(_table([(t(k), v) for k, v in info]))
        if trader.selling_text:
            parts.append(f"<p><i>{trader.selling_text}</i></p>")
        parts.append(self._lines(trader.selling(), selling=True))
        parts.append(self._lines(trader.buying(), selling=False))
        if trader.raw_lines:
            parts.append("<h4>" + t("codex.traders.unreadable") + "</h4>")
            parts.append("".join(f"<p><code>{line}</code></p>" for line in trader.raw_lines))
        return "".join(parts)

    def _deal_rows(self, items, selling: bool) -> List[List[str]]:
        """(item, quantite, prix estime) d'un sens de trade — sert a la fiche
        ET a l'export."""
        data = self.data
        rows = []
        for item in items:
            price = data.market_price(item.name)
            if selling:
                rng = data.estimate_range(item.sell_price, price)
                qty = item.sell_stock
            else:
                rng = data.estimate_range(item.buy_price, price)
                qty = item.buy_max_stock
            lo, hi = rng if rng else (None, None)
            q_lo, q_hi = _qty(qty)
            rows.append([data.display_name(item.name), _range(q_lo, q_hi), _range(lo, hi)])
        return rows

    def _lines(self, items, selling: bool) -> str:
        title = t("codex.traders.sell") if selling else t("codex.traders.buy")
        if not items:
            return f"<h4>{title}</h4><p>{t('codex.traders.none')}</p>"
        rows = self._deal_rows(items, selling)
        html = f"<h4>{title}</h4>" + _table(
            rows, [t("codex.traders.item"), t("codex.traders.qty"),
                   t("codex.col.price")])
        if not selling:
            total_lo = total_hi = 0.0
            for item in items:
                price = self.data.market_price(item.name)
                rng = self.data.estimate_range(item.buy_price, price)
                q_lo, q_hi = _qty(item.buy_max_stock)
                if rng and q_lo is not None:
                    total_lo += rng[0] * q_lo
                    total_hi += rng[1] * q_hi
            if total_lo:
                html += "<p><b>" + t("codex.traders.total") + "</b> " + \
                        _range(total_lo, total_hi) + "</p>"
        return html

    def export_payload(self) -> Optional[Tuple[List[str], List[List[str]]]]:
        """Lignes (marchand, sens, item, quantite, prix) du marchand affiche."""
        if self._trader is None or self.data is None:
            return None
        rows = []
        for selling, items in ((True, self._trader.selling()),
                               (False, self._trader.buying())):
            direction = t("codex.traders.sell") if selling else t("codex.traders.buy")
            for item, qty, price in self._deal_rows(items, selling):
                rows.append([self.data.display_name(self._trader.name),
                             direction, item, qty, price])
        if not rows:
            return None
        return ([t("codex.traders.name"), t("codex.traders.direction"),
                 t("codex.traders.item"), t("codex.traders.qty"),
                 t("codex.col.price")], rows)


class OpportunitiesPane(QWidget):
    """Achete chez l'un, revend a l'autre : profit estime par item."""

    routeRequested = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data: Optional[CodexData] = None
        self._opps: List[Opportunity] = []
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel(t("codex.opp.min_profit")))
        self.spin = QDoubleSpinBox()
        self.spin.setRange(0, 10_000_000)
        self.spin.setDecimals(0)
        self.spin.setSingleStep(1000)
        self.spin.setValue(1)              # les paires sans marge (profit 0) sortent par defaut
        self.spin.valueChanged.connect(self._fill)
        top.addWidget(self.spin)
        self.lbl_count = QLabel("")
        top.addWidget(self.lbl_count, 1)
        self.btn_route = QPushButton(t("codex.opp.to_route"))
        self.btn_route.setToolTip(t("codex.opp.to_route.tip"))
        self.btn_route.clicked.connect(self._make_route)
        top.addWidget(self.btn_route)
        lay.addLayout(top)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            t("codex.traders.item"), t("codex.opp.seller"), t("codex.opp.buyer"),
            t("codex.opp.qty"), t("codex.opp.profit")])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self.table.setWordWrap(False)
        self.table.setSortingEnabled(True)
        lay.addWidget(self.table, 1)

    def set_data(self, data: CodexData) -> None:
        self.data = data
        self._opps = data.opportunities()
        self._fill()

    def rows(self) -> List[Opportunity]:
        """Opportunites affichees (filtre « profit minimum »)."""
        minimum = self.spin.value()
        return [opp for opp in self._opps if (opp.profit or 0) >= minimum]

    def all_opportunities(self) -> List[Opportunity]:
        """Toutes les opportunites : le net d'une route ne doit pas dependre
        du filtre d'affichage."""
        return list(self._opps)

    def _fill(self) -> None:
        if self.data is None:
            return
        rows = self.rows()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for row, opp in enumerate(rows):
            self.table.setItem(row, 0, _cell(self.data.display_name(opp.item)))
            self.table.setItem(row, 1, _cell(self.data.display_name(opp.seller)))
            self.table.setItem(row, 2, _cell(self.data.display_name(opp.buyer)))
            self.table.setItem(row, 3, num_cell(opp.qty))
            self.table.setItem(row, 4, num_cell(opp.profit))
        self.table.setSortingEnabled(True)
        self.lbl_count.setText(t("codex.count", shown=len(rows)))

    def _selected(self) -> Optional[Opportunity]:
        row = self.table.currentRow()
        rows = self.rows()
        if row < 0 or row >= len(rows):
            return None
        return rows[row]

    def _make_route(self) -> None:
        opp = self._selected()
        if opp is not None:
            self.routeRequested.emit(opp)

    def export_payload(self) -> Optional[Tuple[List[str], List[List[str]]]]:
        if self.data is None:
            return None
        rows = [[self.data.display_name(opp.item),
                 self.data.display_name(opp.seller),
                 self.data.display_name(opp.buyer),
                 fmt(opp.qty), fmt(opp.profit)] for opp in self.rows()]
        if not rows:
            return None
        return ([t("codex.traders.item"), t("codex.opp.seller"),
                 t("codex.opp.buyer"), t("codex.opp.qty"),
                 t("codex.opp.profit")], rows)


class PlacesPane(QWidget):
    """Lieux d'un marchand (croisement prefabs) et carnet de lieux suivis."""

    LOC_COLS = ("codex.loc.trader", "codex.loc.playfield", "codex.loc.poi",
                "codex.loc.restock", "codex.loc.status", "codex.loc.notes")
    LOC_KEYS = {1: "playfield", 2: "poi", 3: "restock", 5: "notes"}
    KNOWN_COLS = ("codex.loc.playfield", "codex.loc.poi", "codex.loc.system",
                  "codex.loc.sector", "codex.loc.source", "codex.loc.confidence")

    def __init__(self, working_root, parent=None):
        super().__init__(parent)
        self.root = working_root
        self.data: Optional[CodexData] = None
        self.index: Optional[PlacesIndex] = None
        self._locations: Dict[str, List[dict]] = {}

        lay = QVBoxLayout(self)

        box = QGroupBox(t("codex.loc.known"))
        box_lay = QVBoxLayout(box)
        top = QHBoxLayout()
        self.combo_trader = QComboBox()
        self.combo_trader.currentIndexChanged.connect(self._fill_known)
        top.addWidget(QLabel(t("codex.loc.trader")))
        top.addWidget(self.combo_trader, 1)
        self.btn_search = QPushButton(t("codex.loc.search"))
        self.btn_search.setToolTip(t("codex.loc.search.tip"))
        self.btn_search.clicked.connect(self._search)
        top.addWidget(self.btn_search)
        self.btn_add_known = QPushButton(t("codex.loc.add"))
        self.btn_add_known.clicked.connect(self._add_known)
        top.addWidget(self.btn_add_known)
        box_lay.addLayout(top)
        self.lbl_state = QLabel(t("codex.loc.search_hint"))
        self.lbl_state.setWordWrap(True)
        box_lay.addWidget(self.lbl_state)
        self.known_table = QTableWidget(0, len(self.KNOWN_COLS))
        self.known_table.setHorizontalHeaderLabels([t(key) for key in self.KNOWN_COLS])
        self.known_table.verticalHeader().setVisible(False)
        self.known_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.known_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        box_lay.addWidget(self.known_table, 1)
        lay.addWidget(box, 1)

        log = QGroupBox(t("codex.loc.log"))
        log_lay = QVBoxLayout(log)
        add = QHBoxLayout()
        self.combo_playfield = QComboBox()
        self.combo_playfield.setEditable(True)
        self.combo_playfield.currentIndexChanged.connect(self._fill_pois)
        add.addWidget(QLabel(t("codex.loc.playfield")))
        add.addWidget(self.combo_playfield, 1)
        self.combo_poi = QComboBox()
        self.combo_poi.setEditable(True)
        add.addWidget(QLabel(t("codex.loc.poi")))
        add.addWidget(self.combo_poi, 1)
        self.btn_add = QPushButton(t("codex.loc.add"))
        self.btn_add.clicked.connect(self._add_location)
        add.addWidget(self.btn_add)
        self.btn_visit = QPushButton(t("codex.loc.visited"))
        self.btn_visit.clicked.connect(self._mark_visited)
        add.addWidget(self.btn_visit)
        self.btn_del = QPushButton(t("codex.loc.remove"))
        self.btn_del.clicked.connect(self._remove_location)
        add.addWidget(self.btn_del)
        log_lay.addLayout(add)
        self.loc_table = QTableWidget(0, len(self.LOC_COLS))
        self.loc_table.setHorizontalHeaderLabels([t(key) for key in self.LOC_COLS])
        self.loc_table.verticalHeader().setVisible(False)
        self.loc_table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.Stretch)
        self.loc_table.itemChanged.connect(self._location_edited)
        log_lay.addWidget(self.loc_table, 1)
        lay.addWidget(log, 1)

    # ------------------------------------------------------------ donnees

    def set_data(self, data: CodexData, index: Optional[PlacesIndex] = None) -> None:
        self.data = data
        self.index = index
        stored = load_store(self.root, "locations")
        self._locations = {name: [dict(spot) for spot in spots]
                           for name, spots in stored.items() if isinstance(spots, list)}
        self.combo_trader.blockSignals(True)
        self.combo_trader.clear()
        for trader in sorted(data.traders, key=lambda tr: tr.name.lower()):
            self.combo_trader.addItem(data.display_name(trader.name), trader.name)
        self.combo_trader.blockSignals(False)
        self._fill_playfields_combo()
        self._fill_known()
        self._fill_locations()

    def set_index(self, index: Optional[PlacesIndex]) -> None:
        self.index = index
        self._fill_playfields_combo()
        self._fill_known()

    def _fill_playfields_combo(self) -> None:
        current = self.combo_playfield.currentText()
        self.combo_playfield.blockSignals(True)
        self.combo_playfield.clear()
        if self.index is not None:
            for type_name in sorted(self.index.by_type):
                instances = self.index.by_type[type_name]
                self.combo_playfield.addItem(_place_label(instances, type_name),
                                             type_name)
        self.combo_playfield.setCurrentText(current)
        if self.combo_playfield.currentIndex() < 0 and self.combo_playfield.count():
            self.combo_playfield.setCurrentIndex(0)
        self.combo_playfield.blockSignals(False)
        self._fill_pois()

    def _fill_pois(self) -> None:
        type_name = self.combo_playfield.currentData()
        current = self.combo_poi.currentText()
        self.combo_poi.clear()
        if isinstance(type_name, str) and type_name:
            self.combo_poi.addItems(pois_of_playfield(self.root, type_name))
        self.combo_poi.setCurrentText(current)

    def _playfield_type(self) -> str:
        data = self.combo_playfield.currentData()
        if isinstance(data, str) and data:
            return data
        text = self.combo_playfield.currentText().strip()
        return text.split("[")[-1].rstrip("]") if "[" in text else text

    # -------------------------------------------------------- lieux connus

    def _fill_known(self) -> None:
        trader = self.combo_trader.currentData()
        self.known_table.setRowCount(0)
        if self.data is None or not trader:
            return
        if self.index is None:
            self.lbl_state.setText(t("codex.loc.search_hint"))
            return
        places = self.index.places_for(trader)
        rows = [self._known_row(place) for place in places]
        if not rows:
            # Rien de nomme dans les prefabs : les POI de commerce du scenario
            # sont proposes comme CANDIDATS, jamais comme certitude.
            for playfield, poi in self.index.candidates[:30]:
                rows.append([playfield, poi, "", "",
                             t("codex.loc.source_candidate"), ""])
        self.known_table.setRowCount(len(rows))
        for row, values in enumerate(rows):
            for col, value in enumerate(values):
                self.known_table.setItem(row, col, _cell(str(value)))
        self.known_table.resizeColumnsToContents()
        self.known_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        if places:
            self.lbl_state.setText(t("codex.loc.found", n=len(places)))
        elif rows:
            self.lbl_state.setText(t("codex.loc.candidates",
                                     n=len(self.index.candidates)))
        else:
            self.lbl_state.setText(t("codex.loc.unknown"))

    def _known_row(self, place: TraderPlace) -> List[str]:
        system = sector = ""
        if place.instances:
            system = place.instances[0][0]
            coords = place.instances[0][1]
            sector = f"[{coords[0]}, {coords[1]}, {coords[2]}]"
            if len(place.instances) > 1:
                system += f" (+{len(place.instances) - 1})"
        source = t("codex.loc.source_prefab") if place.source == "prefab" \
            else t("codex.loc.source_zone")
        return [place.playfield, place.poi, system, sector, source,
                t(f"codex.loc.conf.{place.confidence}")]

    def _search(self) -> None:
        if self.data is None:
            return
        names = [trader.name for trader in self.data.traders]
        self.btn_search.setEnabled(False)
        self.lbl_state.setText(t("codex.loc.searching"))
        try:
            index = run_long(self, lambda: build_places_index(self.root, names),
                             "codex.loc.searching")
        except Exception as exc:                     # noqa: BLE001 - affiche
            self.lbl_state.setText(t("codex.load_error", error=str(exc)))
            return
        finally:
            self.btn_search.setEnabled(True)
        self.set_index(index)

    def _add_known(self) -> None:
        trader = self.combo_trader.currentData()
        row = self.known_table.currentRow()
        if not trader or row < 0:
            return
        playfield = self.known_table.item(row, 0)
        poi = self.known_table.item(row, 1)
        if playfield is None:
            return
        self._locations.setdefault(trader, []).append({
            "playfield": playfield.text(),
            "poi": poi.text() if poi is not None else "",
            "restock": 60, "notes": "", "visited": ""})
        self._save_locations()

    # ------------------------------------------------------------- carnet

    def _location_rows(self) -> List[Tuple[str, dict]]:
        return [(trader, spot) for trader, spots in self._locations.items()
                for spot in spots]

    def _fill_locations(self) -> None:
        self.loc_table.blockSignals(True)
        rows = self._location_rows()
        self.loc_table.setRowCount(len(rows))
        now = datetime.datetime.now()
        for row, (trader_name, spot) in enumerate(rows):
            name = self.data.display_name(trader_name) if self.data else trader_name
            trader_item = _cell(name)
            trader_item.setData(Qt.ItemDataRole.UserRole, trader_name)
            self.loc_table.setItem(row, 0, trader_item)
            self.loc_table.setItem(row, 1, _editable(spot.get("playfield", "")))
            self.loc_table.setItem(row, 2, _editable(spot.get("poi", "")))
            restock = num_cell(float(spot.get("restock") or 0))
            restock.setFlags(restock.flags() | Qt.ItemFlag.ItemIsEditable)
            self.loc_table.setItem(row, 3, restock)
            self.loc_table.setItem(row, 4, _cell(self._status(spot, now)))
            self.loc_table.item(row, 4).setToolTip(spot.get("visited", ""))
            self.loc_table.setItem(row, 5, _editable(spot.get("notes", "")))
        self.loc_table.blockSignals(False)

    @staticmethod
    def _status(spot: dict, now: datetime.datetime) -> str:
        visited, restock = spot.get("visited"), float(spot.get("restock") or 0)
        if not visited or restock <= 0:
            return t("codex.loc.unknown")
        try:
            since = datetime.datetime.fromisoformat(visited)
        except ValueError:
            return t("codex.loc.unknown")
        left = restock - (now - since).total_seconds() / 60.0
        return t("codex.loc.ready") if left <= 0 else t("codex.loc.wait", n=int(left) + 1)

    def _add_location(self) -> None:
        trader = self.combo_trader.currentData()
        if not trader:
            return
        self._locations.setdefault(trader, []).append({
            "playfield": self._playfield_type(),
            "poi": self.combo_poi.currentText().strip(),
            "restock": 60, "notes": "", "visited": ""})
        self._save_locations()

    def _remove_location(self) -> None:
        row = self.loc_table.currentRow()
        rows = self._location_rows()
        if row < 0 or row >= len(rows):
            return
        trader_name, spot = rows[row]
        self._locations[trader_name].remove(spot)
        if not self._locations[trader_name]:
            del self._locations[trader_name]
        self._save_locations()

    def _mark_visited(self) -> None:
        row = self.loc_table.currentRow()
        rows = self._location_rows()
        if row < 0 or row >= len(rows):
            return
        rows[row][1]["visited"] = datetime.datetime.now().isoformat(timespec="minutes")
        self._save_locations()

    def _location_edited(self, item: QTableWidgetItem) -> None:
        rows = self._location_rows()
        if item.row() >= len(rows):
            return
        _trader_name, spot = rows[item.row()]
        key = self.LOC_KEYS.get(item.column())
        if key is None:
            return
        if key == "restock":
            try:
                spot["restock"] = int(float(item.text().replace(" ", "") or 0))
            except ValueError:
                spot["restock"] = 0
        else:
            spot[key] = item.text()
        self._save_locations()

    def _save_locations(self) -> None:
        save_store(self.root, "locations", self._locations)
        self._fill_locations()

    def export_payload(self) -> Optional[Tuple[List[str], List[List[str]]]]:
        rows = table_rows(self.loc_table)
        if not rows:
            return None
        return headers_of(self.loc_table), rows


class RoutesPane(QWidget):
    """Carnet de lieux : une route = une suite d'etapes (destination, item
    optionnel, note, vu). Le profit marchand reste calcule quand l'item est
    une opportunite connue."""

    COLS = ("codex.route.col.kind", "codex.route.col.playfield",
            "codex.route.col.system", "codex.route.col.sector",
            "codex.route.col.poi", "codex.route.col.item",
            "codex.route.col.qty", "codex.route.col.note", "codex.route.col.seen")

    def __init__(self, working_root, parent=None):
        super().__init__(parent)
        self.root = working_root
        self.data: Optional[CodexData] = None
        self.index: Optional[PlacesIndex] = None
        self._opps: List[Opportunity] = []
        self._routes: List[dict] = []

        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.combo_routes = QComboBox()
        self.combo_routes.currentIndexChanged.connect(self._fill_route)
        top.addWidget(QLabel(t("codex.route.name")))
        top.addWidget(self.combo_routes, 1)
        self.btn_new = QPushButton(t("codex.route.add"))
        self.btn_new.clicked.connect(lambda: self._add_route())
        top.addWidget(self.btn_new)
        self.btn_dup = QPushButton(t("codex.route.duplicate"))
        self.btn_dup.clicked.connect(self._duplicate_route)
        top.addWidget(self.btn_dup)
        self.btn_rename = QPushButton(t("codex.route.rename"))
        self.btn_rename.clicked.connect(self._rename_route_dialog)
        top.addWidget(self.btn_rename)
        self.btn_del = QPushButton(t("codex.route.remove"))
        self.btn_del.clicked.connect(self._remove_route)
        top.addWidget(self.btn_del)
        self.btn_export = QPushButton(t("codex.route.export"))
        self.btn_export.clicked.connect(self.export_current)
        top.addWidget(self.btn_export)
        lay.addLayout(top)

        add = QHBoxLayout()
        self.combo_kind = QComboBox()
        for code, key in STOP_KINDS:
            self.combo_kind.addItem(t(key), code)
        add.addWidget(self.combo_kind)
        self.combo_playfield = QComboBox()
        self.combo_playfield.setEditable(True)
        self.combo_playfield.currentIndexChanged.connect(self._fill_pois)
        add.addWidget(self.combo_playfield, 1)
        self.combo_poi = QComboBox()
        self.combo_poi.setEditable(True)
        add.addWidget(self.combo_poi, 1)
        self.combo_item = QComboBox()
        self.combo_item.setEditable(True)
        add.addWidget(self.combo_item, 1)
        self.spin_qty = QDoubleSpinBox()
        self.spin_qty.setRange(0, 100000)
        self.spin_qty.setDecimals(0)
        self.spin_qty.setValue(1)
        add.addWidget(self.spin_qty)
        self.btn_add = QPushButton(t("codex.route.add_stop"))
        self.btn_add.clicked.connect(self._add_stop)
        add.addWidget(self.btn_add)
        lay.addLayout(add)

        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels([t(key) for key in self.COLS])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self._stop_edited)
        lay.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        self.btn_remove_stop = QPushButton(t("codex.route.remove_stop"))
        self.btn_remove_stop.clicked.connect(self._remove_stop)
        bottom.addWidget(self.btn_remove_stop)
        self.btn_up = QPushButton(t("codex.route.up"))
        self.btn_up.clicked.connect(lambda: self._move_stop(-1))
        bottom.addWidget(self.btn_up)
        self.btn_down = QPushButton(t("codex.route.down"))
        self.btn_down.clicked.connect(lambda: self._move_stop(1))
        bottom.addWidget(self.btn_down)
        self.btn_seen = QPushButton(t("codex.loc.visited"))
        self.btn_seen.clicked.connect(self._mark_seen)
        bottom.addWidget(self.btn_seen)
        self.lbl_net = QLabel("")
        bottom.addWidget(self.lbl_net, 1)
        lay.addLayout(bottom)

    # ------------------------------------------------------------ donnees

    def set_data(self, data: CodexData, opportunities: List[Opportunity],
                 index: Optional[PlacesIndex] = None) -> None:
        self.data = data
        self._opps = opportunities
        self.index = index
        stored = load_store(self.root, "routes")
        self._routes = [self._migrate(route) for route in (stored.get("routes") or [])
                        if isinstance(route, dict)]
        self.combo_item.clear()
        for entry in sorted(data.entries(),
                            key=lambda entry: data.display_name(entry.name).lower()):
            self.combo_item.addItem(data.display_name(entry.name), entry.name)
        self.set_index(index)
        self._fill_routes()

    def set_index(self, index: Optional[PlacesIndex]) -> None:
        self.index = index
        current = self.combo_playfield.currentData()
        self.combo_playfield.blockSignals(True)
        self.combo_playfield.clear()
        if index is not None:
            for type_name in sorted(index.by_type):
                instances = index.by_type[type_name]
                self.combo_playfield.addItem(_place_label(instances, type_name),
                                             type_name)
        self.combo_playfield.blockSignals(False)
        if current is not None:
            pos = self.combo_playfield.findData(current)
            if pos >= 0:
                self.combo_playfield.setCurrentIndex(pos)
        if self.combo_playfield.currentIndex() < 0 and self.combo_playfield.count():
            self.combo_playfield.setCurrentIndex(0)
        self._fill_pois()
        self._fill_route()

    def _fill_pois(self) -> None:
        type_name = self.combo_playfield.currentData()
        current = self.combo_poi.currentText()
        self.combo_poi.clear()
        if isinstance(type_name, str) and type_name:
            self.combo_poi.addItems(pois_of_playfield(self.root, type_name))
        self.combo_poi.setCurrentText(current)

    def _playfield_type(self) -> str:
        data = self.combo_playfield.currentData()
        if isinstance(data, str) and data:
            return data
        text = self.combo_playfield.currentText().strip()
        return text.split("[")[-1].rstrip("]") if "[" in text else text

    @staticmethod
    def _migrate(route: dict) -> dict:
        """Ancien format (etapes {item, qty}) -> carnet de lieux."""
        route.setdefault("name", "?")
        route.setdefault("notes", "")
        stops = []
        for stop in route.get("stops") or []:
            stops.append({
                "kind": str(stop.get("kind") or ""),
                "playfield": str(stop.get("playfield") or ""),
                "poi": str(stop.get("poi") or ""),
                "item": str(stop.get("item") or ""),
                "qty": int(float(stop.get("qty") or 0)),
                "note": str(stop.get("note") or ""),
                "seen": bool(stop.get("seen") or False),
                "seen_at": str(stop.get("seen_at") or ""),
            })
        route["stops"] = stops
        return route

    def _current_route(self) -> Optional[dict]:
        idx = self.combo_routes.currentIndex()
        if 0 <= idx < len(self._routes):
            return self._routes[idx]
        return None

    def _save(self, refill: bool = False) -> None:
        save_store(self.root, "routes", {"routes": self._routes})
        if refill:
            self._fill_routes()

    # ------------------------------------------------------------- routes

    def _add_route(self, name: Optional[str] = None) -> None:
        name = name or t("codex.route.default_name", n=len(self._routes) + 1)
        self._routes.append({"name": name, "notes": "", "stops": []})
        self._save(refill=True)
        self.combo_routes.setCurrentIndex(len(self._routes) - 1)

    def _duplicate_route(self) -> None:
        route = self._current_route()
        if route is None:
            return
        clone = copy.deepcopy(route)
        clone["name"] = t("codex.route.copy_name", name=route.get("name") or "?")
        self._routes.append(clone)
        self._save(refill=True)
        self.combo_routes.setCurrentIndex(len(self._routes) - 1)

    def _rename_route(self, new_name: str) -> None:
        route = self._current_route()
        if route is None or not (new_name or "").strip():
            return
        route["name"] = new_name.strip()
        self._save(refill=True)

    def _rename_route_dialog(self) -> None:
        route = self._current_route()
        if route is None:
            return
        name, ok = QInputDialog.getText(self, t("codex.route.rename"),
                                        t("codex.route.name"),
                                        text=route.get("name") or "")
        if ok:
            self._rename_route(name)

    def _remove_route(self) -> None:
        idx = self.combo_routes.currentIndex()
        if 0 <= idx < len(self._routes):
            self._routes.pop(idx)
            self._save(refill=True)

    def add_from_opportunity(self, opp: Opportunity) -> None:
        """Deux etapes pretes : le vendeur puis l'acheteur (bouton de
        l'onglet Opportunites)."""
        if self.data is None:
            return
        label = self.data.display_name(opp.item)
        self._add_route(t("codex.route.from_opp", item=label))
        route = self._current_route()
        if route is None:
            return
        qty = int(opp.qty or 1)
        route["stops"].extend([
            {"kind": "poi", "playfield": "", "poi": "", "item": opp.item,
             "qty": qty, "seen": False, "seen_at": "",
             "note": t("codex.route.buy_at", trader=self.data.display_name(opp.seller))},
            {"kind": "poi", "playfield": "", "poi": "", "item": opp.item,
             "qty": qty, "seen": False, "seen_at": "",
             "note": t("codex.route.sell_at", trader=self.data.display_name(opp.buyer))},
        ])
        self._save(refill=True)

    # ------------------------------------------------------------- etapes

    def _add_stop(self) -> None:
        route = self._current_route()
        if route is None:
            return
        item = self.combo_item.currentData()
        route["stops"].append({
            "kind": self.combo_kind.currentData() or "",
            "playfield": self._playfield_type(),
            "poi": self.combo_poi.currentText().strip(),
            "item": item if isinstance(item, str) else "",
            "qty": int(self.spin_qty.value()),
            "note": "", "seen": False, "seen_at": ""})
        self._save()
        self._fill_route()

    def _remove_stop(self) -> None:
        route = self._current_route()
        row = self.table.currentRow()
        if route is None or row < 0 or row >= len(route["stops"]):
            return
        route["stops"].pop(row)
        self._save()
        self._fill_route()

    def _move_stop(self, delta: int) -> None:
        route = self._current_route()
        row = self.table.currentRow()
        if route is None:
            return
        target = row + delta
        stops = route["stops"]
        if row < 0 or not 0 <= target < len(stops):
            return
        stops[row], stops[target] = stops[target], stops[row]
        self._save()
        self._fill_route()
        self.table.selectRow(target)

    def _mark_seen(self) -> None:
        route = self._current_route()
        row = self.table.currentRow()
        if route is None or row < 0 or row >= len(route["stops"]):
            return
        stop = route["stops"][row]
        stop["seen"] = not stop.get("seen")
        stop["seen_at"] = datetime.datetime.now().isoformat(timespec="minutes") \
            if stop["seen"] else ""
        self._save()
        self._fill_route()

    def _stop_edited(self, item: QTableWidgetItem) -> None:
        route = self._current_route()
        if route is None or item.row() >= len(route["stops"]):
            return
        stop = route["stops"][item.row()]
        if item.column() == 6:
            try:
                stop["qty"] = int(float(item.text() or 0))
            except ValueError:
                return
        elif item.column() == 7:
            stop["note"] = item.text()
        elif item.column() == 8:
            stop["seen"] = item.checkState() == Qt.CheckState.Checked
            stop["seen_at"] = datetime.datetime.now().isoformat(timespec="minutes") \
                if stop["seen"] else ""
        else:
            return
        self._save()
        self._fill_route()

    def _fill_routes(self) -> None:
        self.combo_routes.blockSignals(True)
        current = self.combo_routes.currentIndex()
        self.combo_routes.clear()
        for route in self._routes:
            self.combo_routes.addItem(route.get("name") or "?", route.get("name"))
        self.combo_routes.blockSignals(False)
        if 0 <= current < len(self._routes):
            self.combo_routes.setCurrentIndex(current)
        elif self._routes:
            self.combo_routes.setCurrentIndex(0)
        self._fill_route()

    def _system_of(self, type_name: str) -> str:
        if self.index is None or not type_name:
            return ""
        instances = self.index.by_type.get(type_name)
        if not instances:
            return ""
        system = instances[0].system
        return system if len(instances) == 1 else f"{system} (+{len(instances) - 1})"

    def _sector_of(self, type_name: str) -> str:
        if self.index is None or not type_name:
            return ""
        instances = self.index.by_type.get(type_name)
        if not instances:
            return ""
        sector = instances[0].sector
        return f"[{sector[0]}, {sector[1]}, {sector[2]}]"

    def _fill_route(self) -> None:
        route = self._current_route()
        stops = route["stops"] if route else []
        self.table.blockSignals(True)
        self.table.setRowCount(len(stops))
        for row, stop in enumerate(stops):
            kind = _KIND_LABEL.get(stop.get("kind") or "")
            self.table.setItem(row, 0, _cell(t(kind) if kind else ""))
            type_name = stop.get("playfield") or ""
            label = type_name
            if self.index is not None and type_name in self.index.by_type:
                label = _place_label(self.index.by_type[type_name], type_name)
            self.table.setItem(row, 1, _editable(label))
            self.table.setItem(row, 2, _cell(self._system_of(type_name)))
            self.table.setItem(row, 3, _cell(self._sector_of(type_name)))
            self.table.setItem(row, 4, _editable(stop.get("poi") or ""))
            item_name = stop.get("item") or ""
            label_item = self.data.display_name(item_name) \
                if self.data is not None and item_name else ""
            self.table.setItem(row, 5, _editable(label_item))
            self.table.setItem(row, 6, num_cell(float(stop.get("qty") or 0)))
            self.table.setItem(row, 7, _editable(stop.get("note") or ""))
            seen = QTableWidgetItem()
            seen.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            seen.setCheckState(Qt.CheckState.Checked if stop.get("seen")
                               else Qt.CheckState.Unchecked)
            seen.setToolTip(stop.get("seen_at") or "")
            self.table.setItem(row, 8, seen)
        self.table.blockSignals(False)
        low, high = route_net(route, self._opps) if route else (0.0, 0.0)
        text = t("codex.route.net", low=fmt(low), high=fmt(high))
        if route and stops:
            text = t("codex.route.stops", n=len(stops)) + "  —  " + text
        self.lbl_net.setText(text)

    def export_payload(self) -> Optional[Tuple[List[str], List[List[str]]]]:
        """La route courante telle qu'affichee (case « vu » en x/vide)."""
        route = self._current_route()
        if route is None or not route["stops"]:
            return None
        rows = []
        for stop in route["stops"]:
            kind = _KIND_LABEL.get(stop.get("kind") or "")
            type_name = stop.get("playfield") or ""
            label = type_name
            if self.index is not None and type_name in self.index.by_type:
                label = _place_label(self.index.by_type[type_name], type_name)
            item_name = stop.get("item") or ""
            rows.append([
                t(kind) if kind else "", label, self._system_of(type_name),
                self._sector_of(type_name), stop.get("poi") or "",
                self.data.display_name(item_name) if self.data and item_name else "",
                str(stop.get("qty") or ""), stop.get("note") or "",
                "x" if stop.get("seen") else ""])
        return [t(key) for key in self.COLS], rows

    def export_current(self):
        payload = self.export_payload()
        if payload is None:
            return None
        headers, rows = payload
        return export_rows(self, headers, rows, "codex_route")


class TradersTab(QWidget):
    """Marchands, opportunites, lieux et routes."""

    def __init__(self, working_root, parent=None):
        super().__init__(parent)
        self.working_root = working_root
        lay = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.traders = TradersPane()
        self.opps = OpportunitiesPane()
        self.places = PlacesPane(working_root)
        self.routes = RoutesPane(working_root)
        self.locations_tab = QTabWidget()
        self.locations_tab.addTab(self.places, t("codex.loc.tab_places"))
        self.locations_tab.addTab(self.routes, t("codex.route.tab"))
        self.tabs.addTab(self.traders, t("codex.traders.tab"))
        self.tabs.addTab(self.opps, t("codex.opp.tab"))
        self.tabs.addTab(self.locations_tab, t("codex.loc.tab"))
        lay.addWidget(self.tabs, 1)
        self.opps.routeRequested.connect(self._route_from_opportunity)

    def set_data(self, data: CodexData) -> None:
        self.traders.set_data(data)
        self.opps.set_data(data)
        index = cached_places(self.working_root, [tr.name for tr in data.traders])
        self.places.set_data(data, index)
        self.routes.set_data(data, self.opps.all_opportunities(), index)

    def _route_from_opportunity(self, opp) -> None:
        self.routes.add_from_opportunity(opp)
        self.tabs.setCurrentWidget(self.locations_tab)
        self.locations_tab.setCurrentWidget(self.routes)

    # -------------------------------------------------------------- export

    def export_payload(self) -> Optional[Tuple[List[str], List[List[str]]]]:
        """(en-tetes, lignes) de la vue Marchands active."""
        current = self.tabs.currentWidget()
        if current is self.traders:
            return self.traders.export_payload()
        if current is self.opps:
            return self.opps.export_payload()
        if current is self.locations_tab:
            pane = self.locations_tab.currentWidget()
            if isinstance(pane, (PlacesPane, RoutesPane)):
                return pane.export_payload()
        return None
