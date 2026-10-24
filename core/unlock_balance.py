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

"""Equilibrage des UnlockCost (cout en points de deblocage de l'arbre
technologique) — chantier 23/10/2026.

Doctrine validee avec l'utilisateur :
  - PERIMETRE : entrees reellement affichees dans l'arbre (TechTreeNames
    non vide et pas uniquement Hidden), avec un UnlockLevel. Les objets
    hors arbre (POI/loot/deco) ne sont jamais touches.
  - REGLE : base = UnlockLevel (minimum 1), puis facteur de puissance dans
    la meme famille et au meme niveau (sqrt du ratio a la mediane, borne
    0,5-2). A niveau egal, un bloc plus puissant coute plus cher.
  - ECART MINIMAL : une valeur existante dans la bande [0,5 x cible ;
    2 x cible] est conservee. Une valeur hors bande est ramenee a la
    borne, pas a la cible exacte.
  - BORNES : cout mini et cout maxi, globaux et modifiables PAR NIVEAU
    (per_level). La cible ET la valeur ecrite sont bornees : une cellule
    vide herite du defaut (mini global ; maxi global, 0 = aucun plafond).
  - ZEROS : remplis (niveau 1 compris). 1000 : consideres comme un
    plafond aberrant et ramenes a la courbe.
  - MONOTONIE : dans une famille, la valeur ecrite ne decroit jamais quand
    le niveau ou la puissance monte (appliquee APRES les bornes).
  - IDEMPOTENT : la cible ne depend pas du cout actuel (sauf la bande),
    donc un re-scan apres application ne repropose pas les memes lignes.

Ecriture sur la definition FINALE de l'objet (BlocksConfig*.ecf ou
ItemsConfig*.ecf, dernier +Block/+Item gagnant), backup central, atomique.
"""
from __future__ import annotations

import statistics

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.ecf.model import EcfBlock, EcfDocument, add_property_line
from core.fsutil import atomic_write_text
from core.parsers_utils import parse_quoted_list
from core.recipe_balance import (RecipeIndex, family_of, load_recipe_index,
                                 power_of, resolve_prop)

MIN_COST = 1
POWER_FLOOR = 0.5
POWER_CEIL = 2.0
BAND_FLOOR = 0.5
BAND_CEIL = 2.0
OUTLIER_COST = 1000
_EXCLUDED_CATEGORIES = {"", "hidden"}


@dataclass
class UnlockProposal:
    name: str
    kind: str                 # 'block' | 'item'
    family: str
    level: float
    power: Optional[float]
    old_cost: Optional[int]   # None = propriete absente
    target: int               # cible de la courbe
    new_cost: int             # valeur a ecrire (bande appliquee)
    changed: bool
    detail: str
    path: Path
    doc: EcfDocument
    node: EcfBlock


def _num(raw) -> Optional[float]:
    if raw is None:
        return None
    value = str(raw).strip().strip('"').split(",")[0].strip()
    try:
        return float(value)
    except ValueError:
        return None


def _in_tree(idx: RecipeIndex, name: str) -> bool:
    """Meme regle que core/tech_tree.py : au moins une categorie reelle."""
    categories = parse_quoted_list(resolve_prop(idx, name, "TechTreeNames"))
    return bool(categories) and not all(
        category.strip().lower() in _EXCLUDED_CATEGORIES
        for category in categories)


def _median(values: List[Optional[float]]) -> Optional[float]:
    clean = [value for value in values if value is not None and value > 0]
    return statistics.median(clean) if clean else None


def _bounds(level: float, min_cost: int, max_cost: Optional[int],
            per_level: Optional[Dict[int, Tuple[Optional[int],
                                                Optional[int]]]]
            ) -> Tuple[int, Optional[int]]:
    """(mini, maxi) effectifs d'un niveau ; maxi None = aucun plafond.
    Une ligne per_level (None, x) ou (x, None) herite du defaut pour la
    cellule laisse vide."""
    if per_level:
        found = per_level.get(int(level))
        if found:
            lo, hi = found
            return (min_cost if lo is None else lo,
                    max_cost if hi is None else (hi or None))
    return min_cost, max_cost


def _clamp(value: int, lo: int, hi: Optional[int]) -> int:
    value = max(value, lo)
    if hi:
        value = min(value, hi)
    return max(value, lo)          # lo prioritaire si les bornes se croisent


