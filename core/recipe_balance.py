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

"""Equilibrage des RECETTES de craft (Templates*.ecf) par la puissance
reelle des blocs/items (chantier 23/10/2026).

Doctrine validee avec l'utilisateur :
  1. PERIMETRE : tous les templates (blocs ET items, composants compris).
  2. COMPOSITION : pour un template qui existe en vanille, la liste
     d'ingredients de la vanille redevient la base ; pour un template
     scenario-only, la liste de l'auteur est conservee. Dans les deux cas,
     les quantites sont remises a l'echelle pour conserver le COUT TOTAL
     actuel du bloc (l'echelle economique de l'auteur n'est pas deplacee).
  3. PUISSANCE : une statistique principale par classe (EnergyOut,
     ThrusterForce, ShieldCapacity, Damage x ROF, Volume, Armor...), plus
     UnlockLevel comme contrainte secondaire a puissance egale. Les objets
     sans statistique (composants, lingots, nourriture) utilisent un proxy
     economique : la valeur de fabrication VANILLE de l'objet.
  4. FAMILLE : classe x type de vaisseau (TechTreeNames). Un generateur SV
     n'est jamais compare a un generateur CV.
  5. TEMPLATE PARTAGE : la puissance retenue est la MAXIMALE du groupe de
     blocs qui pointent dessus (une recette est par template, pas par
     variante).
  6. COHERENCE : regressions isotoniques (PAVA) en log-cout par famille.
     Le cout est rendu non decroissant avec la puissance, en modifiant le
     moins possible les valeurs de l'auteur (certains baissent, d'autres
     montent).
  7. ECRITURE : quantites entieres (min 1 par ligne, 0 reste 0) et
     CraftTime ajuste du meme facteur, plafonne a x10. Backup central,
     jamais de .bak a cote des fichiers du jeu.

La vanille n'est jamais ecrite. Une recette dont la composition vanille
contient un ingredient absent du scenario est laissee intacte (signal
dans le detail) pour ne jamais produire un template invalide.
"""
from __future__ import annotations

import math
import re
import statistics

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from core.ecf.model import (EcfBlock, EcfDocument, EcfProperty,
                            add_property_line, detect_ingredient_pairs)
from core.ecf.parser import parse_ecf_file
from core.market_balance import config_dir
from core.fsutil import atomic_write_text

VANILLA = "vanilla"
SCENARIO = "scenario"
MIN_RELATIVE_CHANGE = 0.02    # sous 2 %, le cout est considere identique (bruit d'arrondi)
CRAFT_FACTOR_CAP = 10.0       # CraftTime : jamais plus de x10 en une passe
CRAFT_SENTINEL = 100_000      # CraftTime sentinelle (items internes/IA)
MAX_COST_FACTOR = 4.0         # ecart max par passe (relancer pour converger)
STRUCTURAL_CATEGORIES = {"buildingblocks", "blocks", "hull", "structural"}

_STAT_CHILD_RE = re.compile(r"^child\s*\d+$")
_WEAPON_CLASSES = {"Weapon", "TurretAuto", "TurretManual", "ZiraxMinigun"}

# statistique principale par classe (dans l'ordre de repli)
_POWER_FIELDS: Dict[str, Tuple[str, ...]] = {
    "Generator": ("EnergyOut",),
    "SolarPanel": ("EnergyOut", "SolarPanelEfficiency"),
    "Thruster": ("ThrusterForce",),
    "ShieldGenerator": ("ShieldCapacity",),
    "WarpDrive": ("RangeLY",),
    "Teleporter": ("RangeLY",),
    "FuelTank": ("Volume",),
    "Container": ("Volume",),
    "O2Tank": ("Volume",),
    "Core": ("CPUOut", "HitPoints"),
}


# ------------------------------------------------------------------ modeles

@dataclass
class Recipe:
    """Un template du scenario (ou de la vanille, en lecture seule)."""
    name: str
    path: Path
    doc: EcfDocument
    node: EcfBlock
    inputs: List[Tuple[str, float]]
    input_block: Optional[EcfBlock]
    output_count: int
    craft_time: float


@dataclass
class ObjDef:
    """Derniere definition d'un bloc/item (les patches +Block last-wins)."""
    name: str
    kind: str
    path: Path
    doc: EcfDocument
    node: EcfBlock


