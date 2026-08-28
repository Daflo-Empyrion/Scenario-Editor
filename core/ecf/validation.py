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
Validation des regles metier/valeurs pour les fichiers ECF -- complementaire a
core/ecf/dependency_check.py (heritage Ref) et core/ecf/cross_reference_check.py
(references croisees entre fichiers), qui restent les endroits ou verifier
l'EXISTENCE d'une reference. Ce module-ci verifie des VALEURS et des DOUBLONS,
pas des references.

Chaque regle est fondee sur des donnees reelles ou une source officielle
verifiee -- jamais une supposition. Voir le commentaire de chaque regle pour
sa source. Toute regle qui n'a pas pu etre confirmee (plage d'Id "terrain"
0-255, valeurs "Mode" de playfield, format strict de jeton) a ete
volontairement ECARTEE plutot que devinee.
"""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

from .model import EcfBlock, EcfProperty


@dataclass
class ValidationIssue:
    """Un probleme detecte lors de la validation."""
    code: str                    # ex: 'E001', 'W003'
    level: str                   # 'error' | 'warning'
    block: Optional[EcfBlock] = None
    property_key: Optional[str] = None
    message: str = ""
    file_path: Optional[Path] = None

    def label(self) -> str:
        block_id = ''
        if self.block is not None:
            ident = self.block.get('Id') or self.block.get_property('Name') or ''
            block_id = f"[{self.block.kind} {ident}]".strip()
        prop = f" {self.property_key}" if self.property_key else ''
        loc = f" ({self.file_path.name})" if self.file_path else ''
        return f"{self.code} {self.level.upper():7} {block_id}{prop}: {self.message}{loc}"


# ============================================================================
# Constantes de reference -- chacune verifiee, source indiquee en commentaire
# ============================================================================

# Limite reelle actuelle du jeu, CONFIRMEE via les notes de mise a jour
# officielles Eleon (v1.17) sur plusieurs sources independantes
# (forum.empyrion-homeworld.net, empyriononline.com, Steam Community) :
# "Increased max. possible BlockIDs from 4096 to 8192". La valeur de 2048
# parfois citee est une limite historique depassee depuis longtemps (la limite
# etait meme passee par 4096 avant d'atteindre 8192).
MAX_BLOCK_ID = 8192

# Classes de blocs qui necessitent VolumeCapacity -- verifie sur un vrai
# BlocksConfig.ecf (59/62 blocs de ces classes en ont un, les 3 exceptions
# heritent via Ref: ou sont un cas isole non-Ref). Volontairement PLUS
# RESTREINT que la liste initialement proposee : 'Constructor' seul n'existe
# pas comme classe reelle (seulement des variantes ConstructorBig/Hover/
# Survival/etc., dont la GRANDE majorite n'ont PAS VolumeCapacity -- exclues
# pour eviter un flot de faux positifs) ; 'FieldRepairStation' et
# 'ContainerAmmo' egalement exclues (0/1 verifie pour la premiere, la seconde
# n'existe meme pas comme classe reelle).
CONTAINER_CLASSES = {
    'Container', 'ContainerPersonal', 'ContainerController', 'ContainerExtension',
    'ArmorLocker', 'WarpDriveTank', 'RepairStation',
}

# Proprietes de type liste dont la valeur DOIT etre entre guillemets si elle
# contient une virgule (sinon la virgule est interpretee comme un separateur
# de propriete suivante) -- confirme sur un vrai BlocksConfig.ecf pour
# AllowPlacingAt et ChildBlocks specifiquement (les 4 autres proprietes
# initialement suggerees -- FactionTerritory, AllowedInBiomes, UnlockTech,
# RequiredTech -- introuvables sur l'ensemble des fichiers reels disponibles,
# ecartees plutot que devinees).
LIST_PROPERTIES = {'AllowPlacingAt', 'ChildBlocks'}

# Materiaux reellement observes dans un vrai BlocksConfig.ecf -- remplace
# integralement la liste de 10 materiaux generiques initialement proposee
# (qui ne correspondait a presque aucun materiau reel, casse differente en
# plus). Cette liste vient directement de l'extraction du vrai fichier, pas
# d'une supposition -- mais reste marquee comme non garantie exhaustive (un
# scenario personnalise pourrait en definir d'autres), d'ou le niveau
# 'warning' plutot que 'error'.
# 'edenvoidiumt2' ajoute suite a un faux positif signale par l'utilisateur --
# la serie de paliers edenvoidium/edenvoidiumt deja confirmee suggerait
# fortement une suite (t2, peut-etre t3...), mais seul t2 a ete confirme
# reellement present dans un scenario ; pas d'autre palier ajoute sans
# confirmation, pour ne pas retomber dans la supposition ecartee ci-dessus.
VALID_MATERIALS = {
    'BossLegacy', 'BossMetal', 'CarbonLarge', 'CarbonSmall', 'CombatLarge',
    'CombatSmall', 'Concrete', 'ConcreteArmored', 'Device', 'Foundation',
    'Human', 'Hydroponics', 'Legacy', 'SteelLarge', 'SteelSmall', 'Thruster',
    'TitaniumLarge', 'TitaniumSmall', 'WeaponLarge', 'WeaponPlanet',
    'WeaponSmall', 'Wood', 'Xenosteel', 'air', 'bedrock', 'dirt', 'edenadmin',
    'edenice', 'edenrich', 'edenvoidium', 'edenvoidiumt', 'edenvoidiumt2',
    'forcefield', 'grass', 'lava', 'plants', 'resourcehard', 'resourcemedium',
    'resourcesoft', 'rock', 'sand', 'snow', 'stone', 'tree', 'water',
}

# Valeurs de HoldType reellement observees dans un vrai ItemsConfig.ecf --
# remplace la liste {0, 14, 15} initialement proposee (incomplete : 4 autres
# valeurs reelles trouvees, avec des occurrences significatives sauf 2).
VALID_HOLD_TYPES = {0, 6, 14, 15, 16, 17, 20}

# Format BlockColor confirme sur 787 valeurs reelles : "R,G,B" (782 cas) ou
# "R,G,B,A" avec canal alpha (5 cas) -- jamais un autre nombre de composantes,
# chaque composante toujours dans [0,255]. Le "0-255" mentionne dans une
# regle initialement proposee pour les Id etait probablement une confusion
# avec CE format-ci (RGB/RGBA), pas les identifiants de bloc.
_BLOCKCOLOR_PATTERN = re.compile(r'^"?(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*(\d+))?"?$')


# ============================================================================
# API principale
# ============================================================================

def validate_document(doc, file_path: Optional[Path] = None) -> List[ValidationIssue]:
    """Valide un document ECF complet (descend dans les sous-blocs).

    Certaines regles (Material, VolumeCapacity des conteneurs, doublons de
    Name) ne sont fiables que dans le contexte precis ou elles ont ete
    verifiees (BlocksConfig.ecf) -- appliquees telles quelles a d'autres
    fichiers (EClassConfig.ecf, FactionWarfare.ecf, GalaxyConfig.ecf...), 234
    faux positifs sont apparus sur un vrai jeu de fichiers reels : 'Material'
    et 'Class: Container' y designent des concepts differents (entites/
    creatures, pas des blocs de construction), et 'Name' y sert couramment
    d'etiquette de categorie repetee plutot que d'identifiant unique. Ces
    regles sont donc desormais restreintes au fichier ou elles sont
    confirmees fiables -- voir _is_blocks_config_file()."""
    issues: List[ValidationIssue] = []

    all_blocks = list(_iter_all_blocks(doc.nodes))
    blocks_scoped = _is_blocks_config_file(file_path)
    items_scoped = _is_items_config_file(file_path)

    name_index: Dict[str, EcfBlock] = {}
    for block in all_blocks:
        name = block.get_property('Name') or block.get('Name')
        if name and name not in name_index:
            name_index[name] = block

    issues.extend(_check_duplicates(all_blocks, check_name_duplicates=blocks_scoped))

    for block in all_blocks:
        issues.extend(validate_block(block, name_index=name_index,
                                      blocks_scoped=blocks_scoped, items_scoped=items_scoped))

    for issue in issues:
        issue.file_path = file_path
    return issues


def validate_file(path: Path) -> List[ValidationIssue]:
    """Valide un fichier ECF unique."""
    from .parser import parse_ecf_file
    try:
        doc = parse_ecf_file(path)
    except Exception as e:
        return [ValidationIssue(code='E000', level='error',
                                 message=f"Impossible de parser le fichier : {e}",
                                 file_path=path)]
    return validate_document(doc, file_path=path)


def validate_scenario(root: Path) -> Dict[Path, List[ValidationIssue]]:
    """Valide tous les fichiers .ecf de Content/Configuration d'un scenario.
    Retourne un dict {chemin: [issues]} (seuls les fichiers avec des issues)."""
    config_dir = root / 'Content' / 'Configuration'
    if not config_dir.exists():
        config_dir = root
    results: Dict[Path, List[ValidationIssue]] = {}
    for ecf in sorted(config_dir.glob('*.ecf')):
        issues = validate_file(ecf)
        if issues:
            results[ecf] = issues
    return results


def validate_block(block: EcfBlock, name_index: Optional[Dict[str, EcfBlock]] = None,
                    blocks_scoped: bool = True, items_scoped: bool = True) -> List[ValidationIssue]:
    """Valide un bloc ECF unique (hors doublons, verifies au niveau document).
    blocks_scoped=False desactive Material/VolumeCapacity (fiables uniquement
    sur BlocksConfig.ecf) ; items_scoped=False desactive HoldType (fiable
    uniquement sur ItemsConfig.ecf) -- voir _is_blocks_config_file/
    _is_items_config_file.

    Parcourt le REGISTRE de regles (_BLOCK_RULES, voir plus bas) plutot que
    d'appeler chaque _check_* en dur ici -- ajouter une regle se fait
    desormais en l'ajoutant au registre, sans toucher a cette fonction."""
    issues: List[ValidationIssue] = []
    context = {'name_index': name_index or {}, 'blocks_scoped': blocks_scoped, 'items_scoped': items_scoped}
    for rule in _BLOCK_RULES:
        if rule.applies(context):
            issues.extend(rule.run(block, context))
    return issues


