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

"""EQUILIBRAGE PAR CORRELATIONS (chantier 17/10/2026) : chaque propriete de
bloc/item (Mass, HitPoints, Damage, ShieldCapacity) est comparee a la
MEDIANE DE SON GROUPE DE REFERENCE, pas a une valeur globale.

Pourquoi la mediane par groupe et pas une correlation stricte : les
mesures RE2 (17/10) montrent que la masse est un parametre de gameplay
PAR MATERIAU (plastique voulu leger, ArtMass = lest volontaire a x2966,
hologrammes a x0.01) — une cible x1.0 casserait le design. La mediane du
groupe preserve la densite choisie de chaque materiau et ne propose que
les incoherences INTERNES au groupe.

Groupes de reference par propriete :
  Mass        -> ratio masse / masse-des-ingredients (recette recursive),
                 groupe = TEMPLATE EFFECTIF (variantes d'une famille) ;
  HitPoints   -> mediane HP par template effectif (blocs) ;
  Damage      -> mediane par famille x tier du nom (WeaponCVPlasma T2...) ;
  ShieldCapacity -> mediane par classe x tier du nom (SV/CV/BA ont des
                 boucliers par design differents).

Statuts : ok (dans les bornes) / outlier (proposition -> reference du
groupe) / whitelist (design volontaire — ArtMass, effets, roches : jamais
proposes) / zero (valeur <= 0 : jamais proposes) / sans_groupe (Material
absent, tier illisible : ancrage) / sans_valeur (propriete absente :
affiche, jamais ecrit — pas d'ajout de ligne).

Application : set_property sur la definition finale, backup central,
ecriture atomique ; re-scanner apres (les medianes bougent).
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from core.fsutil import atomic_write_text
from core.market_balance import (MarketIndex, _num, _ref_of,
                                 load_index, resolve_template)

LO, HI = 0.7, 1.4              # bornes autour de la reference du groupe
MAX_RATIO = 10.0               # au-dela de x10 AU-DESSUS de la cible, ce
                               # n'est plus une derive de calibrage mais un
                               # design different (propulseur geant vs LCD)
                               # : pas de proposition. Vers le BAS en
                               # revanche, un bloc bien trop leger est
                               # toujours une vraie incoherence (ShutterDoor
                               # mal saisie) : signale sans cap.
MIN_GROUP = 3                  # mediane d'un groupe de 2 = milieu des deux :
                               # elle tirerait des valeurs LEGITIMES vers
                               # l'outlier — pas de proposition en dessous


OK, OUTLIER, WHITELIST, ZERO, SANS_GROUPE, SANS_VALEUR = (
    "ok", "outlier", "whitelist", "zero", "sans_groupe", "sans_valeur")

_TIER_RE = re.compile(r"^(.*?T)(\d+)")
_SIZE_RE = re.compile(r"(\d+)\s*x\s*(\d+)(?:\s*x\s*(\d+))?", re.I)


def _size_factor_from_name(name: str) -> Optional[float]:
    """Repli : produit des dimensions lues dans le nom (ShutterDoor3x3 -> 9).
    None si le nom ne porte aucune dimension (la distinction importe : un
    facteur inconnu doit pouvoir etre resolu par les jumeaux du groupe)."""
    m = _SIZE_RE.search(name)
    if not m:
        return None
    p = 1.0
    for g in m.groups():
        if g:
            p *= int(g)
    return p if p > 0 else None


def _size_factor_opt(idx: MarketIndex, name: str) -> Optional[float]:
    """Produit SizeInBlocks du bloc, None si la propriete est ABSENTE
    (a ne pas confondre avec '1,1,1' = volume 1 legitime)."""
    od = idx.objs.get(name)
    if od is None:
        return None
    raw = od.final.get_property("SizeInBlocks")
    if not raw:
        return None
    p, found = 1.0, False
    for part in str(raw).strip().strip('"').split(","):
        part = part.strip()
        if part.replace(".", "").isdigit():
            p *= float(part)
            found = True
    return p if found and p > 0 else None


def _size_factor(idx: MarketIndex, name: str) -> float:
    """Facteur de taille du bloc : SizeInBlocks (source officielle), repli
    dimensions du nom, sinon 1. Vecu 17/10 : ShutterDoor 1x1/3x3/4x4/5x5
    ont des RECETTES IDENTIQUES — 'ratio median x mon cout' proposait le
    meme 810 aux quatre tailles. La reference devient une DENSITE par
    unite de taille : normalise par le facteur, mediane, puis
    denormalise pour la cible."""
    f = _size_factor_opt(idx, name)
    if f is not None:
        return f
    return _size_factor_from_name(name) or 1.0

# design volontaire : lest (ArtMass), effets/hologrammes, roches decor,
# et blocs a MASSE FONCTIONNELLE par design (vecu 17/10 avec SizeInBlocks :
# canons CV 80 t, MissionContainer alourdi pour les quetes, tourelles,
# decor articule) — leur masse n'a pas a suivre la densite de famille.
WHITELIST_RE = re.compile(
    r"^(ArtMass|Eden_Effects|ReforgedRock|Weapon|Turret|Mission|Deco|Art"
    r"|Retract|Thruster|LegacyPOI|DroneBay|Eden_Turret|Eden_Drone"
    r"|Eden_SalvageTurret)", re.I)


# ------------------------------------------------------------ references

def _effective(idx: MarketIndex, name: str, prop: str,
               _depth: int = 0) -> Optional[float]:
    """Valeur effective d'une propriete : dernier declare, sinon REF."""
    od = idx.objs.get(name)
    if od is None or _depth > 12:
        return None
    v = _num(od.final.get_property(prop))
    if v is not None:
        return v
    ref = _ref_of(od.final)
    if ref:
        return _effective(idx, ref, prop, _depth + 1)
    return None


