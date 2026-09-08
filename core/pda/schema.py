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

"""
Schema canonique du PDA.yaml -- reference unique du NOUVEAU module PDA
(core/pda/, gui/pda/), construit par cartographie automatique de TROIS vrais
fichiers (vanille 1053 chapitres, Atlantis 395, RE2 530 -- voir
PdaScriptDoc/map_schema.py, outil local non suivi git) et complete par la doc
moteur Eleon.PdaScript (PdaScriptDoc/html, Doxygen WIP 2019-06-03 : semantique
multijoueur des taches, dialogs, wave attacks -- mais PAS le schema YAML, les
classes *Data n'y sont pas documentees).

Tout ce qui est ici est CONFIRME par observation, jamais suppose :
- chaque Check liste ses champs avec leur frequence d'apparition reelle ;
- les enums (Category, Activatable, Visibility, Reward.Type, Guiding...) sont
  les valeurs EXACTES trouvees dans les trois fichiers ;
- 'kinds' = type de valeur pour l'editeur GUI (token = texte localise via
  PDA.csv, text = texte brut non localise, int, float, bool, names/types =
  liste de valeurs, enum).

Un check absent de CHECKS reste EDITERABLE (l'editeur affiche ses proprietes
existantes en mode arbitraire, meme discipline que la fiche d'info ECF) : le
schema oriente la saisie, il n'interdit jamais ce qui existe deja dans un
fichier reel."""
from dataclasses import dataclass, field
from typing import Dict, Tuple

# ---------------------------------------------------------------------------
# Kinds de champs (type de valeur pour le GUI et la validation)
# ---------------------------------------------------------------------------
KIND_TOKEN = "token"    # texte localise : la valeur du YAML est un jeton pda_XXXX
                        # resolu dans PDA.csv
KIND_TEXT = "text"      # texte brut NON localise (Comment, Group, PictureFile...)
KIND_INT = "int"
KIND_FLOAT = "float"
KIND_BOOL = "bool"
KIND_NAMES = "names"    # liste '- valeur' (cle YAML 'Names')
KIND_TYPES = "types"    # liste '- valeur' (cle YAML 'Types')
KIND_ENUM = "enum"

# Pools de suggestions contextuelles (resolus a l'execution depuis le scenario
# + la vanille, voir core/pda/suggestions.py -- les cles ci-dessous sont les
# identifiants de pool, pas des cles i18n).
POOL_POI = "poi"
POOL_UNIT = "unit"
POOL_PLAYFIELD = "playfield"
POOL_PLAYFIELD_TYPE = "playfield_type"
POOL_STAR_CLASS = "star_class"
POOL_DIALOG = "dialog"
POOL_SIGNAL = "signal"
POOL_WINDOW = "window"
POOL_RESOURCE = "resource"
POOL_ITEM = "item"
POOL_BLOCK = "block"
POOL_BIOME = "biome"
POOL_FACTION = "faction"
POOL_CHAPTER = "chapter"      # jetons ChapterTitle du meme PDA.yaml
POOL_PDA_TOKEN = "pda_token"  # toutes les cles deja utilisees dans PDA.yaml


@dataclass(frozen=True)
class FieldSpec:
    """Un champ YAML d'action, de chapitre ou de tache."""
    key: str
    kind: str
    label_key: str                  # cle i18n du libelle
    enum_values: Tuple[str, ...] = ()
    pool: str = ""                  # pool de suggestions (kinds names/types/text)
    tooltip_key: str = ""
    default: str = ""               # valeur proposee a la creation ('' = aucune)


@dataclass(frozen=True)
class CheckSpec:
    """Un type de Check d'action ('' = action purement informative sans Check :
    1144 occurrences reelles sur les trois fichiers -- simples lignes de texte
    affichees dans le PDA, jamais cochees)."""
    check: str                      # valeur exacte ecrite dans le YAML ('' = sans Check)
    label_key: str                  # cle i18n du libelle affiche
    desc_key: str                   # cle i18n de la description affichee
    fields: Tuple[FieldSpec, ...] = ()
    uses_names: bool = False
    uses_types: bool = False
    amount_optional: bool = False   # True si l'action a du sens SANS Amount


