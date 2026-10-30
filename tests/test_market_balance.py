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

"""Moteur d'equilibrage des prix marche : cout recursif (OutputCount,
BaseItem, recettes gratuites, ligne a 0, cycle), heritage REF (prix et
TemplateRoot), dernier-qui-declare gagne, statuts en cascade, formule
marge+craft, application (modification ET ajout de ligne)."""

from core.market_balance import (ANCRAGE, COUSIN, FABRIQUABLE, GROUPE,
                                 MATERIAU, NON_VENDABLE, apply_changes,
                                 build_report, load_index, make_changes,
                                 retarget)

ITEMS = """{ Item Name: RockDust
  MarketPrice: 2
}
{ Item Name: IronIngot
  MarketPrice: 4
}
{ Item Name: IronOre
  MarketPrice: 3
}
{ Item Name: Coolant
  MarketPrice: 8
}
{ Item Name: Machine
  MarketPrice: 100
}
{ Item Name: MachineT2
  MarketPrice: 900
}
{ Item Name: Ghost
  MarketPrice: 50
}
{ Item Name: NoPrice
  StackSize: 100
}
{ Item Name: LaserT1
  MarketPrice: 500
}
{ Item Name: LaserT2
  MarketPrice: 900
}
{ Item Name: LoopA
  MarketPrice: 7
}
{ +Item Name: Machine
  MarketPrice: 120
}
"""

TEMPLATES = """{ Template Name: IronIngot
  CraftTime: 10
  OutputCount: 2
  { Child Inputs
    RockDust: 10
  }
}
{ Template Name: IronOre
  BaseItem: true
  CraftTime: 10
  { Child Inputs
    RockDust: 100
  }
}
{ Template Name: Coolant
  CraftTime: 5
  { Child Inputs
    RockDust: 0
  }
}
{ Template Name: Machine
  CraftTime: 60
  { Child Inputs
    IronIngot: 5
    IronOre: 2
    Coolant: 3
  }
}
{ Template Name: MachineT2
  CraftTime: 5
  { Child Inputs
    Machine: 2
    NoPrice: 1
  }
}
{ Template Name: LoopA
  CraftTime: 5
  { Child Inputs
    LoopB: 1
  }
}
{ Template Name: LoopB
  CraftTime: 5
  { Child Inputs
    LoopA: 1
  }
}
{ Template Name: LaserT1
  CraftTime: 10
  { Child Inputs
    IronIngot: 4
  }
}
{ Template Name: RampBlocks
  CraftTime: 5
  { Child Inputs
    RockDust: 1
  }
}
"""

BLOCKS = """{ Block Id: 500, Name: HullParent
  MarketPrice: 40
  Mass: 10
  Material: SteelLarge
}
{ Block Id: 501, Name: HullChild
  Ref: HullParent
}
{ Block Id: 502, Name: RampBlock
  TemplateRoot: RampBlocks
  MarketPrice: 20
  Mass: 4
  Material: SteelLarge
}
{ Block Id: 503, Name: OrphanSlab
  MarketPrice: 30
  Mass: 5
  Material: SteelLarge
}
"""

VANILLA_ITEMS = """{ Item Name: LaserT1
  MarketPrice: 100
}
{ Item Name: LaserT2
  MarketPrice: 400
}
"""


def _scenario(tmp_path):
    cdir = tmp_path / "Content" / "Configuration"
    cdir.mkdir(parents=True)
    (cdir / "ItemsConfig.ecf").write_text(ITEMS, encoding="utf-8")
    (cdir / "Templates.ecf").write_text(TEMPLATES, encoding="utf-8")
    (cdir / "BlocksConfig.ecf").write_text(BLOCKS, encoding="utf-8")
    van = tmp_path / "van"
    (van / "Configuration").mkdir(parents=True)
    (van / "Configuration" / "ItemsConfig.ecf").write_text(
        VANILLA_ITEMS, encoding="utf-8")
    return tmp_path, van


