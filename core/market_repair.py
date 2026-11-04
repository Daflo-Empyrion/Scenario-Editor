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

"""Reparation des prix aberrants et des recettes generees cycliques.

Vecu 04/11/2026 : le generateur de recettes a copie la recette d'un modele
de famille sur des items qui figuraient DEDANS (les 16 templates boost
partagent la liste d'Eden_BoostAbyssRecipe, qui se contient elle-meme).
Le calcul du cout, en presence d'un cycle, se rabattait sur le MarketPrice
du maillon cyclique : chaque application gonflait le prix suivant
(72 objets a 1e17-1e18).

Ce module :
1. detecte les templates issus de cette generation (auto-referents, et
   copies d'une liste auto-referente qui contient plusieurs items) ;
2. simule les couts SANS ces templates (retour aux `Ref:` sains) ;
3. propose une remise a niveau des prix aberrants : prix vanilla quand il
   existe, sinon cout simule si plausible ;
4. applique : suppression des templates + ecriture des prix, sauvegardes
   centrales, verification avant ecriture.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from core import fsutil

from .ecf.model import EcfBlock
from .ecf.parser import parse_ecf_file, parse_ecf_text
from .market_balance import (MAX_SANE_TARGET, MarketIndex, PriceChange,
                             TemplateDef, _unit_cost, apply_changes,
                             load_index, resolve_price)

CONF = "Content/Configuration"


@dataclass
class BadTemplate:
    name: str
    reason: str


@dataclass
class PriceFix:
    name: str
    old: int
    new: int
    source: str                     # 'vanille' | 'cout'


@dataclass
class MarketRepairPlan:
    root: Path
    templates_path: Path
    bad_templates: List[BadTemplate] = field(default_factory=list)
    price_fixes: List[PriceFix] = field(default_factory=list)
    unresolved: List[str] = field(default_factory=list)
    inflated: int = 0

    @property
    def nothing_to_do(self) -> bool:
        return not self.bad_templates and not self.price_fixes


def find_generated_templates(
        templates: Dict[str, TemplateDef]) -> List[BadTemplate]:
    """Templates produits par la generation de recettes : auto-referents, et
    copies d'une liste auto-referente qui contient PLUSIEURS items (la liste
    boost copiee sur 16 templates ; une liste a un seul item, comme un
    hoverbike, ne declenche pas la copie en masse)."""
    selfref = {n for n, t in templates.items()
               if any(i == n for i, _ in t.inputs)}
    shared = set()
    for n in selfref:
        ins = templates[n].inputs
        # la liste boost contient PLUSIEURS items eux-memes auto-referents
        # (Eden_BoostAbyssRecipe, MultiBoost, JetpackBoost) ; une liste
        # alimentaire n'en contient qu'un seul (l'item lui-meme).
        if sum(1 for i, _ in ins if i in selfref) >= 2:
            shared.add(tuple(ins))
    out = []
    for n, t in templates.items():
        if n in selfref:
            out.append(BadTemplate(n, "recette auto-referente"))
        elif tuple(t.inputs) in shared:
            out.append(BadTemplate(n, "liste copiee d'une recette cyclique"))
    return sorted(out, key=lambda b: b.name)


def plan_market_repair(root, vanilla_root: str = "") -> MarketRepairPlan:
    """Analyse sans ecrire : templates a retirer et prix a remettre a niveau."""
    root = Path(root)
    idx, van = load_index(root, vanilla_root)
    path = root / CONF / "Templates.ecf"
    bad = find_generated_templates(idx.templates)
    plan = MarketRepairPlan(root=root, templates_path=path, bad_templates=bad)
    bad_names = {b.name for b in bad}
    clean = MarketIndex(objs=idx.objs,
                        templates={n: t for n, t in idx.templates.items()
                                   if n not in bad_names})
    for name, od in idx.objs.items():
        if od.price is None or od.price <= MAX_SANE_TARGET:
            continue
        plan.inflated += 1
        vp = resolve_price(van, name) if van is not None else None
        if vp is not None and 0 < vp <= MAX_SANE_TARGET:
            plan.price_fixes.append(PriceFix(name, od.price, vp, "vanille"))
            continue
        cost, _ = _unit_cost(clean, name, frozenset())
        if cost is not None and 0 < cost <= MAX_SANE_TARGET:
            plan.price_fixes.append(
                PriceFix(name, od.price, round(cost), "cout"))
        else:
            plan.unresolved.append(name)
    # dernier repli : cible du rapport marche recalcule SUR l'index nettoye
    # (cousin de tier, famille, materiau) pour les items sans prix vanilla
    if plan.unresolved:
        from .market_balance import build_report
        rep = build_report(clean, van)
        by_name = {e.name: e for e in rep.entries}
        rest = []
        for name in plan.unresolved:
            e = by_name.get(name)
            if e is not None and e.target is not None \
                    and 0 < e.target <= MAX_SANE_TARGET:
                plan.price_fixes.append(
                    PriceFix(name, idx.objs[name].price, e.target, "modele"))
            else:
                rest.append(name)
        plan.unresolved = rest
    return plan


def _remove_templates(path: Path, names: set) -> int:
    doc = parse_ecf_file(path)
    targets = [n for n in doc.nodes if isinstance(n, EcfBlock)
               and (n.get_property('Name') or n.get('Name') or '').strip() in names]
    if not targets:
        return 0
    for node in targets:
        doc.nodes.remove(node)
    out = doc.render()
    check = parse_ecf_text(out)
    left = {b.get_property('Name') for b in check.nodes
            if isinstance(b, EcfBlock)} & names
    if left:
        raise RuntimeError(f"Templates non supprimes : {sorted(left)[:5]}")
    fsutil.central_backup(path, 'market_repair')
    # normalise aussi les fins de ligne : le generateur avait converti tout
    # le fichier en LF (read_text), les ECF du jeu sont en CRLF
    text = out.replace('\r\n', '\n').replace('\n', '\r\n')
    fsutil.atomic_write_bytes(path, text.encode('utf-8', 'surrogateescape'))
    return len(targets)


def apply_market_repair(plan: MarketRepairPlan) -> dict:
    """Supprime les templates, ecrit les prix, puis verifie le resultat."""
    if plan.nothing_to_do:
        return {"templates": 0, "prices": 0, "files": 0}
    removed = 0
    if plan.bad_templates:
        removed = _remove_templates(plan.templates_path,
                                    {b.name for b in plan.bad_templates})
    files = 0
    if plan.price_fixes:
        idx, _ = load_index(plan.root)
        changes: List[PriceChange] = []
        for fix in plan.price_fixes:
            od = idx.objs.get(fix.name)
            if od is None or od.price == fix.new:
                continue
            changes.append(PriceChange(path=od.final_path, doc=od.final_doc,
                                       node=od.final, name=fix.name,
                                       old=od.price, new=fix.new))
        files = len(apply_changes(changes))
    return {"templates": removed, "prices": len(plan.price_fixes),
            "files": files}
