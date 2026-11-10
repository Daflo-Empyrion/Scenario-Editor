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

"""Passes de réalisme IA pour un scénario Empyrion (RE2-FR en cible).

Constat 08/11 (reverse moteur + diff vanille, voir docs/ia_pnj_pistes.md) :
PNJ nerveux mais uniformes ; BAIConfig.ecf et Animations.ecf disparus ;
5 noms de vaisseaux PNJ sans .epb ; pression drone bridée (DroneProb 0 sur
~3000 POIs) en contradiction avec des bases Difficulty 6 ; patrouilles
jamais re-popées ; réputation territoriale à zéro.

Chaque passe = `pass_x(scenario, apply=False, store=None) -> dict` ;
`apply=False` = DRY-RUN (rien d'écrit). Toute écriture passe par
BackupStore (original copié AVANT modification, revert(run_id) intégral).
ECF : chirurgie de lignes en TEXTE BRUT (jamais parse+render — règle du
projet). YAML : yamllite (byte-preserving hors lignes modifiées).

Limites assumées : arbres Behavior Designer compilés dans le jeu (non
modifiables) ; pas de validation en jeu tant que RE2-FR ne charge pas
(NRE connu) — valeurs conservatrices, tout réversible.
"""
import hashlib
import json
import re
import shutil
import time
from pathlib import Path

from core.yamllite.parser import parse_yaml_file
from core.yamllite.model import YamlEntry, create_entry

# ---------------------------------------------------------------------------
# Données (presets — P4.2)
# ---------------------------------------------------------------------------

VESSEL_MAPPING = {
    "R2PVZiraxT0": "R2PV_ZiraxCutter01",
    "R2PVZiraxT1": "R2PV_ZiraxCutter01",
    "R2OPVPolarisT1": "R2OPV_PolarisCutter01",
    "R2OPVLegacyT1": "R2OPV_LegacyInfector01",
    "RE2_OPVBanditT1": "Eden_OPV_BanditRT1_1",
}

BAI_TREES = [
    ("Behaviors/HiLevelTrees/MainAnimal", 40),
    ("Behaviors/HiLevelTrees/ZiraxTroopCommands", 40),
    ("Behaviors/HiLevelTrees/TalonGuardianCommands", 30),
    ("Behaviors/HiLevelTrees/MainCivilian", 25),
    ("Behaviors/HiLevelTrees/TalonBaseAttackMeleeAnimal", 15),
    ("Behaviors/HiLevelTrees/TalonBaseAttackRangedAnimal", 15),
    ("Behaviors/HiLevelTrees/TalonShamanCommands", 10),
    ("Behaviors/HiLevelTrees/AlienBug01", 15),
    ("Behaviors/HiLevelTrees/Telluropod", 5),
    ("Behaviors/AnimalSpecific/ScraperDrone/ScraperDrone", 10),
    ("Behaviors/AnimalSpecific/Fish/Fish", 10),
    ("Behaviors/AnimalSpecific/Butterfly/Butterfly", 5),
    ("Behaviors/AnimalSpecific/AnnoyingMosquito/AnnoyingMosquitoBehaviour", 5),
    ("Behaviors/AnimalSpecific/AlienBug01V2/AlienBug01V2MainAnimal", 10),
    ("Behaviors/AnimalSpecific/Parasaur02/Parasaur02_BasicLifeCycle", 5),
    ("Behaviors/AnimalSpecific/Parasaur02/Parasaur02_Flee", 5),
    ("Behaviors/AnimalSpecific/Parasaur02/Parasaur02_LowAlert", 5),
    ("Behaviors/AnimalSpecific/Raptor02/Raptor02_SearchTarget", 5),
    ("Behaviors/AnimalSpecific/Raptor02/Raptor02_SeePrey", 5),
    ("Behaviors/AnimalSpecific/AlienBug01V2/AlienBug01V2BasicLifeCycle", 5),
    ("Behaviors/AnimalSpecific/AlienBug01V2/AlienBug01V2HasNoTarget", 5),
    ("Behaviors/AnimalSpecific/AlienBug01V2/AlienBug01V2HasTarget", 5),
]
BAI_ACTIVITIES = [
    ("Behaviors/Activities/RandomWalk", 30),
    ("Behaviors/Activities/SearchTarget", 40),
    ("Behaviors/Activities/AnimalAttack", 25),
    ("Behaviors/Activities/BasicLifeCycle", 25),
    ("Behaviors/Activities/HerbivoreFlee", 30),
    ("Behaviors/Activities/HerbivoreLowAlert", 20),
    ("Behaviors/Activities/HerbivoreBabyHideOrRun", 3),
    ("Behaviors/Activities/AnimalBabyPlay", 15),
    ("Behaviors/Activities/HumanoidIdle", 40),
    ("Behaviors/Activities/HumanoidBasicAttack", 40),
    ("Behaviors/Activities/HumanoidStationary", 15),
    ("Behaviors/Activities/HumanoidPatrolLifeCycle", 30),
    ("Behaviors/Activities/HumanoidMeleeAttack", 15),
    ("Behaviors/Activities/AnimalMeleeAttack", 15),
    ("Behaviors/Activities/AnimalOtyughAttack", 5),
    ("Behaviors/Activities/AnimalAttackCreepy", 5),
    ("Behaviors/Activities/CirclingMeleeAttack", 5),
    ("Behaviors/Activities/AttackAlienBug02", 5),
    ("Behaviors/Activities/AttackAlienBug03", 5),
]

