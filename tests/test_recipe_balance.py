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

"""Moteur d'equilibrage des recettes (core/recipe_balance.py) : composition
vanille des blocs, isotonique par famille, template partage = puissance
max, proxy proportionnel, monnaies intactes, CraftTime sentinelle, et
ecriture reelle dans Templates.ecf."""

from pathlib import Path

from core.recipe_balance import SCENARIO, VANILLA, analyze, apply_proposals

BLOCKS = """{ Block Id: 1, Name: GenA
  Class: Generator
  Category: Devices
  TechTreeNames: "Small Vessel"
  EnergyOut: 100
  UnlockLevel: 1
  TemplateRoot: GenA
}
{ Block Id: 2, Name: GenB
  Class: Generator
  Category: Devices
  TechTreeNames: "Small Vessel"
  EnergyOut: 200
  UnlockLevel: 2
  TemplateRoot: GenB
}
{ Block Id: 3, Name: GenC
  Class: Generator
  Category: Devices
  TechTreeNames: "Small Vessel"
  EnergyOut: 300
  UnlockLevel: 3
  TemplateRoot: GenC
}
{ Block Id: 4, Name: SharedA
  Class: Generator
  Category: Devices
  EnergyOut: 100
  TemplateRoot: Shared
}
{ Block Id: 5, Name: SharedB
  Class: Generator
  Category: Devices
  EnergyOut: 900
  TemplateRoot: Shared
}
{ Block Id: 6, Name: HullA
  Category: BuildingBlocks
  Mass: 100
  SizeInBlocks: "2,2,2"
  TemplateRoot: HullA
}
{ Block Id: 7, Name: HullB
  Category: BuildingBlocks
  Mass: 200
  SizeInBlocks: "2,2,2"
  TemplateRoot: HullB
}
"""

ITEMS = """{ Item Id: 10, Name: CompA
  Category: Components
  MarketPrice: 10
}
{ Item Id: 11, Name: CompB
  Category: Components
  MarketPrice: 5
}
{ Item Id: 12, Name: Kit
  Category: Components
  MarketPrice: 2
}
{ Item Id: 13, Name: Coin
  Category: Components
  Credits: 50
}
"""

TEMPLATES = """{ Template Name: GenA
  CraftTime: 5
  { Child Inputs
    CompA: 5
  }
}
{ Template Name: GenB
  CraftTime: 5
  { Child Inputs
    CompA: 3
  }
}
{ Template Name: GenC
  CraftTime: 10
  { Child Inputs
    CompA: 20
  }
}
{ Template Name: Shared
  CraftTime: 5
  { Child Inputs
    CompA: 1
  }
}
{ Template Name: HullA
  CraftTime: 2
  { Child Inputs
    CompA: 1
  }
}
{ Template Name: HullB
  CraftTime: 2
  { Child Inputs
    CompA: 2
  }
}
{ Template Name: Kit
  CraftTime: 2
  { Child Inputs
    CompA: 1
    CompB: 1
  }
}
{ Template Name: Coin
  CraftTime: 2
  { Child Inputs
    CompA: 1
  }
}
"""

VANILLA_BLOCKS = """{ Block Id: 1, Name: GenA
  Class: Generator
  Category: Devices
}
"""

VANILLA_ITEMS = """{ Item Id: 10, Name: CompA
  MarketPrice: 10
}
{ Item Id: 11, Name: CompB
  MarketPrice: 5
}
{ Item Id: 12, Name: Kit
  MarketPrice: 2
}
"""

VANILLA_TEMPLATES = """{ Template Name: GenA
  CraftTime: 4
  { Child Inputs
    CompA: 2
    CompB: 1
  }
}
{ Template Name: Kit
  CraftTime: 2
  { Child Inputs
    CompA: 2
  }
}
"""


def _scenario(tmp_path: Path):
    cdir = tmp_path / "Content" / "Configuration"
    cdir.mkdir(parents=True)
    (cdir / "BlocksConfig.ecf").write_text(BLOCKS, encoding="utf-8")
    (cdir / "ItemsConfig.ecf").write_text(ITEMS, encoding="utf-8")
    (cdir / "Templates.ecf").write_text(TEMPLATES, encoding="utf-8")
    vdir = tmp_path / "vanilla" / "Configuration"
    vdir.mkdir(parents=True)
    (vdir / "BlocksConfig.ecf").write_text(VANILLA_BLOCKS, encoding="utf-8")
    (vdir / "ItemsConfig.ecf").write_text(VANILLA_ITEMS, encoding="utf-8")
    (vdir / "Templates.ecf").write_text(VANILLA_TEMPLATES, encoding="utf-8")
    return tmp_path, tmp_path / "vanilla"


