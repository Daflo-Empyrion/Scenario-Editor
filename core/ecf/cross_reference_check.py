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

from core.yamllite.parser import parse_yaml_file
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
# Verification 4 : dialogues -- Next_N/OptionNext_N (et leur eventuel param1
# co-occurrent sur la meme ligne) doivent pointer vers un Name de bloc
# +Dialogue qui existe reellement. Confirme sur un vrai Dialogues.ecf (5417
# dialogues, 3109 Next_N, 8769 OptionNext_N, 473 lignes avec param1) :
# - le motif "OptionNext_N: X, param1: Y" n'est PAS un renvoi vers un autre
#   fichier (hypothese initiale erronee, verifiee et corrigee) -- X et Y sont
#   tous deux des Name de dialogue DANS LE MEME fichier, tous deux a valider
# - "End" et "GotoAndReset" sont des mots-cles reserves (fin de conversation /
#   action speciale), jamais des noms de dialogue -- confirmes absents de
#   toute definition Name sur l'ensemble du fichier de reference
# - "NextIf_N" (condition de script, ex: "TalkCount > 3") n'est PAS une
#   reference et ne doit jamais etre verifiee -- le motif de cle est concu
#   pour l'exclure naturellement (Next_\d+ ne capture pas NextIf_\d+)
# ============================================================================

_DIALOGUE_REF_KEY_PATTERN = re.compile(r'^(Next|OptionNext)_\d+$')
_DIALOGUE_REF_SENTINELS = {'End', 'GotoAndReset', 'Return'}


def _check_dialogue_refs(ctx: CrossRefContext) -> List[CrossRefIssue]:
    dialogue_names: Set[str] = set()
    for path in ctx.ecf_files:
        try:
            doc = parse_ecf_file(path)
        except Exception:
            continue
        for block in doc.iter_blocks():
            if block.kind == '+Dialogue':
                name = block.get_property('Name')
                if name:
                    dialogue_names.add(name)

    issues: List[CrossRefIssue] = []
    for path in ctx.ecf_files:
        try:
            doc = parse_ecf_file(path)
        except Exception:
            continue
        for block in doc.iter_blocks():
            if block.kind != '+Dialogue':
                continue
            for child in block.children:
                if not isinstance(child, EcfProperty):
                    continue
                # Ne traite que les lignes contenant reellement une cle
                # Next_N/OptionNext_N -- une ligne "param1" isolee sans ce
                # contexte (improbable mais par securite) ne doit jamais etre
                # interpretee comme une reference de dialogue.
                has_ref_key = any(k and _DIALOGUE_REF_KEY_PATTERN.match(k) for k, v in child.pairs)
                if not has_ref_key:
                    continue
                for key, value in child.pairs:
                    if not key or not value or value in _DIALOGUE_REF_SENTINELS:
                        continue
                    if value.startswith('@'):
                        continue  # reference dynamique a une Variable_N du meme
                        # dialogue, resolue par le moteur de script au moment de
                        # l'execution (ex: 'Next_1: @NextState' avec
                        # 'Execute: "NextState = ..."' ailleurs dans le meme
                        # bloc) -- jamais un nom de dialogue litteral, impossible
                        # a valider statiquement, confirme sur un vrai fichier.
                    if value not in dialogue_names:
                        issues.append(CrossRefIssue(
                            source_file=path, source_kind=block.kind,
                            source_identity=block_identity(block) or "?",
                            ref_key=key, ref_value=value, check_id="dialogue_refs",
                            detail="attendu comme Name d'un autre bloc +Dialogue",
                            display_path=_relative_display_path(path, ctx.scenario_root),
                        ))
    return issues


# ============================================================================
# Registre -- consulte par l'interface graphique pour construire les cases a
# cocher, dans cet ordre
# ============================================================================

# ============================================================================
# Verification 5 : materiaux references par les blocs (`Material: X`) presents
# dans MaterialConfig.ecf ? (vecu 04/10 : bloc 872 ->
# 'hullcombatcharged' absent du MaterialConfig du scénario -> la table des
# blocs chargeait morte, cascade « No template found » + NRE au demarrage)
# ============================================================================

