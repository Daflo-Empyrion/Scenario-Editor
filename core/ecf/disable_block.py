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
Desactivation/reactivation manuelle d'un bloc, pour tester l'elimination de causes
probables lors d'un bug de lancement (ex: le jeu plante, on veut essayer sans tel
bloc precis sans le supprimer ni casser la structure du fichier).

Reutilise la meme convention de commentaire que le garde-fou anti-collision du merge
(core/ecf/merge.py) -- chaque ligne du bloc prefixee par '# ' -- mais avec son propre
marqueur d'en-tete pour ne pas se confondre avec un conflit d'Id.
"""
import re
from dataclasses import dataclass
from typing import List, Optional

from .model import EcfDocument, EcfBlock, EcfComment, EcfBlank
from .parser import parse_ecf_text

_HEADER_MARKER = "BLOC DESACTIVE (TEST)"


@dataclass
class DisabledBlock:
    header_index: int
    start_index: int
    end_index: int
    header_text: str
    block_text: str  # texte du bloc, '# ' deja retire, pret a re-parser
    label: str        # ex: "Block [1234]" -- pour affichage


def disable_block(doc: EcfDocument, block: EcfBlock, author: str) -> bool:
    """Commente le bloc donne, EXACTEMENT a sa position actuelle dans le fichier (ne
    le deplace jamais en fin de fichier -- important pour l'ordre de chargement).
    Retourne False si le bloc n'est pas trouve au niveau racine du document."""
    index = None
    for i, n in enumerate(doc.nodes):
        if n is block:
            index = i
            break
    if index is None:
        return False

    from .model import block_identity
    ident = block_identity(block)
    label = f"{block.kind} [{ident}]" if ident else block.kind

    header_text = (
        f"# {_HEADER_MARKER} -- {label} -- desactive par {author} pour tester "
        f"l'elimination des causes probables d'un bug. Decommenter (ou utiliser "
        f"'Reactiver' dans l'appli) pour le remettre.\r\n"
    )
    comment_nodes = [EcfComment(raw=header_text)]
    rendered = block.render()
    for line in rendered.splitlines(keepends=True):
        stripped = line.rstrip('\r\n')
        if stripped == '':
            comment_nodes.append(EcfComment(raw="#" + line[len(stripped):]))
        else:
            comment_nodes.append(EcfComment(raw="# " + line))

    doc.nodes[index:index + 1] = comment_nodes
    return True


def find_disabled_blocks(doc: EcfDocument) -> List[DisabledBlock]:
    """Trouve toutes les sequences de commentaires generees par disable_block()."""
    results = []
    nodes = doc.nodes
    i = 0
    n = len(nodes)
    while i < n:
        node = nodes[i]
        if isinstance(node, EcfComment) and _HEADER_MARKER in node.raw:
            header_idx = i
            # Extrait le label affiche depuis l'en-tete (entre les deux '--')
            m = re.search(r'--\s*(.+?)\s*--', node.raw)
            label = m.group(1) if m else "?"
            j = i + 1
            lines = []
            depth = 0
            started = False
            while j < n and isinstance(nodes[j], EcfComment):
                raw = nodes[j].raw
                if raw.startswith('# '):
                    uncommented = raw[2:]
                elif raw.startswith('#'):
                    uncommented = raw[1:]
                else:
                    break
                lines.append(uncommented)
                stripped = uncommented.strip()
                if stripped.startswith('{'):
                    depth += 1
                    started = True
                if stripped.endswith('}'):
                    depth -= 1
                j += 1
                if started and depth <= 0:
                    break
            if lines:
                results.append(DisabledBlock(
                    header_index=header_idx,
                    start_index=i + 1,
                    end_index=j - 1,
                    header_text=node.raw.strip(),
                    block_text="".join(lines),
                    label=label,
                ))
            i = j
        else:
            i += 1
    return results


def enable_disabled_block(doc: EcfDocument, disabled: DisabledBlock) -> bool:
    """Remplace la sequence de commentaires par le bloc reel reactive, EXACTEMENT a
    la meme position dans le fichier (important : preserve l'ordre de chargement)."""
    parsed = parse_ecf_text(disabled.block_text)
    new_blocks = [n for n in parsed.nodes if isinstance(n, EcfBlock)]
    if len(new_blocks) != 1:
        return False

    doc.nodes[disabled.header_index:disabled.end_index + 1] = [new_blocks[0]]
    return True
