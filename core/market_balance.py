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

"""Moteur d'EQUILIBRAGE DES PRIX MARCHE (chantier 16/10/2026) : met chaque
MarketPrice en correlation avec le cout de fabrication de l'objet.

Sources : BlocksConfig*.ecf + ItemsConfig*.ecf + Templates*.ecf du scenario
(derniere definition gagne ; la vanille sert UNIQUEMENT de reference pour
les ratios de famille, jamais ecrite).

Resolution en cascade :
  1. template par Name direct                       -> statut 'fabriquable'
  2. TemplateRoot propre ou herite par chaine REF    -> statut 'groupe'
     (ATTENTION faux positifs connus : TurretZiraxMS* -> BrokenTurretDome ;
      c'est pourquoi aucune proposition n'est precochee dans l'UI)
  3. cousin de tier (T(k) <- T(k-1) RE2 vendable)    -> statut 'cousin'
     (ratio vanille si la famille existe, sinon x2 par tier)
  4. bloc de coque : prix/masse du meme Material     -> statut 'materiau'
  5. sinon                                            -> 'ancrage' (prix
     manuel, aucune proposition) ; sans MarketPrice  -> 'non_vendable'

Formule cible : prix = cout x marge x (1 + fab_pct/100) — la fabrication
ajoute un pourcentage du prix des matieres premieres (decision utilisateur
28/10 : remplace l'ancien facteur temps +x %/30 s, peu pertinent quand la
majorite des crafts durent moins de 30 s). PAS de renormalisation
(decision utilisateur 16/10). Prix ENTIERS >= 1 (regle projet economie).

Cout recursif : Somme(qte x prix_marche(ingredient)) / OutputCount ; un
BaseItem avec prix est une feuille (valorise au marche, on ne descend pas).
Recette gratuite VOLONTAIRE (tous les inputs a 0, ex AluminiumOre) ou
ingredient sans recette : valorises a LEUR prix marche (le marche fixe
l'ancrage ; la recette gratuite est une subvention de l'auteur) ; sans
prix non plus => echec. Une ligne d'input isolee a 0 = ingredient gratuit,
les autres lignes se calculent normalement. Les cibles supposent TOUTES
appliquees en meme temps : une seule passe, re-scanner apres application
pour converger."""
from __future__ import annotations

import re

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.ecf.model import (EcfBlock, EcfDocument, EcfProperty,
                            add_property_line, normalized_kind)
from core.ecf.parser import parse_ecf_file
from core.fsutil import atomic_write_text, central_backup

# Valeurs par defaut validees avec l'utilisateur (16/10/2026, ajustees 28/10)
DEFAULT_MARGIN = 1.0        # philosophie RE2 : prix = cout
DEFAULT_FAB_PCT = 0.0       # % du cout des matieres ajoute (fabrication)

FABRIQUABLE, GROUPE, COUSIN, MATERIAU, FAMILLE, ANCRAGE, NON_VENDABLE = (
    "fabriquable", "groupe", "cousin", "materiau", "famille", "ancrage",
    "non_vendable")
STATUSES = (FABRIQUABLE, GROUPE, COUSIN, MATERIAU, FAMILLE, ANCRAGE,
            NON_VENDABLE)

_TIER_RE = re.compile(r"^(.*?T)(\d+)$")


@dataclass
class TemplateDef:
    """Une recette : inputs [(nom, qte)], OutputCount, BaseItem, CraftTime."""
    name: str
    inputs: List[Tuple[str, float]]
    output_count: int
    base_item: bool
    craft_time: float


@dataclass
class ObjDef:
    """Toutes les definitions ECF d'un meme nom de bloc/item."""
    kind: str                          # 'block' | 'item'
    nodes: List[EcfBlock] = field(default_factory=list)
    final_path: Optional[Path] = None  # fichier de la definition finale
    final_doc: Optional[EcfDocument] = None
    price: Optional[int] = None        # dernier MarketPrice DECLARE

    @property
    def final(self) -> EcfBlock:
        return self.nodes[-1]


@dataclass
class MarketIndex:
    objs: Dict[str, ObjDef]
    templates: Dict[str, TemplateDef]