@dataclass
class RecipeIndex:
    recipes: Dict[str, Recipe] = field(default_factory=dict)
    vrecipes: Dict[str, Recipe] = field(default_factory=dict)
    objs: Dict[str, ObjDef] = field(default_factory=dict)
    vobjs: Dict[str, ObjDef] = field(default_factory=dict)
    value_cache: Dict[str, float] = field(default_factory=dict)
    power_cache: Dict[str, Optional[float]] = field(default_factory=dict)
    kind_cache: Dict[str, str] = field(default_factory=dict)
    cycle_nodes: set = field(default_factory=set)


@dataclass
class Proposal:
    """Une recette proposee, avec son etat AVANT et APRES."""
    name: str
    kind: str                 # 'block' | 'item'
    family: str
    power: float
    level: Optional[float]
    old_inputs: List[Tuple[str, int]]
    new_inputs: List[Tuple[str, int]]
    old_cost: float           # cout de la recette AVANT
    new_cost: float           # cout de la recette APRES ecriture
    target_cost: float        # cible isotonique (avant arrondi)
    old_craft: int
    new_craft: int
    source: str               # 'vanilla' | 'scenario'
    detail: str
    path: Path
    doc: EcfDocument
    node: EcfBlock
    changed: bool
    proxy: bool = False       # puissance = proxy (valeur/masse), pas une stat


# --------------------------------------------------------------- utilitaires

def _num(raw) -> Optional[float]:
    if raw is None:
        return None
    v = str(raw).strip().strip('"').split(",")[0].strip()
    try:
        return float(v)
    except ValueError:
        return None


def _has_inputs(rec: Optional[Recipe]) -> bool:
    return bool(rec and any(q > 0 for _, q in rec.inputs))


def _ints(inputs: Sequence[Tuple[str, float]]) -> List[Tuple[str, int]]:
    return [(name, max(0, int(round(q)))) for name, q in inputs]


def _same_inputs(a: Sequence[Tuple[str, int]],
                 b: Sequence[Tuple[str, int]]) -> bool:
    """Comparaison SANS l'ordre : le rendu peut deplacer les lignes sans
    changer la recette (vecu 23/10 : re-propositions fantomes)."""
    return dict(a) == dict(b)


def _stat_prop(node: EcfBlock, key: str) -> Optional[str]:
    """Propriete du bloc, puis de ses sous-blocs 'Child 0', 'Child 1'..."""
    val = node.get_property(key)
    if val is not None:
        return val
    for child in node.children:
        if not isinstance(child, EcfBlock):
            continue
        kind = child.kind.lstrip("+-").strip().lower()
        if not _STAT_CHILD_RE.match(kind):
            continue
        val = _stat_prop(child, key)
        if val is not None:
            return val
    return None


def resolve_prop(idx: RecipeIndex, name: str, key: str,
                 depth: int = 0) -> Optional[str]:
    """Propriete effective : derniere definition, sous-blocs Child n, puis
    chaine Ref (les blocs RE2 heritent massivement par Ref)."""
    if depth > 12:
        return None
    obj = idx.objs.get(name)
    if obj is None:
        return None
    val = _stat_prop(obj.node, key)
    if val is not None:
        return val
    ref = obj.node.get("Ref") or obj.node.get("REF")
    if ref:
        return resolve_prop(idx, ref.strip().strip('"'), key, depth + 1)
    return None


def _value(idx: RecipeIndex, name: str,
           stack: frozenset = frozenset()) -> float:
    """Valeur de fabrication en unites VANILLE : recette vanille d'abord
    (unite stable), sinon recette scenario (objets ajoutes), sinon
    MarketPrice vanille, sinon MarketPrice scenario, sinon 1.
    Les cycles de recyclage (TitanOre <-> TitanPlates) retombent sur la
    valeur feuille au lieu de boucler."""
    if name in idx.cycle_nodes:
        # boucle volontaire (TitanOre -> TitanPlates -> TitanRods -> TitanOre) :
        # la feuille officielle fixe la valeur, aucune recursion possible
        return _leaf_value(idx, name)
    cached = idx.value_cache.get(name)
    if cached is not None:
        return cached
    if name in stack:
        return _leaf_value(idx, name)
    rec = idx.vrecipes.get(name)
    if not _has_inputs(rec):
        rec = idx.recipes.get(name)
    if _has_inputs(rec):
        total = 0.0
        for ing, qty in rec.inputs:
            if qty > 0:
                total += qty * _value(idx, ing, stack | {name})
        value = total / max(1, rec.output_count)
    else:
        value = _leaf_value(idx, name)
    idx.value_cache[name] = value
    return value


