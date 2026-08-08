"""
Moteur de fusion (merge) entre plusieurs documents ECF, avec ordre de priorité.

Généralise le système de fusion à priorité (RE2/ATLnext/ATLcrew) développé
précédemment, en le rendant réutilisable sur n'importe quel fichier ECF.

Deux modes :

  - mode 'block' (par défaut, le plus sûr) : pour chaque identité de bloc (Id/Name/Ref),
    le bloc ENTIER provient de la source la plus prioritaire qui le possède. Pas de
    mélange de propriétés à l'intérieur d'un même bloc -- le résultat est toujours un
    bloc intact, tel qu'il existait dans une des sources.

  - mode 'properties' : fusion propriété par propriété (ligne par ligne). Pour chaque
    ligne (Count, Size, Name_0, Group_1...), la valeur provient de la source la plus
    prioritaire qui la définit, même si ce n'est pas la même source que pour les autres
    lignes du même bloc. Le bloc de base (structure, commentaires, ordre) est celui de
    la source la plus prioritaire qui possède ce bloc ; les propriétés manquantes chez
    elle mais présentes ailleurs sont ajoutées, copiées depuis leur source d'origine.
    Limite : les sous-blocs (ex: 'Child Items') finissent regroupés après toutes les
    propriétés simples dans le résultat fusionné, même si leur position d'origine était
    différente -- une légère réorganisation, sans impact sur le contenu.

Dans les deux cas, un rapport de fusion liste les identités présentes dans plusieurs
sources (donc "arbitrées" par la priorité), pour revue humaine avant application.
"""
import copy
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .model import EcfDocument, EcfBlock, EcfProperty, block_identity, property_lines


@dataclass
class MergeReportEntry:
    kind: str
    identity: Optional[str]
    sources_present: List[str]                       # labels des sources qui possedaient ce bloc
    winning_source: str                               # source dont vient le bloc (mode block) ou le bloc de base (mode properties)
    property_overrides: List[str] = field(default_factory=list)  # mode 'properties' seulement

    def label(self) -> str:
        return f"{self.kind} [{self.identity}]" if self.identity else self.kind


@dataclass
class MergeResult:
    document: EcfDocument
    report: List[MergeReportEntry]

    def conflicts(self) -> List[MergeReportEntry]:
        """Entrees ou plusieurs sources definissaient le meme bloc -- la priorite a du
        arbitrer, donc a revoir en premier lors d'un controle humain."""
        return [e for e in self.report if len(e.sources_present) > 1]


def merge_documents(sources: List[Tuple[str, EcfDocument]], mode: str = 'block') -> MergeResult:
    """
    sources : liste de (label, EcfDocument), dans l'ordre de PRIORITE DECROISSANTE
              (la premiere source de la liste gagne en cas de conflit).
    mode    : 'block' (par defaut) ou 'properties'.
    """
    if mode not in ('block', 'properties'):
        raise ValueError("mode doit etre 'block' ou 'properties'")
    if not sources:
        raise ValueError("au moins une source est requise")

    grouped: Dict[Tuple[str, Optional[str]], List[Tuple[str, EcfBlock]]] = {}
    order: List[Tuple[str, Optional[str]]] = []

    for label, doc in sources:
        for node in doc.nodes:
            if not isinstance(node, EcfBlock):
                continue
            key = (node.kind, block_identity(node))
            if key not in grouped:
                grouped[key] = []
                order.append(key)
            grouped[key].append((label, node))

    merged_nodes = []
    report: List[MergeReportEntry] = []

    for key in order:
        kind, identity = key
        candidates = grouped[key]  # deja dans l'ordre de priorite (car sources iterees dans cet ordre)
        winning_label, winning_block = candidates[0]
        sources_present = [label for label, _ in candidates]

        if mode == 'block' or len(candidates) == 1:
            merged_block = copy.deepcopy(winning_block)
            entry = MergeReportEntry(kind=kind, identity=identity, sources_present=sources_present,
                                      winning_source=winning_label)
        else:
            merged_block, overrides = _merge_properties(candidates)
            entry = MergeReportEntry(kind=kind, identity=identity, sources_present=sources_present,
                                      winning_source=winning_label, property_overrides=overrides)

        merged_nodes.append(merged_block)
        report.append(entry)

    merged_doc = EcfDocument(nodes=merged_nodes, source_path=None)
    return MergeResult(document=merged_doc, report=report)


