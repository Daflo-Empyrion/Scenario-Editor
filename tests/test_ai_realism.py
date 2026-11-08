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

"""Tests des passes de réalisme IA (core/ai_realism.py) sur un mini-scénario
de fixture : mapping vaisseaux, BAIConfig, tier curves, re-pops, archétypes,
comportements, groupes, réputation — plus backups/revert et audit."""
import json
from pathlib import Path

import pytest

BR = chr(10)

from core.ai_realism import (
    BackupStore, add_entity_lines, entity_spans, run_audit, run_passes,
    set_entity_prop,
)

ECLASS = """{ Entity Name: PredatorBAITemplate
  Faction: Predator
  MaxHealth: 250
  { Child VisionSensor
    VisibleDistance: 130
    ViewAngle: 110
  }
  { Child AlertSensor
    NoiseMaxDistance: 130
    NoiseAlertMultiplier: 1.5
    AlertLevelDrop: 5
  }
}

{ Entity Name: TestRaptor, Ref: PredatorBAITemplate
  Faction: Predator
  MaxHealth: 250
  { Child Hints   # predation
    IsHunting: 100
  }
}

{ Entity Name: TestPrey
  Faction: Prey
  MaxHealth: 120
}
"""

EGROUPS = """{ EGroup Name: Raptors
  TestRaptor: "2, 3"
}
"""

REP = """{ Reputation Name: "Human:1"
  Zirax: 12005
}

{ Reputation Name: "Action.Reputation"
  Order:                   "Zirax,  Talon,  Polaris,  Pirates, Trader,  Colonists,   Xenu,   Rados, Epsilon,  Ghyst,   Serdu, Abyssal,  Tesch,   Farr,  Wastelanders,    ARC,  Eden_Defender"
  StructSpawnedInTerritory:"    0,      0,        0,        0,      0,          0,      0,       0,       0,      0,       0,       0,      0,      0,             0,      0,              0"
  StructStayInTerritory:   "    0,      0,        0,        0,      0,          0,      0,       0,       0,      0,       0,       0,      0,      0,             0,      0,              0"
}
"""

PLAYFIELD = """PlanetType: Barren
PlayfieldType: Planet
Difficulty: 2
DroneBaseSetup:
  Random:
    - GroupName: TestDroneBase
      Difficulty: 6
      Stock:
        - Name: ZiraxMinigun
          Amount: 5
POIs:
  Random:
    - GroupName: ZiraxBase
      DroneProb: 0
      ReserveCount: 0
      TroopTransport: False
CreatureSpawning:
  - Biomes: [ Any ]
    Entities:
      - Name: GolemIce
        Amount: 2
        DelayMinMax: [-1, -1]
SpawnZones:
  - SpawnAt: [ Ruins ]
    Entities:
      - Names: [ZiraxMinigunPatrol]
        Amount: 75
        DelayMinMax: [-1, -1]
DroneSpawning:
  Random:
    - Name: Ambient
      DronesMinMax: [0, 0]
"""


@pytest.fixture
def scenario(tmp_path):
    root = tmp_path / "MiniScenario"
    cfg = root / "Content" / "Configuration"
    cfg.mkdir(parents=True)
    (root / "Playfields" / "TestPF").mkdir(parents=True)
    (root / "Prefabs").mkdir()
    (cfg / "EClassConfig.ecf").write_text(ECLASS, encoding="utf-8", newline="\n")
    (cfg / "EGroupsConfig.ecf").write_text(EGROUPS, encoding="utf-8", newline="\n")
    (cfg / "DefReputation.ecf").write_text(REP, encoding="utf-8", newline="\n")
    (root / "Playfields" / "TestPF" / "playfield_static.yaml").write_text(
        PLAYFIELD, encoding="utf-8", newline="\n")
    (root / "Prefabs" / "R2PV_ZiraxCutter01.epb").write_bytes(b"")
    return root