def _check_material_refs(ctx: CrossRefContext) -> List[CrossRefIssue]:
    materials_file = _find_file(ctx.ecf_files, 'MaterialConfig.ecf')
    if materials_file is None:
        # Scenario sans MaterialConfig propre : les materiaux viennent du jeu
        # de base, on n'a rien a comparer localement.
        return []
    defined: Set[str] = set()
    try:
        doc = parse_ecf_file(materials_file)
    except Exception:
        return []
    for block in doc.iter_blocks():
        if block.kind.lstrip('+').rstrip(',').casefold() == 'material':
            name = block.get_property('Name')
            if name:
                defined.add(name)
    issues: List[CrossRefIssue] = []
    for path in ctx.ecf_files:
        if path == materials_file:
            continue
        try:
            doc = parse_ecf_file(path)
        except Exception:
            continue
        for top_block, _node, key, value in _all_property_pairs(doc):
            if key != 'Material':
                continue
            mat = (value or '').split(',')[0].strip().strip('"')
            if mat and mat not in defined:
                issues.append(CrossRefIssue(
                    source_file=path,
                    source_kind=top_block.kind,
                    source_identity=block_identity(top_block) or '?',
                    ref_key='Material',
                    ref_value=mat,
                    check_id="material_refs",
                    display_path=_relative_display_path(path, ctx.scenario_root),
                ))
    return issues


# ============================================================================
# Verification 6 : POIs cibles des missions du PDA (NearPoi/PoiDiscovered)
# presents dans les playfields du scenario ? (vecu 05/10 : la mission locale
# Masperon de Random EXP cible des cages qui ne spawnaient pas dans le
# scenario hote — mission bloquee sans aucun indice en jeu)
# ============================================================================

_PDA_POI_CHECKS = ('NearPoi', 'PoiDiscovered')


