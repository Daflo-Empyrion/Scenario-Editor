"""
Tests du module de validation des regles metier ECF (core/ecf/validation.py).

Chaque regle est fondee sur une verification directe contre de vrais fichiers
du jeu (BlocksConfig.ecf, ItemsConfig.ecf) ou une source officielle (notes de
mise a jour Eleon) -- jamais une supposition. Voir les commentaires du module
lui-meme pour le detail de chaque source.
"""
from pathlib import Path

import pytest

from core.ecf.parser import parse_ecf_text
from core.ecf.validation import validate_document, MAX_BLOCK_ID


def _issues_with_code(issues, code):
    return [i for i in issues if i.code == code]


# ============================================================================
# E001 -- limite d'Id (8192, confirme via les notes de mise a jour Eleon v1.17)
# ============================================================================

def test_id_below_limit_is_valid():
    doc = parse_ecf_text("{ Block Id: 300\n  Name: TestBlock\n}\n")
    issues = validate_document(doc)
    assert len(_issues_with_code(issues, 'E001')) == 0


def test_id_at_or_above_limit_is_error():
    doc = parse_ecf_text(f"{{ Block Id: {MAX_BLOCK_ID}\n  Name: TestBlock\n}}\n")
    issues = validate_document(doc)
    e001 = _issues_with_code(issues, 'E001')
    assert len(e001) == 1
    assert '8192' in e001[0].message


def test_block_without_id_is_valid():
    """Un bloc sans Id du tout (identifie par Name seul) ne doit jamais
    declencher les regles liees a l'Id."""
    doc = parse_ecf_text("{ Block Name: LegacyForcefield\n  Material: Legacy\n}\n")
    issues = validate_document(doc)
    assert len(_issues_with_code(issues, 'E001')) == 0
    assert len(_issues_with_code(issues, 'E002')) == 0


def test_non_numeric_id_is_error():
    doc = parse_ecf_text("{ Block Id: abc\n  Name: TestBlock\n}\n")
    issues = validate_document(doc)
    assert len(_issues_with_code(issues, 'E002')) == 1


# ============================================================================
# E003/W002 -- doublons
# ============================================================================

def test_duplicate_id_is_error():
    text = "{ Block Id: 300\n  Name: BlockOne\n}\n{ Block Id: 300\n  Name: BlockTwo\n}\n"
    doc = parse_ecf_text(text)
    issues = validate_document(doc)
    assert len(_issues_with_code(issues, 'E003')) == 1


def test_duplicate_name_without_id_is_warning():
    text = "{ Block Name: SameName\n}\n{ Block Name: SameName\n}\n"
    doc = parse_ecf_text(text)
    issues = validate_document(doc)
    assert len(_issues_with_code(issues, 'W002')) == 1


def test_same_name_with_different_ids_is_not_flagged():
    """Deux blocs peuvent partager un Name si distingues par un Id different
    -- ne doit jamais etre traite comme un doublon de Name."""
    text = "{ Block Id: 1\n  Name: SameName\n}\n{ Block Id: 2\n  Name: SameName\n}\n"
    doc = parse_ecf_text(text)
    issues = validate_document(doc)
    assert len(_issues_with_code(issues, 'W002')) == 0


# ============================================================================
# E004 -- virgules non protegees (AllowPlacingAt/ChildBlocks, confirme sur un
# vrai BlocksConfig.ecf)
# ============================================================================

def test_unquoted_comma_in_allowplacingat_is_error():
    doc = parse_ecf_text("{ Block Id: 300\n  Name: TestBlock\n  AllowPlacingAt: Base,MS\n}\n")
    issues = validate_document(doc)
    e004 = _issues_with_code(issues, 'E004')
    assert len(e004) == 1
    assert 'guillemets' in e004[0].message


def test_quoted_comma_is_valid():
    doc = parse_ecf_text('{ Block Id: 300\n  Name: TestBlock\n  AllowPlacingAt: "Base,MS"\n}\n')
    issues = validate_document(doc)
    assert len(_issues_with_code(issues, 'E004')) == 0


