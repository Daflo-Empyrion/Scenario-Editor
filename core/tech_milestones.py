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
"""Jalons technologiques par POI (regime « ressources rares »).

Trois missions PDA qui paient le minerai des mines gardees : fer (toutes),
cobalt (mines de faction), neodyme (mines HOSTILES seulement) — la
progression se gagne donc en prenant des POI, pas en creusant un gisement.

Mecanique verifiee (fiches cerveau pda-minage-types-pas-names,
empyrion-pda-champs-enum) :
- `Check: ItemsPickedUp` compare des TYPES d'objets (`Types: IronOre`), pas
  des Names ; `NamesRequired` est un ENUM (NeedAll/NeedOne) ;
- les recompenses sont `- Type: UP|XP` + `Count` (cf. REWARD_TYPES) ;
- les textes sont des JETONS de localisation (`pda_XXX`) resolus par
  `Extras/PDA/PDA.csv` (colonnes English, Deutsch, Francais...).

Additif et idempotent : chapitres ajoutes en fin de `Chapters:` (avant la
ligne `Creator:`), lignes CSV en fin de fichier, aucune reecriture d'un
chapitre existant ; un marqueur « Jalon » ou une cle deja presente arrete la
passe. Repli : TECH_MILESTONES = False.
"""
import csv as _csv
import io
import re
import tempfile
from pathlib import Path

from core.ai_realism import read_text_raw, write_text_raw

TECH_MILESTONES = True
PDA_YAML = "Extras/PDA/PDA.yaml"
PDA_CSV = "Extras/PDA/PDA.csv"
MARKER = "Jalon "          # present dans les titres FR : garde d'idempotence

# (id de cle, item ramasse, quantite, UP, XP, (titre, resume, texte) FR/EN)
# `done` = message de validation (le jeu n'annonce RIEN sans lui) ;
# `items` = recompense en objets : `(Item, Count)`.
MILESTONES = (
    {"id": "Jal1", "ore": "IronOre", "amount": 200, "up": 3, "xp": 1500,
     "items": (("MultiTool", 1), ("MultiCharge", 250)),
     "done": ("Milestone I complete: +3 unlock points, +1500 XP, and a "
              "Multi-Tool with 250 charges for salvaging POI parts. To keep "
              "going, activate Milestone II in the PDA (F1) > Solo missions.",
              "Jalon I valide : +3 points de deblocage, +1500 XP, plus un "
              "multi-outil et 250 charges pour demonter les pieces des POI. "
              "Pour continuer, active le Jalon II dans le PDA (F1) > "
              "Missions solo."),
     "fr": ("Jalon I - Le premier lingot",
            "Ramassez 200 fer.",
            "Le minerai ne vient plus du sol : il se prend dans les mines "
            "gardees (entrees « Conflict...Mines » sur la carte)."),
     "en": ("Milestone I - The first ingot",
            "Pick up 200 Iron.",
            "Ore no longer grows in the ground: it comes from guarded mines "
            "(the « Conflict...Mines » markers on the map).")},
    {"id": "Jal2", "ore": "CobaltOre", "amount": 150, "up": 5, "xp": 3000,
     "items": (),
     "done": ("Milestone II complete: +5 unlock points and +3000 XP.",
              "Jalon II valide : +5 points de deblocage et +3000 XP."),
     "fr": ("Jalon II - Le cobalt du vaincu",
            "Ramassez 150 cobalt.",
            "Le cobalt n'existe plus que sur les mines de faction : il faut "
            "en chasser les drones."),
     "en": ("Milestone II - Cobalt of the fallen",
            "Pick up 150 Cobalt.",
            "Cobalt now only exists in faction mines: you must fight the "
            "drones to get it.")},
    {"id": "Jal3", "ore": "NeodymiumOre", "amount": 100, "up": 8, "xp": 6000,
     "items": (),
     "done": ("Milestone III complete: +8 unlock points and +6000 XP.",
              "Jalon III valide : +8 points de deblocage et +6000 XP."),
     "fr": ("Jalon III - L'ere du neodyme",
            "Ramassez 100 neodyme.",
            "Le neodyme ne se trouve que sur les mines des factions "
            "HOSTILES : c'est le prix de l'equipement avance."),
     "en": ("Milestone III - The neodymium age",
            "Pick up 100 Neodymium.",
            "Neodymium only spawns in HOSTILE faction mines: that is the "
            "price of advanced gear.")},
)