ANIMATIONS_ECF = """/* For items with weapon hold type=="X" we have a ray cast delay of Y */
/* name=holdtype, value=delay, param1=holster, param2=unholster */
{ Animation Name: animation
  0: 0, param1: 0, param2: 0 \t   /* block */
  1: 0.16, param1: 0.3, param2: 0.3    /* hand player */
  3: 0.6, param1: 0.3, param2: 0.3    /*  */
  4: 0.65, param1: 0.3, param2: 0.3    /* hand total horror */
  5: 0.6, param1: 0.3, param2: 0.3    /* hand talon guardian */
  6: 0.6, param1: 0.3, param2: 0.3    /* hand zirax melee, cave worm, megalonops */
  14: 0, param1: 0.5, param2: 0.5    /* Player Pistol */
  15: 0, param1: 0.5, param2: 0.5    /* Player Rifle */
  16: 0, param1: 0.5, param2: 0.5    /* Player Rifle + weaker shooting animation */
  20: 0, param1: 0.0, param2: 0.0    /* Animation driven animals */
}
"""

ARCHETYPES = {
    "sentry": {
        "VisionSensor": {"VisibleDistance": "110", "ViewAngle": "110"},
        "AlertSensor": {"NoiseMaxDistance": "65", "NoiseAlertMultiplier": "0.8",
                        "AlertLevelDrop": "10"},
    },
    "ambush": {
        "VisionSensor": {"VisibleDistance": "40", "ViewAngle": "90"},
        "AlertSensor": {"NoiseMaxDistance": "45", "NoiseAlertMultiplier": "1.2",
                        "AlertLevelDrop": "15"},
    },
    "scout": {
        "VisionSensor": {"VisibleDistance": "80", "ViewAngle": "140"},
        "AlertSensor": {"NoiseMaxDistance": "90", "NoiseAlertMultiplier": "1.2",
                        "AlertLevelDrop": "6"},
    },
    "prey": {
        "VisionSensor": {"VisibleDistance": "60", "ViewAngle": "200"},
        "AlertSensor": {"NoiseMaxDistance": "60", "NoiseAlertMultiplier": "1.0",
                        "AlertFromFriendDeath": "100"},
    },
    "tank": {
        "VisionSensor": {"VisibleDistance": "50", "ViewAngle": "270"},
        "AlertSensor": {"NoiseMaxDistance": "50", "NoiseAlertMultiplier": "0.3",
                        "AlertLevelDrop": "20"},
    },
}
ARCHETYPE_TEMPLATES = {
    "PredatorBAITemplate": "sentry",
    "PreyBAITemplate": "prey",
    "AlienTemplateBAI": "sentry",
    "CivilianTemplate": "scout",
    "PredatorTemplate": "ambush",
    "CaveWormGrey": "ambush",
}
ARCHETYPE_ENTITIES = {
    "ZiraxMinigun": "sentry", "ZiraxMale": "sentry", "ZiraxRocket": "sentry",
    "ZiraxLaser": "sentry", "ZiraxSniper": "scout", "ZiraxShotgun": "ambush",
    "AssaultCyborg": "sentry", "AssaultCyborgCommando": "sentry",
    "GolemIce": "tank", "GolemDesert": "tank", "GolemSwamp": "tank",
    "ArmoredGolemSmallGreen": "tank", "ArmoredGolemSmallRed": "tank",
    "ArmoredGolemSmallCyan": "tank",
    "Crawler": "ambush", "CaveWormGreen": "ambush", "CaveWormWhite": "ambush",
    "Oviraptor": "prey", "Parasaur": "prey", "Parasaur02": "prey",
    "LizardMule": "prey", "Pangolin": "prey",
    "Raptor": "scout", "Raptor02": "scout", "Spinosaurus": "ambush",
    "TalonGuardian": "sentry", "TalonGuardianShamanBaseAttack": "sentry",
    "MegalonopsBrown": "ambush", "MegalonopsGrey": "scout",
    "Slime": "ambush", "SlimeWhite": "ambush", "Otyugh": "ambush",
    "Creepy": "ambush", "Overseer": "sentry", "GlidingOverseer": "scout",
    "TotalHorror": "ambush", "WoodWalker": "tank",
    "Eden_AlienBugQueen": "tank",
}

HERD_LEADERS = {
    "Raptor": (1, 6), "Raptor02": (1, 6), "Oviraptor": (1, 6),
    "Parasaur": (1, 5), "Parasaur02": (1, 5), "LizardMule": (1, 5),
    "ZiraxMinigun": (2, 5), "ZiraxMale": (1, 4), "ZiraxLaser": (2, 4),
    "TalonGuardian": (2, 5), "Telluropod": (1, 4),
}
HUNTING_ADD = ["Spinosaurus", "MegalonopsBrown", "AlienBug02", "AlienBug03",
               "WoodWalker", "TotalHorror"]
SCAVENGER_ADD = ["MegalonopsGrey", "Otyugh", "Creepy", "Slime", "SlimeWhite"]
# P1.4 : cri de détection — la valeur est le SfxAlert RÉEL de l'entité (ou de
# son template Ref:), jamais un nom inventé : les sons sont des CHEMINS
# d'assets ('Enemies/Crawler/Crawler_SfxRandom'), un nom nu est introuvable.
SFX_SENSE = ["Raptor", "Raptor02", "Spinosaurus", "Crawler", "ZiraxMale"]
NIGHT_SPEEDS = ["Crawler", "Oviraptor", "Parasaur", "Parasaur02",
                "LizardMule", "Pangolin", "MegalonopsBrown", "Otyugh"]

TIER_GROUP = {0: "early", 1: "early", 3: "mid", 5: "mid", 6: "high", 7: "high"}
TIER_CURVES = {
    #          DroneProb(si 0)  Reserve(si 0)  TroopTransport  ambient [0,0]->?
    "early": (None, None, False, None),
    "mid": ("0.3", "2", False, None),
    "high": ("0.5", "5", "33%", ("1", "2")),
}

REPOP_PATROL = ("240", "360")
REPOP_LOCAL_PREDATOR = ("300", "480")
PATROL_PATTERNS = ("Patrol", "BattleGroup", "Battle")
LOCALIZED_PREDATORS = ("Golem", "Megalonops", "WormDesert", "AlienBug",
                       "Spinosaurus", "Telluropod")