@dataclass
class MarketEntry:
    name: str
    kind: str
    status: str
    price: Optional[int]        # effectif (propre ou herite REF)
    cost: Optional[float]       # cout de fabrication recursif
    target: Optional[int]       # prix cible (entier) si calculable
    template: Optional[str]     # template effectif (direct ou TemplateRoot)
    detail: str = ""            # pourquoi ce statut / absence de cible


@dataclass
class MarketReport:
    entries: List[MarketEntry] = field(default_factory=list)
    counts: Dict[str, int] = field(default_factory=dict)


@dataclass
class PriceChange:
    path: Path
    doc: EcfDocument
    node: EcfBlock
    name: str
    old: Optional[int]
    new: int


# ----------------------------------------------------------- indexation

def config_dir(root) -> Optional[Path]:
    """Dossier de configuration d'un scenario/jeu (les deux layouts connus)."""
    root = Path(root)
    for sub in ("Content/Configuration", "Configuration"):
        p = root / sub
        if p.is_dir():
            return p
    return None


def _num(raw) -> Optional[float]:
    if raw is None:
        return None
    v = str(raw).strip().strip('"').split(",")[0].strip()
    try:
        return float(v)
    except ValueError:
        return None


def _read_objs(path: Path, doc: EcfDocument, kind: str,
               objs: Dict[str, ObjDef]) -> None:
    for node in doc.nodes:
        if not isinstance(node, EcfBlock):
            continue
        if normalized_kind(node.kind) != kind:
            continue
        name = (node.get("Name") or "").strip().strip('"')
        if not name:
            continue
        od = objs.setdefault(name, ObjDef(kind=kind.lower()))
        od.nodes.append(node)
        od.final_path, od.final_doc = path, doc
        p = _num(node.get_property("MarketPrice"))
        if p is not None:
            od.price = int(round(p))


def _read_templates(doc: EcfDocument, out: Dict[str, TemplateDef]) -> None:
    for node in doc.nodes:
        if not isinstance(node, EcfBlock) or "Template" not in node.kind:
            continue
        name = (node.get("Name") or "").strip().strip('"')
        if not name:
            continue
        inputs: List[Tuple[str, float]] = []
        for child in node.child_blocks():
            if "Inputs" not in child.kind:
                continue
            for prop in child.children:
                if not isinstance(prop, EcfProperty):
                    continue
                for k, v in prop.pairs:
                    if k is not None:
                        q = _num(v)
                        inputs.append((k, float(q) if q is not None else 0.0))
        out[name] = TemplateDef(
            name=name,
            inputs=inputs,
            output_count=max(1, int(_num(node.get_property("OutputCount")) or 1)),
            base_item=(node.get_property("BaseItem") or "").strip().lower() == "true",
            craft_time=_num(node.get_property("CraftTime")) or 0.0,
        )


def load_index(root, vanilla_root: str = ""
               ) -> Tuple[MarketIndex, Optional[MarketIndex]]:
    """Parse le scenario (+ la vanille en reference lecture seule).
    Retourne (index_scenario, index_vanille|None)."""
    cdir = config_dir(root)
    if cdir is None:
        raise FileNotFoundError(f"no Configuration dir under {root}")
    objs: Dict[str, ObjDef] = {}
    templates: Dict[str, TemplateDef] = {}
    for base, kind in (("BlocksConfig", "Block"), ("ItemsConfig", "Item")):
        for path in sorted(cdir.glob(f"{base}*.ecf")):
            doc = parse_ecf_file(path)
            _read_objs(path, doc, kind, objs)
    for path in sorted(cdir.glob("Templates*.ecf")):
        _read_templates(parse_ecf_file(path), templates)
    van = None
    vdir = config_dir(vanilla_root) if vanilla_root else None
    if vdir is not None:
        vobjs: Dict[str, ObjDef] = {}
        vtemplates: Dict[str, TemplateDef] = {}
        for base, kind in (("BlocksConfig", "Block"), ("ItemsConfig", "Item")):
            for path in sorted(vdir.glob(f"{base}*.ecf")):
                _read_objs(path, parse_ecf_file(path), kind, vobjs)
        for path in sorted(vdir.glob("Templates*.ecf")):
            _read_templates(parse_ecf_file(path), vtemplates)
        van = MarketIndex(objs=vobjs, templates=vtemplates)
    return MarketIndex(objs=objs, templates=templates), van