# ordre des lignes CSV par jalon : (suffixe de cle, indice dans le tuple FR/EN)
_CSV_KEYS = (("Title", 0), ("Desc", 1), ("Task", 0), ("Act", 1), ("Text", 2))

# Chapitre d'accueil, en TETE des chapitres : sans lui, un joueur qui ne lit
# pas la fiche du scenario conclut « plus de ressources = bug ». Il ne
# demande rien (`Check: WindowOpened` sur `Pda` : la tache se valide a la
# premiere ouverture du PDA, donc au moment ou il lit).
INTRO_KEY = "pda_IntroTitle"
# Chapitres de depart et leur PREMIER message : c'est la que la note doit
# arriver. `eden_pda_84WqK` = « Intro: Dread (Dead2) », le vrai prologue du
# depart RE2 (verifie en jeu : premier message « Ow. My head. ») ; le second
# est le prologue UCH d'Empyrion, garde par prudence. Cles du mod, stables ;
# absentes = on saute sans rien casser.
PROLOGUE_MSG = "eden_pda_qWOUGCK"
_NOTE_MSGS = (
    ("eden_pda_qWOUGCK", "Aie. Ma tete. Ou suis-je ? Que s'est-il passe ?"),
    ("pda_mKuKK", "[b][c][00fbff]Prologue : Voyage vers l'inconnu[-][/c][/b]"
                  "\\n\\nTu t'extirpes de l'epave de ta capsule d'evacuation, "
                  "blesse et seul sur un monde inconnu.\\nSans souvenir d'etre "
                  "arrive ici et avec presque rien a ta disposition, le "
                  "gresillement de la radio de ta combinaison te met sur la "
                  "piste de reponses, quelque part dans la nature sauvage de "
                  "cette planete alien."),
)
_MSG_MARK = "ff8800"        # couleur de notre encart (temoin d'idempotence)
_MSG_EN = ("[b][c][ff8800]No ore deposits here.[/c][/b] Ore is stored in the "
           "POI mines you can see on the map; yours is ~1.2 km away and "
           "unguarded. [b]Press F1 again[/b] for the full note.")
_MSG_FR = ("[b][c][ff8800]Aucun gisement ici.[/c][/b] Le minerai est stocke "
           "dans les mines POI visibles sur la carte ; la tienne est a ~1,2 km "
           "et sans garde. [b]Rappuie sur F1[/b] pour la note complete.")
# jetons utilises par le chapitre d'accueil
_CHAP_KEYS = ("Title", "Desc", "Task", "Act", "Text")
_INTRO = {
    "Title": ("RE2-FR - Ore is no longer in the ground",
              "RE2-FR - Le minerai n'est plus dans le sol"),
    "Desc": ("Deposits are gone: ore now comes from guarded mines.",
             "Les gisements ont disparu : le minerai se prend desormais dans "
             "les mines gardees."),
    "Task": ("Spot the mines on the map",
             "Reperer les mines sur la carte"),
    "Act": ("Open the map (M)",
            "Ouvre la carte (M)"),
    "Done": ("Milestone I starts right away: mine 200 Iron from the nearest "
             "mine.",
             "Le Jalon I demarre tout de suite : extrais 200 fer dans la "
             "mine la plus proche."),
    "Text": ("This is not a bug: no planet or moon grows deposits anymore. "
             "All ore sits in POI mines, visible on the map even under fog; "
             "each marker wears its owner faction's colour. « Abandoned "
             "Mine » is your starter mine: 1.2 to "
             "1.5 km from your landing point, no drones, turrets unpowered, "
             "iron and copper. The others (« Mining Hub », « Excavation "
             "Site », « Mining Outpost ») belong to factions: guarded by "
             "drones, they also give cobalt and, when hostile, neodymium. "
             "Every mine refills after 1 to 3 hours of game time. Tip: build "
             "near the landing point (no drone patrol) and stay out of the "
             "coloured faction territories.",
             "Ce n'est pas un bug : aucune planete ni lune ne produit plus de "
             "gisement. Tout le minerai est dans des mines POI, visibles sur "
             "la carte meme sous brouillard ; chaque marqueur prend la "
             "couleur de sa faction. « Abandoned "
             "Mine » est ta mine de depart : a 1,2-1,5 km du point de chute, "
             "sans drones, tourelles hors tension, fer et cuivre. Les autres "
             "(« Mining Hub », « Excavation Site », « Mining Outpost ») sont "
             "tenues par des factions : gardees par des drones, elles donnent "
             "aussi du cobalt et, chez les hostiles, du neodyme. Chaque mine "
             "se recharge apres 1 a 3 heures de jeu. Conseil : pose ta base "
             "pres du point de chute (aucune patrouille de drones) et evite "
             "les territoires colores des factions."),
}