NEW_GROUPS = {
    "TalonGuardianPatrolFew": {"TalonGuardian": '"1, 2"',
                               "TalonGuardianInfectedBlue": '"0, 1"'},
    "PolarisDronePatrol": {"Eden_PolarisMiningDrone": '"1, 2"',
                           "Eden_PolarisSalvageDrone": '"1, 2"'},
    "PirateHoverPatrol": {"DroneHoverZiraxLaser": '"1, 1"',
                          "DroneHoverZiraxRocket": '"1, 1"'},
    "RaptorsFew": {"Raptor": '"1, 2"'},
    "OviraptorsFew": {"Oviraptor": '"1, 2"'},
    "ParasaursFew": {"Parasaur": '"1, 2"'},
}
GROUP_REFERENCES = {
    "TalonGuardianPatrolFew": {
        "playfields": ["EdenTropical2", "EdenJungle_V2", "Temperate_V2"],
        "amount": "2", "delay": "[60, 80]"},
    "PolarisDronePatrol": {
        "playfields": ["BarrenMetal", "Barren"],
        "amount": "2", "delay": "[60, 80]"},
    "PirateHoverPatrol": {
        "playfields": ["DesertBurnt", "EdenDesertPummeled"],
        "amount": "2", "delay": "[60, 80]"},
    "RaptorsFew": {"playfields": ["EdenDesertKharak", "EdenAridMesa"],
                   "amount": "1", "delay": "[60, 80]"},
    "OviraptorsFew": {"playfields": ["EdenDesertOasis_V2"],
                      "amount": "1", "delay": "[60, 80]"},
    "ParasaursFew": {"playfields": ["EdenSwampMire", "TemperateSwamp"],
                     "amount": "1", "delay": "[60, 80]"},
}

PV_IMMOBILE_PLAYFIELDS = ["Arid_V2", "Alien", "EdenDesertKharak"]

AQUATIC_GROUPS = ["Slimes", "SlimesWhite", "Otyughs", "MegalonopsesBrown",
                  "MegalonopsesGrey", "LizardMuleHerd"]
WET_BIOMES = ("swamp", "marsh", "ocean", "lake", "water", "oasis", "river")

REPUTATION_FIX = {
    # valeurs des lignes vanilla COMMENTÉES dans DefReputation.ecf lui-même
    "StructSpawnedInTerritory": ' -1000,  -300,   -400,    -500,  -1000,      0,      -100, -1000,   -800,    -500,  -800,    -400,    -1000,   -500,  -1500,        -1000,   -500',
    "StructStayInTerritory": '  -25,   -50,       0,     -50,    -75,      0,       -25,  -25,     -25,     -25,   -25,     -25,     -25,    -25,    -25,           -30,    -30',
}


# ---------------------------------------------------------------------------
# Backups
# ---------------------------------------------------------------------------

class BackupStore:
    """Copie l'original AVANT la première modification de chaque fichier
    (par run) ; revert() restaure tout le run."""

    def __init__(self, scenario: Path, run_id: str | None = None):
        self.scenario = Path(scenario)
        ts = time.strftime("%Y%m%d_%H%M%S")
        self.run_id = run_id or ts
        self.root = self.scenario.parent / (self.scenario.name + "_ai_backups") / self.run_id
        self.manifest_path = self.root / "manifest.json"
        self.files: dict = {}
        if self.manifest_path.exists():
            self.files = json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def snapshot(self, path: Path) -> None:
        rel = str(Path(path).relative_to(self.scenario)).replace("\\", "/")
        if rel in self.files:
            return
        dest = self.root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        self.files[rel] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        self.manifest_path.write_text(json.dumps(self.files, indent=1), encoding="utf-8")

    def revert(self) -> int:
        n = 0
        for rel in self.files:
            dest = self.root / rel
            if dest.exists():
                shutil.copy2(dest, self.scenario / rel)
                n += 1
        return n


# ---------------------------------------------------------------------------
# Lecture/écriture avec préservation des fins de ligne. RE2-FR est CRLF ;
# Path.read_text (newlines universels) + write_bytes convertissait TOUT le
# fichier en LF (vécu 08/11 : 62 fichiers). Chirurgie sur texte normalisé
# en LF, puis ré-encodage avec l EOL d origine du fichier.
# ---------------------------------------------------------------------------

def read_text_raw(path: Path) -> tuple:
    raw = Path(path).read_bytes()
    eol = "\r\n" if b"\r\n" in raw else "\n"
    # normalise aussi les \r\r\n (dégâts de double conversion) et les \r isolés
    text = raw.decode("utf-8", errors="replace")
    text = re.sub(r"\r+\n", "\n", text).replace("\r", "\n")
    return text, eol


def write_text_raw(path: Path, text: str, eol: str) -> None:
    if eol == "\r\n":
        # idempotent : répare \r\r\n et LF seuls au passage
        text = re.sub(r"\r*\n", "\r\n", text)
    Path(path).write_bytes(text.encode("utf-8"))


# ---------------------------------------------------------------------------
# Helpers ECF (texte brut)
# ---------------------------------------------------------------------------

def entity_spans(text: str) -> dict:
    spans = {}
    for m in re.finditer(r"\{ \+?Entity Name:\s*(\w+)", text):
        depth = 0
        end = len(text)
        for mm in re.finditer(r"[{}]", text[m.start():]):
            depth += 1 if mm.group() == "{" else -1
            if depth == 0:
                end = m.start() + mm.end()
                break
        spans[m.group(1)] = (m.start(), end)
    return spans


def child_span(block: str, prefix: str) -> tuple | None:
    m = re.search(r"\{\s*Child\s+" + prefix + r"\b", block)
    if not m:
        return None
    depth = 0
    for mm in re.finditer(r"[{}]", block[m.start():]):
        depth += 1 if mm.group() == "{" else -1
        if depth == 0:
            return (m.start(), m.start() + mm.end())
    return None


