"""Reglage du danger (core/difficulty_tuning.py) : collecte des 5 domaines,
garde-fous (START, IsImportant, zones a 0, bornes x3), refus destructeur,
application reelle avec commentaires preserves."""

from pathlib import Path

from core.difficulty_tuning import (DOMAINS, PRESETS, DOMAIN_LOOT,
                                    DOMAIN_PATROLS, DOMAIN_RESOURCES,
                                    DOMAIN_SPAWNS, apply_entries, build_plan)

PLAYFIELD = """---
PlayfieldType: Planet

POIs:
    Random:
        - GroupName: Normal
          CountMinMax: [ 10, 20 ]
          DronesMinMax: [ 2, 4 ]
        - GroupName: Important
          IsImportant: True
          CountMinMax: [ 1, 1 ]
        - GroupName: Starting
          CountMinMax: [ 3, 6 ]
          SpawnPOINear: [START]

DroneSpawning:
    Random:
        - DronesMinMax: [ 4, 8 ]
          CenterX: 100
        - DronesMinMax: [ 0, 0 ]
          CenterX: -100

Resources:
-  Name: [AsteroidVoxel01Iron]
   CountMinMax: [ 5, 10 ]
   Probability: 1
"""

DENSITIES = """---
PlayfieldType: Planet

Biomes:
  - Name: Grass
    Resources:
      - [RockResourceIron, 0.002, Free]
      - [RockResourceCopper, 0.001, Free]
"""

LOOT_GROUPS = """{ +LootGroup Name: Test
  Count: all
  Item_0: EmergencyRations, param1: 1
  Item_1: WaterBottle, param1: 5
}
"""

CONTAINERS = """{ +Container Id: 5
  Count: "3,4"
  { Child Items
    Name_0: Fiber, param1: 0.8, param2: "5,19"
    Name_1: TitanOre, param1: 0.6, param2: "2,3"
    Name_2: Bone, param1: 0.4
  }
}
"""

REPUTATION = """{ Reputation Name: "Human:1"
  Zirax: 0
  Talon: 15000
}
"""


def _scenario(tmp_path: Path) -> Path:
    pf = tmp_path / "Playfields" / "Pf"
    pf.mkdir(parents=True)
    (pf / "playfield_static.yaml").write_text(PLAYFIELD, encoding="utf-8")
    (pf / "playfield_dynamic.yaml").write_text(DENSITIES, encoding="utf-8")
    conf = tmp_path / "Content" / "Configuration"
    conf.mkdir(parents=True)
    (conf / "LootGroups.ecf").write_text(LOOT_GROUPS, encoding="utf-8")
    (conf / "Containers.ecf").write_text(CONTAINERS, encoding="utf-8")
    (conf / "DefReputation.ecf").write_text(REPUTATION, encoding="utf-8")
    return tmp_path


def _by_target(plan, needle: str):
    return [e for e in plan.entries if needle in e.target]


def test_domains_and_presets():
    assert set(DOMAINS) == {"spawns", "patrols", "resources", "loot",
                            "reputation"}
    # 'normal' ne change rien : aucun apercu ne doit proposer de valeur
    assert all(v == 1.0 for v in PRESETS["normal"].values())


def test_normal_plan_is_empty(tmp_path):
    plan = build_plan(_scenario(tmp_path), PRESETS["normal"])
    assert plan.entries == []


def test_spawns_scaled_with_guards(tmp_path):
    plan = build_plan(_scenario(tmp_path), {DOMAIN_SPAWNS: 1.5})
    normal = _by_target(plan, "Normal CountMinMax")[0]
    assert normal.old_value == 20 and normal.new_value == 30
    drones = _by_target(plan, "Normal DronesMinMax")[0]
    assert drones.new_value == 6
    # garde-fous
    important = _by_target(plan, "Important CountMinMax")[0]
    assert important.blocked.startswith("POI IsImportant")
    starting = _by_target(plan, "Starting CountMinMax")[0]
    assert starting.blocked.startswith("zone START")


