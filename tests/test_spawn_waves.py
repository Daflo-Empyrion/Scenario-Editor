"""Ondes de spawn (core/spawn_waves.py) : scan transversal sur un scenario
synthetique planete + espace, edition groupée (apercu -> application avec
commentaires preserves) et controles de coherence W310/W311."""

from pathlib import Path

from core.spawn_waves import (KIND_FREEDRONE, KIND_PATROL, KIND_POI,
                              KIND_VESSEL, apply_changes, apply_count,
                              check_spawn_consistency, scan, scale_count)

PLANET_STATIC = """---
# playfield de test (commentaire a PRESERVER)
PlayfieldType: Planet
PvPProb: 0

POIs:
    Random:
        - GroupName: R2DroneBase
          Faction: Zirax
          CountMinMax: [ 2, 5 ]
          DroneProb: 0.5
          DronesMinMax: [ 3, 4 ]

        - GroupName: AlienOutpost
          Faction: Zirax
          CountMinMax: [ 1, 1 ]

DroneBaseSetup:
    DroneBases:
        - Name: R2DroneBase
          Stock:
            - Name: TrapDrone
              Amount: Infinite

DroneSpawning:
    Random:
        - DronesMinMax: [ 4, 6 ]
          CenterX: -5000

SpawnRateZones:
   - SpawnAt: [R2DroneBase]
     Radius: 400
"""

SPACE_DYNAMIC = """---
PlayfieldType: Space
PvPProb: 1

DroneBaseSetup:
    FreeDrones:
        - Name: [SpaceDroneLaser]
          Faction: Zirax
          Count: [30, 50]
    SpaceVessels:
        - Name: [OPVZirax]
          Faction: Zirax
          CountMinMax: [5, 10]
          Probability: 1
"""

# patrouilles ACTIVES sans base -> W310
ACTIVE_PATROL_NO_BASE = """---
PlayfieldType: Planet

DroneSpawning:
    Random:
        - DronesMinMax: [ 2, 3 ]
          CenterX: 100
"""

# patrouilles [0, 0] sans base : volontaire (vanilla Eden, geantes gazeuses)
# -> JAMAIS alerte
ZERO_PATROL_NO_BASE = """---
PlayfieldType: Planet

DroneSpawning:
    Random:
        - DronesMinMax: [ 0, 0 ]
          CenterX: 100
"""

# zone de taux ne designant AUCUN POI existant -> W311 (une liste mixte --
# noms valides + POI desactives -- reste appliquee : jamais alertee)
BAD_RATE_ZONE = """---
PlayfieldType: Planet

POIs:
    Random:
        - GroupName: OutpostA
          CountMinMax: [ 1, 1 ]

SpawnRateZones:
   - SpawnAt: [Introuvable, AussiIntrouvable]
     Radius: 80
"""


def _scenario(tmp_path: Path) -> Path:
    p1 = tmp_path / "Playfields" / "TestPlanet"
    p2 = tmp_path / "Playfields" / "TestSpace"
    p1.mkdir(parents=True)
    p2.mkdir(parents=True)
    (p1 / "playfield_static.yaml").write_text(PLANET_STATIC, encoding="utf-8")
    (p2 / "space_dynamic.yaml").write_text(SPACE_DYNAMIC, encoding="utf-8")
    return tmp_path


def test_scan_summaries(tmp_path):
    res = scan(_scenario(tmp_path))
    by_name = {s.playfield: s for s in res.summaries}
    planet = by_name["TestPlanet"]
    assert planet.pf_type == "Planet"
    assert planet.poi_min == 3 and planet.poi_max == 6
    # garnison : POI 1 seulement (DroneProb 0.5 x [3,4]) -> 2 x 0.5 x 3, 5 x 0.5 x 4
    assert planet.drones_min == 3 and planet.drones_max == 10
    assert planet.vessels_min == 0
    assert planet.patrol_zones == 1
    assert planet.patrol_min == 4 and planet.patrol_max == 6
    assert planet.rate_zones == 1
    space = by_name["TestSpace"]
    assert space.pf_type == "Space"
    assert space.freedrones_min == 30 and space.freedrones_max == 50
    assert space.vessels_min == 5 and space.vessels_max == 10