def _set_in_span(text: str, span: tuple, prop: str, new_value: str):
    s, e = span
    block = text[s:e]
    pat = re.compile(rf"(?m)^([ \t]*)({re.escape(prop)}):[ \t]*[^#\n]*?(#[^\n]*)?[ \t]*$")
    m = pat.search(block)
    if not m:
        return text, 0
    indent, comment = m.group(1), m.group(3) or ""
    current = m.group(0)[len(indent) + len(prop) + 1:]
    current = current.split("#", 1)[0].strip()
    if current == str(new_value).strip():
        return text, 0
    repl = f"{indent}{prop}: {new_value}" + (("  " + comment) if comment else "")
    block = block[:m.start()] + repl + block[m.end():]
    return text[:s] + block + text[e:], 1


def set_entity_prop(text: str, entity: str, prop: str, new_value: str,
                    child: str | None = None):
    spans = entity_spans(text)
    if entity not in spans:
        return text, 0
    s, e = spans[entity]
    block = text[s:e]
    if child:
        inner = child_span(block, child)
        if not inner:
            return text, 0
        span = (s + inner[0], s + inner[1])
    else:
        span = (s, e)
    return _set_in_span(text, span, prop, new_value)


def add_entity_lines(text: str, entity: str, lines: list,
                     child: str | None = None, child_comment: str = ""):
    """Insère des lignes 'Prop: valeur' dans l'entité (racine ou enfant
    { Child X, créé si absent). Retourne (text, nb)."""
    spans = entity_spans(text)
    if entity not in spans:
        return text, 0
    s, e = spans[entity]
    block = text[s:e]
    if child:
        cspan = child_span(block, child)
        if cspan:
            cs, ce = cspan
            inner = block[cs:ce]
            m = re.search(r"(?m)^([ \t]+)\w+:", inner[inner.find("\n") + 1:])
            ind_prop = m.group(1) if m else "  "
            add = "".join(f"{ind_prop}{ln}\n" for ln in lines)
            insert_at = ce - 1  # avant le '}' fermant du child
            block = block[:insert_at] + add + block[insert_at:]
        else:
            m_root = re.search(r"(?m)^([ \t]+)\w+:", block)
            ind_root = m_root.group(1) if m_root else "  "
            ind_prop = ind_root + "  "
            ind_child = ind_root[:-1] if len(ind_root) > 1 else " "
            child_text = (f"{ind_child}{{ Child {child}"
                          + (f"   # {child_comment}" if child_comment else "")
                          + "\n"
                          + "".join(f"{ind_prop}{ln}\n" for ln in lines)
                          + f"{ind_child}}}\n")
            close = block.rfind("}")
            block = block[:close] + child_text + block[close:]
    else:
        m_root = re.search(r"(?m)^([ \t]+)\w+:", block)
        ind_prop = m_root.group(1) if m_root else "  "
        add = "".join(f"{ind_prop}{ln}\n" for ln in lines)
        close = block.rfind("}")
        block = block[:close] + add + block[close:]
    return text[:s] + block + text[e:], len(lines)


# ---------------------------------------------------------------------------
# Helpers YAML
# ---------------------------------------------------------------------------

def find_child(entry, key):
    for c in entry.children:
        if isinstance(c, YamlEntry) and c.key == key:
            return c
    return None


def find_root(doc, key):
    for n in doc.nodes:
        if isinstance(n, YamlEntry) and n.key == key:
            return n
    return None


def seq_children(node):
    return [c for c in node.children if isinstance(c, YamlEntry)]


def item_val(e, key: str) -> str:
    """Valeur d'une clé portée par l'item de séquence LUI-MÊME (item.key == key,
    ex: '- Names: [X, Y]') ou par un de ses enfants directs."""
    if e is None:
        return ""
    if e.key == key:
        return e.value or ""
    c = find_child(e, key)
    return (c.value or "") if c is not None else ""


def _sib_eol(entry) -> str:
    for c in entry.children:
        if isinstance(c, YamlEntry):
            return c.eol
    return entry.eol or "\n"


def edit_yaml(path: Path, mutator, store: "BackupStore | None" = None,
              write: bool = True) -> int:
    """Applique mutator(doc)->nb_modifs ; écrit SEULEMENT si write et n>0,
    après snapshot du store."""
    doc = parse_yaml_file(str(path))
    n = mutator(doc) or 0
    if n > 0 and write:
        if store:
            store.snapshot(path)
        Path(path).write_bytes(doc.render().encode("utf-8"))
    return n


# ---------------------------------------------------------------------------
# Lectures d'état
# ---------------------------------------------------------------------------

def playfield_tier(pf_file: Path) -> str | None:
    """Tier via Difficulty du DroneBaseSetup.Random (early/mid/high)."""
    doc = parse_yaml_file(str(pf_file))
    dbs = find_root(doc, "DroneBaseSetup")
    if not dbs:
        return None
    rnd = find_child(dbs, "Random")
    if not rnd:
        return None
    for item in seq_children(rnd):
        bases = [item] if item.key is not None else seq_children(item)
        for e in bases:
            c = find_child(e, "Difficulty")
            if c is not None and c.value:
                try:
                    return TIER_GROUP.get(int(c.value))
                except ValueError:
                    return None
    return None


def static_playfields(scenario: Path):
    return sorted((scenario / "Playfields").glob("*/playfield_static.yaml"))


# ---------------------------------------------------------------------------
# PASSES
# ---------------------------------------------------------------------------

def pass_vessel_mapping(scenario: Path, apply: bool = False, store=None) -> dict:
    rep = {"pass": "vessel_mapping", "files": 0, "edits": 0, "details": []}
    for pf in sorted((scenario / "Playfields").glob("*/*.yaml")):
        if pf.name not in ("playfield_static.yaml", "space_dynamic.yaml"):
            continue
        text, eol = read_text_raw(pf)
        n = 0
        for old, new in VESSEL_MAPPING.items():
            pat = re.compile(rf"(?m)^(\s*-\s*Name:\s*){re.escape(old)}(\s*)$")
            text, k = pat.subn(rf"\g<1>{new}\g<2>", text)
            n += k
        if n:
            rep["files"] += 1
            rep["edits"] += n
            rep["details"].append(f"{pf.parent.name}: {n}")
            if apply:
                if store:
                    store.snapshot(pf)
                write_text_raw(pf, text, eol)
    return rep


