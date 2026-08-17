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
Moteur de transformations en masse sur un document ECF.

Principe : on cible une CLE de propriete (ex: 'Count', 'param1', 'Health'), on filtre
les blocs concernes (par genre, et eventuellement par liste d'identites precises), et
on applique une operation numerique a toutes les valeurs trouvees pour cette cle --
que ce soit une propriete simple de bloc ('Count: "3,4"') ou une sous-cle repetee dans
des lignes de type liste ('Name_0: X, param1: 0.3, param2: "1,2"').

Les valeurs peuvent etre :
  - un nombre simple, quote ou non : "0.5" ou 0.5
  - une plage min,max, quotee ou non : "3,6"
Dans le cas d'une plage, l'operation s'applique aux DEUX bornes.

Par defaut, la recherche est recursive (elle descend aussi dans les sous-blocs comme
'Child Items'). Les proprietes declarees sur la ligne d'ouverture d'un bloc (Id, etc.)
ne sont jamais ciblees, pour ne jamais toucher accidentellement a un identifiant.
"""
import copy
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .model import EcfDocument, EcfBlock, EcfProperty, block_identity


@dataclass
class TransformRule:
    property_key: str                       # ex: 'param1', 'Count', 'Health'
    operation: str                          # 'multiply' | 'add' | 'set' | 'clamp' | 'round'
    amount: Optional[float] = None          # pour multiply / add / set
    min_value: Optional[float] = None       # pour clamp
    max_value: Optional[float] = None       # pour clamp
    ndigits: int = 2                        # pour round
    block_kind: Optional[str] = None        # None = tous les genres de blocs
    block_ids: Optional[List[str]] = None   # None = tous les blocs de ce genre
    recursive: bool = True                  # chercher aussi dans les sous-blocs (ex: Child Items)


@dataclass
class TransformChange:
    block_kind: str
    block_identity: Optional[str]
    old_value: str
    new_value: str
    # Id et Name captures SEPAREMENT (pas seulement block_identity, qui ne retient
    # que le premier trouve par ordre de priorite Id > Name > Ref -- voir
    # block_identity() dans model.py) : permet d'afficher les deux ensemble cote
    # interface graphique quand un bloc a les deux, bien plus facile a identifier
    # qu'un numero seul lors de la revue avant application.
    block_id: Optional[str] = None
    block_name: Optional[str] = None
    # Reference directe vers l'emplacement exact de la valeur dans le document --
    # None pour tout usage qui ne mute jamais rien (ex: rapport CLI classique).
    # Presente pour permettre a l'interface graphique de proposer une revue ligne
    # par ligne avec edition manuelle avant application (voir gui/ecf_edit_widget.py,
    # TransformDialog) : chaque changement garde une reference directe vers son
    # noeud propriete et l'index de sa paire, pour pouvoir appliquer exactement la
    # valeur finale choisie par l'utilisateur, meme si elle differe du calcul
    # automatique -- necessaire par exemple pour MaxCount, qui doit parfois rester a
    # 1 sur certains blocs a cause d'une limite du moteur du jeu, malgre une regle
    # generale differente pour le reste du fichier.
    prop_node: Optional[EcfProperty] = None
    pair_index: Optional[int] = None
    property_key: Optional[str] = None


@dataclass
class TransformReport:
    changes: List[TransformChange] = field(default_factory=list)
    skipped_non_numeric: int = 0  # valeurs trouvees mais non numeriques -> ignorees, jamais modifiees


def _compute_changes(doc: EcfDocument, rule: TransformRule) -> TransformReport:
    """Calcule les changements proposes par la regle SANS RIEN MUTER -- fonction
    partagee par apply_transform() (qui applique ensuite les valeurs calculees
    telles quelles) et par preview_transform() (qui les laisse tel quel pour revue/
    edition manuelle avant une application ulterieure explicite)."""
    report = TransformReport()

    # Uniquement les blocs de PREMIER NIVEAU ici (pas doc.iter_blocks(), qui parcourt
    # deja recursivement TOUS les blocs y compris imbriques comme "Child Items") --
    # la descente dans les sous-blocs est geree une seule fois, explicitement, par
    # _find_matching_pairs via rule.recursive ci-dessous. Utiliser iter_blocks() ici
    # en plus provoquerait un double comptage : un sous-bloc serait visite une fois
    # via sa recursion propre, puis une seconde fois quand iter_blocks() l'atteint
    # lui-meme independamment -- corrige suite a un signalement de bug reel (valeurs
    # multipliees deux fois sur des proprietes imbriquees).
    top_level_blocks = [n for n in doc.nodes if isinstance(n, EcfBlock)]
    for block in top_level_blocks:
        if rule.block_kind is not None and block.kind != rule.block_kind:
            continue
        if rule.block_ids is not None:
            ident = block_identity(block)
            if ident not in rule.block_ids:
                continue

        matches = _find_matching_pairs(block, rule.property_key, rule.recursive)
        for prop_node, pair_index in matches:
            key, old_value = prop_node.pairs[pair_index]
            new_value, ok = _apply_operation(old_value, rule)
            if not ok:
                report.skipped_non_numeric += 1
                continue
            if new_value == old_value:
                continue
            report.changes.append(TransformChange(
                block_kind=block.kind,
                block_identity=block_identity(block),
                block_id=block.get("Id"),
                block_name=block.get("Name"),
                old_value=old_value,
                new_value=new_value,
                prop_node=prop_node,
                pair_index=pair_index,
                property_key=key,
            ))

    return report


def preview_transform(doc: EcfDocument, rule: TransformRule) -> TransformReport:
    """Calcule les changements proposes SANS LES APPLIQUER -- a utiliser pour un
    apercu (voir gui/ecf_edit_widget.py, TransformDialog). Chaque TransformChange
    du rapport retourne garde une reference directe (prop_node, pair_index) vers
    l'emplacement exact dans le document, pour permettre une application ulterieure
    explicite avec, eventuellement, une valeur ajustee manuellement plutot que celle
    calculee automatiquement."""
    return _compute_changes(doc, rule)


def apply_transform(doc: EcfDocument, rule: TransformRule) -> TransformReport:
    """Calcule ET applique immediatement les changements au document (comportement
    historique, utilise par l'outil en ligne de commande transform_ecf.py -- voir
    preview_transform() ci-dessus pour un calcul sans mutation, utilise par le
    dialogue de l'interface graphique)."""
    report = _compute_changes(doc, rule)
    for change in report.changes:
        change.prop_node.pairs[change.pair_index] = (change.property_key, change.new_value)
        change.prop_node.dirty = True
    return report


def _find_matching_pairs(block: EcfBlock, key: str, recursive: bool) -> List[Tuple[EcfProperty, int]]:
    """Trouve toutes les paires (nœud propriété, index de la paire) dont la clé
    correspond, parmi les lignes de propriété directes du bloc (jamais l'en-tête)."""
    matches = []
    for child in block.children:
        if isinstance(child, EcfProperty):
            for i, (k, v) in enumerate(child.pairs):
                if k == key:
                    matches.append((child, i))
        elif isinstance(child, EcfBlock) and recursive:
            matches.extend(_find_matching_pairs(child, key, recursive))
    return matches


# ------------------------------------------------------------------
# Parsing / formatage numerique (gere les plages "min,max" et le quotage)
# ------------------------------------------------------------------

_NUMBER_RE = re.compile(r'^-?\d+(\.\d+)?$')


def _parse_numbers(value_str: str) -> Optional[Tuple[List[float], bool]]:
    quoted = value_str.startswith('"') and value_str.endswith('"') and len(value_str) >= 2
    inner = value_str[1:-1] if quoted else value_str
    parts = [p.strip() for p in inner.split(',')]
    if not parts or not all(_NUMBER_RE.match(p) for p in parts):
        return None
    return [float(p) for p in parts], quoted


def _format_number(x: float) -> str:
    if x == int(x):
        return str(int(x))
    s = f"{x:.4f}".rstrip('0').rstrip('.')
    return s


def _format_numbers(nums: List[float], quoted: bool) -> str:
    s = ",".join(_format_number(n) for n in nums)
    return f'"{s}"' if quoted else s


def _apply_operation(value_str: str, rule: TransformRule) -> Tuple[str, bool]:
    parsed = _parse_numbers(value_str)
    if parsed is None:
        return value_str, False
    nums, quoted = parsed

    new_nums = []
    for n in nums:
        if rule.operation == 'multiply':
            n = n * rule.amount
        elif rule.operation == 'add':
            n = n + rule.amount
        elif rule.operation == 'set':
            n = rule.amount
        elif rule.operation == 'clamp':
            lo = rule.min_value if rule.min_value is not None else n
            hi = rule.max_value if rule.max_value is not None else n
            n = max(lo, min(hi, n))
        elif rule.operation == 'round':
            n = round(n, rule.ndigits)
        else:
            raise ValueError(f"Operation inconnue : {rule.operation}")
        new_nums.append(n)

    return _format_numbers(new_nums, quoted), True


def format_block_label(change: "TransformChange") -> str:
    """Etiquette lisible d'un bloc pour l'affichage (CLI et interface graphique) :
    combine Id ET Name quand les deux existent (ex: 'Block [399] ConcreteBlocks'),
    plutot que de n'en montrer qu'un seul comme le fait block_identity() -- bien
    plus facile a identifier lors d'une revue de plusieurs changements."""
    if change.block_id and change.block_name:
        return f"{change.block_kind} [{change.block_id}] {change.block_name}"
    if change.block_identity:
        return f"{change.block_kind} [{change.block_identity}]"
    return change.block_kind


def format_report(report: TransformReport, max_lines: int = 50) -> str:
    lines = [f"{len(report.changes)} valeur(s) modifiee(s)"]
    if report.skipped_non_numeric:
        lines.append(f"{report.skipped_non_numeric} valeur(s) trouvee(s) mais non numerique(s) -> ignoree(s)")
    lines.append("")
    for c in report.changes[:max_lines]:
        label = format_block_label(c)
        lines.append(f"  {label} : {c.old_value} -> {c.new_value}")
    if len(report.changes) > max_lines:
        lines.append(f"  ... et {len(report.changes) - max_lines} autre(s)")
    return "\n".join(lines)
