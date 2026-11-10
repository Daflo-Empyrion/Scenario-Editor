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

"""Passes de conflit de factions (moteur 1.19.6 — modèle : GS_ConflictArid vanilla).

Pour chaque playfield PLANÉTAIRE du scénario (`PlayfieldType: Planet`,
découverte automatique, `planet_playfields`) :
- POIs : une base par faction (21). Groupe natif quand le playfield le
  déclare déjà, sinon le pool `Conflict<Faction>Bases` de
  Prefabs/_PoiGroupsConfig.yaml — donc une base partout. Nos entrées sont
  insérées en fin de liste `Random:` (la fin de liste place nos bases APRÈS
  la résolution de START ; en tête = NPE du RandomPlacer).
  Hostiles à 4000+ du START, alliées à 2500+.
- DroneBaseSetup : un DroneSetupID par groupe faction, stock typé
  (FighterDrone / TroopTransport / GroundTroop), + `Random:` qui porte le
  lien POI -> base. La section est créée si absente.
- PlanetVessels : patrouilleurs IA (OPV_/OPVs_/ROPV_/R2OPV_/R2PV_ —
  les CV_* sont des blueprints joueurs : morts en usage IA), ancrés sur le
  groupe retenu pour leur faction.
- DroneSpawning : patrouilles de drones génériques (no-op sans la section).

Règle « safe » : jamais d'ancrage hostile sur START ni sur le POI starter.
Groupes/ancres : fiche cerveau empyrion-conflit-factions-machine-portable.
"""
import hashlib
import os
import re
from pathlib import Path

from core.ai_realism import read_text_raw, write_text_raw


def purge_playfield_cache(path: Path) -> bool:
    """Supprime le cache compilé `<yaml>.bin` du jeu et rafraîchit le mtime
    du yaml. Le jeu compare les DATES : un .bin plus récent que son yaml est
    servi à la place du yaml (modifs invisibles, playfield figé — vecu
    09/11, fiche cerveau playfield-yaml-bin-caches). À appeler après TOUTE
    écriture ou copie d'un playfield vers la production."""
    cache = Path(str(path) + ".bin")
    removed = False
    if cache.exists():
        cache.unlink()
        removed = True
    if Path(path).exists():
        os.utime(path, None)
    return removed


# ---------------------------------------------------------------------------
# Roster : UNE base par faction (21), sur tous les playfields planétaires.
# Le groupe NATIF est utilisé quand le playfield le déclare déjà (Dread et
# les playfields d'origine gardent leur contenu) ; sinon on retombe sur le
# pool `Conflict<Faction>Bases`, défini globalement dans
# Prefabs/_PoiGroupsConfig.yaml — donc disponible partout.
# (faction, groupes natifs candidats — le premier déclaré gagne, hostile)
# ---------------------------------------------------------------------------
# False = bisect : 12 factions d'origine seulement.
TOTAL_WAR = True

_FACTIONS = (
    ("Zirax", ("R2XenuMain", "R2XenuAuxT1"), True),
    ("Kriel", ("KrielMain",), True),
    ("Warlord", (), True),
    ("Pirates", ("R2PirateMain",), True),
    ("TheLegacy", ("R2LegacyDefenseT1",), True),
    ("Polaris", ("R2PolarisMain",), False),
    ("Talon", ("R2TalonMain",), False),
    ("Farr", ("FarrMainRG", "FarrMainSingleRG"), False),
    ("UCH", (), False),
    ("Wastelanders", (), False),
    ("Colonists", ("R2ColonistMain",), False),
    ("ARC", (), False),
    # extension total war : maisons Zirax et factions restantes
    ("Xenu", ("R2XenuAuxT1",), True),
    ("Rados", ("R2RadosMainT3Desert",), True),
    ("Epsilon", ("R2EpsilonMain",), True),
    ("Ghyst", ("R2GhystMain",), True),
    ("Serdu", (), True),
    ("Abyssal", (), True),
    ("Alien", (), True),
    ("Tesch", (), False),
    ("Trader", ("R2TraderMain",), False),
)


def _active_factions() -> tuple:
    return _FACTIONS if TOTAL_WAR else _FACTIONS[:12]


def _pool(faction: str) -> str:
    return "Conflict" + faction + "Bases"

_RETIRED_POI_GROUPS = (
    "ConflictKrielBases", "ConflictPiratesBases", "ConflictLegacyBases",
    "ConflictPolarisBases", "ConflictTalonBases", "ConflictFarrBases",
    "ConflictColonistsBases", "R2PolarisDefenseT1", "R2TalonDefense",
    "FarrDefenseT1RG", "R2KrielMain", "R2KrielDefenseT1",
    "ConflictKrielBases", "R2XenuMainT3",
    # extension total war (retires quand TOTAL_WAR est False)
    "R2XenuAuxT1", "R2RadosMainT3Desert", "R2EpsilonMain",
    "R2GhystMain", "ConflictSerduBases", "ConflictAbyssalBases",
    "ConflictAlienBases", "ConflictTeschBases", "R2TraderMain",
)

# Distance minimale du START. 4000/2500 échouait sur les planètes saturées
# (195 POI natifs sur GUEN 49863 : seules les bases alliées se plaçaient).
_POI_AVOID = {"hostile": 2000, "ally": 1200}

# ---------------------------------------------------------------------------
# Pools _PoiGroupsConfig : un par faction. Le prefab est un petit poste de
# la faction — les gros prefabs échouent au placement (vécu 09/11 : bases
# « Placing FAILED after 2001 max iterations »).
# ---------------------------------------------------------------------------
_POOL_PREFABS = {
    "Zirax": "BAO_ZiraxDefenseT1",
    "Kriel": "BAO_KrielBeacon",
    "Warlord": "BAO_WarlordPromethiumA",
    "Pirates": "BAO_PiratesDefense1",
    "TheLegacy": "BA_LegacyHelixT1",
    "Polaris": "BA_PolarisSecurity1",
    "Talon": "BA_TalonArid_1",
    "Farr": "BAO_FarrRefuelingStation",
    "UCH": "BAO_UCH-Outpost42",
    "Wastelanders": "BAO_WastelandersCarrier",
    "Colonists": "Eden_TSO_Colonists1",
    "ARC": "BAO_ARCDeltaStation",
    "Xenu": "BAO_XenuDefenseT1",
    "Rados": "BAO_RadosRepairStation",
    "Epsilon": "BA_EpsilonAdvOutpost",
    "Ghyst": "BAO_GhystDefenseT1",
    "Serdu": "BAO_SerduChapel",
    "Abyssal": "BAO_AbyssalSmallScience",
    "Alien": "BA_AlienTower1",
    "Tesch": "BAO_TeschNodeT1a",
    "Trader": "BA_TraderDefenseT1",
}


def _poi_groups() -> tuple:
    """(GroupName, prefab, faction, hostile) des factions actives."""
    return tuple((_pool(f), _POOL_PREFABS[f], f, h)
                 for f, _, h in _active_factions())


def missing_pool_prefabs(scenario: Path) -> list:
    """(faction, prefab) dont le .epb manque dans Prefabs/ du scénario."""
    pre = scenario / "Prefabs"
    return [(f, p) for _, p, f, _ in _poi_groups()
            if not (pre / (p + ".epb")).is_file()]


def _poi_group_block(gname: str, prefab: str, faction: str, hostile: bool) -> str:
    return (
        "    - GroupName: " + gname + "\n"
        "      Filters:\n"
        "          BlueprintFileNames: [ " + prefab + " ]\n"
        "      Defaults:\n"
        "          Faction: " + faction + "\n"
        "          NoShieldReload: true\n"
        "          CountMinMax: [ 1, 1 ]\n"
        "          LevelMod: 0\n"
        "          InitPower: true\n"
        "          DroneProb: 0.6\n"
        "          DronesMinMax: [ 3, 5 ]\n"
        "          ReserveCount: 3\n"
        "          TroopTransport: " + str(hostile).lower())


def _poi_groups_block() -> str:
    return "\n".join(_poi_group_block(*g) for g in _poi_groups())


def _declares(text: str, gname: str) -> bool:
    """Le playfield déclare-t-il ce GroupName dans ses POIs ? (toutes
    indentations : 8 espaces en standard, `   -  ` sur 2 playfields)"""
    return re.search(r"(?m)^[ \t]*-[ \t]+GroupName: " + re.escape(gname)
                     + r"[ \t]*(#.*)?$", text) is not None


# Roster par playfield : 21 bases ne peuvent PAS se placer sur une planete
# saturee (mesure 09/11 : 195 POI natifs, seules les alliees passaient).
# On tire donc 8 factions par planete et 6 par lune, de facon DETERMINISTE
# sur le nom du playfield : stable d'un run a l'autre, et toutes les
# factions existent quelque part dans la galaxie.
_ROSTER_SIZE = {"planet": 8, "moon": 6}


def _playfield_kind(text: str) -> str:
    m = re.search(r"(?m)^PlayfieldType:[ \t]*(\w+)", text)
    return m.group(1).lower() if m else "planet"


def _roster(name: str, text: str) -> tuple:
    """Factions retenues pour ce playfield (Zirax toujours present)."""
    size = _ROSTER_SIZE.get(_playfield_kind(text), 8)
    factions = list(_active_factions())
    zirax = next((f for f in factions if f[0] == "Zirax"), None)
    pool = [f for f in factions if f[0] != "Zirax"]
    if zirax is not None and size > 1:
        pool = sorted(pool, key=lambda f: hashlib.sha256(
            (name + "|" + f[0]).encode("utf-8")).hexdigest())
        picked = [zirax] + pool[:size - 1]
    else:
        picked = pool[:size]
    return tuple(sorted(picked, key=lambda f: f[0]))