def _f(key, kind, label_key, **kw) -> FieldSpec:
    return FieldSpec(key=key, kind=kind, label_key=label_key, **kw)


# ---------------------------------------------------------------------------
# Enums confirmes (valeurs exactes observees dans les 3 fichiers)
# ---------------------------------------------------------------------------
CATEGORIES = ("SoloMission", "FactionMission", "Tutorial", "Knowledgebase", "FAQ", "JourneyBook")
ACTIVATABLE = ("Always", "Never", "WhenRewarded", "ByLevel", "ByReputation", "ByCredits", "WhenChecked")
VISIBILITY = ("Always", "Never", "WhenRewarded", "WhileCompleted", "WhenChecked", "ByLevel", "ByReputation")
GUIDING = ("Destination", "TempIndoor")
REWARD_TYPES = ("XP", "UP", "Reputation", "ReputationTarget", "LevelTarget", "LevelIncrease")

# Fenetres UI observees pour WindowOpened/WindowClosed (pool statique + les
# valeurs deja presentes dans le fichier ouvert, voir suggestions.py).
KNOWN_WINDOWS = ("Pda", "GalaxyMap", "Player", "Logistics", "StationInterface",
                 "TechTree", "ControlPanel", "Devices", "ConstructorSurvival")
# Classes stellaires observees pour StarClassEntered.
KNOWN_STAR_CLASSES = ("O", "B", "A", "F", "G", "K", "M", "D", "R", "N", "A4V", "M1Ia")

# ---------------------------------------------------------------------------
# Champs d'action COMMUNS (observés sur plusieurs checks -- proposes par
# l'editeur pour tout check, en plus des champs specifiques ci-dessous)
# ---------------------------------------------------------------------------
ACTION_COMMON_FIELDS: Tuple[FieldSpec, ...] = (
    _f("AllowManualCompletion", KIND_BOOL, "pda.field.allow_manual"),
    _f("IsOrdered", KIND_BOOL, "pda.field.is_ordered"),
    _f("IsOptional", KIND_BOOL, "pda.field.is_optional",
       tooltip_key="pda.field.is_optional.tooltip"),
    _f("Required", KIND_BOOL, "pda.field.required",
       tooltip_key="pda.field.required.tooltip"),
    _f("NamesRequired", KIND_BOOL, "pda.field.names_required"),
    _f("TriggerDistance", KIND_INT, "pda.field.trigger_distance", default="50"),
    _f("GuidingDistance", KIND_INT, "pda.field.guiding_distance", default="-1"),
    _f("Guiding", KIND_ENUM, "pda.field.guiding", enum_values=GUIDING),
    _f("Comment", KIND_TEXT, "pda.field.comment"),
)

_DESCRIPTION_FIELD = _f("Description", KIND_TOKEN, "pda.field.description")
_COMPLETED_MESSAGE_FIELD = _f("CompletedMessage", KIND_TOKEN, "pda.field.completed_message")

