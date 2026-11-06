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

"""Codex : couche de DONNEES (sans Qt) du navigateur d'objets/blocs,
recettes, marchands et matrice de degats — portage du Codex communautaire
(Empyrion Codex 1.4.0) sur nos propres parseurs ECF.

Regles portees du Codex, a ne pas « ameliorer » sans preuve dans le jeu :
  - PRIX : MarketPrice declare, sinon herite par chaine Ref (le jeu fait de
    meme) ; `mf=` d'un marchand s'applique a ce prix, une plage absolue non.
  - RECETTE APLATIE : recursion jusqu'aux materiaux de base, SAUF les 4
    minerais (NO_EXPAND) et garde anti-cycle ; le temps de craft cumule
    celui des sous-recettes, pas la recette racine.
  - MATRICE DE DEGATS : cellules = MAXIMUM des multiplicateurs directs
    couvrant la categorie ; les seuils des 4 paliers sont EMPIRIQUES par
    colonne (percentiles 25/75/90, interpolation lineaire), pas des valeurs
    absolues — c'est le choix du Codex, il evite les « 0,05 parait extreme »
    compares a des armes qui ne visent pas ce materiau.
  - un multiplicateur ABSENT (pas d'entree ECF) n'est pas 1x pour l'echelle :
    il est exclu des percentiles et affiche « defaut ». Un 0 explicite est
    une immunite (« aucun »), jamais un point bas de l'echelle.
Scenario prioritaire sur la vanille (meme nom = la derniere definition de
la copie de travail gagne, comme au chargement par le moteur)."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from core.ecf.model import EcfBlock, EcfProperty
from core.ecf.parser import parse_ecf_file
from core.economy.model import RangeSpec, TradeItem
from core.localization_lookup import LocalizationIndex, build_localization_index
from core.market_balance import _num, config_dir
from core.settings import CONFIG_DIR

KIND_ITEM, KIND_BLOCK, KIND_TOKEN = "item", "block", "token"

# Fichiers par famille de donnees (glob `base*.ecf`, donc `+Block` inclus).
_FILES = {
    KIND_ITEM: "ItemsConfig",
    KIND_BLOCK: "BlocksConfig",
    KIND_TOKEN: "TokenConfig",
    "template": "Templates",
    "material": "MaterialConfig",
    "trader": "TraderNPCConfig",
    "damage": "DamageMultiplierConfig",
}

# Exclusions du Codex (le scenario peut legitimer ces noms : ils restent
# presents dans les donnees, seulement masques par defaut dans la grille).
NAME_SKIP = ("Template", "Debug", "_Old", "(POI)", "Enemy")

# Minerais jamais aplatis : le joueur les mine, il ne les craft pas.
NO_EXPAND = frozenset({"IronOre", "CopperOre", "Graphite", "SiliconOre"})

# Paliers de la matrice : percentiles du Codex (manifeste vanilla).
TIER_PERCENTILES = (("ineffective", 25.0), ("normal", 75.0), ("effective", 90.0))

# Proprietes de bruit : jamais affichees dans la fiche (le Codex a une liste
# noire de ~150 cles ; on couvre les familles, le reste reste consultable).
_NOISE = re.compile(
    r"^(Mesh|Shape|Sfx|Sound|Particle|Pfx|Texture|Drop|Model|Tracer|Radial|Map)"
    r"|^(DamageMultiplier_|BlastDamageMultiplier_|Class$|display$|param1$|type$|formatter$)",
    re.I,
)
_MULT = re.compile(r"^(Blast)?DamageMultiplier_\d+$", re.I)
_ITEM_LINE = re.compile(r"^Item(\d+)$")
# Balises BBCode du jeu (relevees dans le pack de localisation) : couleurs
# hexa, [c]/[-], [b], [i], [u], [sup]. Volontairement ETROIT : `[T2]` ou
# `[POI]` dans un nom ne sont pas des balises et doivent rester lisibles.
_BBCODE = re.compile(r"\[(?:/?c|/?b|/?i|/?u|/?sup|-|[0-9a-fA-F]{3,8})\]")
_TOKEN_REF = re.compile(r"^Token:(\d+)", re.I)


# --------------------------------------------------------------- utilitaires

def _clean(raw) -> str:
    """Valeur ECF -> texte nu (guillemets externes retires)."""
    return (raw or "").strip().strip('"').strip()


def _flag(raw) -> bool:
    """ShowUser/RemoveOnUse : absent = vrai ; 'No'/'false' = faux."""
    text = _clean(raw).lower()
    return text not in ("no", "false", "0")


def _props_of(node: EcfBlock) -> Iterable[Tuple[str, str]]:
    """(cle, valeur) des lignes de propriete d'un bloc — premiere paire
    seulement : `param1`/`display`/`type` sont des MODIFICATEURS de la meme
    ligne, pas des proprietes distinctes."""
    for child in node.children:
        if isinstance(child, EcfProperty) and child.pairs:
            key, value = child.pairs[0]
            if key:
                yield key, value


def _all_props(node: EcfBlock) -> Iterable[EcfProperty]:
    for child in node.children:
        if isinstance(child, EcfProperty):
            yield child
        elif isinstance(child, EcfBlock):
            yield from _all_props(child)


def _split_list(raw) -> Tuple[str, ...]:
    text = _clean(raw)
    if not text:
        return ()
    return tuple(part.strip() for part in text.split(",") if part.strip())


def _percentile(values: List[float], p: float) -> float:
    """Percentile par interpolation lineaire (convention du Codex)."""
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    idx = (p / 100.0) * (len(values) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (idx - lo)


def _qty(spec: Optional[RangeSpec]) -> Optional[Tuple[float, float]]:
    if spec is None:
        return None
    return spec.lo_f, spec.hi_f


def _off(spec: Optional[RangeSpec]) -> bool:
    """'0' comme '0-0' : la direction du trade est INACTIVE (regle du Codex)."""
    if spec is None:
        return True
    return spec.lo_f == 0 and spec.hi_f == 0


# ------------------------------------------------------------------- modeles

@dataclass
class CodexEntry:
    """Item, bloc ou jeton, tel que le Codex l'affiche. `nodes` garde TOUTES
    les definitions du meme nom (patch `+Item` compris) : scenario en
    dernier, donc dernier gagne, comme le moteur."""
    kind: str
    name: str
    id: Optional[int] = None
    props: Dict[str, str] = field(default_factory=dict)
    nodes: List[EcfBlock] = field(default_factory=list, repr=False)

    # Indirections declarees (resolues par CodexData, chaine Ref comprise).
    price: Optional[float] = None
    ref: str = ""
    damage_group: str = ""

    @property
    def hidden(self) -> bool:
        return any(sub in self.name for sub in NAME_SKIP)

    @property
    def label_key(self) -> str:
        """Cle de traduction (Info des objets, sinon le nom technique)."""
        return _clean(self.props.get("Info")) or self.name

    @property
    def category(self) -> str:
        return _clean(self.props.get("Category"))

    @property
    def show_user(self) -> bool:
        raw = self.props.get("ShowUser")
        return True if raw is None else _flag(raw)

    def num(self, *keys: str) -> Optional[float]:
        for key in keys:
            if key in self.props:
                value = _num(self.props[key])
                if value is not None:
                    return value
        return None

    @property
    def mass(self) -> Optional[float]:
        return self.num("Mass")

    @property
    def volume(self) -> Optional[float]:
        return self.num("Volume")

    @property
    def stack(self) -> Optional[float]:
        return self.num("StackSize")

    @property
    def durability(self) -> Optional[float]:
        return self.num("Durability")

    @property
    def unlock_level(self) -> Optional[float]:
        return self.num("UnlockLevel")

    @property
    def unlock_cost(self) -> Optional[float]:
        return self.num("UnlockCost")

    @property
    def hp(self) -> Optional[float]:
        return self.num("HitPoints", "HP")

    @property
    def material(self) -> str:
        return _clean(self.props.get("Material"))

    @property
    def weapon_item(self) -> str:
        return _clean(self.props.get("WeaponItem"))

    @property
    def allow_placing_at(self) -> Tuple[str, ...]:
        return _split_list(self.props.get("AllowPlacingAt"))

    @property
    def child_blocks(self) -> Tuple[str, ...]:
        return _split_list(self.props.get("ChildBlocks"))


@dataclass
class CodexTemplate:
    name: str
    craft_time: float = 0.0
    output_count: int = 1
    targets: Tuple[str, ...] = ()
    inputs: Tuple[Tuple[str, float], ...] = ()


@dataclass
class CodexTrader:
    name: str
    selling_text: str = ""
    discount: str = ""
    items: List[TradeItem] = field(default_factory=list)
    raw_lines: List[str] = field(default_factory=list)

    def sells(self, item: TradeItem) -> bool:
        return not _off(item.sell_stock)

    def buys(self, item: TradeItem) -> bool:
        return not _off(item.buy_max_stock)

    def selling(self) -> List[TradeItem]:
        return [i for i in self.items if self.sells(i)]

    def buying(self) -> List[TradeItem]:
        return [i for i in self.items if self.buys(i)]


@dataclass
class DamageGroup:
    """Multiplicateurs directs (Blast mis a part : il ne sert qu'a la vue
    « par bloc », jamais a la matrice)."""
    name: str = ""
    direct: List[Tuple[float, Tuple[str, ...]]] = field(default_factory=list)
    blast: List[Tuple[float, Tuple[str, ...]]] = field(default_factory=list)

    def mult(self, categories: Iterable[str]) -> Optional[float]:
        """MAXIMUM des multiplicateurs explicites couvrant une categorie de
        la colonne ; None = pas d'entree (le jeu applique 1x, le Codex non)."""
        wanted = {c for c in categories if c}
        best = None
        for value, cats in self.direct:
            if wanted.intersection(cats) and (best is None or value > best):
                best = value
        return best


