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

from .model import EcfDocument, EcfBlock, EcfProperty, EcfComment, EcfBlank, block_identity, property_lines, normalized_kind


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
class IdConflict:
    """
    Cas dangereux : deux blocs partagent le meme (genre, identite) -- typiquement le
    meme Id -- mais leur propriete 'Name' differe, ce qui indique qu'il s'agit en
    realite de DEUX ELEMENTS DIFFERENTS qui se trouvent juste avoir le meme numero
    d'Id d'un scenario a l'autre (ex: Id 628 = 'InteriorBath' dans un scenario,
    'CPUExtenderLargeT5' dans un autre -- les Id de BlocksConfig.ecf ne sont PAS
    garantis coherents entre deux scenarios independants).

    Dans ce cas, on ne fusionne JAMAIS automatiquement (ce serait fusionner deux
    materiels differents entre eux, silencieusement). Le bloc de la source non
    prioritaire est ajoute au document en fin de fichier, mais DESACTIVE (commente),
    avec une note explicative -- a l'utilisateur de lui assigner un Id libre puis de
    le decommenter manuellement.
    """
    kind: str
    identity: str
    base_name: Optional[str]
    base_source: str
    conflicting_source: str
    conflicting_name: Optional[str]
    block: EcfBlock


@dataclass
class MergeResult:
    document: EcfDocument
    report: List[MergeReportEntry]
    id_conflicts: List[IdConflict] = field(default_factory=list)

    def conflicts(self) -> List[MergeReportEntry]:
        """Entrees ou plusieurs sources definissaient le meme bloc -- la priorite a du
        arbitrer, donc a revoir en premier lors d'un controle humain."""
        return [e for e in self.report if len(e.sources_present) > 1]


def _blocks_correspond(base_block: EcfBlock, other_block: EcfBlock) -> bool:
    """Verifie qu'un Id (ou autre identite) partage designe bien le MEME element
    materiel des deux cotes. On compare 'Name' ET plusieurs proprietes revelatrices
    de l'identite REELLE du bloc (CustomIcon, TemplateRoot, Model).

    Pourquoi pas 'Name' seul : les scenarios recyclent parfois un ancien Id/Name
    vanilla pour un objet completement different (ex: 'InteriorBath' garde son nom
    d'origine mais devient en realite un Quantum CPU via son CustomIcon/TemplateRoot).
    Deux blocs peuvent donc avoir exactement le meme 'Name' tout en etant des elements
    totalement differents -- il faut regarder plus loin que le nom affiche.

    Un mismatch sur N'IMPORTE LAQUELLE de ces cles (quand les deux blocs la definissent)
    suffit a declencher un conflit."""
    identity_keys = ('Name', 'CustomIcon', 'TemplateRoot', 'Model', 'IndexName')
    for key in identity_keys:
        val_a = base_block.get_property(key)
        val_b = other_block.get_property(key)
        if val_a is not None and val_b is not None and val_a != val_b:
            return False
    return True


