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

"""Tests des correctifs de balance (core/balance_audit.py) : chaque correctif
applique SA garde (valeur actuelle attendue), écrit la nouvelle valeur, et
un second passage ne change plus rien (les gardes sautent)."""
import pytest

BR = chr(10)

ECLASS = BR.join([
    "{ +Entity Name: DroneBaseAttackHeavyMinigun, Ref: DroneBaseAttackMinigun",
    "  MaxHealth: 10000",
    "  XpFactor: 69",
    "}",
    "",
    "{ +Entity Name: Eden_ZiraxInfectedGreenEasy, Ref: ZiraxInfectedGreen",
    "  MaxHealth: 1000",
    "}",
    "",
    "{ +Entity Name: Eden_SpaceDronePirateGatling, Ref: SpaceDronePlasma",
    "  MaxHealth: 1500",
    "}",
    "",
    "{ +Entity Name: Eden_RoyalZiraxCommander",
    "  MaxHealth: 3500",
    "  ItemsOnEnterGame: MinigunEpic",
    "}",
    "",
    "{ Entity Name: TestOrphan",
    "  Material: MechArmored",
    "}",
    "",
    "{ +Entity Name: Eden_DroneBaySwarm_Drone",
    "  MaxHealth: 25000",
    "  XpFactor: 0",
    "}",
    "",
    "{ +Entity Name: AssaultMechT2",
    "  MaxHealth: 10000",
    "  XpFactor: 35",
    "}",
    "",
    "{ +Entity Name: Eden_AbyssalAssaultMech",
    "  MaxHealth: 20000",
    "  Material: MechArmored",
    "  XpFactor: 100",
    "}",
    "",
    "{ +Entity Name: LightBomberBase",
    "  XpFactor: 15",
    "}",
    "",
    "{ +Entity Name: FastTransport",
    "  XpFactor: 10",
    "}",
    "",
    "{ +Entity Name: Eden_AlienBugQueenStatic",
    "  XpFactor: 25",
    "}",
    "",
    "{ +Entity Name: SpaceDroneLaserEasy",
    "  XpFactor: 9",
    "}",
    "",
])

ITEMS = BR.join([
    "{ +Item Id: 507, Name: MeleeMegalonopsGrey, Ref: MeleeTemplate",
    "  { Child 0",
    "    Class: Melee",
    "    ROF: 2, type: float",
    "    Damage: 550",
    "  }",
    "}",
    "",
    "{ Item Id: 3082, Name: Eden_Dissolver_Weapon2",
    "  { Child 0",
    "    ROF: 0.1, type: float",
    "    Damage: 125",
    "  }",
    "}",
    "",
    "{ +Item Id: 3004, Name: Eden_AbyssalSentry2_Weapon, Ref: RocketLauncherT2",
    "  { Child 0",
    "    ROF: 8, type: float",
    "    Damage: 400",
    "  }",
    "}",
    "",
    "{ +Item Id: 24640, Name: Eden_DroneAbyssalLaser_Ammo",
    "  Damage: 1200",
    "}",
    "",
    "{ Item Id: 38, Name: SubmachineGunT3",
    "  Damage: 66",
    "}",
    "",
    "{ +Item Id: 1401, Name: PulseRifleT3",
    "  Damage: 100",
    "}",
    "",
    "{ +Item Id: 20, Name: PistolT2, Ref: Pistol",
    "  Damage: 90",
    "}",
    "",
    "{ +Item Id: 3120, Name: Eden_ShotgunDouble",
    "  { Child 0",
    "    ROF: 0.5, type: float",
    "    BulletsPerShot: 12",
    "    Damage: 153",
    "  }",
    "}",
    "",
    "{ Item Id: 501, Name: BrafusFungi",
    "  { Child 0",
    "    AddHealth: 481",
    "  }",
    "}",
    "",
    "{ Item Id: 502, Name: Salad",
    "  { Child 0",
    "    AddHealth: 150",
    "  }",
    "}",
    "",
    "{ +Item Id: 612, Name: ArmorCombat",
    "  Armor: 500",
    "}",
    "",
    "{ +Item Id: 3028, Name: Eden_CultistOverseer_Weapon, Ref: MeleeTemplate",
    "  { Child 0",
    "    ROF: 2, type: float",
    "    Damage: 1",
    "  }",
    "}",
    "",
    "{ +Item Id: 3090, Name: Eden_Weston_Weapon, Ref: Eden_InfectedPositronWeapon",
    "  { Child 0",
    "    ROF: 0.2, type: float",
    "    Damage: 15",
    "  }",
    "}",
    "",
    "{ Item Id: 606, Name: ArmorLightT2, Ref: ArmorLight",
    "  RecipeName: LightArmor",
    "}",
    "",
    "{ Item Id: 607, Name: ArmorMediumT2, Ref: ArmorMedium",
    "  RecipeName: MediumArmor",
    "}",
    "",
    "{ +Item Id: 608, Name: ArmorHeavyT2, Ref: ArmorHeavy",
    "  RecipeName: HeavyArmor",
    "}",
    "",
    "{ Item Id: 603, Name: ArmorLightEpic, Ref: ArmorLight",
    "  RecipeName: LightArmorEpic",
    "}",
    "",
    "{ Item Id: 604, Name: ArmorMediumEpic, Ref: ArmorMedium",
    "  RecipeName: MediumArmorEpic",
    "}",
    "",
    "{ +Item Id: 605, Name: ArmorHeavyEpic, Ref: ArmorHeavy",
    "  RecipeName: HeavyArmorEpic",
    "}",
    "",
])