def _value_recipe(idx: RecipeIndex, name: str) -> Optional[Recipe]:
    """Recette utilisee pour VALORISER : vanille d'abord, sinon scenario."""
    rec = idx.vrecipes.get(name)
    if _has_inputs(rec):
        return rec
    rec = idx.recipes.get(name)
    return rec if _has_inputs(rec) else None


def _mark_cycles(idx: RecipeIndex) -> None:
    """Composantes fortement connexes : les noeuds d'un cycle de recettes
    sont valorises a leur feuille officielle, jamais par recursion."""
    graph: Dict[str, List[str]] = {}
    for name in set(idx.recipes) | set(idx.vrecipes):
        rec = _value_recipe(idx, name)
        graph[name] = [ing for ing, qty in rec.inputs if qty > 0] if rec else []
    counter = [0]
    stack: List[str] = []
    on_stack: set = set()
    order: Dict[str, int] = {}
    low: Dict[str, int] = {}
    cycles: set = set()

    import sys
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(limit, len(graph) * 2 + 100))
    try:
        def visit(start: str) -> None:
            work = [(start, 0)]
            while work:
                node, pos = work[-1]
                if pos == 0:
                    order[node] = low[node] = counter[0]
                    counter[0] += 1
                    stack.append(node)
                    on_stack.add(node)
                neighbours = graph.get(node, [])
                if pos < len(neighbours):
                    work[-1] = (node, pos + 1)
                    nxt = neighbours[pos]
                    if nxt not in order:
                        work.append((nxt, 0))
                    elif nxt in on_stack:
                        low[node] = min(low[node], order[nxt])
                    continue
                work.pop()
                if work:
                    parent = work[-1][0]
                    low[parent] = min(low[parent], low[node])
                if low[node] == order[node]:
                    component: List[str] = []
                    while True:
                        popped = stack.pop()
                        on_stack.discard(popped)
                        component.append(popped)
                        if popped == node:
                            break
                    if len(component) > 1 or node in graph.get(node, ()):
                        cycles.update(component)

        for name in graph:
            if name not in order:
                visit(name)
    finally:
        sys.setrecursionlimit(limit)
    idx.cycle_nodes = cycles


def _obj_price(objs: Dict[str, ObjDef], name: str,
               depth: int = 0) -> Optional[float]:
    """MarketPrice effectif d'un objet, chaine Ref comprise."""
    if depth > 12:
        return None
    obj = objs.get(name)
    if obj is None:
        return None
    price = _num(_stat_prop(obj.node, "MarketPrice"))
    if price is not None:
        return price
    ref = obj.node.get("Ref") or obj.node.get("REF")
    if ref:
        return _obj_price(objs, ref.strip().strip('"'), depth + 1)
    return None


def _leaf_value(idx: RecipeIndex, name: str) -> float:
    for objs in (idx.vobjs, idx.objs):
        price = _obj_price(objs, name)
        if price and price > 0:
            return float(price)
    return 1.0


def _recipe_cost(idx: RecipeIndex, inputs: Sequence[Tuple[str, float]],
                 output_count: int) -> float:
    total = 0.0
    for ing, qty in inputs:
        if qty > 0:
            total += qty * _value(idx, ing)
    return total / max(1, output_count)


def _mass_volume_proxy(idx: RecipeIndex, name: str) -> float:
    mass = _num(resolve_prop(idx, name, "Mass")) or 0.0
    size = resolve_prop(idx, name, "SizeInBlocks") or ""
    volume = 1.0
    parts = [p for p in size.replace('"', "").split(",") if p.strip()]
    try:
        nums = [float(p) for p in parts]
        if nums:
            volume = max(1.0, math.prod(nums))
    except ValueError:
        volume = 1.0
    if mass <= 0:
        return 1.0
    return mass * volume


def _weapon_power(idx: RecipeIndex, name: str) -> Optional[float]:
    damage = _num(resolve_prop(idx, name, "Damage"))
    rof = _num(resolve_prop(idx, name, "ROF"))
    if damage is None:
        weapon_item = resolve_prop(idx, name, "WeaponItem")
        if weapon_item:
            item = weapon_item.strip().strip('"')
            damage = _num(resolve_prop(idx, item, "Damage"))
            if rof is None:
                rof = _num(resolve_prop(idx, item, "ROF"))
    if damage is None:
        ammo = resolve_prop(idx, name, "AmmoType")
        if ammo:
            ammo = ammo.strip().strip('"')
            damage = _num(resolve_prop(idx, ammo, "Damage"))
            blast = _num(resolve_prop(idx, ammo, "BlastDamage")) or 0.0
            damage = (damage or 0.0) + blast
    if damage is None or damage <= 0:
        return None
    return damage * max(rof or 1.0, 0.01)


