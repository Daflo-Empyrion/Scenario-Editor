"""Fiche du scenario (core/scenario_digest.py) : origines par prefixe,
inventaire joueur uniquement, monde (playfields/POI), ratios vs vanille et
rendu FR + EN."""

from pathlib import Path

from core.scenario_digest import collect_digest, origin_of, render_markdown

VAN_BLOCKS = """{ Block Name: VanHull
  Material: Device
  HitPoints: 100, type: int
  CPUIn: 10, type: int
  MarketPrice: 100
  TechTreeNames: "Base"
  UnlockLevel: 1
}

{ Block Name: VanWeapon
  Material: Device
  BlastDamage: 50
  TechTreeNames: "Base"
  UnlockLevel: 3
}

{ Block Name: VanHidden
  Material: Device
  TechTreeNames: "Hidden"
}
"""

VAN_ITEMS = """{ Item Name: VanDrill
  Material: Device
  TechTreeNames: "Base"
  UnlockLevel: 1
  { Child 0
    Class: Driller
    Damage: 100
  }
}
"""

SCN_BLOCKS = """{ Block Name: VanHull
  Material: Device
  HitPoints: 200, type: int
  CPUIn: 20, type: int
  MarketPrice: 50
  TechTreeNames: "Base"
  UnlockLevel: 1
}

{ Block Name: VanWeapon
  Material: Device
  BlastDamage: 100
  TechTreeNames: "Base"
  UnlockLevel: 3
}

{ Block Name: Eden_Blaster
  Material: Device
  HitPoints: 300
  TechTreeNames: "Base"
  UnlockLevel: 5
}

{ Block Name: ATL_Turret
  Material: Device
  TechTreeNames: "Base"
  UnlockLevel: 5
}

{ Block Name: BIZON_Core
  Material: Device
  TechTreeNames: "Base"
  UnlockLevel: 5
}

{ Block Name: AG_Wall
  Material: Device
  TechTreeNames: "Hidden"
}

{ Block Name: HiddenThing
  Material: Device
  TechTreeNames: "Hidden"
}

{ Block Name: UnprefixedBlock
  Material: Device
  TechTreeNames: "Base"
  UnlockLevel: 5
}
"""

SCN_ITEMS = """{ Item Name: VanDrill
  Material: Device
  TechTreeNames: "Base"
  UnlockLevel: 1
  { Child 0
    Class: Driller
    Damage: 200
  }
}

{ Item Name: Eden_Kit
  Material: Device
  TechTreeNames: "Base"
  UnlockLevel: 5
}

{ Item Name: ATL_Scanner
  Material: Device
  TechTreeNames: "Base"
  UnlockLevel: 5
}

{ Item Name: BIZON_Ammo
  Material: Device
  TechTreeNames: "Base"
  UnlockLevel: 5
}

{ Item Name: AG_Tool
  Material: Device
  TechTreeNames: "Hidden"
}
"""

PLANET = """PlayfieldType: Planet
PlanetType: Temperate
Difficulty: 3

POIs:
    Random:
        - GroupName: Base1
          CountMinMax: [ 1, 2 ]
        - Name: [Poi2]
          CountMinMax: [ 2, 4 ]
"""

MOON = """PlayfieldType: Moon
PlanetType: Snow

POIs:
    Random:
        - GroupName: MoonBase
          CountMinMax: [ 1, 1 ]
"""

SPACE = """PlayfieldType: Space
PlanetType: Space

POIs:
    Random:
        - GroupName: Wreck
          CountMinMax: [ 1, 1 ]
"""

SECTORS = """SolarSystems:
  - Name: Sys1
    Sectors:
      - Coordinates: [0, 0, 0]
        Playfields:
          - ['0,0,0', PlanetA, PlanetA]
          - ['0,0,0', MoonA, MoonA]
          - ['0,0,0', SpaceA, SpaceA]
          - ['0,0,0', Gen, StarterRandom_Hub, '']
"""


def _write_tree(base: Path, blocks: str, items: str) -> Path:
    conf = base / "Content" / "Configuration"
    conf.mkdir(parents=True)
    (conf / "BlocksConfig.ecf").write_text(blocks, encoding="utf-8")
    (conf / "ItemsConfig.ecf").write_text(items, encoding="utf-8")
    return base


