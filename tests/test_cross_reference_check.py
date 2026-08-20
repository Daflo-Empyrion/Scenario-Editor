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
    # plutot que corrige davantage. Verification dialogues ajoutee ensuite
    # (voir test_registry_has_four_checks_including_dialogues plus bas).
    ids = [c.id for c in CROSS_REFERENCE_CHECKS]
    assert ids == ["ref_inheritance", "item_block_pool", "token_refs", "dialogue_refs"]


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


# ============================================================================
# Verification 4 : dialogues -- bases sur les motifs reels confirmes sur un
# vrai Dialogues.ecf (5417 blocs, 3109 Next_N, 8769 OptionNext_N)
# ============================================================================

DIALOGUES_FIXTURE = Path(__file__).parent / "fixtures" / "dialogues_scenario" / "Dialogues.ecf"


def _dialogue_ctx():
    return CrossRefContext(ecf_files=[DIALOGUES_FIXTURE], yaml_files=[], scenario_root=None)


def test_registry_has_four_checks_including_dialogues():
    ids = [c.id for c in CROSS_REFERENCE_CHECKS]
    assert ids == ["ref_inheritance", "item_block_pool", "token_refs", "dialogue_refs"]


def test_dialogue_refs_enabled_by_default():
    by_id = {c.id: c for c in CROSS_REFERENCE_CHECKS}
    assert by_id["dialogue_refs"].enabled_by_default is True


def test_dialogue_refs_finds_only_genuinely_broken_targets():
    from core.ecf.cross_reference_check import _check_dialogue_refs
    issues = _check_dialogue_refs(_dialogue_ctx())
    values = {i.ref_value for i in issues}
    assert values == {"NPC_TargetThatWasNeverCreated", "undefined"}


def test_dialogue_refs_ignores_reserved_sentinels():
    """'End', 'GotoAndReset' et 'Return' sont des mots-cles reserves du
    moteur de dialogue -- jamais de vrais noms de dialogue, confirme par
    recherche exhaustive sur un vrai Dialogues.ecf (aucune des trois valeurs
    n'existe comme Name nulle part dans le fichier reel)."""
    from core.ecf.cross_reference_check import _check_dialogue_refs
    issues = _check_dialogue_refs(_dialogue_ctx())
    values = {i.ref_value for i in issues}
    assert "End" not in values
    assert "GotoAndReset" not in values
    assert "Return" not in values


def test_dialogue_refs_ignores_dynamic_variable_pattern():
    """'@NomVariable' est une reference dynamique resolue par le moteur de
    script au moment de l'execution (confirme sur un vrai fichier : la
    variable est declaree via Variable_N et assignee dans Execute), jamais un
    nom de dialogue litteral -- impossible et incorrect a valider
    statiquement."""
    from core.ecf.cross_reference_check import _check_dialogue_refs
    issues = _check_dialogue_refs(_dialogue_ctx())
    values = {i.ref_value for i in issues}
    assert not any(v.startswith("@") for v in values)


def test_dialogue_refs_accepts_valid_param1_dual_reference():
    """'OptionNext_1: Barking_Set, param1: Trader_Talk' -- les DEUX valeurs
    sont des references locales a valider (pas un renvoi vers un autre
    fichier, hypothese initiale erronee corrigee par verification directe sur
    un vrai fichier) ; les deux existent ici, aucune ne doit etre signalee."""
    from core.ecf.cross_reference_check import _check_dialogue_refs
    issues = _check_dialogue_refs(_dialogue_ctx())
    values = {i.ref_value for i in issues}
    assert "Barking_Set" not in values
    assert "Trader_Talk" not in values


def test_dialogue_refs_nextif_never_checked_as_reference():
    """'NextIf_N' est une condition de script (ex: 'SomeCondition == true'),
    jamais une reference -- ne doit jamais apparaitre comme ref_key."""
    from core.ecf.cross_reference_check import _check_dialogue_refs
    issues = _check_dialogue_refs(_dialogue_ctx())
    ref_keys = {i.ref_key for i in issues}
    assert not any("NextIf" in k for k in ref_keys)


def test_dialogue_refs_empty_when_no_dialogue_blocks():
    ctx = CrossRefContext(ecf_files=[FIXTURE_DIR / "ItemsConfig.ecf"], yaml_files=[], scenario_root=None)
    from core.ecf.cross_reference_check import _check_dialogue_refs
    assert _check_dialogue_refs(ctx) == []