@dataclass
class WeaponRow:
    block: str
    item: str
    group: str
    cells: Tuple[Optional[float], ...]
    tiers: Tuple[str, ...] = ()
    kind: str = "block"                    # 'block' (tourelle) ou 'item' (arme a main)


@dataclass
class DamageMatrix:
    columns: Tuple[str, ...] = ()
    thresholds: Tuple[Optional[Dict[str, float]], ...] = ()
    rows: List[WeaponRow] = field(default_factory=list)


@dataclass
class Opportunity:
    item: str
    seller: str
    buyer: str
    qty: Optional[float] = None
    cost_lo: float = 0.0                   # prix paye au vendeur, borne basse
    cost_hi: float = 0.0
    gain_lo: float = 0.0                   # prix paye par l'acheteur
    gain_hi: float = 0.0
    profit: Optional[float] = None         # optimiste = qty x (gain_hi - cost_lo)


def tier_of(mult: Optional[float], thresholds: Optional[Dict[str, float]]) -> str:
    """Palier d'affichage d'un multiplicateur (voir docstring du module)."""
    if mult is None:
        return "default"
    if mult == 0 or thresholds is None:
        return "none"
    if mult < thresholds["ineffective"]:
        return "ineffective"
    if mult <= thresholds["normal"]:
        return "normal"
    if mult <= thresholds["effective"]:
        return "effective"
    return "very_effective"


