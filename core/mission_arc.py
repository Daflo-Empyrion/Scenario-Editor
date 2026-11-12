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

"""Missions narratives « Anomalie » : chapitres PDA ecrits par une passe
idempotente, meme contrat que `core/tech_milestones.py`.

Plan et couverture moteur : `docs/plan_missions_moteur_v2.md`. Chaque mission
declare les leviers qu'elle exerce (compte a rebours HUD, vagues, effets de
statut, recompenses de largage...). Les textes sont des JETONS
(`pda_<id><Suffixe>`) : le YAML ne porte que le jeton, le CSV porte EN + FR
(colonne 4 = francais, la 3 est l'allemand).

Regle de tenue : aucune ecriture a la main dans `PDA.yaml` — on modifie
`MISSIONS` puis on relance la passe (idempotente par cle de chapitre).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.ai_realism import read_text_raw, write_text_raw

PDA_YAML = "Extras/PDA/PDA.yaml"
PDA_CSV = "Extras/PDA/PDA.csv"
# Chaine « Anomalie » DESACTIVEE (12/12) : la planete de depart a deja
# ses missions, on ne surcharge pas le starter. Contenu conserve dans
# MISSIONS pour la reprise APRES le decollage ; repasser a True reecrit
# les chapitres, a False les retire (PDA + CSV).
MISSION_ARC = False

# Une mission = un chapitre. Champs reconnus :
#   id            identifiant court, sert aux jetons (pda_Ano1Title...)
#   title/desc    (EN, FR)
#   activation    None ou dict(check, names, notify, message_time)
#                 ex. check="DayNightChange", names=["Sunset"]
#   tasks         tuple de dicts : title (EN, FR), actions (tuple)
#   rewards       tuple de dicts : {"type": "XP"|"UP"|"Item"|"Reputation",
#                 "count": n, "item": nom, "faction": nom}
#   done          (EN, FR) message de validation
#   sound         piste `CompletedSound` (optionnel)
#   ops           dict {"OnCompletePlayfieldOps": [...]} recopie tel quel
# Une action : title (EN, FR), desc (EN, FR), check, names, types, amount,
#   set_timer/timer_rate, trigger_distance, guiding_distance, invisible,
#   manual, optional
MISSIONS: Tuple[Dict, ...] = (
    {
        "id": "Ano1",
        "title": ("RE2-FR - Anomaly I: the hatch",
                  "RE2-FR - Anomalie I : le sas"),
        "desc": ("A sealed hatch on the mine's north face. The lock is dead, "
                 "but the purge cycle is not.",
                 "Un sas scelle sur la face nord de la mine. La serrure est "
                 "morte, mais le cycle de purge, non."),
        "preamble": (
            "The blast door of the gallery closes behind you with a sound you "
            "feel in your teeth. Somewhere above, a pump starts counting down. "
            "You have ten minutes of air in this section — take what the "
            "colonists left and find the way out.",
            "Le rideau de fer de la galerie se referme derriere toi avec un "
            "bruit que tu sens dans tes dents. Quelque part au-dessus, une "
            "pompe commence a compter. Tu as dix minutes d'air dans cette "
            "section — prends ce que les colons ont laisse et trouve la "
            "sortie."),
        "activation": {"check": "NearPoi", "names": ["ConflictStarterMine"],
                       "trigger_distance": 120,
                       "notify": "pda_Ano1Notify", "message_time": 20},
        "notify_text": ("Radio: the mine hatch just sealed behind you.",
                        "Radio : le sas de la mine vient de se refermer "
                        "derriere toi."),
        "tasks": (
            {"title": ("Reach the sealed gallery", "Atteindre la galerie scellee"),
             "actions": ({"title": ("Go down into the mine",
                                    "Descends dans la mine"),
                          "desc": ("The entrance is on the north face, past "
                                   "the collapsed winch.",
                                   "L'entree est sur la face nord, apres le "
                                   "treuil effondre."),
                          "check": "NearPoi", "names": ["ConflictStarterMine"],
                          "trigger_distance": 60},)},
            # Pas de « serrure » dans Empyrion et le noyau empeche la
            # recuperation au multi-outil : la seule action reelle est de
            # detruire le CoreNPC de la mine (idiome vanilla `BlockDestroyed`
            # avec `Names: [<POI>]` + `Types: [CoreNPC]`, cf. chapitres RE2).
            {"title": ("Kill the core", "Eteindre le noyau"),
             "actions": ({"title": ("Destroy the mine core",
                                    "Detruis le noyau de la mine"),
                          "desc": ("The core feeds the purge and locks the "
                                   "salvage: take it out.",
                                   "Le noyau alimente la purge et verrouille "
                                   "la recuperation : detruis-le."),
                          "check": "BlockDestroyed",
                          "names": ["ConflictStarterMine"],
                          "types": ["CoreNPC"], "amount": 1},)},
            {"title": ("Get out before the purge", "Sortir avant la purge"),
             "actions": ({"title": ("Ten minutes of air", "Dix minutes d'air"),
                          "desc": ("The purge is counting down in your HUD.",
                                   "La purge s'egrene dans ton HUD."),
                          "set_timer": 600, "timer_rate": 1,
                          "manual": False},
                         {"title": ("Bring back 50 iron",
                                    "Rapporte 50 fer"),
                          "desc": ("The vein is under the collapsed walkway.",
                                   "Le filon est sous la passerelle effondree."),
                          "check": "ItemsPickedUp", "types": ["IronOre"],
                          "amount": 50},)},
        ),
        "rewards": ({"type": "XP", "count": 80},
                    {"type": "Item", "item": "Token", "count": 1,
                     "meta": 4001}),
        "done": ("The hatch gives way and the pump falls silent. Someone will "
                 "want this keycard back.",
                 "Le sas cede et la pompe se tait. Quelqu'un voudra recuperer "
                 "cette carte."),
        "sound": "Sounds/Misc/DroneSignalBad",
    },
)


def _token(ms: Dict, suffixe: str) -> str:
    return "pda_" + ms["id"] + suffixe


def _txt(v) -> str:
    return v[0] if isinstance(v, (tuple, list)) else str(v)


def _action(ms: Dict, i: int, a: Dict) -> str:
    out = ["          - ActionTitle: " + _token(ms, "A%dT" % i),
           "            Description: " + _token(ms, "A%dD" % i)]
    if a.get("check"):
        out.append("            Check: " + a["check"])
    for champ, cle in (("names", "Names"), ("types", "Types")):
        if a.get(champ):
            out.append("            " + cle + ":")
            out += ["              - " + v for v in a[champ]]
    if a.get("amount"):
        out.append("            Amount: " + str(a["amount"]))
    # SetTimer = duree en SECONDES, decrementee de TimerRate toutes les
    # TimerRate secondes ; l'action se complete quand le compteur atteint 0
    # (action minuteur : CompletedFloatAmount / NotifyIncrementDecrement...).
    if a.get("set_timer"):
        out.append("            SetTimer: " + str(a["set_timer"]))
        out.append("            TimerRate: " + str(a.get("timer_rate", 1)))
    if a.get("trigger_distance"):
        out.append("            TriggerDistance: " + str(a["trigger_distance"]))
    if a.get("guiding_distance"):
        out.append("            GuidingDistance: " + str(a["guiding_distance"]))
    for drapeau, cle in (("invisible", "IsInvisible"),
                          ("manual", "AllowManualCompletion"),
                          ("optional", "IsOptional")):
        if a.get(drapeau):
            out.append("            " + cle + ": true")
    return "\n".join(out) + "\n"


def _chapter(ms: Dict) -> str:
    act = ms.get("activation") or {}
    out = ["  - ChapterTitle: " + _token(ms, "Title"),
           "    Category: SoloMission",
           "    NoSkip: true",
           "    Activatable: " + ms.get("activatable", "Always"),
           "    Visibility: " + ms.get("visibility", "Always"),
           "    PlayerLevel: 1",
           "    Description: " + _token(ms, "Desc")]
    if ms.get("prereq"):
        out.append("    RewardedChapters:")
        out.append("      - " + ms["prereq"])
    if act:
        # `ChapterActivation:` est une SEQUENCE (une ou plusieurs activations) :
        # un mapping fait jeter YamlDotNet « Expected 'SequenceStart', got
        # 'MappingStart' » et le PDA n'est plus charge du tout (vecu 12/11).
        out.append("    ChapterActivation:")
        out.append("      - Check: " + act["check"])
        if act.get("names"):
            out.append("        Names:")
            out += ["          - " + v for v in act["names"]]
        if act.get("types"):
            out.append("        Types:")
            out += ["          - " + v for v in act["types"]]
        if act.get("amount"):
            out.append("        Amount: " + str(act["amount"]))
        if act.get("trigger_distance"):
            out.append("        TriggerDistance: " + str(act["trigger_distance"]))
        if act.get("notify"):
            out.append("        NotifyMessage: " + act["notify"])
        if act.get("message_time"):
            out.append("        MessageTime: " + str(act["message_time"]))
    if ms.get("preamble"):
        # `Preamble` ne s'affiche que si StartMessage est vide ou commence par
        # `mbox` : briefing plein ecran.
        out.append("    Preamble: " + _token(ms, "Pre"))
    out.append("    Tasks:")
    for i, t in enumerate(ms.get("tasks") or (), 1):
        out.append("      - TaskTitle: " + _token(ms, "T%d" % i))
        out.append("        Actions:")
        for j, a in enumerate(t.get("actions") or (), 1):
            out.append(_action(ms, (i - 1) * 10 + j, a).rstrip("\n"))
    if ms.get("ops"):
        for cle, lignes in ms["ops"].items():
            out.append("    " + cle + ":")
            out += ["      - " + l for l in lignes]
    if ms.get("rewards"):
        out.append("    Rewards:")
        for r in ms["rewards"]:
            out.append("      - Type: " + r["type"])
            if r.get("count"):
                out.append("        Count: " + str(r["count"]))
            if r.get("item"):
                out.append("        Item: " + r["item"])
            if r.get("meta"):
                out.append("        Meta: " + str(r["meta"]))
            if r.get("faction"):
                out.append("        Faction:")
                out.append("          - " + r["faction"])
    if ms.get("sound"):
        out.append("    CompletedSound: " + ms["sound"])
    out.append("    CompletedMessage: norm;25|" + _token(ms, "Done"))
    return "\n".join(out) + "\n"


def _yaml_parse_ok(texte: str) -> bool:
    """Le texte reste-t-il un YAML lisible ?

    PyYAML quand il est disponible (validation stricte, poste de dev) ; sinon
    le parseur maison `core.yamllite`, qui est celui de l'application. Une
    dependance absente ne doit JAMAIS decider si la passe ecrit : vecu CI
    12/11, `import yaml` levait ModuleNotFoundError, la fonction repondait
    False et la passe se bloquait sur « YAML invalide apres ajout : abandon »
    alors que le fichier etait bon.

    shortcut: sans PyYAML la validation est structurelle (le texte se relit),
    pas syntaxique -- suffisant pour une insertion de bloc, revoir si la passe
    se met a produire des valeurs complexes.
    """
    try:
        import yaml
    except ImportError:
        yaml = None
    if yaml is not None:
        try:
            yaml.safe_load(texte)
            return True
        except Exception:                   # noqa: BLE001 - validation souple
            return False
    try:
        from core.yamllite.parser import parse_yaml_text
        return bool(parse_yaml_text(texte).nodes)
    except Exception:                       # noqa: BLE001 - validation souple
        return False


def _rows(ms: Dict) -> List[Tuple[str, str, str]]:
    """(cle, anglais, francais) pour tous les jetons de la mission."""
    lignes = [(_token(ms, "Title"), *_paire(ms["title"])),
              (_token(ms, "Desc"), *_paire(ms["desc"])),
              (_token(ms, "Done"), *_paire(ms.get("done", ("", ""))))]
    if (ms.get("activation") or {}).get("notify"):
        lignes.append((_token(ms, "Notify"), *_paire(ms.get("notify_text", ("", "")))))
    if ms.get("preamble"):
        lignes.append((_token(ms, "Pre"), *_paire(ms["preamble"])))
    for i, t in enumerate(ms.get("tasks") or (), 1):
        lignes.append((_token(ms, "T%d" % i), *_paire(t["title"])))
        for j, a in enumerate(t.get("actions") or (), 1):
            n = (i - 1) * 10 + j
            lignes.append((_token(ms, "A%dT" % n), *_paire(a["title"])))
            lignes.append((_token(ms, "A%dD" % n), *_paire(a.get("desc", a["title"]))))
    return lignes


def _paire(v) -> Tuple[str, str]:
    if isinstance(v, (tuple, list)) and len(v) >= 2:
        return str(v[0]), str(v[1])
    return str(v), str(v)


def _csv_ligne(cle: str, anglais: str, francais: str) -> str:
    def esc(v: str) -> str:
        return '"' + v.replace('"', '""') + '"' if "," in v or '"' in v else v
    return ",".join([cle, esc(anglais), "", esc(francais)] + [""] * 14)


def _ensure_chapter(texte: str, ms: Dict) -> Tuple[str, int]:
    """Remplace le chapitre s'il differe de la version courante (mise a jour
    automatique quand `MISSIONS` change), l'ajoute sinon en fin de liste."""
    bloc = _chapter(ms)
    entete = "  - ChapterTitle: " + _token(ms, "Title")
    pat = re.compile(r"(?m)^" + re.escape(entete) + r"[ \t]*$.*?"
                     r"(?=^  - ChapterTitle:|^Chapters:|^[A-Za-z_]|\Z)", re.S)
    m = pat.search(texte)
    if m is not None:
        if m.group(0).rstrip() == bloc.rstrip():
            return texte, 0
        return texte[:m.start()] + bloc + texte[m.end():], 1
    ancre = re.search(r"(?m)^Chapters:", texte)
    if ancre is None:
        return texte, 0
    # fin du bloc : premiere cle de niveau 0 apres `Chapters:` (nos missions se
    # rangent APRES les chapitres existants, la chaine narrative reste lisible)
    fin = re.search(r"(?m)^[A-Za-z_]", texte[ancre.end():])
    pos = ancre.end() + fin.start() if fin else len(texte)
    return texte[:pos].rstrip("\n") + "\n\n" + bloc + "\n" + texte[pos:], 1


