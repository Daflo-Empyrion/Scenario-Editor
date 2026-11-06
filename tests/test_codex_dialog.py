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

"""Fenetre Codex : onglets, filtres, colonne de cases (comparateur), fiche,
matrice de degats, lieux, carnet de routes et export CSV."""

import types

import pytest
from PyQt6.QtCore import Qt

from test_codex import (BLOCKS, DAMAGE, ITEMS, LOCALIZATION, MATERIALS,
                        TEMPLATES, TOKENS, TRADERS, VANILLA_BLOCKS,
                        VANILLA_ITEMS, _write)


@pytest.fixture
def root(tmp_path):
    scenario = _write(tmp_path / "scenario", {
        "ItemsConfig.ecf": ITEMS,
        "BlocksConfig.ecf": BLOCKS,
        "Templates.ecf": TEMPLATES,
        "MaterialConfig.ecf": MATERIALS,
        "DamageMultiplierConfig.ecf": DAMAGE,
        "TraderNPCConfig.ecf": TRADERS,
        "TokenConfig.ecf": TOKENS,
    })
    extras = scenario / "Extras"
    extras.mkdir(parents=True, exist_ok=True)
    (extras / "Localization.csv").write_text(LOCALIZATION, encoding="utf-8")
    _write(tmp_path / "vanilla", {"ItemsConfig.ecf": VANILLA_ITEMS,
                                  "BlocksConfig.ecf": VANILLA_BLOCKS})
    return scenario


@pytest.fixture
def dialog(qapp, root):
    from PyQt6 import sip
    from gui.codex_dialog import CodexDialog
    dlg = CodexDialog(None, str(root), str(root.parent / "vanilla"))
    yield dlg
    sip.delete(dlg)


def _row_of(dialog, label: str) -> int:
    """Ligne dont la colonne « Nom » (1) affiche `label`."""
    table = dialog.items.table
    for row in range(table.rowCount()):
        item = table.item(row, 1)
        if item is not None and item.text() == label:
            return row
    raise AssertionError(f"{label} absent de la grille")


def _has(dialog, label: str) -> bool:
    try:
        _row_of(dialog, label)
        return True
    except AssertionError:
        return False


def _check(dialog, label: str, checked: bool = True) -> None:
    item = dialog.items.table.item(_row_of(dialog, label), 0)
    item.setCheckState(Qt.CheckState.Checked if checked
                       else Qt.CheckState.Unchecked)


def _check_devname(dialog, devname: str) -> None:
    table = dialog.items.table
    for row in range(table.rowCount()):
        entry = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if entry is not None and entry.name == devname:
            table.item(row, 0).setCheckState(Qt.CheckState.Checked)
            return
    raise AssertionError(devname)


def _pinned(dialog) -> list:
    return [entry.name for entry in dialog.items.pinned()]


# ------------------------------------------------------------- structure

def test_dialog_loads_four_tabs(dialog):
    assert dialog.data is not None
    assert dialog.tabs.count() == 4
    assert dialog.items.table.rowCount() > 5           # scenario + vanille
    assert "objets" in dialog.lbl_path.text()


def test_search_filters_on_localized_name(dialog):
    dialog.items.edit_search.setText("Plaque")
    names = [dialog.items.table.item(row, 1).text()
             for row in range(dialog.items.table.rowCount())]
    assert names == ["Plaque d'acier"]
    # la fiche suit le filtre meme quand la ligne 0 reste la meme selection
    assert "Plaque d'acier" in dialog.items.detail.toHtml()


def test_kind_and_price_filters(dialog):
    dialog.items.combo_kind.setCurrentIndex(3)           # jetons
    assert dialog.items.table.rowCount() == 1
    dialog.items.combo_kind.setCurrentIndex(0)
    dialog.items.chk_price.setChecked(True)
    names = {dialog.items.table.item(row, 0).data(Qt.ItemDataRole.UserRole).name
             for row in range(dialog.items.table.rowCount())}
    assert "Ghost" not in names                        # sans MarketPrice
    assert "SteelPlate" in names


def test_detail_shows_recipe_and_flattened_recipe(dialog):
    from core.i18n import t
    entry = dialog.data.entry("SteelPlate")
    html = dialog.items.detail_html(entry, flatten=False)
    assert t("codex.detail.recipe") in html
    flat = dialog.items.detail_html(entry, flatten=True)
    assert t("codex.detail.flat") in flat
    assert dialog.data.flatten_ingredients("SteelPlate")[0] == {"IronOre": 0.2}