def _report(tmp_path):
    root, van = _scenario(tmp_path)
    idx, vidx = load_index(root, str(van))
    return idx, vidx, build_report(idx, vidx)


def _entry(rep, name):
    return next(e for e in rep.entries if e.name == name)


def test_recursive_cost_with_output_count(tmp_path):
    _, _, rep = _report(tmp_path)
    e = _entry(rep, "IronIngot")
    assert e.status == FABRIQUABLE
    assert e.cost == 10.0        # 10 x RockDust(2) / OutputCount 2
    assert e.target == 10        # marge 1.0, fabrication 0 % -> prix = cout


def test_base_item_is_leaf_priced_by_market(tmp_path):
    _, _, rep = _report(tmp_path)
    e = _entry(rep, "IronOre")
    assert e.cost == 3.0         # BaseItem : prix marche, pas 100x RockDust


def test_free_recipe_falls_back_to_market_price(tmp_path):
    # Coolant : recette gratuite volontaire mais vendu -> valorise 8 ;
    # Machine = 5x IronIngot(10) + 2x IronOre(3) + 3x Coolant(8)
    _, _, rep = _report(tmp_path)
    e = _entry(rep, "Machine")
    assert e.cost == 80.0


def test_patch_last_declared_price_wins(tmp_path):
    _, _, rep = _report(tmp_path)
    assert _entry(rep, "Machine").price == 120   # +Item patch 100 -> 120


def test_missing_ingredient_without_price_blocks_recipe(tmp_path):
    # MachineT2 <- NoPrice (ni prix ni recette) : PAS de cout partiel
    _, _, rep = _report(tmp_path)
    e = _entry(rep, "MachineT2")
    assert e.cost is None


def test_cycle_resolves_to_market_price(tmp_path):
    # LoopA/LoopB se referencent ; le cycle est coupe par le PRIX MARCHE
    # du maillon qui en a un : cout de LoopA = 7 (feuille), prix conserve
    _, _, rep = _report(tmp_path)
    e = _entry(rep, "LoopA")
    assert e.cost == 7.0
    assert e.price == 7
    assert e.target == 7


def test_ref_inherits_price(tmp_path):
    _, _, rep = _report(tmp_path)
    assert _entry(rep, "HullChild").price == 40


def test_templaroot_group_status(tmp_path):
    # RampBlock n'a pas de template a son nom : TemplateRoot RampBlocks
    # (recette 1 RockDust = 2) -> statut groupe, cout du groupe
    _, _, rep = _report(tmp_path)
    e = _entry(rep, "RampBlock")
    assert e.status == GROUPE
    assert e.template == "RampBlocks"
    assert e.cost == 2.0


def test_cousin_tier_ratio(tmp_path):
    # LaserT2 sans template : cousin de LaserT1 (500) ; ratio vanille 400/100
    _, _, rep = _report(tmp_path)
    e = _entry(rep, "LaserT2")
    assert e.status == COUSIN
    assert e.target == 2000       # 500 x (400/100)


def test_material_fallback_for_blocks(tmp_path):
    # OrphanSlab : sans recette, Material SteelLarge, masse 5 ; RampBlock
    # (groupe, prix 20, masse 4) donne 5/unite de masse -> cible 25
    _, _, rep = _report(tmp_path)
    e = _entry(rep, "OrphanSlab")
    assert e.status == MATERIAU
    assert e.target == 25


def test_no_price_is_never_writable(tmp_path):
    _, _, rep = _report(tmp_path)
    e = _entry(rep, "NoPrice")
    assert e.status == NON_VENDABLE
    assert e.target is None


def test_fabrication_percent_applied_on_material_cost(tmp_path):
    idx, _ = load_index(_scenario(tmp_path)[0], "")
    rep = build_report(idx, margin=1.0, fab_pct=0.0)
    e = _entry(rep, "Machine")
    assert e.target == 80          # 0 % : prix = cout des matieres
    rep2 = build_report(idx, margin=1.0, fab_pct=50.0)
    # +50 % du cout des matieres : 80 x 1.5 = 120
    assert _entry(rep2, "Machine").target == 120