def _power_info(idx: RecipeIndex, name: str) -> Tuple[Optional[float], str]:
    """(puissance, nature). 'stat' = vraie statistique de jeu ;
    'value' = proxy economique ; 'mass' = proxy structurel."""
    if name in idx.kind_cache:
        return idx.power_cache.get(name), idx.kind_cache[name]
    obj = idx.objs.get(name)
    if obj is None:
        return None, "value"
    cls = (resolve_prop(idx, name, "Class") or "").strip()
    power: Optional[float] = None
    kind = "value"
    if obj.kind == "block":
        if cls in _WEAPON_CLASSES:
            power = _weapon_power(idx, name)
            kind = "stat"
        if power is None:
            for field_name in _POWER_FIELDS.get(cls, ()):
                val = _num(resolve_prop(idx, name, field_name))
                if val and val > 0:
                    power = val
                    kind = "stat"
                    break
        if power is None:
            # sans classe : masse x volume UNIQUEMENT pour le structurel
            # (une antenne deco a une masse de 80 t sans rapport avec son
            # cout reel) ; partout ailleurs, proxy economique.
            category = (resolve_prop(idx, name, "Category") or "").strip().lower()
            if not cls and category in STRUCTURAL_CATEGORIES:
                power, kind = _mass_volume_proxy(idx, name), "mass"
            else:
                power, kind = _value(idx, name), "value"
    else:
        if cls in ("Ranged", "Melee"):
            power = _weapon_power(idx, name)
            kind = "stat"
        elif cls == "Projectile":
            damage = _num(resolve_prop(idx, name, "Damage")) or 0.0
            blast = _num(resolve_prop(idx, name, "BlastDamage")) or 0.0
            power = damage + blast
            kind = "stat"
        elif cls in ("Armor", "ArmorBoost"):
            power = _num(resolve_prop(idx, name, "Armor"))
            kind = "stat"
        if power is None:
            # proxy economique : la valeur de fabrication vanille
            power, kind = _value(idx, name), "value"
    idx.power_cache[name] = power
    idx.kind_cache[name] = kind
    return power, kind


def power_of(idx: RecipeIndex, name: str) -> Optional[float]:
    return _power_info(idx, name)[0]


def resolve_template_name(idx: RecipeIndex, name: str,
                          depth: int = 0) -> Optional[str]:
    """Template effectif : Name direct, sinon TemplateRoot, sinon Ref."""
    if name in idx.recipes:
        return name
    obj = idx.objs.get(name)
    if obj is None or depth > 12:
        return None
    root = obj.node.get_property("TemplateRoot")
    if root:
        root = root.strip().strip('"')
        if root in idx.recipes:
            return root
    ref = obj.node.get("Ref") or obj.node.get("REF")
    if ref:
        return resolve_template_name(idx, ref.strip().strip('"'), depth + 1)
    return None


def level_of(idx: RecipeIndex, name: str) -> Optional[float]:
    return _num(resolve_prop(idx, name, "UnlockLevel"))


def family_of(idx: RecipeIndex, name: str) -> str:
    """Classe x type de vaisseau. Repli sur Category quand il n'y a pas de
    Class (blocs structurels, composants, nourriture) : sans ce repli, tous
    les objets sans classe atterrissaient dans une seule famille geante.
    Le genre (block/item) est prefixe pour ne jamais comparer un bloc
    structurel a un item de meme categorie."""
    cls = (resolve_prop(idx, name, "Class") or "").strip()
    if not cls:
        category = (resolve_prop(idx, name, "Category") or "").strip()
        obj = idx.objs.get(name)
        kind = obj.kind if obj else "obj"
        cls = f"{kind}:{category}" if category else kind
    tree = (resolve_prop(idx, name, "TechTreeNames") or "").strip().strip('"')
    return f"{cls} / {tree or '(sans type)'}"


# ------------------------------------------------------------------ lecture

