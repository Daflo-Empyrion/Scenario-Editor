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
from typing import Callable, Dict, List, Optional, Set

from core.yamllite.parser import parse_yaml_file
from .parser import parse_ecf_file_cached
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
            doc = parse_ecf_file_cached(path)
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
            doc = parse_ecf_file_cached(path)
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


def _collect_token_ids(path, token_ids: Set[str]) -> None:
    try:
        doc = parse_ecf_file_cached(path)
        for block in doc.iter_blocks():
            id_val = block.get_property('Id')
            if id_val:
                token_ids.add(id_val.strip().lstrip('0') or '0')
    except Exception:
        pass


def _check_token_refs(ctx: CrossRefContext) -> List[CrossRefIssue]:
    token_file = _find_file(ctx.ecf_files, 'TokenConfig.ecf')
    token_ids: Set[str] = set()
    if token_file is not None:
        _collect_token_ids(token_file, token_ids)
    # Le jeu charge la config VANILLA comme couche de base sous celle du
    # scenario : un Id defini la-bas existe en jeu meme sans redeclaration
    # (vecu 03/11/2026 : les CredTokens 100-113 etaient signales a tort).
    # Repli gracieux si le chemin du jeu n'est pas renseigne.
    from core.settings import get_vanilla_content_path
    content = get_vanilla_content_path()
    if content:
        _collect_token_ids(Path(content) / 'Configuration' / 'TokenConfig.ecf',
                           token_ids)

    issues: List[CrossRefIssue] = []
    for path in ctx.ecf_files:
        try:
            doc = parse_ecf_file_cached(path)
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


def _collect_dialogue_names(path, names: Set[str]) -> None:
    try:
        doc = parse_ecf_file_cached(path)
    except Exception:
        return
    for block in doc.iter_blocks():
        if block.kind == '+Dialogue':
            name = block.get_property('Name')
            if name:
                names.add(name)


def _check_dialogue_refs(ctx: CrossRefContext) -> List[CrossRefIssue]:
    dialogue_names: Set[str] = set()
    for path in ctx.ecf_files:
        _collect_dialogue_names(path, dialogue_names)
    # Le jeu charge la config VANILLA comme couche de base sous celle du
    # scenario : un dialogue defini la-bas existe en jeu meme sans
    # redeclaration (comme pour les jetons, vecu 03/11/2026). Repli
    # gracieux si le chemin du jeu n'est pas renseigne.
    from core.settings import get_vanilla_content_path
    content = get_vanilla_content_path()
    if content:
        _collect_dialogue_names(
            Path(content) / 'Configuration' / 'Dialogues.ecf', dialogue_names)

    issues: List[CrossRefIssue] = []
    for path in ctx.ecf_files:
        try:
            doc = parse_ecf_file_cached(path)
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

def _collect_material_names(path, defined: Set[str]) -> None:
    try:
        doc = parse_ecf_file_cached(path)
    except Exception:
        return
    for block in doc.iter_blocks():
        if block.kind.lstrip('+').rstrip(',').casefold() == 'material':
            name = block.get_property('Name')
            if name:
                defined.add(name)


def _check_material_refs(ctx: CrossRefContext) -> List[CrossRefIssue]:
    materials_file = _find_file(ctx.ecf_files, 'MaterialConfig.ecf')
    if materials_file is None:
        # Scenario sans MaterialConfig propre : les materiaux viennent du jeu
        # de base, on n'a rien a comparer localement.
        return []
    defined: Set[str] = set()
    try:
        doc = parse_ecf_file_cached(materials_file)
    except Exception:
        return []
    for block in doc.iter_blocks():
        if block.kind.lstrip('+').rstrip(',').casefold() == 'material':
            name = block.get_property('Name')
            if name:
                defined.add(name)
    # couche de base : un materiau defini dans la VANILLA existe en jeu meme
    # sans redeclaration du scenario (comme jetons et dialogues, vecu
    # 03/11/2026). Repli gracieux si le chemin du jeu n'est pas renseigne.
    from core.settings import get_vanilla_content_path
    content = get_vanilla_content_path()
    if content:
        _collect_material_names(
            Path(content) / 'Configuration' / 'MaterialConfig.ecf', defined)
    issues: List[CrossRefIssue] = []
    for path in ctx.ecf_files:
        if path == materials_file:
            continue
        if path.name == 'EClassConfig.ecf':
            # les ENTITES reference des archetypes de materiau INTERNES AU
            # MOTEUR (HumanSoft, CreatureSoft, Mechanical, DronePlanet,
            # Player...) : AUCUN MaterialConfig ne les definit — ni vanilla
            # (37 materiaux de terrain/blocs), ni RE2, ni ATL ; RE2 les
            # reference sans les definir depuis toujours (vecu 03/11/2026 :
            # 146 faux positifs). L'incident du 04/10 concernait les BLOCS
            # (BlocksConfig -> table morte + NRE) : on ne verifie que la.
            continue
        try:
            doc = parse_ecf_file_cached(path)
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


