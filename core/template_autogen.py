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
Generation des Templates manquants d'un scenario.

Objectif : tout bloc/item defini dans le scenario (ou herite de la vanille)
doit pouvoir etre demonte au Deconstructor. Les Templates crees ici sont
volontairement **non craftables** (`Target: ""`, meme convention que les
templates caches de la vanille : `HullDestroyed`, `DecoStoneBlocks`...) mais
restent utilises par le Deconstructor, qui indexe les templates par leur nom
de sortie sans regarder `Target`.

La recette de chaque Template manquant est copiee du **modele connu le plus
proche** parmi les Templates qui existent deja : meme groupe, meme famille de
nom, meme materiau/categorie/classe, puis proximite de masse. Les quantites
sont ramenees a une unite et, quand les deux masses sont connues et
comparables, ajustees au ratio de masse (facteur borne x0.5..x3) ; la quantite
est divisee par l'OutputCount de la source (recettes d'ammo par 10, etc.).

Regles de surete :
- jamais d'ingredient egal au bloc produit (boucle immediate) ;
- jamais de quantite > MAX_QTY ;
- jamais de CraftTime > MAX_CRAFT_TIME (le temps de demontage suit le
  CraftTime) ;
- les ressources brutes (minerais, monnaie) recoivent un template VIDE :
  les demonter ne doit pas dupliquer une ressource rare ;
- les entrees techniques (`*Template`, `Air`, `TestDec*`...) sont ignorees.

Le fichier Templates.ecf n'est jamais reecrit : les nouvelles entrees sont
ajoutees a la fin (les commentaires/mise en forme existants sont preserves).
Les noms deja presents sont ignores, donc l'operation est idempotente.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .ecf.parser import parse_ecf_file, parse_ecf_text
from .fsutil import atomic_write_bytes, clear_readonly

CONF = "Content/Configuration"
MAX_QTY = 100_000
MAX_CRAFT_TIME = 600

SAFE_NAME = re.compile(r"^[A-Za-z0-9_.\-']+$")
ABSTRACT = re.compile(r"(?i)(^air$|template$|^childtest$|^dummyblock$|^testdec|debug$)")
BAD_CANDIDATE = re.compile(r"(?i)(template$|^npc|spawn|^securityguard|^melee|debug$|^test)")
RAW_NAME = re.compile(r"(?i)(ore|resource)$")

STOPWORDS = {
    "block", "blocks", "small", "large", "medium", "stage", "harvested",
    "template", "new", "old", "the", "mod", "pro", "base",
    "t1", "t2", "t3", "t4", "01", "02", "03", "1", "2", "3", "4", "5",
}
# Prefixes de faction : partages par des centaines d'entrees, ils ne
# prouvent pas a eux seuls une ressemblance de recette.
GENERIC_PREFIXES = {
    "eden", "atl", "bizon", "esd", "rpg", "hvp", "cv", "sv", "gv", "ms",
    "ss", "ba", "poi",
}

MAT_EARTH = {"stone", "dirt", "grass", "clay", "bedrock", "fertile",
             "foundation", "grassblock"}
MAT_SAND = {"sand", "sandblock"}
MAT_SNOW = {"snow", "ice", "water", "edenice"}
MAT_ROCK = {"rock", "rockhard", "lava"}
MAT_ORE = {"resourcehard", "resourcesoft", "resourcemedium", "resource",
           "naqahdah", "edenvoidium", "edenvoidiumt2", "edenrich",
           "crystal", "crystals"}
MAT_PLANT = {"plants", "plant", "hydroponics"}
MAT_TREE = {"tree", "palm"}
MAT_WOOD = {"wood", "woodblock", "woodhard", "woodsoft", "woodplanks"}
MAT_STRUCT = {"metalhard", "metal", "metallight", "hull", "hullcombat",
              "hullarmored", "hullarmoredsmall", "hulllight", "steelsmall",
              "steellarge", "titaniumsmall", "titaniumlarge", "concrete",
              "concretearmored", "plastic", "carbonsmall", "carbonlarge",
              "alien", "xenosteel", "forcefield", "legacy"}
