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

"""Vocabulaire des declencheurs d'evenements (GameEventType) reference par le
moteur du jeu, et liste des valeurs de 'Check:' acceptees par le PDA.

GAME_EVENT_TYPES = enumeration officielle du moteur, relevee dans la
reference de modding livree avec le jeu (Content/Extras/Modding Doc).
Un 'Check:' de PDA.yaml pioche dans ce vocabulaire et l'etend : les valeurs
observees dans les fichiers reels du jeu et du scenario de reference
(WaveDestroyed, ViewSelected, InventoryOpenedPoi, BiomeChanged...) sont
ajoutees par CHECKS de core/pda/schema.py.

Ce module ne sert qu'a la VALIDATION : une valeur de Check inconnue de la
reunion (schema + ce vocabulaire) est signalee au bilan, sans jamais etre
bloquee (le schema oriente, il n'interdit pas -- regle du projet).
"""
from __future__ import annotations

GAME_EVENT_TYPES = (
    "None",
    "InventoryOpened", "InventoryClosed", "InventoryEmptied",
    "InventoryContains", "InventoryContainsCountOfItem", "ToolbarContains",
    "ConstructionQueueContains",
    "BlocksPlaced", "StructureSpawned", "WindowOpened", "WindowClosed",
    "ItemsPickedUp", "ItemsUsed", "ItemsConsumed", "ItemsUnlocked",
    "ItemsCrafted",
    "BlocksRemoved", "BlockDestroyed",
    "DevicePowered", "DeviceNamePowered", "DeviceUsed", "MainPowerSwitched",
    "ResourceDiscovered", "PoiDiscovered",
    "NearResource", "NearPoi", "NearUnit",
    "SubjectKilled", "Signal",
    "PlayfieldEntered", "PlayfieldTypeEntered",
    "GameStarted", "GameEnded", "PlayerDied", "PlayerLevelUp",
    "SettingChanged", "StatusEffectApplied",
    "AttackedEntity", "KilledEntity",
    "EnterSVCockpit", "EnterGVCockpit",
    "PlacedConstructor", "PlacedFoodProcessor", "PlacedFuelTankInBase",
    "PlacedGeneratorInBase", "PlacedMedicinelabMS",
    "EscapePodHitGround",
    "OpenedBlueprintLibCreative", "OpenedBlueprintLibSurvival",
    "OpenedBlueprintLibSaveOverwrite", "OpenedBlueprintFactory",
    "OpenedEnergyNeedingObject", "OpenedConstructor",
    "OpenedOxygenGenerator",
    "CreatedBase", "CreatedSV", "CreatedGV", "CreatedCV",
    "LowOxygen", "LowFood", "PlantHarvested",
    "DrilledOrFilledBlocks", "OresDropped",
    "AttackedBlock", "StructureInEnemyTerritory", "BlockChanged",
    "AttackWave", "WaveDestroyed", "SetTimer", "NpcCorePlaced",
    "ShieldAttacked", "WaitAction", "DialogOption", "CreatedAstVoxel",
)

# Valeurs de 'Check:' observees dans les fichiers PDA reels mais absentes de
# l'enumeration moteur (le PDA ajoute ses propres declencheurs, ex.
# InventoryOpenedPoi, StarClassEntered, PlayfieldLeft).
PDA_EXTRA_CHECKS = (
    "InventoryOpenedPoi", "InventoryClosedPoi", "BiomeChanged",
    "PlayfieldLeft", "PlayfieldTypeLeft", "StarClassEntered",
    "ViewSelected", "HoldingItem", "StructureProduced",
    "ArmorEquipped", "ArmorBoostEquipped",
)


def known_checks() -> frozenset:
    """Vocabulaire complet connu : enum moteur + extras PDA + specs du schema
    (import tardif : le schema importe ce module serait circulaire autrement)."""
    from core.pda.schema import CHECKS
    return frozenset(GAME_EVENT_TYPES) | frozenset(PDA_EXTRA_CHECKS) \
        | frozenset(CHECKS)


def unknown_pda_checks(root) -> list:
    """[(fichier, valeur, occurrences)] des 'Check:' inconnus des fichiers
    Extras/PDA/*.yaml du scenario. Lecture ligne a ligne : 'Check' est
    toujours un scalaire dans les fichiers reels (aucun parsing YAML requis,
    donc aucun faux positif sur les fichiers mal formates -- ceux-la sont
    deja couverts par le controle YAML du bilan)."""
    import re
    from pathlib import Path

    known = known_checks()
    pattern = re.compile(
        r"^\s*(?:-\s+)?Check:\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:#.*)?$")
    found = []
    for path in sorted(Path(root).glob("Extras/PDA/*.yaml")):
        counts = {}
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            match = pattern.match(line)
            if match and match.group(1) not in known:
                counts[match.group(1)] = counts.get(match.group(1), 0) + 1
        for value, count in sorted(counts.items()):
            found.append((path, value, count))
    return found