_PREFAB_DISPLAY_CACHE: Dict[str, tuple] = {}


def _prefab_display_names(scenario_root) -> Set[str]:
    """Noms d'AFFICHAGE des prefabs du scenario (propriete 16 de l'en-tete).

    Un `NearPoi:` du PDA peut viser ce nom et non un nom de playfield :
    `Ship Landing Site` est le DisplayName de R2BA_FreighterStory.epb et
    fonctionne en jeu (signale par l'utilisateur le 03/11/2026, verifie sur
    la source RE2). Cache memoire par signature du dossier (nombre + mtime)."""
    prefabs = Path(scenario_root) / "Prefabs"
    if not prefabs.is_dir():
        return set()
    files = sorted(prefabs.glob("*.epb"))
    sig = (len(files), max((f.stat().st_mtime_ns for f in files), default=0))
    cached = _PREFAB_DISPLAY_CACHE.get(str(prefabs))
    if cached is not None and cached[0] == sig:
        return cached[1]
    from core.epb_blueprint import read_display_name
    names: Set[str] = set()
    for f in files:
        try:
            name = read_display_name(f)
        except Exception:
            continue
        if name:
            names.add(name.casefold())
    _PREFAB_DISPLAY_CACHE[str(prefabs)] = (sig, names)
    return names


_PREFAB_ENTITY_CACHE: Dict[str, tuple] = {}


def _prefab_entity_names(scenario_root) -> Set[str]:
    """Noms d'ENTITES (crew/NPC) lus dans les en-tetes des .epb.

    Un `NearPoi:` du PDA peut viser une entite et non un POI de playfield :
    `Security Manager` est un NPC d'un prefab (confirme par l'utilisateur
    le 03/11/2026). Extraction sur le seul header (cf.
    `core.epb_blueprint.read_entity_names`), mise en cache disque
    (`~/.empyrion_editor/cache/prefab_entities.json`) car le scan de 5 800
    prefabs coute quelques dizaines de secondes."""
    import json
    prefabs = Path(scenario_root) / "Prefabs"
    if not prefabs.is_dir():
        return set()
    files = sorted(prefabs.glob("*.epb"))
    sig = [len(files), max((f.stat().st_mtime_ns for f in files), default=0)]
    cache = Path.home() / ".empyrion_editor" / "cache" / "prefab_entities.json"
    cached = _PREFAB_ENTITY_CACHE.get(str(prefabs))
    if cached is not None and cached[0] == sig:
        return cached[1]
    if cache.is_file():
        try:
            raw = json.loads(cache.read_text(encoding="utf-8"))
            if raw.get("sig") == sig:
                names = set(raw.get("names", []))
                _PREFAB_ENTITY_CACHE[str(prefabs)] = (sig, names)
                return names
        except (OSError, ValueError):
            pass
    from core.epb_blueprint import read_entity_names
    names: Set[str] = set()
    for f in files:
        names |= read_entity_names(f)
    folded = {n.casefold() for n in names}
    _PREFAB_ENTITY_CACHE[str(prefabs)] = (sig, folded)
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"sig": sig, "names": sorted(folded)}),
                         encoding="utf-8")
    except OSError:
        pass
    return folded