def _entry_groups(text: str, name: str) -> tuple:
    """(groupe, faction, hostile) retenus pour CE playfield : groupe natif
    s'il est déjà déclaré, sinon le pool de la faction."""
    out = []
    for faction, natives, hostile in _roster(name, text):
        gname = next((n for n in natives if _declares(text, n)), _pool(faction))
        out.append((gname, faction, hostile))
    return tuple(out)


def _poi_entries_block(groups: tuple, style: dict) -> str:
    e, c = style["entry"], style["cont"]
    tail = c + "Properties:\n" + style["item"] + "Key: RegenAfter\n" \
        + style["val"] + "Value: 720\n"
    out = []
    # Base de drones : SANS elle, aucun drone sur la planete (les POI
    # defendus d'Arid_V2 sont poses SpawnPOINear: [R2DroneBase] et le
    # stock de drones vient de la). Dread n'en avait aucune.
    out.append(
        e + "GroupName: R2DroneBase\n"
        + c + "Faction: Zirax\n"
        + c + "IsImportant: True\n"
        + c + "CountMinMax: [ 1, 1 ]\n"
        + c + "DroneProb: 1.0\n"
        + c + "DronesMinMax: [ 8, 12 ]\n"
        + c + "ReserveCount: 12\n"
        + c + "TroopTransport: True\n"
        + c + "SpawnPOIAvoid: [START]\n"
        + c + "SpawnPOIAvoidDistance: 4000\n"
        + tail)
    for gname, faction, hostile in groups:
        dist = _POI_AVOID["hostile" if hostile else "ally"]
        out.append(
            e + "GroupName: " + gname + "\n"
            + c + "Faction: " + faction + "\n"
            # relie la base a son stock de drones (schema GS_ConflictArid)
            + c + "DroneBaseSetup: "
            + _FACTION_DRONE_SETUP.get(faction, "DroneBaseSetup") + "\n"
            + c + "CountMinMax: [ 1, 1 ]\n"
            + c + "DroneProb: 1.0\n"
            + c + "DronesMinMax: [ 6, 10 ]\n"
            + c + "ReserveCount: 10\n"
            + c + "TroopTransport: " + str(hostile).lower() + "\n"
            + c + "SpawnPOIAvoid: [START]\n"
            + c + "SpawnPOIAvoidDistance: " + str(dist) + "\n"
            + tail)
    return "\n".join(out)


# ---------------------------------------------------------------------------
# PlanetVessels : (Name, Faction, DistToGround, drone escorte, vitesse)
# L'ancre n'est plus figée : c'est le groupe de la faction retenu pour le
# playfield (natif ou pool), sinon le patrouilleur visait un POI absent.
# ---------------------------------------------------------------------------
_VESSELS = (
    ("R2PV_ZiraxCutter01", "Zirax", 300, "DroneHoverZiraxLaser", 20),
    ("R2OPV_PolarisCutter01", "Polaris", 200, "DroneSmallPolarisLaser", 12),
    ("ROPV_KrielAccipiter", "Kriel", 300, "DroneSmallFast01Rocket", 14),
    ("ROPV_WarlordPhoenix", "Warlord", 300, "DroneSmallFast01Minigun", 14),
    ("ROPV_PiratesDreadmaw", "Pirates", 300, "DroneSmallFast01Rocket", 14),
    ("R2OPV_LegacyInfector01", "TheLegacy", 300, "DroneSmallFast01Rocket", 12),
    ("OPVs_TalonarModScoutPlayer", "Talon", 200, "DroneSmallFast01Minigun", 12),
    ("ROPV_FarrGuardian", "Farr", 200, "DroneSmallFast01Minigun", 12),
    ("OPV_UCHDestroyer", "UCH", 200, "DroneSmallFast01Minigun", 12),
    ("OPV_WastelandersEnforcer", "Wastelanders", 200, "DroneSmallFast01Minigun", 12),
    ("OPV_ColonistsJLNMAC", "Colonists", 200, "DroneSmallFast01Minigun", 12),
    ("OPV_ARCBronco", "ARC", 200, "DroneSmallFast01Minigun", 12),
)

# patrouilleurs de l'extension total war (voir TOTAL_WAR)
_VESSELS_EXTRA = (
    ("PV_EpsilonPatrolVessel1", "Epsilon", 250, "DroneSmallFast01Minigun", 13),
    ("PV_GhystPatrolVessel3", "Ghyst", 250, "DroneSmallFast01Rocket", 13),
    ("PV_SerduCutterT2", "Serdu", 250, "DroneSmallFast01Minigun", 13),
    ("OPV_TraderHeavy", "Trader", 200, "DroneSmallFast01Minigun", 11),
)

def _vessel_items(groups: tuple) -> list:
    """Blocs PlanetVessels, ancrés sur le groupe retenu pour chaque faction."""
    anchor_of = {faction: gname for gname, faction, _ in groups}
    roster = set(anchor_of)
    out = []
    for name, faction, dist, drone, speed in _active_vessels():
        if faction not in roster:
            continue
        anchor = anchor_of.get(faction, _pool(faction))
        out.append(
            "              - Name: " + name + "\n"
            "                Faction: " + faction + "\n"
            "                CountMinMax: [1, 1]\n"
            "                FixedMaxSpeed: " + str(speed) + "\n"
            "                DelayBetweenRespawn: 1200\n"
            "                DelayBeforeSelfDestruction: 1200\n"
            "                IsRespawnAfterDestruction: False\n"
            "                RangePatrolTask:\n"
            "                  POINameAsPositionRef: [" + anchor + "]\n"
            "                  DistToGround: " + str(dist) + "\n"
            "                Properties:\n"
            "                  - Key: Discovery\n"
            "                    Value: False\n"
            "                Stock:\n"
            "                  - Name: " + drone + "\n"
            "                    Amount: 4\n"
            "                    Type: FighterDrone\n")
    return out


_RETIRED_VESSELS = (
    "CV_KrielAccipiter", "CV_WarlordHoplite", "OPV_PiratesCorvetteT1A",
    "OPV_LegacyDecimator", "CV_TalonArGuardian", "Eden_OPV_FarrHQ1",
    "CV_UCH001Hyperion", "CV_ArcBronco", "R2OPV_PolarisCorvette01",
    # extension total war
    "PV_EpsilonPatrolVessel1", "PV_GhystPatrolVessel3",
    "PV_SerduCutterT2", "OPV_TraderHeavy",
)

# ---------------------------------------------------------------------------
# Patrouilles de drones : STYLE RE2 (RealmEngine/RE2 n'utilise ni Name: ni
# Faction: dans DroneSpawning — verifie sur 173 playfields : seules nos
# propres entrees en avaient). Le type de drone vient du Stock du groupe
# DroneBaseSetup du playfield. Les 4 secteurs couvrent la planete, comme
# Desert/playfield_static (reference native).
# ---------------------------------------------------------------------------
_DRONE_PATROLS = (
    ("[ 6, 10 ]", 5000, 3500),
    ("[ 6, 10 ]", -5000, 3500),
    ("[ 5, 8 ]", 2500, 3500),
    ("[ 5, 8 ]", -2500, 3500),
    ("[ 4, 8 ]", 0, 4000),
)


def _spawn_entries() -> list:
    out = []
    for minmax, center_x, radius in _DRONE_PATROLS:
        out.append("        - DronesMinMax: " + minmax + "\n"
                   "          CenterX: " + str(center_x) + "\n"
                   "          Radius: " + str(radius) + "\n")
    return out


# Playfields exclus du périmètre automatique (tous les `PlayfieldType:
# Planet` sont pris par défaut). Utile pour écarter un cas cassé.
CONFLICT_SKIP: set = set()


def conflict_playfields(scenario: Path) -> list:
    """Playfields du scénario visés : planètes ET lunes (dossiers
    Playfields/* dont le playfield_static.yaml porte
    `PlayfieldType: Planet` ou `Moon`)."""
    out = []
    for path in sorted((scenario / "Playfields").glob("*/playfield_static.yaml")):
        name = path.parent.name
        if name.startswith(("+", ".")) or ".bak" in path.name:
            continue
        try:
            text = path.read_text("utf-8", errors="replace")
        except OSError:
            continue
        if re.search(r"(?m)^PlayfieldType:[ \t]*(?:Planet|Moon)\b", text):
            out.append(name)
    return [n for n in out if n not in CONFLICT_SKIP]


# nom historique (les appels externes s'en servent encore)
planet_playfields = conflict_playfields

# NE PAS mettre DroneSetupID sur les entrees POI : sur Dread (un seul
# DroneBaseSetup generique) cela fait echouer le placement -> aucune base
# ne spawn + message d'erreur (vecu 09/11).

# Bande de niveau du playfield : pilote le niveau de TOUS les POI
# (bases comprises, sans compensation de LevelMod) et les bandes de
# vagues FactionWarfare (PlayFieldLvl1/5/10 dans FactionWarfare.ecf).
# [1,1] = starter fige au tier 1 ; [1,2] = la vanille RE2 (153 playfields).
CONFLICT_PLAYFIELD_LEVEL = (1, 2)