def _recipe_mass(idx: MarketIndex, name: str,
                 seen: frozenset) -> Tuple[Optional[float], str]:
    """Masse d'ingredients pour 1 unite produite (BaseItem = sa propre
    masse). Meme doctrine que le cout du prix marche : ingredient sans
    masse -> echec (jamais de total partiel)."""
    tname = resolve_template(idx, name)
    if tname is None:
        return None, "sans recette"
    t = idx.templates[tname]
    own = _effective(idx, name, "Mass")
    if t.base_item and own is not None:
        return own, ""
    if name in seen:
        return None, "cycle"
    if not t.inputs or all(q == 0 for _, q in t.inputs):
        return None, "recette gratuite"
    total = 0.0
    for ing, qty in t.inputs:
        if qty == 0:
            continue
        im = _effective(idx, ing, "Mass")
        if im is None:
            im, why = _recipe_mass(idx, ing, seen | {name})
            if im is None:
                return None, f"ingredient {ing}: {why or 'masse inconnue'}"
        total += qty * im
    return total / t.output_count, ""


# La correlation masse/HP n'a de sens que pour la COQUE STRUCTURELLE —
# c'est elle qui affecte la physique du vaisseau (SI, poussée, masse
# totale). Mesures 17/10 : les blocs SANS Material (portes, canapes NPC,
# posters) et les devices (Device, Thruster...) portent des masses
# ARBITRAIRES par design (SofaNPC 320->1280->5120 : chaque application
# promenait la valeur) — hors perimetre, definitivement.
HULL_MATERIALS = {
    "steellarge", "steelsmall", "titaniumlarge", "titaniumsmall",
    "combatlarge", "combatsmall", "plasticlarge", "plasticsmall",
    "concrete", "concretelarge", "concretesmall", "wood", "woodlarge",
    "woodsmall", "xenosteel", "hardenedlarge", "hardenedsmall",
    "alienlarge", "aliensmall", "foundation",
}


def _group_template(idx: MarketIndex, name: str) -> Optional[str]:
    """Groupe = TEMPLATE EFFECTIF (variantes d'une meme famille : membres
    de HullLargeBlocks, rampes...), RESERVE aux blocs de coque (Material
    dans HULL_MATERIALS). Homogene par construction ; les devices et decos
    solitaires tombent sous MIN_GROUP, les autres sont hors perimetre."""
    od = idx.objs.get(name)
    if od is None or od.kind != "block":
        return None
    mat = od.final.get_property("Material")
    if not mat or mat.strip().strip('"').lower() not in HULL_MATERIALS:
        return None
    return resolve_template(idx, name)


def _group_item(idx: MarketIndex, name: str) -> Optional[str]:
    return "__item__"