def _make_pending_comment_nodes(conflict: IdConflict) -> List:
    """Transforme un bloc en conflit en une sequence de commentaires inertes (meme
    convention que les blocs deja desactives manuellement dans les fichiers Empyrion :
    '# { +Container Id: ...'), precedee d'une note expliquant le conflit."""
    header_text = (
        f"# CONFLIT D'ID {conflict.identity} ({conflict.kind}) : la copie de travail "
        f"utilise deja cet Id pour \"{conflict.base_name}\" (source: {conflict.base_source}), "
        f"mais {conflict.conflicting_source} l'utilise pour \"{conflict.conflicting_name}\". "
        f"Bloc DESACTIVE ci-dessous -- assigner un Id libre puis decommenter pour l'activer.\r\n"
    )
    nodes = [EcfBlank(raw="\r\n"), EcfComment(raw=header_text)]
    rendered = conflict.block.render()
    for line in rendered.splitlines(keepends=True):
        stripped = line.rstrip('\r\n')
        if stripped == '':
            nodes.append(EcfComment(raw="#" + line[len(stripped):]))
        else:
            nodes.append(EcfComment(raw="# " + line))
    return nodes


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
    id_conflicts: List[IdConflict] = []

    for label, doc in sources:
        for node in doc.nodes:
            if not isinstance(node, EcfBlock):
                continue
            key = (normalized_kind(node.kind), block_identity(node))
            if key in grouped:
                base_label, base_block = grouped[key][0]
                if key[1] is not None and not _blocks_correspond(base_block, node):
                    id_conflicts.append(IdConflict(
                        kind=node.kind, identity=key[1],
                        base_name=base_block.get_property('Name'), base_source=base_label,
                        conflicting_source=label, conflicting_name=node.get_property('Name'),
                        block=node,
                    ))
                    continue
            else:
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

    for conflict in id_conflicts:
        merged_nodes.extend(_make_pending_comment_nodes(conflict))

    merged_doc = EcfDocument(nodes=merged_nodes, source_path=None)
    return MergeResult(document=merged_doc, report=report, id_conflicts=id_conflicts)


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
    if result.id_conflicts:
        lines.append(f"⚠ {len(result.id_conflicts)} CONFLIT(S) D'ID : Id partage entre deux elements "
                      f"DIFFERENTS -- ajoutes en fin de fichier, DESACTIVES (commentes), non fusionnes")
    lines.append("")

    entries = result.report if show_all else conflicts
    if not entries:
        lines.append("(aucun conflit de fusion -- toutes les identites de bloc n'apparaissaient que dans une seule source)")
    for e in entries:
        sources_str = " > ".join(e.sources_present)
        lines.append(f"  {e.label()} : {sources_str}  (gagnant: {e.winning_source})")
        for ov in e.property_overrides:
            lines.append(f"      + {ov}")

    if result.id_conflicts:
        lines.append("")
        lines.append("CONFLITS D'ID (a revoir manuellement) :")
        for c in result.id_conflicts:
            lines.append(f"  {c.kind} [{c.identity}] : \"{c.base_name}\" ({c.base_source}) "
                          f"vs \"{c.conflicting_name}\" ({c.conflicting_source}) -- bloc desactive en fin de fichier")

    return "\n".join(lines)


# ------------------------------------------------------------------
# Fusion d'un seul bloc (sans toucher au reste du fichier)
# ------------------------------------------------------------------

def merge_single_block(working_doc: EcfDocument, incoming: EcfBlock,
                        source_label: str) -> Tuple[str, object]:
    """
    Fusionne UN SEUL bloc (venant d'une source) dans un document deja charge (la copie
    de travail), sans toucher au reste du fichier -- utile pour importer une seule
    modification/ajout lors d'une mise a jour, sans avoir a tout re-controler.

    Retourne (status, info) ou status vaut :
      'added'    : bloc absent de la copie de travail -> ajoute tel quel.
                   info = (kind, identite)
      'merged'   : bloc deja present et coherent (meme 'Name') -> complete avec les
                   proprietes manquantes. info = ((kind, identite), {cles ajoutees})
      'conflict' : meme identite mais 'Name' different (materiel different) -> PAS
                   fusionne, ajoute en fin de document sous forme de bloc desactive
                   (commente). info = l'IdConflict correspondant.
    """
    key = (normalized_kind(incoming.kind), block_identity(incoming))
    existing = None
    for node in working_doc.nodes:
        if isinstance(node, EcfBlock) and (normalized_kind(node.kind), block_identity(node)) == key:
            existing = node
            break

    if existing is None:
        working_doc.nodes.append(copy.deepcopy(incoming))
        return 'added', key

    if key[1] is not None and not _blocks_correspond(existing, incoming):
        conflict = IdConflict(
            kind=incoming.kind, identity=key[1],
            base_name=existing.get_property('Name'), base_source="copie de travail",
            conflicting_source=source_label, conflicting_name=incoming.get_property('Name'),
            block=incoming,
        )
        working_doc.nodes.extend(_make_pending_comment_nodes(conflict))
        return 'conflict', conflict

    merged_block, overrides = _merge_properties([("copie de travail", existing), (source_label, incoming)])
    idx = working_doc.nodes.index(existing)
    working_doc.nodes[idx] = merged_block
    idents = {ov.split(' (depuis')[0] for ov in overrides}
    return 'merged', (key, idents)