def _scenario(tmp_path: Path) -> tuple[Path, Path]:
    vanilla = _write_tree(tmp_path / "vanilla", VAN_BLOCKS, VAN_ITEMS)
    root = _write_tree(tmp_path / "scenario", SCN_BLOCKS, SCN_ITEMS)
    for name in ("PlanetA", "MoonA", "SpaceA"):
        (root / "Playfields" / name).mkdir(parents=True)
    (root / "Playfields" / "PlanetA" / "playfield_static.yaml").write_text(
        PLANET, encoding="utf-8")
    (root / "Playfields" / "MoonA" / "playfield_static.yaml").write_text(
        MOON, encoding="utf-8")
    (root / "Playfields" / "SpaceA" / "space_dynamic.yaml").write_text(
        SPACE, encoding="utf-8")
    (root / "Sectors").mkdir()
    (root / "Sectors" / "Sectors.yaml").write_text(SECTORS, encoding="utf-8")
    (root / "gameoptions.yaml").write_text(
        "Options:\n  - EnableCPUPoints: False\n    MaxStructures: 2000\n",
        encoding="utf-8")
    return root, vanilla


def test_origin_by_prefix():
    vanilla = {"VanHull"}
    assert origin_of("VanHull", vanilla) == "vanilla"
    assert origin_of("Eden_Blaster", vanilla) == "eden"
    assert origin_of("ATL_Turret", vanilla) == "atl"
    assert origin_of("AG_Wall", vanilla) == "ag"
    assert origin_of("BIZON_Core", vanilla) == "bizon"
    assert origin_of("UnprefixedBlock", vanilla) == "base"


def test_digest_counts_only_visible_nodes(tmp_path):
    root, vanilla = _scenario(tmp_path)
    d = collect_digest(root, str(vanilla / "Content"))
    assert d.blocks == {"vanilla": 2, "eden": 1, "atl": 1, "ag": 0,
                        "bizon": 1, "base": 1}
    assert d.items == {"vanilla": 1, "eden": 1, "atl": 1, "ag": 0,
                       "bizon": 1, "base": 0}
    assert d.blocks_total == 6 and d.items_total == 4
    # les noeuds Hidden ne comptent pas, mais restent dans la config
    assert d.all_blocks["ag"] == 1 and d.blocks["ag"] == 0
    assert sum(d.all_blocks.values()) == 8
    assert sum(d.all_items.values()) == 5


def test_digest_world_counts(tmp_path):
    root, vanilla = _scenario(tmp_path)
    d = collect_digest(root, str(vanilla / "Content"))
    assert d.playfields == {"planet": 1, "moon": 1, "space": 1, "other": 0}
    assert d.instances == {"planet": 1, "moon": 1, "space": 1, "other": 1}
    assert d.instances_total == 4
    assert d.poi_defs == {"planet": 2, "moon": 1, "space": 1, "other": 0}
    assert d.poi_max == 6 + 1 + 1
    assert d.planet_difficulty == 3.0


def test_digest_ratios_effective_values(tmp_path):
    root, vanilla = _scenario(tmp_path)
    d = collect_digest(root, str(vanilla / "Content"))
    ratios = {r.key: (r.count, r.median) for r in d.ratios}
    assert ratios["hp"] == (1, 2.0)
    assert ratios["cpu"] == (1, 2.0)
    assert ratios["damage"] == (1, 2.0)
    assert ratios["price"] == (1, 0.5)
    assert ratios["mining"] == (1, 2.0)
    assert "shield" not in ratios
    assert d.options["EnableCPUPoints"] == "False"
    assert d.tree_visible == 10
    assert d.vanilla_tree_visible == 3


def test_render_fr_en_and_hidden_note(tmp_path):
    root, vanilla = _scenario(tmp_path)
    d = collect_digest(root, str(vanilla / "Content"))
    text = render_markdown(d)
    assert "## FR" in text and "## EN" in text
    assert "Contenu joueur" in text and "Player content" in text
    assert "| Eden (RE2) | 1 | 1 |" in text
    assert "Entièrement hors arbre : AG (Atlantis)" in text
    assert "**6 blocs et 4 items visibles.**" in text
    assert f"*{d.date}*" in text
    assert "x2.0" in text and "x0.5" in text


def test_digest_without_vanilla_has_no_ratios(tmp_path):
    root, _vanilla = _scenario(tmp_path)
    d = collect_digest(root, "")
    assert d.ratios == []
    assert d.vanilla_tree_visible == 0
    assert "Aucun nom commun mesurable" in render_markdown(d)