# ---------------------------------------------------- cases / comparateur

def test_checking_a_row_fills_the_comparison(dialog):
    _check(dialog, "Plaque d'acier")
    assert _pinned(dialog) == ["SteelPlate"]
    assert dialog.compare.table.columnCount() == 2      # propriete + 1 colonne
    assert dialog.compare.table.rowCount() > 3
    assert dialog.tabs.tabText(1).endswith("(1)")


def test_unchecking_removes_from_the_comparison(dialog):
    _check(dialog, "Plaque d'acier")
    _check(dialog, "Plaque d'acier", checked=False)
    assert _pinned(dialog) == []
    assert dialog.tabs.tabText(1) == "Comparer"


def test_fifth_check_is_refused(dialog):
    _check(dialog, "Plaque d'acier")
    for devname in ("SteelPlateT2", "IronOre", "Graphite", "Ghost"):
        _check_devname(dialog, devname)
    assert len(_pinned(dialog)) == 4
    assert "plein" in dialog.lbl_path.text()


def test_differences_only_keeps_unilateral_properties(dialog):
    _check(dialog, "Plaque d'acier")
    _check_devname(dialog, "SteelPlateT2")
    dialog.compare.chk_diff.setChecked(True)
    labels = [dialog.compare.table.item(row, 0).text()
              for row in range(dialog.compare.table.rowCount())]
    # « Empilable » : 100 d'un cote, 5 de l'autre ; « Masse » et « Volume »
    # n'existent que sur SteelPlate -> ce sont bien des differences.
    assert "Empilable" in labels
    assert "Masse" in labels and "Volume" in labels
    assert "Type" not in labels


def test_numeric_values_are_compared_by_value(dialog):
    from gui.codex_items import _differs
    assert not _differs(["1.50", "1.5"])
    assert _differs(["1.5", ""])            # absence = difference
    assert _differs(["a", "A"])


# ------------------------------------------------------------- degats

def test_weapons_matrix_and_lookup(dialog):
    table = dialog.weapons.matrix.table
    assert table.rowCount() == 3                        # 3 armes avec degats positifs
    symbols = {table.item(row, col).text()
               for row in range(table.rowCount())
               for col in range(1, table.columnCount())}
    assert "▲▲" in symbols and "▼" in symbols
    dialog.weapons.lookup.set_data(dialog.data)
    dialog.weapons.lookup.combo.setCurrentIndex(0)
    assert dialog.weapons.lookup.table.rowCount() > 0


# ----------------------------------------------------------- marchands

def test_traders_and_opportunities(dialog):
    assert dialog.traders.traders.list.count() == 3
    assert dialog.traders.opps.table.rowCount() == 1
    dialog.traders.opps.spin.setValue(5000)             # profit 1000 < 5000
    assert dialog.traders.opps.table.rowCount() == 0


def test_lieux_affichent_le_croisement(dialog):
    from core.codex_places import PlacesIndex, PlayfieldInstance, TraderPlace
    index = PlacesIndex(
        by_trader={"Seller": [TraderPlace(
            "Seller", "PlanetA", "POI-Zirax",
            instances=(("Alpha", (2, 0, 0), "PlanetAInst"),))]},
        candidates=(("PlanetA", "R2TradeTower"),),
        by_type={"PlanetA": [PlayfieldInstance("Alpha", (2, 0, 0),
                                               "PlanetAInst", "PlanetA")]})
    places = dialog.traders.places
    places.set_index(index)
    places.combo_trader.setCurrentIndex(places.combo_trader.findData("Seller"))
    table = places.known_table
    assert [table.item(0, col).text() for col in range(4)] == [
        "PlanetA", "POI-Zirax", "Alpha", "[2, 0, 0]"]
    table.selectRow(0)
    places._add_known()
    from core.codex import load_store
    stored = load_store(dialog.working_root, "locations")
    assert stored["Seller"][0]["poi"] == "POI-Zirax"


def test_lieux_sans_croisement_proposent_les_candidats(dialog):
    from core.codex_places import PlacesIndex
    places = dialog.traders.places
    places.set_index(PlacesIndex(candidates=(("PlanetA", "R2TradeTower"),)))
    places.combo_trader.setCurrentIndex(0)
    assert places.known_table.item(0, 1).text() == "R2TradeTower"


# -------------------------------------------------------------- routes