def _group_thruster(idx: MarketIndex, name: str) -> Optional[str]:
    """Groupe = FAMILLE de propulseur x tier (ThrusterMSDrive T2/T3 sont
    des progressions distinctes ; les tailles 2x2/3x3 et suffixes
    Armored/Slant sont des variantes normalisees par le volume)."""
    n = re.sub(r"^Eden_", "", name)
    n = _SIZE_RE.sub("", n)
    m = re.search(r"T(\d+)", n)
    tier = f"-t{m.group(1)}" if m else ""
    n = re.sub(r"T\d+", "", n)
    n = re.sub(r"(Armored|Slant|Sloped|Blocks|Retract)", "", n, flags=re.I)
    fam = re.sub(r"[^A-Za-z]", "", n).lower()
    return f"{fam}{tier}" if fam else None


def _group_family_tier(idx: MarketIndex, name: str) -> Optional[str]:
    # T\d + suffixe (V2, Odd...) : le groupe = famille x TIER, le suffixe
    # de variante ne cree pas un groupe a part (RE2 a des T2V2 partout)
    m = _TIER_RE.match(name)
    return f"{m.group(1)}{m.group(2)}".lower() if m else None


_CLASS_RE = re.compile(r"(SV|HV|CV|BA|MS)T(\d+)", re.I)


def _group_tier(idx: MarketIndex, name: str) -> Optional[str]:
    """Groupe = classe (SV/HV/CV/BA/MS) x tier ; sans classe : tier seul.
    Vecu 17/10 : SVT2 (8k) et CVT2 (24k) dans un meme 't2' proposaient
    17k aux deux — le CV est plus fort par design."""
    m = _CLASS_RE.search(name)
    if m:
        return f"{m.group(1).lower()}-t{m.group(2)}"
    m = _TIER_RE.match(name)
    return f"t{m.group(2)}" if m else None


# ------------------------------------------------------------ specs

@dataclass(frozen=True)
class CorrSpec:
    key: str                     # cle i18n + identite
    prop: str                    # propriete ECF cible
    kinds: Tuple[str, ...]       # 'block' / 'item'
    ref: str                     # 'recipe_ratio' | 'group_median'
    group_fn: Callable[[MarketIndex, str], Optional[str]]
    fmt_int: bool = True         # False = une decimale (Mass des decos)
    size_norm: bool = False      # normaliser par la taille du nom
    heavy_cap: bool = False      # masse : device volontairement lourd ->
                                 # pas de proposition au-dela de x10 ; les
                                 # stats de PERFORMANCE (HP, bouclier...)
                                 # n'ont pas ce cap (x45 vs son tier = typo)
    whitelist: Optional[re.Pattern] = None   # None = whitelist globale


SPECS = {
    "mass": CorrSpec("mass", "Mass", ("block",), "recipe_ratio",
                     _group_template, fmt_int=False, size_norm=True,
                     heavy_cap=True),
    "hitpoints": CorrSpec("hitpoints", "HitPoints", ("block",),
                          "group_median", _group_template, size_norm=True),
    "damage": CorrSpec("damage", "Damage", ("block", "item"),
                       "group_median", _group_family_tier),
    "shield": CorrSpec("shield", "ShieldCapacity", ("block",),
                       "group_median", _group_tier),
    "thrusterforce": CorrSpec(
        "thrusterforce", "ThrusterForce", ("block",), "group_median",
        _group_thruster, size_norm=True,
        whitelist=re.compile(r"^(ArtMass|Eden_Effects|ReforgedRock|LegacyPOI"
                             r"|Deco)", re.I)),
}


# ------------------------------------------------------------ rapport

@dataclass
class CorrEntry:
    name: str
    kind: str
    group: Optional[str]
    status: str
    value: Optional[float]
    reference: Optional[float]      # reference du groupe (median x cost)
    target: Optional[float]
    detail: str = ""


@dataclass
class CorrReport:
    spec_key: str
    entries: List[CorrEntry] = field(default_factory=list)
    counts: Dict[str, int] = field(default_factory=dict)
    groups: Dict[str, float] = field(default_factory=dict)   # medianes
    fmt_int: bool = True


