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

"""Codex : couche de donnees — fusion scenario/vanille, prix par chaine Ref,
recettes aplaties (minerais non developpes, cycle), prix marchands, opportunites
de trade, matrice de degats (percentiles) et stockage lieux/routes."""

import pytest

from core.codex import (build_codex_data, load_store, route_net, save_store,
                        store_path, tier_of)

ITEMS = """{ Item Id: 1, Name: SteelPlate
  MarketPrice: 100
  Mass: 1.2
  Volume: 2
  StackSize: 100
}
{ Item Id: 2, Name: SteelPlateT2
  Ref: SteelPlate
  StackSize: 5
  ShowUser: No
}
{ Item Id: 3, Name: IronOre
  MarketPrice: 5
}
{ Item Id: 4, Name: Graphite
  MarketPrice: 7
}
{ Item Id: 5, Name: Ghost
  StackSize: 10
}
{ Item Id: 50, Name: WeaponHull
  { Child 0
    DamageMultiplier_1: 3, param1: hullcombat
    DamageMultiplier_2: 0, param1: metal
  }
}
{ Item Id: 51, Name: WeaponStone
  { Child 0
    DamageMultiplier_1: 0.5, param1: hullcombat
  }
}
{ Item Id: 52, Name: WeaponNone
  { Child 0
    DamageMultiplier_1: 0, param1: hullcombat
  }
}
{ Item Id: 53, Name: WeaponNoEntry
  StackSize: 1
}
{ Item Id: 54, Name: PistolWeapon
  DamageMultiplier_Group: CollectionAll
}
{ Item Id: 60, Name: DebugItem
  MarketPrice: 1
}
"""

BLOCKS = """{ Block Id: 100, Name: HullBlock
  Material: hullblockmat
  HitPoints: 500
}
{ Block Id: 101, Name: MetalBlock
  Material: metalmat
}
{ Block Id: 200, Name: TurretHull
  WeaponItem: WeaponHull
}
{ Block Id: 201, Name: TurretStone
  WeaponItem: WeaponStone
}
{ Block Id: 202, Name: TurretNone
  WeaponItem: WeaponNone
}
{ Block Id: 203, Name: TurretNoEntry
  WeaponItem: WeaponNoEntry
}
{ Block Id: 204, Name: PistolBlock
  WeaponItem: PistolWeapon
}
{ Block Id: 205, Name: TurretTemplate
  WeaponItem: WeaponHull
}
"""

TEMPLATES = """{ +Template Name: SteelPlate
  CraftTime: 10
  OutputCount: 10
  Target: "BaseC,SmallC"
  { Child Inputs
    IronOre: 2
  }
}
{ +Template Name: Machine
  CraftTime: 20
  OutputCount: 2
  Target: "AdvC"
  { Child Inputs
    SteelPlate: 2
    Graphite: 1
  }
}
{ +Template Name: MachineNoPrice
  CraftTime: 5
  { Child Inputs
    SteelPlate: 1
    Ghost: 1
  }
}
{ +Template Name: LoopA
  { Child Inputs
    LoopB: 1
  }
}
{ +Template Name: LoopB
  { Child Inputs
    LoopA: 1
  }
}
"""

MATERIALS = """{ Material Name: hullblockmat
  damage_category: hullcombat
}
{ Material Name: metalmat
  damage_category: metal
}
"""

DAMAGE = """{ DamageMultiplierGroup Name: Pistol
  DamageMultiplier_1: 4, param1: hullcombat
}
{ DamageMultiplierGroup Name: CollectionAll
  Collection: Pistol
  DamageMultiplier_1: 1.5, param1: metal
}
{ DamageMultiplierGroup Name: Empty
  DamageMultiplier_1: 9
}
"""

TRADERS = """{ Trader Name: Seller
  SellingText: "Hello there"
  Discount: 5
  Item1: "SteelPlate, mf=0.5-0.8, 10-20, 0, 0"
  Item2: "Ghost, 100-150, 5, 0, 0"
  Item10: "Token:1, 0, 0, mf=1.0-2.0, 3"
  Item11: "Token:9, 0, 0, mf=1.0-2.0, 3"
}
{ Trader Name: Buyer
  Item1: "SteelPlate, 0, 0, mf=1.0-1.5, 5-10"
}
{ Trader Name: Broken
  Item1: "pas un item"
}
"""

TOKENS = """{ Token Id: 1, Name: CredTokenUCH
  MarketPrice: 500
}
"""