# --- Agressivité des drones (guerre drone vs drone) -------------------------
# Par défaut les drones ne détectent que "Player,BA,SV,HV,CV" (valeur
# documentée dans EClassConfig, ligne commentée AITarget-1 DroneDetection).
# Les jetons valides incluent NPCFighter et EnemyDrone : les ajouter fait
# que les drones des factions ennemies se ciblent entre eux.
# BISECT : cocher les jetons un par un. `()` = retour au défaut vanilla,
# état validé en jeu (0 crash) le 09/11 — c'est le point de repli.
DRONE_EXTRA_TARGETS = ("NPCFighter",)
_DRONE_VANILLA_TARGETS = "Player,BA,SV,HV,CV"
DRONE_AGGRESSION = bool(DRONE_EXTRA_TARGETS)
_DRONE_TARGETS = ",".join((_DRONE_VANILLA_TARGETS,) + DRONE_EXTRA_TARGETS)
_DRONE_ECLASSES = (
    "DroneSmallFast01Minigun", "DroneSmallFast01Rocket",
    "DroneSmallAttackBase", "DroneSmallPolarisLaser",
    "DroneBomberAttackBase", "EnemyDroneV2Plasma",
    "DroneHoverZiraxLaser", "DroneTroopsTransport",
)


# ---------------------------------------------------------------------------
# Mutateurs (texte et blocs en LF : read_text_raw normalise,
# write_text_raw convertit vers l'EOL du fichier)
# ---------------------------------------------------------------------------

def _ensure_poi_groups(pgroups_path: Path, apply: bool, store) -> int:
    """Crée / met à jour CHAQUE pool de faction, individuellement : un pool
    étranger ajouté après les nôtres n'est plus détruit (comportement
    d'avant : la queue du fichier était remplacée en bloc)."""
    text, eol = read_text_raw(pgroups_path)
    n = 0
    for g in _poi_groups():
        blk = _poi_group_block(*g)
        pat = re.compile(r"(?m)^ {4}- GroupName: " + re.escape(g[0]) + r"[ \t]*$"
                         r".*?(?=^ {4}- GroupName:|\Z)", re.S)
        m = pat.search(text)
        if m is None:
            text = text.rstrip("\n") + "\n" + blk + "\n"
            n += 1
        elif m.group(0).rstrip("\n") != blk.rstrip("\n"):
            text = text[:m.start()] + blk + "\n" + text[m.end():]
            n += 1
    if n and apply:
        if store:
            store.snapshot(pgroups_path)
        write_text_raw(pgroups_path, text, eol)
    return n


def _poi_style(text: str) -> dict:
    """Prefixes d'indentation des entrées POI, LUS sur la première entrée du
    playfield : 188 fichiers utilisent `        - ` (8 espaces), 2 utilisent
    `   -  ` (3 espaces). Écrire une indentation figée déplaçait nos entrées
    hors de la liste (vécu 09/11 : EdenBarrenElder)."""
    d = {"entry": "        - ", "cont": "          ",
         "item": "            - ", "val": "              "}
    m = re.search(r"(?m)^ *POIs:[ \t]*\n[ \t]*Random:[ \t]*\n", text)
    if m is None:
        return d
    e = re.search(r"(?m)^([ \t]*-[ \t]+)GroupName:", text[m.end():])
    if e is None:
        return d
    entry = e.group(1)
    body = text[m.end() + e.end():][:2000]
    c = re.search(r"(?m)^( +)[A-Za-z]+:", body)
    cont = c.group(1) if c else " " * len(entry)
    it = re.search(r"(?m)^([ \t]*-[ \t]+)Key:", body)
    item = it.group(1) if it else " " * (len(cont) + 2) + "- "
    v = re.search(r"(?m)^( +)Value:", body)
    val = v.group(1) if v else " " * len(item)
    return {"entry": entry, "cont": cont, "item": item, "val": val}


def _poi_zone(text: str, style: dict) -> tuple:
    """(fin de l'en-tête POIs/Random, fin de la zone) ou (None, None)."""
    m = re.search(r"(?m)^ *POIs:[ \t]*\n[ \t]*Random:[ \t]*\n", text)
    if m is None:
        return None, None
    indent = len(style["entry"]) - len(style["entry"].lstrip())
    # La zone s'arrete a la 1re CLE de meme niveau ou moins indentee que les
    # entrees : avec `   -  ` (3 espaces), `   FixedPlayerStart:` est a 3
    # et etait rate => nos entrees tombaient DANS FixedPlayerStart (crash
    # "Property 'GroupName' not found on type PoiData+PlayerStartData").
    end = re.search(r"(?m)^ {0,%d}[A-Za-z_]\w*:" % max(indent, 0),
                    text[m.end():])
    return m, (m.end() + end.start() if end else len(text))


def _entry_block_pat(style: dict, gname: str):
    """Motif d'un bloc d'entrée POI : de `- GroupName: <gname>` jusqu'à
    l'entrée suivante ou une clé moins indentée — les sous-listes
    (`- Key:` / `Value:`) sont INCLUSES, sinon leurs queues restent
    orphelines et cassent le YAML (`did not find expected key`)."""
    stop = r"(?!(?:[ \t]*-[ \t]+)GroupName:| {0,%d}[A-Za-z_]\w*:)" % (
        max(len(style["cont"]) - 1, 0))
    return re.compile(r"(?m)^" + re.escape(style["entry"]) + r"GroupName: "
                      + re.escape(gname) + r"[^\n]*\n(?:" + stop + r"[^\n]*\n)*")


def _remove_pois(text: str, groupnames: tuple, style: dict = None) -> tuple:
    """Retire les entrées POIs périmées (une par GroupName), dans le style
    d'indentation du playfield."""
    st = style or _poi_style(text)
    removed = 0
    for gn in groupnames:
        text, k = _entry_block_pat(st, gn).subn("", text)
        removed += k
    return text, removed


def _ensure_pois(text: str, block: str) -> tuple:
    """Insère nos entrées POIs EN FIN de la liste Random: — jamais en tête
    (SpawnPOIAvoid [START] serait traité avant que START existe : NPE du
    RandomPlacer) et jamais après la fin de section (GroupName dans
    FixedPlayerStart : crash PoiData+PlayerStartData).
    Le style d'indentation est celui du playfield, cf. `_poi_style`.
    Auto-réparation : un GroupName présent avec un texte différent est
    retiré puis réinséré."""
    style = _poi_style(text)
    entries = re.split(r"\n\n", block.rstrip("\n"))
    gnames = []
    for e in entries:
        gm = re.search(r"(?m)^" + re.escape(style["entry"])
                       + r"GroupName: ([\w-]+)$", e)
        gnames.append(gm.group(1) if gm else "?")
    m, zone_end = _poi_zone(text, style)
    if m is None:
        return text, 0
    # auto-réparation : toute occurrence de NOS entrées HORS de la zone
    # Random (ex. restée dans FixedPlayerStart => crash au chargement) est
    # retirée, puis réinsérée proprement.
    n_stray = 0
    for gname in set(gnames):
        pat = _entry_block_pat(style, gname)
        for mt in list(pat.finditer(text)):
            if m.end() <= mt.start() <= zone_end:
                continue
            text = text[:mt.start()] + text[mt.end():]
            zone_end -= mt.end() - mt.start()
            n_stray += 1
    zone = text[m.end():zone_end]
    missing = [e for e in entries if e + "\n" not in text]
    zone_last = zone.rfind(style["entry"] + "GroupName: ")
    ours_last = zone_last >= 0 and any(
        zone.startswith(style["entry"] + "GroupName: " + g, zone_last)
        for g in set(gnames))
    if not missing and ours_last:
        return text, n_stray
    if missing:
        todo = [(gn, e) for gn, e in zip(gnames, entries) if e + "\n" not in text]
    else:
        todo = list(zip(gnames, entries))
    text, removed = _remove_pois(text, tuple(gn for gn, _ in todo), style)
    m, zone_end = _poi_zone(text, style)
    if m is None:
        return text, removed + n_stray
    zone_content = text[m.end():zone_end]
    after = text[zone_end:]
    joined = "\n\n".join(e.rstrip("\n") for _, e in todo) + "\n\n"
    return (text[:m.end()] + zone_content.rstrip("\n") + "\n\n" + joined + after,
            removed + len(todo))


# Les declarations multiples d'un meme GroupName (Biome/BiomesExcluded
# differents) sont du DESIGN vanilla (RuinsLogisticsAuxT1 x8,
# CrashedShipStarter x3) : ne JAMAIS les fusionner.

_FACTION_DRONE_SETUP = {
    "Zirax": "DroneBaseSetup", "Kriel": "DroneBaseSetupKrl",
    "Warlord": "DroneBaseSetupWar", "Pirates": "DroneBaseSetup",
    "TheLegacy": "DroneBaseSetup", "Polaris": "DroneBaseSetupPol",
    "Talon": "DroneBaseSetup", "Farr": "DroneBaseSetupFarr",
    "UCH": "DroneBaseSetup", "Wastelanders": "DroneBaseSetupWar",
    "Colonists": "DroneBaseSetupPol", "ARC": "DroneBaseSetup",
    # total war : maisons Zirax et factions restantes
    "Xenu": "DroneBaseSetup", "Rados": "DroneBaseSetup",
    "Epsilon": "DroneBaseSetupEps", "Ghyst": "DroneBaseSetup",
    "Serdu": "DroneBaseSetup", "Abyssal": "DroneBaseSetup",
    "Alien": "DroneBaseSetup", "Tesch": "DroneBaseSetup",
    "Trader": "DroneBaseSetup",
}

def _active_vessels() -> tuple:
    return _VESSELS + (_VESSELS_EXTRA if TOTAL_WAR else ())


# groupes jamais réduits par scale_poi_density : nos bases (natifs possibles
# + pools), quelle que soit la planète.
_BASE_GROUPS = frozenset(
    g for f, natives, _ in _active_factions() for g in (natives + (_pool(f),)))