# ---------------------------------------------------------------------------
# Checks confirmes -- un par type, champs = union observee (le seul champ
# universellement present, Description, est ajoute automatiquement par
# action_fields() ci-dessous, pas duplique ici).
# ---------------------------------------------------------------------------
CHECKS: Dict[str, CheckSpec] = {s.check: s for s in (
    CheckSpec("", "pda.check.none.label", "pda.check.none.desc"),
    CheckSpec("WaitAction", "pda.check.wait.label", "pda.check.wait.desc", fields=(
        _f("Amount", KIND_INT, "pda.field.amount_seconds", default="10"),
    ), amount_optional=True),
    CheckSpec("NearPoi", "pda.check.near_poi.label", "pda.check.near_poi.desc", fields=(
        _f("Names", KIND_NAMES, "pda.field.names_poi", pool=POOL_POI),
    ), uses_names=True),
    CheckSpec("NearUnit", "pda.check.near_unit.label", "pda.check.near_unit.desc", fields=(
        _f("Names", KIND_NAMES, "pda.field.names_unit", pool=POOL_UNIT),
    ), uses_names=True),
    CheckSpec("NearResource", "pda.check.near_resource.label", "pda.check.near_resource.desc", fields=(
        _f("Types", KIND_TYPES, "pda.field.types_resource", pool=POOL_RESOURCE),
    ), uses_types=True),
    CheckSpec("DialogOption", "pda.check.dialog_option.label", "pda.check.dialog_option.desc", fields=(
        _f("Names", KIND_NAMES, "pda.field.names_dialog", pool=POOL_DIALOG),
        _f("Value", KIND_INT, "pda.field.value_option"),
    ), uses_names=True),
    CheckSpec("Signal", "pda.check.signal.label", "pda.check.signal.desc", fields=(
        _f("Names", KIND_NAMES, "pda.field.names_signal", pool=POOL_SIGNAL),
    ), uses_names=True),
    CheckSpec("PlayfieldEntered", "pda.check.playfield_entered.label", "pda.check.playfield_entered.desc", fields=(
        _f("Names", KIND_NAMES, "pda.field.names_playfield", pool=POOL_PLAYFIELD),
    ), uses_names=True),
    CheckSpec("PlayfieldLeft", "pda.check.playfield_left.label", "pda.check.playfield_left.desc", fields=(
        _f("Names", KIND_NAMES, "pda.field.names_playfield", pool=POOL_PLAYFIELD),
    ), uses_names=True),
    CheckSpec("PlayfieldTypeEntered", "pda.check.pf_type_entered.label", "pda.check.pf_type_entered.desc", fields=(
        _f("Names", KIND_NAMES, "pda.field.names_pf_type", pool=POOL_PLAYFIELD_TYPE),
    ), uses_names=True),
    CheckSpec("PlayfieldTypeLeft", "pda.check.pf_type_left.label", "pda.check.pf_type_left.desc", fields=(
        _f("Names", KIND_NAMES, "pda.field.names_pf_type", pool=POOL_PLAYFIELD_TYPE),
    ), uses_names=True),
    CheckSpec("StarClassEntered", "pda.check.star_class.label", "pda.check.star_class.desc", fields=(
        _f("Names", KIND_NAMES, "pda.field.names_star_class", pool=POOL_STAR_CLASS),
    ), uses_names=True),
    CheckSpec("SubjectKilled", "pda.check.subject_killed.label", "pda.check.subject_killed.desc", fields=(
        _f("Names", KIND_NAMES, "pda.field.names_targets", pool=POOL_UNIT),
        _f("Amount", KIND_INT, "pda.field.amount_kills", default="10"),
    ), uses_names=True),
    CheckSpec("BlockDestroyed", "pda.check.block_destroyed.label", "pda.check.block_destroyed.desc", fields=(
        _f("Types", KIND_TYPES, "pda.field.types_block", pool=POOL_BLOCK),
        _f("Names", KIND_NAMES, "pda.field.names_optional", pool=POOL_UNIT),
        _f("Amount", KIND_INT, "pda.field.amount", default="10"),
    ), uses_names=True, uses_types=True),
    CheckSpec("BlocksPlaced", "pda.check.blocks_placed.label", "pda.check.blocks_placed.desc", fields=(
        _f("Types", KIND_TYPES, "pda.field.types_block", pool=POOL_BLOCK),
        _f("Amount", KIND_INT, "pda.field.amount", default="1"),
    ), uses_types=True),
    CheckSpec("BlocksRemoved", "pda.check.blocks_removed.label", "pda.check.blocks_removed.desc", fields=(
        _f("Names", KIND_NAMES, "pda.field.names_optional", pool=POOL_UNIT),
        _f("Types", KIND_TYPES, "pda.field.types_block", pool=POOL_BLOCK),
        _f("Amount", KIND_INT, "pda.field.amount", default="1"),
    ), uses_names=True, uses_types=True),
    CheckSpec("InventoryContains", "pda.check.inventory_contains.label", "pda.check.inventory_contains.desc", fields=(
        _f("Names", KIND_NAMES, "pda.field.names_poi", pool=POOL_POI),
        _f("Types", KIND_TYPES, "pda.field.types_item", pool=POOL_ITEM),
        _f("Amount", KIND_INT, "pda.field.amount", default="1"),
    ), uses_names=True, uses_types=True),
    CheckSpec("InventoryContainsCountOfItem", "pda.check.inventory_count.label", "pda.check.inventory_count.desc", fields=(
        _f("Names", KIND_NAMES, "pda.field.names_poi", pool=POOL_POI),
        _f("Types", KIND_TYPES, "pda.field.types_item", pool=POOL_ITEM),
        _f("Amount", KIND_INT, "pda.field.amount", default="1"),
    ), uses_names=True, uses_types=True),
    CheckSpec("InventoryOpened", "pda.check.inventory_opened.label", "pda.check.inventory_opened.desc", fields=(
        _f("Names", KIND_NAMES, "pda.field.names_poi", pool=POOL_POI),
    ), uses_names=True),
    CheckSpec("InventoryClosed", "pda.check.inventory_closed.label", "pda.check.inventory_closed.desc", fields=(
        _f("Names", KIND_NAMES, "pda.field.names_poi", pool=POOL_POI),
    ), uses_names=True),
    CheckSpec("InventoryOpenedPoi", "pda.check.inventory_opened_poi.label", "pda.check.inventory_opened_poi.desc", fields=(
        _f("Names", KIND_NAMES, "pda.field.names_poi", pool=POOL_POI),
    ), uses_names=True),
    CheckSpec("InventoryClosedPoi", "pda.check.inventory_closed_poi.label", "pda.check.inventory_closed_poi.desc", fields=(
        _f("Names", KIND_NAMES, "pda.field.names_poi", pool=POOL_POI),
    ), uses_names=True),
    CheckSpec("ItemsPickedUp", "pda.check.items_picked.label", "pda.check.items_picked.desc", fields=(
        _f("Types", KIND_TYPES, "pda.field.types_item", pool=POOL_ITEM),
        _f("Amount", KIND_INT, "pda.field.amount", default="1"),
    ), uses_types=True),
    CheckSpec("ItemsCrafted", "pda.check.items_crafted.label", "pda.check.items_crafted.desc", fields=(
        _f("Names", KIND_NAMES, "pda.field.names_item", pool=POOL_ITEM),
        _f("Types", KIND_TYPES, "pda.field.types_item", pool=POOL_ITEM),
        _f("Amount", KIND_INT, "pda.field.amount", default="1"),
    ), uses_names=True, uses_types=True),
    CheckSpec("ItemsUnlocked", "pda.check.items_unlocked.label", "pda.check.items_unlocked.desc", fields=(
        _f("Types", KIND_TYPES, "pda.field.types_item", pool=POOL_ITEM),
        _f("Amount", KIND_INT, "pda.field.amount", default="1"),
    ), uses_types=True),
    CheckSpec("ToolbarContains", "pda.check.toolbar_contains.label", "pda.check.toolbar_contains.desc", fields=(
        _f("Types", KIND_TYPES, "pda.field.types_item", pool=POOL_ITEM),
        _f("Amount", KIND_INT, "pda.field.amount", default="1"),
    ), uses_types=True),
    CheckSpec("DeviceUsed", "pda.check.device_used.label", "pda.check.device_used.desc", fields=(
        _f("Names", KIND_NAMES, "pda.field.names_poi", pool=POOL_POI),
    ), uses_names=True),
    CheckSpec("DeviceNamePowered", "pda.check.device_powered.label", "pda.check.device_powered.desc", fields=(
        _f("Names", KIND_NAMES, "pda.field.names_device", pool=POOL_SIGNAL),
    ), uses_names=True),
    CheckSpec("MainPowerSwitched", "pda.check.main_power.label", "pda.check.main_power.desc", fields=(
        _f("Names", KIND_NAMES, "pda.field.names_poi", pool=POOL_POI),
    ), uses_names=True),
    CheckSpec("WindowOpened", "pda.check.window_opened.label", "pda.check.window_opened.desc", fields=(
        _f("Names", KIND_NAMES, "pda.field.names_window", pool=POOL_WINDOW),
    ), uses_names=True),
    CheckSpec("WindowClosed", "pda.check.window_closed.label", "pda.check.window_closed.desc", fields=(
        _f("Names", KIND_NAMES, "pda.field.names_window", pool=POOL_WINDOW),
    ), uses_names=True),
    CheckSpec("PlantHarvested", "pda.check.plant_harvested.label", "pda.check.plant_harvested.desc", fields=(
        _f("Types", KIND_TYPES, "pda.field.types_plant", pool=POOL_ITEM),
        _f("Amount", KIND_INT, "pda.field.amount", default="1"),
    ), uses_types=True),
    CheckSpec("ResourceDiscovered", "pda.check.resource_discovered.label", "pda.check.resource_discovered.desc", fields=(
        _f("Types", KIND_TYPES, "pda.field.types_resource", pool=POOL_RESOURCE),
    ), uses_types=True),
    CheckSpec("PoiDiscovered", "pda.check.poi_discovered.label", "pda.check.poi_discovered.desc", fields=(
        _f("Names", KIND_NAMES, "pda.field.names_poi", pool=POOL_POI),
    ), uses_names=True, amount_optional=True),
    CheckSpec("StructureSpawned", "pda.check.structure_spawned.label", "pda.check.structure_spawned.desc", fields=(
        _f("Names", KIND_NAMES, "pda.field.names_structure", pool=POOL_UNIT),
        _f("Amount", KIND_INT, "pda.field.amount", default="1"),
    ), uses_names=True),
    CheckSpec("BiomeChanged", "pda.check.biome_changed.label", "pda.check.biome_changed.desc", fields=(
        _f("Names", KIND_NAMES, "pda.field.names_biome", pool=POOL_BIOME),
    ), uses_names=True),
)}