LOCALIZATION = """KEY,English,Français
SteelPlate,Steel Plate,Plaque d'acier
WeaponHull,"[c][ff8800]Fusil [T2][-][/c]",Fusil
"""

VANILLA_ITEMS = """{ Item Id: 1, Name: SteelPlate
  MarketPrice: 1
}
{ Item Id: 7, Name: VanillaOnly
  MarketPrice: 42
}
"""

VANILLA_BLOCKS = """{ Block Id: 900, Name: VanillaBlock
  Material: hullblockmat
}
"""


def _write(root, files):
    cfg = root / "Content" / "Configuration"
    cfg.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (cfg / name).write_text(text, encoding="utf-8")
    return root


@pytest.fixture
def codex(tmp_path):
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
    vanilla = _write(tmp_path / "vanilla", {
        "ItemsConfig.ecf": VANILLA_ITEMS,
        "BlocksConfig.ecf": VANILLA_BLOCKS,
    })
    return build_codex_data(scenario, str(vanilla), language="fr")


# ------------------------------------------------------------------- build

def test_build_merges_scenario_over_vanilla(codex):
    assert codex.market_price("SteelPlate") == 100        # scenario gagne
    assert "VanillaOnly" in codex.items                   # vanille complete
    assert "VanillaBlock" in codex.blocks
    assert codex.items["VanillaOnly"].price == 42
    assert codex.templates["Machine"].output_count == 2
    assert codex.templates["SteelPlate"].targets == ("BaseC", "SmallC")
    assert codex.traders and codex.traders[0].name == "Seller"


def test_build_without_configuration_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        build_codex_data(tmp_path)


def test_display_names_follow_localization(codex):
    assert codex.display_name("SteelPlate") == "Plaque d'acier"
    assert codex.display_name("Inconnu") == "Inconnu"


def test_bbcode_stripped_in_plain_names_kept_in_html(codex):
    # fr = "Fusil" (sans balise) : on force la colonne anglaise, balisee.
    codex.language = "en"
    assert codex.display_name("WeaponHull") == "Fusil [T2]"
    assert "<span" in codex.display_html("WeaponHull") or "ff8800" in codex.display_html("WeaponHull")


def test_entry_flags(codex):
    assert codex.items["SteelPlate"].mass == 1.2
    assert codex.blocks["HullBlock"].hp == 500
    assert codex.items["SteelPlateT2"].show_user is False
    assert codex.items["DebugItem"].hidden is True
    assert "DebugItem" not in [e.name for e in codex.entries()]
    assert "DebugItem" in [e.name for e in codex.entries(include_hidden=True)]


# -------------------------------------------------------------------- prix

def test_price_inherits_from_ref_chain(codex):
    assert codex.market_price("SteelPlateT2") == 100
    assert codex.market_price("Ghost") is None
    assert codex.market_price("Inexistant") is None


def test_estimate_range_factor_and_absolute(codex):
    seller = codex.traders[0]
    steel = next(i for i in seller.items if i.name == "SteelPlate")
    assert codex.estimate_range(steel.sell_price, 100) == (50, 80)   # mf x prix
    ghost = next(i for i in seller.items if i.name == "Ghost")
    assert codex.estimate_range(ghost.sell_price, None) == (100, 150)  # absolu
    assert codex.estimate_range(steel.sell_price, None) is None        # mf sans prix
    from core.economy.model import RangeSpec
    assert codex.estimate_range(RangeSpec.parse("0-0"), 100) is None


def test_token_refs_resolve_or_hide(codex):
    assert codex.resolve_devname("Token:1") == "CredTokenUCH"
    assert codex.resolve_devname("Token:9") is None
    assert codex.resolve_devname("SteelPlate") == "SteelPlate"


# ---------------------------------------------------------------- recettes

def test_flatten_expands_sub_recipes_and_divides_by_output_count(codex):
    totals, craft = codex.flatten_ingredients("Machine")
    # Machine (2 par craft) -> 1 SteelPlate + 0,5 Graphite par piece,
    # SteelPlate (10 par craft) -> 0,2 IronOre.
    assert totals == {"IronOre": 0.2, "Graphite": 0.5}
    assert craft == 11.0                     # 20 / 2 (Machine) + 10 x 1 / 10


def test_flatten_stops_on_cycle(codex):
    totals, _craft = codex.flatten_ingredients("LoopA")
    assert totals == {"LoopA": 1.0}


def test_flatten_without_recipe(codex):
    assert codex.flatten_ingredients("Ghost") == ({}, 0.0)