def pass_baiconfig(scenario: Path, apply: bool = False, store=None) -> dict:
    rep = {"pass": "baiconfig", "files": 0, "edits": 0, "details": []}
    target = scenario / "Content" / "Configuration" / "BAIConfig.ecf"
    if target.exists():
        rep["details"].append("existe déjà — rien à faire")
        return rep
    parts = [
        "// Pools de behavior trees precharges (genere par ai_realism le "
        + time.strftime("%d/%m/%Y") + " ;",
        "// counts calques vanille 1.19.1, modulés par l'usage RE2 mesuré 08/11)",
        "",
        "//  ***************************************************** ",
        "//  ***************     HI LEVEL    ********************* ",
        "//  ***************************************************** ",
        "",
    ]
    for name, count in BAI_TREES:
        parts += ["{ Element Name: BehaviorPoolPreload", f'  Name: "{name}"',
                  f"  Count: {count}", "}", ""]
    parts += ["//  ***************************************************** ",
              "//  **************    ACTIVITIES    ********************* ",
              "//  ***************************************************** ",
              ""]
    for name, count in BAI_ACTIVITIES:
        parts += ["{ Element Name: BehaviorPoolPreload", f'  Name: "{name}"',
                  f"  Count: {count}", "}", ""]
    rep["files"] = 1
    rep["edits"] = 1
    rep["details"].append(f"{len(BAI_TREES)} arbres + {len(BAI_ACTIVITIES)} activities")
    if apply:
        write_text_raw(target, "\n".join(parts), "\r\n")
    return rep


def pass_animations(scenario: Path, apply: bool = False, store=None) -> dict:
    rep = {"pass": "animations", "files": 0, "edits": 0, "details": []}
    target = scenario / "Content" / "Configuration" / "Animations.ecf"
    if target.exists():
        rep["details"].append("existe déjà — rien à faire")
        return rep
    rep["files"] = 1
    rep["edits"] = 1
    rep["details"].append("table vanille (hold types NPC 0/14/15/20 couverts)")
    if apply:
        write_text_raw(target, ANIMATIONS_ECF, "\r\n")
    return rep


def _make_tier_mutator(tier: str):
    dp, reserve, tt, ambient = TIER_CURVES[tier]

    def mut(doc) -> int:
        n = 0
        pois = find_root(doc, "POIs")
        if pois is not None:
            rnd = find_child(pois, "Random")
            for item in seq_children(rnd) if rnd else []:
                bases = [item] if item.key is not None else seq_children(item)
                for e in bases:
                    if dp is not None:
                        c = find_child(e, "DroneProb")
                        if c is not None and c.value.strip() in ("0", "0.0"):
                            c.value, c.dirty = dp, True
                            n += 1
                    if reserve is not None:
                        c = find_child(e, "ReserveCount")
                        if c is not None and c.value.strip() == "0":
                            c.value, c.dirty = reserve, True
                            n += 1
                    if tt:
                        c = find_child(e, "TroopTransport")
                        if c is not None and c.value.strip() == "False":
                            seed = (item_val(e, "GroupName")
                                    or item_val(e, "Type")) + e.raw[:20]
                            if int(hashlib.md5(seed.encode()).hexdigest(), 16) % 100 < 33:
                                c.value, c.dirty = "True", True
                                n += 1
        if ambient:
            ds = find_root(doc, "DroneSpawning")
            if ds is not None:
                rnd = find_child(ds, "Random")
                for item in seq_children(rnd) if rnd else []:
                    bases = [item] if item.key is not None else seq_children(item)
                    for e in bases:
                        d = find_child(e, "DronesMinMax")
                        if d is not None and d.value.replace(" ", "") in ("[0,0]", "[0,0]"):
                            d.value = f"[{ambient[0]}, {ambient[1]}]"
                            d.dirty = True
                            n += 1
        return n
    return mut


def pass_tier_curves(scenario: Path, apply: bool = False, store=None) -> dict:
    rep = {"pass": "tier_curves", "files": 0, "edits": 0, "details": []}
    for pf in static_playfields(scenario):
        tier = playfield_tier(pf)
        if tier is None:
            continue
        n = edit_yaml(pf, _make_tier_mutator(tier), store if apply else None,
                      write=apply)
        if n:
            rep["files"] += 1
            rep["edits"] += n
            rep["details"].append(f"{pf.parent.name} [{tier}]: {n}")
    return rep


def _make_repop_mutator():
    def mut(doc) -> int:
        n = 0
        cs = find_root(doc, "CreatureSpawning")
        if cs is not None:
            for biome in seq_children(cs):
                ents = find_child(biome, "Entities")
                for e in seq_children(ents) if ents else []:
                    nmv = item_val(e, "Name") or item_val(e, "Names")
                    d = find_child(e, "DelayMinMax")
                    if d is None:
                        continue
                    if d.value.replace(" ", "") == "[-1,-1]" and any(
                            p in nmv for p in LOCALIZED_PREDATORS):
                        d.value = f"[{REPOP_LOCAL_PREDATOR[0]}, {REPOP_LOCAL_PREDATOR[1]}]"
                        d.dirty = True
                        n += 1
        szs = find_root(doc, "SpawnZones")
        if szs is not None:
            for zone in seq_children(szs):
                ents = find_child(zone, "Entities")
                for e in seq_children(ents) if ents else []:
                    nmv = item_val(e, "Names")
                    d = find_child(e, "DelayMinMax")
                    if d is None:
                        continue
                    if d.value.replace(" ", "") == "[-1,-1]" and any(
                            p in nmv for p in PATROL_PATTERNS):
                        d.value = f"[{REPOP_PATROL[0]}, {REPOP_PATROL[1]}]"
                        d.dirty = True
                        n += 1
        return n
    return mut