def _cle(ms: dict, quoi: str) -> str:
    return "pda_" + ms["id"] + quoi


def _cle_intro(suffixe: str) -> str:
    return "pda_Intro" + suffixe


def _intro_chapter() -> str:
    # `Activatable: WhenRewarded` (sur le Jalon I) ne suffit PAS : c'est le
    # chapitre PRECEDENT qui l'offre, via `ActivateChapterOnCompletion` (lance
    # la suite) + `RewardedChapters` (satisfait le WhenRewarded). Schema lu
    # dans le prologue RE2 (`pda_iG40h` -> `pda_u8qi4`), vecu 12/11 : sans ces
    # deux cles le Jalon I restait affiche « a recompenser ».
    return (
        "  - ChapterTitle: " + _cle_intro("Title") + "\n"
        "    Category: Tutorial\n"
        "    NoSkip: true\n"
        "    Activatable: Always\n"
        "    Visibility: Always\n"
        "    PlayerLevel: 1\n"
        "    Description: " + _cle_intro("Desc") + "\n"
        "    Tasks:\n"
        "      - TaskTitle: " + _cle_intro("Task") + "\n"
        "        Actions:\n"
        "          - ActionTitle: " + _cle_intro("Act") + "\n"
        "            Description: " + _cle_intro("Text") + "\n"
        "            AllowManualCompletion: true\n"
        "            Check: WindowOpened\n"
        "            Names:\n"
        "              - Map\n"
        "              - SectorMap\n"
        "              - SystemMap\n"
        "    ActivateChapterOnCompletion: " + _cle(MILESTONES[0], "Title") + "\n"
        "    RewardedChapters:\n"
        "      - " + _cle(MILESTONES[0], "Title") + "\n"
        "    CompletedMessage: norm;25|" + _cle_intro("Done") + "\n")


def _strip_chapter(texte: str, cle: str) -> str:
    """Retire un de NOS chapitres, ou qu'il soit dans la liste."""
    pat = re.compile(r"(?m)^  - ChapterTitle: " + re.escape(cle)
                     + r"[ \t]*$.*?(?=^  - ChapterTitle:|^[A-Za-z_]|\Z)", re.S)
    m = pat.search(texte)
    return texte[:m.start()] + texte[m.end():] if m else texte


def _reorder_chapters(texte: str, blocs: tuple) -> tuple:
    """Place NOS chapitres en TETE, dans l'ordre donne, et retire les
    versions presentes ailleurs. L'ordre n'est pas cosmetique : `WhenRewarded`
    (chainage intro -> Jalon I) ne s'appuie que sur le chapitre qui PRECEDE
    dans la liste. Idempotent."""
    avant = texte
    for cle, _ in blocs:
        texte = _strip_chapter(texte, cle)
    texte = _apres_chapters(texte, "".join(b for _, b in blocs))
    return texte, int(texte != avant)


def _place_our_chapters(texte: str) -> tuple:
    """Groupe ordonne : accueil, puis Jalon I (auto-enchaine), II et III."""
    blocs = ((_cle_intro("Title"), _intro_chapter()),)
    blocs += tuple((_cle(ms, "Title"), _chapter(ms)) for ms in MILESTONES)
    return _reorder_chapters(texte, blocs)


def _strip_intro_task(texte: str) -> str:
    """Retire la tache de note posee par la version precedente : dans un
    chapitre `HideTasks: true` elle n'affichait RIEN (vecu 12/11, le joueur
    ne voyait pas la note). Le texte est desormais ajoute au premier MESSAGE
    du prologue, seul canal garanti."""
    if _cle_intro("Msg") not in texte:
        return texte
    lignes = texte.split("\n")
    out, i = [], 0
    while i < len(lignes):
        if re.match(r"^\s+- TaskTitle: " + _cle_intro("Task") + r"\s*$",
                    lignes[i]):
            j = i + 1
            while j < len(lignes) and not re.match(r"^\s+- TaskTitle:", lignes[j]) \
                    and not lignes[j].startswith("  - ChapterTitle:"):
                j += 1
            bloc = "\n".join(lignes[i:j])
            if _cle_intro("Msg") in bloc:
                i = j
                continue
        out.append(lignes[i])
        i += 1
    return "\n".join(out)


