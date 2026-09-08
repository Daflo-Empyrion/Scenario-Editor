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


# ============================================================================
# Blocs DESACTIVEES NATIVEMENT (commentes par l'auteur du fichier, pas par
# l'application) -- YAML-009 cote ECF
# ============================================================================

@dataclass
class NativeCommentedBlock:
    """Un bloc ECF entierement commente dans le fichier source (ex: '#{ +Block',
    '#  Id: 5'..., '#}') -- que l'auteur avait desactive AVANT l'import, sans
    passer par la fonction disable_block() de l'application."""
    label: str   # lisible : kind + Id/Name extraits du texte commente
    nodes: list  # [EcfComment | EcfBlank] du bloc, dans l'ordre du fichier


def find_native_commented_blocks(doc) -> List[NativeCommentedBlock]:
    """Trouve les blocs commentes NATIFS : un run de commentaires qui ouvre une
    accolade ('#{ +Block', '# { +Item'...) et se ferme par un commentaire avec
    '}'. Les lignes vides intercalees font partie du bloc. Ne modifie rien."""
    from .model import EcfComment

    def _body(raw: str) -> str:
        return raw.lstrip().lstrip('#').strip()

    found: List[NativeCommentedBlock] = []
    run: list = []
    in_block = False

    def _flush():
        nonlocal run, in_block
        if in_block and run:
            text = " ".join(_body(n.raw) for n in run if hasattr(n, 'raw'))
            m_id = re.search(r'\bId:\s*(\d+)', text)
            m_name = re.search(r'\bName:\s*"?([^"\r\n}]+)"?', text)
            m_kind = re.search(r'[{\s][-+]?\s*([A-Za-z]\w*)', text)
            label = (m_kind.group(1) if m_kind else "Bloc")
            ident = m_id.group(1) if m_id else (m_name.group(1).strip() if m_name else "?")
            found.append(NativeCommentedBlock(label=f"{label} [{ident}]", nodes=list(run)))
        run = []
        in_block = False

    for node in doc.nodes:
        if isinstance(node, EcfComment):
            body = _body(node.raw)
            if not in_block and '{' in body:
                _flush()
                in_block = True
                run.append(node)
                if '}' in body:
                    _flush()
            elif in_block:
                run.append(node)
                if '}' in body:
                    _flush()
            else:
                _flush()
        elif isinstance(node, EcfBlank):
            if in_block:
                run.append(node)
        else:
            _flush()
    _flush()
    return found


def uncomment_native_block(block: NativeCommentedBlock) -> None:
    """Reactiver un bloc commente nativement : retire les '#' de chaque ligne
    (EN MEMOIRE) ; l'appelant re-parse ensuite le document et rafraichit."""
    from .model import EcfComment
    for node in block.nodes:
        if isinstance(node, EcfComment):
            stripped = node.raw.lstrip()
            indent = node.raw[:len(node.raw) - len(stripped)]
            body = stripped.lstrip('#')
            if body.startswith((' ', '{')):
                body = body.lstrip() if body.startswith('{') else body
            node.raw = indent + body