def test_materials_cost_and_partial(codex):
    assert codex.materials_cost("Machine") == (4.5, False)    # 0,2 x 5 + 0,5 x 7
    cost, partial = codex.materials_cost("MachineNoPrice")
    assert cost == 1.0 and partial is True                    # Ghost non cote
    assert codex.materials_cost("Ghost") == (None, False)


# --------------------------------------------------------------- marchands

def test_trader_directions_and_broken_lines(codex):
    seller = next(t for t in codex.traders if t.name == "Seller")
    assert [i.name for i in seller.selling()] == ["SteelPlate", "Ghost"]
    assert [i.name for i in seller.buying()] == ["Token:1", "Token:9"]
    assert seller.selling_text == "Hello there" and seller.discount == "5"
    broken = next(t for t in codex.traders if t.name == "Broken")
    assert broken.items == [] and broken.raw_lines == ["pas un item"]


def test_opportunities(codex):
    opps = codex.opportunities()
    assert [o.item for o in opps] == ["SteelPlate"]            # Ghost: pas de rachat
    opp = opps[0]
    assert (opp.seller, opp.buyer) == ("Seller", "Buyer")
    assert opp.qty == 10.0                                     # min(20, 10)
    assert (opp.cost_lo, opp.cost_hi) == (50, 80)
    assert (opp.gain_lo, opp.gain_hi) == (100, 150)
    assert opp.profit == 1000.0                                # 10 x (150 - 50)
    low, high = route_net({"stops": [{"item": "SteelPlate", "qty": 4}]}, opps)
    assert (low, high) == (80.0, 400.0)                        # 4 x (100-80) / (150-50)


def test_traders_for_lists_both_directions(codex):
    assert [t.name for t, _i in codex.traders_for("SteelPlate")] == ["Seller", "Buyer"]
    assert codex.traders_for("Ghost") != []


# ------------------------------------------------------------------ degats

def test_damage_group_collection_is_merged(codex):
    group = codex.damage_group_for("PistolWeapon")
    assert group is not None and group.name == "CollectionAll"
    assert group.mult(("hullcombat",)) == 4.0        # venu du sous-groupe Pistol
    assert group.mult(("metal",)) == 1.5
    assert group.mult(("stone",)) is None            # pas d'entree = defaut


def test_damage_matrix_columns_tiers_and_exclusions(codex):
    matrix = codex.damage_matrix()
    assert matrix.columns == ("hullcombat", "metal")
    names = [row.block for row in matrix.rows]
    assert "TurretNothing" not in names
    assert "TurretNoEntry" not in names              # aucune entree de degats
    assert "TurretTemplate" not in names             # nom filtre (atelier)
    assert "TurretNone" not in names                 # immunite seule
    assert set(names) == {"TurretHull", "TurretStone", "PistolBlock"}

    hull = matrix.columns.index("hullcombat")
    tiers = {row.block: row.tiers[hull] for row in matrix.rows}
    assert tiers["TurretStone"] == "ineffective"     # 0,5
    assert tiers["TurretHull"] == "normal"           # 3, seuils 1,75/3,5/3,8
    assert tiers["PistolBlock"] == "very_effective"  # 4


def test_weapons_against_orders_and_keeps_immunity(codex):
    rows = codex.weapons_against("hullcombat")
    assert rows[0] == ("PistolBlock", 4.0, "very_effective")
    assert ("TurretNone", 0.0, "none") in rows
    assert rows == sorted(rows, key=lambda entry: -entry[1])


def test_tier_boundaries():
    thresholds = {"ineffective": 1.0, "normal": 2.0, "effective": 3.0}
    assert tier_of(None, thresholds) == "default"
    assert tier_of(0, thresholds) == "none"
    assert tier_of(0.5, thresholds) == "ineffective"   # exclusif
    assert tier_of(1.0, thresholds) == "normal"        # inclusif
    assert tier_of(2.0, thresholds) == "normal"
    assert tier_of(3.0, thresholds) == "effective"
    assert tier_of(3.1, thresholds) == "very_effective"
    assert tier_of(5, None) == "none"


# ------------------------------------------------------------- persistance

def test_store_roundtrip(tmp_path):
    root = tmp_path / "scenario"
    assert load_store(root, "locations") == {}         # absent = vide
    save_store(root, "locations", {"traderA": {"poi": "POI-1", "restock": 30}})
    assert load_store(root, "locations")["traderA"]["poi"] == "POI-1"
    assert store_path(root, "locations").parent.name      # un dossier par scenario
    assert store_path(root, "locations") != store_path(tmp_path / "autre", "locations")
