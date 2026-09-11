# -*- coding: utf-8 -*-
"""Injecte les messages de validation PDA (core/pda/validation.py) dans
data/i18n_strings.json."""
import json
from pathlib import Path

T = {
    "pda.val.no_completed_message": (
        "CompletedMessage manquant : obligatoire pour que la mission "
        "fonctionne ($ = message par défaut du jeu).",
        "Missing CompletedMessage: required for the mission to run "
        "($ = game default message)."),
    "pda.val.multiple_checks": (
        "Plusieurs clés Check sur la même action : le jeu n'en lit qu'une "
        "(une seule condition par action).",
        "Several Check keys on the same action: the game reads only one "
        "(one condition per action)."),
    "pda.val.needs_names_or_types": (
        "Le Check {check} exige au moins un NAMES (où) ou un TYPES (quoi).",
        "The {check} check requires at least one NAMES (where) or TYPES "
        "(what)."),
    "pda.val.needs_names": (
        "Le Check {check} exige au moins un NAMES (où / sur quoi).",
        "The {check} check requires at least one NAMES (where / what)."),
    "pda.val.needs_types": (
        "Le Check {check} exige au moins un TYPES (quoi).",
        "The {check} check requires at least one TYPES (what)."),
    "pda.val.unused_names_field": (
        "Names renseigné mais le Check {check} ne l'utilise pas : le jeu "
        "l'ignorera (résidu d'édition ?).",
        "Names is filled but the {check} check ignores it: the game will "
        "not use it (editing leftover?)."),
    "pda.val.unused_types_field": (
        "Types renseigné mais le Check {check} ne l'utilise pas : le jeu "
        "l'ignorera (résidu d'édition ?).",
        "Types is filled but the {check} check ignores it: the game will "
        "not use it (editing leftover?)."),
    "pda.val.when_rewarded_first": (
        "Visibility: WhenRewarded sur le PREMIER chapitre : aucun chapitre "
        "précédent à terminer, il ne sera jamais visible.",
        "Visibility: WhenRewarded on the FIRST chapter: there is no previous "
        "chapter to complete, it will never show."),
    "pda.val.chain_target_missing": (
        "{key} : le chapitre cible « {target} » n'existe pas (titre de "
        "chapitre introuvable dans ce PDA.yaml).",
        "{key}: target chapter \"{target}\" does not exist (chapter title "
        "not found in this PDA.yaml)."),
    "pda.val.token_missing": (
        "Jeton absent du PDA.csv : {token}",
        "Token missing from PDA.csv: {token}"),
    "pda.val.token_orphan": (
        "Jeton orphelin dans le PDA.csv (plus référencé par le YAML) : "
        "{token}",
        "Orphan token in PDA.csv (no longer referenced by the YAML): "
        "{token}"),
    "pda.val.reward_count_over": (
        "Récompense « {item} » : quantité {count} > pile maximale du jeu "
        "({max}). Le guide : ajouter une ligne de récompense "
        "supplémentaire.",
        "Reward \"{item}\": count {count} > game max stack ({max}). The "
        "guide: add another reward line."),
    "pda.val.title_over": (
        "{key} : {n} caractères (max {max}) — le HUD passera à la ligne. "
        "Limite Visible après retrait des balises BBCode.",
        "{key}: {n} characters (max {max}) — the HUD will wrap the line. "
        "Limit applies to visible text after BBCode removal."),
}

path = Path(__file__).resolve().parent.parent / "data" / "i18n_strings.json"
data = json.loads(path.read_text(encoding="utf-8"))
added = 0
for key, (fr, en) in T.items():
    if key in data:
        continue
    data[key] = {"fr": fr, "en": en}
    added += 1
out = json.dumps(data, ensure_ascii=False, indent=1) + "\n"
path.write_bytes(out.replace("\n", "\r\n").encode("utf-8"))
print(f"{added} messages de validation ajoutes (sur {len(T)} prevus)")
