# -*- coding: utf-8 -*-
"""Injecte les infobulles PDA (basees sur le guide officiel
Create-own-Missions) dans data/i18n_strings.json -- FR/EN, une cle
<pda.X.Y>.tooltip par champ du schema core/pda/schema.py."""
import json
from pathlib import Path

T = {
    # ---------------- chapitre ----------------
    "pda.chapter.category.tooltip": (
        "Onglet du PDA où le chapitre apparaît : FactionMission, SoloMission, "
        "Tutorial ou Knowledgebase.",
        "Which PDA tab the chapter appears in: FactionMission, SoloMission, "
        "Tutorial or Knowledgebase."),
    "pda.chapter.noskip.tooltip": (
        "Coché : le joueur ne peut PAS passer/sauter ce chapitre.",
        "Checked: the player CANNOT skip this chapter."),
    "pda.chapter.activatable.tooltip": (
        "Définit quand le chapitre peut être activé par le joueur "
        "(Always : à tout moment).",
        "Defines when the chapter can be activated by the player "
        "(Always: at any time)."),
    "pda.chapter.visibility.tooltip": (
        "Quand le chapitre est visible dans la liste du PDA : Always (toujours), "
        "ByLevel (à partir d'un niveau), WhenRewarded (une fois le chapitre "
        "précédent terminé). ATTENTION : pour WhenRewarded, l'ORDRE des "
        "chapitres dans le PDA.yaml décrit la progression.",
        "When the chapter shows in the PDA list: Always, ByLevel (from a given "
        "level), WhenRewarded (after the previous chapter is completed). NOTE: "
        "for WhenRewarded, the ORDER of chapters in PDA.yaml defines the flow."),
    "pda.chapter.player_level.tooltip": (
        "Niveau minimum du joueur pour pouvoir ACTIVER ce chapitre.",
        "Minimum player level required to ACTIVATE this chapter."),
    "pda.chapter.group.tooltip": (
        "Nom de groupe : regroupe plusieurs chapitres sous une même entrée "
        "du PDA.",
        "Group name: gathers several chapters under one PDA entry."),
    "pda.chapter.hide_tasks.tooltip": (
        "Coché : la liste des tâches est masquée dans le détail du chapitre.",
        "Checked: the task list is hidden in the chapter detail view."),
    "pda.chapter.description.tooltip": (
        "Description affichée dans l'écran de détail du chapitre (visible en "
        "cliquant sur son titre dans le PDA). Champ localisé : la valeur est "
        "un jeton traduit dans le PDA.csv.",
        "Description shown in the chapter detail screen (visible when clicking "
        "its title in the PDA). Localized field: the value is a token "
        "translated in PDA.csv."),
    "pda.chapter.start_message.tooltip": (
        "Message affiché au joueur quand le chapitre démarre. $ = message par "
        "défaut du jeu.",
        "Message shown to the player when the chapter starts. $ = game default."),
    "pda.chapter.completed_message.tooltip": (
        "Message de fin de chapitre. $ = message par défaut du jeu "
        "(« You successfully completed '<titre>' »). Une valeur est "
        "nécessaire pour que la mission fonctionne.",
        "Chapter completion message. $ = game default (\"You successfully "
        "completed '<title>'\"). A value is required for the mission to run."),
    "pda.chapter.skip_message.tooltip": (
        "Message affiché si le joueur passe (skip) ce chapitre.",
        "Message shown if the player skips this chapter."),
    "pda.chapter.faction.tooltip": (
        "Faction de référence du chapitre (utilisée avec le niveau de "
        "réputation).",
        "Reference faction of the chapter (used with the reputation level)."),
    "pda.chapter.reputation_level.tooltip": (
        "Niveau de réputation requis auprès de la faction pour ce chapitre.",
        "Reputation level required with the faction for this chapter."),
    "pda.chapter.picture.tooltip": (
        "Image affichée dans l'écran de détail. Le fichier doit se trouver "
        "dans Content/Extras/PDA du jeu.",
        "Picture shown in the detail screen. The file must be located in the "
        "game's Content/Extras/PDA folder."),
    "pda.chapter.auto_activate.tooltip": (
        "Coché : le chapitre s'active automatiquement au démarrage de la "
        "partie.",
        "Checked: the chapter activates automatically when the game starts."),
    "pda.chapter.activate_on_completion.tooltip": (
        "Chapitre activé AUTOMATIQUEMENT quand celui-ci est terminé (les "
        "conditions comme le niveau restent vérifiées).",
        "Chapter activated AUTOMATICALLY when this one is completed "
        "(conditions like player level are still checked)."),
    "pda.chapter.activate_on_skip.tooltip": (
        "Chapitre activé si le joueur passe (skip) celui-ci.",
        "Chapter activated if the player skips this one."),
    "pda.chapter.playfields.tooltip": (
        "Chapitre limité à ces playfields précis (vide = tous).",
        "Chapter restricted to these exact playfields (empty = all)."),
    "pda.chapter.playfield_types.tooltip": (
        "Chapitre limité à ces TYPES de playfields (planète, lune, espace...).",
        "Chapter restricted to these playfield TYPES (planet, moon, space...)."),
    "pda.chapter.visible_on_start.tooltip": (
        "Visible au démarrage de la partie uniquement sur ces playfields.",
        "Visible at game start only on these playfields."),
    "pda.chapter.visible_on_start_types.tooltip": (
        "Visible au démarrage uniquement sur ces types de playfields.",
        "Visible at game start only on these playfield types."),
    "pda.chapter.player_credits.tooltip": (
        "Crédits versés au joueur à la complétion du chapitre (récompense "
        "alternative/ajoutée aux items).",
        "Credits granted to the player on chapter completion (reward on top "
        "of items)."),
    # ---------------- tache ----------------
    "pda.task.headline.tooltip": (
        "Titre de la tâche : affiché au-dessus de la liste d'actions dans le "
        "HUD et en sous-titre du chapitre dans le PDA. Maximum ~26 caractères "
        "(au-delà, retour à la ligne moche dans le HUD).",
        "Task title: shown above the HUD action list and as the chapter "
        "sub-header in the PDA. Max ~26 characters (longer text wraps badly "
        "in the HUD)."),
    "pda.task.start_delay.tooltip": (
        "Délai (secondes) avant que la tâche ne démarre après son activation.",
        "Delay (seconds) before this task starts after activation."),
    "pda.task.unique_items.tooltip": (
        "Coché : les items de la tâche sont uniques (ne peuvent être "
        "fournis/réutilisés par ailleurs).",
        "Checked: the task's items are unique (cannot be provided/reused "
        "elsewhere)."),
    "pda.task.only_visible_rewarded.tooltip": (
        "Coché : la tâche n'est visible que lorsque la tâche/chapitre "
        "précédent a été récompensé.",
        "Checked: the task is only visible once the previous task/chapter "
        "has been rewarded."),
    "pda.task.on_activate_signal.tooltip": (
        "Signal de POI déclenché quand la tâche s'ACTIVE (utilise * comme "
        "joker dans les blueprints de POI).",
        "POI signal fired when the task ACTIVATES (use * as wildcard in POI "
        "blueprints)."),
    "pda.task.on_complete_signal.tooltip": (
        "Signal de POI déclenché quand la tâche est TERMINÉE.",
        "POI signal fired when the task is COMPLETED."),
    "pda.task.rewarded_tasks.tooltip": (
        "Tâches marquées comme récompensées quand celle-ci est terminée.",
        "Tasks marked as rewarded when this one completes."),
    "pda.task.rewarded_chapters.tooltip": (
        "Chapitres marqués comme récompensés quand cette tâche est terminée.",
        "Chapters marked as rewarded when this task completes."),
    # ---------------- action / champs communs ----------------
    "pda.field.description.tooltip": (
        "Description détaillée de l'action, affichée à droite de l'écran de "
        "détail du PDA. Champ localisé (jeton PDA.csv).",
        "Detailed action description, shown on the right of the PDA detail "
        "screen. Localized field (PDA.csv token)."),
    "pda.field.completed_message.tooltip": (
        "OBLIGATOIRE. $ = message par défaut (« You successfully completed "
        "'<titre>' ») ; remplace le $ par ton propre texte si besoin.",
        "REQUIRED. $ = default message (\"You successfully completed "
        "'<title>'\"); replace the $ with your own text if needed."),
    "pda.field.allow_manual.tooltip": (
        "Coché : le joueur peut cocher lui-même la case de l'action dans le "
        "PDA pour la terminer manuellement. Décoché = complétion automatique "
        "uniquement.",
        "Checked: the player can tick the action's checkbox in the PDA to "
        "complete it manually. Unchecked = automatic completion only."),
    "pda.field.is_ordered.tooltip": (
        "Coché : les tâches de ce chapitre doivent être accomplies dans "
        "l'ordre du fichier.",
        "Checked: this chapter's tasks must be completed in file order."),
    "pda.field.is_optional.tooltip": (
        "Coché : la tâche/l'action est optionnelle pour terminer le "
        "chapitre/la tâche.",
        "Checked: the task/action is optional to complete the chapter/task."),
    "pda.field.required.tooltip": (
        "S'applique aux TYPES : coché = TOUS les types listés sont requis "
        "(NeedAll) ; décoché = un seul suffit (NeedOne).",
        "Applies to TYPES: checked = ALL listed types are required (NeedAll); "
        "unchecked = any single one is enough (NeedOne)."),
    "pda.field.names_required.tooltip": (
        "S'applique aux NAMES : coché = TOUS les emplacements listés sont "
        "concernés (NeedAll) ; décoché = un seul suffit (NeedOne).",
        "Applies to NAMES: checked = ALL listed locations apply (NeedAll); "
        "unchecked = any single one is enough (NeedOne)."),
    "pda.field.amount.tooltip": (
        "Quantité d'éléments (NAMES ou TYPES) nécessaire pour compléter "
        "l'action.",
        "How many of the listed NAMES or TYPES are needed to complete the "
        "action."),
    "pda.field.amount_kills.tooltip": (
        "Nombre d'unités à éliminer pour compléter l'action.",
        "Number of units to kill to complete the action."),
    "pda.field.amount_seconds.tooltip": (
        "Durée en secondes (attente/écoute) pour compléter l'action.",
        "Duration in seconds (wait/listen) to complete the action."),
    "pda.field.comment.tooltip": (
        "Note interne : non utilisée par le jeu, pour toi/ton équipe.",
        "Internal note: ignored by the game, for you/your team."),
    "pda.field.trigger_distance.tooltip": (
        "Distance (en mètres) de déclenchement du Check de proximité.",
        "Distance (meters) at which the proximity Check triggers."),
    "pda.field.guiding_distance.tooltip": (
        "Distance (mètres) à laquelle le guidage/waypoint s'affiche "
        "(-1 = désactivé).",
        "Distance (meters) at which the guiding/waypoint shows (-1 = off)."),
    "pda.field.guiding.tooltip": (
        "Mode de guidage du joueur vers l'objectif (waypoint, direction...).",
        "Player guiding mode towards the objective (waypoint, direction...)."),
    "pda.field.value_option.tooltip": (
        "Numéro de l'option de dialogue concernée (1 = première option).",
        "Number of the targeted dialog option (1 = first option)."),
    # ---------------- NAMES / TYPES (WHERE / WHAT) ----------------
    "pda.field.names_poi.tooltip": (
        "NAMES = OÙ : POI (base, installation) concerné par le Check.",
        "NAMES = WHERE: the POI (base, structure) targeted by the Check."),
    "pda.field.names_unit.tooltip": (
        "NAMES = OÙ/QUI : entité concernée (NPC, créature, drone...).",
        "NAMES = WHERE/WHO: the entity involved (NPC, creature, drone...)."),
    "pda.field.names_targets.tooltip": (
        "NAMES = CIBLES : entités à atteindre/éliminer pour le Check.",
        "NAMES = TARGETS: entities to reach/eliminate for the Check."),
    "pda.field.names_device.tooltip": (
        "NAMES = le dispositif concerné par le Check.",
        "NAMES = the device involved in the Check."),
    "pda.field.names_signal.tooltip": (
        "Nom du SIGNAL (utilise * comme joker dans les blueprints de POI).",
        "SIGNAL name (use * as wildcard in POI blueprints)."),
    "pda.field.names_playfield.tooltip": (
        "NAMES = OÙ : playfield (planète/lune/espace) concerné.",
        "NAMES = WHERE: the playfield (planet/moon/space) involved."),
    "pda.field.names_pf_type.tooltip": (
        "Type de playfield concerné (planète, lune, espace).",
        "Playfield type involved (planet, moon, space)."),
    "pda.field.names_biome.tooltip": (
        "Biome concerné par le Check (désert, neige...).",
        "Biome the Check applies to (desert, snow...)."),
    "pda.field.names_star_class.tooltip": (
        "Classe spectrale de l'étoile du système concerné.",
        "Spectral class of the system's star."),
    "pda.field.names_structure.tooltip": (
        "Structure (vaisseau/base avec bloc de démarrage) concernée.",
        "Structure (vessel/base with starter block) involved."),
    "pda.field.names_dialog.tooltip": (
        "Dialogue/NPC dont l'option est surveillée par le Check.",
        "Dialog/NPC whose option is watched by the Check."),
    "pda.field.names_item.tooltip": (
        "Item concerné par le Check (inventaire, fabrication...).",
        "Item involved in the Check (inventory, crafting...)."),
    "pda.field.names_optional.tooltip": (
        "NAMES optionnels : complètent le Check sans être obligatoires.",
        "Optional NAMES: complete the Check without being mandatory."),
    "pda.field.names_window.tooltip": (
        "Fenêtre/écran du PDA concerné par le Check.",
        "PDA window/screen the Check applies to."),
    "pda.field.types_block.tooltip": (
        "TYPES = QUOI : bloc concerné (poser, détruire, récolter...).",
        "TYPES = WHAT: the block involved (place, destroy, mine...)."),
    "pda.field.types_item.tooltip": (
        "TYPES = QUOI : item à posséder/fabriquer/consommer.",
        "TYPES = WHAT: item to own/craft/consume."),
    "pda.field.types_plant.tooltip": (
        "TYPES = QUOI : plante à récolter.",
        "TYPES = WHAT: plant to harvest."),
    "pda.field.types_resource.tooltip": (
        "TYPES = QUOI : ressource à découvrir/être à proximité.",
        "TYPES = WHAT: resource to discover/be near."),
    # ---------------- activation / repeat ----------------
    "pda.activation.check.tooltip": (
        "Condition (Check) qui active automatiquement ce chapitre/activité "
        "quand elle est remplie par le joueur.",
        "Condition (Check) that auto-activates this chapter/activity when "
        "the player fulfills it."),
    "pda.activation.popup_activates.tooltip": (
        "Coché : la popup d'information active le chapitre quand le joueur "
        "la ferme.",
        "Checked: the info popup activates the chapter when the player "
        "closes it."),
    "pda.activation.notify_message.tooltip": (
        "Message de notification affiché à l'écran (jeton PDA.csv).",
        "Notification message shown on screen (PDA.csv token)."),
    "pda.activation.message_time.tooltip": (
        "Durée d'affichage de la notification (secondes).",
        "How long the notification stays on screen (seconds)."),
    "pda.repeat.num_repeats.tooltip": (
        "Nombre de répétitions du rappel/activité.",
        "How many times the reminder/activity repeats."),
    "pda.repeat.delay_seconds.tooltip": (
        "Délai en secondes entre deux répétitions.",
        "Delay in seconds between repeats."),
    "pda.repeat.delay.tooltip": (
        "Délai (unité jeu) avant la première répétition.",
        "Delay (game unit) before the first repeat."),
    "pda.repeat.delay_add.tooltip": (
        "Temps ajouté à chaque répétition au délai précédent.",
        "Time added to the previous delay on every repeat."),
    "pda.repeat.no_reminder.tooltip": (
        "Coché : pas de rappel à l'écran pour cette entrée.",
        "Checked: no on-screen reminder for this entry."),
}

path = Path(__file__).resolve().parent.parent / "data" / "i18n_strings.json"
data = json.loads(path.read_text(encoding="utf-8"))
added = 0
for key, (fr, en) in T.items():
    if key in data:
        continue
    data[key] = {"fr": fr, "en": en}
    added += 1
path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n",
                encoding="utf-8")
print(f"{added} infobulles ajoutees (sur {len(T)} prevues)")
