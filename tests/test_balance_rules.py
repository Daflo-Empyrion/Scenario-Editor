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

"""Moteur d'equilibrage (core/balance_rules.py, MODULE_EQUILIBRAGE.md) :
inventaire vanille/scenario, propositions par regles (conserve / vanille /
plafond / POURCENTAGE — demande 24/09 : x% preserve les ratios internes
contrairement au plafond), application avec backups ; dialogue."""
import types

import pytest

from core.balance_rules import (BalanceConfig, _fmt_num, apply_proposals,
                                load_inventory, propose_changes)


@pytest.fixture
def ecf_trees(tmp_path):
    """Vanille : Turret MaxCount 6 + CPUIn 100 ; scenario : tout buffe."""
    van = tmp_path / "van" / "Configuration"
    scen = tmp_path / "scen" / "Content" / "Configuration"
    van.mkdir(parents=True)
    scen.mkdir(parents=True)
    (van / "BlocksConfig.ecf").write_text(
        "{ Block Id: 900, Name: TurretX\n"
        "  MaxCount: 6\n"
        "  CPUIn: 100\n"
        "  Damage: 50\n"
        "  EnergyOut: 0\n"
        "  HitPoints: 400\n"
        "  Volume: 100\n}\n"
        "{ Block Id: 901, Name: GeneratorX\n"
        "  EnergyOut: 1500\n}\n",
        encoding="utf-8")
    (scen / "BlocksConfig.ecf").write_text(
        "{ Block Id: 900, Name: TurretX\n"
        "  MaxCount: 32\n"
        "  ForceMaxCount: true\n"
        "  CPUIn: 5000\n"
        "  Damage: 900\n"
        "  EnergyOut: 0\n"
        "  HitPoints: 3200\n"
        "  Volume: 31.25\n}\n"
        "{ Block Id: 901, Name: GeneratorX\n"
        "  EnergyOut: 2000\n}\n"
        "{ Block Id: 902, Name: MissionContainer\n"
        "  CPUIn: 10000000\n}\n",
        encoding="utf-8")
    return van, scen


def test_inventory_last_definition_wins(ecf_trees):
    van, scen = ecf_trees
    inv = load_inventory([van], [scen])
    assert set(inv.vanilla) == {"TurretX", "GeneratorX"}
    final = inv.final_def("TurretX")
    assert final is not None and final.value("MaxCount") == "32"
    assert inv.final_def("Absent") is None


def test_propose_vanille(ecf_trees):
    van, scen = ecf_trees
    inv = load_inventory([van], [scen])
    props = propose_changes(inv, BalanceConfig.preset_vanille())
    got = {(p.block, p.prop): p.new for p in props}
    assert got[("TurretX", "MaxCount")] == "6"
    assert got[("TurretX", "CPUIn")] == "100"
    assert got[("TurretX", "Damage")] == "50"
    assert got[("TurretX", "HitPoints")] == "400"
    assert got[("TurretX", "Volume")] == "100"
    assert got[("GeneratorX", "EnergyOut")] == "1500"
    # MissionContainer : liste blanche CPU + pas d'equivalent vanille
    assert ("MissionContainer", "CPUIn") not in got
    # ForceMaxCount n'existe qu'au scenario : jamais touche en vanille
    assert all(p.prop != "ForceMaxCount" for p in props)


def test_propose_plafond(ecf_trees):
    van, scen = ecf_trees
    inv = load_inventory([van], [scen])
    cfg = BalanceConfig(
        policies={"MaxCount": "plafond", "CPUIn": "plafond"},
        plafonds={"MaxCount": 10, "CPUIn": 1000})
    got = {(p.block, p.prop): p.new for p in propose_changes(inv, cfg)}
    assert got[("TurretX", "MaxCount")] == "10"
    assert got[("TurretX", "CPUIn")] == "1000"
    # MissionContainer exclu du plafond CPU par la liste blanche
    assert ("MissionContainer", "CPUIn") not in got