def pass_repop(scenario: Path, apply: bool = False, store=None) -> dict:
    rep = {"pass": "repop", "files": 0, "edits": 0, "details": []}
    for pf in static_playfields(scenario):
        n = edit_yaml(pf, _make_repop_mutator(), store if apply else None,
                      write=apply)
        if n:
            rep["files"] += 1
            rep["edits"] += n
            rep["details"].append(f"{pf.parent.name}: {n}")
    return rep


def pass_archetypes(scenario: Path, apply: bool = False, store=None) -> dict:
    rep = {"pass": "archetypes", "files": 0, "edits": 0, "details": []}
    path = scenario / "Content" / "Configuration" / "EClassConfig.ecf"
    text, eol = read_text_raw(path)
    new_text = text
    total = 0
    applied = []
    for target_name, arch in (list(ARCHETYPE_TEMPLATES.items())
                              + list(ARCHETYPE_ENTITIES.items())):
        preset = ARCHETYPES.get(arch)
        if not preset:
            continue
        n = 0
        for child, props in preset.items():
            for prop, value in props.items():
                new_text, k = set_entity_prop(new_text, target_name, prop,
                                              value, child=child)
                n += k
        if n:
            applied.append(f"{target_name}={arch}:{n}")
            total += n
    rep["edits"] = total
    rep["details"] = applied
    if total:
        rep["files"] = 1
        if apply:
            if store:
                store.snapshot(path)
            write_text_raw(path, new_text, eol)
    return rep


def _entity_sound(text: str, entity: str, depth: int = 0) -> str | None:
    """SfxAlert (sinon SfxRandom) de l'entité, en remontant le Ref: si absent."""
    spans = entity_spans(text)
    if entity not in spans or depth > 4:
        return None
    s, e = spans[entity]
    body = text[s:e]
    for key in ("SfxAlert", "SfxRandom"):
        m = re.search(rf"(?m)^\s*{key}:\s*([^\s#]+)", body)
        if m:
            return m.group(1)
    ref = re.match(r"\{ \+?Entity Name:\s*\w+,\s*Ref:\s*(\w+)", body)
    return _entity_sound(text, ref.group(1), depth + 1) if ref else None


def pass_behaviors(scenario: Path, apply: bool = False, store=None) -> dict:
    """P1.2-P1.5 : chefs de groupe, chasse/charogne, SfxSense, vitesses nuit."""
    rep = {"pass": "behaviors", "files": 0, "edits": 0, "details": []}
    path = scenario / "Content" / "Configuration" / "EClassConfig.ecf"
    text, eol = read_text_raw(path)
    new_text = text
    total = 0
    counts = {}

    def body_of(ent):
        spans = entity_spans(new_text)
        return new_text[spans[ent][0]:spans[ent][1]] if ent in spans else ""

    for ent, (prio, maxg) in HERD_LEADERS.items():
        if ent not in entity_spans(new_text):
            continue
        if "GroupLeaderPriority:" not in body_of(ent):
            new_text, k = add_entity_lines(new_text, ent,
                                           [f"GroupLeaderPriority: {prio}",
                                            f"MaxCountInGroup: {maxg}"])
            total += k
        if "TickIfLead" not in body_of(ent):
            new_text, k = add_entity_lines(new_text, ent, ["TickIfLead: True"],
                                           child="GroupDirectionSensor")
            total += k
    for ent in HUNTING_ADD:
        if ent in entity_spans(new_text) and "IsHunting" not in body_of(ent):
            new_text, k = add_entity_lines(new_text, ent, ["IsHunting: 100"],
                                           child="Hints", child_comment="predation")
            total += k
    for ent in SCAVENGER_ADD:
        if ent in entity_spans(new_text) and "IsScavenger" not in body_of(ent):
            new_text, k = add_entity_lines(new_text, ent, ["IsScavenger: True"],
                                           child="Hints", child_comment="charogne")
            total += k
    for ent in SFX_SENSE:
        if ent not in entity_spans(new_text):
            continue
        sfx = _entity_sound(new_text, ent)
        body = body_of(ent)
        m = re.search(r"(?m)^\s*SfxSense:\s*([^\s#]+)", body)
        if not sfx:
            # aucun son réel : retire une valeur nue posée par un run antérieur
            if m is not None and "/" not in m.group(1):
                s, e = entity_spans(new_text)[ent]
                block = re.sub(r"(?m)^[ \t]*SfxSense:[ \t]*[^\s#/]+[ \t]*\r?\n",
                               "", new_text[s:e], count=1)
                new_text = new_text[:s] + block + new_text[e:]
                total += 1
            continue
        if m is None:
            new_text, k = add_entity_lines(new_text, ent, [f"SfxSense: {sfx}"])
            total += k
        elif "/" not in m.group(1):
            # réparation : un nom nu (sans chemin d'asset) est introuvable
            new_text, k = set_entity_prop(new_text, ent, "SfxSense", sfx)
            total += k
    for ent in NIGHT_SPEEDS:
        if ent not in entity_spans(new_text):
            continue
        body = body_of(ent)
        lines = []
        if "NightWanderSpeed:" not in body:
            lines.append("NightWanderSpeed: 0.4")
        if "NightApproachSpeed:" not in body:
            lines.append("NightApproachSpeed: 1.2")
        if lines:
            new_text, k = add_entity_lines(new_text, ent, lines)
            total += k
    rep["edits"] = total
    if total:
        rep["files"] = 1
        if apply:
            if store:
                store.snapshot(path)
            write_text_raw(path, new_text, eol)
    return rep