def _read_recipes(path: Path, doc: EcfDocument,
                  out: Dict[str, Recipe]) -> None:
    for node in doc.nodes:
        if not isinstance(node, EcfBlock):
            continue
        if "template" not in node.kind.lstrip("+-").lower():
            continue
        name = (node.get("Name") or "").strip().strip('"')
        if not name:
            continue
        inputs: List[Tuple[str, float]] = []
        input_block: Optional[EcfBlock] = None
        for child in node.child_blocks():
            if "inputs" not in child.kind.lstrip("+-").lower():
                continue
            rows = detect_ingredient_pairs(child)
            if rows is None:
                # format inattendu (plusieurs paires par ligne) : lecture
                # brute, l'ecriture retombera sur la composition d'origine
                for prop in child.children:
                    if not isinstance(prop, EcfProperty):
                        continue
                    for key, raw in prop.pairs:
                        if key:
                            inputs.append((key, _num(raw) or 0.0))
            else:
                input_block = child
                for prop, key in rows:
                    inputs.append((key, _num(prop.get(key)) or 0.0))
            break
        out[name] = Recipe(
            name=name,
            path=path,
            doc=doc,
            node=node,
            inputs=inputs,
            input_block=input_block,
            output_count=max(1, int(_num(node.get_property("OutputCount")) or 1)),
            craft_time=_num(node.get_property("CraftTime")) or 0.0,
        )


def _read_objs(path: Path, doc: EcfDocument, kind: str,
               out: Dict[str, ObjDef]) -> None:
    want = kind.lower()
    for node in doc.nodes:
        if not isinstance(node, EcfBlock):
            continue
        if node.kind.lstrip("+-").strip().lower() != want:
            continue
        name = (node.get("Name") or "").strip().strip('"')
        if not name:
            continue
        out[name] = ObjDef(name=name, kind=kind.lower(), path=path, doc=doc,
                           node=node)


def load_recipe_index(root, vanilla_root: str = ""
                      ) -> Tuple[RecipeIndex, Optional[RecipeIndex]]:
    """Parse le scenario (+ la vanille en lecture seule)."""
    cdir = config_dir(root)
    if cdir is None:
        raise FileNotFoundError(f"no Configuration dir under {root}")
    idx = RecipeIndex()
    for base, kind in (("BlocksConfig", "Block"), ("ItemsConfig", "Item")):
        for path in sorted(cdir.glob(f"{base}*.ecf")):
            doc = parse_ecf_file(path)
            _read_objs(path, doc, kind, idx.objs)
    for path in sorted(cdir.glob("Templates*.ecf")):
        _read_recipes(path, parse_ecf_file(path), idx.recipes)

    van: Optional[RecipeIndex] = None
    vdir = config_dir(vanilla_root) if vanilla_root else None
    if vdir is not None:
        v_idx = RecipeIndex()
        for base, kind in (("BlocksConfig", "Block"), ("ItemsConfig", "Item")):
            for path in sorted(vdir.glob(f"{base}*.ecf")):
                doc = parse_ecf_file(path)
                _read_objs(path, doc, kind, v_idx.vobjs)
        for path in sorted(vdir.glob("Templates*.ecf")):
            _read_recipes(path, parse_ecf_file(path), v_idx.recipes)
        # la vanille est un referentiel : objs = vobjs pour la resolution
        v_idx.objs = v_idx.vobjs
        van = v_idx
        # valorisation : recettes et prix vanille disponibles depuis idx
        idx.vrecipes = van.recipes
        idx.vobjs = van.vobjs
    _mark_cycles(idx)
    return idx, van


# ------------------------------------------------------------- isotonique

def _pava(values: Sequence[float],
          weights: Sequence[float]) -> List[float]:
    """Pool Adjacent Violators : plus proche suite non decroissante."""
    stack: List[List] = []          # [moyenne, poids, indices]
    for i, (val, weight) in enumerate(zip(values, weights)):
        stack.append([val, weight, [i]])
        while len(stack) > 1 and stack[-2][0] > stack[-1][0]:
            v2, w2, i2 = stack.pop()
            v1, w1, i1 = stack.pop()
            stack.append([(v1 * w1 + v2 * w2) / (w1 + w2),
                          w1 + w2, i1 + i2])
    out = [0.0] * len(values)
    for val, _weight, indices in stack:
        for i in indices:
            out[i] = val
    return out


# --------------------------------------------------------------- analyse