def test_retarget_recomputes_without_reparse(tmp_path):
    idx, _ = load_index(_scenario(tmp_path)[0], "")
    rep = build_report(idx)
    retarget(rep, idx, margin=2.0, fab_pct=0.0)
    assert _entry(rep, "Machine").target == 160   # 80 x 2, fabrication neutre


def test_make_changes_skips_unchanged_and_apply_writes(tmp_path):
    root, _ = _scenario(tmp_path)
    idx, _ = load_index(root, "")
    rep = build_report(idx)
    # IronIngot : prix 4 -> cible 10 ; HullChild : sans cible (ancrage)
    # -> rien ; Machine : 120 -> 80
    changes = make_changes(idx, rep, {"IronIngot", "HullChild", "Machine"})
    by_name = {c.name: c for c in changes}
    assert set(by_name) == {"IronIngot", "Machine"}
    assert by_name["IronIngot"].new == 10
    done = apply_changes(changes)
    items_path = root / "Content" / "Configuration" / "ItemsConfig.ecf"
    assert done[items_path] == 2
    text = items_path.read_text(encoding="utf-8")
    assert "MarketPrice: 10" in text
    assert "MarketPrice: 80" in text


def test_apply_adds_line_when_inherited_price(tmp_path):
    # HullChild n'a PAS de ligne MarketPrice propre : l'ecriture doit
    # AJOUTER la ligne sur l'enfant, pas toucher le parent
    root, _ = _scenario(tmp_path)
    idx, _ = load_index(root, "")
    # donne au child une cible via un template de groupe réel
    (root / "Content" / "Configuration" / "Templates.ecf").write_text(
        TEMPLATES + "{ Template Name: HullParent\n  CraftTime: 5\n"
        "  { Child Inputs\n    RockDust: 5\n  }\n}\n"
        "{ Template Name: HullChildBlocks\n  CraftTime: 5\n"
        "  { Child Inputs\n    RockDust: 1\n  }\n}\n", encoding="utf-8")
    idx, _ = load_index(root, "")
    rep = build_report(idx)
    e = _entry(rep, "HullChild")   # template herite de HullParent par REF
    assert e.status == GROUPE
    assert e.cost == 10.0          # 5 x RockDust(2)
    changes = make_changes(idx, rep, {"HullChild"})
    assert changes and changes[0].new == 10
    apply_changes(changes)
    blocks_path = root / "Content" / "Configuration" / "BlocksConfig.ecf"
    text = blocks_path.read_text(encoding="utf-8")
    assert "MarketPrice: 10" in text
    # le parent garde SON prix
    assert "MarketPrice: 40" in text


def test_roundtrip_parser_keeps_other_properties(tmp_path):
    root, _ = _scenario(tmp_path)
    idx, _ = load_index(root, "")
    rep = build_report(idx)
    changes = make_changes(idx, rep, {"LaserT1"})
    if changes:
        apply_changes(changes)
        text = (root / "Content" / "Configuration" / "ItemsConfig.ecf").read_text(
            encoding="utf-8")
        assert "{ Item Name: RockDust" in text
        assert "StackSize: 100" in text


# -- coherence globale (30/10) : famille, suspects, recettes generees -------

FAM_ITEMS = """{ Item Name: RockDust
  MarketPrice: 2
}
{ Item Name: IronIngot
  MarketPrice: 10
}
{ Item Name: PistolA
  MarketPrice: 100
}
{ Item Name: PistolB
  MarketPrice: 200
}
{ Item Name: PistolC
  MarketPrice: 150
}
{ Item Name: OldPistol
  MarketPrice: 1
}
{ Item Name: GoldCoin
  MarketPrice: 50
}
{ Item Name: GoldBar
  MarketPrice: 50
}
{ Item Name: IronOre
  MarketPrice: 3
}
"""

