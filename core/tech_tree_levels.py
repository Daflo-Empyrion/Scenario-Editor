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

"""Reparation de la progression de l'arbre technologique.

Le moteur exige un UnlockLevel STRICTEMENT superieur a celui du parent
(« Item unlock level of higher tier <= lower tier: X », vecu 27/10). La
regle de correction suit les paliers reels du jeu (1/3/5/7/10/12/15/20/25),
puis parent+1 au-dela. Relever un parent peut a son tour invalider ses
enfants : le plan calcule donc le point fixe avant toute ecriture.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core import fsutil

from .ecf.model import add_property_line
from .ecf.parser import parse_ecf_file, parse_ecf_text
from .tech_tree import load_tech_tree

LADDER = (1, 3, 5, 7, 10, 12, 15, 20, 25)


@dataclass
class LevelFix:
    name: str
    source: str                 # 'block' | 'item'
    path: Path
    current: int
    parent: str
    parent_level: int
    new_level: int


@dataclass
class LevelPlan:
    fixes: List[LevelFix] = field(default_factory=list)

    @property
    def nothing_to_do(self) -> bool:
        return not self.fixes


def next_level(parent_level: int) -> int:
    """Premier palier strictement superieur au parent, sinon parent+1."""
    for step in LADDER:
        if step > parent_level:
            return step
    return parent_level + 1


def _path_for(source: str, blocks_path: Optional[Path],
              items_path: Optional[Path]) -> Optional[Path]:
    return blocks_path if source == 'block' else items_path


def plan_unlock_progression(blocks_path, items_path,
                            vanilla_root: Optional[str] = None) -> LevelPlan:
    """Plan sans ecriture, point fixe inclus (les enfants d'un parent releve
    sont releves a leur tour si necessaire)."""
    blocks_path = Path(blocks_path) if blocks_path else None
    items_path = Path(items_path) if items_path else None
    tree = load_tech_tree(blocks_path, items_path, vanilla_root)
    levels: Dict[str, int] = {n.name: n.unlock_level for n in tree.nodes}
    by_name = {n.name: n for n in tree.nodes}
    fixes: Dict[str, LevelFix] = {}
    for _ in range(200):                       # point fixe borne
        changed = False
        for n in tree.nodes:
            p = by_name.get(n.parent_name) if n.parent_name else None
            if p is None:
                continue
            parent_level = levels.get(p.name, p.unlock_level)
            if levels.get(n.name, n.unlock_level) > parent_level:
                continue
            new = next_level(parent_level)
            levels[n.name] = new
            path = _path_for(n.source, blocks_path, items_path)
            if path is None:
                continue
            fixes[n.name] = LevelFix(
                name=n.name, source=n.source, path=path,
                current=n.unlock_level, parent=p.name,
                parent_level=parent_level, new_level=new)
            changed = True
        if not changed:
            break
    return LevelPlan(fixes=list(fixes.values()))


def _set_level(block, new_level: int) -> bool:
    if block.get_property('UnlockLevel') is None:
        add_property_line(block, [('UnlockLevel', str(new_level))])
        return True
    return block.set_property('UnlockLevel', str(new_level))


def apply_unlock_progression(plan: LevelPlan) -> int:
    """Ecrit les niveaux par fichier (un seul rendu par fichier), verifie le
    rendu AVANT ecriture, puis sauvegarde chaque fichier modifie."""
    if plan.nothing_to_do:
        return 0
    by_path: Dict[Path, List[LevelFix]] = {}
    for fix in plan.fixes:
        by_path.setdefault(Path(fix.path), []).append(fix)
    written = 0
    for path, fixes in by_path.items():
        doc = parse_ecf_file(path)
        done = 0
        for fix in fixes:
            block = _find_block(doc, fix.name)
            if block is not None and _set_level(block, fix.new_level):
                done += 1
        if not done:
            continue
        out = doc.render()
        check = parse_ecf_text(out)
        for fix in fixes:
            block = _find_block(check, fix.name)
            if block is not None and block.get_property('UnlockLevel') != str(fix.new_level):
                raise RuntimeError(f"UnlockLevel non ecrit pour {fix.name} : "
                                   "ecriture annulee")
        fsutil.central_backup(path, 'tech_tree_levels')
        fsutil.atomic_write_bytes(path, out.encode('utf-8', 'surrogateescape'))
        written += done
    return written


def _find_block(doc, name: str):
    for block in doc.iter_blocks():
        if block.get_property('Name') == name or block.get('Name') == name:
            return block
    return None


def remaining_violations(blocks_path, items_path,
                         vanilla_root: Optional[str] = None) -> List[Tuple[str, str]]:
    """(enfant, parent) encore en niveau non croissant, pour verification."""
    tree = load_tech_tree(Path(blocks_path) if blocks_path else None,
                          Path(items_path) if items_path else None, vanilla_root)
    by_name = {n.name: n for n in tree.nodes}
    out = []
    for n in tree.nodes:
        p = by_name.get(n.parent_name) if n.parent_name else None
        if p is not None and n.unlock_level <= p.unlock_level:
            out.append((n.name, p.name))
    return out