MAT_DEVICE = {"device", "devicepro", "weaponlarge", "weaponsmall",
              "weaponlargepro", "weapon", "weaponplanet", "weaponsmallpro",
              "thruster", "thrusterpro", "combatsmall", "combatlarge",
              "nogravity"}

TREE_TOKENS = {
    "tree", "palm", "sapling", "trunk", "log", "logs", "branch", "bamboo",
    "cedar", "birch", "oak", "elm", "willow", "spruce", "cypress", "banyan",
    "juniper", "redwood", "maple", "pine", "fir", "ash", "poplar", "sycamore",
    "acacia", "dracaena", "holly",
}
WOOD_TOKENS = {"wood", "plank", "planks", "timber", "lumber"}
PLANT_TOKENS = {
    "plant", "bush", "fern", "mushroom", "shroom", "coral",
    "seaweed", "crop", "wheat", "corn", "tomato", "pumpkin", "fruit", "roots",
    "root", "moss", "fungus", "grass", "flower", "cactus", "seed", "weed",
    "algae", "vine", "harvested", "cattail", "hydrilla", "waterleaf",
    "rainforest", "undergrowth", "canopy", "reed", "lily", "bromeliad",
}
GROUND_TOKENS = {"rock", "stone", "ore", "crystal", "sand", "snow", "ice",
                 "lava", "dirt", "clay", "bedrock", "boulder", "butte",
                 "crag", "cliff", "peak", "statue", "monument", "cross",
                 "pillar", "column", "boulder"}
STRUCT_TOKENS = {
    "hull", "steel", "metal", "titanium", "concrete", "plastic", "window",
    "wall", "ramp", "corner", "beam", "pillar", "floor", "roof", "block",
    "plate", "wing", "stairs", "truss",
}
DEVICE_TOKENS = {
    "turret", "weapon", "thruster", "generator", "light", "lcd", "sign",
    "seat", "container", "fridge", "teleporter", "warp", "shield",
    "detector", "sensor", "console", "station", "control", "door", "hangar",
    "shutter", "forcefield", "gate", "airlock", "solar", "panel",
    "lamp", "cable", "wire", "pipe", "antenna", "radar",
}
FURNITURE_TOKENS = {"bed", "sofa", "table", "chair", "kitchen", "bookshelf",
                    "lcd", "sign", "bathroom", "tv"}

SHAPE_TOKENS = {"ramp", "corner", "wing", "wall", "floor", "roof", "door",
                 "window", "beam", "pillar", "plate", "truss", "stairs",
                 "shutter", "hangar", "container", "solar", "lamp", "panel",
                 "cable", "pipe"}

WEAPON_TYPES = {
    "pistol", "rifle", "assaultrifle", "sniper", "shotgun", "minigun", "smg",
    "launcher", "rocket", "cannon", "drill", "sword", "knife", "club", "axe",
    "spear", "bow", "crossbow", "flamethrower", "welder", "tool", "filler",
    "repair", "scanner", "charge", "ammo", "bullet", "shell", "grenade",
    "mine", "torpedo", "emp", "artillery", "flak", "railgun", "multiturret",
}

# Modeles "canoniques" par sous-famille : uniquement des Templates qui
# existent dans le scenario (RE2 a remplace les blocs de terrain vanille par
# ATL_EarthBlock / ATL_SandBlock, d'ou ces choix).
PREFERRED = {
    "earth": ["ATL_EarthBlock", "EarthBlock"],
    "sand": ["ATL_SandBlock", "SandBlock"],
    "snow": ["ATL_EarthBlock", "SnowBlock", "IceBlocks"],
    "rock": ["DecoStoneBlocks", "ATL_EarthBlock"],
    "plant": ["PlantDead2", "PlantDead", "BIZON_Plants"],
    "tree": ["OutdoorTreeBlocks", "WoodBlocks", "PlantDead2"],
    "wood": ["WoodBlocks", "OutdoorTreeBlocks"],
    "deco": ["DecoTables", "IndoorPlants", "DecoBlocks"],
}


@dataclass
class Recipe:
    name: str
    inputs: Tuple[Tuple[str, int], ...]
    craft_time: float
    output_count: int
    decon: str
    target: str