def scale_poi_density(text: str, factor: float) -> tuple:
    """Réduit d'un facteur les CountMinMax des groupes POI d'origine pour
    libérer des emplacements de placement (les bases de faction, déjà à
    [1,1], ne sont pas touchées). Une déclaration = un bloc ; les
    déclarations multiples par biome gardent chacune son propre compte."""
    n = 0

    def repl(mo):
        nonlocal n
        block = mo.group(0)
        if mo.group(1) in _BASE_GROUPS:
            return block
        cm = re.search(r"CountMinMax: \[ *(\d+) *, *(\d+) *\]", block)
        if cm is None:
            return block
        lo, hi = int(cm.group(1)), int(cm.group(2))
        nlo = max(1, round(lo * factor))
        nhi = max(nlo, round(hi * factor))
        if (nlo, nhi) == (lo, hi):
            return block
        n += 1
        return block[:cm.start()] + f"CountMinMax: [ {nlo}, {nhi} ]" + block[cm.end():]

    text = re.sub(r"(?ms)^[ \t]*-[ \t]+GroupName: (\w+)[^\n]*\n"
                  r"(?:[ \t]+(?![ \t]*-)[^\n]*\n)*", repl, text)
    return text, n


SCALE_MARKER = "# conflict: scale "


def pass_scale_pois(scenario: Path, factor: float, apply: bool = False,
                    store=None, playfields=None) -> dict:
    """Réduit la densité de POIs une seule fois par playfield : un marqueur
    `# conflict: scale <f>` est écrit en tête, un playfield déjà marqué est
    sauté (avant, chaque passage réduisait encore). Les caches .bin sont
    purgés après écriture."""
    rep = {"id": "scale_pois", "factor": factor, "files": 0, "edits": 0,
           "details": []}
    for pfname in (playfields or planet_playfields(scenario)):
        path = scenario / "Playfields" / pfname / "playfield_static.yaml"
        if not path.is_file():
            continue
        text, eol = read_text_raw(path)
        if SCALE_MARKER in text:
            continue
        m = re.search(r"(?ms)^POIs:.*?(?=^DroneBaseSetup:)", text)
        before = re.findall(r"CountMinMax: \[ *(\d+) *, *(\d+) *\]", m.group(0)) if m else []
        text, n = scale_poi_density(text, factor)
        if not n:
            continue
        text = SCALE_MARKER + ("%g" % factor) + "\n" + text
        m = re.search(r"(?ms)^POIs:.*?(?=^DroneBaseSetup:)", text)
        after = re.findall(r"CountMinMax: \[ *(\d+) *, *(\d+) *\]", m.group(0)) if m else []
        rep["files"] += 1
        rep["edits"] += n
        rep["details"].append(
            "%s : %d blocs, %d-%d -> %d-%d POIs"
            % (pfname, n, sum(int(a) for a, _ in before), sum(int(b) for _, b in before),
               sum(int(a) for a, _ in after), sum(int(b) for _, b in after)))
        if apply:
            if store:
                store.snapshot(path)
            write_text_raw(path, text, eol)
            purge_playfield_cache(path)
    return rep


def _remove_vessels(text: str, names: tuple) -> tuple:
    """Retire les items de vaisseaux périmés du bloc PlanetVessels.
    L'item va de `- Name:` jusqu'à la prochaine ligne MOINS indentée : la
    borne par `^DroneSpawning:` échouait sur les playfields sans cette
    section, et le dernier vaisseau n'était jamais retiré (idempotence
    cassée, 13 playfields)."""
    removed = 0
    for name in names:
        pat = re.compile(r"(?m)^ {14}- Name: " + re.escape(name) + r"\n"
                         r"(?: {15,}[^\n]*\n)*")
        text, k = pat.subn("", text)
        removed += k
    return text, removed


# Les DEUX sous-sections sont nécessaires (vécu 09/11 soir) :
# - `Random:` liste un `GroupName` par faction : c'est LE LIEN que la clé
#   `DroneBaseSetup: <groupe>` d'une entrée POI résout. Le supprimer fait
#   disparaître les bases du playfield (vérifié en jeu).
# - `DroneBases:` porte le `DroneSetupID` moderne, seul à produire
#   réellement des drones (stock en `Amount: Infinite`, modèle GS_Akua).
# On émet donc un DroneSetupID par valeur distincte de
# _FACTION_DRONE_SETUP dans les deux sections, avec `DroneSetupID:` aussi
# sur l'entrée `Random:` (champ prévu par le schéma du moteur).
_DRONE_STOCKS = {
    "DroneBaseSetup": (
        "DroneSmallFast01Minigun", "DroneSmallFast01Rocket",
        "DroneBomberAttackBase", "EnemyDroneV2Plasma",
        "DroneTroopsTransport", "ZiraxMinigun", "ZiraxRocket"),
    "DroneBaseSetupKrl": (
        "DroneSmallFast01Rocket", "DroneSmallAttackBase",
        "DroneTroopsTransport", "AlienAssassinRed", "Hexapod"),
    "DroneBaseSetupWar": (
        "DroneSmallFast01Minigun", "DroneSmallAttackBase",
        "DroneTroopsTransport", "AssaultCyborg"),
    "DroneBaseSetupPol": (
        "DroneSmallPolarisLaser", "DroneSmallAttackBase",
        "DroneTroopsTransport", "AssaultCyborg"),
    "DroneBaseSetupFarr": (
        "DroneSmallFast01Minigun", "DroneSmallAttackBase",
        "DroneTroopsTransport"),
    "DroneBaseSetupEps": (
        "DroneSmallFast01Minigun", "DroneSmallAttackBase",
        "DroneTroopsTransport", "ZiraxMale"),
}


def _drone_type(name: str) -> str:
    # rôles documentés par Eleon (+ExampleInstance) : un Stock sans `Type:`
    # produit une unité dégénérée -> NRE en boucle au tick de sélection.
    if "TroopsTransport" in name:
        return "TroopTransport"
    return "FighterDrone" if name.startswith(("Drone", "EnemyDrone")) else "GroundTroop"


def _stock_lines(setup_id: str) -> list:
    stock = _DRONE_STOCKS.get(setup_id, _DRONE_STOCKS["DroneBaseSetup"])
    return ["              - Name: " + n + "\n"
            "                Amount: Infinite\n"
            "                Type: " + _drone_type(n) for n in stock]


def _drone_setup_block() -> str:
    # un DroneSetupID par valeur RÉFÉRENCÉE : jamais de clé POI orpheline
    ids = list(dict.fromkeys(_FACTION_DRONE_SETUP.values()))
    out = ["DroneBaseSetup:", "    DroneBases:"]
    for setup_id in ids:
        out += ["        - DroneSetupID: " + setup_id, "          Stock:"]
        out += _stock_lines(setup_id)
    out.append("    Random:")
    for setup_id in ids:
        out += ["        - GroupName: " + setup_id,
                "          DroneSetupID: " + setup_id,
                "          Difficulty: 6", "          PresetStyle: 3",
                "          Stock:"]
        out += _stock_lines(setup_id)
    return "\n".join(out) + "\n"


# Fin d'un bloc de premier niveau : prochaine clé en colonne 0.
_NEXT_TOP = r"(?=^[A-Za-z_]|\Z)"


def _ensure_drone_setup(text: str) -> tuple:
    """Installe le DroneBaseSetup complet (schema GS_ConflictArid : un
    stock par faction, relié aux POI par la clé `DroneBaseSetup:`).
    Crée la section si elle manque (géantes gazeuses) ; la sous-section
    PlanetVessels est PRÉSERVÉE ; le bloc est borné par la prochaine clé
    de niveau 0 — jamais par `DroneSpawning:` seul, sinon tout ce qui suit
    (SpawnZones, CreatureSpawning) était supprimé."""
    m = re.search(r"(?ms)^DroneBaseSetup:[ \t]*\n.*?" + _NEXT_TOP, text)
    ids = dict.fromkeys(_FACTION_DRONE_SETUP.values())
    typed = "                Amount: Infinite\n                Type: "
    if m is None:
        anchor = re.search(r"(?m)^(DroneSpawning:|SpawnZones:)", text)
        pos = anchor.start() if anchor else len(text)
        head = text[:pos]
        if head and not head.endswith("\n\n"):
            head = head.rstrip("\n") + "\n\n"
        return head + _drone_setup_block() + "\n" + text[pos:], 1
    if (all("- DroneSetupID: " + s in m.group(0)
            and "- GroupName: " + s in m.group(0) for s in ids)
            and typed in m.group(0)):
        return text, 0
    pv = re.search(r"(?ms)^    PlanetVessels:.*?(?=^[A-Za-z_]|\Z)", m.group(0))
    keep = ("\n" + pv.group(0).rstrip("\n") + "\n") if pv else "\n"
    return text[:m.start()] + _drone_setup_block() + keep + text[m.end():], 1