# ============================================================================
# Helpers internes
# ============================================================================

def _iter_all_blocks(nodes):
    for node in nodes:
        if isinstance(node, EcfBlock):
            yield node
            yield from _iter_all_blocks(node.children)


def _is_blocks_config_file(file_path: Optional[Path]) -> bool:
    """True si ce fichier est bien BlocksConfig.ecf -- seul fichier ou les
    regles Material/VolumeCapacity/doublons-de-Name ont ete verifiees contre
    de vraies donnees. Si file_path est None (validation directe d'un
    document sans fichier associe, ex: tests), applique ces regles par
    defaut plutot que de les desactiver silencieusement."""
    if file_path is None:
        return True
    return file_path.name == 'BlocksConfig.ecf'


def _is_items_config_file(file_path: Optional[Path]) -> bool:
    """True si ce fichier est bien ItemsConfig.ecf -- seul fichier ou la
    regle HoldType a ete verifiee contre de vraies donnees."""
    if file_path is None:
        return True
    return file_path.name == 'ItemsConfig.ecf'


def _resolve_ref_chain(block: EcfBlock, name_index: Dict[str, EcfBlock],
                        max_depth: int = 10) -> List[EcfBlock]:
    """Suit la chaine Ref: d'un bloc (ex: A Ref: B, B Ref: C) et retourne la
    liste des blocs ancetres, dans l'ordre. S'arrete a max_depth pour se
    proteger d'une chaine circulaire malformee."""
    chain = []
    seen = set()
    current = block
    for _ in range(max_depth):
        ref_name = current.get_property('Ref')
        if not ref_name or ref_name in seen:
            break
        seen.add(ref_name)
        parent = name_index.get(ref_name)
        if parent is None:
            break
        chain.append(parent)
        current = parent
    return chain


