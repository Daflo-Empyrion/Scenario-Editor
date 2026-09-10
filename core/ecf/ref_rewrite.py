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

"""Reecriture des references internes d'un bloc duplique.

Quand on duplique un bloc identifie (Id: 1234 -> Id: 5678), les sous-blocs
du clone qui heritaient de l'ORIGINAL via 'Ref: 1234' doivent pointer vers
le clone ('Ref: 5678') -- sinon le clone reste accroche a l'original :
modifier le clone ne servirait a rien, les deux evoluant ensemble.
Reecriture CONSERVATRIVE : seules les proprietes 'Ref' dont la valeur est
exactement l'ancien Id sont touchees (les Ref vers d'autres blocs, les
valeurs avec espaces supplements et les autres cles de reference ne sont
pas modifiees)."""

from typing import List

from core.ecf.model import EcfBlock


def rewrite_internal_refs(nodes: List, old_id: str, new_id: str) -> int:
    """Parcourt les blocs de `nodes` (recursivement) ; pour chaque bloc dont
    l'Id vaut new_id (le clone), remplace dans son sous-arbre les 'Ref:
    old_id' par 'Ref: new_id'. Retourne le nombre de reecritures."""
    if not old_id or not new_id or old_id == new_id:
        return 0
    count = 0

    def visit(node) -> None:
        nonlocal count
        if not isinstance(node, EcfBlock):
            return
        if node.get('Id') == new_id:
            count += _rewrite_tree(node, old_id, new_id)
        for child in node.children:
            visit(child)

    for node in nodes:
        visit(node)
    return count


def _rewrite_tree(block: EcfBlock, old_id: str, new_id: str) -> int:
    count = 0
    for child in block.children:
        if isinstance(child, EcfBlock):
            count += _rewrite_tree(child, old_id, new_id)
        elif hasattr(child, 'pairs'):
            for i, (key, value) in enumerate(child.pairs):
                if key in ('Ref', 'ref') and value is not None \
                        and value.strip() == old_id:
                    child.pairs[i] = (key, new_id)
                    child.dirty = True
                    count += 1
    return count