# ------------------------------------------------- resolutions effectives

def _ref_of(node: EcfBlock) -> Optional[str]:
    # get_property couvre la ligne d'ouverture ET les lignes enfants
    ref = node.get_property("Ref") or node.get_property("REF")
    return ref.strip().strip('"') if ref else None


def resolve_price(idx: MarketIndex, name: str, _depth: int = 0) -> Optional[int]:
    """Prix effectif : dernier MarketPrice declare, sinon herite du REF."""
    od = idx.objs.get(name)
    if od is None or _depth > 12:
        return od.price if od else None
    if od.price is not None:
        return od.price
    ref = _ref_of(od.final)
    if ref:
        return resolve_price(idx, ref, _depth + 1)
    return None


def resolve_template(idx: MarketIndex, name: str,
                     _depth: int = 0) -> Optional[str]:
    """Template effectif : Name direct, sinon TemplateRoot propre ou herite
    par chaine REF (mecanique officielle des groupes d'upgrade)."""
    if name in idx.templates:
        return name
    od = idx.objs.get(name)
    if od is None or _depth > 12:
        return None
    tr = od.final.get_property("TemplateRoot")
    if tr:
        tr = tr.strip().strip('"')
        if tr in idx.templates:
            return tr
    ref = _ref_of(od.final)
    if ref:
        return resolve_template(idx, ref, _depth + 1)
    return None


def _unit_cost(idx: MarketIndex, name: str, seen: frozenset
               ) -> Tuple[Optional[float], str]:
    """(cout d'1 unite, raison d'echec). Feuilles = prix marche. Un
    ingredient inexploitable mais VENDU vaut son prix marche (ancrage) ;
    sans prix non plus => echec complet de la recette."""
    tname = resolve_template(idx, name)
    price = resolve_price(idx, name)
    if tname is None:
        if price is None:
            return None, "pas de recette ni de prix"
        return float(price), ""
    t = idx.templates[tname]
    if t.base_item and price is not None:
        return float(price), ""
    if name in seen:
        return None, "cycle de recettes"
    if not t.inputs or all(q == 0 for _, q in t.inputs):
        if price is None:
            return None, ("recette sans ingredients" if not t.inputs
                          else "recette gratuite (inputs a 0)")
        return float(price), "valorise au prix marche (recette gratuite)"
    total = 0.0
    for ing, qty in t.inputs:
        if qty == 0:
            continue                # ligne isolee a 0 = ingredient gratuit
        c, why = _unit_cost(idx, ing, seen | {name})
        if c is None:
            p = resolve_price(idx, ing)
            if p is None:
                return None, f"ingredient {ing}: {why or 'non valorisable'}"
            c = float(p)
        total += qty * c
    return total / t.output_count, ""


def _apply_formula(cost: float, margin: float, fab_pct: float) -> int:
    return max(1, round(cost * margin * (1.0 + fab_pct / 100.0)))