@dataclass
class Obj:
    name: str
    kind: str           # "block" | "item"
    props: Dict[str, str]      # proprietes effectives (pour le matching)
    own: Dict[str, str]        # derniere declaration seule (pour la couverture)


@dataclass
class TemplatePlan:
    name: str
    kind: str
    inputs: List[Tuple[str, int]]
    source: str
    method: str
    craft_time: int
    decon: str
    show_user: str

    @property
    def empty(self) -> bool:
        return not self.inputs


@dataclass
class AutogenResult:
    entries: List[TemplatePlan] = field(default_factory=list)
    skipped: List[Tuple[str, str, str]] = field(default_factory=list)
    counts: Dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Chargement / couverture
# ---------------------------------------------------------------------------

def _property_pairs(block) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for child in block.children:
        if type(child).__name__ != "EcfProperty":
            continue
        for key, value in child.pairs:
            if key:
                out.append((key, value))
    return out


def _read_defs(paths: Sequence[Path], kinds: Sequence[str]) -> Dict[str, Obj]:
    """Fusion vanille -> scenario pour le matching, et derniere declaration
    seule pour la couverture (le scenario peut omettre TemplateRoot : on ne
    suppose pas qu'il herite, c'est le cas conservateur)."""
    merged: Dict[str, Dict[str, str]] = {}
    own: Dict[str, Dict[str, str]] = {}
    kind_of: Dict[str, str] = {}
    for path in paths:
        if not path.exists():
            continue
        for block in parse_ecf_file(path).iter_blocks():
            if block.kind not in kinds:
                continue
            name = (block.get_property("Name") or "").strip()
            if not name:
                continue
            props = dict(_property_pairs(block))
            props["Name"] = name
            own[name] = props
            merged.setdefault(name, {}).update(props)
            kind_of[name] = "block" if "Block" in kinds else "item"
    return {name: Obj(name, kind_of[name], merged[name], own[name])
            for name in merged}


def _parse_templates(doc) -> Dict[str, Recipe]:
    out: Dict[str, Recipe] = {}
    for block in doc.iter_blocks():
        if block.kind not in ("Template", "+Template"):
            continue
        name = (block.get_property("Name") or "").strip()
        if not name:
            continue
        inputs: List[Tuple[str, int]] = []
        for child in block.children:
            if not str(getattr(child, "kind", "")).startswith("Child Inputs"):
                continue
            for prop in child.children:
                if type(prop).__name__ != "EcfProperty":
                    continue
                for key, value in prop.pairs:
                    if not key:
                        continue
                    try:
                        qty = int(float(str(value).strip().strip('"')))
                    except (TypeError, ValueError):
                        continue
                    if qty > 0:
                        inputs.append((key, qty))
        try:
            craft = float(str(block.get_property("CraftTime") or "1").strip())
        except ValueError:
            craft = 1.0
        try:
            output = int(float(str(block.get_property("OutputCount") or "1").strip()))
        except ValueError:
            output = 1
        out[name] = Recipe(
            name=name,
            inputs=tuple(inputs),
            craft_time=craft,
            output_count=max(1, output),
            decon=(block.get_property("DeconOverride") or "").strip().strip('"'),
            target=(block.get_property("Target") or "").strip(),
        )
    return out


def _read_templates(paths: Sequence[Path]) -> Tuple[Dict[str, Recipe], Dict[str, Recipe]]:
    """(tous les Templates, Templates d'origine uniquement).

    La section generee en fin de fichier est exclue du pool de modeles :
    sinon une seconde execution trouverait de nouveaux "modeles" parmi les
    entrees qu'elle vient de creer (idempotence cassee)."""
    everything: Dict[str, Recipe] = {}
    sources: Dict[str, Recipe] = {}
    for path in paths:
        if not path.exists():
            continue
        everything.update(_parse_templates(parse_ecf_file(path)))
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if GENERATED_MARKER in text:
            head = text[:text.index(GENERATED_MARKER)]
            sources.update(_parse_templates(parse_ecf_text(head, str(path))))
        else:
            sources.update(_parse_templates(parse_ecf_file(path)))
    return everything, sources


def _config_paths(root: Path, vanilla_root: str) -> Tuple[Path, Path]:
    root = Path(root)
    conf = root if root.name == "Configuration" else root / CONF
    vanilla = Path(vanilla_root) / "Configuration" if vanilla_root else None
    return conf, vanilla