BLOCKS = BR.join([
    "{ +Block Id: 1679, Name: TurretLegacyDisruptor",
    "  HitPoints: 35000",
    "}",
    "",
    "{ Block Name: Eden_TurretPlasmaSmall",
    "  PickupTarget: TurretBaseLaserBlocks",
    "  TemplateRoot: TurretBaseLaserBlocks",
    "  XpFactor: 10",
    "}",
])

DMC = BR.join([
    "{ DamageMultiplierGroup Name: MinigunT2",
    "  DamageMultiplier_6: 1.2, param1: DronePlanet|DroneSpace|Mechanical",
    "  DamageMultiplier_7: 0.80, param1: CreatureHard",
    "}",
    "",
])

STATUS = BR.join([
    "{ StatusEffect Name: Eden_RegenerationImmunity",
    "  Duration: 30",
    "  Stack: extend",
    "  { Child Modify0",
    "    Stat: health",
    "    Amount: 500",
    "    Rate: 0.1",
    "  }",
    "}",
    "",
    "{ StatusEffect Name: Resurrected",
    "  Duration: 300",
    "  { Child Modify1",
    "    Stat: health",
    "    ModifyMaxValue: -300",
    "    NumberOperationType: Flat",
    "  }",
    "  { Child Modify2",
    "    Stat: stamina",
    "    ModifyMaxValue: -300",
    "    NumberOperationType: Flat",
    "  }",
    "}",
    "",
])

DIALOGUES = (
    "  OptionExecute_1: \"Player.Skills['PlasmaT1AmmoDamage'] = 300; "
    "Player.Skills['PlasmaT1AmmoBlastDamage'] = -300; RemoveItem('Token', 1, 68); "
    "PlasmaT1Ammo = 'Phonon Maser Converter'; ModSelection = 'Phonon Maser Converter'; "
    "PlasmaT1AmmoStat = 'Impact Damage +300 / Blast Damage -100%'\"" + BR
)


@pytest.fixture
def scenario(tmp_path):
    root = tmp_path / "Mini"
    cfg = root / "Content" / "Configuration"
    cfg.mkdir(parents=True)
    (cfg / "EClassConfig.ecf").write_text(ECLASS, encoding="utf-8", newline="")
    (cfg / "ItemsConfig.ecf").write_text(ITEMS, encoding="utf-8", newline="")
    (cfg / "StatusEffects.ecf").write_text(STATUS, encoding="utf-8", newline="")
    (cfg / "Dialogues.ecf").write_text(DIALOGUES, encoding="utf-8", newline="")
    (cfg / "DamageMultiplierConfig.ecf").write_text(DMC, encoding="utf-8", newline="")
    (cfg / "BlocksConfig.ecf").write_text(BLOCKS, encoding="utf-8", newline="")
    (cfg / "EGroupsConfig.ecf").write_text("{" + BR + "}", encoding="utf-8", newline="")
    (cfg / "FactionWarfare.ecf").write_text("# vide" + BR, encoding="utf-8", newline="")
    return root