def _material_price_per_mass(entries: List[MarketEntry], idx: MarketIndex
                             ) -> Dict[str, float]:
    """Prix/masse MEDIAN des blocs avec un cout fiable (fabriquables ou
    template de groupe), par Material — sert le repli des blocs de coque."""
    by_mat: Dict[str, List[float]] = {}
    for e in entries:
        if (e.status not in (FABRIQUABLE, GROUPE) or e.price is None
                or e.price <= 0):
            continue
        od = idx.objs.get(e.name)
        if od is None:
            continue
        mat = (od.final.get_property("Material") or "").strip().strip('"')
        mass = _num(od.final.get_property("Mass"))
        if mat and mass and mass > 0:
            by_mat.setdefault(mat, []).append(e.price / mass)
    return {mat: sorted(vals)[len(vals) // 2] for mat, vals in by_mat.items()}


def _cousin_target(idx: MarketIndex, van: Optional[MarketIndex], name: str
                   ) -> Optional[int]:
    """T(k) herite le prix de T(k-1) RE2 vendable, avec le ratio de la
    famille VANILLE si elle existe (sinon x2 par tier)."""
    m = _TIER_RE.match(name)
    if not m:
        return None
    base, tier = m.group(1), int(m.group(2))
    if tier < 2:
        return None
    prev = f"{base}{tier - 1}"
    prev_price = resolve_price(idx, prev)
    if prev_price is None:
        return None
    ratio = 2.0
    if van is not None:
        pv, vv = resolve_price(van, prev), resolve_price(van, name)
        if pv and vv:
            ratio = vv / pv
    return max(1, round(prev_price * ratio))


def _tokens(name: str) -> set:
    """Tokens significatifs d'un nom : separation camelCase + non-alphabetique,
    >= 4 caracteres, marques/marqueurs ecartes."""
    stop = {"eden", "atl", "uch", "legacy", "player", "epic", "dual",
            "trench", "admin", "test"}
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s)
    return {w.lower() for w in re.split(r"[^A-Za-z]+", s)
            if len(w) >= 4 and w.lower() not in stop}


def famille_targets(report: MarketReport, idx: MarketIndex,
                    min_members: int = 3) -> int:
    """Cible = MEDIANE des cibles de la famille (tokens partagees) pour les
    vendables restes sans proposition (ancrage). Familles de
    < min_members membres ignorees ; les items en cycle de recettes ne sont
    jamais proposes. Retourne le nombre de cibles posees."""
    fam: Dict[str, List[int]] = {}
    for e in report.entries:
        if e.status in (FAMILLE, ANCRAGE, NON_VENDABLE) or e.target is None:
            continue
        for w in _tokens(e.name):
            fam.setdefault(w, []).append(e.target)
    fam = {w: sorted(v)[len(v) // 2] for w, v in fam.items()
           if len(v) >= min_members}
    placed = 0
    for e in report.entries:
        if e.status != ANCRAGE or e.target is not None:
            continue
        if "cycle" in (e.detail or ""):
            continue
        toks = [w for w in _tokens(e.name) if w in fam]
        if not toks:
            continue
        best = max(toks, key=lambda w: sum(
            1 for o in report.entries
            if o.status not in (FAMILLE, ANCRAGE, NON_VENDABLE)
            and o.target is not None and w in _tokens(o.name)))
        e.status = FAMILLE
        e.target = fam[best]
        e.detail += f" ; mediane de famille [{best}]"
        placed += 1
    return placed


def single_input_suspects(idx: MarketIndex, report: MarketReport
                          ) -> List[Dict[str, object]]:
    """Recettes A INGRÉDIENT UNIQUE ou l'entree vaut ~le prix de sortie
    (1:1 sans valeur ajoutee) : liste pour decision manuelle — jamais
    modifiees automatiquement."""
    by_name = {e.name: e for e in report.entries}
    out: List[Dict[str, object]] = []
    for tname, t in idx.templates.items():
        if t.base_item:
            continue           # materiel premier ancre : recette figurative
        ins = [(m, q) for m, q in t.inputs if q != 0]
        if len(ins) != 1:
            continue
        e = by_name.get(tname)
        if e is None or e.price is None:
            continue
        mat, qty = ins[0]
        pin = resolve_price(idx, mat)
        if pin is None:
            continue
        unit_in = float(pin) / max(1, t.output_count)
        val = (e.target if e.target is not None else e.price)
        if unit_in * qty >= 0.95 * val:
            out.append({"template": tname, "input": mat, "qty": qty,
                        "input_price": pin, "output": val})
    return out


@dataclass
class RecipePlan:
    """Recette GENEREE : matieres de la famille dosées pour atteindre la
    cible de prix de l'item (politique prix = cout)."""
    name: str
    target: int
    craft_time: int
    inputs: List[Tuple[str, int]]
    source: str


def plan_recipes(idx: MarketIndex, report: MarketReport
                 ) -> Tuple[List[RecipePlan], List[str]]:
    """Recettes proposables pour les vendables sans recette utilisable :
    le modele = la recette d'un membre de la meme famille dont la cible est
    la plus proche, dosee au prorata target_cible / target_membre.
    Exclus : items en cycle, cibles <= 1 (placeholders), sans membre modele.
    Retourne (plans, candidats ecartes avec raison)."""
    by_name = {e.name: e for e in report.entries}
    fam_members: Dict[str, List[str]] = {}
    for e in report.entries:
        if e.status in (FAMILLE, ANCRAGE, NON_VENDABLE) or e.target is None:
            continue
        if e.name in idx.templates:
            for w in _tokens(e.name):
                fam_members.setdefault(w, []).append(e.name)
    plans: List[RecipePlan] = []
    skipped: List[str] = []
    for e in report.entries:
        if e.status not in (FAMILLE, COUSIN, MATERIAU, ANCRAGE):
            continue
        if e.target is None or e.target <= 1:
            if e.price is not None and e.status != ANCRAGE:
                skipped.append(f"{e.name}: cible <= 1 (placeholder ?)")
            continue
        if "cycle" in (e.detail or ""):
            skipped.append(f"{e.name}: cycle de recettes")
            continue
        toks = [w for w in _tokens(e.name) if w in fam_members]
        if not toks:
            skipped.append(f"{e.name}: aucun modele de famille")
            continue
        best_m, best_gap = None, None
        for w in toks:
            for m in fam_members[w]:
                gap = abs((by_name[m].target or 0) - (e.target or 0))
                if best_gap is None or gap < best_gap:
                    best_m, best_gap = m, gap
        mt = idx.templates.get(best_m)
        me = by_name.get(best_m)
        if mt is None or me is None or me.target is None:
            skipped.append(f"{e.name}: modele de famille illisible")
            continue
        ratio = (e.target or 1) / max(1.0, float(me.target))
        inputs = [(m, max(1, round(q * ratio))) for m, q in mt.inputs
                  if q != 0]
        if not inputs:
            skipped.append(f"{e.name}: modele de famille vide")
            continue
        plans.append(RecipePlan(name=e.name, target=e.target,
                                craft_time=mt.craft_time or 10,
                                inputs=inputs, source=best_m))
    return plans, skipped


def apply_recipes(plans: List[RecipePlan], root) -> Tuple[Path, int]:
    """Ecrit les recettes generees en fin de Templates.ecf (+Template,
    name-based, conventions du projet) : backup central du fichier avant,
    ecriture atomique, revalidation par le parseur. Retourne (chemin, n)."""
    cdir = config_dir(root)
    path = cdir / "Templates.ecf"
    central_backup(path, "market_recipes")
    blocks = []
    for pl in plans:
        ins = "\n".join(f"    {m}: {q}" for m, q in pl.inputs)
        blocks.append(
            f"{{ +Template Name: {pl.name}\n"
            f"  CraftTime: {pl.craft_time}\n"
            f'  Target: "SurvC,SmallC,HoverC,BaseC,LargeC,AdvC"\n'
            f"  {{ Child Inputs\n{ins}\n  }}\n}}\n")
    text = path.read_text(encoding="utf-8", errors="replace")
    if text and not text.endswith("\n"):
        text += "\n"
    text += "\n" + "\n".join(blocks)
    atomic_write_text(path, text)
    parse_ecf_file(path)                    # revalidation : echec = exception
    return path, len(plans)


def build_report(idx: MarketIndex, van: Optional[MarketIndex] = None,
                 margin: float = DEFAULT_MARGIN,
                 fab_pct: float = DEFAULT_FAB_PCT) -> MarketReport:
    """Rapport complet : statut, cout, cible pour chaque bloc/item.
    Une seule passe ; les cibles supposent TOUTES appliquees en meme
    temps (cascade bottom-up)."""
    entries: List[MarketEntry] = []
    for name, od in idx.objs.items():
        price = resolve_price(idx, name)
        tname = resolve_template(idx, name)
        entry = MarketEntry(name=name, kind=od.kind, status=ANCRAGE,
                            price=price, cost=None, target=None, template=tname)
        if price is None:
            entry.status = NON_VENDABLE
            entry.detail = "aucun MarketPrice (jamais ecrit)"
            entries.append(entry)
            continue
        # le "cout" d'un objet SANS template n'existe pas : _unit_cost y
        # retournerait son propre prix (feuille marche) — valable pour un
        # INGREDIENT, pas comme cout de fabrication de la racine
        cost, why = ((None, "") if tname is None
                     else _unit_cost(idx, name, frozenset()))
        if cost is not None and cost > 0:
            entry.cost = cost
            entry.status = FABRIQUABLE if tname == name else GROUPE
            entry.detail = why if tname == name else (
                f"template de groupe: {tname}" + (f" ({why})" if why else ""))
        else:
            entry.detail = why or ("aucune recette" if tname is None
                                   else "cout non calculable")
            cousin = _cousin_target(idx, van, name)
            if cousin is not None:
                entry.status = COUSIN
                entry.target = cousin
                entry.detail += " ; cousin de tier inferieur"
        entries.append(entry)
    # repli materiau/masse : blocs de coque restes sans cible
    ppm = _material_price_per_mass(entries, idx)
    for entry in entries:
        if entry.status != ANCRAGE or entry.kind != "block":
            continue
        od = idx.objs.get(entry.name)
        if od is None:
            continue
        mat = (od.final.get_property("Material") or "").strip().strip('"')
        mass = _num(od.final.get_property("Mass"))
        if mat in ppm and mass and mass > 0:
            entry.status = MATERIAU
            entry.target = max(1, round(ppm[mat] * mass))
            entry.detail += f" ; prix/masse du materiau {mat}"
    report = MarketReport(entries=entries)
    retarget(report, idx, margin, fab_pct)
    # repli FAMILLE : mediane des cibles des items partageant un token —
    # APRES retarget (les cibles fabriquables/groupe doivent exister)
    famille_targets(report, idx)
    report.counts = {}
    for e in entries:
        report.counts[e.status] = report.counts.get(e.status, 0) + 1
    return report


def retarget(report: MarketReport, idx: MarketIndex, margin: float,
             fab_pct: float = DEFAULT_FAB_PCT) -> None:
    """Recalcule les cibles a partir du COUT (fabriquables + groupes) quand
    un parametre bouge — CPU pur, sans re-parse. Les statuts de repli
    (cousin, materiau) ne dependent pas des parametres."""
    for e in report.entries:
        if e.cost is not None and e.cost > 0 and e.status in (FABRIQUABLE, GROUPE):
            e.target = _apply_formula(e.cost, margin, fab_pct)
    # les cibles FAMILLE suivent la mediane (les cibles sources viennent
    # de bouger ci-dessus) — rafraichissement idempotent
    if any(e.status == FAMILLE for e in report.entries):
        famille_targets(report, idx)


# ------------------------------------------------------------ application

def make_changes(idx: MarketIndex, report: MarketReport,
                 names: set) -> List[PriceChange]:
    """Changements pour les objets choisis dont la cible differe du prix
    actuel. Ecriture TOUJOURS sur la definition finale du nom (un +Block
    patch porte proprement la surcharge MarketPrice)."""
    by_name = {e.name: e for e in report.entries}
    out: List[PriceChange] = []
    for name in names:
        e = by_name.get(name)
        od = idx.objs.get(name)
        if (e is None or od is None or e.target is None
                or e.price == e.target):
            continue
        out.append(PriceChange(path=od.final_path, doc=od.final_doc,
                               node=od.final, name=name,
                               old=e.price, new=e.target))
    return out


def apply_changes(changes: List[PriceChange]) -> Dict[Path, int]:
    """Ecrit les changements : MarketPrice existant -> modifie ; absent ->
    ligne AJOUTEE (bloc heritant d'un REF). Backup central prealable
    (jamais de .bak a cote des fichiers du jeu), ecriture atomique."""
    from core.fsutil import central_backup   # local : le monkeypatch conftest s'applique
    by_file: Dict[Path, List[PriceChange]] = {}
    for ch in changes:
        by_file.setdefault(ch.path, []).append(ch)
    done: Dict[Path, int] = {}
    for path, items in by_file.items():
        applied = 0
        for ch in items:
            if not ch.node.set_property("MarketPrice", str(ch.new)):
                add_property_line(ch.node, [("MarketPrice", str(ch.new))])
            applied += 1
        central_backup(path, "market_price")
        atomic_write_text(path, items[0].doc.render())
        done[path] = applied
    return done
