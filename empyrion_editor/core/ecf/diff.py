"""
Diff structurel entre deux documents ECF (EcfDocument).

Principe : on ne compare pas ligne à ligne (ça n'aurait aucun sens vu que l'ordre des
blocs peut changer, ou qu'une ligne ajoutée décale tout le reste). On compare bloc par
bloc, en les appariant par identité :
  - Si un bloc a une propriété identifiante (Id, Name, ou Ref -- dans cet ordre de
    priorité), on apparie les blocs de même 'genre' (kind) par cette valeur.
  - Sinon (ex: 'Child Items', qui n'a pas d'identifiant propre), on apparie par position
    s'il y a le même nombre de blocs de ce genre à ce niveau, sinon on les traite comme
    ajoutés/supprimés au mieux.

Pour un couple de blocs appariés, on compare :
  - leurs propriétés directes (Cle: valeur), en aplatissant celles déclarées sur la
    ligne d'ouverture ET celles des lignes enfants
  - récursivement leurs sous-blocs, avec la même logique d'appariement

Le résultat est un arbre de BlockDiff, élagué pour ne garder que ce qui a changé
(un bloc identique dans ses moindres détails n'apparaît pas dans le résultat).
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .model import EcfBlock, EcfDocument, EcfProperty, IDENTITY_KEYS, block_identity as _block_identity, property_lines, normalized_kind


@dataclass
class PropertyDiff:
    key: str
    value_a: Optional[str]   # None si absent du document A (= ajoutée dans B)
    value_b: Optional[str]   # None si absent du document B (= supprimée dans B)
    status: str              # 'added' | 'removed' | 'changed'


@dataclass
class BlockDiff:
    kind: str
    identity: Optional[str]           # valeur Id/Name/Ref, ou None
    status: str                       # 'added' | 'removed' | 'modified'
    property_diffs: List[PropertyDiff] = field(default_factory=list)
    child_diffs: List["BlockDiff"] = field(default_factory=list)
    block_a: Optional[EcfBlock] = None
    block_b: Optional[EcfBlock] = None

    def label(self) -> str:
        if self.identity:
            return f"{self.kind} [{self.identity}]"
        return self.kind

    def has_changes(self) -> bool:
        return bool(self.property_diffs) or bool(self.child_diffs) or self.status in ('added', 'removed')


def diff_documents(doc_a: EcfDocument, doc_b: EcfDocument) -> List[BlockDiff]:
    """Diff au niveau racine du document. Retourne uniquement les blocs qui ont changé
    (ajoutés, supprimés, ou modifiés quelque part dans leur sous-arbre)."""
    blocks_a = [n for n in doc_a.nodes if isinstance(n, EcfBlock)]
    blocks_b = [n for n in doc_b.nodes if isinstance(n, EcfBlock)]
    return diff_blocks(blocks_a, blocks_b)


def diff_blocks(blocks_a: List[EcfBlock], blocks_b: List[EcfBlock]) -> List[BlockDiff]:
    """Diff une liste de blocs (à un niveau donné, ex: tous les enfants directs d'un bloc
    parent, ou les blocs racine du document). Regroupe par 'kind' puis apparie."""
    results: List[BlockDiff] = []

    by_kind_a = _group_by_kind(blocks_a)
    by_kind_b = _group_by_kind(blocks_b)

    all_kinds = list(dict.fromkeys(list(by_kind_a.keys()) + list(by_kind_b.keys())))

    for kind in all_kinds:
        group_a = by_kind_a.get(kind, [])
        group_b = by_kind_b.get(kind, [])
        results.extend(_diff_block_group(kind, group_a, group_b))

    return results


def _group_by_kind(blocks: List[EcfBlock]) -> Dict[str, List[EcfBlock]]:
    groups: Dict[str, List[EcfBlock]] = {}
    for b in blocks:
        groups.setdefault(normalized_kind(b.kind), []).append(b)
    return groups


def _diff_block_group(kind: str, group_a: List[EcfBlock], group_b: List[EcfBlock]) -> List[BlockDiff]:
    results: List[BlockDiff] = []

    identities_a = {_block_identity(b): b for b in group_a}
    identities_b = {_block_identity(b): b for b in group_b}

    has_real_identities = any(k is not None for k in identities_a) or any(k is not None for k in identities_b)

    if has_real_identities:
        # Appariement par identité (Id/Name/Ref)
        all_ids = list(dict.fromkeys(
            [k for k in identities_a if k is not None] + [k for k in identities_b if k is not None]
        ))
        for ident in all_ids:
            a = identities_a.get(ident)
            b = identities_b.get(ident)
            results.extend(_diff_matched_pair(kind, ident, a, b))

        # Blocs sans identité du tout dans ce groupe (rare) -> appariement positionnel de secours
        none_a = [b for b in group_a if _block_identity(b) is None]
        none_b = [b for b in group_b if _block_identity(b) is None]
        results.extend(_diff_positional(kind, none_a, none_b))
    else:
        # Aucun bloc de ce genre n'a d'identifiant (ex: 'Child Items') -> appariement positionnel
        results.extend(_diff_positional(kind, group_a, group_b))

    return results


def _diff_positional(kind: str, group_a: List[EcfBlock], group_b: List[EcfBlock]) -> List[BlockDiff]:
    results = []
    n = max(len(group_a), len(group_b))
    for i in range(n):
        a = group_a[i] if i < len(group_a) else None
        b = group_b[i] if i < len(group_b) else None
        results.extend(_diff_matched_pair(kind, None, a, b))
    return results


def _diff_matched_pair(kind: str, identity: Optional[str],
                        a: Optional[EcfBlock], b: Optional[EcfBlock]) -> List[BlockDiff]:
    if a is None and b is not None:
        return [BlockDiff(kind=kind, identity=identity or _block_identity(b), status='added',
                           block_a=None, block_b=b)]
    if b is None and a is not None:
        return [BlockDiff(kind=kind, identity=identity or _block_identity(a), status='removed',
                           block_a=a, block_b=None)]
    if a is None and b is None:
        return []

    # Les deux existent -> diff des propriétés + recursion sur les sous-blocs
    prop_diffs = _diff_properties(a, b)
    child_diffs = diff_blocks(
        [c for c in a.children if isinstance(c, EcfBlock)],
        [c for c in b.children if isinstance(c, EcfBlock)],
    )

    if not prop_diffs and not child_diffs:
        return []  # bloc strictement identique -> pas de bruit dans le resultat

    return [BlockDiff(kind=kind, identity=identity or _block_identity(a), status='modified',
                       property_diffs=prop_diffs, child_diffs=child_diffs, block_a=a, block_b=b)]


def _format_pairs(pairs: List[Tuple[Optional[str], str]]) -> str:
    """Formate une ligne de propriété pour l'affichage, sans repeter la 1ere cle
    (deja utilisee comme identifiant de la ligne dans le diff)."""
    if not pairs:
        return ''
    _, first_v = pairs[0]
    rest = pairs[1:]
    s = first_v
    if rest:
        s += ", " + ", ".join(f"{k}: {v}" for k, v in rest)
    return s


def _diff_properties(a: EcfBlock, b: EcfBlock) -> List[PropertyDiff]:
    lines_a = property_lines(a)
    lines_b = property_lines(b)

    diffs = []
    all_idents = list(dict.fromkeys(list(lines_a.keys()) + list(lines_b.keys())))
    for ident in all_idents:
        pa = lines_a.get(ident)
        pb = lines_b.get(ident)
        if pa == pb:
            continue
        if pa is None:
            diffs.append(PropertyDiff(key=ident, value_a=None, value_b=_format_pairs(pb), status='added'))
        elif pb is None:
            diffs.append(PropertyDiff(key=ident, value_a=_format_pairs(pa), value_b=None, status='removed'))
        else:
            diffs.append(PropertyDiff(key=ident, value_a=_format_pairs(pa), value_b=_format_pairs(pb), status='changed'))
    return diffs


# ------------------------------------------------------------------
# Rendu texte lisible du resultat de diff
# ------------------------------------------------------------------

def format_diff(diffs: List[BlockDiff], indent: int = 0) -> str:
    lines = []
    pad = "  " * indent
    for d in diffs:
        if d.status == 'added':
            lines.append(f"{pad}+ {d.label()}  (nouveau)")
        elif d.status == 'removed':
            lines.append(f"{pad}- {d.label()}  (supprime)")
        else:
            lines.append(f"{pad}~ {d.label()}  (modifie)")
            for pd in d.property_diffs:
                if pd.status == 'changed':
                    lines.append(f"{pad}    {pd.key}: {pd.value_a} -> {pd.value_b}")
                elif pd.status == 'added':
                    lines.append(f"{pad}    + {pd.key}: {pd.value_b}  (nouvelle propriete)")
                elif pd.status == 'removed':
                    lines.append(f"{pad}    - {pd.key}: {pd.value_a}  (propriete supprimee)")
            if d.child_diffs:
                lines.append(format_diff(d.child_diffs, indent + 2))
    return "\n".join(lines)


def summarize_diff(diffs: List[BlockDiff]) -> Dict[str, int]:
    """Compte recursivement le nombre de blocs ajoutes/supprimes/modifies dans tout l'arbre."""
    counts = {'added': 0, 'removed': 0, 'modified': 0}

    def _walk(items: List[BlockDiff]):
        for d in items:
            counts[d.status] += 1
            if d.child_diffs:
                _walk(d.child_diffs)

    _walk(diffs)
    return counts