def test_vessel_mapping_apply_and_revert(scenario):
    pf = scenario / "Playfields" / "TestPF" / "playfield_static.yaml"
    pf.write_text(pf.read_text(encoding="utf-8").replace(
        "GroupName: ZiraxBase", "GroupName: ZiraxBase"), encoding="utf-8")
    # ajoute une référence morte
    txt = pf.read_text(encoding="utf-8")
    txt = txt.replace("- GroupName: ZiraxBase",
                      "- Name: R2PVZiraxT1\n      Faction: Xenu\n- GroupName: ZiraxBase")
    pf.write_text(txt, encoding="utf-8", newline="\n")
    original = pf.read_bytes()

    dry = run_passes(scenario, ["vessel_mapping"], apply=False)[0]
    assert dry["edits"] == 1 and pf.read_bytes() == original

    rep = run_passes(scenario, ["vessel_mapping"], apply=True)[0]
    assert rep["edits"] == 1
    assert "R2PV_ZiraxCutter01" in pf.read_text(encoding="utf-8")
    assert "R2PVZiraxT1" not in pf.read_text(encoding="utf-8")

    # revert via le dernier run
    backups = scenario.parent / (scenario.name + "_ai_backups")
    run_id = sorted(p.name for p in backups.iterdir() if p.is_dir())[-1]
    store = BackupStore(scenario, run_id=run_id)
    assert store.revert() >= 1
    assert pf.read_bytes() == original


def test_baiconfig_and_animations_generated(scenario):
    rep = run_passes(scenario, ["baiconfig", "animations"], apply=True)
    assert all(r["edits"] == 1 for r in rep)
    cfg = scenario / "Content" / "Configuration"
    bai = (cfg / "BAIConfig.ecf").read_text(encoding="utf-8")
    assert "MainAnimal" in bai and "RandomWalk" in bai
    anim = (cfg / "Animations.ecf").read_text(encoding="utf-8")
    assert "hold type" in anim and "20: 0" in anim
    # 2e passe : no-op
    again = run_passes(scenario, ["baiconfig"], apply=True)[0]
    assert again["edits"] == 0


def test_tier_curves_high_tier(scenario):
    pf = scenario / "Playfields" / "TestPF" / "playfield_static.yaml"
    rep = run_passes(scenario, ["tier_curves"], apply=True)[0]
    assert rep["edits"] >= 3  # DroneProb + Reserve (+ TroopTransport si hash 33%)
    txt = pf.read_text(encoding="utf-8")
    assert "DroneProb: 0.5" in txt
    assert "ReserveCount: 5" in txt
    assert "DronesMinMax: [1, 2]" in txt
    # tier early : rien ne change
    pf.write_text(pf.read_text(encoding="utf-8").replace("Difficulty: 6",
                                                         "Difficulty: 1"),
                  encoding="utf-8")
    before = pf.read_bytes()
    run_passes(scenario, ["tier_curves"], apply=True)
    assert pf.read_bytes() == before


def test_repop_patrols_and_predators(scenario):
    pf = scenario / "Playfields" / "TestPF" / "playfield_static.yaml"
    rep = run_passes(scenario, ["repop"], apply=True)[0]
    assert rep["edits"] == 2
    txt = pf.read_text(encoding="utf-8")
    assert "DelayMinMax: [240, 360]" in txt       # patrouille
    assert "DelayMinMax: [300, 480]" in txt       # prédateur localisé (Golem)


def test_archetypes_edit_templates_and_entities(scenario):
    path = scenario / "Content" / "Configuration" / "EClassConfig.ecf"
    before = path.read_bytes()
    rep = run_passes(scenario, ["archetypes"], apply=True)[0]
    assert rep["edits"] >= 4
    txt = path.read_text(encoding="utf-8")
    # template Predator -> sentry
    assert "VisibleDistance: 110" in txt
    assert "NoiseAlertMultiplier: 0.8" in txt
    assert path.read_bytes() != before


def test_set_entity_prop_preserves_comment(scenario):
    path = scenario / "Content" / "Configuration" / "EClassConfig.ecf"
    text = path.read_text(encoding="utf-8")
    new_text, n = set_entity_prop(text, "PredatorBAITemplate", "MaxHealth", "999")
    assert n == 1
    assert "MaxHealth: 999" in new_text
    # clé absente -> 0, texte intact
    new_text2, n2 = set_entity_prop(text, "PredatorBAITemplate", "Inconnu", "1")
    assert n2 == 0 and new_text2 == text


