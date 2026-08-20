from pathlib import Path

from core.ecf.cross_reference_check import (
    CrossRefContext, CROSS_REFERENCE_CHECKS, run_checks,
    _check_ref_inheritance, _check_item_block_pool, _check_token_refs,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "cross_ref_scenario"


def _ctx():
    ecf_files = sorted(FIXTURE_DIR.glob("*.ecf"))
    return CrossRefContext(ecf_files=ecf_files, yaml_files=[], scenario_root=FIXTURE_DIR)


def test_registry_has_three_checks_with_expected_ids():
    # Verification POI/Prefabs retiree : le champ verifie ("Prefab"/"POI") ne
    # correspondait en realite pas au nom du POI dans un vrai playfield mais a
    # un GroupName, un concept different -- controle non pertinent, supprime
    # plutot que corrige davantage.
    ids = [c.id for c in CROSS_REFERENCE_CHECKS]
    assert ids == ["ref_inheritance", "item_block_pool", "token_refs"]


def test_all_checks_enabled_by_default():
    for check in CROSS_REFERENCE_CHECKS:
        assert check.enabled_by_default is True


def test_item_block_pool_flags_only_nonexistent_item():
    issues = _check_item_block_pool(_ctx())
    values = {i.ref_value for i in issues}
    assert values == {"NonExistentItem"}
    # Les entrees valides (IronOre depuis ItemsConfig.ecf, ConcreteBlock depuis
    # BlocksConfig.ecf) ne doivent jamais apparaitre comme cassees.
    assert "IronOre" not in values
    assert "ConcreteBlock" not in values


def test_token_refs_flags_only_undefined_token():
    issues = _check_token_refs(_ctx())
    values = {i.ref_value for i in issues}
    assert values == {"Token:9999"}
    assert "Token:1" not in values


def test_ref_inheritance_clean_on_scenario_without_ref():
    issues = _check_ref_inheritance(_ctx())
    assert issues == []


def test_run_checks_respects_selected_ids_only():
    ctx = _ctx()
    issues = run_checks(ctx, ["ref_inheritance"])
    assert issues == []  # ce scenario n'a pas de Ref casse

    issues = run_checks(ctx, ["item_block_pool", "token_refs"])
    assert len(issues) == 2
    check_ids = {i.check_id for i in issues}
    assert check_ids == {"item_block_pool", "token_refs"}


def test_run_checks_empty_selection_returns_empty():
    ctx = _ctx()
    assert run_checks(ctx, []) == []


def test_item_block_pool_falls_back_to_all_files_when_no_dedicated_files():
    # Sans ItemsConfig.ecf/BlocksConfig.ecf dedies dans la liste, le repli doit
    # chercher dans TOUS les fichiers fournis plutot que de ne rien verifier.
    sample = Path(__file__).parent / "fixtures" / "sample.ecf"
    ctx = CrossRefContext(ecf_files=[sample], yaml_files=[], scenario_root=None)
    issues = _check_item_block_pool(ctx)
    # IronOre/CopperOre n'existent nulle part dans ce fichier unique -> signales
    values = {i.ref_value for i in issues}
    assert "IronOre" in values
    assert "CopperOre" in values


def test_display_path_shows_relative_scenario_path():
    """Le chemin affiche pour un resultat doit rester exploitable meme si le
    fichier ne s'appelle pas directement (sous-dossier Content/Configuration/,
    coherent avec un vrai scenario)."""
    issues = _check_item_block_pool(_ctx())
    assert len(issues) == 1
    assert issues[0].display_path == "Containers.ecf"
