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

"""Reordonnancement des declarations ECF pour le chargeur sequentiel du jeu.

Le chargeur ECF resout un `Ref:` au fil du chargement : la cible doit etre
DECLAREE AVANT le bloc qui la reference, sinon le client jette
« Block '<cible>' not found for block '<nom>' » (cascade de NRE a l'ecran de
chargement, vecu 27/10). La vanille respecte cet ordre partout.

`plan_ref_order` liste les couples fautifs ; `apply_ref_order` deplace la
declaration CIBLE (bloc de premier niveau) juste au-dessus du bloc fautif,
puis re-verifie le rendu AVANT ecriture : aucun couple ne doit subsister,
aucun bloc ne doit disparaitre. Les cycles de Ref sont signales comme non
reparables et aucun fichier n'est ecrit s'il en reste.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from core import fsutil

from .model import EcfBlock
from .parser import parse_ecf_file, parse_ecf_text

_KINDS = {"Block", "+Block", "Item", "+Item"}


@dataclass
class RefOrderFix:
    """Une declaration a remonter au-dessus de son utilisateur."""
    target: str
    user: str


@dataclass
class RefOrderPlan:
    path: Path
    fixes: List[RefOrderFix] = field(default_factory=list)
    cycles: List[str] = field(default_factory=list)

    @property
    def nothing_to_do(self) -> bool:
        return not self.fixes


def _name(block: EcfBlock) -> Optional[str]:
    name = block.get_property('Name') or block.get('Name')
    return name.strip() if name else None


def _ref(block: EcfBlock) -> Optional[str]:
    ref = block.get_property('Ref')
    return ref.strip().strip('"') if ref else None


def _decl_blocks(doc) -> List[EcfBlock]:
    """Blocs declares, en ordre de chargement (parcours recursif)."""
    return [b for b in doc.iter_blocks() if b.kind in _KINDS and _name(b)]


def find_offenders(doc) -> List[Tuple[str, str]]:
    """(cible, utilisateur) des Ref dont la cible est declaree APRES --
    meme regle que core.engine_loaders._check_ref_order."""
    blocks = _decl_blocks(doc)
    declared = {_name(b) for b in blocks}
    seen: Set[str] = set()
    out: List[Tuple[str, str]] = []
    for b in blocks:
        name, ref = _name(b), _ref(b)
        if ref and name and ref in declared and ref not in seen:
            out.append((ref, name))
        if name:
            seen.add(name)
    return out


def _cycle_nodes(refs: Dict[str, str]) -> Set[str]:
    """Noms impliques dans un cycle de Ref (DFS 3 couleurs)."""
    state: Dict[str, int] = {}
    in_cycle: Set[str] = set()

    def visit(n: str, stack: List[str]) -> None:
        state[n] = 1
        stack.append(n)
        nxt = refs.get(n)
        if nxt:
            if state.get(nxt) == 1:
                in_cycle.update(stack[stack.index(nxt):])
            elif state.get(nxt, 0) == 0:
                visit(nxt, stack)
        stack.pop()
        state[n] = 2

    for n in refs:
        if state.get(n, 0) == 0:
            visit(n, [])
    return in_cycle


def plan_ref_order(path) -> RefOrderPlan:
    """Analyse sans ecrire : couples fautifs et cycles eventuels."""
    path = Path(path)
    doc = parse_ecf_file(path)
    plan = RefOrderPlan(path=path)
    offenders = find_offenders(doc)
    if not offenders:
        return plan
    refs = {_name(b): _ref(b) for b in _decl_blocks(doc)}
    cycles = _cycle_nodes({k: v for k, v in refs.items() if v})
    for name in sorted(cycles):
        plan.cycles.append(f"{name} -> {refs[name]}")
    for target, user in offenders:
        if target in cycles or user in cycles:
            continue
        plan.fixes.append(RefOrderFix(target=target, user=user))
    return plan


def _top_node(doc, name: str):
    """Bloc de premier niveau qui contient la declaration `name`."""
    def walk(block: EcfBlock) -> bool:
        if _name(block) == name:
            return True
        return any(walk(c) for c in block.children if isinstance(c, EcfBlock))

    for node in doc.nodes:
        if isinstance(node, EcfBlock) and walk(node):
            return node
    return None


def apply_ref_order(plan: RefOrderPlan) -> int:
    """Deplace les cibles fautives au-dessus de leur utilisateur, verifie le
    rendu, puis ecrit. Retourne le nombre de deplacements."""
    if plan.nothing_to_do:
        return 0
    path = Path(plan.path)
    doc = parse_ecf_file(path)
    before = sum(1 for n in doc.nodes if isinstance(n, EcfBlock))
    moved = 0
    for fix in plan.fixes:
        target = _top_node(doc, fix.target)
        user = _top_node(doc, fix.user)
        if target is None or user is None or target is user:
            continue
        ti, ui = doc.nodes.index(target), doc.nodes.index(user)
        if ti < ui:                 # deja satisfait par un deplacement precedent
            continue
        doc.nodes.remove(target)
        doc.nodes.insert(doc.nodes.index(user), target)
        moved += 1
    out = doc.render()
    check = parse_ecf_text(out)
    refs = {_name(b): _ref(b) for b in _decl_blocks(check)}
    cycle_nodes = _cycle_nodes({k: v for k, v in refs.items() if v})
    remaining = [(t, u) for t, u in find_offenders(check)
                 if t not in cycle_nodes and u not in cycle_nodes]
    if remaining:
        raise RuntimeError("Ordre Ref toujours invalide apres deplacement : "
                           + str(remaining[:3]))
    after = sum(1 for n in check.nodes if isinstance(n, EcfBlock))
    if after != before:
        raise RuntimeError(f"Blocs perdus ({before} -> {after}) : ecriture annulee")
    fsutil.central_backup(path, 'ref_order')
    fsutil.atomic_write_bytes(path, out.encode('utf-8', 'surrogateescape'))
    return moved
