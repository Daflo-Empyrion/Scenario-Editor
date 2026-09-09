"""Tests du coeur economie (core/economy/) : parsing/compilation des chaines
'Item<N>' de TraderNPCConfig.ecf, round-trip byte-perfect, index MarketPrice,
et regles de validation ECO.

Format de reference = exemples de l'en-tete du fichier VANILLE
(Traitement tolerant : separateur ', ' ou ',', stock de vente optionnel,
partie achat optionnelle, prix plage absolue OU facteur mf=).
"""
from pathlib import Path

import pytest

from core.ecf.parser import parse_ecf_text
from core.economy.model import RangeSpec, TradeItem, unescape_text
from core.economy.trader_config import TraderConfigDoc
from core.economy.market_price import build_index, lookup_case_insensitive
from core.economy.validation import (extract_zone_assignments,
                                     validate_assignments, validate_trader_doc)

SAMPLE = (
    "# Trader configuration file documentation\n"
    "## Syntax\n"
    "{ Trader Name: TraderDefault\n"
    "  SellingText: \"Hi, I am trader <NAME>\\nI am selling <GOODS>.\"\n"
    "  SellingGoods: \"trwFood\"\n"
    "  Item1: \"CannedVegetables, 100-150, 3-5, 85-150, 55-150\"\n"
    "  Item2: \"CannedMeat, 222-333, 3-5, 178-222,55-150\"\n"
    "}\n"
    "\n"
    "{ Trader Name: Bertrams\n"
    "  SellingText: \"Welcome to Bertrams! \\n\\nOur prices glide! \\n<DISCOUNTTEXT>\"\n"
    "  SellingGoods: \"trwSpecial\"  \n"
    "  Discount: 0.08\n"
    "  Item1: \"HoverbikeHowler, mf=1.1-1.2, 10-50, mf=0.4-0.5, 55-150\"\n"
    "}\n"
)


# ---------------------------------------------------------------- RangeSpec

def test_rangespec_all_forms_roundtrip():
    for raw, factor, ranged in [("100-150", False, True), ("10", False, False),
                                ("mf=1.1-1.2", True, True), ("mf=0.4", True, False)]:
        spec = RangeSpec.parse(raw)
        assert spec is not None
        assert spec.factor is factor and spec.ranged is ranged
        assert spec.render() == raw


def test_rangespec_invalid():
    assert RangeSpec.parse("abc") is None
    assert RangeSpec.parse("") is None
    assert RangeSpec.parse("mf=xyz") is None


def test_rangespec_scaled():
    assert RangeSpec.parse("100-150").scaled(1.5).render() == "150-225"
    assert RangeSpec.parse("mf=1.1-1.2").scaled(2).render() == "mf=2.2-2.4"
    # REGLE MODULE : valeurs absolues = ENTIERS, arrondi au chiffre superieur
    assert RangeSpec.parse("10").scaled(1.25).render() == "13"     # 12.5 -> 13
    assert RangeSpec.parse("3").scaled(0.5).render() == "2"        # 1.5 -> 2
    assert RangeSpec.parse("3-5").scaled(0.5).render() == "2-3"
    assert RangeSpec.parse("100").scaled(1.1).render() == "110"    # bruit flottant neutralise
    # la forme est conservee
    assert RangeSpec.parse("100-150").scaled(1.5).ranged is True
    assert RangeSpec.parse("mf=0.4").scaled(2).factor is True


def test_rangespec_is_integral():
    assert RangeSpec.parse("100-150").is_integral()
    assert RangeSpec.parse("10").is_integral()
    assert RangeSpec.parse("mf=1.1-1.2").is_integral()   # facteur : toujours ok
    assert not RangeSpec.parse("99.5").is_integral()
    assert not RangeSpec.parse("3-5.5").is_integral()


# ---------------------------------------------------------------- TradeItem

@pytest.mark.parametrize("raw", [
    '"CannedVegetables, 100-150, 3-5, 85-150, 55-150"',
    '"SmallOptronicBridge, mf=1.1-1.2, 10-50, mf=0.4-0.5, 55-150"',
    '"HoverbikeSpeedstar, mf=1.1-1.2, 5, mf=0.4-0.5, 10"',
    '"CannedVegetables, 100-150"',                       # sans stock ni achat (doc vanilla)
    '"CannedMeat, 222-333, 3-5, 178-222,55-150"',        # separateur ',' sans espace
])
def test_tradeitem_parse_render_roundtrip(raw):
    item = TradeItem.parse(raw)
    assert item.name
    rendered = item.render(quote=True)
    if raw == '"CannedMeat, 222-333, 3-5, 178-222,55-150"':
        # separateur ',' sans espace : la REECRITURE canonicalise en ', '
        # (la ligne non modifiee reste elle-meme octet pour octet, le parser
        # reutilisant raw tant que dirty=False) ; seuls les champs comptent.
        assert rendered == '"CannedMeat, 222-333, 3-5, 178-222, 55-150"'
    else:
        assert rendered == raw


