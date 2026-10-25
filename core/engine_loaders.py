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
Validations REPLIQUANT les chargeurs du moteur (regles verifiees contre le
chargement reel du jeu, build 25/09/2026 ; session du 25/10/2026).

Pourquoi : le moteur JETTE une exception a la PREMIERE erreur et abandonne —
le boot reel (dedi_boot_check) ne revele qu'un fantome par iteration.
Repliquer les chargeurs en statique liste TOUTES les erreurs d'un coup, avec
les MESSAGES EXACTS du moteur.

Sources des checks (classes du jeu) :
- ItemsConfig  : GroupTree.TestDevice (+ StoreInDynamicProps pour le parseur)
- BlocksConfig : SymbolList.OpenNetwork + PartitionDictionary.Init
- TechTree     : ConfigTree.LoadDeployment / FindDeployment / OpenNetwork
- Templates    : DialogSettings (Table bloc -> Template, cle Target)

Fidelite :
- Resolution des noms de blocs/items SENSIBLE A LA CASSE (TryGetValue du
  jeu) — un ChildBlocks: hullfull pour Name: HullFull est FATAL en jeu.
- Le '+' des +Block/+Item est un flag du parseur (IsPublic) : les
  declarations sont des elements a part entiere.
- Id invalide -> 0 (uint.TryParse du jeu), doublon d'Id items -> FATAL.
- Blocs : doublon de Name = warning « overridden » (ecrasement) — mais
  doublon d'Id ITEMS = throw : reproduits tels quels.
- Sans vanilla (vanilla_content=""), les checks de whitelist (Class/Place/
  Shape/Mesh) et de references vers la config de base sont SILICIEUSEMENT
  sautes : le scenerio seul ne peut pas les prouver (meme discipline que
  _check_values de launch_check).
- « No template found » : warning du jeu (barre constructeur absente),
  limite aux blocs affiches dans l'arbre (categories non Hidden).