def _ensure_vessels(text: str, items: list) -> tuple:
    """Ajoute au bloc PlanetVessels les vaisseaux absents ET repointe l'ancre
    des vaisseaux existants vers le groupe retenu pour leur faction (sinon
    un patrouilleur garde une ancre morte d'un playfield voisin).
    Crée PlanetVessels au besoin, sans exiger DroneSpawning."""
    n = 0
    pending = []
    for it in items:
        m = re.search(r"(?m)^ +- Name: ([A-Za-z0-9_]+)", it)
        anchor = re.search(r"POINameAsPositionRef: \[(\w+)\]", it)
        if not m or not anchor:
            continue
        name, want = m.group(1), anchor.group(1)
        block = re.search(r"(?m)^ +- Name: " + re.escape(name) + r"[ \t]*$"
                          r".*?(?=^ +- Name: |^[A-Za-z_]|\Z)", text, re.S)
        if block is None:
            pending.append(it)
            continue
        fixed = re.sub(r"POINameAsPositionRef: \[\w+\]",
                       "POINameAsPositionRef: [" + want + "]", block.group(0))
        if fixed != block.group(0):
            text = text[:block.start()] + fixed + text[block.end():]
            n += 1
    if not pending:
        return text, n
    joined = "\n".join(it.rstrip("\n") for it in pending) + "\n"
    m = re.search(r"(?ms)^    PlanetVessels:.*?" + _NEXT_TOP, text)
    if m is not None:
        return text[:m.end()].rstrip("\n") + "\n" + joined + text[m.end():], n + len(pending)
    db = re.search(r"(?ms)^DroneBaseSetup:[ \t]*\n.*?" + _NEXT_TOP, text)
    if db is None:
        return text, n
    block = "    PlanetVessels:\n" + joined
    return text[:db.end()].rstrip("\n") + "\n" + block + text[db.end():], n + len(pending)


def _ensure_playfield_level(text: str, level: tuple = CONFLICT_PLAYFIELD_LEVEL) -> tuple:
    """Fixe PlayfieldLevelOverride (playfield_dynamic.yaml). Niveau de tous
    les POI + bandes d'escalade FactionWarfare. Idempotent."""
    lo, hi = level
    pat = re.compile(r"(?m)^PlayfieldLevelOverride:[ \t]*\[[ \t]*\d+[ \t]*,[ \t]*\d+[ \t]*\]")
    if pat.search(text) is None:
        return text, 0
    new = pat.sub("PlayfieldLevelOverride: [%d,%d]" % (lo, hi), text, count=1)
    return (new, 1) if new != text else (text, 0)


def _ensure_spawn_entries(text: str, entries: list) -> tuple:
    """Le pass POSSÈDE le bloc DroneSpawning > Random : toute entrée de
    patrouille (DronesMinMax: ou Name:) est remplacée par le jeu courant —
    sinon les anciennes valeurs s'empilent à chaque changement de densité.
    Le bloc est borné par la prochaine clé de niveau 0 : les sections
    suivantes (SpawnZones, CreatureSpawning) sont préservées. La borne
    était avant le premier commentaire `#`, donc tout ce qui suivait
    DroneSpawning sans commentaire était écrasé (vécu 09/11 : 8 playfields
    ont perdu SpawnZones/SpawnRateZones/CreatureSpawning)."""
    m = re.search(r"(?m)^DroneSpawning:[ \t]*\n[ \t]*Random:[ \t]*\n", text)
    if m is None:
        return text, 0
    end = re.search(r"(?m)^[A-Za-z_]\w*:", text[m.end():])
    body_end = m.end() + end.start() if end else len(text)
    head, body, tail = text[:m.end()], text[m.end():body_end], text[body_end:]
    ours = tuple(e.rstrip("\n") for e in entries)
    kept, dropped = [], 0
    for blk in re.findall(
            r"(?ms)^[ \t]*-[ \t]+(?:DronesMinMax|Name):[^\n]*\n"
            r"(?:[ \t]+(?![ \t]*-)[^\n]*\n)*", body):
        body = body.replace(blk, "", 1)
        if blk.rstrip("\n") in ours:
            kept.append(blk.rstrip("\n"))
        else:
            dropped += 1
    missing = [e for e in entries if e.rstrip("\n") not in kept]
    if not missing and not dropped:
        return text, 0
    content = kept + [e.rstrip("\n") for e in missing]
    return head + "\n\n".join(content) + "\n\n" + tail, max(len(missing) + dropped, 1)


def _is_planet_drone(name: str) -> bool:
    """Drones PLANÉTAIRES visés par la passe : tout nom contenant Drone
    sauf les drones joueur, spatiaux, gabarits/tests et modules de
    vaisseau (BA_/CV_ClusterDrone)."""
    if "Drone" not in name:
        return False
    if "Space" in name or "PlayerDrone" in name:
        return False
    if "Template" in name or "Test" in name or "ClusterDrone" in name:
        return False
    return True


def _ensure_drone_targets(text: str) -> tuple:
    """Étend la liste de cibles de TOUS les drones planétaires
    (EClassConfig) à NPCFighter et EnemyDrone : sans ça les drones
    n'attaquent que le joueur et ses vaisseaux, jamais ceux d'une faction
    ennemie. Idempotent ; les alias `Ref:` héritent et sont ignorés."""
    n = 0
    out = []
    pos = 0
    for m in re.finditer(r"(?ms)^\{ *\+?Entity Name: *([A-Za-z0-9_]+)[^\n]*\n.*?^\}",
                         text):
        name = m.group(1)
        blk = m.group(0)
        if not _is_planet_drone(name) or re.search(r"^\{ *Entity Name:.*Ref:", blk):
            continue
        # idempotence : ligne ACTIVE déjà à la valeur voulue
        line = ('AITarget-1: DroneDetection, param1: "' + _DRONE_TARGETS
                + '", param2: EntityShipSV')
        if re.search(r"(?m)^ *" + re.escape(line) + r"\s*$", blk):
            continue
        at = re.search(r"(?m)^( *)AITarget-1: DroneDetection.*$", blk)
        if at:
            new = blk[:at.start()] + at.group(1) + line + blk[at.end():]
        else:
            anchor = re.search(r"(?m)^( *)#? *AITask-\d+:.*$", blk)
            if anchor is not None:
                ind = anchor.group(1) or "  "
                new = blk[:anchor.end()] + "\n" + ind + line + blk[anchor.end():]
            else:
                new = blk.replace("\n", "\n  " + line + "\n", 1)
        out.append(text[pos:m.start()])
        out.append(new)
        pos = m.end()
        n += 1
    out.append(text[pos:])
    return "".join(out), n


# Factions hostiles (Factions.ecf Unfriendly: true) qui doivent figurer
# dans la réputation INITIALE du joueur. Absentes de la table "Human:1",
# elles retombent sur le défaut moteur et leurs drones ignorent le joueur
# (vécu 09/11 : drones TheLegacy inoffensifs alors que Zirax, listé à 0,
# attaque normalement).
_HOSTILE_FACTIONS = ("TheLegacy", "Kriel", "Warlord", "Alien",
                     "Serdu", "Abyssal", "Xenu", "Rados", "Epsilon", "Ghyst")


def pass_hostile_reputation(scenario: Path, apply: bool = False, store=None) -> dict:
    """CF.3 : garantit que chaque faction hostile a une réputation
    initiale explicite (0, comme Zirax) dans DefReputation.ecf."""
    rep = {"id": "hostile_reputation", "edits": 0, "files": 0, "details": []}
    path = scenario / "Content/Configuration/DefReputation.ecf"
    if not path.is_file():
        rep["details"].append("DefReputation.ecf absent")
        return rep
    text, eol = read_text_raw(path)
    m = re.search(r'(?ms)^\{ Reputation Name: "Human:1"(.*?)^\}', text)
    if m is None:
        rep["details"].append('bloc "Human:1" introuvable')
        return rep
    missing = [f for f in _HOSTILE_FACTIONS
               if not re.search(r"(?m)^\s+" + f + r":", m.group(1))]
    if not missing:
        return rep
    add = "".join("  " + f + ": 0\n" for f in missing)
    # insère juste avant l'accolade fermante du bloc (dernier "}" du match)
    close = text.rfind("}", m.start(), m.end())
    text = text[:close] + add + text[close:]
    rep["files"] = 1
    rep["edits"] = len(missing)
    rep["details"].append("réputation hostile ajoutée : " + ", ".join(missing))
    if apply:
        if store:
            store.snapshot(path)
        write_text_raw(path, text, eol)
    return rep


# NPC référencés par des spawners de prefabs RE2 mais ABSENTS de
# l'EClassConfig de RE2-FR : le jeu logue « Spawner NPC X not found -
# cannot calc value » (40x sur Dread) et ces entités fantômes font
# échouer la sérialisation du playfield (« Exception on playfield »).
# Alias vers l'EClass existant le plus proche.
_NPC_ALIASES = {"MechanoidMinigun": "Mechanoid", "MechanoidFlak": "Mechanoid"}


def _ensure_npc_aliases(text: str) -> tuple:
    """Ajoute les alias d'EClass manquants (Ref vers un EClass existant).
    Idempotent."""
    missing = [(n, t) for n, t in _NPC_ALIASES.items()
               if not re.search(r"(?m)^\{ *\+?Entity Name: *" + n + r"\b", text)]
    if not missing:
        return text, 0
    add = "".join("{ Entity Name: " + n + ", Ref: " + t + "\n}\n" for n, t in missing)
    return text.rstrip("\n") + "\n\n" + add, len(missing)


def pass_drone_aggression(scenario: Path, apply: bool = False, store=None) -> dict:
    """CF.2 : les drones des factions ennemies se ciblent entre eux
    (EClassConfig AITarget : + NPCFighter,EnemyDrone)."""
    rep = {"id": "drone_aggression", "edits": 0, "files": 0, "details": []}
    path = scenario / "Content/Configuration/EClassConfig.ecf"
    if not path.is_file():
        rep["details"].append("EClassConfig.ecf absent")
        return rep
    text, eol = read_text_raw(path)
    if not DRONE_AGGRESSION:
        # retour aux 5 types vanilla, param2 PRESERVE (sinon NRE au save)
        pat = (r'(?m)^( *)AITarget-1: DroneDetection, param1: "[^"]*"'
               r'(.*)$')
        text, k = re.subn(
            pat, lambda m: (m.group(1) + 'AITarget-1: DroneDetection, '
                            'param1: "' + _DRONE_VANILLA_TARGETS + '"'
                            + m.group(2)), text)
        if k and apply:
            if store:
                store.snapshot(path)
            write_text_raw(path, text, eol)
        if k:
            rep["files"] = 1
            rep["edits"] = k
            rep["details"].append(f"extension cibles drones RETIREE ({k} entites)")
        return rep
    text, n = _ensure_drone_targets(text)
    text, n2 = _ensure_npc_aliases(text)
    if n or n2:
        rep["files"] = 1
        rep["edits"] = n + n2
        if n:
            rep["details"].append(f"cibles drones etendues ({n} entites)")
        if n2:
            rep["details"].append(f"alias NPC ajoutes ({n2})")
        if apply:
            if store:
                store.snapshot(path)
            write_text_raw(path, text, eol)
    return rep