def check_spec(check: str) -> CheckSpec:
    """Spec d'un check, y compris INCONNU (tenu a l'ecart mais editable :
    meme discipline que la fiche d'info ECF -- le schema oriente, n'interdit
    pas)."""
    return CHECKS.get(check, CheckSpec(check, "pda.check.unknown.label", "pda.check.unknown.desc"))


def action_fields(check: str) -> Tuple[FieldSpec, ...]:
    """Champs SAISISSABLES d'une action du check donne, dans l'ordre d'affiche :
    Description (token, toujours), champs specifiques du check, CompletedMessage,
    puis les champs communs. Les autres cles presentes dans le fichier restent
    affichees par la section 'autres proprietes' de l'editeur."""
    spec = check_spec(check)
    fields: list = [_DESCRIPTION_FIELD]
    fields.extend(spec.fields)
    fields.append(_COMPLETED_MESSAGE_FIELD)
    fields.extend(ACTION_COMMON_FIELDS)
    return tuple(fields)


# ---------------------------------------------------------------------------
# Chapitre : cles scalaires editables (les structures Tasks / Rewards /
# RepeatConditions / ChapterActivation / RewardedChapters ont leurs propres
# editeurs -- jamais traitees comme de simples cles).
# ---------------------------------------------------------------------------
CHAPTER_FIELDS: Tuple[FieldSpec, ...] = (
    _f("Category", KIND_ENUM, "pda.chapter.category", enum_values=CATEGORIES, default="SoloMission"),
    _f("NoSkip", KIND_BOOL, "pda.chapter.noskip", default="true"),
    _f("Activatable", KIND_ENUM, "pda.chapter.activatable", enum_values=ACTIVATABLE, default="Always"),
    _f("Visibility", KIND_ENUM, "pda.chapter.visibility", enum_values=VISIBILITY, default="Always"),
    _f("PlayerLevel", KIND_INT, "pda.chapter.player_level", default="1"),
    _f("Group", KIND_TEXT, "pda.chapter.group"),
    _f("HideTasks", KIND_BOOL, "pda.chapter.hide_tasks"),
    _f("Description", KIND_TOKEN, "pda.chapter.description"),
    _f("StartMessage", KIND_TOKEN, "pda.chapter.start_message"),
    _f("CompletedMessage", KIND_TOKEN, "pda.chapter.completed_message"),
    _f("SkipMessage", KIND_TOKEN, "pda.chapter.skip_message"),
    _f("Faction", KIND_TEXT, "pda.chapter.faction", pool=POOL_FACTION),
    _f("ReputationLevel", KIND_INT, "pda.chapter.reputation_level"),
    _f("PictureFile", KIND_TEXT, "pda.chapter.picture"),
    _f("AutoActivateOnGameStart", KIND_BOOL, "pda.chapter.auto_activate"),
    _f("ActivateChapterOnCompletion", KIND_TEXT, "pda.chapter.activate_on_completion", pool=POOL_CHAPTER),
    _f("ActivateChapterOnSkip", KIND_TEXT, "pda.chapter.activate_on_skip", pool=POOL_CHAPTER),
    _f("Playfields", KIND_NAMES, "pda.chapter.playfields", pool=POOL_PLAYFIELD),
    _f("PlayfieldTypes", KIND_NAMES, "pda.chapter.playfield_types", pool=POOL_PLAYFIELD_TYPE),
    _f("VisibleOnStartPlayfields", KIND_NAMES, "pda.chapter.visible_on_start", pool=POOL_PLAYFIELD),
    _f("VisibleOnStartPlayfieldTypes", KIND_NAMES, "pda.chapter.visible_on_start_types", pool=POOL_PLAYFIELD_TYPE),
    _f("PlayerCredits", KIND_INT, "pda.chapter.player_credits"),
    _f("Comment", KIND_TEXT, "pda.field.comment"),
)
# Cles de structure, gerees par des editeurs dedies (jamais dans CHAPTER_FIELDS).
# TOUTES les cles de premier niveau observees sur les vrais fichiers sont
# couvertes : scalaires dans CHAPTER_FIELDS, structures ici.
CHAPTER_STRUCTURE_KEYS = ("Tasks", "Rewards", "RepeatConditions", "ChapterActivation",
                          "RewardedChapters")