def test_single_value_without_comma_is_valid():
    """Confirme sur un vrai fichier : 'AllowPlacingAt: MS' (une seule valeur,
    pas de virgule du tout) est une syntaxe normale, jamais une erreur."""
    doc = parse_ecf_text("{ Block Id: 300\n  Name: TestBlock\n  AllowPlacingAt: MS, display: true\n}\n")
    issues = validate_document(doc)
    assert len(_issues_with_code(issues, 'E004')) == 0


# ============================================================================
# E005 -- VolumeCapacity pour les classes conteneur, avec resolution Ref:
# ============================================================================

def test_container_without_volume_capacity_is_error():
    doc = parse_ecf_text("{ Block Id: 500\n  Name: TestContainer\n  Class: Container\n}\n")
    issues = validate_document(doc)
    assert len(_issues_with_code(issues, 'E005')) == 1


def test_container_with_volume_capacity_is_valid():
    doc = parse_ecf_text("{ Block Id: 500\n  Name: TestContainer\n  Class: Container\n  VolumeCapacity: 1000\n}\n")
    issues = validate_document(doc)
    assert len(_issues_with_code(issues, 'E005')) == 0


def test_container_inheriting_volume_capacity_via_ref_is_valid():
    """Confirme sur un vrai BlocksConfig.ecf : 2 des 3 exceptions apparentes
    heritent VolumeCapacity d'un bloc parent via Ref: -- ne doivent jamais
    etre signalees comme en defaut."""
    text = (
        "{ Block Id: 500\n  Name: BaseContainer\n  Class: Container\n  VolumeCapacity: 1000\n}\n"
        "{ Block Id: 501\n  Name: VariantContainer\n  Class: Container\n  Ref: BaseContainer\n}\n"
    )
    doc = parse_ecf_text(text)
    issues = validate_document(doc)
    assert len(_issues_with_code(issues, 'E005')) == 0


def test_non_container_class_is_never_checked():
    doc = parse_ecf_text("{ Block Id: 500\n  Name: TestDoor\n  Class: Door\n}\n")
    issues = validate_document(doc)
    assert len(_issues_with_code(issues, 'E005')) == 0


# ============================================================================
# W007/W008 -- materiau et HoldType (listes issues de vrais fichiers)
# ============================================================================

def test_known_material_is_not_flagged():
    doc = parse_ecf_text("{ Block Id: 300\n  Name: TestBlock\n  Material: Concrete\n}\n")
    issues = validate_document(doc)
    assert len(_issues_with_code(issues, 'W007')) == 0


def test_unknown_material_is_warning():
    doc = parse_ecf_text("{ Block Id: 300\n  Name: TestBlock\n  Material: unobtainium\n}\n")
    issues = validate_document(doc)
    assert len(_issues_with_code(issues, 'W007')) == 1


def test_known_hold_type_is_not_flagged():
    doc = parse_ecf_text("{ Block Id: 300\n  Name: TestBlock\n  HoldType: 20\n}\n")
    issues = validate_document(doc)
    assert len(_issues_with_code(issues, 'W008')) == 0


def test_unknown_hold_type_is_warning():
    doc = parse_ecf_text("{ Block Id: 300\n  Name: TestBlock\n  HoldType: 99\n}\n")
    issues = validate_document(doc)
    assert len(_issues_with_code(issues, 'W008')) == 1


# ============================================================================
# W009 -- BlockColor (format confirme sur 787 valeurs reelles : RGB ou RGBA)
# ============================================================================

def test_valid_rgb_blockcolor_is_not_flagged():
    doc = parse_ecf_text('{ Block Id: 300\n  Name: TestBlock\n  BlockColor: "110,110,110"\n}\n')
    issues = validate_document(doc)
    assert len(_issues_with_code(issues, 'W009')) == 0


def test_valid_rgba_blockcolor_is_not_flagged():
    """Confirme sur un vrai fichier : le canal alpha (4e valeur) est une
    syntaxe legitime, pas une erreur de format."""
    doc = parse_ecf_text('{ Block Id: 300\n  Name: TestBlock\n  BlockColor: "15,25,35,255"\n}\n')
    issues = validate_document(doc)
    assert len(_issues_with_code(issues, 'W009')) == 0