def _drop_rows(csv_texte: str, cles: tuple) -> tuple:
    """Supprime des lignes devenues orphelines (jeton plus reference)."""
    lignes = csv_texte.split("\n")
    garde = [ln for ln in lignes if ln.split(",", 1)[0] not in cles]
    return "\n".join(garde), len(lignes) - len(garde)


def _patch_prologue_texts(csv_texte: str) -> tuple:
    """Pose l'encart « plus de gisement » aux PREMIERS messages des chapitres
    de depart (EN + version FR en colonne Francais). L'encart est RECALCULE a
    chaque passage — l'ancien (repere par sa couleur) est retire — donc
    raccourcir le texte ici suffit a le mettre a jour partout."""
    lignes = csv_texte.split("\n")
    orig = dict(_NOTE_MSGS)
    marque = "[b][c][" + _MSG_MARK + "]"
    n = 0
    for i, ligne in enumerate(lignes):
        cle = ligne.split(",", 1)[0]
        if cle not in orig:
            continue
        cols = next(_csv.reader(io.StringIO(ligne)), [])
        if len(cols) < 4:
            continue
        neuf = []
        for j, note in ((1, _MSG_EN), (3, _MSG_FR)):
            # `\n` est ici du TEXTE (deux caracteres) : rstrip() ne le coupe pas
            base = re.sub(r"(?:\\n)+\s*$", "",
                          cols[j].split(marque)[0]).rstrip()
            if j == 3 and not base.strip():
                base = orig[cle]
            neuf.append(base + "\\n\\n" + note)
        if neuf[0] == cols[1] and neuf[1] == cols[3]:
            continue
        lignes[i] = _csv_ligne(cols[0], neuf[0], neuf[1])
        n += 1
    return "\n".join(lignes), n


def _refresh_intro_rows(csv_texte: str) -> tuple:
    """Reecrit NOS lignes CSV depuis les constantes : retoucher un texte ici
    PROPAGE la correction aux scenarios deja remplis (le « marqueur blanc »
    etait faux : la couleur suit la faction, vecu 12/11). Couvre l'accueil
    (tous suffixes) et les messages de validation des jalons."""
    attendu = {_cle_intro(s): _INTRO[s] for s in _CHAP_KEYS + ("Done",)}
    attendu.update({_cle(ms, "Done"): ms["done"] for ms in MILESTONES})
    lignes = csv_texte.split("\n")
    n = 0
    for i, ligne in enumerate(lignes):
        cle = ligne.split(",", 1)[0]
        if cle not in attendu:
            continue
        en, fr = attendu[cle]
        neuve = _csv_ligne(cle, en, fr)
        if lignes[i] != neuve:
            lignes[i] = neuve
            n += 1
    return "\n".join(lignes), n


def _chapter(ms: dict) -> str:
    items = "".join(
        "      - Item: " + nom + "\n        Count: " + str(n) + "\n"
        for nom, n in ms["items"])
    # Jalon I : `WhenRewarded` = deverrouille par le chapitre PRECEDENT
    # (l'accueil, qui le precede immediatement grâce a _place_our_chapters) ;
    # II et III restent activables a la main, l'acces est annonce a la fin du I.
    activation = "WhenRewarded" if ms["id"] == MILESTONES[0]["id"] else "Always"
    return (
        "  - ChapterTitle: " + _cle(ms, "Title") + "\n"
        "    Category: SoloMission\n"
        "    NoSkip: true\n"
        "    Activatable: " + activation + "\n"
        "    Visibility: Always\n"
        "    PlayerLevel: 1\n"
        "    Description: " + _cle(ms, "Desc") + "\n"
        "    Tasks:\n"
        "      - TaskTitle: " + _cle(ms, "Task") + "\n"
        "        Actions:\n"
        "          - ActionTitle: " + _cle(ms, "Act") + "\n"
        "            Description: " + _cle(ms, "Text") + "\n"
        "            Check: ItemsPickedUp\n"
        "            Types:\n"
        "              - " + ms["ore"] + "\n"
        "            NamesRequired: NeedAll\n"
        "            Amount: " + str(ms["amount"]) + "\n"
        "    Rewards:\n"
        "      - Type: UP\n"
        "        Count: " + str(ms["up"]) + "\n"
        "      - Type: XP\n"
        "        Count: " + str(ms["xp"]) + "\n"
        + items
        + "    CompletedMessage: norm;25|" + _cle(ms, "Done") + "\n")