def test_propose_pourcentage(ecf_trees):
    """Demande 24/09 : x% multiplie la valeur ACTUELLE de chaque bloc —
    les ratios entre blocs sont preserves (contrairement au plafond)."""
    van, scen = ecf_trees
    inv = load_inventory([van], [scen])
    cfg = BalanceConfig(
        policies={"Damage": "pourcentage", "HitPoints": "pourcentage",
                  "Volume": "pourcentage"},
        pourcentages={"Damage": 80.0, "HitPoints": 80.0, "Volume": 80.0})
    got = {(p.block, p.prop): p.new for p in propose_changes(inv, cfg)}
    # chaque bloc garde son ratio : 900*0.8=720, 3200*0.8=2560
    assert got[("TurretX", "Damage")] == "720"
    assert got[("TurretX", "HitPoints")] == "2560"
    # decimal : 31.25*0.8=25 (entier -> ecrit sans decimales)
    assert got[("TurretX", "Volume")] == "25"
    # GeneratorX non concerne (regles limitees a Damage/HitPoints/Volume)
    assert ("GeneratorX", "EnergyOut") not in got


def test_fmt_num():
    assert _fmt_num(720.0) == "720"
    assert _fmt_num(25.0) == "25"
    assert _fmt_num(15.625) == "15.62"      # arrondi bancaire du format
    assert _fmt_num(0.5) == "0.5"


def test_catalog_covers_essential_properties():
    """Garde-fou (vecu : CPUIn et HitPoints oublies en refaisant le
    catalogue) : les proprietes d'equilibrage essentielles doivent exister
    comme regles, plus celles demandees par l'utilisateur."""
    from core.balance_rules import RULES
    for prop in ("MaxCount", "CPUIn", "HitPoints", "Damage", "EnergyOut",
                 "EnergyIn", "EnergyInIdle", "MarketPrice", "Mass",
                 "Volume", "CostPerAU", "CostPerLY", "RangeAU", "RangeLY",
                 "StackSize", "SolarPanelEfficiency", "Range", "RangeSpace",
                 "ShieldCapacityBonus", "ReturnFactor", "ShieldCapacity",
                 "ShieldRecharge", "ShieldCooldown", "ShieldPerCrystal",
                 "BlastShieldDamagePenFac", "ShieldDamagePenFac",
                 "ShieldHitCooldown", "ThrusterForce"):
        assert prop in RULES, f"regle manquante : {prop}"


def test_apply_writes_backup_and_reloads(ecf_trees):
    van, scen = ecf_trees
    path = scen / "BlocksConfig.ecf"
    inv = load_inventory([van], [scen])
    props = [p for p in propose_changes(inv, BalanceConfig.preset_vanille())
             if p.block == "TurretX"]
    done = apply_proposals(props)
    assert done[path] == 5
    bak = path.with_suffix(".ecf.bak")
    assert bak.exists() and "MaxCount: 32" in bak.read_text(encoding="utf-8")
    inv2 = load_inventory([van], [scen])
    final = inv2.final_def("TurretX")
    assert final.value("MaxCount") == "6"
    assert final.value("CPUIn") == "100"
    assert final.value("HitPoints") == "400"
    assert final.value("Volume") == "100"
    # GeneratorX intact (aucune proposition cochee pour lui)
    assert inv2.final_def("GeneratorX").value("EnergyOut") == "2000"


def test_conserve_makes_no_proposal(ecf_trees):
    van, scen = ecf_trees
    inv = load_inventory([van], [scen])
    assert propose_changes(inv, BalanceConfig()) == []


def test_dialog_analyze_and_apply(qapp, ecf_trees, monkeypatch):
    """Regle projet : construction testee ; flux complet preset vanille ->
    apercu coche -> application -> message et bouton desactive."""
    from gui.balance_dialog import BalanceDialog
    van, scen = ecf_trees
    main = types.SimpleNamespace(workspace=types.SimpleNamespace(
        working_root=scen.parent.parent))
    pushes = []
    monkeypatch.setattr("core.settings.get_vanilla_content_path",
                        lambda: str(van.parent))
    monkeypatch.setattr("gui.msgboxes.info", lambda *a, **k: None)
    dlg = BalanceDialog(main)
    assert dlg.combo_preset.count() == 2
    dlg.combo_preset.setCurrentIndex(1)          # preset vanille
    assert all(c.currentData() == "vanille"
               for c in dlg._rule_policies.values())
    dlg._analyze()
    assert dlg.tree.topLevelItemCount() >= 5
    assert dlg.btn_apply.isEnabled()
    main._push_workspace_undo = lambda undo: pushes.append(undo)
    main._reload_tab_if_open_and_unmodified = lambda path: None
    dlg._apply()
    assert pushes, "l'undo espace de travail doit etre pousse"
    assert dlg.btn_apply.isEnabled() is False
    path = scen / "BlocksConfig.ecf"
    assert "MaxCount: 6" in path.read_text(encoding="utf-8")