def test_add_entity_lines_creates_child_block(scenario):
    path = scenario / "Content" / "Configuration" / "EClassConfig.ecf"
    text = path.read_text(encoding="utf-8")
    new_text, n = add_entity_lines(text, "TestPrey", ["GroupLeaderPriority: 2",
                                                      "MaxCountInGroup: 5"])
    assert n == 2
    assert "GroupLeaderPriority: 2" in new_text
    # indentation cohérente : la ligne insérée a l'indent du bloc entité
    assert "\n  GroupLeaderPriority: 2" in new_text
    # child manquant -> bloc créé
    new_text3, n3 = add_entity_lines(new_text, "TestPrey", ["TickIfLead: True"],
                                     child="GroupDirectionSensor")
    assert n3 == 1 and "{ Child GroupDirectionSensor" in new_text3
    # re-parseable : les spans d'entités restent stables
    assert set(entity_spans(new_text3)) == {"PredatorBAITemplate", "TestRaptor",
                                            "TestPrey"}


def test_behaviors_pass(scenario):
    path = scenario / "Content" / "Configuration" / "EClassConfig.ecf"
    # ajoute "Raptor" (cible de HERD_LEADERS/SFX_SENSE/NIGHT_SPEEDS) sans Hints
    text = path.read_text(encoding="utf-8")
    raptor_block = (
        "{ Entity Name: Raptor" + BR +
        "  Faction: Predator" + BR +
        "  MaxHealth: 250" + BR +
        "  SfxAlert: Enemies/Raptor/RaptorAlert" + BR +
        "}" + BR)
    path.write_text(text + raptor_block, encoding="utf-8", newline="")
    rep = run_passes(scenario, ["behaviors"], apply=True)[0]
    assert rep["edits"] > 0
    txt = path.read_text(encoding="utf-8")
    assert "GroupLeaderPriority: 1" in txt          # chef de meute
    assert "TickIfLead: True" in txt                # sensor de groupe
    assert "IsHunting: 100" in txt                  # Hints créés
    # cri de détection = le SfxAlert RÉEL de l'entité (chemin d'asset)
    assert "SfxSense: Enemies/Raptor/RaptorAlert" in txt
    # Raptor n'est pas dans NIGHT_SPEEDS (prédateur nocturne actif)
    assert "NightWanderSpeed:" not in txt


def test_sfxsense_bare_value_repaired_or_removed(scenario):
    """Une valeur SfxSense nue (sans chemin) posée par un run antérieur est
    réparée si l'entité a un son réel, retirée sinon."""
    from core.ai_realism import pass_behaviors
    path = scenario / "Content" / "Configuration" / "EClassConfig.ecf"
    text = path.read_text(encoding="utf-8")
    text += ("{ Entity Name: Crawler" + BR + "  SfxAlert: Enemies/Crawler/X" + BR
             + "  SfxSense: Crawler_SfxRandom" + BR + "}" + BR
             + "{ Entity Name: Spinosaurus" + BR + "  MaxHealth: 900" + BR
             + "  SfxSense: Spinosaurus_SfxRandom" + BR + "}" + BR)
    path.write_text(text, encoding="utf-8", newline="")
    pass_behaviors(scenario, apply=True)
    txt = path.read_text(encoding="utf-8")
    assert "SfxSense: Enemies/Crawler/X" in txt          # réparé
    assert "Spinosaurus_SfxRandom" not in txt            # retiré (aucun son)


def test_faction_groups_and_references(scenario):
    rep = run_passes(scenario, ["faction_groups"], apply=True)[0]
    assert rep["edits"] > 0
    groups = (scenario / "Content" / "Configuration" / "EGroupsConfig.ecf").read_text(
        encoding="utf-8")
    assert "{ EGroup Name: RaptorsFew" in groups
    pf = scenario / "Playfields" / "TestPF" / "playfield_static.yaml"
    # le fixture n'est pas dans les cibles GROUP_REFERENCES : rien dans le PF
    assert "RaptorsFew" not in pf.read_text(encoding="utf-8")