def _bump_msg_duration(texte: str) -> tuple:
    """Double la duree d'affichage de la boite du premier message du depart
    (`norm;10|` etait trop court pour lire la note ajoutee)."""
    avant = texte
    texte = re.sub(r"(?m)^([ \t]+StartMessage: norm;)(?:10|15|20|25)(\|"
                   + re.escape(PROLOGUE_MSG) + r")",
                   r"\g<1>30\g<2>", texte)
    return texte, int(texte != avant)


def _ensure_chapter(texte: str, ms: dict) -> tuple:
    """Remplace le chapitre du jalon s'il differe de la version courante :
    les jalons deja poses (avant l'ajout du message de validation et des
    objets) se mettent ainsi a jour tout seuls."""
    pat = re.compile(r"(?m)^  - ChapterTitle: " + re.escape(_cle(ms, "Title"))
                     + r"[ \t]*$.*?(?=^  - ChapterTitle:|^[A-Za-z_]|\Z)", re.S)
    m = pat.search(texte)
    if m is None:
        return texte, 0
    bloc = _chapter(ms)
    if m.group(0).strip() == bloc.strip():
        return texte, 0
    return texte[:m.start()] + bloc + texte[m.end():], 1


def _csv_ligne(cle: str, anglais: str, francais: str) -> str:
    """Ligne CSV 18 colonnes : KEY, English, Deutsch, Francais, puis 14
    langues vides. Le francais va en colonne 4 — la colonne 3 est
    l'allemand (les 15 lignes de jalons deja ecrites y etaient ; corrige
    par `_repair_fr_column`)."""
    def esc(v: str) -> str:
        return '"' + v.replace('"', '""') + '"' if "," in v or '"' in v else v
    return ",".join([cle, esc(anglais), "", esc(francais)] + [""] * 14)


def _repair_fr_column(texte: str, cles: tuple) -> tuple:
    """Deplace vers la colonne Francais le texte laisse en colonne Deutsch.
    Retourne (texte, nb_lignes_corrigees). Ne touche qu'aux cles a nous."""
    import csv as _csv
    import io
    lignes = texte.split("\n")
    n = 0
    for i, ligne in enumerate(lignes):
        if not ligne or ligne.split(",", 1)[0].lstrip('"') not in cles:
            continue
        cols = next(_csv.reader(io.StringIO(ligne)), [])
        if len(cols) > 3 and cols[2].strip() and not cols[3].strip():
            cols[3] = cols[2]
            cols[2] = ""
            lignes[i] = _csv_ligne(cols[0], cols[1], cols[3])
            n += 1
    return "\n".join(lignes), n


def _apres_chapters(texte: str, ajout: str) -> str:
    """Insere juste APRES la ligne `Chapters:` : le chapitre d'accueil doit
    apparaitre en tete du PDA."""
    lignes = texte.split("\n")
    for i, ligne in enumerate(lignes):
        if ligne.strip() == "Chapters:":
            return "\n".join(lignes[:i + 1]) + "\n" + ajout \
                + "\n".join(lignes[i + 1:])
    return texte.rstrip("\n") + "\n" + ajout


def _avant_creator(texte: str, ajout: str) -> str:
    """Insere AVANT la ligne finale `Creator:` : nos chapitres restent dans
    la sequence `Chapters:` (seul autre bloc de niveau 0 du fichier)."""
    lignes = texte.split("\n")
    for i in range(len(lignes) - 1, -1, -1):
        if lignes[i].startswith("Creator:"):
            return "\n".join(lignes[:i]) + "\n" + ajout + "\n".join(lignes[i:])
    return texte.rstrip("\n") + "\n" + ajout


def _yaml_parse_ok(texte: str) -> bool:
    """Garde-fou : le YAML produit doit se parser avec le parseur du projet."""
    from core.yamllite.parser import parse_yaml_file
    tmp = Path(tempfile.mkdtemp()) / "PDA.yaml"
    tmp.write_text(texte, encoding="utf-8")
    try:
        parse_yaml_file(tmp)
        return True
    except Exception:                      # noqa: BLE001 - YAML casse = abandon
        return False