def load(root: Path, vanilla_root: str = "") -> Tuple[Dict[str, Obj], Dict[str, Obj], Dict[str, Recipe], Dict[str, Recipe]]:
    """Blocs, items et templates DU SCENARIO.

    `vanilla_root` est ignore : vecu le 28/10/2026 (crash client sur
    `_Acacia_Sapling_Fall`), le jeu charge le Blocks/Items/Templates.ecf du
    scenario A LA PLACE de celui de la base — un nom defini en vanille seule
    n'existe pas a l'execution, et un Template qui le vise est fatal
    (« No item/block with name 'X' existing », le chargeur avorte toute la
    suite des templates). La couverture ne doit donc jamais merger la
    vanille. Le parametre reste accepte pour la compatibilite des appels."""
    conf, _vanilla = _config_paths(root, vanilla_root)
    block_paths = [conf / "BlocksConfig.ecf"]
    item_paths = [conf / "ItemsConfig.ecf"]
    tpl_paths = [conf / "Templates.ecf"]
    blocks = _read_defs([p for p in block_paths if p.exists()], ("Block", "+Block"))
    items = _read_defs([p for p in item_paths if p.exists()], ("Item", "+Item"))
    templates, sources = _read_templates([p for p in tpl_paths if p.exists()])
    return blocks, items, templates, sources


def missing(blocks: Dict[str, Obj], items: Dict[str, Obj],
            templates: Dict[str, Recipe]) -> Tuple[List[str], List[str]]:
    """Blocs/items sans Template utilisable.

    Pour un bloc, un TemplateRoot direct vers un Template existant suffit :
    le chargeur du jeu resout alors la recette du root (ViewPlugin)."""
    miss_blocks: List[str] = []
    for name, obj in blocks.items():
        if name in templates:
            continue
        root_name = (obj.own.get("TemplateRoot") or "").strip()
        if root_name and root_name in templates:
            continue
        miss_blocks.append(name)
    miss_items = [name for name in items if name not in templates]
    return miss_blocks, miss_items


# ---------------------------------------------------------------------------
# Familles / similarite
# ---------------------------------------------------------------------------

def _tokens(name: str) -> List[str]:
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", name or "")
    text = re.sub(r"([A-Za-z])([0-9])", r"\1 \2", text)
    return [part.lower() for part in re.split(r"[^A-Za-z0-9]+", text) if part]


def _significant(name: str) -> set:
    return {_canon(tok) for tok in _tokens(name)
            if (len(tok) >= 4 or tok in {"bed", "sofa", "tv", "lcd"})
            and tok not in STOPWORDS and tok not in GENERIC_PREFIXES}


def _mass(props: Dict[str, str]) -> float:
    try:
        return float(str(props.get("Mass", "0")).strip().strip('"'))
    except (TypeError, ValueError):
        return 0.0


