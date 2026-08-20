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
Verification de coherence ENTRE plusieurs fichiers du scenario -- complement a
core/ecf/dependency_check.py, qui ne verifie que 'Ref' (heritage) au sein d'un
meme ensemble de fichiers ECF. Ici, chaque verification cible un croisement
different (un item/bloc mentionne existe-t-il vraiment ailleurs ? un token
existe-t-il ? un POI de playfield existe-t-il sur le disque ?).

Chaque verification est independante et activable/desactivable -- voir
CROSS_REFERENCE_CHECKS ci-dessous, la liste consultee par l'interface
graphique (gui/cross_reference_dialog.py) pour construire les cases a cocher.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Set

from .parser import parse_ecf_file
from .model import block_identity, EcfBlock, EcfProperty


@dataclass
class CrossRefIssue:
    source_file: Path
    source_kind: str
    source_identity: str      # Id (ou Name a defaut) du bloc contenant la reference cassee
    ref_key: str               # ex: 'Name_0', 'Ref', motif "Token:XXXX" trouve dans une valeur
    ref_value: str              # la valeur qui n'a pas ete trouvee
    check_id: str                # quelle verification a signale ce probleme
    detail: str = ""              # contexte supplementaire (ou la valeur etait attendue)
    display_path: str = ""         # chemin lisible (calcule par la verification qui a genere
                                     # ce probleme) -- utile quand le simple nom de fichier est
                                     # ambigu, ex: "playfield_dynamic.yaml" existe dans CHAQUE
                                     # dossier de playfield ; vide = repli sur source_file.name

    def label(self) -> str:
        suffix = f" ({self.detail})" if self.detail else ""
        path_display = self.display_path or self.source_file.name
        return (f"{path_display} : {self.source_kind} [{self.source_identity}] -- "
                f"{self.ref_key}: {self.ref_value}{suffix}")


@dataclass
class CrossRefCheck:
    id: str
    label_fr: str
    label_en: str
    description_fr: str
    description_en: str
    enabled_by_default: bool
    run: Callable[["CrossRefContext"], List[CrossRefIssue]]


@dataclass
class CrossRefContext:
    """Fichiers du scenario deja localises, pour eviter que chaque verification
    reparse ou re-parcoure le disque independamment."""
    ecf_files: List[Path] = field(default_factory=list)
    yaml_files: List[Path] = field(default_factory=list)
    scenario_root: Optional[Path] = None


def _find_file(files: List[Path], filename: str) -> Optional[Path]:
    for f in files:
        if f.name == filename:
            return f
    return None


def _all_property_pairs(doc):
    """Genere (block, prop_node, key, value) pour CHAQUE paire cle/valeur du
    document, y compris dans les sous-blocs (Child Items etc.) -- reutilise le
    meme principe que _all_property_keys_recursive() dans gui/ecf_edit_widget.py,
    mais retourne aussi le bloc racine (premier niveau) pour identifier la source
    d'une reference cassee de facon lisible."""
    def walk(nodes, current_top_block):
        for node in nodes:
            if isinstance(node, EcfBlock):
                top = node if current_top_block is None else current_top_block
                for k, v in node.pairs:
                    if k:
                        yield top, node, k, v
                yield from walk(node.children, top)
            elif isinstance(node, EcfProperty):
                if current_top_block is not None:
                    for k, v in node.pairs:
                        if k:
                            yield current_top_block, node, k, v

    yield from walk(doc.nodes, None)


# ============================================================================
# Verification 1 : heritage Ref -- reprend dependency_check.py existant
# ============================================================================

def _relative_display_path(path: Path, scenario_root: Optional[Path]) -> str:
    """Chemin lisible relatif a la racine du scenario quand possible (ex:
    'Content/Configuration/Containers.ecf'), sinon juste le nom de fichier."""
    if scenario_root is not None:
        try:
            return str(path.relative_to(scenario_root))
        except ValueError:
            pass
    return path.name


def _check_ref_inheritance(ctx: CrossRefContext) -> List[CrossRefIssue]:
    from .dependency_check import check_references
    broken = check_references(ctx.ecf_files)
    return [
        CrossRefIssue(
            source_file=b.file, source_kind=b.kind, source_identity=b.identity,
            ref_key=b.ref_key, ref_value=b.ref_value, check_id="ref_inheritance",
            display_path=_relative_display_path(b.file, ctx.scenario_root),
        )
        for b in broken
    ]


# ============================================================================
# Verification 2 : items/blocs references (motif "Name_N") existent-ils dans
# le pool combine ItemsConfig.ecf + BlocksConfig.ecf (un bloc ramasse devient
# un item du meme nom -- les deux fichiers partagent le meme espace de noms
# pour ce genre de reference, voir Containers.ecf/LootGroups.ecf/Templates.ecf)
# ============================================================================

_NAME_N_PATTERN = re.compile(r'^Name_\d+$')


def _build_item_block_pool(ctx: CrossRefContext) -> Set[str]:
    items_file = _find_file(ctx.ecf_files, 'ItemsConfig.ecf')
    blocks_file = _find_file(ctx.ecf_files, 'BlocksConfig.ecf')
    target_files = [f for f in (items_file, blocks_file) if f is not None]
    if not target_files:
        # Repli : si ces deux fichiers precis ne sont pas dans le projet (scenario
        # personnalise avec d'autres noms de fichiers), utilise tous les fichiers
        # ECF disponibles plutot que de ne rien verifier du tout.
        target_files = ctx.ecf_files

    pool: Set[str] = set()
    for path in target_files:
        try:
            doc = parse_ecf_file(path)
        except Exception:
            continue
        for block in doc.iter_blocks():
            name = block.get_property('Name')
            if name:
                pool.add(name)
    return pool