def collect_pda_poi_pool(scenario_root):
    """(noms exacts, chaines d'affichage) des POI des playfields — le pool du
    check pda_poi_refs, repris tel quel par la fenetre de correction pour
    suggerer les cibles existantes (GroupName, Name, Prefab, PrefabName,
    DisplayName, a toute profondeur, crochets retires), PLUS les noms
    d'affichage des prefabs (DisplayName de l'en-tete .epb)."""
    pool_exact: Set[str] = set()
    display_pool: List[str] = []
    pf_dir = Path(scenario_root) / 'Playfields'
    for f in sorted(pf_dir.rglob('*.yaml')) if pf_dir.is_dir() else []:
        try:
            pf_doc = parse_yaml_file(f)
        except Exception:
            continue

        def collect(nodes):
            for node in nodes:
                k = getattr(node, 'key', None)
                if k not in ('GroupName', 'Name', 'Prefab', 'PrefabName',
                             'DisplayName'):
                    collect(getattr(node, 'children', None) or [])
                    continue
                # noms composes : le PDA peut cible une sous-chaine du
                # nom affiche (vecu 03/11 : NearPoi 'Kenex Station 62'
                # vs DisplayName 'Kenex 62 Kenex Station 62') ; les valeurs
                # peuvent etre bracketees 'Name: [X]' (le parseur yamllite
                # rend alors les items en enfants) ou en liste '[A, B]'
                values = []
                v = (getattr(node, 'value', '') or '').strip()
                if v:
                    values.append(v)
                for ch in getattr(node, 'children', None) or []:
                    cv = (getattr(ch, 'value', '') or '').strip()
                    if cv:
                        values.append(cv)
                for raw in values:
                    val = raw.strip("'\"[] ")
                    if not val:
                        continue
                    pool_exact.add(val.casefold())
                    # convention RE2/ATL : le GroupName d'un POI = stem du
                    # blueprint + suffixe (RG, Story...) et le nom VISIBLE
                    # en jeu vient du blueprint — le PDA vise le stem
                    # (vecu 03/11 : NearPoi 'FarrTemplePrime' vs GroupName
                    # 'FarrTemplePrimeRG') ; sous-chaine acceptee pour
                    # GroupName/Name/DisplayName
                    if k in ('GroupName', 'Name', 'DisplayName'):
                        display_pool.append(val.casefold())
                    if k == 'PrefabName':
                        pool_exact.add(Path(val).stem.casefold())
                collect(getattr(node, 'children', None) or [])
        collect(pf_doc.nodes)
    # noms affiches des prefabs : le PDA les vise directement
    # (`NearPoi: Ship Landing Site` = DisplayName de R2BA_FreighterStory.epb)
    pool_exact |= _prefab_display_names(scenario_root)
    # entites internes des prefabs : un NearPoi peut viser un NPC
    # (`Security Manager`), qui n'existe dans aucun playfield
    pool_exact |= _prefab_entity_names(scenario_root)
    return pool_exact, display_pool


def _check_pda_poi_refs(ctx: CrossRefContext) -> List[CrossRefIssue]:
    """Chaque POI cible par une action de mission du PDA.yaml
    (Check: NearPoi / PoiDiscovered, propriete Names) doit correspondre a
    un POI spawnable dans les playfields du scenario. Collecte GENEREUSE du
    pool pour minimiser les faux positifs (vecu 03/11/2026 : 15 cibles
    legitimes ratees) : GroupName/Name/Prefab/PrefabName/DisplayName a toute
    profondeur de Playfields/, crochets retires (Name: [X]), et sous-chaine
    des Name/DisplayName (NearPoi 'Kenex Station 62' vs DisplayName
    'Kenex 62 Kenex Station 62') ; les noms avec joker '*' sont ignores.
    Scenario sans PDA.yaml ou sans Playfields -> rien a verifier."""
    if ctx.scenario_root is None:
        return []
    pda_path = Path(ctx.scenario_root) / 'Extras' / 'PDA' / 'PDA.yaml'
    if not pda_path.is_file():
        return []
    try:
        pda_doc = parse_yaml_file(pda_path)
    except Exception:
        return []

    pool_exact, display_pool = collect_pda_poi_pool(ctx.scenario_root)

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
                        cf = nm.casefold()
                        if cf in pool_exact or any(cf in d for d in display_pool):
                            continue
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


def apply_pda_poi_fix(path: Path, action_title: str, check_key: str,
                      old_value: str, new_value: Optional[str]) -> bool:
    """Repare une cible POI du PDA SUR DISQUE (ecriture atomique, parse SANS
    cache — fonction mutatrice, meme regle qu'apply_dialogue_ref_fix) :
    - new_value = nom -> remplace l'item vise dans la liste Names de l'action
      'action_title' dont le Check est 'check_key' ;
    - new_value = None -> RETIRE l'item de la liste (l'etape ne pourra plus
      jamais se declencher : c'est assume, la fenetre previent).
    Retourne True si la modification a eu lieu."""
    from core.yamllite.model import remove_entry
    from ..fsutil import atomic_write_text

    doc = parse_yaml_file(path)
    target = None

    def find(nodes):
        nonlocal target
        for node in nodes:
            k = getattr(node, 'key', None)
            if (k == 'ActionTitle'
                    and (getattr(node, 'value', '') or '').strip() == action_title):
                # ref_key porte la VALEUR du Check ('NearPoi'), pas la cle
                # du noeud ('Check') : retrouver Names + valider le Check
                names_entry = has_check = None
                for ch in getattr(node, 'children', None) or []:
                    ck = getattr(ch, 'key', None)
                    if ck == 'Names':
                        names_entry = ch
                    elif ck == 'Check' and (getattr(ch, 'value', '') or '').strip() == check_key:
                        has_check = ch
                if has_check is not None and names_entry is not None:
                    for item in getattr(names_entry, 'children', None) or []:
                        v = (getattr(item, 'value', '') or '').strip().strip("'\"")
                        if v == old_value:
                            target = (names_entry, item)
                            return
            if target is None:
                find(getattr(node, 'children', None) or [])
    find(doc.nodes)
    if target is None:
        return False
    names_entry, item = target
    if new_value is None:
        if not remove_entry(names_entry.children, item):
            return False
    else:
        item.set_own_value(new_value)
    atomic_write_text(path, doc.render())
    return True


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
            doc = parse_ecf_file_cached(path)
        except Exception:
            continue
        for block in doc.iter_blocks():
            if block.kind == '+Dialogue':
                name = block.get_property('Name')
                if name:
                    names.add(name)
    return sorted(names)