TASK_FIELDS: Tuple[FieldSpec, ...] = (
    _f("Headline", KIND_TOKEN, "pda.task.headline"),
    _f("StartMessage", KIND_TOKEN, "pda.chapter.start_message"),
    _f("CompletedMessage", KIND_TOKEN, "pda.chapter.completed_message"),
    _f("StartDelay", KIND_INT, "pda.task.start_delay"),
    _f("HasUniqueItems", KIND_BOOL, "pda.task.unique_items"),
    _f("OnlyVisibleWhenRewarded", KIND_BOOL, "pda.task.only_visible_rewarded"),
    _f("OnActivateSignal", KIND_TEXT, "pda.task.on_activate_signal", pool=POOL_SIGNAL),
    _f("OnCompleteSignal", KIND_TEXT, "pda.task.on_complete_signal", pool=POOL_SIGNAL),
    _f("RewardedTasks", KIND_NAMES, "pda.task.rewarded_tasks", pool=POOL_PDA_TOKEN),
    _f("RewardedChapters", KIND_NAMES, "pda.task.rewarded_chapters", pool=POOL_CHAPTER),
    _f("PictureFile", KIND_TEXT, "pda.chapter.picture"),
    _f("Comment", KIND_TEXT, "pda.field.comment"),
)
# Cles de structure de tache : Actions et Rewards ont des editeurs dedies ; les
# sections On*Ops (automatisations du jeu : playfield ops, player ops, UI ops,
# PDA data ops -- observees sur 398 taches du RE2 pour PictureFile et 171 pour
# OnCompletePdaDataOps) restent LECTURE SEULE dans la section 'Avance' du
# panneau tache (formats complexes non documentes : edition fiable via l'onglet
# YAML brut). RewardedTasks/RewardedChapters sont dans TASK_FIELDS (listes).
TASK_STRUCTURE_KEYS = ("Actions", "Rewards")
TASK_ADVANCED_KEYS = ("OnCompletePdaDataOps", "OnCompletePlayfieldOps", "OnCompletePlayerOps",
                      "OnActivatePlayfieldOps", "OnCompleteUIOps", "OnActivateUIOps",
                      "OnActivatePlayerOps")