def test_patrols_skip_zero_zones(tmp_path):
    plan = build_plan(_scenario(tmp_path), {DOMAIN_PATROLS: 2.0})
    patrols = [e for e in plan.entries if e.domain == DOMAIN_PATROLS]
    assert len(patrols) == 1                      # la zone [0,0] est ignoree
    assert patrols[0].old_value == 8 and patrols[0].new_value == 16


def test_resources_asteroid_and_density(tmp_path):
    plan = build_plan(_scenario(tmp_path), {DOMAIN_RESOURCES: 0.5})
    asteroid = _by_target(plan, "AsteroidVoxel01Iron")[0]
    assert asteroid.old_value == 10 and asteroid.new_value == 5
    iron = _by_target(plan, "densite RockResourceIron")[0]
    assert abs(iron.new_value - 0.001) < 1e-9
    assert iron.label_value(iron.new_value) in ("0.001", "0.001000")


def test_loot_quantities_only(tmp_path):
    plan = build_plan(_scenario(tmp_path), {DOMAIN_LOOT: 2.0})
    # LootGroups : quantite = param1
    water = _by_target(plan, "WaterBottle")[0]
    assert water.old_value == 5 and water.new_value == 10
    # Containers : quantite = param2 ; 'Bone' n'a pas de param2 -> ignoree
    fiber = _by_target(plan, "Fiber")[0]
    assert fiber.old_value == 19 and fiber.new_max_raw == 38
    assert _by_target(plan, "Bone") == []


def test_reputation_skips_zero(tmp_path):
    plan = build_plan(_scenario(tmp_path), {"reputation": 1.5})
    assert len(plan.entries) == 1
    entry = plan.entries[0]
    assert entry.target.endswith("Talon")
    assert entry.old_value == 15000 and entry.new_value == 22500


def test_cap_x3(tmp_path):
    plan = build_plan(_scenario(tmp_path), {DOMAIN_SPAWNS: 10.0})
    normal = _by_target(plan, "Normal CountMinMax")[0]
    assert normal.new_value == 60                  # plafond x3 de 20


def test_refuse_zero_coefficient(tmp_path):
    plan = build_plan(_scenario(tmp_path), {DOMAIN_SPAWNS: 0.0})
    assert plan.refusals and "coefficient nul" in plan.refusals[0]


def test_apply_writes_scaled_values(tmp_path):
    root = _scenario(tmp_path)
    plan = build_plan(root, {DOMAIN_SPAWNS: 1.5, DOMAIN_RESOURCES: 0.5})
    entries = [e for e in plan.entries if not e.blocked]
    assert entries
    apply_entries(entries)
    text = (root / "Playfields/Pf/playfield_static.yaml").read_text(
        encoding="utf-8")
    assert "CountMinMax: [15, 30]" in text
    assert "DronesMinMax: [3, 6]" in text
    # garde-fous intacts
    assert "SpawnPOINear: [START]" in text
    # ligne Starting inchangee, avec SA mise en forme d'origine
    assert "CountMinMax: [ 3, 6 ]" in text
    dyn = (root / "Playfields/Pf/playfield_dynamic.yaml").read_text(
        encoding="utf-8")
    assert "[RockResourceIron, 0.001, Free]" in dyn


def test_apply_loot_keeps_other_params(tmp_path):
    root = _scenario(tmp_path)
    plan = build_plan(root, {DOMAIN_LOOT: 2.0})
    apply_entries([e for e in plan.entries if not e.blocked])
    text = (root / "Content/Configuration/Containers.ecf").read_text(
        encoding="utf-8")
    assert 'param1: 0.8' in text                    # probabilite intacte
    assert 'param2: "10,38"' in text                # quantite x2
    assert "param2: \"1,2\"" not in text
    groups = (root / "Content/Configuration/LootGroups.ecf").read_text(
        encoding="utf-8")
    assert "Item_1: WaterBottle, param1: 10" in groups