def test_blockcolor_out_of_range_is_warning():
    doc = parse_ecf_text('{ Block Id: 300\n  Name: TestBlock\n  BlockColor: "300,0,0"\n}\n')
    issues = validate_document(doc)
    assert len(_issues_with_code(issues, 'W009')) == 1


def test_malformed_blockcolor_is_warning():
    doc = parse_ecf_text('{ Block Id: 300\n  Name: TestBlock\n  BlockColor: "notacolor"\n}\n')
    issues = validate_document(doc)
    assert len(_issues_with_code(issues, 'W009')) == 1


# ============================================================================
# W005/W010/W011 -- HitPoints, Mass, MaxCount (0 occurrence anormale trouvee
# sur un vrai BlocksConfig.ecf -- confirme que toute occurrence est une vraie
# anomalie)
# ============================================================================

def test_negative_hitpoints_is_warning():
    doc = parse_ecf_text("{ Block Id: 300\n  Name: TestBlock\n  HitPoints: -5\n}\n")
    issues = validate_document(doc)
    assert len(_issues_with_code(issues, 'W005')) == 1


def test_positive_hitpoints_is_valid():
    doc = parse_ecf_text("{ Block Id: 300\n  Name: TestBlock\n  HitPoints: 100\n}\n")
    issues = validate_document(doc)
    assert len(_issues_with_code(issues, 'W005')) == 0


def test_negative_mass_is_warning():
    doc = parse_ecf_text("{ Block Id: 300\n  Name: TestBlock\n  Mass: -1.5\n}\n")
    issues = validate_document(doc)
    assert len(_issues_with_code(issues, 'W010')) == 1


def test_zero_maxcount_is_warning():
    doc = parse_ecf_text("{ Block Id: 300\n  Name: TestBlock\n  MaxCount: 0\n}\n")
    issues = validate_document(doc)
    assert len(_issues_with_code(issues, 'W011')) == 1


# ============================================================================
# W006 -- CustomIcon vide
# ============================================================================

def test_empty_custom_icon_is_warning():
    doc = parse_ecf_text('{ Block Id: 300\n  Name: TestBlock\n  CustomIcon: ""\n}\n')
    issues = validate_document(doc)
    assert len(_issues_with_code(issues, 'W006')) == 1


def test_filled_custom_icon_is_valid():
    doc = parse_ecf_text("{ Block Id: 300\n  Name: TestBlock\n  CustomIcon: MyIcon\n}\n")
    issues = validate_document(doc)
    assert len(_issues_with_code(issues, 'W006')) == 0


# ============================================================================
# Integration -- vrais fichiers du jeu
# ============================================================================

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "playfield_scenario"


def test_validate_real_blocks_config_produces_no_crash():
    """Le vrai BlocksConfig.ecf (reduit, fixture existante) doit se valider
    sans erreur de traitement -- meme sans forcement zero 'issue'."""
    issues = validate_document(parse_ecf_text((FIXTURE_DIR / "BlocksConfig.ecf").read_text(encoding='utf-8')))
    assert isinstance(issues, list)


# ============================================================================
# Filtrage par fichier -- Material/VolumeCapacity/doublons-de-Name (fiables
# uniquement sur BlocksConfig.ecf) et HoldType (fiable uniquement sur
# ItemsConfig.ecf). Regression directe : applique sans filtrage aux vrais
# fichiers du jeu, ces regles produisaient 234 faux positifs sur EClassConfig/
# FactionWarfare/GalaxyConfig/StatusEffects.ecf (Material et Class: Container
# y designent des concepts differents -- entites/creatures, pas des blocs de
# construction -- et Name y sert souvent d'etiquette de categorie repetee).
# ============================================================================

def test_material_check_active_on_blocks_config():
    doc = parse_ecf_text("{ Block Id: 300\n  Name: TestBlock\n  Material: unobtainium\n}\n")
    issues = validate_document(doc, file_path=Path('BlocksConfig.ecf'))
    assert len(_issues_with_code(issues, 'W007')) == 1


def test_material_check_disabled_outside_blocks_config():
    doc = parse_ecf_text("{ Entity Id: 300\n  Name: TestEntity\n  Material: Player\n}\n")
    issues = validate_document(doc, file_path=Path('EClassConfig.ecf'))
    assert len(_issues_with_code(issues, 'W007')) == 0