# ============================================================================
# Regles au niveau du document
# ============================================================================

def _check_duplicates(all_blocks: List[EcfBlock], check_name_duplicates: bool = True) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    seen_ids: Dict[str, EcfBlock] = {}
    seen_names: Dict[str, EcfBlock] = {}

    for block in all_blocks:
        id_val = block.get('Id')
        name_val = block.get_property('Name') or block.get('Name')

        if id_val is not None:
            if id_val in seen_ids:
                issues.append(ValidationIssue(
                    code='E003', level='error', block=block, property_key='Id',
                    message=f"Id {id_val} duplique (deja utilise par un autre bloc)."))
            else:
                seen_ids[id_val] = block

        if check_name_duplicates and name_val and id_val is None:
            if name_val in seen_names:
                issues.append(ValidationIssue(
                    code='W002', level='warning', block=block, property_key='Name',
                    message=f"Name '{name_val}' duplique (sans Id pour le distinguer)."))
            else:
                seen_names[name_val] = block

    return issues


# ============================================================================
# Regles au niveau du bloc
# ============================================================================

def _check_id(block: EcfBlock) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    id_value = block.get('Id')
    if id_value is None:
        return issues
    try:
        id_num = int(id_value)
    except ValueError:
        issues.append(ValidationIssue(
            code='E002', level='error', block=block, property_key='Id',
            message=f"Id '{id_value}' n'est pas un nombre entier."))
        return issues
    if id_num >= MAX_BLOCK_ID:
        issues.append(ValidationIssue(
            code='E001', level='error', block=block, property_key='Id',
            message=f"Id {id_num} >= {MAX_BLOCK_ID} (limite reelle du jeu depuis la v1.17)."))
    return issues