def test_vanilla_composition_only_for_blocks(tmp_path):
    root, vanilla = _scenario(tmp_path)
    by_name = {p.name: p for p in analyze(root, vanilla)}
    gen_a = by_name["GenA"]
    assert gen_a.source == VANILLA
    assert ("CompB", 2) in gen_a.new_inputs
    kit = by_name["Kit"]
    # item : la composition de l'auteur est conservee (la vanille ne la
    # remplace pas)
    assert kit.source == SCENARIO
    assert [name for name, _qty in kit.new_inputs] == ["CompA", "CompB"]


def test_family_is_monotonic_in_power(tmp_path):
    root, vanilla = _scenario(tmp_path)
    by_name = {p.name: p for p in analyze(root, vanilla)}
    gen_a, gen_b = by_name["GenA"], by_name["GenB"]
    assert gen_b.changed
    assert gen_b.new_cost >= gen_a.new_cost


def test_shared_template_uses_max_power(tmp_path):
    root, vanilla = _scenario(tmp_path)
    shared = {p.name: p for p in analyze(root, vanilla)}["Shared"]
    assert shared.power == 900          # SharedB, pas SharedA (100)


def test_proxy_family_is_proportional(tmp_path):
    root, vanilla = _scenario(tmp_path)
    by_name = {p.name: p for p in analyze(root, vanilla)}
    hull_a, hull_b = by_name["HullA"], by_name["HullB"]
    assert hull_a.proxy and hull_b.proxy
    assert abs(hull_b.target_cost / hull_a.target_cost - 2.0) < 0.1


def test_currency_is_never_touched(tmp_path):
    root, vanilla = _scenario(tmp_path)
    coin = {p.name: p for p in analyze(root, vanilla)}["Coin"]
    assert not coin.changed
    assert "Credits" in coin.detail


def test_apply_writes_composition_and_craft_time(tmp_path):
    root, vanilla = _scenario(tmp_path)
    by_name = {p.name: p for p in analyze(root, vanilla)}
    apply_proposals([by_name["GenA"], by_name["GenB"]])
    text = (root / "Content/Configuration/Templates.ecf").read_text(
        encoding="utf-8")
    assert "CompB: 2" in text                 # composition vanille GenA
    assert "CompA: 4" in text                 # GenB remonte
    assert "CraftTime: 7" in text             # GenB 5 -> 7


def test_pinned_rescan_does_not_repropose(tmp_path):
    """Anti-ratchet : apres application, le re-scan avec les cibles
    epinglees ne doit pas reproposer les memes blocs."""
    root, vanilla = _scenario(tmp_path)
    first = analyze(root, vanilla)
    changed = [p for p in first if p.changed]
    assert changed
    apply_proposals(changed)
    pinned = {p.name: p.target_cost for p in changed}
    again = analyze(root, vanilla, pinned=pinned)
    assert [p for p in again if p.changed and p.name in pinned] == []


def test_craft_time_sentinel_is_preserved(tmp_path):
    root, vanilla = _scenario(tmp_path)
    cdir = root / "Content/Configuration"
    (cdir / "BlocksConfig.ecf").write_text(
        BLOCKS + """{ Block Id: 8, Name: IntA
  Class: Generator
  Category: Devices
  EnergyOut: 50
  TemplateRoot: IntA
}
{ Block Id: 9, Name: IntB
  Class: Generator
  Category: Devices
  EnergyOut: 500
  TemplateRoot: IntB
}
""", encoding="utf-8")
    (cdir / "Templates.ecf").write_text(
        TEMPLATES + """{ Template Name: IntA
  CraftTime: 999999
  { Child Inputs
    CompA: 1
  }
}
{ Template Name: IntB
  CraftTime: 999999
  { Child Inputs
    CompA: 1
  }
}
""", encoding="utf-8")
    by_name = {p.name: p for p in analyze(root, vanilla)}
    assert by_name["IntB"].old_craft == 999999
    assert by_name["IntB"].new_craft == 999999