def test_reputation_restored(scenario):
    path = scenario / "Content" / "Configuration" / "DefReputation.ecf"
    rep = run_passes(scenario, ["reputation"], apply=True)[0]
    assert rep["edits"] >= 2
    txt = path.read_text(encoding="utf-8")
    assert '" -1000,  -300,' in txt
    assert '"  -25,   -50,' in txt


def test_audit_finds_then_clears(scenario):
    # ajoute une référence morte pour déclencher l'audit vessels
    pf = scenario / "Playfields" / "TestPF" / "playfield_static.yaml"
    txt = pf.read_text(encoding="utf-8")
    pf.write_text(txt.replace("- GroupName: ZiraxBase",
                              "- Name: R2OPVPolarisT1\n    - GroupName: ZiraxBase"),
                  encoding="utf-8", newline="\n")
    findings = {f["id"]: f for f in run_audit(scenario)}
    assert findings["vessels"]["severity"] == "critical"
    assert "baiconfig" in findings and "animations" in findings
    assert findings["drone_zero"]["count"] >= 1
    assert findings["patrol_norepop"]["count"] >= 1

    run_passes(scenario, ["vessel_mapping", "baiconfig", "animations",
                          "tier_curves", "repop"], apply=True)

    run_passes(scenario, ["vessel_mapping", "baiconfig", "animations",
                          "tier_curves", "repop"], apply=True)
    after = {f["id"] for f in run_audit(scenario)}
    assert not {"vessels", "baiconfig", "animations",
                "drone_zero", "patrol_norepop"} & after


def test_all_passes_are_idempotent(scenario):
    """Un 2e run complet ne doit RIEN modifier (vécu 08/11 : TickIfLead
    ajouté à chaque run -> doublons ; set_entity_prop comptait les valeurs
    déjà à jour)."""
    from core.ai_realism import ALL_PASSES
    path = scenario / "Content" / "Configuration" / "EClassConfig.ecf"
    raptor = ("{ Entity Name: Raptor" + BR + "  Faction: Predator" + BR
              + "  SfxAlert: Enemies/Raptor/RaptorAlert" + BR + "}" + BR)
    path.write_text(path.read_text(encoding="utf-8") + raptor,
                    encoding="utf-8", newline="")
    first = run_passes(scenario, list(ALL_PASSES), apply=True)
    assert sum(r["edits"] for r in first) > 0
    snapshot = {p: p.read_bytes() for p in scenario.rglob("*") if p.is_file()}
    second = run_passes(scenario, list(ALL_PASSES), apply=True)
    assert sum(r["edits"] for r in second) == 0, [
        (r["pass"], r["edits"]) for r in second if r["edits"]]
    for p, data in snapshot.items():
        assert p.read_bytes() == data, f"{p.name} modifié au 2e run"


def test_reputation_scoped_to_action_block(scenario):
    """Les blocs *.Rivalry ont aussi des StructSpawnedInTerritory à zéro, de
    sens différent : la passe ne doit toucher QUE Action.Reputation, même
    relancée (vécu 08/11 : un re-run non borné aurait écrasé Talon.Rivalry)."""
    path = scenario / "Content" / "Configuration" / "DefReputation.ecf"
    rivalry = ("{ Reputation Name: \"Talon.Rivalry\"" + BR
               + "  StructSpawnedInTerritory:\"    0,     0,     0\"" + BR
               + "}" + BR)
    path.write_text(path.read_text(encoding="utf-8") + rivalry,
                    encoding="utf-8", newline="")
    run_passes(scenario, ["reputation"], apply=True)
    run_passes(scenario, ["reputation"], apply=True)   # 2e run
    txt = path.read_text(encoding="utf-8")
    rival = txt[txt.find("Talon.Rivalry"):]
    assert "\"    0,     0,     0\"" in rival          # rivalité intacte
    assert '" -1000,  -300,' in txt                    # Action.Reputation corrigé