# ------------------------------------------------------------------- lecture

def _config_dirs(working_root, vanilla_root) -> List[Path]:
    """Vanille d'abord, scenario ensuite : l'ordre est la precedence."""
    dirs = []
    if vanilla_root:
        vdir = config_dir(vanilla_root)
        if vdir is not None:
            dirs.append(vdir)
    sdir = config_dir(working_root)
    if sdir is not None:
        dirs.append(sdir)
    return dirs


def _blocks(dirs: List[Path], base: str, kind: str) -> Iterable[EcfBlock]:
    """Blocs racine de genre `kind` ('Item', 'Block'...), tous fichiers
    `base*.ecf` confondus, dans l'ordre de precedence."""
    wanted = kind.lower()
    for cdir in dirs:
        for path in sorted(cdir.glob(f"{base}*.ecf")):
            try:
                doc = parse_ecf_file(path)
            except OSError:
                continue
            for node in doc.nodes:
                if isinstance(node, EcfBlock) \
                        and node.kind.lstrip("+-").strip().lower() == wanted:
                    yield node


def _fill(entry: CodexEntry, node: EcfBlock) -> None:
    """Applique une definition sur l'entree : scalaires ecrases (dernier
    gagne), proprietes ACCUMULEES (un patch `+Item` ne repete pas tout)."""
    raw_id = _clean(node.get("Id"))
    if raw_id.isdigit():
        entry.id = int(raw_id)
    price = _num(node.get_property("MarketPrice"))
    if price is not None:
        entry.price = price
    ref = _clean(node.get_property("Ref") or node.get_property("REF"))
    if ref:
        entry.ref = ref
    group = _clean(node.get("DamageMultiplier_Group")
                   or node.get_property("DamageMultiplier_Group"))
    if not group:
        for child in node.child_blocks():
            group = _clean(child.get("DamageMultiplier_Group"))
            if group:
                break
    if group:
        entry.damage_group = group
    for key, value in _props_of(node):
        if not _NOISE.match(key) and key not in ("Id", "Name"):
            entry.props[key] = value