def _canon(token: str) -> str:
    if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _subfamily(props: Dict[str, str]) -> str:
    tokens = {_canon(tok) for tok in _tokens(props.get("Name") or "")}
    if tokens & FURNITURE_TOKENS:
        return "deco"
    cls = (props.get("Class") or "").strip()
    group = (props.get("Group") or "").strip().lower()
    # Un appareil cpg* reste un appareil meme si son habillage est en bois
    # (four/traiteur Talon...), sinon il heriterait de la recette du bois.
    if cls and group.startswith("cpg") and cls not in {
            "CropsGrown", "PlantGrowing", "PlantHarvest", "Farming"}:
        return "device"
    if tokens & DEVICE_TOKENS:
        return "device"
    if tokens & {"water", "ice", "snow"}:
        return "snow"
    if tokens & {"lava", "magma"}:
        return "rock"
    material = (props.get("Material") or "").strip().lower().replace(" ", "")
    if material in MAT_EARTH:
        return "earth"
    if material in MAT_SAND:
        return "sand"
    if material in MAT_SNOW:
        return "snow"
    if material in MAT_ROCK:
        return "rock"
    if material in MAT_ORE:
        return "ore"
    if material in MAT_PLANT:
        return "plant"
    if material in MAT_TREE:
        return "tree"
    if material in MAT_WOOD:
        return "wood"
    if material in MAT_STRUCT:
        return "structure"
    if material in MAT_DEVICE:
        return "device"
    category = (props.get("Category") or "").strip().lower()
    if category == "buildingblocks":
        return "structure"
    if category == "devices":
        return "device"
    if category == "farming":
        return "plant"
    if category == "deco blocks":
        return "deco"
    if category == "weapons/items":
        return "device"
    shape = (props.get("Shape") or "").strip().lower()
    if shape in ("terrain", "liquidterrain"):
        return "earth"
    if group in ("stone", "grass", "dirt", "sand", "snow", "resource", "rock"):
        return {"stone": "earth", "grass": "earth", "dirt": "earth",
                "sand": "sand", "snow": "snow", "resource": "ore",
                "rock": "rock"}[group]
    if tokens & {"desktop", "hero", "indoor", "deco", "houseplant"}:
        return "plant"
    if tokens & TREE_TOKENS:
        return "tree"
    if tokens & WOOD_TOKENS:
        return "wood"
    if tokens & PLANT_TOKENS:
        return "plant"
    if tokens & GROUND_TOKENS:
        if "rock" in tokens:
            return "rock"
        if "sand" in tokens:
            return "sand"
        if tokens & {"snow", "ice"}:
            return "snow"
        return "earth"
    if tokens & STRUCT_TOKENS:
        return "structure"
    return ""


def _compatible(target: Obj, cand: Obj) -> bool:
    want, got = _subfamily(target.props), _subfamily(cand.props)
    if want in {"earth", "sand", "snow", "rock", "plant", "tree", "wood"}:
        return want == got
    return not want or not got or want == got


def _weapon_clash(a: str, b: str) -> bool:
    wa = {tok for tok in _tokens(a) if tok in WEAPON_TYPES}
    wb = {tok for tok in _tokens(b) if tok in WEAPON_TYPES}
    return bool(wa and wb and not (wa & wb))


def _is_abstract(name: str) -> bool:
    return bool(ABSTRACT.search(name))


def _is_raw(obj: Obj) -> bool:
    return (_subfamily(obj.props) in {"ore"}
            or bool(RAW_NAME.search(obj.name))
            or bool(re.search(r"(?i)^(money|currency)", obj.name)))


# ---------------------------------------------------------------------------
# Selection du modele
# ---------------------------------------------------------------------------

