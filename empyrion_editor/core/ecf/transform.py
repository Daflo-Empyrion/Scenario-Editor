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


@dataclass
class TransformReport:
    changes: List[TransformChange] = field(default_factory=list)
    skipped_non_numeric: int = 0  # valeurs trouvees mais non numeriques -> ignorees, jamais modifiees


def apply_transform(doc: EcfDocument, rule: TransformRule) -> TransformReport:
    report = TransformReport()

    for block in doc.iter_blocks(rule.block_kind):
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
            prop_node.pairs[pair_index] = (key, new_value)
            prop_node.dirty = True
            report.changes.append(TransformChange(
                block_kind=block.kind,
                block_identity=block_identity(block),
                old_value=old_value,
                new_value=new_value,
            ))

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


def format_report(report: TransformReport, max_lines: int = 50) -> str:
    lines = [f"{len(report.changes)} valeur(s) modifiee(s)"]
    if report.skipped_non_numeric:
        lines.append(f"{report.skipped_non_numeric} valeur(s) trouvee(s) mais non numerique(s) -> ignoree(s)")
    lines.append("")
    for c in report.changes[:max_lines]:
        label = f"{c.block_kind} [{c.block_identity}]" if c.block_identity else c.block_kind
        lines.append(f"  {label} : {c.old_value} -> {c.new_value}")
    if len(report.changes) > max_lines:
        lines.append(f"  ... et {len(report.changes) - max_lines} autre(s)")
    return "\n".join(lines)