Non reproduit (hors portee de cette session) : « Meshfile missing » depend
d'un override C# par classe d'item non traçable simplement.
"""
from pathlib import Path
import re
from typing import Dict, List, Optional, Set, Tuple

from .ecf.doc_cache import get_parsed_doc
from .ecf.parser import parse_ecf_file
from .launch_check import LaunchIssue
from .parsers_utils import parse_quoted_list

# Tables de registres du moteur (build 25/09/2026) : classes « Block »,
# « ItemClass », « BlockPlacement » et « BlockShape » connues du chargeur,
# plus les classes C# nommees qu'il resout directement. Un scenario ne peut
# pas creer de classe C# : toute valeur hors de ces tables est fatale en jeu.
# ItemClass : completee par les classes utilisees par la vanilla.
BLOCK_CLASSES = {
    "AIDroneBay", "ATM", "ArmorLocker", "AutoMiner",
    "BlockPortal",
    "BlockTeleporter", "CockpitMS", "CockpitSS", "ConstructorBig", "ConstructorBigV2", "ConstructorHover",
    "ConstructorRecursive", "ConstructorSmall", "ConstructorSmallV2", "ConstructorSurvival", "ConstructorSurvivalV2", "ConstructorT0",
    "Container", "ContainerController", "ContainerExtension", "ContainerPersonal", "Core", "CropsGrown",
    "Damage", "DarkFactionPillarBase", "Deadgrass", "DecalControl", "Deconstructor", "Door",
    "Elevator", "EnergyWallEffect", "Explosive", "FieldRepairStation", "FoodProcessor", "FoodProcessorV2",
    "FuelTank", "Furnace", "Generator", "HoverEngine", "Ladder", "LandClaimDevice",
    "LandingGear", "Light", "LightBarrier", "LightSpot", "MedicStation", "MotionSensor",
    "NPCDialogue", "O2Generator", "O2GeneratorSmall", "O2H2Generator", "O2Station", "O2Tank",
    "PassengerSeat", "Plant", "PlantGrowing", "Portal", "RemoteConnector", "RepairBay",
    "RepairBayConsole", "RepairStation", "Sensor", "ShieldGenerator", "Sign", "Sleeping",
    "SolarGenerator", "SolarPanel", "Spawner", "SurvivalTent", "Switch", "Teleporter",
    "Thruster", "TraderNPC", "TradingStation", "TrapDoorOneTime", "TurretAuto", "TurretManual",
    "UpgradeRated", "Vent", "WarpDrive", "WarpDriveTank", "WaterGenerator", "Weapon",
}
ITEMCLASS_CLASSES = {
    "Activatable", "Armor", "ArmorBoost", "Block", "Toggle", "Token",
}
BLOCKPLACEMENT_CLASSES = {
    "Cockpit", "Face", "FlyDir", "FlyDirBottom", "Free", "NoRotation",
    "WeaponDir",
}
BLOCKSHAPE_CLASSES = {
    "BillboardGrass1", "BillboardGrass2", "BillboardGrass3", "BillboardPlant",
    "Config3DCollider", "Cube", "Deco", "EnergyWallEffect",
    "Ext3dModel", "Grass", "Invisible", "LightBarrier", "LiquidBlock", "LiquidTerrain",
    "ModelEntity", "ModelEntity2", "New", "Terrain", "Turret",
}

_CONF = "Content/Configuration"
_MAX_ANCESTORS = 7          # le jeu jette au 8e ancetre (compteur > 5)
_ALT_RE = re.compile(r"^(?:Alt)?([0-9]|1[0-9]|20)$")


def _name(b) -> Optional[str]:
    return b.get('Name') or b.get_property('Name')


def _prop(b, key: str) -> Optional[str]:
    """Valeur declaree sur le bloc (ligne d'ouverture ou ligne enfant)."""
    return b.get_property(key)


def _uint(v: Optional[str]) -> int:
    """uint.TryParse du jeu : echec -> 0 (jamais negatif)."""
    if v is None:
        return 0
    v = v.strip().strip('"')
    return int(v) if v.isdigit() else 0


def _int_strict(v: str) -> bool:
    try:
        int(v.strip())
        return True
    except ValueError:
        return False


def _index_kinds(paths: List[Path], kinds: Set[str]) -> Dict[str, object]:
    """Nom -> bloc (dernier gagne), sur plusieurs fichiers (scenario
    prioritaire : passe en dernier dans la liste d'appel)."""
    index: Dict[str, object] = {}
    for p in paths:
        if p is None or not Path(p).exists():
            continue
        doc = get_parsed_doc(Path(p))
        for b in doc.iter_blocks():
            if b.kind not in kinds:
                continue
            name = _name(b)
            if name:
                index[name] = b
    return index


def _index_ids(paths: List[Path], kinds: Set[str]) -> Dict[int, List[Tuple[str, object]]]:
    """Id -> [(Name, bloc)] dans l'ordre du fichier (doublons conserves)."""
    ids: Dict[int, List[Tuple[str, object]]] = {}
    for p in paths:
        if p is None or not Path(p).exists():
            continue
        doc = get_parsed_doc(Path(p))
        for b in doc.iter_blocks():
            if b.kind not in kinds:
                continue
            raw = b.get('Id')
            if raw is None:
                continue
            ids.setdefault(_uint(raw), []).append((_name(b), b))
    return ids


def _value_shapes(paths: List[Path], kinds: Set[str], key: str) -> Set[str]:
    """Ensemble des valeurs observees pour `key` (whitelists vanilla)."""
    out: Set[str] = set()
    for p in paths:
        if p is None or not Path(p).exists():
            continue
        doc = parse_ecf_file(Path(p))
        for b in doc.iter_blocks():
            if b.kind not in kinds:
                continue
            v = _prop(b, key)
            if v:
                out.add(v.strip().strip('"'))
    return out


def _template_targets(paths: List[Path]) -> Set[str]:
    """Noms de blocs/item produits par au moins un Template. Fidelite au
    chargeur du jeu (OutlineFactory.JoinComponent) : le template est indexe
    par SON PROPRE Name, resolu en Id (outputItemType = UnregisterAspect(name))
    — la convention « un Template s'appelle comme sa sortie ». La cle
    Target: des fichiers est la liste des CONSTRUCTEURS (SurvC, BaseC...),
    pas la cible."""
    out: Set[str] = set()
    for p in paths:
        if p is None or not Path(p).exists():
            continue
        doc = get_parsed_doc(Path(p))
        for b in doc.iter_blocks():
            if b.kind not in ("Template", "+Template"):
                continue
            name = _name(b)
            if name:
                out.add(name.strip().strip('"'))
    return out


class _Ctx:
    """Index partages entre les checks d'une meme execution du bilan."""

    def __init__(self, root: Path, vanilla_conf: Optional[Path]):
        self.root = root
        self.conf = root / _CONF
        self.vanilla_conf = vanilla_conf
        self._blocks_name: Optional[Dict[str, object]] = None
        self._items_name: Optional[Dict[str, object]] = None
        self._materials: Optional[Dict[str, object]] = None

    # fichiers SCENARIO (obligatoires pour les checks concernes)
    @property
    def blocks_path(self) -> Optional[Path]:
        p = self.conf / "BlocksConfig.ecf"
        return p if p.exists() else None

    @property
    def items_path(self) -> Optional[Path]:
        p = self.conf / "ItemsConfig.ecf"
        return p if p.exists() else None

    def _paths(self, fname: str) -> List[Path]:
        paths: List[Path] = []
        if self.vanilla_conf is not None:
            paths.append(self.vanilla_conf / fname)
        p = self.conf / fname
        if p.exists():
            paths.append(p)     # scenario en dernier = prioritaire
        return paths

    def blocks_by_name(self) -> Dict[str, object]:
        if self._blocks_name is None:
            self._blocks_name = _index_kinds(
                self._paths("BlocksConfig.ecf"), {"Block", "+Block"})
        return self._blocks_name

    def items_by_name(self) -> Dict[str, object]:
        if self._items_name is None:
            self._items_name = _index_kinds(
                self._paths("ItemsConfig.ecf"), {"Item", "+Item"})
        return self._items_name

    def materials(self) -> Dict[str, object]:
        if self._materials is None:
            self._materials = _index_kinds(
                self._paths("MaterialConfig.ecf"), {"Material", "+Material"})
        return self._materials

    def vanilla_only(self, fname: str, kinds: Set[str], key: str) -> Set[str]:
        if self.vanilla_conf is None:
            return set()
        return _value_shapes([self.vanilla_conf / fname], kinds, key)


def _issue(path: str, severity: str, message: str) -> LaunchIssue:
    return LaunchIssue(check="engine", path=path, line=0,
                       severity=severity, message=message)


def _ref_value(ctx: _Ctx, index: Dict[str, object], name: str, key: str,
               depth: int = 0) -> Optional[str]:
    """Valeur effective : declaration, sinon chaine Ref (memes regles que le
    jeu : CopyFrom parent puis CopyFrom element ; garde 12 niveaux)."""
    b = index.get(name)
    if b is not None:
        v = _prop(b, key)
        if v is not None:
            return v
    if depth >= 12:
        return None
    ref = _prop(b, 'Ref') if b is not None else None
    if not ref:
        return None
    return _ref_value(ctx, index, ref.strip().strip('"'), key, depth + 1)


# ---------------------------------------------------------------------------
# ItemsConfig — GroupTree.TestDevice
# ---------------------------------------------------------------------------

def _check_items(ctx: _Ctx, issues: List[LaunchIssue]) -> None:
    path = ctx.items_path
    if path is None:
        return
    rel = f"{_CONF}/ItemsConfig.ecf"
    doc = get_parsed_doc(path)
    items = ctx.items_by_name()
    mats = ctx.materials()
    vanilla_classes = ctx.vanilla_only("ItemsConfig.ecf", {"Item", "+Item"}, "Class")

    seen_ids: Dict[int, str] = {}
    for b in doc.iter_blocks():
        if b.kind not in ("Item", "+Item"):
            continue
        name = _name(b)
        if not name:
            continue
        iid = _uint(b.get('Id'))

        # doublon d'Id (id > 0) — le jeu jette (« Item already defined »)
        if iid > 0:
            if iid in seen_ids:
                issues.append(_issue(rel, "error",
                                     f"moteur (chargeur items) : « Item already "
                                     f"defined: Id {iid} » — {name} entre en "
                                     f"conflit avec {seen_ids[iid]}"))
                continue
            seen_ids[iid] = name

        # Ref vers un item inexistant (casse stricte)
        ref = b.get_property('Ref')
        if ref:
            ref = ref.strip().strip('"')
            if ref and ref not in items:
                issues.append(_issue(rel, "error",
                                     f"moteur (chargeur items) : « Referenced "
                                     f"item {ref} is not specified for item "
                                     f"{name} »"))

        # Class inconnue du moteur (whitelist vanilla ; un scenario ne peut
        # pas creer de classe C#)
        cls = _ref_value(ctx, items, name, 'Class')
        if cls is not None:
            cls = cls.strip().strip('"')
            if cls not in ITEMCLASS_CLASSES and (not vanilla_classes
                                                 or cls not in vanilla_classes):
                issues.append(_issue(rel, "error",
                                     f"moteur (chargeur items) : « No class "
                                     f"'{cls}' found » — {name}"))

        # Material obligatoire et resolu (fidelite : valeur via Ref possible)
        mat = _ref_value(ctx, items, name, 'Material')
        if not mat:
            issues.append(_issue(rel, "error",
                                 f"moteur (chargeur items) : « Material missing "
                                 f"on item '{name}' »"))
        else:
            mat = mat.strip().strip('"')
            if mats and mat not in mats:
                issues.append(_issue(rel, "error",
                                     f"moteur (chargeur items) : « Material "
                                     f"'{mat}' not found in item '{name}' »"))

        # HoldType / Durability : entier strict (le jeu jette) — messages
        # fideles : « hold_type » en snake_case, « Durability » tel quel
        for key, shown in (("HoldType", "hold_type"), ("Durability", "Durability")):
            v = _ref_value(ctx, items, name, key)
            if v is not None and not _int_strict(v.strip().strip('"')):
                issues.append(_issue(rel, "error",
                                     f"moteur (chargeur items) : « Cannot parse "
                                     f"attribute {shown} for item id "
                                     f"'{iid}' » ({key}: {v.strip()[:20]}) — "
                                     f"{name}"))

        # sections AltN (n numerique) : Class obligatoire
        for child in b.child_blocks():
            m = _ALT_RE.match(child.kind.strip())
            if m and not child.get_property('Class'):
                issues.append(_issue(rel, "error",
                                     f"moteur (chargeur items) : « No child "
                                     f"{m.group(1)} found in item with id "
                                     f"'{iid}' » — section {child.kind} de "
                                     f"{name} sans Class"))


# ---------------------------------------------------------------------------
# BlocksConfig — SymbolList.OpenNetwork + PartitionDictionary.Init
# ---------------------------------------------------------------------------

def _check_blocks(ctx: _Ctx, issues: List[LaunchIssue]) -> None:
    path = ctx.blocks_path
    if path is None:
        return
    rel = f"{_CONF}/BlocksConfig.ecf"
    doc = get_parsed_doc(path)
    blocks = ctx.blocks_by_name()
    mats = ctx.materials()
    vanilla_classes = ctx.vanilla_only("BlocksConfig.ecf", {"Block", "+Block"}, "Class")
    vanilla_places = ctx.vanilla_only("BlocksConfig.ecf", {"Block", "+Block"}, "Place")
    vanilla_meshes = ctx.vanilla_only("BlocksConfig.ecf", {"Block", "+Block"}, "Mesh")
    # formes : le jeu resout « BlockShape » + Shape principal ET chaque
    # partie de ChildShapes — la whitelist = l'union des deux champs vanilla
    vanilla_shapes = ctx.vanilla_only("BlocksConfig.ecf", {"Block", "+Block"}, "Shape")
    for cs in ctx.vanilla_only("BlocksConfig.ecf", {"Block", "+Block"}, "ChildShapes"):
        for part in cs.split(','):
            part = part.strip().strip('"').strip()
            if part:
                vanilla_shapes.add(part)

    seen_names: Set[str] = set()
    for b in doc.iter_blocks():
        if b.kind not in ("Block", "+Block"):
            continue
        name = _name(b)
        if not name:
            continue

        # doublon de Name : le jeu ECRASE avec un warning (« overridden »)
        if name in seen_names:
            issues.append(_issue(rel, "warning",
                                 f"moteur (chargeur blocs) : « Block {name} is "
                                 f"overridden » — la deuxieme declaration "
                                 f"remplace la premiere"))
        seen_names.add(name)

        bid = _uint(b.get('Id'))
        if bid >= 2048:
            issues.append(_issue(rel, "error",
                                 f"moteur (chargeur blocs) : « Not allowed to "
                                 f"assign a block id >= 2048 in BlocksConfig.ecf "
                                 f"({name}). Please leave the 'Id:' out! »"))

        # Ref vers un bloc inexistant (casse stricte)
        ref = b.get_property('Ref')
        if ref:
            ref = ref.strip().strip('"')
            if ref and ref not in blocks:
                issues.append(_issue(rel, "error",
                                     f"moteur (chargeur blocs) : « Block "
                                     f"'{ref}' not found for block '{name}' »"))

        # Class inconnue (le message du jeu ne cite pas la classe) :
        # registre « Block » du jeu (table du chargeur) + vanilla
        cls = _ref_value(ctx, blocks, name, 'Class')
        if cls is not None:
            cls = cls.strip().strip('"')
            if cls not in BLOCK_CLASSES and (not vanilla_classes
                                             or cls not in vanilla_classes):
                issues.append(_issue(rel, "error",
                                     f"moteur (chargeur blocs) : « Block class "
                                     f"not found! » — Class: {cls} sur {name} "
                                     f"inconnue du moteur"))

        # Material obligatoire
        mat = _ref_value(ctx, blocks, name, 'Material')
        if not mat:
            issues.append(_issue(rel, "error",
                                 f"moteur (chargeur blocs) : « Block {bid} has "
                                 f"missing/empty material » — {name}"))
        elif mats and mat.strip().strip('"') not in mats:
            issues.append(_issue(rel, "error",
                                 f"moteur (chargeur blocs) : « Block {bid} "
                                 f"references a not existing material "
                                 f"'{mat.strip()}' » — {name}"))

        # Mesh connu du moteur
        mesh = _ref_value(ctx, blocks, name, 'Mesh')
        if mesh is not None:
            mesh = mesh.strip().strip('"')
            if vanilla_meshes and mesh not in vanilla_meshes:
                issues.append(_issue(rel, "error",
                                     f"moteur (chargeur blocs) : « Unknown mesh "
                                     f"attribute '{mesh} » — {name}"))

        # Place (classe de placement BlockPlacement*)
        place = _ref_value(ctx, blocks, name, 'Place')
        if place is not None:
            place = place.strip().strip('"')
            if place not in BLOCKPLACEMENT_CLASSES and (
                    not vanilla_places or place not in vanilla_places):
                issues.append(_issue(rel, "error",
                                     f"moteur (chargeur blocs) : « No block "
                                     f"placement class 'BlockPlacement{place}' "
                                     f"found! » — {name}"))

        # Texture : chaque partie doit etre un entier
        texture = _ref_value(ctx, blocks, name, 'Texture')
        if texture is not None:
            texture = texture.strip().strip('"')
            for part in texture.split(','):
                if not _int_strict(part):
                    issues.append(_issue(rel, "error",
                                         f"moteur (chargeur blocs) : « Error "
                                         f"parsing texture id '{part.strip()}' "
                                         f"in block {name} »"))
                    break

        # references de blocs par NOM (sensibles a la casse) : Init()
        for key in ("TemplateRoot", "BlockChangeTop", "ChildBlocks",
                    "ParentBlocks"):
            raw = _ref_value(ctx, blocks, name, key)
            if raw is None:
                continue
            raw = raw.strip().strip('"')
            for part in raw.split(','):
                part = part.strip().strip('"')
                if part and part != name and part not in blocks:
                    issues.append(_issue(rel, "error",
                                         f"moteur (chargeur blocs) : « Block "
                                         f"'{part}' not found on block {bid} » "
                                         f"— {key}: sur {name}"))

        # Shape principal -> classe BlockShape* (defaut implicite « Cube ») ;
        # registre « BlockShape » du jeu + classes C# nommees. ATTENTION : les
        # ChildShapes ne sont JAMAIS resous en classes (faux positif assure) —
        # pas de check sur elles.
        shape = _ref_value(ctx, blocks, name, 'Shape')
        shape = shape.strip().strip('"') if shape is not None else "Cube"
        if shape not in BLOCKSHAPE_CLASSES and (
                not vanilla_shapes or shape not in vanilla_shapes):
            issues.append(_issue(rel, "error",
                                 f"moteur (chargeur blocs) : « No shape class "
                                 f"'BlockShape{shape}' found » — {name}"))

# ---------------------------------------------------------------------------
# TechTree — ConfigTree (+ parseur ECF)
# ---------------------------------------------------------------------------

def _check_techtree(ctx: _Ctx, issues: List[LaunchIssue]) -> None:
    from .tech_tree import load_tech_tree
    targets = _template_targets(ctx._paths("Templates.ecf"))

    tree = load_tech_tree(ctx.blocks_path, ctx.items_path,
                          vanilla_root=str(ctx.vanilla_conf)
                          if ctx.vanilla_conf else "")
    for n in tree.nodes:
        visible = any(c not in ("Hidden", "") for c in n.categories)
        if visible and targets and n.name not in targets:
            issues.append(_issue(
                f"{_CONF}/{'BlocksConfig.ecf' if n.source == 'block' else 'ItemsConfig.ecf'}",
                "warning",
                f"moteur (arbre technologique) : « No template found for "
                f"{n.name} » — aucun Template ne vise ce bloc (Target:), pas "
                f"de barre constructeur en jeu"))

    # recursion des chaines TechTreeParent (le jeu jette au 8e ancetre)
    parents: Dict[str, str] = {}
    for n in tree.nodes:
        if n.parent_name:
            parents[n.name] = n.parent_name

    def _chain_depth(name: str) -> Tuple[int, Optional[str]]:
        seen = {name}
        cur = name
        depth = 0
        while True:
            parent = parents.get(cur)
            if not parent or parent in seen:
                return depth, None
            depth += 1
            if depth > _MAX_ANCESTORS:
                return depth, parent
            seen.add(parent)
            cur = parent

    faulty = {n.name for n in tree.nodes if n.parent_name
              and _chain_depth(n.name)[1] is not None}
    for n in tree.nodes:
        if n.name not in faulty:
            continue
        # une seule erreur par chaine : les descendants d'un noeud deja
        # fautif sont couverts par celui-ci (le jeu jette a la premiere)
        cur, covered = n.parent_name, False
        while cur in parents:
            if cur in faulty:
                covered = True
                break
            cur = parents[cur]
        if covered:
            continue
        depth, at = _chain_depth(n.name)
        issues.append(_issue(
            f"{_CONF}/{'BlocksConfig.ecf' if n.source == 'block' else 'ItemsConfig.ecf'}",
            "error",
            f"moteur (arbre technologique) : « TechTree recursion "
            f"error: object = {at} » — chaine TechTreeParent plus "
            f"profonde que la limite du moteur depuis {n.name}"))

    # indices d'onglet « Nom$N » contradictoires sur le meme nom de categorie
    sort_seen: Dict[str, Set[int]] = {}
    for fname, kinds in (("BlocksConfig.ecf", {"Block", "+Block"}),
                         ("ItemsConfig.ecf", {"Item", "+Item"})):
        p = ctx.conf / fname
        if not p.exists():
            continue
        doc = get_parsed_doc(p)
        for b in doc.iter_blocks():
            if b.kind not in kinds or not _name(b):
                continue
            raw = b.get_property('TechTreeNames')
            for token in parse_quoted_list(raw) or []:
                token = token.strip()
                if '$' not in token:
                    continue
                cat, _, suffix = token.rpartition('$')
                try:
                    idx = int(suffix.strip())
                except ValueError:
                    continue
                seen = sort_seen.setdefault(cat, set())
                if idx not in seen and seen:
                    other = sorted(seen)[0]
                    issues.append(_issue(
                        f"{_CONF}/{fname}", "error",
                        f"moteur (arbre technologique) : « Tech tree '{cat}' "
                        f"is used with different sort indices ({idx} and "
                        f"{other}) »"))
                seen.add(idx)


def _check_ecf_parse(ctx: _Ctx, issues: List[LaunchIssue]) -> None:
    """Parseur ECF du jeu : element sans Id NI Name = LogError + IGNORE
    (StoreInDynamicProps)."""
    for fname, kinds in (("BlocksConfig.ecf", {"Block", "+Block"}),
                         ("ItemsConfig.ecf", {"Item", "+Item"})):
        p = ctx.conf / fname
        if not p.exists():
            continue
        doc = get_parsed_doc(p)
        for b in doc.iter_blocks():
            if b.kind not in kinds:
                continue
            if b.get('Name') is None and b.get('Id') is None \
                    and b.get_property('Name') is None:
                issues.append(_issue(
                    f"{_CONF}/{fname}", "error",
                    f"moteur (parseur ECF) : « ECF config contains an element "
                    f"start line without an id or name » — element {b.kind} "
                    f"ignore par le jeu"))


def run_engine_loader_checks(root: Path, vanilla_content: str = "") -> list[LaunchIssue]:
    """Les checks « chargeurs du moteur » du bilan : repliquent les
    validations fatales des chargeurs ECF/TechTree du jeu (voir docstring du
    module). Retourne des LaunchIssue de categorie check="engine"."""
    ctx = _Ctx(Path(root),
               Path(vanilla_content) / "Configuration" if vanilla_content else None)
    issues: List[LaunchIssue] = []
    _check_ecf_parse(ctx, issues)
    _check_blocks(ctx, issues)
    _check_items(ctx, issues)
    _check_techtree(ctx, issues)
    return issues