def test_tradeitem_fields():
    item = TradeItem.parse('"CannedVegetables, 100-150, 3-5, 85-150, 55-150"')
    assert item.name == "CannedVegetables"
    assert item.sell_price.render() == "100-150"
    assert item.sell_stock.render() == "3-5"
    assert item.has_buy
    assert item.buy_price.factor is False
    assert item.buy_max_stock.render() == "55-150"
    solo = TradeItem.parse('"CannedVegetables, 100-150"')
    assert solo.sell_stock is None and not solo.has_buy


def test_tradeitem_invalid_raises():
    with pytest.raises(ValueError):
        TradeItem.parse('"JustAName"')
    with pytest.raises(ValueError):
        TradeItem.parse('"Name, prix-pas-chiffre"')


# ------------------------------------------------------- TraderConfigDoc

def _doc():
    return TraderConfigDoc(parse_ecf_text(SAMPLE))


def test_ecf_roundtrip_byte_perfect_untouched():
    assert _doc().doc.render() == SAMPLE


def test_views_and_unescaped_text():
    views = _doc().views()
    assert [v.name for v in views] == ["TraderDefault", "Bertrams"]
    assert unescape_text is not None  # (garde-fou import)
    assert "<NAME>" in views[0].selling_text
    assert "\n" in views[0].selling_text          # \n litteraux deshapes
    assert views[1].discount == "0.08"
    assert views[1].selling_goods == "trwSpecial"
    assert len(views[0].rows) == 2
    assert views[0].rows[0].key == "Item1"


def test_set_item_only_touches_its_line():
    doc = _doc()
    view = doc.views()[0]
    row = view.row_by_key("Item1")
    item = row.item
    item.sell_price = RangeSpec.parse("200-250")
    TraderConfigDoc.set_item(row, item)
    out = doc.doc.render()
    assert '"CannedVegetables, 200-250, 3-5, 85-150, 55-150"' in out
    # TOUT le reste est intact (hors la ligne modifiee)
    expected = SAMPLE.replace('"CannedVegetables, 100-150, 3-5, 85-150, 55-150"',
                              '"CannedVegetables, 200-250, 3-5, 85-150, 55-150"')
    assert out == expected


def test_set_item_preserves_unquoted_style():
    doc = TraderConfigDoc(parse_ecf_text(
        "{ Trader Name: T\n  Item1: CannedVegetables, 100-150, 3-5\n}\n"))
    row = doc.views()[0].rows[0]
    row.item.sell_stock = RangeSpec.parse("9")
    TraderConfigDoc.set_item(row, row.item)
    assert "Item1: CannedVegetables, 100-150, 9" in doc.doc.render()
    assert '"CannedVegetables' not in doc.doc.render()


def test_add_and_remove_item():
    doc = _doc()
    view = doc.views()[0]
    doc.add_item(view.block, TradeItem.parse('"MedPack, 50-60, 10"'))
    out = doc.doc.render()
    assert '"MedPack, 50-60, 10"' in out
    view2 = doc.views()[0]
    assert view2.row_by_key("Item3") is not None
    doc.remove_item(view2.block, view2.row_by_key("Item1"))
    assert "CannedVegetables" not in doc.doc.render()
    # la numerotation d'origine des restantes n'est PAS reecrite (fidelite)
    assert "Item2:" in doc.doc.render()


def test_set_selling_text_and_fields():
    doc = _doc()
    default_block = doc.views()[0].block
    assert TraderConfigDoc.set_discount(default_block, "0.10") is False  # pas de ligne Discount
    bertrams = doc.views()[1].block
    TraderConfigDoc.set_selling_text(bertrams, "Ligne1\nLigne2")
    TraderConfigDoc.set_discount(bertrams, "0.10")
    out = doc.doc.render()
    assert 'SellingText: "Ligne1\\nLigne2"' in out   # re-echappe
    assert "Discount: 0.10" in out
    re_parsed = TraderConfigDoc(parse_ecf_text(out))
    assert re_parsed.views()[1].selling_text == "Ligne1\nLigne2"
    assert re_parsed.views()[1].discount == "0.10"