def pass_faction_groups(scenario: Path, apply: bool = False, store=None) -> dict:
    """P3.1/P3.2 : nouveaux groupes (patrouilles + hardes Few) dans
    EGroupsConfig + références dans les playfields cibles."""
    rep = {"pass": "faction_groups", "files": 0, "edits": 0, "details": []}
    groups_path = scenario / "Content" / "Configuration" / "EGroupsConfig.ecf"
    text, eol_groups = read_text_raw(groups_path)
    existing = set(re.findall(r"\{ \+?E?Group Name:\s*(\w+)", text))
    new_text = text
    added = []
    for name, members in NEW_GROUPS.items():
        if name in existing:
            continue
        block = "{ EGroup Name: " + name + "\n"
        for ent, rng in members.items():
            block += f"  {ent}: {rng}\n"
        block += "}\n\n"
        new_text += block
        added.append(name)
    if added:
        rep["edits"] += len(added)
        rep["details"].append("EGroups + " + ", ".join(added))
        rep["files"] += 1
        if apply:
            if store:
                store.snapshot(groups_path)
            write_text_raw(groups_path, new_text, eol_groups)

    def make_ref_mutator(group, spec):
        def mut(doc) -> int:
            cs = find_root(doc, "CreatureSpawning")
            if cs is None:
                return 0
            biomes = seq_children(cs)
            if not biomes:
                return 0
            biome = biomes[0]
            ents = find_child(biome, "Entities")
            if ents is None:
                return 0
            # évite les doublons
            for e in seq_children(ents):
                if (item_val(e, "Name") or item_val(e, "Names")) == group:
                    return 0
            items = seq_children(ents)
            eol = _sib_eol(ents)
            ind = items[0].indent if items else "      "
            # propriétés d'un item : 1er enfant non-séquence de l'item existant
            prop_ind = ind + "  "
            for it in items:
                subs = seq_children(it)
                if subs:
                    prop_ind = subs[0].indent
                    break
            ents.children.append(create_entry("Name", group, indent=ind,
                                              is_sequence_item=True, eol=eol))
            for k, v in (("Amount", spec["amount"]),
                         ("DelayMinMax", spec["delay"]),
                         ("Period", "Always")):
                ents.children.append(create_entry(k, v, indent=prop_ind, eol=eol))
            return 1
        return mut

    for group, spec in GROUP_REFERENCES.items():
        for pfname in spec["playfields"]:
            pf = scenario / "Playfields" / pfname / "playfield_static.yaml"
            if not pf.exists():
                continue
            n = edit_yaml(pf, make_ref_mutator(group, spec),
                          store if apply else None, write=apply)
            if n:
                rep["files"] += 1
                rep["edits"] += n
                rep["details"].append(f"{pfname} <- {group}")
    return rep


def pass_space_missions(scenario: Path, apply: bool = False, store=None) -> dict:
    """P3.3 : 1er PlanetVessel de certains playfields -> ImmobileTask (dérive)."""
    rep = {"pass": "space_missions", "files": 0, "edits": 0, "details": []}

    def mut(doc) -> int:
        dbs = find_root(doc, "DroneBaseSetup")
        if dbs is None:
            return 0
        pvs = find_child(dbs, "PlanetVessels")
        if pvs is None:
            return 0
        items = seq_children(pvs)
        if not items:
            return 0
        first = items[0]
        if first.key is None:
            subs = seq_children(first)
            if not subs:
                return 0
            first = subs[0]
        # NewPlanetVessel.Immobile n'existe pas -> YamlException au chargement
        # du playfield ; la propriété moteur est ImmobileTask (FixedSpaceVessel
        # spatiale garde Immobile).
        if find_child(first, "ImmobileTask") is not None:
            return 0
        patrol = find_child(first, "RangePatrolTask")
        if patrol is None:
            return 0
        ref = find_child(patrol, "POINameAsPositionRef")
        patrol.dirty = True
        patrol.key = "ImmobileTask"
        patrol.value = ""
        patrol.children = [c for c in patrol.children
                           if not (isinstance(c, YamlEntry) and c.key in
                                   ("Radius", "DistToGround",
                                    "RangePatrolAvoidArea",
                                    "IsAllowToReturnToBaseWhenOver"))]
        if ref is None:
            from core.yamllite.model import create_entry
            patrol.children.append(create_entry(
                "POINameAsPositionRef", '""',
                indent=patrol.indent + "  ", eol=patrol.eol))
        return 1

    for pfname in PV_IMMOBILE_PLAYFIELDS:
        pf = scenario / "Playfields" / pfname / "playfield_static.yaml"
        if not pf.exists():
            continue
        n = edit_yaml(pf, mut, store if apply else None, write=apply)
        if n:
            rep["files"] += 1
            rep["edits"] += n
            rep["details"].append(pfname)
    return rep


def pass_aquatic(scenario: Path, apply: bool = False, store=None) -> dict:
    """P3.4 : AllowInWater pour espèces semi-aquatiques en biomes humides."""
    rep = {"pass": "aquatic", "files": 0, "edits": 0, "details": []}

    def mut(doc) -> int:
        n = 0
        cs = find_root(doc, "CreatureSpawning")
        if cs is None:
            return 0
        for biome in seq_children(cs):
            bname = biome.value or ""
            if biome.key != "Biomes":
                b = find_child(biome, "Biomes")
                bname = (b.value if b is not None else "") or ""
            if not any(w in bname.lower() for w in WET_BIOMES):
                continue
            ents = find_child(biome, "Entities")
            for e in seq_children(ents) if ents else []:
                nmv = item_val(e, "Name") or item_val(e, "Names")
                if nmv not in AQUATIC_GROUPS:
                    continue
                if find_child(e, "AllowInWater") is None:
                    e.children.append(create_entry(
                        "AllowInWater", "True",
                        indent=e.indent + "  " if e.key else e.indent,
                        eol=_sib_eol(e)))
                    n += 1
        return n

    for pf in static_playfields(scenario):
        n = edit_yaml(pf, mut, store if apply else None, write=apply)
        if n:
            rep["files"] += 1
            rep["edits"] += n
            rep["details"].append(f"{pf.parent.name}: {n}")
    return rep