def test_scan_entries(tmp_path):
    res = scan(_scenario(tmp_path))
    by_kind = {}
    for e in res.entries:
        by_kind.setdefault(e.kind, []).append(e)
    pois = by_kind[KIND_POI]
    assert [(e.name, e.count_min, e.count_max, e.faction)
            for e in pois] == [("R2DroneBase", 2, 5, "Zirax"),
                               ("AlienOutpost", 1, 1, "Zirax")]
    vessels = by_kind[KIND_VESSEL]
    assert len(vessels) == 1 and vessels[0].count_min == 5 \
        and vessels[0].count_max == 10 and vessels[0].probability == 1.0
    freed = by_kind[KIND_FREEDRONE]
    assert freed[0].count_min == 30 and freed[0].count_key == "Count"
    patrols = by_kind[KIND_PATROL]
    assert patrols[0].count_min == 4 and patrols[0].name == "Center -5000"


def test_scale_count_rounding_and_clamp():
    res = scan(_scenario(Path(__import__("tempfile").mkdtemp())))

    def entry(cmin, cmax):
        e = res.entries[0]
        e.count_min, e.count_max = cmin, cmax
        return e

    assert scale_count(entry(2, 5), 0.5) == (1, 2)      # arrondi
    assert scale_count(entry(3, 3), 3) == (9, 9)
    assert scale_count(entry(1, 1), 0.05) == (0, 0)     # plancher
    assert scale_count(entry(5, 2), 2) == (4, 10)       # max >= min


def test_apply_count_and_changes_preserves_comments(tmp_path):
    root = _scenario(tmp_path)
    res = scan(root)
    poi = next(e for e in res.entries if e.name == "R2DroneBase")
    assert apply_count(poi, 4, 10)
    assert apply_changes([poi]) == {poi.path: 1}
    text = poi.path.read_text(encoding="utf-8")
    assert "CountMinMax: [4, 10]" in text
    assert "# playfield de test (commentaire a PRESERVER)" in text
    assert "DroneProb: 0.5" in text                     # autre param intact


def test_checks_w310_w311_and_zero_patrol(tmp_path):
    root = _scenario(tmp_path)
    p3 = root / "Playfields" / "EdenGiant"
    p3.mkdir()
    (p3 / "playfield_static.yaml").write_text(ZERO_PATROL_NO_BASE,
                                              encoding="utf-8")
    p4 = root / "Playfields" / "EdenHive"
    p4.mkdir()
    (p4 / "playfield_static.yaml").write_text(ACTIVE_PATROL_NO_BASE,
                                              encoding="utf-8")
    p5 = root / "Playfields" / "BadZone"
    p5.mkdir()
    (p5 / "playfield_static.yaml").write_text(BAD_RATE_ZONE,
                                              encoding="utf-8")
    issues = check_spawn_consistency(root)
    codes = sorted(i.code for i in issues)
    assert codes == ["W310", "W311"]                    # zero-patrol muet
    w310 = next(i for i in issues if i.code == "W310")
    assert w310.file_path.parent.name == "EdenHive"
    w311 = next(i for i in issues if i.code == "W311")
    assert "Introuvable" in w311.message


def test_checks_mixed_rate_zone_not_flagged(tmp_path):
    root = _scenario(tmp_path)
    p = root / "Playfields" / "MixedZone"
    p.mkdir()
    (p / "playfield_static.yaml").write_text(
        BAD_RATE_ZONE.replace("[Introuvable, AussiIntrouvable]",
                              "[OutpostA, Introuvable]"), encoding="utf-8")
    assert check_spawn_consistency(root) == []


def test_checks_clean_scenario(tmp_path):
    issues = check_spawn_consistency(_scenario(tmp_path))
    assert issues == []