def _representatives(idx: RecipeIndex) -> Dict[str, str]:
    """Template -> bloc/item le plus puissant qui l'utilise (partage)."""
    best: Dict[str, Tuple[Tuple[float, float, bool, str], str]] = {}
    for name, obj in idx.objs.items():
        template = resolve_template_name(idx, name)
        if template is None:
            continue
        power = power_of(idx, name) or 0.0
        level = level_of(idx, name) or 0.0
        key = (power, level, name == template, name)
        current = best.get(template)
        if current is None or key > current[0]:
            best[template] = (key, name)
    return {template: name for template, (_key, name) in best.items()}


def _safe_base_inputs(idx: RecipeIndex, rec: Recipe,
                      vanilla: Optional[Recipe]) -> Optional[List[Tuple[str, float]]]:
    """Composition vanille si elle est utilisable dans le scenario."""
    if not _has_inputs(vanilla):
        return list(rec.inputs)
    missing = [name for name, qty in vanilla.inputs
               if qty > 0 and name not in idx.objs]
    if missing:
        return None
    return list(vanilla.inputs)


def analyze(root, vanilla_root: str = "",
            pinned: Optional[Dict[str, float]] = None) -> List[Proposal]:
    """Toutes les propositions (une par template), changed=False incluses.

    `pinned` = cibles deja appliquees (anti-ratchet) : elles ne sont ni
    refittees ni re-proposees, seules les recettes encore libres sont
    analysees. Le bouton Analyser du dialogue repart sans pin (analyse
    neuve) ; le re-scan post-application le passe."""
    idx, van = load_recipe_index(root, vanilla_root)
    vanilla = van or RecipeIndex()
    pinned = pinned or {}
    reps = _representatives(idx)
    staged: List[Proposal] = []
    families: Dict[str, List[int]] = {}

    for template, rec in idx.recipes.items():
        rep = reps.get(template)
        if rep is None:
            continue
        power, kind = _power_info(idx, rep)
        if power is None or power <= 0:
            continue
        level = level_of(idx, rep)
        family = family_of(idx, rep)
        obj = idx.objs[rep]
        old_inputs = _ints(rec.inputs)
        old_craft = max(0, int(round(rec.craft_time)))
        proxy = kind != "stat"

        # regle projet : une monnaie (Credits:) n'est JAMAIS touchee
        credits = _num(resolve_prop(idx, rep, "Credits"))
        if obj.kind == "item" and credits and credits > 0:
            staged.append(Proposal(
                name=template, kind=obj.kind, family=family, power=power,
                level=level, old_inputs=old_inputs, new_inputs=old_inputs,
                old_cost=_recipe_cost(idx, rec.inputs, rec.output_count),
                new_cost=_recipe_cost(idx, rec.inputs, rec.output_count),
                target_cost=0.0, old_craft=old_craft, new_craft=old_craft,
                source=SCENARIO, detail="monnaie (Credits) : intacte",
                path=rec.path, doc=rec.doc, node=rec.node, changed=False,
                proxy=True))
            continue

        # la composition vanille ne remplace QUE celle des BLOCS : les
        # items (kits, armes, munitions) gardent le design de l'auteur,
        # seules leurs quantites sont ajustees.
        if obj.kind == "block":
            base = _safe_base_inputs(idx, rec, vanilla.recipes.get(template))
        else:
            base = list(rec.inputs)
        if base is None:
            staged.append(Proposal(
                name=template, kind=obj.kind, family=family, power=power,
                level=level, old_inputs=old_inputs, new_inputs=old_inputs,
                old_cost=_recipe_cost(idx, rec.inputs, rec.output_count),
                new_cost=_recipe_cost(idx, rec.inputs, rec.output_count),
                target_cost=0.0, old_craft=old_craft, new_craft=old_craft,
                source=SCENARIO,
                detail="ingredient vanille absent du scenario : recette intacte",
                path=rec.path, doc=rec.doc, node=rec.node, changed=False,
                proxy=proxy))
            continue

        source = (VANILLA if obj.kind == "block"
                  and _has_inputs(vanilla.recipes.get(template)) else SCENARIO)
        cur_cost = _recipe_cost(idx, rec.inputs, rec.output_count)
        base_cost = _recipe_cost(idx, base, rec.output_count)
        factor = (cur_cost / base_cost
                  if base_cost > 0 and cur_cost > 0 else 1.0)
        scaled = [(name, max(1, int(round(qty * factor))) if qty > 0 else 0)
                  for name, qty in base]
        new_cost = _recipe_cost(idx, scaled, rec.output_count)
        if new_cost <= 0:
            new_cost = cur_cost

        detail_parts = ["composition vanille" if source == VANILLA
                        else "composition scenario"]
        proposal = Proposal(
            name=template, kind=obj.kind, family=family, power=power,
            level=level, old_inputs=old_inputs, new_inputs=scaled,
            old_cost=cur_cost, new_cost=new_cost, target_cost=new_cost,
            old_craft=old_craft, new_craft=old_craft, source=source,
            detail=" ; ".join(detail_parts), path=rec.path, doc=rec.doc,
            node=rec.node, changed=False, proxy=proxy)
        if template in pinned:
            # cible epinglee : deja appliquee, ne participe pas au nouveau fit
            proposal.target_cost = pinned[template]
        staged.append(proposal)
        if new_cost > 0 and template not in pinned:
            families.setdefault(family, []).append(len(staged) - 1)

    # ---------------------------------------------- monotonie par famille
    for indices in families.values():
        stats = [i for i in indices if not staged[i].proxy]
        proxies = [i for i in indices if staged[i].proxy]
        if stats:
            # vraie statistique : isotonique (ecart minimal en log-cout)
            ordered = sorted(stats, key=lambda i: (
                staged[i].power, staged[i].level or 0.0, staged[i].name))
            logs = [math.log(max(staged[i].new_cost, 1e-9)) for i in ordered]
            fitted = _pava(logs, [1.0] * len(logs))
            for pos, i in enumerate(ordered):
                staged[i].target_cost = math.exp(fitted[pos])
        if proxies:
            # famille "proxy" : le cout doit rester PROPORTIONNEL a la
            # valeur/masse. L'isotonique pure aplatirait tous les
            # composants a un meme cout (vecu en dry-run RE2).
            ratios = [staged[i].new_cost / staged[i].power for i in proxies
                      if staged[i].power > 0 and staged[i].new_cost > 0]
            if ratios:
                scale = statistics.median(ratios)
                for i in proxies:
                    staged[i].target_cost = staged[i].power * scale

    # --------------------------------------------- quantites / CraftTime
    for proposal in staged:
        if proposal.target_cost <= 0 or proposal.new_cost <= 0:
            continue
        # ecretage : un seul passage ne peut pas deplacer un cout de x4000
        # (vecu : bloc deco a 1 372 -> 5,8 M). Une cible EPINGLEE est deja
        # le resultat d'un ecretage : on l'applique telle quelle, sinon le
        # re-scan la re-ecreterait a chaque passe (ratchet).
        if proposal.name not in pinned:
            clamped = min(max(proposal.target_cost,
                              proposal.new_cost / MAX_COST_FACTOR),
                          proposal.new_cost * MAX_COST_FACTOR)
            if clamped != proposal.target_cost:
                proposal.target_cost = clamped
                proposal.detail += f" ; cible ecretee x{MAX_COST_FACTOR:g}"
        ratio = proposal.target_cost / proposal.new_cost
        rel = abs(proposal.target_cost - proposal.new_cost) / proposal.new_cost
        if rel < MIN_RELATIVE_CHANGE:
            ratio = 1.0
        qty = [(name, max(1, int(round(q * ratio))) if q > 0 else 0)
               for name, q in proposal.new_inputs]
        achieved = _recipe_cost(idx, qty, _output_count(idx, proposal.name))
        craft = proposal.old_craft
        new_craft = craft
        # le CraftTime suit le cout REELLEMENT atteint, pas la cible
        # theorique : sinon une recette saturee (quantites a 1) changerait
        # de temps a chaque re-scan sans jamais converger.
        old_cost = _recipe_cost(idx, proposal.old_inputs,
                                _output_count(idx, proposal.name))
        achieved_ratio = (achieved / old_cost
                          if old_cost > 0 and achieved > 0 else 1.0)
        # plancher de GRANULARITE : si l'arrondi entier ne deplace plus le
        # cout (<0,5 %) alors que la cible est encore loin, aucune passe
        # supplementaire ne convergera (vecu 23/10 : tail de 12 recettes).
        move = abs(achieved - old_cost) / old_cost if old_cost > 0 else 0.0
        gap = (abs(proposal.target_cost - old_cost) / old_cost
               if old_cost > 0 else 0.0)
        granular_floor = move < 0.005 and gap > 0.02
        if granular_floor:
            qty = proposal.old_inputs
            new_craft = proposal.old_craft
            achieved = old_cost
            proposal.detail += " ; plancher de granularite"
        if (0 < craft < CRAFT_SENTINEL and achieved_ratio != 1.0
                and not granular_floor):
            capped = min(achieved_ratio, CRAFT_FACTOR_CAP)
            new_craft = max(1, int(round(craft * capped)))
        floor = (ratio < 1.0 and any(
            q > 1 for _n, q in proposal.new_inputs)
            and _same_inputs(qty, [(n, 1 if q > 0 else 0)
                                   for n, q in proposal.new_inputs]))
        # cible epinglee deja appliquee : un residu de granularite (<5 %)
        # ne doit pas relancer une salve a chaque re-scan (vecu 23/10).
        pinned_residual = (proposal.name in pinned
                           and proposal.target_cost > 0 and achieved > 0
                           and abs(achieved - proposal.target_cost)
                           / proposal.target_cost <= 0.05)
        if pinned_residual:
            qty = proposal.old_inputs
            new_craft = proposal.old_craft
            achieved = proposal.old_cost
            proposal.detail += " ; cible epinglee atteinte (residu <5%)"
        proposal.new_inputs = qty
        proposal.new_craft = new_craft
        proposal.new_cost = achieved if achieved > 0 else proposal.new_cost
        if floor:
            proposal.detail += " ; plancher de quantites atteint"
        if achieved_ratio != 1.0 and not pinned_residual:
            proposal.detail += f" ; cout x{achieved_ratio:.2f}"
        proposal.changed = (not _same_inputs(proposal.new_inputs,
                                             proposal.old_inputs)
                            or proposal.new_craft != proposal.old_craft)
        if not proposal.changed:
            proposal.detail += " ; deja coherent"
    return staged