def pass_reputation(scenario: Path, apply: bool = False, store=None) -> dict:
    """P3.5 : réputation territoriale (valeurs vanilla du fichier) + chasse."""
    rep = {"pass": "reputation", "files": 0, "edits": 0, "details": []}
    path = scenario / "Content" / "Configuration" / "DefReputation.ecf"
    text, eol_rep = read_text_raw(path)
    # BORNÉ au bloc "Action.Reputation" : les blocs *.Rivalry ont aussi des
    # lignes StructSpawnedInTerritory à zéro, de sens différent (vécu 08/11 :
    # un re-run non borné aurait écrasé Talon.Rivalry)
    mb = re.search(r'\{ Reputation Name: "Action\.Reputation"', text)
    if not mb:
        rep["details"].append("bloc Action.Reputation introuvable")
        return rep
    end = text.find(chr(10) + "}", mb.end())
    end = len(text) if end == -1 else end + 2
    head, block, tail = text[:mb.start()], text[mb.start():end], text[end:]
    new_text = block
    n = 0
    for action, vector in REPUTATION_FIX.items():
        pat = re.compile(rf"(?m)^([ \t]*)({action}:[ \t]*)" + r'"[0 ,]+"([ \t]*#.*)?$')
        m = pat.search(new_text)
        if m:
            new_text = (new_text[:m.start()] + f"{m.group(1)}{action}:   \"{vector}\""
                        + (m.group(3) or "") + new_text[m.end():])
            n += 1
    # chasse au prédateur rémunérée (1re colonne = Zirax 0 -> 0.1)
    m = re.search(r'(?m)^([ \t]*)(AttackedPrey:[ \t]*)"([^"]*)"(.*)$', new_text)
    if m:
        vals = m.group(3).split(",")
        if vals and vals[0].strip() == "0":
            vals[0] = "  0.1"
            new_text = (new_text[:m.start()] + f"{m.group(1)}{m.group(2)}\""
                        + ",".join(vals) + "\"" + m.group(4) + new_text[m.end():])
            n += 1
    rep["edits"] = n
    if n:
        rep["files"] = 1
        if apply:
            if store:
                store.snapshot(path)
            write_text_raw(path, head + new_text + tail, eol_rep)
    return rep


# ---------------------------------------------------------------------------
# Audit (P4.1)
# ---------------------------------------------------------------------------

def run_audit(scenario: Path) -> list:
    findings = []
    epb = {p.stem for p in scenario.glob("Prefabs/**/*.epb")}
    bad_vessels = set()
    for pf in (scenario / "Playfields").glob("*/*.yaml"):
        if pf.name not in ("playfield_static.yaml", "space_dynamic.yaml"):
            continue
        txt = pf.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"(?m)^\s*-\s*Name:\s*(\w+)\s*$", txt):
            if m.group(1) in VESSEL_MAPPING and m.group(1) not in epb:
                bad_vessels.add(m.group(1))
    if bad_vessels:
        findings.append({"id": "vessels", "severity": "critical",
                         "count": len(bad_vessels),
                         "message": "vaisseaux PNJ sans .epb (correctif: vessel_mapping)",
                         "sample": sorted(bad_vessels)[:5]})
    cfg = scenario / "Content" / "Configuration"
    if not (cfg / "BAIConfig.ecf").exists():
        findings.append({"id": "baiconfig", "severity": "warn", "count": 1,
                         "message": "BAIConfig.ecf absent — pools non préchargés"})
    if not (cfg / "Animations.ecf").exists():
        findings.append({"id": "animations", "severity": "warn", "count": 1,
                         "message": "Animations.ecf absent — timing ray-cast par défaut"})
    n_zero_high = n_patrol = 0
    for pf in static_playfields(scenario):
        tier = playfield_tier(pf)
        doc = parse_yaml_file(str(pf))
        if tier == "high":
            pois = find_root(doc, "POIs")
            if pois is not None:
                rnd = find_child(pois, "Random")
                for item in seq_children(rnd) if rnd else []:
                    bases = [item] if item.key is not None else seq_children(item)
                    for e in bases:
                        c = find_child(e, "DroneProb")
                        if c is not None and c.value.strip() in ("0", "0.0"):
                            n_zero_high += 1
                        break
        szs = find_root(doc, "SpawnZones")
        if szs is not None:
            for zone in seq_children(szs):
                ents = find_child(zone, "Entities")
                for e in seq_children(ents) if ents else []:
                    nmv = item_val(e, "Names")
                    d = find_child(e, "DelayMinMax")
                    if (d is not None and d.value.replace(" ", "") == "[-1,-1]"
                            and any(p in nmv for p in PATROL_PATTERNS)):
                        n_patrol += 1
    if n_zero_high:
        findings.append({"id": "drone_zero", "severity": "warn", "count": n_zero_high,
                         "message": "POIs haut tier avec DroneProb 0 (correctif: tier_curves)"})
    if n_patrol:
        findings.append({"id": "patrol_norepop", "severity": "warn", "count": n_patrol,
                         "message": "patrouilles jamais re-popées (correctif: repop)"})
    return findings


ALL_PASSES = {
    "vessel_mapping": pass_vessel_mapping,
    "baiconfig": pass_baiconfig,
    "animations": pass_animations,
    "tier_curves": pass_tier_curves,
    "repop": pass_repop,
    "archetypes": pass_archetypes,
    "behaviors": pass_behaviors,
    "faction_groups": pass_faction_groups,
    "space_missions": pass_space_missions,
    "aquatic": pass_aquatic,
    "reputation": pass_reputation,
}


def run_passes(scenario: Path, names: list, apply: bool = False) -> list:
    store = BackupStore(scenario) if apply else None
    return [ALL_PASSES[name](scenario, apply=apply, store=store) for name in names]