def _check_container_volume(block: EcfBlock, name_index: Dict[str, EcfBlock]) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    class_value = block.get_property('Class')
    if not class_value or class_value not in CONTAINER_CLASSES:
        return issues
    if block.get_property('VolumeCapacity') is not None:
        return issues
    # Suit la chaine Ref: -- VolumeCapacity peut etre herite d'un bloc parent
    for ancestor in _resolve_ref_chain(block, name_index):
        if ancestor.get_property('VolumeCapacity') is not None:
            return issues
    issues.append(ValidationIssue(
        code='E005', level='error', block=block, property_key='VolumeCapacity',
        message=f"La classe '{class_value}' necessite VolumeCapacity (absent, y compris via Ref:)."))
    return issues


def _check_unquoted_commas(block: EcfBlock) -> List[ValidationIssue]:
    """Detecte les virgules non protegees dans une propriete-liste. Le
    parseur ECF scinde deja 'AllowPlacingAt: Base,MS' en deux paires
    distinctes des l'analyse ('AllowPlacingAt': 'Base') puis (None: 'MS') --
    confirme directement sur notre propre parseur. La signature a detecter
    n'est donc pas une virgule DANS une valeur, mais une paire LIST_PROPERTIES
    immediatement suivie sur la meme ligne d'une paire "orpheline" (cle=None)."""
    issues: List[ValidationIssue] = []
    for child in block.children:
        if not isinstance(child, EcfProperty):
            continue
        for i, (key, value) in enumerate(child.pairs):
            if key not in LIST_PROPERTIES or value is None:
                continue
            stripped = value.strip()
            if stripped.startswith('"') and stripped.endswith('"'):
                continue
            if i + 1 < len(child.pairs) and child.pairs[i + 1][0] is None:
                orphan_value = child.pairs[i + 1][1]
                issues.append(ValidationIssue(
                    code='E004', level='error', block=block, property_key=key,
                    message=(f"Virgule non protegee : '{stripped},{orphan_value}' scinde "
                             f"en deux -- ecrire {key}: \"...\" entre guillemets.")))
    return issues


def _check_material(block: EcfBlock) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    material = block.get_property('Material')
    if material and material not in VALID_MATERIALS:
        issues.append(ValidationIssue(
            code='W007', level='warning', block=block, property_key='Material',
            message=f"Materiau '{material}' non reconnu (peut-etre specifique a ce scenario)."))
    return issues


def _check_hold_type(block: EcfBlock) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    hold_type = block.get_property('HoldType')
    if hold_type is not None:
        try:
            if int(hold_type) not in VALID_HOLD_TYPES:
                issues.append(ValidationIssue(
                    code='W008', level='warning', block=block, property_key='HoldType',
                    message=f"HoldType {hold_type} non reconnu."))
        except ValueError:
            pass
    return issues