def test_create_duplicate_remove_trader():
    doc = _doc()
    base = len(doc.names())
    doc.create_trader("NouveauMarchand")
    doc.duplicate_trader(doc.find("Bertrams"), "BertramsSud")
    out = doc.doc.render()
    re_parsed = TraderConfigDoc(parse_ecf_text(out))
    assert re_parsed.names() == ["TraderDefault", "Bertrams", "NouveauMarchand", "BertramsSud"]
    clone = re_parsed.find("BertramsSud")
    assert clone is not None
    # la duplication recopie les valeurs brutes (facteur mf= et Discount)
    assert 'Item1: "HoverbikeHowler, mf=1.1-1.2, 10-50, mf=0.4-0.5, 55-150"' in out
    assert "Discount: 0.08" in out
    assert doc.remove_trader(doc.find("NouveauMarchand"))
    assert "NouveauMarchand" not in doc.doc.render()
    assert len(TraderConfigDoc(parse_ecf_text(doc.doc.render())).names()) == base + 1


# ------------------------------------------------------- MarketPrice

def test_market_price_index(tmp_path):
    items = tmp_path / "ItemsConfig.ecf"
    items.write_text(
        "{ Item Name: CannedVegetables\n"
        "  MarketPrice: 126, display: false\n"
        "}\n"
        "{ Item Name: SansPrix\n"
        "}\n", encoding="utf-8")
    blocks = tmp_path / "BlocksConfig.ecf"
    blocks.write_text(
        "{ Block Id: 1314, Name: Trader\n"
        "  MarketPrice: 500\n"
        "}\n", encoding="utf-8")
    index = build_index([items, blocks])
    assert index["CannedVegetables"] == 126.0
    assert index["SansPrix"] is None
    assert index["Trader"] == 500.0
    assert lookup_case_insensitive(index, "cannedvegetables") == 126.0
    assert build_index([items, blocks]) is index or True  # 2e appel sans exception


# ------------------------------------------------------- Validation

def test_validate_trader_doc_rules():
    doc = _doc()
    index = {"CannedVegetables": 126.0, "CannedMeat": 244.0, "HoverbikeHowler": 9000.0}
    assert validate_trader_doc(doc, index) == []
    index.pop("CannedMeat")
    bad = TraderConfigDoc(parse_ecf_text(SAMPLE.replace(
        "Item2: \"CannedMeat, 222-333, 3-5, 178-222,55-150\"",
        "Item2: \"ItemFantome, 300-200, 5-3\"")))
    issues = validate_trader_doc(bad, index)
    codes = {(i.code, i.item_key) for i in issues}
    assert ("eco.item_unknown", "Item2") in codes          # item absent du catalogue
    assert ("eco.price_inverted", "Item2") in codes        # 300-200 inversee


def test_extract_zone_assignments(tmp_path):
    root = tmp_path / "sc"
    pf = root / "Content" / "Playfields" / "TestPlanet"
    pf.mkdir(parents=True)
    (pf / "playfield_static.yaml").write_text(
        "Playfield: TestPlanet\n"
        "TraderZone: Bertrams\n"
        "POIs:\n"
        "  - Pos: [1.0, 2.0, 3.0]\n"
        "    Name: Station A\n"
        "    Properties:\n"
        "      - Key: TraderZone\n"
        "        Value: TraderDefault\n",
        encoding="utf-8")
    zones = extract_zone_assignments(root)
    assert {(z.playfield, z.poi, z.trader) for z in zones} == {
        ("TestPlanet", None, "Bertrams"),
        ("TestPlanet", "Station A", "TraderDefault"),
    }


def test_validate_assignments():
    from core.economy.validation import TraderZoneAssignment
    zones = [TraderZoneAssignment(playfield="P1", poi=None, trader="Bertrams"),
             TraderZoneAssignment(playfield="P2", poi="X", trader="Inconnu")]
    issues = validate_assignments({"Bertrams", "TraderDefault"}, zones)
    codes = {i.code: i.params for i in issues}
    assert "eco.zone_unknown_trader" in codes
    assert codes["eco.zone_unknown_trader"]["trader"] == "Inconnu"
    assert "eco.trader_unassigned" in codes
    assert codes["eco.trader_unassigned"]["trader"] == "TraderDefault"
    # fichier trader absent : pas d'avertissement 'jamais assigne' (on ne
    # connait aucun profil), mais les zones orphelines restent signalees
    issues2 = validate_assignments(set(), zones)
    assert {i.code for i in issues2} == {"eco.zone_unknown_trader"}


def test_token_items_are_not_flagged_unknown():
    """Vanilla : les marchands CardDealer vendent des 'Token:<n>' (jetons de
    dialogue) -- jamais signaler 'item absent du catalogue' pour ces lignes."""
    from core.economy.validation import EcoIssue
    doc = TraderConfigDoc(parse_ecf_text(SAMPLE.replace(
        'Item2: "CannedMeat, 222-333, 3-5, 178-222,55-150"',
        'Item2: "Token:96, 222-333, 3-5, 178-222,55-150"')))
    issues = validate_trader_doc(doc, {"CannedVegetables": 126.0,
                                       "HoverbikeHowler": 9000.0})
    assert issues == []