class _Picker:
    def __init__(self, blocks: Dict[str, Obj], items: Dict[str, Obj],
                 templates: Dict[str, Recipe], sources: Dict[str, Recipe]):
        self.blocks = blocks
        self.items = items
        self.templates = sources
        self.block_candidates = [
            (blocks[name], sources[name], blocks[name])
            for name in blocks
            if name in sources
            and not BAD_CANDIDATE.search(name) and not _is_abstract(name)
        ]
        # Bloc couvert par un TemplateRoot : sa recette est celle du root,
        # mais ses propres proprietes (masse, classe) doivent peser dans le
        # choix du modele pour les autres blocs.
        self.block_candidates += [
            (blocks[name], sources[root], blocks[name])
            for name in blocks
            if name not in sources
            for root in [(blocks[name].own.get("TemplateRoot") or "").strip()]
            if root and root in sources
            and not BAD_CANDIDATE.search(name) and not _is_abstract(name)
        ]
        self.item_candidates = [
            (items[name], sources[name], items[name])
            for name in items if name in sources
            and not BAD_CANDIDATE.search(name) and not _is_abstract(name)
        ]

    def _best_name(self, target: Obj, candidates, kind: str):
        want_sig = _significant(target.name)
        first = _canon(next((tok for tok in _tokens(target.name)
                             if tok not in GENERIC_PREFIXES), ""))
        pool = []
        for cand, recipe, props in candidates:
            shared = want_sig & _significant(cand.name)
            if not shared:
                continue
            cand_first = _canon(next((tok for tok in _tokens(cand.name)
                                      if tok not in GENERIC_PREFIXES), ""))
            if (cand_first != first and len(shared) < 2
                    and not (shared & SHAPE_TOKENS)):
                continue
            if kind == "item":
                ca = (props.props.get("Category") or "").strip()
                da = (target.props.get("Category") or "").strip()
                if ca and da and ca != da:
                    continue
                if _weapon_clash(target.name, cand.name):
                    continue
                if da in {"Food", "Ingredients", "Medical"} and not ca and len(shared) < 2:
                    continue
            elif not _compatible(target, cand):
                continue
            if kind == "block" and _subfamily(target.props) == "plant"                     and (props.props.get("Category") or "").strip() == "Deco Blocks":
                continue
            pool.append((cand, recipe, shared, cand_first == first))
        if not pool:
            return None
        nonempty = [row for row in pool if row[1].inputs]
        if not nonempty:
            return None

        def score(row):
            cand, recipe, shared, same_first = row
            return (
                0 if _subfamily(cand.props) == _subfamily(target.props) else 1,
                0 if (cand.props.get("Category") or "") == (target.props.get("Category") or "") else 1,
                -len(shared),
                0 if same_first else 1,
                abs(_mass(cand.props) - _mass(target.props)),
            )

        best = min(nonempty, key=score)
        return best[0].name, best[1], best[0], "name"

    def _template_root_model(self, target: Obj):
        root = (target.props.get("TemplateRoot") or "").strip()
        if not root or root == target.name or root not in self.templates:
            return None
        recipe = self.templates[root]
        return root, recipe, self.blocks.get(root, Obj(root, "block", {}, {})), "root"

    def _same_group(self, target: Obj, candidates, family: str):
        group = (target.props.get("Group") or "").strip()
        if not group or family not in {"device", "structure"} or _mass(target.props) <= 0:
            return None
        target_class = (target.props.get("Class") or "").strip()
        pool = [row for row in candidates
                if (row[2].props.get("Group") or "").strip() == group
                and _compatible(target, row[0]) and row[1].inputs
                and (not target_class or not (row[2].props.get("Class") or "").strip()
                     or (row[2].props.get("Class") or "").strip() == target_class)]
        if not pool:
            return None
        mass = _mass(target.props)
        near = [row for row in pool if _mass(row[2].props) > 0
                and 0.25 <= _mass(row[2].props) / mass <= 4]
        if near:
            pool = near
        return min(pool, key=lambda row: abs(math.log((_mass(row[2].props) or 1) / mass)))

    def _preferred(self, target: Obj, family: str):
        for name in PREFERRED.get(family, ()):
            recipe = self.templates.get(name)
            if recipe and recipe.inputs:
                return name, recipe, self.blocks.get(name) or self.items.get(name) or Obj(name, "block", {}, {}), "preferred"
        return None

    def _same_family(self, target: Obj, candidates, family: str):
        if not family:
            return None
        if family in {"structure", "device", "deco"}:
            target_class = (target.props.get("Class") or "").strip()
            if not target_class or _mass(target.props) <= 0:
                return None
        pool = [row for row in candidates
                if _subfamily(row[2].props) == family and row[1].inputs]
        if family in {"structure", "device", "deco"}:
            target_class = (target.props.get("Class") or "").strip()
            pool = [row for row in pool
                    if (row[2].props.get("Class") or "").strip() == target_class]
        mass = _mass(target.props)
        if mass > 0:
            near = [row for row in pool if _mass(row[2].props) > 0
                    and 0.5 <= _mass(row[2].props) / mass <= 2]
            if near:
                pool = near
        if not pool:
            return None
        best = min(pool, key=lambda row: abs(math.log((_mass(row[2].props) or 1) / (mass or 1))))
        return best

    def pick(self, target: Obj):
        if _is_abstract(target.name):
            return None, "skipped"
        if _is_raw(target):
            return None, "raw"
        if target.kind == "block":
            root_model = self._template_root_model(target)
            if root_model:
                return root_model[:3], "root"
            name_model = self._best_name(target, self.block_candidates, "block")
            if name_model:
                return name_model[:3], "name"
            family = _subfamily(target.props)
            same_group = self._same_group(target, self.block_candidates, family)
            if same_group:
                return (same_group[0].name, same_group[1], same_group[0]), "group"
            preferred = self._preferred(target, family)
            if preferred:
                return preferred[:3], "preferred"
            same_family = self._same_family(target, self.block_candidates, family)
            if same_family:
                return (same_family[0].name, same_family[1], same_family[0]), "family"
            if family == "structure":
                recipe = self.templates.get("HullSmallBlocks")
                if recipe and recipe.inputs:
                    return ("HullSmallBlocks", recipe,
                            self.blocks.get("HullSmallBlocks") or Obj("HullSmallBlocks", "block", {}, {})), "generic"
            return None, "none"
        name_model = self._best_name(target, self.item_candidates, "item")
        if name_model:
            return name_model[:3], "name"
        return None, "none"