FAM_TEMPLATES = """{ Template Name: IronIngot
  CraftTime: 10
  OutputCount: 2
  { Child Inputs
    RockDust: 10
  }
}
{ Template Name: PistolA
  CraftTime: 10
  { Child Inputs
    IronIngot: 10
  }
}
{ Template Name: PistolB
  CraftTime: 10
  { Child Inputs
    IronIngot: 20
  }
}
{ Template Name: PistolC
  CraftTime: 10
  { Child Inputs
    IronIngot: 15
  }
}
{ Template Name: GoldCoin
  CraftTime: 5
  { Child Inputs
    GoldBar: 1
  }
}
{ Template Name: IronOre
  BaseItem: true
  { Child Inputs
    RockDust: 10
  }
}
"""


def _fam_scenario(tmp_path):
    cdir = tmp_path / "Content" / "Configuration"
    cdir.mkdir(parents=True)
    (cdir / "ItemsConfig.ecf").write_text(FAM_ITEMS, encoding="utf-8")
    (cdir / "Templates.ecf").write_text(FAM_TEMPLATES, encoding="utf-8")
    (cdir / "BlocksConfig.ecf").write_text(
        "{ Block Id: 500, Name: Pillar\n  MarketPrice: 40\n}\n",
        encoding="utf-8")
    return tmp_path


def test_famille_median_gives_target_to_anchor(tmp_path):
    """OldPistol (prix 1, sans recette) herite la MEDIANE de la famille
    pistol (PistolA 100 / B 200 / C 150 -> 150)."""
    from core.market_balance import FAMILLE, load_index, build_report
    root = _fam_scenario(tmp_path)
    idx, _van = load_index(root)
    rep = build_report(idx)
    e = next(x for x in rep.entries if x.name == "OldPistol")
    assert e.status == FAMILLE
    assert e.target == 150
    assert "pistol" in (e.detail or "")


def test_single_input_suspects_flags_1to1_and_skips_baseitem(tmp_path):
    from core.market_balance import load_index, build_report, \
        single_input_suspects
    root = _fam_scenario(tmp_path)
    idx, _van = load_index(root)
    rep = build_report(idx)
    sus = single_input_suspects(idx, rep)
    names = [s["template"] for s in sus]
    assert "GoldCoin" in names          # 1:1, aucune valeur ajoutee
    assert "IronOre" not in names       # BaseItem ancre : recette figurative


def test_plan_and_apply_generated_recipe(tmp_path, monkeypatch):
    """La recette generee reprend le modele de famille le plus proche,
    dose au prorata des cibles ; apres application l'item passe
    fabriquable et n'est plus propose."""
    from core.market_balance import (apply_recipes, build_report,
                                     load_index, plan_recipes)
    root = _fam_scenario(tmp_path)
    monkeypatch.setattr("core.market_balance.central_backup",
                        lambda path, kind: tmp_path / "bak" / path.name)
    idx, _van = load_index(root)
    rep = build_report(idx)
    plans, _skipped = plan_recipes(idx, rep)
    plan = next(p for p in plans if p.name == "OldPistol")
    assert plan.target == 150 and plan.inputs == [("IronIngot", 15)]
    _path, n = apply_recipes(plans, root)
    assert n == len(plans)
    tpath = root / "Content" / "Configuration" / "Templates.ecf"
    text = tpath.read_text(encoding="utf-8")
    assert "+Template Name: OldPistol" in text
    idx2, _v = load_index(root)
    rep2 = build_report(idx2)
    e = next(x for x in rep2.entries if x.name == "OldPistol")
    assert e.status == FABRIQUABLE and e.target == 150
    plans2, _s = plan_recipes(idx2, rep2)
    assert all(p.name != "OldPistol" for p in plans2)