def _merge_properties(candidates: List[Tuple[str, EcfBlock]]) -> Tuple[EcfBlock, List[str]]:
    """Fusionne les proprietes de plusieurs versions d'un meme bloc (mode 'properties').
    `candidates` est deja trie par priorite decroissante."""
    base_label, base_block = candidates[0]
    merged = copy.deepcopy(base_block)

    base_lines = property_lines(merged)
    overrides = []

    for label, block in candidates[1:]:
        other_lines = property_lines(block)
        for ident, pairs in other_lines.items():
            if ident in base_lines:
                continue  # une source plus prioritaire definit deja cette ligne
            _add_property_line(merged, pairs)
            base_lines[ident] = pairs
            overrides.append(f"{ident} (depuis {label})")

    # Fusionne aussi les sous-blocs (ex: Child Items), et les substitue dans merged.children
    # sans toucher aux lignes de propriete simples deja en place ci-dessus.
    merged_sub_blocks = _merge_child_blocks(candidates)
    merged.children = [c for c in merged.children if not isinstance(c, EcfBlock)] + merged_sub_blocks

    return merged, overrides


def _add_property_line(block: EcfBlock, pairs: List[Tuple[Optional[str], str]]) -> None:
    """Insere une nouvelle ligne de propriete (copiee depuis une autre source) dans un
    bloc. Placee avant le premier sous-bloc s'il y en a un, pour rester groupee avec les
    autres proprietes simples plutot qu'apres un bloc imbrique comme 'Child Items'."""
    indent = "  "
    for child in block.children:
        if isinstance(child, EcfProperty):
            indent = child.indent
            break
    new_prop = EcfProperty(raw="", indent=indent, pairs=list(pairs), comment=None, eol=block.eol, dirty=True)

    insert_at = len(block.children)
    for i, child in enumerate(block.children):
        if isinstance(child, EcfBlock):
            insert_at = i
            break
    block.children.insert(insert_at, new_prop)


def _merge_child_blocks(candidates: List[Tuple[str, EcfBlock]]) -> List[EcfBlock]:
    """Fusionne les sous-blocs (EcfBlock enfants directs) de plusieurs versions d'un
    bloc, par (kind, identite), avec la meme logique de priorite qu'au niveau racine."""
    grouped: Dict[Tuple[str, Optional[str]], List[Tuple[str, EcfBlock]]] = {}
    order: List[Tuple[str, Optional[str]]] = []

    for label, block in candidates:
        for child in block.children:
            if isinstance(child, EcfBlock):
                key = (child.kind, block_identity(child))
                if key not in grouped:
                    grouped[key] = []
                    order.append(key)
                grouped[key].append((label, child))

    merged_sub_blocks = []
    for key in order:
        subcandidates = grouped[key]
        if len(subcandidates) == 1:
            merged_sub_blocks.append(copy.deepcopy(subcandidates[0][1]))
        else:
            sub_merged, _ = _merge_properties(subcandidates)
            merged_sub_blocks.append(sub_merged)

    return merged_sub_blocks


# ------------------------------------------------------------------
# Rendu texte lisible du rapport de fusion
# ------------------------------------------------------------------

def format_report(result: MergeResult, show_all: bool = False) -> str:
    lines = []
    conflicts = result.conflicts()
    lines.append(f"Total : {len(result.report)} bloc(s) dans le resultat fusionne")
    lines.append(f"Dont {len(conflicts)} present(s) dans plusieurs sources (arbitres par la priorite)")
    lines.append("")

    entries = result.report if show_all else conflicts
    if not entries:
        lines.append("(aucun conflit -- toutes les identites de bloc n'apparaissaient que dans une seule source)")
    for e in entries:
        sources_str = " > ".join(e.sources_present)
        lines.append(f"  {e.label()} : {sources_str}  (gagnant: {e.winning_source})")
        for ov in e.property_overrides:
            lines.append(f"      + {ov}")
    return "\n".join(lines)