# ---------------------------------------------------------------------------
# Construction des entrees
# ---------------------------------------------------------------------------

def _scale_inputs(inputs: Iterable[Tuple[str, int]], source_props: Dict[str, str],
                  target_props: Dict[str, str], output_count: int,
                  target_name: str) -> List[Tuple[str, int]]:
    factor = 1.0
    src_mass, tgt_mass = _mass(source_props), _mass(target_props)
    if src_mass > 0 and tgt_mass > 0:
        ratio = tgt_mass / src_mass
        if 0.25 <= ratio <= 4.0:
            factor = min(3.0, max(0.5, ratio))
    factor /= max(1, output_count)
    out: List[Tuple[str, int]] = []
    seen = set()
    for name, qty in inputs:
        if name == target_name or name in seen:
            continue
        seen.add(name)
        qty = max(1, min(MAX_QTY, int(round(qty * factor))))
        out.append((name, qty))
    return out


def _make_plan(name: str, kind: str, model, method: str,
               blocks: Dict[str, Obj], items: Dict[str, Obj]) -> TemplatePlan:
    target = (blocks if kind == "block" else items)[name]
    if model is None:
        inputs: List[Tuple[str, int]] = []
        source = ""
        craft = 1
        decon = "Stop"
    else:
        source, recipe, source_props = model
        inputs = _scale_inputs(recipe.inputs, source_props.props,
                               target.props, recipe.output_count, name)
        craft = max(1, min(MAX_CRAFT_TIME, int(round(recipe.craft_time or 1))))
        # Continue = le Deconstructor descend dans les ingredients ; Stop
        # ferait echouer le demontage au premier niveau (CraftTime/ P3 = 0).
        decon = "Continue" if inputs else "Stop"
    return TemplatePlan(
        name=name,
        kind=kind,
        inputs=inputs,
        source=source,
        method=method,
        craft_time=craft,
        decon=decon,
        show_user=(target.props.get("ShowUser") or "(default=Yes)").strip(),
    )