def analyze(root, vanilla_root: str = "",
            min_cost: int = MIN_COST, max_cost: Optional[int] = None,
            per_level: Optional[Dict[int, Tuple[Optional[int],
                                                Optional[int]]]] = None
            ) -> List[UnlockProposal]:
    """Toutes les propositions, changed=False incluses (aucune ecriture).

    min_cost / max_cost : bornes globales (max_cost None = aucun plafond) ;
    per_level : {niveau: (mini|None, maxi|None)} — chaque cellule vide
    herite de la borne globale correspondante."""
    idx, _van = load_recipe_index(root, vanilla_root)
    entries: List[UnlockProposal] = []
    for name, obj in idx.objs.items():
        if not _in_tree(idx, name):
            continue
        level = _num(resolve_prop(idx, name, "UnlockLevel"))
        if level is None:
            continue
        old_raw = resolve_prop(idx, name, "UnlockCost")
        old_cost = _num(old_raw)
        entries.append(UnlockProposal(
            name=name, kind=obj.kind, family=family_of(idx, name),
            level=level, power=power_of(idx, name),
            old_cost=int(old_cost) if old_cost is not None else None,
            target=MIN_COST, new_cost=0, changed=False, detail="",
            path=obj.path, doc=obj.doc, node=obj.node))

    by_group: Dict[Tuple[str, float], List[Optional[float]]] = defaultdict(list)
    by_family: Dict[str, List[Optional[float]]] = defaultdict(list)
    for entry in entries:
        by_group[(entry.family, entry.level)].append(entry.power)
        by_family[entry.family].append(entry.power)

    # ------------------------------------------------ cible niveau x puissance
    for entry in entries:
        group = by_group[(entry.family, entry.level)]
        reference = (_median(group) if len(group) >= 2
                     else _median(by_family[entry.family]))
        factor = 1.0
        if entry.power and reference and reference > 0:
            factor = (entry.power / reference) ** 0.5
            factor = min(max(factor, POWER_FLOOR), POWER_CEIL)
        entry.target = max(MIN_COST, int(round(
            max(1.0, entry.level) * factor)))
        lo, hi = _bounds(entry.level, min_cost, max_cost, per_level)
        entry.target = _clamp(entry.target, lo, hi)

    # -------------------------------------------- monotonie dans la famille
    families: Dict[str, List[UnlockProposal]] = defaultdict(list)
    for entry in entries:
        families[entry.family].append(entry)
    for members in families.values():
        members.sort(key=lambda e: (e.level, e.power or 0.0, e.name))
        previous = MIN_COST
        for entry in members:
            if entry.target < previous:
                entry.target = previous
            previous = entry.target

    # --------------------------------------------------- bande d'ecart minimal
    for entry in entries:
        lo, hi = _bounds(entry.level, min_cost, max_cost, per_level)
        old = entry.old_cost
        if old is None or old <= 0:
            entry.new_cost = _clamp(entry.target, lo, hi)
            entry.detail = "rempli (cout absent ou 0)"
        elif old >= OUTLIER_COST:
            entry.new_cost = _clamp(entry.target, lo, hi)
            entry.detail = f"plafond {OUTLIER_COST} ramene a la courbe"
        elif old < BAND_FLOOR * entry.target:
            entry.new_cost = _clamp(
                max(MIN_COST, int(round(BAND_FLOOR * entry.target))), lo, hi)
            entry.detail = "sous la bande : remonte a la borne basse"
        elif old > BAND_CEIL * entry.target:
            entry.new_cost = _clamp(
                int(round(BAND_CEIL * entry.target)), lo, hi)
            entry.detail = "au-dessus de la bande : ramene a la borne haute"
        else:
            entry.new_cost = _clamp(old, lo, hi)
            entry.detail = "dans la bande"

    # la bande peut casser la monotonie (faible a 2x sa cible, fort a 0,5x) :
    # derniere passe sur les valeurs ECRITES, dans l'ordre niveau/puissance.
    # La monotonie s'applique DANS les bornes (elle ne depasse jamais le
    # maxi du niveau) ; elle ne releve donc pas un niveau 25 a 50 parce
    # qu'un niveau 15 est a 50 alors que son maxi est 40 (vecu 24/10).
    for members in families.values():
        members.sort(key=lambda e: (e.level, e.power or 0.0, e.name))
        previous = MIN_COST
        for entry in members:
            lo, hi = _bounds(entry.level, min_cost, max_cost, per_level)
            if entry.new_cost < previous:
                raised = min(previous, hi) if hi else previous
                if raised > entry.new_cost:
                    entry.new_cost = raised
                    if "monotonie" not in entry.detail:
                        entry.detail += " ; releve par monotonie"
            previous = entry.new_cost

    for entry in entries:
        entry.changed = entry.new_cost != (entry.old_cost or 0)
    return entries


def apply_proposals(proposals: List[UnlockProposal]) -> Dict[Path, int]:
    """Ecrit les UnlockCost choisis ; backup central + atomique."""
    from core.fsutil import central_backup   # local : monkeypatch conftest
    by_file: Dict[Path, List[UnlockProposal]] = defaultdict(list)
    for proposal in proposals:
        if proposal.changed:
            by_file[proposal.path].append(proposal)
    done: Dict[Path, int] = {}
    for path, items in by_file.items():
        for proposal in items:
            value = str(int(proposal.new_cost))
            if not proposal.node.set_property("UnlockCost", value):
                add_property_line(proposal.node, [("UnlockCost", value)])
        central_backup(path, "unlock_cost")
        atomic_write_text(path, items[0].doc.render())
        done[path] = len(items)
    return done