def _check_block_color(block: EcfBlock) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    color = block.get_property('BlockColor')
    if color is None:
        return issues
    m = _BLOCKCOLOR_PATTERN.match(color.strip())
    if not m:
        issues.append(ValidationIssue(
            code='W009', level='warning', block=block, property_key='BlockColor',
            message=f"BlockColor '{color}' hors format attendu (\"R,G,B\" ou \"R,G,B,A\")."))
        return issues
    values = [int(g) for g in m.groups() if g is not None]
    if any(v < 0 or v > 255 for v in values):
        issues.append(ValidationIssue(
            code='W009', level='warning', block=block, property_key='BlockColor',
            message=f"BlockColor '{color}' : composante(s) hors plage [0, 255]."))
    return issues


def _check_custom_icon(block: EcfBlock) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    custom_icon = block.get_property('CustomIcon')
    if custom_icon is not None and not custom_icon.strip().strip('"'):
        issues.append(ValidationIssue(
            code='W006', level='warning', block=block, property_key='CustomIcon',
            message="CustomIcon est vide."))
    return issues


def _check_hitpoints(block: EcfBlock) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    hp = block.get_property('HitPoints')
    if hp is not None:
        try:
            if int(hp) <= 0:
                issues.append(ValidationIssue(
                    code='W005', level='warning', block=block, property_key='HitPoints',
                    message=f"HitPoints {hp} <= 0."))
        except ValueError:
            pass
    return issues


def _check_mass(block: EcfBlock) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    mass = block.get_property('Mass')
    if mass is not None:
        try:
            if float(mass) < 0:
                issues.append(ValidationIssue(
                    code='W010', level='warning', block=block, property_key='Mass',
                    message=f"Mass {mass} negative."))
        except ValueError:
            pass
    return issues


def _check_maxcount(block: EcfBlock) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    maxcount = block.get_property('MaxCount')
    if maxcount is not None:
        try:
            if int(maxcount) <= 0:
                issues.append(ValidationIssue(
                    code='W011', level='warning', block=block, property_key='MaxCount',
                    message=f"MaxCount {maxcount} <= 0 (bloc/item jamais placable)."))
        except ValueError:
            pass
    return issues


# ============================================================================
# Registre de regles -- une entree par regle, avec sa condition d'application
# (voir validate_block ci-dessus, qui parcourt ce registre au lieu d'appeler
# chaque _check_* en dur). Ajouter une regle : ecrire une fonction _check_*
# puis l'enregistrer ici, sans toucher a validate_block.
# ============================================================================

@dataclass
class _BlockRule:
    name: str
    check_fn: object          # Callable[[EcfBlock, dict], List[ValidationIssue]]
    condition: object = None  # Callable[[dict], bool] ou None (= toujours applicable)

    def applies(self, context: dict) -> bool:
        return self.condition is None or self.condition(context)

    def run(self, block: EcfBlock, context: dict) -> List[ValidationIssue]:
        return self.check_fn(block, context)


_BLOCK_RULES: List[_BlockRule] = [
    _BlockRule('id', lambda block, ctx: _check_id(block)),
    _BlockRule('unquoted_commas', lambda block, ctx: _check_unquoted_commas(block)),
    _BlockRule('block_color', lambda block, ctx: _check_block_color(block)),
    _BlockRule('custom_icon', lambda block, ctx: _check_custom_icon(block)),
    _BlockRule('hitpoints', lambda block, ctx: _check_hitpoints(block)),
    _BlockRule('mass', lambda block, ctx: _check_mass(block)),
    _BlockRule('maxcount', lambda block, ctx: _check_maxcount(block)),
    _BlockRule('container_volume', lambda block, ctx: _check_container_volume(block, ctx['name_index']),
                condition=lambda ctx: ctx['blocks_scoped']),
    _BlockRule('material', lambda block, ctx: _check_material(block),
                condition=lambda ctx: ctx['blocks_scoped']),
    _BlockRule('hold_type', lambda block, ctx: _check_hold_type(block),
                condition=lambda ctx: ctx['items_scoped']),
]