def analyze_correlations(scenario_root, spec_key: str,
                         pinned_medians: Optional[Dict[str, float]] = None
                         ) -> Tuple[MarketIndex, CorrReport]:
    """Analyse complete d'une propriete : (index, rapport). Les documents
    ECF vivants restent dans idx (od.final_doc : MEME parse que od.final —
    modifier le noeud puis rendre un autre doc perdait l'ecriture, vecu
    aux tests 17/10).

    pinned_medians : medianes d'une analyse precedente. Sans elles, chaque
    re-scan recalcule les medianes sur les valeurs ACTUELLES — apres une
    application partielle, la mediane bouge et cree de NOUVELLES
    propositions sur les membres non appliques (ratchet vecu 17/10 :
    16 lignes apparues apres application). Epingler = les membres corriges
    atterrissent exactement sur la cible, zero proposal fantome."""
    spec = SPECS[spec_key]
    wl = spec.whitelist or WHITELIST_RE
    idx, _ = load_index(scenario_root)
    report = CorrReport(spec_key=spec_key)

    # valeur de reference par objet : ratio a la recette ou valeur brute
    # Phase A : candidats (groupe, nom, valeur, facteur ou None) — facteur
    # None = ni SizeInBlocks ni dimension dans le nom
    # Phase B : facteur None -> adopter celui d'un PAIR du meme groupe a la
    # MEME valeur (jumeaux physiques Sloped/Armored/Blocks sans
    # SizeInBlocks, vecu 17/10 : ThrusterMSDriveT3Sloped vol=1 vs base
    # vol=54 scindait la mediane en deux) ; sinon 1.0
    candidates: List[Tuple[str, str, float, Optional[float]]] = []
    for name, od in idx.objs.items():
        if od.kind not in spec.kinds:
            continue
        if wl.match(name):
            continue
        value = _effective(idx, name, spec.prop)
        if value is None or value <= 0:
            continue          # <= 0 = degenere (status zero) : hors medianes
        g = spec.group_fn(idx, name)
        if g is None:
            continue
        if spec.size_norm:
            # None = taille inconnue (ni SizeInBlocks ni dimensions du nom)
            f = _size_factor_opt(idx, name)
            if f is None:
                f = _size_factor_from_name(name)
            candidates.append((g, name, value, f))
        else:
            candidates.append((g, name, value, 1.0))
    known: Dict[Tuple[str, float], float] = {}
    for g, _n, v, f in candidates:
        if f is not None:
            known[(g, v)] = f
    factors: Dict[str, float] = {}     # facteurs RESOLUS (jumeaux inclus)
    ref_items: List[Tuple[str, str, float]] = []
    for g, name, value, f in candidates:
        if f is None:
            f = known.get((g, value), 1.0)
        factors[name] = f
        if spec.ref == "recipe_ratio":
            cost, _why = _recipe_mass(idx, name, frozenset())
            if cost is None or cost <= 0:
                continue
            ref_items.append((g, name, value / (cost * f)))
        else:
            ref_items.append((g, name, value / f))

    # mediane par groupe
    by_group: Dict[str, List[float]] = {}
    for g, _n, r in ref_items:
        by_group.setdefault(g, []).append(r)
    medians = {g: statistics.median(v) for g, v in by_group.items()
               if len(v) >= MIN_GROUP}
    if pinned_medians:
        medians.update({k: v for k, v in pinned_medians.items()
                        if k in by_group})

    # sous-designs homogenes : >= MIN_GROUP membres du groupe avec le MEME
    # ratio normalise (vecu 17/10 : TribalBarrow/Oven/Boat/Hearth tous a
    # 400) — l'auteur a CHOISI cette densite pour la sous-famille ; la
    # mediane du groupe, tiree par d'autres membres, ne doit pas les mettre
    # tous a l'amende.
    sub_design: set = set()
    by_gn: Dict[str, List[Tuple[str, float]]] = {}
    for g, n, r in ref_items:
        by_gn.setdefault(g, []).append((n, r))
    for g, pairs in by_gn.items():
        if g not in medians:
            continue
        by_ratio: Dict[float, List[str]] = {}
        for n, r in pairs:
            by_ratio.setdefault(round(r, 4), []).append(n)
        for ratio, names in by_ratio.items():
            if len(names) >= MIN_GROUP and ratio != round(medians[g], 4):
                sub_design.update(names)
    report.groups = medians

    # parcours de tous les objets -> entrees
    for name, od in idx.objs.items():
        if od.kind not in spec.kinds:
            continue
        value = _effective(idx, name, spec.prop)
        status = OK
        group = spec.group_fn(idx, name)
        target = None
        reference = medians.get(group) if group else None
        detail = ""
        if wl.match(name):
            status = WHITELIST
            detail = "design volontaire (lest/effets/decor)"
        elif value is None:
            status = SANS_VALEUR
            detail = "propriete absente (jamais ecrite)"
        elif value <= 0:
            status = ZERO
            detail = "valeur <= 0 (jamais proposee)"
        elif group is None or reference is None:
            status = SANS_GROUPE
            detail = "pas de groupe de reference (sans recette/materiau)"
        elif name in sub_design:
            status = OK
            detail = "sous-design homogene (>=3 valeurs identiques)"
        else:
            factor = factors.get(name, 1.0) if spec.size_norm else 1.0
            if spec.ref == "recipe_ratio":
                cost, why = _recipe_mass(idx, name, frozenset())
                if cost is None or cost <= 0:
                    status = SANS_GROUPE
                    detail = why or "reference non calculable"
                else:
                    reference = medians[group]
                    target = reference * cost * factor
                    lo, hi = LO * reference, HI * reference
                    if not lo <= value / (cost * factor) <= hi:
                        if (spec.heavy_cap and target > 0
                                and value / target > MAX_RATIO):
                            status = SANS_GROUPE
                            target = None
                            detail = ("plus de x10 la reference : "
                                      "probablement un design volontaire "
                                      "(device leste), pas une derive")
                        else:
                            status = OUTLIER
            else:
                target = reference * factor
                lo, hi = LO * reference, HI * reference
                if not lo <= value / factor <= hi:
                    if (spec.heavy_cap and target > 0
                            and value / target > MAX_RATIO):
                        status = SANS_GROUPE
                        target = None
                        detail = ("plus de x10 la reference : probablement "
                                  "un design volontaire (device leste), "
                                  "pas une derive")
                    else:
                        status = OUTLIER
        if target is not None and spec.fmt_int:
            target = round(target)
        else:
            target = round(target, 1) if target is not None else None
        report.entries.append(CorrEntry(
            name=name, kind=od.kind, group=group, status=status,
            value=value, reference=reference, target=target, detail=detail))
    report.counts = {}
    for e in report.entries:
        report.counts[e.status] = report.counts.get(e.status, 0) + 1

    report.fmt_int = spec.fmt_int
    return idx, report