def pass_faction_conflict(scenario: Path, apply: bool = False, store=None,
                          playfields=None) -> dict:
    """CF.1 : conflit de factions sur les playfields planétaires.

    Une base par faction et par playfield : groupe natif quand le playfield
    le déclare déjà, sinon le pool `Conflict<Faction>Bases`. Les
    patrouilleurs suivent le groupe retenu pour leur faction."""
    rep = {"id": "faction_conflict", "edits": 0, "files": 0, "details": []}
    pgroups_path = scenario / "Prefabs" / "_PoiGroupsConfig.yaml"
    missing = missing_pool_prefabs(scenario)
    if missing:
        rep["details"].append(
            "Prefabs manquants : "
            + ", ".join(f"{f}={p}" for f, p in missing))
        return rep
    if not pgroups_path.exists():
        rep["details"].append("_PoiGroupsConfig.yaml absent")
    else:
        k = _ensure_poi_groups(pgroups_path, apply, store)
        if k:
            rep["files"] += 1
            rep["edits"] += k
            rep["details"].append("PoiGroups : %d pools Conflict a jour" % k)
    for pfname in (playfields or planet_playfields(scenario)):
        path = scenario / "Playfields" / pfname / "playfield_static.yaml"
        if not path.exists():
            rep["details"].append(f"{pfname} : absent")
            continue
        text, eol = read_text_raw(path)
        if not re.search(r"(?m)^POIs:", text):
            rep["details"].append(f"{pfname} : sans bloc POIs (ignore)")
            continue
        groups = _entry_groups(text, pfname)
        before_keys = set(re.findall(r"(?m)^([A-Za-z_]\w*):", text))
        if len(re.findall(r"(?m)^POIs:", text)) > 1:
            rep["details"].append(
                f"{pfname} : plusieurs blocs POIs, seul le premier est traite")
        used = {g for g, _, _ in groups}
        # Retrait : UNIQUEMENT nos pools `Conflict*Bases`. Les groupes
        # natifs ne sont jamais retirés, même hors roster : ils
        # appartiennent au playfield (les retirer supprimait du contenu
        # vanilla, vécu 09/11 sur R2GhystMain).
        our_pools = {_pool(f) for f, _, _ in _active_factions()}
        retired_g = tuple(sorted(our_pools - used))
        text, k_rm = _remove_pois(text, retired_g)
        text, k_move = _ensure_pois(text, _poi_entries_block(groups, _poi_style(text)))
        roster = {f for _, f, _ in groups}
        retired_v = tuple(n for n in _RETIRED_VESSELS
                          if n not in {v[0] for v in _active_vessels()}) \
            + tuple(n for n, f, *_ in _active_vessels() if f not in roster)
        text, k_r = _remove_vessels(text, retired_v)
        # DroneBaseSetup AVANT les vaisseaux : ceux-ci s'y rattachent
        text, k_ds = _ensure_drone_setup(text)
        text, k_v = _ensure_vessels(text, _vessel_items(groups))
        text, k_s = _ensure_spawn_entries(text, _spawn_entries())
        # garde-fou : aucune section de niveau 0 ne doit disparaître
        lost = sorted(before_keys - set(re.findall(r"(?m)^([A-Za-z_]\w*):", text)))
        if lost:
            rep["details"].append(
                f"{pfname} : ABANDON (sections perdues : {', '.join(lost)})")
            continue
        n = k_rm + k_move + k_r + k_v + k_s + k_ds
        if n and apply:
            if store:
                store.snapshot(path)
            write_text_raw(path, text, eol)
            purge_playfield_cache(path)
        if n:
            rep["files"] += 1
            rep["edits"] += n
            rep["details"].append(
                f"{pfname} : pois={k_move} vaisseaux={k_v} "
                f"retires={k_rm}/{k_r} spawns={k_s} dronebase={k_ds}")
        if not re.search(r"(?m)^DroneSpawning:", text):
            rep["details"].append(
                f"{pfname} : sans DroneSpawning (pas de patrouille de drones)")
        dyn = scenario / "Playfields" / pfname / "playfield_dynamic.yaml"
        if dyn.is_file():
            dtext, deol = read_text_raw(dyn)
            dtext, k_lvl = _ensure_playfield_level(dtext)
            if k_lvl:
                if apply:
                    if store:
                        store.snapshot(dyn)
                    write_text_raw(dyn, dtext, deol)
                    purge_playfield_cache(dyn)
                rep["files"] += 1
                rep["edits"] += k_lvl
                rep["details"].append(
                    f"{pfname} : PlayfieldLevelOverride -> "
                    f"[{CONFLICT_PLAYFIELD_LEVEL[0]},{CONFLICT_PLAYFIELD_LEVEL[1]}]")
    return rep


# ---------------------------------------------------------------------------
# ESPACE (space_dynamic.yaml) : schéma différent du sol. Pas de `POIs`
# ancrés sur START ni de PlanetVessels, mais :
#   DroneBaseSetup > FreeDrones   (drones spatiaux libres, par faction)
#   DroneBaseSetup > SpaceVessels (patrouilleurs spatiaux, par faction)
# Les deux acceptent `AIManPatrolFactions` : c'est ce qui fait que les
# factions se ciblent entre elles.
# ---------------------------------------------------------------------------
_SPACE_ROSTER_SIZE = 6

_SPACE_DRONES = {
    "Zirax": ("DroneSpaceZiraxLaser", "DroneSpaceZiraxPlasma",
              "DroneSpaceZiraxRocket"),
    "Pirates": ("DroneSpacePiratesEMP", "DroneSpacePiratesSwarmRocket"),
    "Polaris": ("DroneSpacePolarisLaser", "DroneSpacePolarisBeamLaser"),
    "Kriel": ("DroneSpaceKrielRailgun",),
    "TheLegacy": ("DroneSpaceLegacyAntiProton",),
    "Trader": ("DroneSpaceTraderPlasmaRocket", "DroneSpaceTraderRailgun"),
}
_SPACE_DRONE_FALLBACK = "Eden_SpaceDroneBanditT1"
_SPACE_SHIP_FALLBACK = "OPV_Cyrano"


def space_playfields(scenario: Path) -> list:
    """Playfields spatiaux : dossiers dont le space_dynamic.yaml porte
    `PlayfieldType: Space`."""
    out = []
    for path in sorted((scenario / "Playfields").glob("*/space_dynamic.yaml")):
        name = path.parent.name
        if name.startswith(("+", ".")) or ".bak" in path.name:
            continue
        try:
            text = path.read_text("utf-8", errors="replace")
        except OSError:
            continue
        if re.search(r"(?m)^PlayfieldType:[ \t]*Space\b", text):
            out.append(name)
    return [n for n in out if n not in CONFLICT_SKIP]


def _space_roster(name: str) -> tuple:
    """6 factions par playfield spatial, tirage déterministe (Zirax inclus)."""
    factions = list(_active_factions())
    zirax = next((f for f in factions if f[0] == "Zirax"), None)
    pool = [f for f in factions if f[0] != "Zirax"]
    pool = sorted(pool, key=lambda f: hashlib.sha256(
        (name + "|space|" + f[0]).encode("utf-8")).hexdigest())
    picked = ([zirax] if zirax else []) + pool[:max(_SPACE_ROSTER_SIZE - 1, 0)]
    return tuple(sorted(picked, key=lambda f: f[0]))


def _space_ship(faction: str) -> str:
    for name, fac, *_ in _active_vessels():
        if fac == faction:
            return name
    return _SPACE_SHIP_FALLBACK


def _space_drone_block(faction: str, patrol: str) -> str:
    drones = _SPACE_DRONES.get(faction, (_SPACE_DRONE_FALLBACK,))
    return (
        "          - Name: [" + ", ".join(drones) + "]\n"
        "            Faction: " + faction + "\n"
        "            CanNotBeControlledByMasterAI: False\n"
        "            Count: [4, 8]\n"
        "            Radius: [500, 4000]\n"
        "            Properties:\n"
        "              - Key: AIManPatrolFactions\n"
        '                Value: "' + patrol + '"\n'
        "              - Key: AIManMaxPursuitRange\n"
        "                Value: 5000\n"
        "            # conflict:auto")