def _read_entries(dirs: List[Path], kind: str) -> Dict[str, CodexEntry]:
    base = _FILES[kind]
    ecf_kind = {"item": "Item", "block": "Block", "token": "Token"}[kind]
    out: Dict[str, CodexEntry] = {}
    for node in _blocks(dirs, base, ecf_kind):
        name = _clean(node.get("Name"))
        if not name:
            continue
        entry = out.get(name)
        if entry is None:
            entry = out[name] = CodexEntry(kind=kind, name=name)
        entry.nodes.append(node)
        _fill(entry, node)
    return out


def _read_templates(dirs: List[Path]) -> Dict[str, CodexTemplate]:
    out: Dict[str, CodexTemplate] = {}
    for node in _blocks(dirs, _FILES["template"], "Template"):
        name = _clean(node.get("Name"))
        if not name:
            continue
        inputs: List[Tuple[str, float]] = []
        for child in node.child_blocks():
            if "Inputs" not in child.kind:
                continue
            for key, value in _props_of(child):
                qty = _num(value)
                inputs.append((key, qty if qty is not None else 0.0))
        out[name] = CodexTemplate(
            name=name,
            craft_time=_num(node.get_property("CraftTime")) or 0.0,
            output_count=max(1, int(_num(node.get_property("OutputCount")) or 1)),
            targets=_split_list(node.get_property("Target")),
            inputs=tuple(inputs),
        )
    return out