# RepeatConditions confirmees (Delay et DelayAdd = variantes du vrai fichier,
# gardees telles quelles -- la difference exacte de semantique moteur n'est pas
# documentee ; l'editeur ne propose que NumRepeats/DelaySeconds/NoReminder a la
# CREATION, mais edite tout ce qui existe deja).
REPEAT_FIELDS: Tuple[FieldSpec, ...] = (
    _f("NumRepeats", KIND_INT, "pda.repeat.num_repeats", default="5"),
    _f("DelaySeconds", KIND_INT, "pda.repeat.delay_seconds"),
    _f("Delay", KIND_INT, "pda.repeat.delay"),
    _f("DelayAdd", KIND_INT, "pda.repeat.delay_add"),
    _f("NoReminder", KIND_BOOL, "pda.repeat.no_reminder"),
)

# ChapterActivation : entree de la liste -- le Check y est le plus souvent
# ABSENT (= activation par proximite de POI implicite, 583 cas sur 591) ;
# champs observes confirmes.
ACTIVATION_FIELDS: Tuple[FieldSpec, ...] = (
    _f("Check", KIND_TEXT, "pda.activation.check", tooltip_key="pda.activation.check.tooltip"),
    _f("Names", KIND_NAMES, "pda.field.names_poi", pool=POOL_POI),
    _f("Types", KIND_TYPES, "pda.field.types_block", pool=POOL_BLOCK),
    _f("Amount", KIND_INT, "pda.field.amount"),
    _f("Value", KIND_INT, "pda.field.value_option"),
    _f("TriggerDistance", KIND_INT, "pda.field.trigger_distance", default="100"),
    _f("GuidingDistance", KIND_INT, "pda.field.guiding_distance", default="-1"),
    _f("NoSkip", KIND_BOOL, "pda.chapter.noskip"),
    _f("PopupActivatesChapter", KIND_BOOL, "pda.activation.popup_activates"),
    _f("NotifyMessage", KIND_TOKEN, "pda.activation.notify_message"),
    _f("MessageTime", KIND_INT, "pda.activation.message_time"),
    _f("Required", KIND_BOOL, "pda.field.required"),
    _f("NamesRequired", KIND_BOOL, "pda.field.names_required"),
)


