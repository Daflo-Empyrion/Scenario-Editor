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
Detection et activation des "blocs en attente" -- ceux ajoutes en fin de fichier,
desactives (commentes), par le garde-fou anti-collision d'Id du merge (voir
core/ecf/merge.py, IdConflict). Permet de les reactiver DEPUIS L'APPLI avec un nouvel
Id, sans jamais avoir a editer le fichier a la main dans un editeur externe -- ce qui
evite une source d'erreur reelle (ex: decommenter le bloc mais oublier la '}' de
fermeture, ce qui casse la structure du reste du fichier).
"""
import re
from dataclasses import dataclass
from pathlib import Path
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
                # une ligne RE-commentee (le bloc source contenait lui-meme
                # du commente, ex: '#   # }' -- vecu 26/09 sur les items
                # vanille a enfant desactive) RESTE un commentaire : ses
                # accolades ne comptent pas, sinon le groupe est tronque a
                # la premiere fermeture commentee et l'activation produisait
                # un bloc jamais referme
                if not stripped.startswith('#'):
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


def parse_pending_block(conflict: "PendingConflict") -> Optional[EcfBlock]:
    """Reparse le texte d'un bloc en attente (deja decommenter en memoire) pour
    l'inspecter -- SANS toucher au document d'origine ni changer son Id. Utile pour
    afficher son contenu avant de decider de l'activer."""
    parsed = parse_ecf_text(conflict.block_text)
    blocks = [n for n in parsed.nodes if isinstance(n, EcfBlock)]
    return blocks[0] if len(blocks) == 1 else None


def find_used_ids(ecf_files: List[Path]) -> set:
    """Recense tous les Id numeriques utilises dans une liste de fichiers ECF (tous
    genres de blocs confondus) -- pour pouvoir suggerer des Id libres."""
    used = set()
    for path in ecf_files:
        try:
            with open(path, 'r', encoding='utf-8', newline='') as f:
                doc = parse_ecf_text(f.read())
        except Exception:
            continue
        for block in doc.iter_blocks():
            val = block.get('Id')
            if val and val.strip().lstrip('-').isdigit():
                used.add(int(val))
    return used


def suggest_free_ids(used_ids: set, count: int = 10) -> List[int]:
    """Propose `count` Id libres, au-dessus du maximum actuellement utilise -- la
    zone la plus sure pour ne rentrer en collision avec rien d'existant (scenario
    comme vanilla). Le mod lui-meme peut avoir ses propres conventions de plage
    d'Id -- ceci est une suggestion de depart, pas une regle absolue."""
    if not used_ids:
        return list(range(1, count + 1))
    start = max(used_ids) + 1
    return list(range(start, start + count))


def pending_has_numeric_id(conflict: "PendingConflict") -> bool:
    """Le bloc en attente porte-t-il un Id NUMERIQUE ? Les blocs identifies
    par leur nom (GalaxyConfig : etoiles 'Neutron Star'...) n'ont pas d'Id
    assignable -- vecu 26/09 : 'Activer avec cet Id' echouait sur eux avec
    'motif Id: introuvable' ; ils demandent un REMPLACEMENT du bloc actif."""
    return re.search(r'\bId:\s*\d', conflict.block_text) is not None


def _balanced(conflict: "PendingConflict") -> bool:
    """Un groupe aux accolades non equilibrees (endommage, vecu 26/09)
    produirait un bloc jamais referme qui avalerait tout le fichier au
    re-parse : refuse par les deux operations d'activation."""
    return conflict.block_text.count('{') == conflict.block_text.count('}')


def replace_pending_conflict(doc: EcfDocument, conflict: PendingConflict) -> bool:
    """Blocs SANS Id numerique (identifies par leur Name) : remplace le bloc
    actif de meme identite par le bloc en attente (sur place -- l'ordre de
    chargement est preserve) ; si aucun bloc actif de meme identite n'est
    trouve, insere le bloc en attente a la place des commentaires.
    Retourne False si le texte du bloc n'est pas re-parsable."""
    if not _balanced(conflict):
        return False
    parsed = parse_ecf_text(conflict.block_text)
    new_blocks = [n for n in parsed.nodes if isinstance(n, EcfBlock)]
    if len(new_blocks) != 1:
        return False
    new_block = new_blocks[0]

    del doc.nodes[conflict.header_index:conflict.end_index + 1]

    from .model import block_identity, normalized_kind
    ident = block_identity(new_block)
    target = None
    if ident is not None:
        nkind = normalized_kind(new_block.kind)
        for idx, node in enumerate(doc.nodes):
            if not isinstance(node, EcfBlock) or block_identity(node) != ident:
                continue
            if normalized_kind(node.kind) == nkind:
                target = idx
                break
            if target is None:
                target = idx          # repli : meme identite, kind different
    if target is not None:
        doc.nodes[target] = new_block
    else:
        doc.nodes.insert(conflict.header_index, new_block)
    return True


def activate_pending_conflict_name_only(doc: EcfDocument,
                                        conflict: PendingConflict) -> bool:
    """Active le bloc en attente SANS son Id : identification par Name seul
    (demande 26/09 -- meme convention que les 1335 blocs Id-less du RE2,
    references par les POIs via le mapping de noms). Aucune collision d'Id
    possible. Refuse si un bloc actif porte deja ce Name."""
    if not _balanced(conflict):
        return False
    text = re.sub(r'\bId:\s*\d+\s*,?\s*', '', conflict.block_text, count=1)
    if text == conflict.block_text:
        return False
    parsed = parse_ecf_text(text)
    new_blocks = [n for n in parsed.nodes if isinstance(n, EcfBlock)]
    if len(new_blocks) != 1:
        return False
    new_block = new_blocks[0]
    name = new_block.get_property('Name')
    if not name:
        return False
    for n in doc.nodes:
        if isinstance(n, EcfBlock) and n.get_property('Name') == name:
            return False          # un bloc actif porte deja ce nom
    del doc.nodes[conflict.header_index:conflict.end_index + 1]
    doc.nodes.insert(conflict.header_index, new_block)
    return True


def activate_pending_conflict(doc: EcfDocument, conflict: PendingConflict, new_id: str) -> bool:
    """Remplace la sequence de commentaires par un VRAI bloc actif, avec le nouvel Id
    fourni. Retourne False si le remplacement de l'Id n'a pas pu se faire."""
    if not _balanced(conflict):
        return False
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


def prune_already_imported_conflicts(doc: EcfDocument) -> int:
    """Supprime les groupes de conflit dont le bloc en attente existe DEJA
    actif dans le document sous un autre Id (importe precedemment avec un
    Id libre -- vecu 26/09 : chaque refusion re-proposait ces items, la
    garde anti-collision ne comparant que l'Id, jamais le Name).
    Retourne le nombre de groupes supprimes."""
    from .model import normalized_kind

    active_names = set()
    for node in doc.nodes:
        if isinstance(node, EcfBlock):
            name = node.get_property('Name')
            if name:
                active_names.add((normalized_kind(node.kind), name))

    to_delete = []
    for conflict in find_pending_conflicts(doc):
        pending = parse_pending_block(conflict)
        if pending is None:
            continue
        name = pending.get_property('Name')
        if name and (normalized_kind(pending.kind), name) in active_names:
            to_delete.append(conflict)
    for conflict in sorted(to_delete, key=lambda c: -c.header_index):
        del doc.nodes[conflict.header_index:conflict.end_index + 1]
    return len(to_delete)