def _read_materials(dirs: List[Path]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for node in _blocks(dirs, _FILES["material"], "Material"):
        name = _clean(node.get("Name"))
        category = _clean(node.get_property("damage_category")).lower()
        if name and category:
            out[name.lower()] = category
    return out


def _read_damage_groups(dirs: List[Path]) -> Dict[str, DamageGroup]:
    groups: Dict[str, DamageGroup] = {}
    collections: List[Tuple[DamageGroup, Tuple[str, ...]]] = []
    for node in _blocks(dirs, _FILES["damage"], "DamageMultiplierGroup"):
        name = _clean(node.get("Name"))
        if not name:
            continue
        group = DamageGroup(name=name)
        for prop in _all_props(node):
            key = prop.pairs[0][0] if prop.pairs else ""
            match = _MULT.match(key or "")
            if not match:
                continue
            value = _num(prop.pairs[0][1])
            if value is None:
                continue
            cats = tuple(c.strip().lower()
                         for c in (prop.get("param1") or "").split("|") if c.strip())
            (group.blast if match.group(1) else group.direct).append((value, cats))
        groups[name] = group
        sub = _split_list(node.get_property("Collection"))
        if sub:
            collections.append((group, sub))
    # Groupes `Collection` : fusion des sous-groupes, une fois tous connus.
    for group, names in collections:
        for sub in names:
            parent = groups.get(sub)
            if parent is not None:
                group.direct.extend(parent.direct)
                group.blast.extend(parent.blast)
    return groups


def _read_traders(dirs: List[Path]) -> Dict[str, CodexTrader]:
    out: Dict[str, CodexTrader] = {}
    for node in _blocks(dirs, _FILES["trader"], "Trader"):
        name = _clean(node.get("Name"))
        if not name:
            continue
        trader = CodexTrader(
            name=name,
            selling_text=_clean(node.get_property("SellingText")),
            discount=_clean(node.get_property("Discount")),
        )
        indexed: List[Tuple[int, TradeItem]] = []
        for prop in _all_props(node):
            for key, value in prop.pairs:
                match = _ITEM_LINE.match(key or "")
                if not match:
                    continue
                try:
                    indexed.append((int(match.group(1)), TradeItem.parse(value)))
                except ValueError:
                    trader.raw_lines.append(_clean(value))
        indexed.sort(key=lambda pair: pair[0])
        trader.items = [item for _idx, item in indexed]
        out[name] = trader
    return out


# ------------------------------------------------------------------ donnees

class CodexData:
    """Toutes les donnees Codex d'un scenario + les calculs derives."""

    def __init__(self, items: Dict[str, CodexEntry], blocks: Dict[str, CodexEntry],
                 tokens: Dict[str, CodexEntry], templates: Dict[str, CodexTemplate],
                 traders: Dict[str, CodexTrader], materials: Dict[str, str],
                 damage_groups: Dict[str, DamageGroup], localization: LocalizationIndex,
                 language: str, working_root: str = ""):
        self.items = items
        self.blocks = blocks
        self.tokens = tokens
        self.templates = templates
        self.traders = list(traders.values())
        self.materials = materials
        self.damage_groups = damage_groups
        self.localization = localization
        self.language = language
        self.working_root = working_root
        self._matrix: Optional[DamageMatrix] = None
        self._token_by_id = {e.id: e for e in tokens.values() if e.id is not None}

    # ---------------------------------------------------------- noms/fiches
    def display_name(self, key: Optional[str]) -> str:
        """Traduction dans la langue courante, repli = cle technique. Les
        balises BBCode du jeu sont retirees : ces noms vont dans des cellules
        de tableau (une grille Qt n'interprete rien et afficherait `[c]`)."""
        return _BBCODE.sub("", self.localization.get(key, self.language) or (key or ""))

    def display_html(self, key: Optional[str]) -> str:
        """Version riche : le BBCode du jeu est converti (couleurs, gras)."""
        from core.block_info_card import description_html
        return description_html(self.localization.get(key, self.language) or (key or ""))

    def entry(self, name: str) -> Optional[CodexEntry]:
        return self.items.get(name) or self.blocks.get(name) or self.tokens.get(name)

    def entries(self, include_hidden: bool = False) -> List[CodexEntry]:
        out = [*self.items.values(), *self.blocks.values(), *self.tokens.values()]
        return [e for e in out if include_hidden or not e.hidden]

    # ------------------------------------------------------------- prix
    def _chain(self, name: str) -> List[str]:
        """Chaine Ref du plus specifique au parent, garde anti-cycle."""
        out: List[str] = []
        while name and name not in out and len(out) <= 12:
            out.append(name)
            entry = self.entry(name)
            name = entry.ref if entry else ""
        return out

    def market_price(self, name: str) -> Optional[float]:
        """MarketPrice declare, sinon herite par Ref (mecanique du jeu)."""
        for candidate in self._chain(name):
            entry = self.entry(candidate)
            if entry is not None and entry.price is not None:
                return entry.price
        return None

    def resolve_devname(self, devname: str) -> Optional[str]:
        """'Token:3' -> nom du jeton ; None si le jeton est inconnu (le Codex
        masque la ligne plutot que d'afficher un prix faux)."""
        match = _TOKEN_REF.match(devname or "")
        if not match:
            return devname
        token = self._token_by_id.get(int(match.group(1)))
        return token.name if token else None

    def estimate_range(self, spec: Optional[RangeSpec],
                       price: Optional[float] = None) -> Optional[Tuple[float, float]]:
        """Prix estime d'une ligne marchand : facteur x MarketPrice, ou bornes
        absolues telles quelles. None = indeterminable (facteur sans prix)."""
        if spec is None:
            return None
        if spec.factor:
            if price is None:
                return None
            return round(spec.lo_f * price), round(spec.hi_f * price)
        if spec.lo_f == 0 and spec.hi_f == 0:
            return None
        return spec.lo_f, spec.hi_f

    # ----------------------------------------------------------- recettes
    def template_for(self, name: str) -> Optional[CodexTemplate]:
        """Recette effective : RecipeName, sinon TemplateRoot, sinon une
        recette du meme nom, sinon heritage par Ref (mecanique officielle des
        groupes d'upgrade). Le nom peut designer une recette sans qu'aucun
        item/bloc ne porte ce nom : la chaine est alors vide."""
        for candidate in self._chain(name) or [name]:
            entry = self.entry(candidate)
            if entry is not None:
                for key in ("RecipeName", "TemplateRoot"):
                    ref = _clean(entry.props.get(key))
                    if ref in self.templates:
                        return self.templates[ref]
            if candidate in self.templates:
                return self.templates[candidate]
        return None

    def flatten_ingredients(self, name: str) -> Tuple[Dict[str, float], float]:
        """Recette aplatie aux materiaux de base + temps de craft cumule des
        sous-recettes. Les 4 minerais et les productions cycliques s'arretent
        d'eux-memes (NO_EXPAND / garde anti-cycle).

        Les quantites sont ramenees a UN exemplaire : une recette qui produit
        `OutputCount` pieces par craft ne consomme qu'un OutputCount-ieme de
        ses ingredients par piece (verifie sur RE2-FR : Shotgun -> 1,1
        minerai de fer, la version sans division annoncait 225, soit 125 fois
        le prix marche)."""
        if self.template_for(name) is None:
            return {}, 0.0
        totals: Dict[str, float] = {}
        craft = [0.0]

        def walk(item: str, mult: float, visited: frozenset) -> None:
            tmpl = self.template_for(item)
            if tmpl is None or item in visited or item in NO_EXPAND:
                totals[item] = totals.get(item, 0.0) + mult
                return
            per_craft = max(1, tmpl.output_count)
            craft[0] += tmpl.craft_time * mult / per_craft
            for ingredient, qty in tmpl.inputs:
                walk(ingredient, qty * mult / per_craft, visited | {item})

        walk(name, 1.0, frozenset())
        return totals, craft[0]

    def materials_cost(self, name: str) -> Tuple[Optional[float], bool]:
        """(cout des ingredients, incomplet) — incomplet = au moins un
        ingredient sans MarketPrice, donc un total sous-estime."""
        totals, _craft = self.flatten_ingredients(name)
        if not totals:
            return None, False
        total = 0.0
        partial = False
        for ingredient, qty in totals.items():
            price = self.market_price(ingredient)
            if price is None:
                partial = True
            else:
                total += price * qty
        return (total if total > 0 else None), partial

    # ---------------------------------------------------------- marchands
    def traders_for(self, name: str) -> List[Tuple[CodexTrader, TradeItem]]:
        out = []
        for trader in self.traders:
            for item in trader.items:
                if item.name == name and (trader.sells(item) or trader.buys(item)):
                    out.append((trader, item))
        return out

    def opportunities(self) -> List[Opportunity]:
        """Items vendus par un marchand ET rachetes par un autre, triee par
        profit total estime (quantite echangeable x gain unitaire)."""
        sell: Dict[str, List[Tuple[str, Tuple[float, float], Optional[Tuple[float, float]]]]] = {}
        buy: Dict[str, List[Tuple[str, Tuple[float, float], Optional[Tuple[float, float]]]]] = {}
        for trader in self.traders:
            for item in trader.items:
                name = self.resolve_devname(item.name)
                if not name:
                    continue
                price = self.market_price(item.name)
                if trader.sells(item):
                    rng = self.estimate_range(item.sell_price, price)
                    if rng:
                        sell.setdefault(name, []).append((trader.name, rng, _qty(item.sell_stock)))
                if trader.buys(item):
                    rng = self.estimate_range(item.buy_price, price)
                    if rng:
                        buy.setdefault(name, []).append((trader.name, rng, _qty(item.buy_max_stock)))

        out: List[Opportunity] = []
        for name, sellers in sell.items():
            buyers = buy.get(name)
            if not buyers:
                continue
            best = None
            for seller_name, (cost_lo, cost_hi), seller_qty in sellers:
                for buyer_name, (gain_lo, gain_hi), buyer_qty in buyers:
                    qty = min(seller_qty[1] if seller_qty else 1.0,
                              buyer_qty[1] if buyer_qty else 1.0)
                    profit = qty * (gain_hi - cost_lo)
                    if best is None or profit > best.profit:
                        best = Opportunity(item=name, seller=seller_name, buyer=buyer_name,
                                           qty=qty, cost_lo=cost_lo, cost_hi=cost_hi,
                                           gain_lo=gain_lo, gain_hi=gain_hi,
                                           profit=profit)
            if best is not None:
                out.append(best)
        out.sort(key=lambda opp: (opp.profit is None, -(opp.profit or 0)))
        return out

    # ------------------------------------------------------------- degats
    def damage_columns(self) -> Tuple[str, ...]:
        """Une colonne par categorie de degats DECLAREE par les materiaux du
        scenario (aucun manifeste a maintenir)."""
        return tuple(sorted({c for c in self.materials.values() if c}))

    def _block_damage_category(self, block: CodexEntry) -> str:
        return self.materials.get(block.material.lower(), "")

    def damage_group_for(self, item_name: str) -> Optional[DamageGroup]:
        """Groupe nomme (chaine Ref entiere d'abord), sinon multiplicateurs
        inline — ordre du Codex."""
        chain = self._chain(item_name)
        for name in chain:
            entry = self.entry(name)
            if entry is not None and entry.damage_group:
                group = self.damage_groups.get(entry.damage_group)
                if group is not None:
                    return group
        for name in chain:
            entry = self.entry(name)
            if entry is None:
                continue
            direct: List[Tuple[float, Tuple[str, ...]]] = []
            blast: List[Tuple[float, Tuple[str, ...]]] = []
            for node in entry.nodes:
                for prop in _all_props(node):
                    if not prop.pairs:
                        continue
                    match = _MULT.match(prop.pairs[0][0] or "")
                    if not match:
                        continue
                    value = _num(prop.pairs[0][1])
                    if value is None:
                        continue
                    cats = tuple(c.strip().lower()
                                 for c in (prop.get("param1") or "").split("|") if c.strip())
                    (blast if match.group(1) else direct).append((value, cats))
            if direct or blast:
                return DamageGroup(name="", direct=direct, blast=blast)
        return None

    def _ammo_items(self) -> set:
        """Noms d'items cites en AmmoType : ce sont des munitions. Elles
        portent des multiplicateurs de degats (ceux de l'arme qui les tire)
        et pollueraient la matrice."""
        out = set()
        for entry in self.items.values():
            for node in entry.nodes:
                for prop in _all_props(node):
                    for key, value in prop.pairs:
                        if key == "AmmoType":
                            out.add(_clean(value))
        return out

    def _weapon_groups(self) -> List[Tuple[str, str, DamageGroup, str]]:
        """(nom affiche, item d'arme, groupe de degats, genre) — une entree
        par arme. Deux sources : les BLOCS a WeaponItem (tourelles) et les
        ITEMS a multiplicateurs (armes a main), que le Codex d'origine omet
        — sans eux la matrice d'une partie entiere serait vide cote joueur.
        Les blocs d'atelier/template et les munitions sont ecartes."""
        out: List[Tuple[str, str, DamageGroup, str]] = []
        seen: set = set()
        covered: set = set()
        for block in self.blocks.values():
            if not block.weapon_item or block.hidden or block.name in seen:
                continue
            item = self.resolve_devname(block.weapon_item) or block.weapon_item
            covered.add(item)
            group = self.damage_group_for(item)
            if group is None:
                continue
            seen.add(block.name)
            out.append((block.name, item, group, "block"))
        ammo = self._ammo_items()
        for entry in self.items.values():
            if entry.hidden or entry.name in seen or entry.name in covered \
                    or entry.name in ammo:
                continue
            group = self.damage_group_for(entry.name)
            if group is None:
                continue
            out.append((entry.name, entry.name, group, "item"))
        return out

    def damage_matrix(self) -> DamageMatrix:
        """Matrice armes x categories. Les colonnes sans AUCUN multiplicateur
        explicite positif sont ecartees : elles seraient entierement vides
        (le scenario RE2 en declare 45, 26 ont des valeurs)."""
        weapons = self._weapon_groups()
        columns = tuple(
            cat for cat in self.damage_columns()
            if any((group.mult((cat,)) or 0) > 0 for _n, _i, group, _k in weapons))
        rows = [WeaponRow(block=name, item=item, group=group.name, kind=kind,
                          cells=tuple(group.mult((cat,)) for cat in columns))
                for name, item, group, kind in weapons]
        # Une arme sans AUCUN degat positif n'a rien a faire dans la matrice
        # (elle n'afficherait que des points et des tirets).
        rows = [row for row in rows
                if any(value is not None and value > 0 for value in row.cells)]
        rows.sort(key=lambda row: self.display_name(row.block).lower())

        thresholds: List[Optional[Dict[str, float]]] = []
        for idx in range(len(columns)):
            explicit = sorted(row.cells[idx] for row in rows
                              if row.cells[idx] is not None and row.cells[idx] > 0)
            thresholds.append({name: _percentile(explicit, pct)
                               for name, pct in TIER_PERCENTILES} if explicit else None)
        for row in rows:
            row.tiers = tuple(tier_of(value, thresholds[idx])
                              for idx, value in enumerate(row.cells))
        return DamageMatrix(columns=columns, thresholds=tuple(thresholds), rows=rows)

    def blocks_by_damage_category(self) -> Dict[str, List[CodexEntry]]:
        out: Dict[str, List[CodexEntry]] = {}
        for block in self.blocks.values():
            category = self._block_damage_category(block)
            if category:
                out.setdefault(category, []).append(block)
        for group in out.values():
            group.sort(key=lambda e: self.display_name(e.name).lower())
        return out

    def weapons_against(self, category: str) -> List[Tuple[str, float, str]]:
        """(bloc arme, multiplicateur, palier) contre une categorie de blocs,
        du plus efficace au moins efficace. Une arme SANS entree explicite
        vaut 1x au tri et s'affiche « defaut » (regle du Codex)."""
        values = [(name, group.mult((category,)))
                  for name, _item, group, _kind in self._weapon_groups()]
        explicit = sorted(value for _name, value in values
                          if value is not None and value > 0)
        thresholds = ({name: _percentile(explicit, pct) for name, pct in TIER_PERCENTILES}
                      if explicit else None)
        out = [(name, 1.0 if value is None else value, tier_of(value, thresholds))
               for name, value in values]
        out.sort(key=lambda entry: -entry[1])
        return out


def build_codex_data(working_root, vanilla_root: Optional[str] = None,
                     language: Optional[str] = None) -> CodexData:
    """Construit les donnees Codex (thread : aucun QWidget ici). Le scenario
    passe APRES la vanille, donc ses definitions gagnent a nom egal."""
    dirs = _config_dirs(working_root, vanilla_root)
    if not dirs:
        raise FileNotFoundError(f"aucun dossier Configuration sous {working_root}")
    if language is None:
        from core.i18n import get_language
        language = get_language()
    return CodexData(
        items=_read_entries(dirs, KIND_ITEM),
        blocks=_read_entries(dirs, KIND_BLOCK),
        tokens=_read_entries(dirs, KIND_TOKEN),
        templates=_read_templates(dirs),
        traders=_read_traders(dirs),
        materials=_read_materials(dirs),
        damage_groups=_read_damage_groups(dirs),
        localization=build_localization_index(Path(working_root)),
        language=language,
        working_root=str(working_root),
    )


# ------------------------------------------------------------- persistance
# Lieux et routes sont des donnees de TRAVAIL de l'utilisateur (jamais dans
# le scenario) : un JSON par scenario, cle = empreinte du chemin.

def store_path(working_root, name: str) -> Path:
    key = hashlib.sha1(str(Path(working_root).resolve()).encode("utf-8")).hexdigest()[:12]
    return Path(CONFIG_DIR) / "codex" / key / f"{name}.json"


def load_store(working_root, name: str) -> dict:
    path = store_path(working_root, name)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_store(working_root, name: str, data: dict) -> None:
    from core.fsutil import atomic_write_text
    path = store_path(working_root, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=1))


# --------------------------------------------------------------- routes
def route_net(route: dict, opportunities: List[Opportunity]) -> Tuple[float, float]:
    """(net conservateur, net optimiste) d'une route : somme des etapes dont
    l'item est une opportunite connue, a la quantite saisie par l'etape."""
    by_item = {opp.item: opp for opp in opportunities}
    low = high = 0.0
    for stop in route.get("stops", []):
        opp = by_item.get(stop.get("item", ""))
        if opp is None:
            continue
        qty = float(stop.get("qty") or 0)
        if qty <= 0:
            continue
        low += qty * (opp.gain_lo - opp.cost_hi)
        high += qty * (opp.gain_hi - opp.cost_lo)
    return low, high