def pass_tech_milestones(scenario: Path, apply: bool = False, store=None) -> dict:
    """Ajoute les trois jalons + le chapitre d'accueil (PDA.yaml + PDA.csv).
    Idempotent, et repare la colonne Francais des lignes deja ecrites."""
    rep = {"id": "tech_milestones", "edits": 0, "files": 0, "details": []}
    if not TECH_MILESTONES:
        rep["details"].append("jalons desactives")
        return rep
    yaml_path = Path(scenario) / PDA_YAML
    csv_path = Path(scenario) / PDA_CSV
    if not yaml_path.is_file() or not csv_path.is_file():
        rep["details"].append("PDA.yaml ou PDA.csv absent")
        return rep
    texte, eol = read_text_raw(yaml_path)
    csv_texte, csv_eol = read_text_raw(csv_path)

    besoin_intro = INTRO_KEY not in texte
    # detection par CLE : les titres des jalons sont des jetons (pda_Jal1Title)
    # dans le YAML, jamais le mot « Jalon » — c'est le CSV qui porte le texte.
    besoin_jalons = _cle(MILESTONES[0], "Title") not in texte
    cles_intro = [_cle_intro(s) for s in _CHAP_KEYS + ("Done",)]
    cles_jalons = [_cle(ms, s) for ms in MILESTONES for s, _ in _CSV_KEYS]
    cles_done = [_cle(ms, "Done") for ms in MILESTONES]
    deja_csv = {ligne.split(",", 1)[0] for ligne in csv_texte.split("\n") if ligne}
    a_ajouter = (cles_intro if besoin_intro else []) \
        + (cles_jalons if besoin_jalons else []) \
        + [k for k in cles_done if k not in deja_csv]
    collisions = [k for k in a_ajouter if k in texte or k in deja_csv]
    if collisions:
        rep["details"].append("cles deja presentes : " + ", ".join(collisions))
        return rep

    csv_texte2, n_fr = _repair_fr_column(
        csv_texte, tuple(cles_intro + cles_jalons + cles_done))
    nouveau = texte
    # nettoyage de la tache de note posee par la version precedente
    nouveau = _strip_intro_task(nouveau)
    # placement en tete, dans l'ordre : accueil, Jalon I, II, III
    nouveau, n_maj = _place_our_chapters(nouveau)
    nouveau, n_duree = _bump_msg_duration(nouveau)
    attendu = (texte.count("  - ChapterTitle: ") + int(besoin_intro)
               + int(besoin_jalons) * len(MILESTONES))
    if nouveau.count("  - ChapterTitle: ") != attendu:
        rep["details"].append("nombre de chapitres inattendu : abandon")
        return rep
    if nouveau != texte and not _yaml_parse_ok(nouveau):
        rep["details"].append("YAML invalide apres ajout : abandon")
        return rep
    csv_texte2, n_note = _patch_prologue_texts(csv_texte2)
    csv_texte2, n_txt = _refresh_intro_rows(csv_texte2)
    # ligne du jeton de la tache supprimee : orpheline, on la retire
    csv_texte2, n_orph = _drop_rows(csv_texte2, (_cle_intro("Msg"),))
    n_note += n_orph

    lignes = []
    if besoin_jalons:
        for ms in MILESTONES:
            for suffixe, indice in _CSV_KEYS:
                lignes.append(_csv_ligne(_cle(ms, suffixe),
                                         ms["en"][indice], ms["fr"][indice]))
    for ms in MILESTONES:
        if _cle(ms, "Done") not in deja_csv:
            en, fr = ms["done"]
            lignes.append(_csv_ligne(_cle(ms, "Done"), en, fr))
    for suffixe in _CHAP_KEYS + ("Done",):
        if _cle_intro(suffixe) in deja_csv:
            continue
        en, fr = _INTRO[suffixe]
        lignes.append(_csv_ligne(_cle_intro(suffixe), en, fr))
    if not (lignes or nouveau != texte or n_fr or n_note or n_txt):
        return rep                       # deja tout pose : 0 edit
    if apply:
        if store:
            store.snapshot(yaml_path)
            store.snapshot(csv_path)
        if nouveau != texte:
            write_text_raw(yaml_path, nouveau, eol)
        csv_final = csv_texte2.rstrip("\n") + "\n"
        if lignes:
            csv_final += "\n".join(lignes) + "\n"
        write_text_raw(csv_path, csv_final, csv_eol)
    rep["files"] = 2
    rep["edits"] = (n_maj + n_duree + len(lignes) + n_fr + n_note + n_txt)
    rep["details"].append(
        f"ordre_chapitres={n_maj} duree_msg={n_duree} note_prologue={n_note} "
        f"maj_textes={n_txt} {len(lignes)} lignes CSV, "
        f"{n_fr} colonne(s) FR corrigee(s)")
    return rep