@dataclass(frozen=True)
class RewardSpec:
    """Une ligne de Rewards : Item+Count[+Meta] OU Type+Count[+Faction[+Meta]]
    -- formes confirmees sur les 3 fichiers (voir cartographie)."""
    kind: str = "Item"          # 'Item' ou 'Type'
    item_name: str = ""         # si kind == 'Item' (pool POOL_ITEM)
    reward_type: str = "XP"     # si kind == 'Type' (enum REWARD_TYPES)
    count: int = 1
    faction: str = ""           # 'Type: Reputation' uniquement (liste a 1 valeur)
    meta: str = ""


# Pools statiques (completes a l'execution par les valeurs du fichier ouvert,
# voir suggestions.py -- un pool est TOUJOURS la fusion statique + fichier).
STATIC_POOLS: Dict[str, Tuple[str, ...]] = {
    POOL_WINDOW: KNOWN_WINDOWS,
    POOL_STAR_CLASS: KNOWN_STAR_CLASSES,
    POOL_PLAYFIELD_TYPE: ("StartPlanet", "Moon", "Orbit", "SunOrbit", "Asteroid Field",
                          "Space Asteroid Field", "Space Warp Target", "Deep Space"),
    POOL_BIOME: ("Water", "Sandstorm", "Rain", "Snow", "MeteorFire", "Radioactive", "Heat"),
    POOL_FACTION: ("Talon", "Polaris", "Pirates", "Trader", "UCH", "Abyssal", "Colonists",
                   "Zirax", "Tesch", "Farr", "Xenu", "Ghyst", "PrennFederation", "Ereon"),
}
