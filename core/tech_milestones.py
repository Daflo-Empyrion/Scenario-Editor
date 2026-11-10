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
import tempfile
from pathlib import Path

from core.ai_realism import read_text_raw, write_text_raw

TECH_MILESTONES = True
PDA_YAML = "Extras/PDA/PDA.yaml"
PDA_CSV = "Extras/PDA/PDA.csv"
MARKER = "Jalon "          # present dans les titres FR : garde d'idempotence

# (id de cle, item ramasse, quantite, UP, XP, (titre, resume, texte) FR/EN)
MILESTONES = (
    {"id": "Jal1", "ore": "IronOre", "amount": 200, "up": 3, "xp": 1500,
     "fr": ("Jalon I - Le premier lingot",
            "Ramassez 200 fer.",
            "Le minerai ne vient plus du sol : il se prend dans les mines "
            "gardees (entrees « Conflict...Mines » sur la carte)."),
     "en": ("Milestone I - The first ingot",
            "Pick up 200 Iron.",
            "Ore no longer grows in the ground: it comes from guarded mines "
            "(the « Conflict...Mines » markers on the map).")},
    {"id": "Jal2", "ore": "CobaltOre", "amount": 150, "up": 5, "xp": 3000,
     "fr": ("Jalon II - Le cobalt du vaincu",
            "Ramassez 150 cobalt.",
            "Le cobalt n'existe plus que sur les mines de faction : il faut "
            "en chasser les drones."),
     "en": ("Milestone II - Cobalt of the fallen",
            "Pick up 150 Cobalt.",
            "Cobalt now only exists in faction mines: you must fight the "
            "drones to get it.")},
    {"id": "Jal3", "ore": "NeodymiumOre", "amount": 100, "up": 8, "xp": 6000,
     "fr": ("Jalon III - L'ere du neodyme",
            "Ramassez 100 neodyme.",
            "Le neodyme ne se trouve que dans les mines des factions "
            "HOSTILES : c'est le prix de l'equipement avance."),
     "en": ("Milestone III - The neodymium age",
            "Pick up 100 Neodymium.",
            "Neodymium only spawns in HOSTILE faction mines: that is the "
            "price of advanced gear.")},
)

# ordre des lignes CSV par jalon : (suffixe de cle, indice dans le tuple FR/EN)
_CSV_KEYS = (("Title", 0), ("Desc", 1), ("Task", 0), ("Act", 1), ("Text", 2))


def _cle(ms: dict, quoi: str) -> str:
    return "pda_" + ms["id"] + quoi


def _chapter(ms: dict) -> str:
    return (
        "  - ChapterTitle: " + _cle(ms, "Title") + "\n"
        "    Category: SoloMission\n"
        "    NoSkip: true\n"
        "    Activatable: Always\n"
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
        "        Count: " + str(ms["xp"]) + "\n")


def _csv_ligne(cle: str, anglais: str, francais: str) -> str:
    """Ligne CSV 18 colonnes (les 15 autres langues restent vides)."""
    def esc(v: str) -> str:
        return '"' + v.replace('"', '""') + '"' if "," in v or '"' in v else v
    return ",".join([cle, esc(anglais), esc(francais)] + [""] * 15)


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
    """Ajoute les trois jalons (PDA.yaml + PDA.csv). Idempotent."""
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
    if MARKER in texte:
        return rep                       # jalons deja poses : 0 edit

    cles = [_cle(ms, suffixe) for ms in MILESTONES for suffixe, _ in _CSV_KEYS]
    collisions = [k for k in cles if k in texte]
    csv_texte, csv_eol = read_text_raw(csv_path)
    if not collisions:
        deja = {ligne.split(",", 1)[0] for ligne in csv_texte.split("\n") if ligne}
        collisions = [k for k in cles if k in deja]
    if collisions:
        rep["details"].append("cles deja presentes : " + ", ".join(collisions))
        return rep

    ajout = "".join(_chapter(ms) for ms in MILESTONES)
    nouveau = _avant_creator(texte, ajout)
    avant = texte.count("  - ChapterTitle: ")
    if nouveau.count("  - ChapterTitle: ") != avant + len(MILESTONES):
        rep["details"].append("nombre de chapitres inattendu : abandon")
        return rep
    if not _yaml_parse_ok(nouveau):
        rep["details"].append("YAML invalide apres ajout : abandon")
        return rep

    lignes = []
    for ms in MILESTONES:
        for suffixe, indice in _CSV_KEYS:
            lignes.append(_csv_ligne(_cle(ms, suffixe),
                                     ms["en"][indice], ms["fr"][indice]))

    if apply:
        if store:
            store.snapshot(yaml_path)
            store.snapshot(csv_path)
        write_text_raw(yaml_path, nouveau, eol)
        write_text_raw(csv_path,
                       csv_texte.rstrip("\n") + "\n" + "\n".join(lignes) + "\n",
                       csv_eol)
    rep["files"] = 2
    rep["edits"] = len(MILESTONES) + len(lignes)
    rep["details"].append(
        f"{len(MILESTONES)} jalons PDA, {len(lignes)} lignes CSV (EN+FR)")
    return rep