def test_container_volume_check_active_on_blocks_config():
    doc = parse_ecf_text("{ Block Id: 300\n  Name: TestBlock\n  Class: Container\n}\n")
    issues = validate_document(doc, file_path=Path('BlocksConfig.ecf'))
    assert len(_issues_with_code(issues, 'E005')) == 1


def test_container_volume_check_disabled_outside_blocks_config():
    """Confirme sur un vrai EClassConfig.ecf : 'Class: Container' y designe un
    conteneur de butin d'entite, pas un conteneur de bloc -- ne suit pas la
    meme regle VolumeCapacity."""
    doc = parse_ecf_text("{ Entity Id: 300\n  Name: DropContainer\n  Class: Container\n}\n")
    issues = validate_document(doc, file_path=Path('EClassConfig.ecf'))
    assert len(_issues_with_code(issues, 'E005')) == 0


def test_duplicate_name_check_active_on_blocks_config():
    text = "{ Block Name: SameName\n}\n{ Block Name: SameName\n}\n"
    doc = parse_ecf_text(text)
    issues = validate_document(doc, file_path=Path('BlocksConfig.ecf'))
    assert len(_issues_with_code(issues, 'W002')) == 1


def test_duplicate_name_check_disabled_outside_blocks_config():
    """Confirme sur un vrai FactionWarfare.ecf : 'Element Name: FactionSettings'
    apparait legitimement une fois par faction, jamais un vrai doublon."""
    text = "{ Element Name: FactionSettings\n}\n{ Element Name: FactionSettings\n}\n"
    doc = parse_ecf_text(text)
    issues = validate_document(doc, file_path=Path('FactionWarfare.ecf'))
    assert len(_issues_with_code(issues, 'W002')) == 0


def test_hold_type_check_active_on_items_config():
    doc = parse_ecf_text("{ Item Id: 300\n  Name: TestItem\n  HoldType: 99\n}\n")
    issues = validate_document(doc, file_path=Path('ItemsConfig.ecf'))
    assert len(_issues_with_code(issues, 'W008')) == 1


def test_hold_type_check_disabled_outside_items_config():
    doc = parse_ecf_text("{ Entity Id: 300\n  Name: TestEntity\n  HoldType: 99\n}\n")
    issues = validate_document(doc, file_path=Path('EClassConfig.ecf'))
    assert len(_issues_with_code(issues, 'W008')) == 0


def test_universal_rules_still_apply_regardless_of_file():
    """Id/BlockColor/HitPoints/Mass/MaxCount/CustomIcon restent verifies
    partout -- aucune preuve trouvee qu'ils different selon le fichier."""
    doc = parse_ecf_text(f"{{ Entity Id: 99999\n  Name: TestEntity\n}}\n")
    issues = validate_document(doc, file_path=Path('EClassConfig.ecf'))
    assert len(_issues_with_code(issues, 'E001')) == 1


def test_no_file_path_applies_all_rules_by_default():
    """Sans file_path (ex: validation directe d'un document en test), toutes
    les regles restent actives plutot que d'etre desactivees en silence."""
    doc = parse_ecf_text("{ Block Id: 300\n  Name: TestBlock\n  Material: unobtainium\n}\n")
    issues = validate_document(doc, file_path=None)
    assert len(_issues_with_code(issues, 'W007')) == 1


def test_full_real_gameconfig_produces_only_known_issues():
    """Test d'integration large : sur l'ensemble des vrais fichiers ECF du
    jeu disponibles, seuls les 2 problemes deja identifies et confirmes sur
    BlocksConfig.ecf doivent remonter -- tout le reste doit rester silencieux
    apres le filtrage par fichier."""
    from core.ecf.validation import validate_file
    uploads = Path("/mnt/user-data/uploads")
    if not uploads.exists():
        pytest.skip("Dossier de vrais fichiers non disponible dans cet environnement")
    total = 0
    for ecf_path in sorted(uploads.glob("*.ecf")):
        total += len(validate_file(ecf_path))
    assert total == 2