def collect_dialogue_stats(ecf_files: List[Path]) -> Dict[str, dict]:
    """Par nom de dialogue du scenario : combien de references Next/OptionNext
    le pointent, et s'il est terminal (aucune branche : affiche un texte puis
    se termine). Indicateur de coherence affiche par la fenetre de correction :
    remplacer par un dialogue terminal = l'echange s'arrete la ; remplacer par
    un dialogue pointe ailleurs = un chemin deja parcouru par le scenario."""
    stats: Dict[str, dict] = {}
    for path in ecf_files:
        try:
            doc = parse_ecf_file_cached(path)
        except Exception:
            continue
        # passe 1 : les noms definis (une reference peut pointer vers un
        # dialogue declare PLUS LOIN dans le fichier)
        for block in doc.iter_blocks():
            if block.kind == '+Dialogue':
                name = block.get_property('Name')
                if name:
                    stats.setdefault(name, {"refs": 0, "terminal": True})
        # passe 2 : les branches et les references qu'elles portent
        for block in doc.iter_blocks():
            if block.kind != '+Dialogue':
                continue
            name = block.get_property('Name')
            if not name:
                continue
            info = stats[name]
            for child in block.children:
                if not isinstance(child, EcfProperty):
                    continue
                has_ref = False
                for k, v in child.pairs:
                    if (k and v and _DIALOGUE_REF_KEY_PATTERN.match(k)
                            and not v.startswith('@') and v in stats):
                        stats[v]["refs"] += 1
                        has_ref = True
                if has_ref:
                    info["terminal"] = False
    return stats


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
    - new_value = None -> RETIRE la reference (et la ligne entiere si elle ne
      contenait qu'elle) ; pour une OptionNext_N, retire aussi l'option du
      menu NPC (Option_N/OptionIf_N...) — sinon le PNJ garderait un bouton
      sans cible.
    Retourne True si la modification a eu lieu (fonction MUTATRICE : parse
    SANS cache — un echec d'ecriture laisserait sinon un doc modifie en
    cache, divergent du disque)."""
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

    m_option = None if new_value is not None else re.fullmatch(
        r"OptionNext_(\d+)", ref_key)
    m_next = None if new_value is not None else re.fullmatch(
        r"Next_(\d+)", ref_key)
    modified = False
    for child in list(target.children):
        if not isinstance(child, EcfProperty):
            continue
        if not any(k == ref_key and v == ref_value for k, v in child.pairs):
            continue
        if new_value is None:
            # suppression : on retire la paire cassee ; une ligne qui ne
            # contient plus que des param1 (orphelins sans leur reference,
            # ex: 'OptionNext_2: X, param1: GotoAndReset') saute entiere
            new_pairs = [(k, v) for k, v in child.pairs
                         if not (k == ref_key and v == ref_value)]
            modified = True
            if new_pairs and all(k == "param1" for k, _ in new_pairs):
                new_pairs = []
            if new_pairs:
                child.pairs = new_pairs
                child.dirty = True
            else:
                target.children.remove(child)
        else:
            new_pairs = []
            for k, v in child.pairs:
                if k == ref_key and v == ref_value:
                    new_pairs.append((k, new_value))
                    modified = True
                    continue
                new_pairs.append((k, v))
            child.pairs = new_pairs
            child.dirty = True
    if m_option:
        # l'option du menu NPC va avec sa cible : retirer aussi son texte
        # (Option_N), sa condition (OptionIf_N) etc., sinon le PNJ garderait
        # un bouton mort. Les cles de localisation restent dans
        # Localization.csv (sans effet).
        for child in list(target.children):
            if not isinstance(child, EcfProperty):
                continue
            if any(k and re.fullmatch(rf"Option(?!Next).*_{m_option.group(1)}", k)
                   for k, _ in child.pairs):
                target.children.remove(child)
                modified = True
    if m_next:
        # la condition NextIf_N va avec sa branche Next_N : orpheline sans
        # elle, elle ne signifierait plus rien pour le moteur
        for child in list(target.children):
            if not isinstance(child, EcfProperty):
                continue
            if any(k and k == f"NextIf_{m_next.group(1)}"
                   for k, _ in child.pairs):
                target.children.remove(child)
                modified = True
    if not modified:
        return False
    atomic_write_text(path, doc.render())
    return True