def _space_vessel_block(faction: str, patrol: str) -> str:
    drone = _SPACE_DRONES.get(faction, (_SPACE_DRONE_FALLBACK,))[0]
    return (
        "          - Name: [" + _space_ship(faction) + "]\n"
        "            Faction: " + faction + "\n"
        "            CountMinMax: [1, 3]\n"
        "            Probability: 1\n"
        "            CanNotBeControlledByMasterAI: False\n"
        "            FixedMaxSpeed: [40, 70]\n"
        "            Mission: SpacePatrol\n"
        "            MissionDescription:\n"
        "              DelayBetweenRespawnMinMax: [3600, 3600]\n"
        "              DelayBeforeSelfDestructionMinMax: [3600, 3600]\n"
        "              IsRespawnAfterDestruction: False\n"
        "              RadiusMinMax: [1500, 3500]\n"
        "              Position:\n"
        "                PosXZMinMax: [300, 4000]\n"
        "                PosYMax: 2000\n"
        "            StockDescription:\n"
        "              Name: [" + drone + "]\n"
        "              AmountMinMax: [0, 0]\n"
        "              ExtraMinMax: [0, 0]\n"
        "              Type: FighterDrone\n"
        "            Properties:\n"
        "              - Key: AIManPatrolFactions\n"
        '                Value: "' + patrol + '"\n'
        "              - Key: MapDistance\n"
        "                Value: 20000\n"
        "              - Key: HudDistance\n"
        "                Value: 20000\n"
        "              - Key: AIManMaxPursuitRange\n"
        "                Value: 8000\n"
        "            # conflict:auto")


def _section_end(text: str, start: int) -> int:
    """Fin d'une liste d'items : première ligne non vide/non commentaire
    moins indentée que 10 espaces."""
    pos = text.find("\n", start)
    pos = len(text) if pos < 0 else pos + 1
    for line in text[pos:].split("\n"):
        if line.strip() and not line.lstrip().startswith("#") \
                and (len(line) - len(line.lstrip())) < 10:
            break
        pos += len(line) + 1
    return min(pos, len(text))


def _ensure_space_units(text: str, roster: tuple) -> tuple:
    """Un bloc FreeDrones et un bloc SpaceVessels par faction du roster.
    Nos blocs portent `# conflict:auto` : eux seuls sont réécrits (mise à
    jour des réglages) ; un bloc natif de la même faction reste intact.
    Analyse LIGNE À LIGNE : les regex à quantificateurs imbriqués sur ces
    sections de plusieurs milliers de lignes explosaient en backtracking."""
    factions = [f[0] for f in roster]
    debut = "          - Name: ["
    n = 0
    for anchor, maker in (("      - FreeDrones:", _space_drone_block),
                          ("        SpaceVessels:", _space_vessel_block)):
        if anchor not in text:
            continue
        pos = text.index(anchor)
        fin = _section_end(text, pos)
        lignes = text[pos:fin].split("\n")
        # découpe en blocs d'items
        blocs, cur = [], None
        for i, ln in enumerate(lignes):
            if ln.startswith(debut):
                if cur is not None:
                    blocs.append((cur, i))
                cur = i
            elif cur is not None and ln.strip() \
                    and not ln.startswith("          ") and (len(ln) - len(ln.lstrip())) < 10:
                blocs.append((cur, i))
                cur = None
        if cur is not None:
            blocs.append((cur, len(lignes)))
        # mise à jour des blocs marqués, ajout des factions absentes
        presents, repl, add = set(), [], []
        for a, b in blocs:
            corps = "\n".join(lignes[a:b])
            fac = re.search(r"(?m)^[ \t]+Faction: (\w+)", corps)
            if not fac or fac.group(1) not in factions:
                continue
            f = fac.group(1)
            presents.add(f)
            if "# conflict:auto" not in corps:
                continue                       # bloc natif : intact
            want = maker(f, ", ".join(x for x in factions if x != f))
            if corps.rstrip("\n") != want.rstrip("\n"):
                repl.append((a, b, want.split("\n")))
        for f in factions:
            if f not in presents:
                add.append(maker(f, ", ".join(x for x in factions if x != f)).split("\n"))
        if not repl and not add:
            continue
        for a, b, want in reversed(repl):
            lignes[a:b] = want
            n += 1
        if add:
            plat = []
            for w in add:
                plat.extend(w)
            while lignes and not lignes[-1].strip():
                lignes.pop()
            lignes.extend(plat)
            n += len(add)
        text = text[:pos] + "\n".join(lignes) + "\n" + text[fin:]
    return text, n


def pass_space_conflict(scenario: Path, apply: bool = False, store=None,
                        playfields=None) -> dict:
    """Conflit de factions dans l'ESPACE : patrouilleurs + drones spatiaux
    par faction (rotation de 6 factions par playfield)."""
    rep = {"id": "space_conflict", "edits": 0, "files": 0, "details": []}
    for pfname in (playfields if playfields is not None
                   else space_playfields(scenario)):
        path = scenario / "Playfields" / pfname / "space_dynamic.yaml"
        if not path.is_file():
            continue
        text, eol = read_text_raw(path)
        if not re.search(r"(?m)^DroneBaseSetup:", text):
            rep["details"].append(f"{pfname} : sans DroneBaseSetup (ignore)")
            continue
        roster = _space_roster(pfname)
        before = len(text)
        text, n = _ensure_space_units(text, roster)
        if n and len(text) < before:
            rep["details"].append(f"{pfname} : ABANDON (texte raccourci)")
            continue
        if not n:
            continue
        if apply:
            if store:
                store.snapshot(path)
            write_text_raw(path, text, eol)
            purge_playfield_cache(path)
        rep["files"] += 1
        rep["edits"] += n
        rep["details"].append(
            f"{pfname} : {n} blocs ({', '.join(f[0] for f in roster)})")
    return rep


# ---------------------------------------------------------------------------
# GUERRE TOTALE (Factions.ecf) : chaque faction active declare attaquer
# TOUTES les autres. Le joueur (`Eden_Defender`) n'est JAMAIS ajoute : les
# factions qui l'attaquaient deja le font encore, les autres restent neutres
# pour lui. On n'utilise pas `AttackNPC: true` (Factions.ecf:24) : il ecrase
# `ForceAttack` et son effet sur l'attaque du joueur n'est pas prouve.
# Repli : TOTAL_WAR_FORCE_ATTACK = False (0 edit).
# ---------------------------------------------------------------------------
TOTAL_WAR_FORCE_ATTACK = True


def _ecf_blocks(text: str, head: str) -> list:
    """(debut, fin) de chaque bloc `{ <head> ... }`, accolades comptees.
    LIGNE A LIGNE et lignes commentees ignorees : les blocs desactives
    (`# { Faction ...` en double dans RE2) ne doivent pas compter."""
    out, start, depth = [], None, 0
    for i, ln in enumerate(text.split("\n")):
        if ln.lstrip().startswith("#"):
            continue
        if start is None:
            if not re.match(head, ln):
                continue
            start, depth = i, ln.count("{") - ln.count("}")
            if depth <= 0:
                out.append((i, i))
                start = None
            continue
        depth += ln.count("{") - ln.count("}")
        if depth <= 0:
            out.append((start, i))
            start = None
    return out


def _faction_names(text: str) -> list:
    """Noms des blocs `{ Faction ... }` actifs, dans l'ordre du fichier."""
    lignes = text.split("\n")
    noms = []
    for a, b in _ecf_blocks(text, r"\{ *Faction Id"):
        m = re.search(r'Name: *"(\w+)"', lignes[a])
        if m:
            noms.append(m.group(1))
    return noms


def pass_force_attack(scenario: Path, apply: bool = False, store=None) -> dict:
    """CF.4 : guerre totale NPC-vs-NPC (ForceAttack symetrique)."""
    rep = {"id": "force_attack", "edits": 0, "files": 0, "details": []}
    path = scenario / "Content/Configuration/Factions.ecf"
    if not path.is_file():
        rep["details"].append("Factions.ecf absent")
        return rep
    text, eol = read_text_raw(path)
    lignes = text.split("\n")
    presents = _faction_names(text)
    actives = [f for f in (x[0] for x in _active_factions()) if f in presents]
    if not TOTAL_WAR_FORCE_ATTACK:
        rep["details"].append("guerre totale desactivee")
        return rep
    n = 0
    # style du fichier : RE2 ecrit ses listes SANS guillemets
    quote = '"' if re.search(r"(?m)^\s+ForceAttack: *\"", text) else ""
    for a, b in reversed(_ecf_blocks(text, r"\{ *Faction Id")):
        nm = re.search(r'Name: *"(\w+)"', lignes[a])
        nom = nm.group(1) if nm else ""
        if nom not in actives:
            continue
        ip = next((k for k in range(a, b + 1)
                   if re.match(r"\s*ForceAttack[ \t]*:", lignes[k])), None)
        if ip is None:
            ind = next((re.match(r"([ \t]+)\w", lignes[k]).group(1)
                        for k in range(a + 1, b)
                        if re.match(r"[ \t]+\w", lignes[k])), "  ")
            cur, sep, tail = [], ",", ""
        else:
            m = re.match(r"([ \t]*ForceAttack[ \t]*:)([^#]*)(.*)$", lignes[ip])
            ind = re.match(r"([ \t]*)", lignes[ip]).group(1)
            corps = m.group(2).strip().strip('"')
            sep = ", " if ", " in corps else ","
            cur = [x.strip() for x in corps.split(",") if x.strip()]
            tail = (" " + m.group(3).strip()) if m.group(3).strip() else ""
        manque = [f for f in actives if f != nom and f not in cur]
        if not manque and ip is not None:
            continue
        cibles = quote + sep.join(cur + manque) + quote
        ligne = ind + "ForceAttack: " + cibles + tail
        if ip is None:
            lignes.insert(b, ligne)
        else:
            lignes[ip] = ligne
        n += 1
        rep["details"].append(nom + " : +" + str(len(manque)))
    if not n:
        return rep
    if apply:
        if store:
            store.snapshot(path)
        write_text_raw(path, "\n".join(lignes), eol)
    rep["files"] = 1
    rep["edits"] = n
    return rep


