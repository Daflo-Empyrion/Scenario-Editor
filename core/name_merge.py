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

"""Fusion ECF par NOM (demande du 01/10/2026 : « les creatures etc » —
EGroupsConfig.ecf, EClassConfig.ecf...) pour les fichiers dont les blocs
sont identifies par leur Name sans Id. Contrairement a la fusion ECF
generique, elle ne suppose PAS des identites uniques dans la copie de
travail (les doublons internes du working sont affiches mais ignores) :
elle PROPOSE uniquement les blocs sources dont le Name est absent, les
ajoute en fin de fichier (separateur commente, .bak) et est IDEMPOTENTE.
Le working reste prioritaire : un bloc de meme Name chez la source est
signale comme conflit, jamais ecrase."""

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.ecf.model import EcfBlock, EcfComment
from core.ecf.parser import parse_ecf_file
from core.fsutil import atomic_write_text

SEPARATOR_MARKER = "Fusion depuis"
# Fichiers cibles de l'action clic droit (evolutif) :
NAME_MERGE_FILES = {"egroupsconfig.ecf", "eclassconfig.ecf"}


@dataclass(frozen=True)
class NameBlock:
    name: str
    kind: str
    node: EcfBlock


@dataclass
class NameMergePlan:
    blocks_add: List[NameBlock] = field(default_factory=list)
    blocks_same: List[str] = field(default_factory=list)
    working_dupes: List[Tuple[str, int]] = field(default_factory=list)
    source_dupes: List[Tuple[str, int]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _block_name(node: EcfBlock) -> str:
    v = node.get_property("Name")
    return str(v).strip().strip('"') if v is not None else ""


def _name_blocks(path: Path) -> Tuple[Dict[str, NameBlock],
                                      List[Tuple[str, int]]]:
    """({Name: bloc}, doublons internes [(Name, occurrences-1)])."""
    doc = parse_ecf_file(path)
    counts: Dict[str, NameBlock] = {}
    occurrences: Dict[str, int] = {}
    for node in doc.nodes:
        if not isinstance(node, EcfBlock):
            continue
        nm = _block_name(node)
        if not nm:
            continue
        occurrences[nm] = occurrences.get(nm, 0) + 1
        counts.setdefault(nm, NameBlock(
            name=nm, kind=node.kind, node=node))
    dupes = [(nm, c - 1) for nm, c in sorted(occurrences.items())
             if c > 1]
    return counts, dupes


def analyze_name_merge(working_path, source_path) -> NameMergePlan:
    """Blocs de la source absents du working (par Name) + infos. Ne
    modifie rien."""
    plan = NameMergePlan()
    working_path, source_path = Path(working_path), Path(source_path)
    try:
        w_counts, w_dupes = _name_blocks(working_path)
    except Exception as e:                                  # noqa: BLE001
        plan.errors.append(f"working illisible : {e}")
        return plan
    try:
        s_counts, s_dupes = _name_blocks(source_path)
    except Exception as e:                                  # noqa: BLE001
        plan.errors.append(f"source illisible : {e}")
        return plan
    plan.working_dupes = w_dupes
    plan.source_dupes = s_dupes
    for nm, blk in s_counts.items():
        if nm in w_counts:
            plan.blocks_same.append(nm)
        else:
            plan.blocks_add.append(blk)
    return plan


def apply_name_merge(plan: NameMergePlan, working_path,
                     names: Optional[List[str]] = None) -> Dict[str, int]:
    """Ajoute les blocs coches en fin de fichier (separateur commente une
    seule fois, .bak avant ecriture). Idempotent : re-fusion = rien."""
    working_path = Path(working_path)
    stats = {"blocks": 0}
    if not plan.ok or not plan.blocks_add:
        return stats
    doc = parse_ecf_file(working_path)
    wanted = [b for b in plan.blocks_add
              if names is None or b.name in names]
    if not wanted:
        return stats
    has_marker = any(isinstance(n, EcfComment) and SEPARATOR_MARKER
                     in n.raw for n in doc.nodes)
    if not has_marker:
        doc.nodes.append(EcfComment(
            raw=f"# ===== {SEPARATOR_MARKER} source : blocs ajoutes "
                f"ci-dessous =====\r\n"))
    for b in wanted:
        doc.nodes.append(copy.deepcopy(b.node))
        stats["blocks"] += 1
    import shutil
    bak = working_path.with_suffix(working_path.suffix + ".bak")
    if working_path.exists():
        shutil.copy2(working_path, bak)
    atomic_write_text(working_path, doc.render())
    return stats