def _output_count(idx: RecipeIndex, name: str) -> int:
    rec = idx.recipes.get(name)
    return max(1, rec.output_count) if rec else 1


# ---------------------------------------------------------------- ecriture

def _find_inputs_block(node: EcfBlock) -> Optional[EcfBlock]:
    for child in node.child_blocks():
        if "inputs" in child.kind.lstrip("+-").lower():
            return child
    return None


def _new_inputs_block(node: EcfBlock) -> EcfBlock:
    indent = node.indent + "  "
    eol = node.eol or "\r\n"
    return EcfBlock(indent=indent, kind="Child Inputs", pairs=[], comment=None,
                    eol=eol, raw_open="", close_raw=indent + "}" + eol,
                    children=[], dirty=True)


def _rewrite(proposal: Proposal) -> None:
    """Ecrit la composition et le CraftTime dans le noeud du template."""
    block = _find_inputs_block(proposal.node)
    if block is None:
        if proposal.new_inputs:
            block = _new_inputs_block(proposal.node)
            proposal.node.children.append(block)
        else:
            block = None
    if block is not None:
        rows = detect_ingredient_pairs(block)
        if rows is not None:
            existing = {key: prop for prop, key in rows}
            indent = rows[0][0].indent if rows else block.indent + "  "
            eol = rows[0][0].eol if rows else block.eol
            for name, qty in proposal.new_inputs:
                prop = existing.pop(name, None)
                if prop is not None:
                    prop.set(name, str(int(qty)))
                else:
                    block.children.append(EcfProperty(
                        raw="", indent=indent, pairs=[(name, str(int(qty)))],
                        comment=None, eol=eol, dirty=True))
            for prop in existing.values():
                if prop in block.children:
                    block.children.remove(prop)
    if proposal.new_craft != proposal.old_craft:
        if not proposal.node.set_property("CraftTime",
                                          str(int(proposal.new_craft))):
            add_property_line(proposal.node,
                              [("CraftTime", str(int(proposal.new_craft)))])


def apply_proposals(proposals: Sequence[Proposal]) -> Dict[Path, int]:
    """Ecrit les propositions modifiees ; backup central + atomique."""
    from core.fsutil import central_backup   # local : monkeypatch conftest
    by_file: Dict[Path, List[Proposal]] = {}
    for proposal in proposals:
        if proposal.changed:
            by_file.setdefault(proposal.path, []).append(proposal)
    done: Dict[Path, int] = {}
    for path, items in by_file.items():
        for proposal in items:
            _rewrite(proposal)
        central_backup(path, "recipe_balance")
        atomic_write_text(path, items[0].doc.render())
        done[path] = len(items)
    return done
