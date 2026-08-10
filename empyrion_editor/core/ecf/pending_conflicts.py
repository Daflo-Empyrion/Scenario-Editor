"""
Detection et activation des "blocs en attente" -- ceux ajoutes en fin de fichier,
desactives (commentes), par le garde-fou anti-collision d'Id du merge (voir
core/ecf/merge.py, IdConflict). Permet de les reactiver DEPUIS L'APPLI avec un nouvel
Id, sans jamais avoir a editer le fichier a la main dans un editeur externe -- ce qui
evite une source d'erreur reelle (ex: decommenter le bloc mais oublier la '}' de
fermeture, ce qui casse la structure du reste du fichier).
"""
import re
from dataclasses import dataclass
from typing import List, Optional

from .model import EcfDocument, EcfBlock, EcfComment, EcfBlank
from .parser import parse_ecf_text

_HEADER_MARKER = "CONFLIT D'ID"


@dataclass
class PendingConflict:
    header_index: int    # index dans doc.nodes du commentaire d'en-tete explicatif
    start_index: int      # premier index du bloc commente lui-meme
    end_index: int         # dernier index (inclusif) du bloc commente
    header_text: str
    block_text: str        # texte du bloc, '# ' deja retire, pret a re-parser


def find_pending_conflicts(doc: EcfDocument) -> List[PendingConflict]:
    """Trouve toutes les sequences de commentaires generees par le garde-fou
    anti-collision du merge (reperables par leur en-tete '# CONFLIT D'ID ...')."""
    results = []
    nodes = doc.nodes
    i = 0
    n = len(nodes)
    while i < n:
        node = nodes[i]
        if isinstance(node, EcfComment) and _HEADER_MARKER in node.raw:
            header_idx = i
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
                results.append(PendingConflict(
                    header_index=header_idx,
                    start_index=i + 1,
                    end_index=j - 1,
                    header_text=node.raw.strip(),
                    block_text="".join(lines),
                ))
            i = j
        else:
            i += 1
    return results


def activate_pending_conflict(doc: EcfDocument, conflict: PendingConflict, new_id: str) -> bool:
    """Remplace la sequence de commentaires par un VRAI bloc actif, avec le nouvel Id
    fourni. Retourne False si le remplacement de l'Id n'a pas pu se faire."""
    new_text = re.sub(r'(Id:\s*)[^\s,]+', r'\g<1>' + new_id, conflict.block_text, count=1)
    if new_text == conflict.block_text:
        return False

    parsed = parse_ecf_text(new_text)
    new_blocks = [n for n in parsed.nodes if isinstance(n, EcfBlock)]
    if len(new_blocks) != 1:
        return False

    new_block = new_blocks[0]

    del doc.nodes[conflict.header_index:conflict.end_index + 1]
    doc.nodes.insert(conflict.header_index, new_block)
    return True