def _strip_chapters(texte: str, prefixe: str = "pda_Ano") -> Tuple[str, int]:
    """Retire nos chapitres (par prefixe de jeton) et leurs lignes CSV.

    Utilise quand la chaine est DESACTIVEE : sans ca, couper `MISSION_ARC`
    laisserait le chapitre deja pose dans le PDA (surcharge inutile de la
    planete de depart)."""
    n = 0
    while True:
        m = re.search(r"(?m)^  - ChapterTitle: " + re.escape(prefixe)
                      + r"\w*[ \t]*$.*?(?=^  - ChapterTitle:|^Chapters:"
                      r"|^[A-Za-z_]|\Z)", texte, re.S)
        if m is None:
            return texte, n
        texte = (texte[:m.start()] + texte[m.end():]).replace("\n\n\n", "\n\n")
        n += 1


def pass_mission_arc(scenario: Path, apply: bool = False, store=None) -> dict:
    """Insere / met a jour les chapitres des missions « Anomalie » ; les retire
    quand la chaine est desactivee. Idempotent : 2e passage = 0 edition."""
    rep = {"id": "mission_arc", "edits": 0, "files": 0, "details": []}
    yaml_path = Path(scenario) / PDA_YAML
    csv_path = Path(scenario) / PDA_CSV
    actif = MISSION_ARC and bool(MISSIONS)
    if not actif:
        if not yaml_path.is_file() or not csv_path.is_file():
            rep["details"].append("chaine desactivee (PDA absent)")
            return rep
        texte, eol = read_text_raw(yaml_path)
        csv_texte, csv_eol = read_text_raw(csv_path)
        nouveau, n_yaml = _strip_chapters(texte)
        lignes = csv_texte.split("\n")
        gardees = [l for l in lignes if not l.startswith("pda_Ano")]
        n_csv = len(lignes) - len(gardees)
        if not (n_yaml or n_csv):
            rep["details"].append("chaine desactivee : rien a retirer")
            return rep
        if apply:
            if store:
                store.snapshot(yaml_path)
                store.snapshot(csv_path)
            write_text_raw(yaml_path, nouveau, eol)
            write_text_raw(csv_path, "\n".join(gardees), csv_eol)
            rep["files"] = 2
        rep["edits"] = n_yaml + n_csv
        rep["details"].append(
            "chaine desactivee : %d chapitre(s), %d ligne(s) CSV retires"
            % (n_yaml, n_csv))
        return rep
    if not yaml_path.is_file() or not csv_path.is_file():
        rep["details"].append("PDA.yaml ou PDA.csv absent")
        return rep
    texte, eol = read_text_raw(yaml_path)
    csv_texte, csv_eol = read_text_raw(csv_path)

    nouveau, n_yaml = texte, 0
    for ms in MISSIONS:
        nouveau, k = _ensure_chapter(nouveau, ms)
        n_yaml += k
    if n_yaml and not _yaml_parse_ok(nouveau):
        rep["details"].append("YAML invalide apres ajout : abandon")
        return rep

    deja = {ligne.split(",", 1)[0] for ligne in csv_texte.split("\n") if ligne}
    manquantes = [(c, en, fr) for ms in MISSIONS for c, en, fr in _rows(ms)
                  if c not in deja]
    if not (n_yaml or manquantes):
        return rep
    if apply:
        if store:
            store.snapshot(yaml_path)
            store.snapshot(csv_path)
        if n_yaml:
            write_text_raw(yaml_path, nouveau, eol)
            rep["files"] += 1
        if manquantes:
            final = csv_texte.rstrip("\n") + "\n"
            final += "\n".join(_csv_ligne(c, en, fr) for c, en, fr in manquantes) + "\n"
            write_text_raw(csv_path, final, csv_eol)
            rep["files"] += 1
    rep["edits"] = n_yaml + len(manquantes)
    rep["details"].append(
        "chapitres %d, lignes CSV %d" % (n_yaml, len(manquantes)))
    return rep