def test_all_fixes_apply_on_fresh_fixture(scenario):
    from core.balance_audit import ALL_BALANCE_FIXES, run_balance_fixes
    reports = run_balance_fixes(scenario, list(ALL_BALANCE_FIXES), apply=True)
    by_id = {r["id"]: r for r in reports}
    # Sur le fixture minimal, seuls les correctifs dont les cibles existent
    # doivent s'appliquer — les autres sautent proprement (gardes).
    expected_zero = {"s1_antishield_t1", "s2_cutter_weapons", "t_player_mults",
                     "t_raider_ladder", "t_boss_weapons", "t_plasma_exploit",
                     "t_colored_hp", "t_yellow_hp", "t_xp_boss",
                     "t_turret_aliases", "easy_moon_patrol", "t_purple_ammo",
                     "t_t4_rof", "fw_scaling", "fw_reputation",
                     "fw_talon_prices", "fw_space_defense",
                     "fw_dead_categories"}
    for r in reports:
        if r["id"] in expected_zero:
            continue  # cibles absentes du fixture minimal
        assert r["edits"] > 0, (r["id"], r["details"])
    txt = (scenario / "Content" / "Configuration" / "EClassConfig.ecf").read_text("utf-8")
    assert "XpFactor: 6" in txt and "XpFactor: 69" not in txt
    assert "MaxHealth: 300" in txt and "Material: Mechanical" in txt
    assert "MaxHealth: 8000" in txt
    assert "XpFactor: 15" in txt
    items = (scenario / "Content" / "Configuration" / "ItemsConfig.ecf").read_text("utf-8")
    assert "Damage: 55" in items and "Damage: 550" not in items
    assert "ROF: 1.0" in items and "ROF: 0.8" in items and "Damage: 400" in items
    status = (scenario / "Content" / "Configuration" / "StatusEffects.ecf").read_text("utf-8")
    assert "Amount: 25" in status and "Rate: 0.5" in status
    # le malus stamina de Resurrected n'est PAS touché
    assert status.count("ModifyMaxValue: -300") == 1
    dlg = (scenario / "Content" / "Configuration" / "Dialogues.ecf").read_text("utf-8")
    assert "= 45" in dlg and "= -75" in dlg and "+45 / Blast Damage -25%" in dlg


def test_p2_fixes_apply(scenario):
    from core.balance_audit import run_balance_fixes
    reports = run_balance_fixes(scenario, [
        "p2_weapons_progression", "p2_minigun_t2_hard", "p2_titan_armor",
        "p2_armor_t2", "p2_armor_epic", "p2_heal_food", "p2_boss_weapons",
        "p2_xp_coherence"], apply=True)
    assert all(r["edits"] > 0 for r in reports), [
        (r["id"], r["details"]) for r in reports if r["edits"] == 0]
    items = (scenario / "Content" / "Configuration" / "ItemsConfig.ecf").read_text("utf-8")
    assert "Damage: 120" in items and "Damage: 80" in items and "Damage: 110" in items
    assert "Armor: 650" in items and "Armor: 150" in items and "Armor: 400" in items
    assert "AddHealth: 75" in items and "Damage: 60" in items
    dmc = (scenario / "Content" / "Configuration" / "DamageMultiplierConfig.ecf").read_text("utf-8")
    assert "1.2, param1: CreatureHard" in dmc
    eclass = (scenario / "Content" / "Configuration" / "EClassConfig.ecf").read_text("utf-8")
    assert "XpFactor: 10" in eclass and "XpFactor: 20" in eclass


def test_second_run_is_noop(scenario):
    from core.balance_audit import ALL_BALANCE_FIXES, run_balance_fixes
    run_balance_fixes(scenario, list(ALL_BALANCE_FIXES), apply=True)
    snapshot = {p: p.read_bytes() for p in scenario.rglob("*") if p.is_file()}
    second = run_balance_fixes(scenario, list(ALL_BALANCE_FIXES), apply=True)
    assert all(r["edits"] == 0 for r in second), [
        (r["id"], r["details"]) for r in second if r["edits"]]
    for p, data in snapshot.items():
        assert p.read_bytes() == data


def test_guards_skip_on_mismatch(scenario):
    """Valeur actuelle différente de l'audit -> correction sautée, rien écrit."""
    from core.balance_audit import ALL_BALANCE_FIXES, run_balance_fixes
    items = scenario / "Content" / "Configuration" / "ItemsConfig.ecf"
    items.write_text(items.read_text("utf-8").replace("Damage: 550", "Damage: 999"),
                     encoding="utf-8", newline="")
    rep = run_balance_fixes(scenario, ["megalonops_melee"], apply=True)[0]
    assert rep["edits"] == 0
    assert "garde non satisfaite" in rep["details"][0]
    assert "Damage: 999" in items.read_text("utf-8")


def test_resurrected_stamina_malus_untouched(scenario):
    """Le -300 de stamina de Resurrected doit survivre à la correction (vécu :
    le premier projet de correctif touchait Modify1 ET Modify2)."""
    from core.balance_audit import ALL_BALANCE_FIXES, run_balance_fixes
    run_balance_fixes(scenario, ["resurrected_floor"], apply=True)
    status = (scenario / "Content" / "Configuration" / "StatusEffects.ecf").read_text("utf-8")
    assert "ModifyMaxValue: -100" in status
    assert "ModifyMaxValue: -300" in status   # stamina
