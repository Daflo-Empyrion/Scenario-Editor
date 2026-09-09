"""Tests TraderZone cote playfield (economy 3e etape) : helpers
core/playfield_editor.py (cle top-level + Properties de POI crees/supprimees)
et integration dans PlayfieldEditWidget (combo top-level + colonne POI)."""
import shutil
from pathlib import Path

import pytest

PLAYFIELD_TEXT = (
    "Playfield: TestPlanet\n"
    "PvP: False\n"
    "POIs:\n"
    "  - GroupName: StationA\n"
    "    Faction: Zirax\n"
    "    Properties:\n"
    "      - Key: RegenAfter\n"
    "        Value: 4320\n"
    "  - GroupName: StationB\n"
    "    Faction: Zirax\n"
)


@pytest.fixture
def scenario(qapp, tmp_path):
    """Scenario minimal avec TraderNPCConfig.ecf + un playfield."""
    root = tmp_path
    cfg = root / "Content" / "Configuration"
    cfg.mkdir(parents=True)
    (cfg / "TraderNPCConfig.ecf").write_text(
        "{ Trader Name: Bertrams\n"
        "  SellingGoods: \"trwSpecial\"\n"
        "  Item1: \"CannedVegetables, 100-150, 3-5\"\n"
        "}\n"
        "{ Trader Name: Medic\n"
        "  SellingGoods: \"trwMedicine\"\n"
        "}\n", encoding="utf-8")
    pf = root / "Content" / "Playfields" / "TestPlanet"
    pf.mkdir(parents=True)
    yaml_path = pf / "playfield_static.yaml"
    yaml_path.write_text(PLAYFIELD_TEXT, encoding="utf-8")
    return root, yaml_path


# ------------------------------------------------------------- helpers core

def test_top_level_trader_zone_lifecycle(scenario):
    from core.yamllite.parser import parse_yaml_file
    from core.playfield_editor import (get_top_level_trader_zone,
                                       set_top_level_trader_zone)
    _, yaml_path = scenario
    doc = parse_yaml_file(yaml_path)
    original = doc.render()
    assert get_top_level_trader_zone(doc) is None

    assert set_top_level_trader_zone(doc, "Bertrams") is True
    out = doc.render()
    lines = out.splitlines()
    # inseree juste apres la 1re entree ('Playfield:')
    assert lines[1] == "TraderZone: Bertrams"
    assert get_top_level_trader_zone(doc) == "Bertrams"

    assert set_top_level_trader_zone(doc, "Medic") is True
    assert get_top_level_trader_zone(doc) == "Medic"
    assert set_top_level_trader_zone(doc, "") is True
    assert get_top_level_trader_zone(doc) is None
    assert doc.render() == original                    # cycle complet sans trace
    assert set_top_level_trader_zone(doc, "") is False  # rien a supprimer


def test_properties_value_create_update_remove(scenario):
    from core.yamllite.parser import parse_yaml_file
    from core.playfield_editor import (find_poi_items, get_properties_value,
                                       set_or_create_properties_value)
    _, yaml_path = scenario
    doc = parse_yaml_file(yaml_path)
    pois = find_poi_items(doc)
    by_name = {p.value: p for p in pois}

    # POI A : Properties existe (RegenAfter) -> simple ajout d'une paire
    assert get_properties_value(by_name["StationA"], "TraderZone") is None
    assert set_or_create_properties_value(by_name["StationA"], "TraderZone", "Bertrams")
    assert get_properties_value(by_name["StationA"], "TraderZone") == "Bertrams"
    assert get_properties_value(by_name["StationA"], "RegenAfter") == "4320"  # intact

    # POI B : ni Properties ni TraderZone -> creation complete de la structure
    assert set_or_create_properties_value(by_name["StationB"], "TraderZone", "Medic")
    assert get_properties_value(by_name["StationB"], "TraderZone") == "Medic"

    # round-trip : re-parse du rendu (en memoire) -> les valeurs reviennent
    from core.yamllite.parser import parse_yaml_text
    doc2 = parse_yaml_text(doc.render())
    for p in find_poi_items(doc2):
        expected = "Bertrams" if p.value == "StationA" else "Medic"
        assert get_properties_value(p, "TraderZone") == expected

    # vidage -> retrait de la paire (StationA garde son RegenAfter, StationB
    # perd tout le bloc Properties devenu vide)
    assert set_or_create_properties_value(by_name["StationA"], "TraderZone", "")
    assert get_properties_value(by_name["StationA"], "TraderZone") is None
    assert get_properties_value(by_name["StationA"], "RegenAfter") == "4320"
    assert set_or_create_properties_value(by_name["StationB"], "TraderZone", "")
    assert get_properties_value(by_name["StationB"], "TraderZone") is None
    assert "Properties" not in doc.render().split("StationB")[1]


# ----------------------------------------------------------------- widget

@pytest.fixture
def widget(scenario, qapp):
    from gui.theme import apply_theme
    from gui.playfield_edit_widget import PlayfieldEditWidget
    apply_theme(qapp)
    _root, yaml_path = scenario
    w = PlayfieldEditWidget(yaml_path, blocks_ecf_files=[])
    w.show()
    yield w
    w.close()


def test_combo_shows_trader_names(widget):
    items = [widget.trader_zone_combo.itemText(i)
             for i in range(widget.trader_zone_combo.count())]
    assert "Bertrams" in items and "Medic" in items
    assert widget.trader_zone_combo.currentText() == ""


def test_combo_sets_top_level_and_save(widget):
    widget.trader_zone_combo.setCurrentText("Bertrams")
    widget._on_trader_zone_changed()
    assert widget.raw_widget.is_modified()
    out = widget.raw_widget.doc.render()
    assert "TraderZone: Bertrams" in out
    widget.save()
    assert "TraderZone: Bertrams" in Path(widget.path).read_text(encoding="utf-8")


def test_poi_table_has_trader_zone_column(widget):
    poi_tab = widget.tab_widget.widget(2)
    table = poi_tab._playfield_tables[0]
    headers = [table.table.horizontalHeaderItem(c).text()
               for c in range(table.table.columnCount())]
    assert any("TraderZone" in h for h in headers)
    # choices de la colonne = noms des marchands du scenario
    r = [i for i, h in enumerate(headers) if "TraderZone" in h][0] - 1
    assert table.synthetic_columns[r].choices_fn() == ["Bertrams", "Medic"]


def test_poi_trader_zone_edit_roundtrip(widget):
    poi_tab = widget.tab_widget.widget(2)
    table = poi_tab._playfield_tables[0]
    # ligne 1 = StationB (sans Properties) : on saisit une zone via le setter
    item_b = table._items_by_row[1]
    assert item_b.value == "StationB"
    assert table.synthetic_columns[1].setter(item_b, "Medic") is True
    widget.save()
    saved = Path(widget.path).read_text(encoding="utf-8")
    assert "TraderZone" in saved.split("StationB")[1]