def _check_item_block_pool(ctx: CrossRefContext) -> List[CrossRefIssue]:
    pool = _build_item_block_pool(ctx)
    issues: List[CrossRefIssue] = []

    for path in ctx.ecf_files:
        try:
            doc = parse_ecf_file(path)
        except Exception:
            continue
        for top_block, prop_node, key, value in _all_property_pairs(doc):
            if not value or not _NAME_N_PATTERN.match(key or ""):
                continue
            if value.startswith("Token:"):
                continue  # verifie separement par _check_token_refs
            if value not in pool:
                issues.append(CrossRefIssue(
                    source_file=path, source_kind=top_block.kind,
                    source_identity=block_identity(top_block) or "?",
                    ref_key=key, ref_value=value, check_id="item_block_pool",
                    detail="attendu dans ItemsConfig.ecf ou BlocksConfig.ecf",
                    display_path=_relative_display_path(path, ctx.scenario_root),
                ))
    return issues


# ============================================================================
# Verification 3 : references "Token:XXXX" -- le jeton doit exister (par son
# Id) dans TokenConfig.ecf
# ============================================================================

_TOKEN_REF_PATTERN = re.compile(r'Token:\s*(\d+)')


def _check_token_refs(ctx: CrossRefContext) -> List[CrossRefIssue]:
    token_file = _find_file(ctx.ecf_files, 'TokenConfig.ecf')
    token_ids: Set[str] = set()
    if token_file is not None:
        try:
            doc = parse_ecf_file(token_file)
            for block in doc.iter_blocks():
                id_val = block.get_property('Id')
                if id_val:
                    token_ids.add(id_val.strip().lstrip('0') or '0')
        except Exception:
            pass

    issues: List[CrossRefIssue] = []
    for path in ctx.ecf_files:
        try:
            doc = parse_ecf_file(path)
        except Exception:
            continue
        for top_block, prop_node, key, value in _all_property_pairs(doc):
            if not value:
                continue
            for m in _TOKEN_REF_PATTERN.finditer(value):
                token_id = m.group(1).lstrip('0') or '0'
                if token_file is None:
                    detail = "TokenConfig.ecf introuvable dans le projet"
                elif token_id not in token_ids:
                    detail = "aucun bloc avec cet Id dans TokenConfig.ecf"
                else:
                    continue
                issues.append(CrossRefIssue(
                    source_file=path, source_kind=top_block.kind,
                    source_identity=block_identity(top_block) or "?",
                    ref_key=key, ref_value=f"Token:{m.group(1)}", check_id="token_refs",
                    detail=detail, display_path=_relative_display_path(path, ctx.scenario_root),
                ))
    return issues


# ============================================================================
# Registre -- consulte par l'interface graphique pour construire les cases a
# cocher, dans cet ordre
# ============================================================================

CROSS_REFERENCE_CHECKS: List[CrossRefCheck] = [
    CrossRefCheck(
        id="ref_inheritance",
        label_fr="Heritage Ref (au sein des fichiers ECF)",
        label_en="Ref inheritance (within ECF files)",
        description_fr="Chaque 'Ref:' correspond-il a un 'Name' existant ?",
        description_en="Does each 'Ref:' match an existing 'Name'?",
        enabled_by_default=True,
        run=_check_ref_inheritance,
    ),
    CrossRefCheck(
        id="item_block_pool",
        label_fr="Items/blocs references (Templates, Containers, LootGroups...)",
        label_en="Referenced items/blocks (Templates, Containers, LootGroups...)",
        description_fr="Chaque item/bloc mentionne (motif 'Name_N') existe-t-il dans "
                        "ItemsConfig.ecf ou BlocksConfig.ecf ?",
        description_en="Does each mentioned item/block (pattern 'Name_N') exist in "
                        "ItemsConfig.ecf or BlocksConfig.ecf?",
        enabled_by_default=True,
        run=_check_item_block_pool,
    ),
    CrossRefCheck(
        id="token_refs",
        label_fr="Jetons (Token:XXXX) definis dans TokenConfig.ecf",
        label_en="Tokens (Token:XXXX) defined in TokenConfig.ecf",
        description_fr="Chaque reference 'Token:XXXX' correspond-elle a un bloc "
                        "existant dans TokenConfig.ecf ?",
        description_en="Does each 'Token:XXXX' reference match an existing block "
                        "in TokenConfig.ecf?",
        enabled_by_default=True,
        run=_check_token_refs,
    ),
]


def run_checks(ctx: CrossRefContext, check_ids: List[str]) -> List[CrossRefIssue]:
    """Lance uniquement les verifications dont l'id figure dans check_ids, dans
    l'ordre du registre -- utilise par le dialogue GUI selon les cases cochees."""
    issues: List[CrossRefIssue] = []
    by_id = {c.id: c for c in CROSS_REFERENCE_CHECKS}
    for check_id in check_ids:
        check = by_id.get(check_id)
        if check is None:
            continue
        issues.extend(check.run(ctx))
    return issues