# ---------------------------------------------------------------------------
# DEFENSES SPATIALES (FactionWarfare.ecf + space_dynamic.yaml). Une faction
# sans `FactionSettings` + `SDScenarioGroup` n'a AUCUN renfort d'espace ; les
# vagues viennent des blocs `Unit` qui portent
# `IsInGroups: "<Faction>SpaceDefense"` et `Category: BaseDefenseOrbitVessel`.
# Le gate par POI reste `SpaceDefenseOverrideDefaults: True` +
# `SpaceDefenseProbability` (doc FactionWarfare.ecf:6-8).
# Repli : SPACE_DEFENSE_ENABLED = False (0 edit).
# ---------------------------------------------------------------------------
SPACE_DEFENSE_ENABLED = True
SPACE_DEFENSE_PROB = 0.35              # part des POI de faction qui defensent
SPACE_DEFENSE_POI_PRICE = (30, 60)     # SpaceDefensePriceMinMax par POI
SD_PROB_MINMAX = (0.30, 0.60)          # SDProbabilityMin/Max (lvl 1 -> 10)
SD_PRICE_MINMAX = (30, 60)             # SDPriceMin/Max des blocs CREES
SD_UNITS = (("drone", 15), ("vessel", 40))   # (type, CommandPointsLvl1)


def _sd_unit_block(faction: str, classe: str, cout: int) -> str:
    return ("{ Element Name: Unit\n"
            "  Faction: " + faction + "\n"
            "  ClassName: " + classe + "\n"
            "  Category: BaseDefenseOrbitVessel\n"
            '  IsInGroups: "' + faction + 'SpaceDefense"\n'
            "  CommandPointsLvl1: " + str(cout) + "\n"
            "  CommandPointsPerLevel: 1\n"
            "}\n")


def _sd_settings_block(faction: str) -> str:
    """FactionSettings cree de zero : prix d'attaque PLANETAIRE a 0 pour ne
    pas ouvrir a la faction les vagues de base-attack existantes (« planetary
    base attack only for Talon and Zirax »), defense spatiale complete."""
    return ("{ Element Name: FactionSettings\n"
            "  Faction: " + faction + "\n"
            "  ScenarioGroup: " + faction + "\n"
            "  Lvl1MinPrice:0\n"
            "  Lvl1MaxPrice:0\n"
            "  Lvl5MinPrice:0\n"
            "  Lvl5MaxPrice:0\n"
            "  Lvl10MinPrice:0\n"
            "  Lvl10MaxPrice:0\n"
            "  SDScenarioGroup: " + faction + "SpaceDefense\n"
            "  SDProbabilityMin: " + str(SD_PROB_MINMAX[0]) + "\n"
            "  SDProbabilityMax: " + str(SD_PROB_MINMAX[1]) + "\n"
            "  SDPriceMin: " + str(SD_PRICE_MINMAX[0]) + "\n"
            "  SDPriceMax: " + str(SD_PRICE_MINMAX[1]) + "\n"
            "}\n")


def _sd_settings_keys(faction: str) -> dict:
    return {"SDScenarioGroup": faction + "SpaceDefense",
            "SDProbabilityMin": str(SD_PROB_MINMAX[0]),
            "SDProbabilityMax": str(SD_PROB_MINMAX[1]),
            "SDPriceMin": str(SD_PRICE_MINMAX[0]),
            "SDPriceMax": str(SD_PRICE_MINMAX[1])}


def _ensure_sd_settings(text: str, factions: list) -> tuple:
    """Complete les `FactionSettings` existants (cles SD manquantes, probas a
    0 remontees) et cree les blocs des factions qui n'en ont pas. Les prix
    d'attaque planetaire existants ne sont pas touches."""
    lignes = text.split("\n")
    n, connues = 0, []
    for a, b in reversed(_ecf_blocks(text, r"\{ *Element Name: *FactionSettings")):
        m = next((re.match(r"\s+Faction: *(\w+)", lignes[k])
                  for k in range(a, b + 1)
                  if re.match(r"\s+Faction: *\w+", lignes[k])), None)
        if m is None:
            continue
        fac = m.group(1)
        if fac not in factions:
            continue
        connues.append(fac)
        ajout = []
        for cle, val in _sd_settings_keys(fac).items():
            ki = next((k for k in range(a, b + 1)
                       if re.match(r"\s*" + cle + r"[ \t]*:", lignes[k])), None)
            if ki is None:
                ajout.append("  " + cle + ": " + val)
            elif cle.startswith("SDProbability") and \
                    lignes[ki].split(":", 1)[1].split("#")[0].strip() \
                    in ("0", "0.0"):
                lignes[ki] = "  " + cle + ": " + val
                n += 1
        if ajout:
            lignes[b:b] = ajout
            n += len(ajout)
    manque = [f for f in factions if f not in connues]
    if manque:
        text = "\n".join(lignes).rstrip("\n") + "\n" + "".join(
            _sd_settings_block(f) for f in manque)
        n += len(manque)
    else:
        text = "\n".join(lignes)
    return text, n, manque


def _ensure_sd_units(text: str, factions: list) -> tuple:
    """Un drone + un vaisseau `BaseDefenseOrbitVessel` par faction sans
    renfort spatial. Le moteur choisit selon le prix demande (SDPrice)."""
    lignes = text.split("\n")
    ont = set()
    for a, b in _ecf_blocks(text, r"\{ *Element Name: *Unit"):
        corps = "\n".join(lignes[a:b + 1])
        if "BaseDefenseOrbitVessel" not in corps:
            continue
        m = re.search(r"(?m)^\s+Faction: *(\w+)", corps)
        if m:
            ont.add(m.group(1))
    manque = [f for f in factions if f not in ont]
    if not manque:
        return text, 0, []
    add = ""
    for f in manque:
        classes = {"drone": _SPACE_DRONES.get(f, (_SPACE_DRONE_FALLBACK,))[0],
                   "vessel": _space_ship(f)}
        for quoi, cout in SD_UNITS:
            add += _sd_unit_block(f, classes[quoi], cout)
    return text.rstrip("\n") + "\n" + add, len(manque) * len(SD_UNITS), manque


def _ensure_poi_space_defense(text: str, factions: set) -> tuple:
    """Active la defense des POI spatiaux de faction : ceux qui portent
    `SpaceDefenseOverrideDefaults: True` ET `SpaceDefenseProbability: 0`.
    Les POI sans faction active (Eden_Wreck, Civilian, None...) sont laisses
    tels quels : ce ne sont pas des cibles defensables."""
    lignes = text.split("\n")
    deb = [i for i, ln in enumerate(lignes)
           if re.match(r"^ {0,7}- +(?:Type|Name):", ln)]
    n = 0
    for a, b in reversed(list(zip(deb, deb[1:] + [len(lignes)]))):
        corps = lignes[a:b]
        fac = next((m.group(1) for ln in corps
                    if (m := re.match(r"\s+Faction: +(\w+)", ln))), "")
        if fac not in factions:
            continue
        if not any(re.match(r"\s+SpaceDefenseOverrideDefaults: *True", ln)
                   for ln in corps):
            continue
        ip = next((a + k for k, ln in enumerate(corps)
                   if re.match(r"\s+SpaceDefenseProbability:", ln)), None)
        if ip is None or lignes[ip].split(":", 1)[1].split("#")[0].strip() \
                not in ("0", "0.0"):
            continue
        ind = re.match(r"(\s+)", lignes[ip]).group(1)
        lignes[ip] = ind + "SpaceDefenseProbability: " + str(SPACE_DEFENSE_PROB)
        if not any(re.match(ind + r"SpaceDefensePriceMinMax:", ln) for ln in corps):
            pmin, pmax = SPACE_DEFENSE_POI_PRICE
            lignes.insert(ip + 1, ind + "SpaceDefensePriceMinMax: [ " + str(pmin)
                          + ", " + str(pmax) + " ]")
        n += 1
    return "\n".join(lignes), n


def pass_space_defense(scenario: Path, apply: bool = False, store=None,
                      playfields=None) -> dict:
    """CF.5 : renforts spatiaux par faction (FactionWarfare.ecf) et gate par
    POI dans space_dynamic.yaml."""
    rep = {"id": "space_defense", "edits": 0, "files": 0, "details": []}
    if not SPACE_DEFENSE_ENABLED:
        rep["details"].append("defenses spatiales desactivees")
        return rep
    factions = [f[0] for f in _active_factions()]
    fw = scenario / "Content/Configuration/FactionWarfare.ecf"
    if not fw.is_file():
        rep["details"].append("FactionWarfare.ecf absent")
    else:
        text, eol = read_text_raw(fw)
        text, n1, _ = _ensure_sd_settings(text, factions)
        text, n2, manque = _ensure_sd_units(text, factions)
        if n1 or n2:
            if apply:
                if store:
                    store.snapshot(fw)
                write_text_raw(fw, text, eol)
            rep["files"] += 1
            rep["edits"] += n1 + n2
            rep["details"].append(
                "FactionWarfare : " + str(n1) + " cles SD, "
                + str(n2) + " factions dotees en unites")
    actives = set(factions)
    for pfname in (playfields if playfields is not None
                   else space_playfields(scenario)):
        path = scenario / "Playfields" / pfname / "space_dynamic.yaml"
        if not path.is_file():
            continue
        text, eol = read_text_raw(path)
        text, n = _ensure_poi_space_defense(text, actives)
        if not n:
            continue
        if apply:
            if store:
                store.snapshot(path)
            write_text_raw(path, text, eol)
            purge_playfield_cache(path)
        rep["files"] += 1
        rep["edits"] += n
        rep["details"].append(pfname + " : " + str(n) + " POI defens")
    return rep