def _check_pda_poi_refs(ctx: CrossRefContext) -> List[CrossRefIssue]:
    """Chaque POI cible par une action de mission du PDA.yaml
    (Check: NearPoi / PoiDiscovered, propriete Names) doit correspondre a
    un POI spawnable dans les playfields du scenario (GroupName, Name ou
    Prefab). Collecte GENEREUSE du pool (toute profondeur, tous les yamls
    de Playfields/) pour minimiser les faux positifs ; les noms avec
    joker '*' sont ignores. Scenario sans PDA.yaml ou sans Playfields ->
    rien a verifier."""
    if ctx.scenario_root is None:
        return []
    pda_path = Path(ctx.scenario_root) / 'Extras' / 'PDA' / 'PDA.yaml'
    if not pda_path.is_file():
        return []
    try:
        pda_doc = parse_yaml_file(pda_path)
    except Exception:
        return []

    pool_cf: Set[str] = set()
    pf_dir = Path(ctx.scenario_root) / 'Playfields'
    for f in sorted(pf_dir.glob('*/*.yaml')) if pf_dir.is_dir() else []:
        try:
            pf_doc = parse_yaml_file(f)
        except Exception:
            continue

        def collect(nodes):
            for node in nodes:
                k = getattr(node, 'key', None)
                v = (getattr(node, 'value', '') or '').strip().strip("'\"")
                if k in ('GroupName', 'Name', 'Prefab') and v:
                    pool_cf.add(v.casefold())
                collect(getattr(node, 'children', None) or [])
        collect(pf_doc.nodes)

    issues: List[CrossRefIssue] = []

    def walk_actions(nodes):
        for node in nodes:
            if getattr(node, 'key', None) == 'ActionTitle':
                check_val = names = None
                for ch in getattr(node, 'children', []) or []:
                    ck = getattr(ch, 'key', None)
                    if ck == 'Check':
                        check_val = (getattr(ch, 'value', '') or '').strip()
                    elif ck == 'Names':
                        names = ch
                if check_val in _PDA_POI_CHECKS and names is not None:
                    for c in getattr(names, 'children', []) or []:
                        nm = (getattr(c, 'value', '') or '').strip().strip("'\"")
                        if not nm or '*' in nm:
                            continue
                        if nm.casefold() not in pool_cf:
                            issues.append(CrossRefIssue(
                                source_file=pda_path,
                                source_kind='PDA',
                                source_identity=str(getattr(node, 'value', '') or '?'),
                                ref_key=check_val,
                                ref_value=nm,
                                check_id='pda_poi_refs',
                                display_path='Extras/PDA/PDA.yaml',
                            ))
            walk_actions(getattr(node, 'children', []) or [])

    walk_actions(pda_doc.nodes)
    return issues


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
    CrossRefCheck(
        id="dialogue_refs",
        label_fr="Dialogues (Next/OptionNext vers un Name existant)",
        label_en="Dialogues (Next/OptionNext to an existing Name)",
        description_fr="Chaque cible Next_N/OptionNext_N (et son eventuel "
                        "param1) correspond-elle a un dialogue (+Dialogue "
                        "Name) qui existe reellement ? 'End' et "
                        "'GotoAndReset' sont des mots-cles reserves, jamais "
                        "verifies comme reference.",
        description_en="Does each Next_N/OptionNext_N target (and its "
                        "optional param1) match a dialogue (+Dialogue Name) "
                        "that genuinely exists? 'End' and 'GotoAndReset' are "
                        "reserved keywords, never checked as a reference.",
        enabled_by_default=True,
        run=_check_dialogue_refs,
    ),
    CrossRefCheck(
        id="material_refs",
        label_fr="Materiaux (Material: defini dans MaterialConfig.ecf)",
        label_en="Materials (Material: defined in MaterialConfig.ecf)",
        description_fr="Chaque propriete 'Material:' d'un bloc correspond-elle "
                        "a un materiau defini dans MaterialConfig.ecf ? (vecu : "
                        "un bloc au materiau absent casse toute la table des "
                        "blocs au chargement)",
        description_en="Does each block 'Material:' property match a material "
                        "defined in MaterialConfig.ecf? (a block with a missing "
                        "material breaks the whole block table at load)",
        enabled_by_default=True,
        run=_check_material_refs,
    ),
    CrossRefCheck(
        id="pda_poi_refs",
        label_fr="POIs des missions PDA (spawn dans les playfields)",
        label_en="PDA mission POIs (spawn in playfields)",
        description_fr="Chaque POI cible d'une action de mission (NearPoi/"
                        "PoiDiscovered) correspond-il a un GroupName/Name/"
                        "Prefab des playfields du scenario ?",
        description_en="Does each mission action target POI (NearPoi/"
                        "PoiDiscovered) match a playfield GroupName/Name/"
                        "Prefab?",
        enabled_by_default=True,
        run=_check_pda_poi_refs,
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


# ============================================================================
# Propositions de correction pour les references de dialogues cassees
# (VERIF-006) -- analyse + application, utilises par l'interface
# ============================================================================

def collect_dialogue_names(ecf_files: List[Path]) -> List[str]:
    """Tous les Name des blocs +Dialogue des fichiers donnes, tries -- alimente
    la liste de choix de la fenetre de correction."""
    names: Set[str] = set()
    for path in ecf_files:
        try:
            doc = parse_ecf_file(path)
        except Exception:
            continue
        for block in doc.iter_blocks():
            if block.kind == '+Dialogue':
                name = block.get_property('Name')
                if name:
                    names.add(name)
    return sorted(names)


def closest_dialogue_name(value: str, names: List[str]) -> Optional[str]:
    """Le nom de dialogue existant le plus proche de la reference cassee
    (typo probable) -- None si rien ne se rapproche assez."""
    import difflib
    matches = difflib.get_close_matches(value, names, n=1, cutoff=0.75)
    return matches[0] if matches else None


def apply_dialogue_ref_fix(path: Path, source_identity: str, ref_key: str,
                           ref_value: str, new_value: Optional[str]) -> bool:
    """Applique la correction choisie SUR DISQUE (ecriture atomique) :
    - new_value = nom -> remplace la valeur de la reference cassee ;
    - new_value = None -> RETIRE la paire cassee (et la ligne entiere si elle
      ne contenait qu'elle).
    Retourne True si la modification a eu lieu."""
    from .parser import parse_ecf_file
    from .model import EcfProperty, block_identity
    from ..fsutil import atomic_write_text

    doc = parse_ecf_file(path)
    target = None
    for block in doc.iter_blocks():
        if block.kind == '+Dialogue' and block_identity(block) == source_identity:
            target = block
            break
    if target is None:
        # Repli (fichiers non canoniques ou identite '?' -- verif VERIF-006) :
        # le +Dialogue contenant EXACTEMENT cette paire (reference, valeur).
        candidates = []
        for block in doc.iter_blocks():
            if block.kind != '+Dialogue':
                continue
            for child in block.children:
                if isinstance(child, EcfProperty) and any(
                        k == ref_key and v == ref_value for k, v in child.pairs):
                    candidates.append(block)
                    break
        if len(candidates) == 1:
            target = candidates[0]
    if target is None:
        return False

    modified = False
    for child in list(target.children):
        if not isinstance(child, EcfProperty):
            continue
        if not any(k == ref_key and v == ref_value for k, v in child.pairs):
            continue
        if new_value is None and len(child.pairs) == 1:
            target.children.remove(child)
            modified = True
        else:
            new_pairs = []
            for k, v in child.pairs:
                if k == ref_key and v == ref_value:
                    if new_value is not None:
                        new_pairs.append((k, new_value))
                    modified = True
                    continue
                new_pairs.append((k, v))
            child.pairs = new_pairs
            child.dirty = True
    if not modified:
        return False
    atomic_write_text(path, doc.render())
    return True