def plan(root: Path, vanilla_root: str = "", include_empty: bool = False) -> AutogenResult:
    """Construit la liste des Templates a ajouter (aucune ecriture).

    `include_empty=True` ecrit aussi les entrees sans modele (recette vide,
    DeconOverride Stop) : elles rendent le nom present mais le Deconstructor
    ne produit rien. Par defaut elles sont seulement listees dans `skipped`.
    """
    blocks, items, templates, sources = load(root, vanilla_root)
    miss_blocks, miss_items = missing(blocks, items, templates)
    picker = _Picker(blocks, items, templates, sources)
    result = AutogenResult()

    for names, kind, source_map in ((miss_blocks, "block", blocks),
                                    (miss_items, "item", items)):
        for name in names:
            if not SAFE_NAME.match(name):
                result.skipped.append((name, kind, "nom ECF non sur"))
                continue
            obj = source_map[name]
            model, method = picker.pick(obj)
            if method == "skipped":
                result.skipped.append((name, kind, "entree technique"))
                continue
            entry = _make_plan(name, kind, model, method, blocks, items)
            if not entry.inputs and not include_empty:
                result.skipped.append((name, kind,
                                       "ressource brute" if method == "raw"
                                       else "aucun modele proche"))
                continue
            result.entries.append(entry)
    # Un Template genere dont TOUS les ingredients sont sans Template ne
    # serait pas demontable : CloneLine n'aurait aucune sortie. La vanille
    # traite ces ingredients (minerais, nourriture brute, kits) comme des
    # feuilles via un Template vide. On ajoute donc ces feuilles pour tout
    # ingredient reference par une entree generee.
    covered = set(templates) | {entry.name for entry in result.entries}
    for block_name, block_obj in blocks.items():
        root_name = (block_obj.own.get("TemplateRoot") or "").strip()
        if root_name and root_name in templates:
            covered.add(block_name)
    pending = {name for entry in result.entries for name, _qty in entry.inputs}
    terminal_names = set()
    for name in sorted(pending - covered):
        target = blocks.get(name) or items.get(name)
        if target is None:
            continue
        result.entries.append(TemplatePlan(
            name=name, kind=target.kind, inputs=[], source="", method="terminal",
            craft_time=1, decon="Stop",
            show_user=(target.props.get("ShowUser") or "(default=Yes)").strip(),
        ))
        covered.add(name)
        terminal_names.add(name)
    if terminal_names:
        # Ces noms ont bien recu un Template (feuille) : ils ne sont plus
        # "ignores", meme s'ils n'avaient aucun modele.
        result.skipped = [row for row in result.skipped
                          if row[0] not in terminal_names]
    result.entries.sort(key=lambda e: (e.kind, e.name.casefold()))
    result.counts = {
        "entries": len(result.entries),
        "non_empty": sum(1 for e in result.entries if e.inputs),
        "empty": sum(1 for e in result.entries if not e.inputs),
        "skipped": len(result.skipped),
        "blocks": sum(1 for e in result.entries if e.kind == "block"),
        "items": sum(1 for e in result.entries if e.kind == "item"),
        "terminal": sum(1 for e in result.entries if e.method == "terminal"),
    }
    return result


# ---------------------------------------------------------------------------
# Rendu / ecriture
# ---------------------------------------------------------------------------

GENERATED_MARKER = "# Templates de deconstruction generes automatiquement"

SECTION_HEADER = (
    "# =============================================================================\r\n"
    "# Templates de deconstruction generes automatiquement (Target vide = non\r\n"
    "# craftable, mais utilisable par le Deconstructor).\r\n"
    "# Recettes copiees du modele connu le plus proche, quantites ramenees a une\r\n"
    "# unite (OutputCount de la source divise) et ajustees a la masse quand elle\r\n"
    "# est connue des deux cotes.\r\n"
    "# Regenerer : python tools/generate_missing_templates.py --apply\r\n"
    "# =============================================================================\r\n\r\n"
)


def render(entries: Sequence[TemplatePlan], eol: str = "\r\n") -> str:
    """Rend les entrees au dialecte ECF du fichier (Template sans +, Target "")."""
    lines: List[str] = []
    for entry in entries:
        if not SAFE_NAME.match(entry.name):
            continue
        lines.append("{ Template Name: %s" % entry.name)
        lines.append("  CraftTime: %d" % entry.craft_time)
        lines.append('  Target: ""')
        decon = entry.decon if entry.decon in {"Stop", "Continue"} else ""
        if not entry.inputs:
            decon = "Stop"
        if decon:
            lines.append("  DeconOverride: %s" % decon)
        lines.append("  { Child Inputs")
        for name, qty in entry.inputs:
            if not SAFE_NAME.match(name):
                continue
            lines.append("    %s: %d" % (name, qty))
        lines.append("  }")
        lines.append("}")
        lines.append("")
    return eol.join(lines)


def apply(root: Path, vanilla_root: str = "", include_empty: bool = False) -> Tuple[AutogenResult, int]:
    """Ajoute les Templates manquants a Templates.ecf (backup + ecriture atomique)."""
    conf, _ = _config_paths(root, vanilla_root)
    path = conf / "Templates.ecf"
    result = plan(root, vanilla_root, include_empty=include_empty)
    if not result.entries:
        return result, 0
    existing = path.read_bytes() if path.exists() else b""
    if existing and not existing.endswith(b"\n"):
        existing += b"\r\n"
    payload = render(result.entries)
    data = existing + SECTION_HEADER.encode("utf-8") + payload.encode("utf-8")
    if path.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = path.with_name(path.name + ".bak_" + stamp)
        backup.write_bytes(path.read_bytes())
    atomic_write_bytes(path, data)
    return result, len(result.entries)