def test_route_book_crud_and_persistence(dialog):
    from core.codex import load_store
    routes = dialog.traders.routes
    routes._add_route("Or")
    routes.combo_item.setCurrentIndex(routes.combo_item.findData("SteelPlate"))
    routes.spin_qty.setValue(50)
    routes._add_stop()
    route = routes._current_route()
    assert route["name"] == "Or"
    assert route["stops"][0]["item"] == "SteelPlate"
    assert route["stops"][0]["qty"] == 50
    assert "50" in routes.table.item(0, 6).text()

    routes._rename_route("Route or")
    assert routes._current_route()["name"] == "Route or"
    routes._duplicate_route()
    assert len(routes._routes) == 2
    assert routes._current_route()["name"].startswith("Route or")

    routes.table.selectRow(0)
    routes._mark_seen()
    assert routes._current_route()["stops"][0]["seen"] is True
    assert routes._current_route()["stops"][0]["seen_at"]

    stored = load_store(dialog.working_root, "routes")["routes"]
    assert len(stored) == 2 and stored[-1]["stops"][0]["seen"] is True

    routes._remove_route()
    assert len(routes._routes) == 1


def test_route_migration_from_old_format(dialog):
    routes = dialog.traders.routes
    old = {"name": "Ancienne", "stops": [{"item": "SteelPlate", "qty": 5}]}
    migrated = routes._migrate(dict(old))
    assert migrated["stops"][0] == {
        "kind": "", "playfield": "", "poi": "", "item": "SteelPlate",
        "qty": 5, "note": "", "seen": False, "seen_at": ""}


def test_route_from_opportunity(dialog):
    opps = dialog.traders.opps
    opp = opps.rows()[0]
    opps.table.selectRow(0)
    opps._make_route()
    routes = dialog.traders.routes
    route = routes._current_route()
    assert len(route["stops"]) == 2
    assert route["stops"][0]["item"] == opp.item
    assert routes.table.rowCount() == 2
    assert dialog.traders.tabs.currentWidget() is dialog.traders.locations_tab


# -------------------------------------------------------------- export

def _patch_save(monkeypatch, out):
    monkeypatch.setattr(
        "gui.codex_export.QFileDialog.getSaveFileName",
        staticmethod(lambda *a, **k: (str(out), "CSV (*.csv)")))


def _csv_rows(path):
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")            # BOM Excel
    return raw.decode("utf-8-sig").strip().splitlines()


def test_export_items_table(dialog, tmp_path, monkeypatch):
    out = tmp_path / "objets.csv"
    _patch_save(monkeypatch, out)
    dialog.items.edit_search.setText("Plaque")
    dialog.tabs.setCurrentIndex(0)
    dialog._export()
    lines = _csv_rows(out)
    assert len(lines) == 2                            # en-tete + 1 objet
    assert ";" in lines[0] and "Plaque d'acier" in lines[1]
    assert str(out) in dialog.lbl_path.text()


def test_export_opportunities_table(dialog, tmp_path, monkeypatch):
    out = tmp_path / "opportunites.csv"
    _patch_save(monkeypatch, out)
    dialog.tabs.setCurrentWidget(dialog.traders)
    dialog.traders.tabs.setCurrentWidget(dialog.traders.opps)
    dialog._export()
    lines = _csv_rows(out)
    assert len(lines) == 2                            # en-tete + 1 opportunite
    assert "acier" in lines[1].lower()


def test_export_route(dialog, tmp_path, monkeypatch):
    out = tmp_path / "route.csv"
    _patch_save(monkeypatch, out)
    routes = dialog.traders.routes
    routes._add_route("Or")
    routes.combo_item.setCurrentIndex(routes.combo_item.findData("SteelPlate"))
    routes._add_stop()
    routes.export_current()
    lines = _csv_rows(out)
    assert len(lines) == 2
    assert "Playfield" in lines[0] and "Plaque d'acier" in lines[1]


# ------------------------------------------------------------- fenetre

def test_open_codex_keeps_the_dialog_alive(qapp, root):
    from PyQt6 import sip
    from gui.codex_dialog import open_codex
    fake = types.SimpleNamespace(
        workspace=types.SimpleNamespace(working_root=root))
    try:
        assert open_codex(None, fake) is True
        assert fake._codex_dialog.isVisible()
        assert fake._codex_dialog.data is not None
    finally:
        sip.delete(fake._codex_dialog)