# ------------------------------------------------------------ application

@dataclass
class CorrChange:
    path: Path
    doc: object
    node: object
    name: str
    prop: str
    old: Optional[float]
    new: float


def _render_num(x: float, fmt_int: bool) -> str:
    if fmt_int:
        return str(int(round(x)))
    s = f"{x:.1f}".rstrip("0").rstrip(".")
    return s or "0"


def make_changes(idx: MarketIndex, report: CorrReport,
                 names: set) -> List[CorrChange]:
    """Changes pour les entrees outliers choisies dont la cible differe.
    Ecriture TOUJOURS sur la definition finale."""
    spec = SPECS[report.spec_key]
    by_name = {e.name: e for e in report.entries if e.status == OUTLIER}
    out: List[CorrChange] = []
    for name in names:
        e = by_name.get(name)
        od = idx.objs.get(name)
        if e is None or od is None or e.target is None:
            continue
        if e.value is not None and abs(e.value - e.target) < 1e-9:
            continue
        if od.final_doc is None:
            continue
        out.append(CorrChange(path=od.final_path, doc=od.final_doc,
                              node=od.final, name=name, prop=spec.prop,
                              old=e.value, new=e.target))
    return out


def _render_for(report: CorrReport, x: float) -> str:
    return _render_num(x, report.fmt_int)


def apply_changes(changes: List[CorrChange], fmt_int: bool = True) -> Dict[
        Path, int]:
    """Ecrit les changes (set_property, backup central, ecriture atomique).
    Une propriete ABSENTE du bloc (valeur effective HERITEE d'un Ref, vecu
    17/10 : 5 ThrusterForce + 2 HitPoints materialisees nues -> 'Error
    converting property ... Type: System.String' en jeu, propulseurs sans
    poussee) est creee AVEC son attribut 'type:' -- une ligne numerique sans
    type est lue en string par le jeu."""
    from core.ecf.model import add_property_line
    from core.fsutil import central_backup  # local : monkeypatch conftest
    by_file: Dict[Path, List[CorrChange]] = {}
    for ch in changes:
        by_file.setdefault(ch.path, []).append(ch)
    done: Dict[Path, int] = {}
    for path, items in by_file.items():
        applied = 0
        for ch in items:
            value_text = _render_num(ch.new, fmt_int)
            if not ch.node.set_property(ch.prop, value_text):
                add_property_line(ch.node, [(ch.prop, value_text),
                                            ("type", "int" if fmt_int else "float")])
            applied += 1
        central_backup(path, "correlation")
        atomic_write_text(path, items[0].doc.render())
        done[path] = applied
    return done
