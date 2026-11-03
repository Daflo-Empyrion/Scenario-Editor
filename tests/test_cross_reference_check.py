from pathlib import Path

from core.ecf.cross_reference_check import (
    CrossRefContext, CROSS_REFERENCE_CHECKS, run_checks,
    _check_material_refs, _check_pda_poi_refs, _check_ref_inheritance,
    _check_item_block_pool, _check_token_refs,
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
    assert ids == ["ref_inheritance", "item_block_pool", "token_refs",
                   "dialogue_refs", "material_refs", "pda_poi_refs"]


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


def test_token_refs_flags_only_undefined_token(tmp_path, monkeypatch):
    # hermetique : la machine de dev peut avoir un jeu configure
    # (vanilla_content_path) dont le TokenConfig defini aussi 9999
    _no_vanilla(monkeypatch)
    issues = _check_token_refs(_ctx())
    values = {i.ref_value for i in issues}
    assert values == {"Token:9999"}
    assert "Token:1" not in values


def test_token_refs_accepts_vanilla_defined_token(tmp_path, monkeypatch):
    """Vecu 03/11/2026 : les CredTokens 100-113 etaient signales a tort —
    ils sont definis dans le TokenConfig VANILLA du jeu, que le moteur
    charge comme couche de base sous le scenario."""
    conf = tmp_path / "Configuration"
    conf.mkdir()
    (conf / "TokenConfig.ecf").write_text(
        "{ Token Id: 100, Name: CredTokenZiraxEmpire\n}\n", encoding="utf-8")
    monkeypatch.setattr("core.settings.get_vanilla_content_path",
                        lambda: str(tmp_path))
    issues = _check_token_refs(_ctx())
    values = {i.ref_value for i in issues}
    assert values == {"Token:9999"}       # 9999 n'existe ni au scenario ni a la fausse vanilla
    assert "Token:1" not in values


def _no_vanilla(monkeypatch):
    monkeypatch.setattr("core.settings.get_vanilla_content_path", lambda: "")


def test_dialogue_refs_accepts_vanilla_defined_dialogue(tmp_path, monkeypatch):
    """Vecu 03/11/2026 : le jeu charge la vanilla comme couche de base —
    un Next_1 vers un dialogue defini dans la VANILLA existe en jeu, pas
    d'alerte (repli gracieux si le chemin du jeu n'est pas renseigne)."""
    conf = tmp_path / "Configuration"
    conf.mkdir()
    (conf / "Dialogues.ecf").write_text(
        '{ +Dialogue Name: Pir_VanillaTalk\n}\n', encoding="utf-8")
    monkeypatch.setattr("core.settings.get_vanilla_content_path",
                        lambda: str(tmp_path))
    scenario = tmp_path / "scenario" / "Dialogues.ecf"
    scenario.parent.mkdir()
    scenario.write_text(
        '{ +Dialogue Name: A\n  Next_1: Pir_VanillaTalk\n}\n'
        '{ +Dialogue Name: B\n  Next_1: Fantome\n}\n', encoding="utf-8")
    ctx = CrossRefContext(ecf_files=[scenario], yaml_files=[], scenario_root=None)
    from core.ecf.cross_reference_check import _check_dialogue_refs
    issues = _check_dialogue_refs(ctx)
    assert [i.ref_value for i in issues] == ["Fantome"]


def test_ref_inheritance_clean_on_scenario_without_ref():
    issues = _check_ref_inheritance(_ctx())
    assert issues == []


def test_run_checks_respects_selected_ids_only(tmp_path, monkeypatch):
    _no_vanilla(monkeypatch)
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
    assert ids == ["ref_inheritance", "item_block_pool", "token_refs",
                   "dialogue_refs", "material_refs", "pda_poi_refs"]


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


# ============================================================================
# Verification 5 : materiaux (vecu 04/10 : bloc 872 ->
# 'hullcombatcharged' absent du MaterialConfig -> table des blocs morte ->
# cascade « No template found » + NRE au demarrage du jeu)
# ============================================================================

def test_material_refs_flags_missing_material(tmp_path):
    (tmp_path / "MaterialConfig.ecf").write_text(
        "{ Material Name: SteelHull\n  damage_category: metal\n}\n",
        encoding="utf-8")
    (tmp_path / "BlocksConfig.ecf").write_text(
        "{ +Block Id: 1, Name: BonBloc\n  Material: SteelHull\n}\n"
        "{ +Block Id: 2, Name: BlocCassee\n  Material: GhostMat\n}\n",
        encoding="utf-8")
    ctx = CrossRefContext(ecf_files=[tmp_path / "MaterialConfig.ecf",
                                     tmp_path / "BlocksConfig.ecf"],
                          yaml_files=[], scenario_root=tmp_path)
    issues = _check_material_refs(ctx)
    assert len(issues) == 1
    assert issues[0].ref_value == "GhostMat"
    assert issues[0].check_id == "material_refs"
    assert issues[0].source_identity == "2"


def test_material_refs_exempts_entity_classes(tmp_path):
    """Vecu 03/11/2026 : 146 faux positifs — les ENTITES (EClassConfig)
    reference des archetypes de materiau internes au moteur (HumanSoft,
    CreatureSoft, DronePlanet, Player...) qu'aucun MaterialConfig ne definit,
    ni vanilla ni RE2 ni ATL. Seuls les BLOCS sont verifiables."""
    (tmp_path / "MaterialConfig.ecf").write_text(
        "{ Material Name: SteelHull\n  damage_category: metal\n}\n",
        encoding="utf-8")
    (tmp_path / "EClassConfig.ecf").write_text(
        "{ +Entity Name: UnMec\n  Material: HumanSoft\n}\n", encoding="utf-8")
    (tmp_path / "BlocksConfig.ecf").write_text(
        "{ +Block Id: 1, Name: B\n  Material: GhostMat\n}\n", encoding="utf-8")
    ctx = CrossRefContext(ecf_files=[tmp_path / "MaterialConfig.ecf",
                                     tmp_path / "EClassConfig.ecf",
                                     tmp_path / "BlocksConfig.ecf"],
                          yaml_files=[], scenario_root=tmp_path)
    issues = _check_material_refs(ctx)
    assert [i.ref_value for i in issues] == ["GhostMat"]


def test_material_refs_accepts_vanilla_defined_material(tmp_path, monkeypatch):
    conf = tmp_path / "Configuration"
    conf.mkdir()
    (conf / "MaterialConfig.ecf").write_text(
        "{ Material Name: HullVanilla\n  damage_category: metal\n}\n",
        encoding="utf-8")
    monkeypatch.setattr("core.settings.get_vanilla_content_path",
                        lambda: str(tmp_path))
    scenario = tmp_path / "scenario"
    scenario.mkdir()
    (scenario / "MaterialConfig.ecf").write_text(
        "{ Material Name: SteelHull\n  damage_category: metal\n}\n",
        encoding="utf-8")
    (scenario / "BlocksConfig.ecf").write_text(
        "{ +Block Id: 1, Name: B\n  Material: HullVanilla\n}\n"
        "{ +Block Id: 2, Name: C\n  Material: GhostMat\n}\n", encoding="utf-8")
    ctx = CrossRefContext(ecf_files=[scenario / "MaterialConfig.ecf",
                                     scenario / "BlocksConfig.ecf"],
                          yaml_files=[], scenario_root=scenario)
    issues = _check_material_refs(ctx)
    assert [i.ref_value for i in issues] == ["GhostMat"]


def test_material_refs_silent_without_materialconfig(tmp_path):
    """Scenario sans MaterialConfig propre : les materiaux viennent du jeu
    de base, rien a verifier localement."""
    (tmp_path / "BlocksConfig.ecf").write_text(
        "{ +Block Id: 1, Name: B\n  Material: X\n}\n", encoding="utf-8")
    ctx = CrossRefContext(ecf_files=[tmp_path / "BlocksConfig.ecf"],
                          yaml_files=[], scenario_root=tmp_path)
    assert _check_material_refs(ctx) == []


# ============================================================================
# Verification 6 : POIs cibles des missions PDA (vecu 05/10 : la mission
# locale Masperon de Random EXP cible des cages absentes du scenario hote)
# ============================================================================

PDA_Y = """- ChapterTitle: pda_t1
  Tasks:
    - TaskTitle: pda_t2
      Actions:
        - ActionTitle: pda_a1
          Check: NearPoi
          Names:
            - MyCage
        - ActionTitle: pda_a2
          Check: NearPoi
          Names:
            - GhostPoi
"""

PF_Y = """POIs:
    Random:
        - GroupName: MyCage
          Faction: Abyssal
"""


def test_pda_poi_refs_flags_missing_poi(tmp_path):
    (tmp_path / "Playfields" / "GS_X").mkdir(parents=True)
    (tmp_path / "Playfields" / "GS_X" / "playfield_static.yaml").write_text(
        PF_Y, encoding="utf-8")
    (tmp_path / "Extras" / "PDA").mkdir(parents=True)
    (tmp_path / "Extras" / "PDA" / "PDA.yaml").write_text(PDA_Y, encoding="utf-8")
    ctx = CrossRefContext(ecf_files=[], yaml_files=[], scenario_root=tmp_path)
    issues = _check_pda_poi_refs(ctx)
    values = {i.ref_value for i in issues}
    assert values == {"GhostPoi"}
    assert all(i.check_id == "pda_poi_refs" for i in issues)


def test_pda_poi_refs_silent_without_pda(tmp_path):
    (tmp_path / "Playfields" / "GS_X").mkdir(parents=True)
    (tmp_path / "Playfields" / "GS_X" / "playfield_static.yaml").write_text(
        PF_Y, encoding="utf-8")
    ctx = CrossRefContext(ecf_files=[], yaml_files=[], scenario_root=tmp_path)
    assert _check_pda_poi_refs(ctx) == []


def test_pda_poi_refs_accepts_displayname_prefabname_brackets(tmp_path):
    """Vecu 03/11/2026 : 15 faux positifs — le pool ne connaissait ni
    PrefabName, ni DisplayName (le PDA cible une SOUS-CHAINE du nom affiche :
    'Kenex Station 62' in 'Kenex 62 Kenex Station 62'), ni les valeurs
    bracketees 'Name: [X]', ni les yamls a plus de 2 niveaux."""
    (tmp_path / "Playfields" / "GS_X" / "sous").mkdir(parents=True)
    (tmp_path / "Playfields" / "GS_X" / "sous" / "profond.yaml").write_text(
        "POIs:\n"
        "    Fixed:\n"
        "        - PrefabName: Prefabs/Eden_BAO_UCHResearchShp.epb\n"
        "          DisplayName: Kenex 62 Kenex Station 62\n"
        "          Name: [RBA_RedRogue01]\n"
        "          GroupName: MaCage\n", encoding="utf-8")
    pda = (
        "- ChapterTitle: c\n"
        "  Tasks:\n"
        "    - TaskTitle: t\n"
        "      Actions:\n"
        "        - ActionTitle: a\n"
        "          Check: NearPoi\n"
        "          Names:\n"
        "            - Eden_BAO_UCHResearchShp\n"
        "            - Kenex Station 62\n"
        "            - RBA_RedRogue01\n"
        "            - MaCage\n"
        "            - Cage\n"
        "            - VraiFantome\n")
    (tmp_path / "Extras" / "PDA").mkdir(parents=True)
    (tmp_path / "Extras" / "PDA" / "PDA.yaml").write_text(pda, encoding="utf-8")
    ctx = CrossRefContext(ecf_files=[], yaml_files=[], scenario_root=tmp_path)
    issues = _check_pda_poi_refs(ctx)
    assert [i.ref_value for i in issues] == ["VraiFantome"]

# ============================================================================
# Reparation VERIF-006 (vecu 03/11/2026) : supprimer une OptionNext cassee
# doit retirer l'option ENTIERE du menu NPC (texte + condition), pas seulement
# la cible — sinon le PNJ garde un bouton mort.
# ============================================================================

def test_apply_fix_removes_whole_option(tmp_path):
    from core.ecf.cross_reference_check import apply_dialogue_ref_fix
    f = tmp_path / "Dialogues.ecf"
    f.write_text(
        '{ +Dialogue Name: A\n'
        '  Option_1: eden_dialogue_a\n'
        '  OptionNext_1: End\n'
        '  Option_3: eden_dialogue_c\n'
        '  OptionNext_3: Fantome\n'
        '}\n', encoding="utf-8")
    assert apply_dialogue_ref_fix(f, "A", "OptionNext_3", "Fantome", None)
    text = f.read_text(encoding="utf-8")
    assert "Fantome" not in text
    assert "eden_dialogue_c" not in text      # l'option 3 (texte) part avec sa cible
    assert "Option_1" in text and "OptionNext_1: End" in text   # option 1 intacte


def test_apply_fix_removes_next_branch_and_orphan_param1(tmp_path):
    from core.ecf.cross_reference_check import apply_dialogue_ref_fix
    f = tmp_path / "Dialogues.ecf"
    f.write_text(
        '{ +Dialogue Name: A\n'
        '  Next_1: B\n'
        '  NextIf_1: "x == 0"\n'
        '  Next_2: undefined\n'
        '}\n'
        '{ +Dialogue Name: C\n'
        '  OptionNext_2: Fantome, param1: GotoAndReset\n'
        '}\n', encoding="utf-8")
    assert apply_dialogue_ref_fix(f, "A", "Next_2", "undefined", None)
    assert apply_dialogue_ref_fix(f, "C", "OptionNext_2", "Fantome", None)
    text = f.read_text(encoding="utf-8")
    assert "undefined" not in text
    assert "Next_1" in text and 'NextIf_1: "x == 0"' in text    # branche saine intacte
    assert "GotoAndReset" not in text         # param1 orphelin saute avec sa reference


def test_apply_fix_removes_nextif_with_its_branch(tmp_path):
    """Supprimer Next_1 doit emporter sa condition NextIf_1 (orpheline sans
    sa branche) mais laisser Next_2 et sa propre condition intactes."""
    from core.ecf.cross_reference_check import apply_dialogue_ref_fix
    f = tmp_path / "Dialogues.ecf"
    f.write_text(
        '{ +Dialogue Name: Smuggler\n'
        '  Next_1: Greet_Fantome\n'
        '  NextIf_1: "PDACheck == true"\n'
        '  Next_2: Deny_Fantome\n'
        '  NextIf_2: "HasItem()"\n'
        '}\n', encoding="utf-8")
    assert apply_dialogue_ref_fix(f, "Smuggler", "Next_1", "Greet_Fantome", None)
    text = f.read_text(encoding="utf-8")
    assert "Greet_Fantome" not in text and "PDACheck" not in text
    assert "Deny_Fantome" in text and "HasItem()" in text


def test_apply_pda_poi_fix_replaces_and_removes(tmp_path):
    """Fenetre de correction PDA : remplacer une cible par un POI existant
    (round-trip yamllite) ou retirer l'item de la liste Names."""
    from core.ecf.cross_reference_check import apply_pda_poi_fix
    pda = tmp_path / "PDA.yaml"
    pda.write_text(PDA_Y, encoding="utf-8")
    # remplacement (GhostPoi est vise par l'action pda_a2 dans PDA_Y)
    assert apply_pda_poi_fix(pda, "pda_a2", "NearPoi", "GhostPoi", "MonPoi")
    text = pda.read_text(encoding="utf-8")
    assert "GhostPoi" not in text and "MonPoi" in text
    assert "MyCage" in text                     # l'autre cible intacte
    assert "NearPoi" in text                    # la ligne Check intacte
    # retrait
    assert apply_pda_poi_fix(pda, "pda_a2", "NearPoi", "MonPoi", None)
    text = pda.read_text(encoding="utf-8")
    assert "MonPoi" not in text and "MyCage" in text
    # le yaml reste lisible par le check (plus rien de signale pour MonPoi)
    pf = tmp_path / "Playfields" / "GS_X" / "playfield_static.yaml"
    pf.parent.mkdir(parents=True, exist_ok=True)
    pf.write_text(PF_Y, encoding="utf-8")
    ctx = CrossRefContext(ecf_files=[], yaml_files=[], scenario_root=tmp_path)
    assert _check_pda_poi_refs(ctx) == []


def test_apply_fix_replaces_value(tmp_path):
    from core.ecf.cross_reference_check import apply_dialogue_ref_fix
    f = tmp_path / "Dialogues.ecf"
    f.write_text(
        '{ +Dialogue Name: A\n'
        '  OptionNext_3: Eden_PurgStartPod3_Log3\n'
        '}\n'
        '{ +Dialogue Name: Eden_PurgStartPod3_Log\n}\n', encoding="utf-8")
    assert apply_dialogue_ref_fix(f, "A", "OptionNext_3",
                                  "Eden_PurgStartPod3_Log3",
                                  "Eden_PurgStartPod3_Log")
    text = f.read_text(encoding="utf-8")
    assert "Eden_PurgStartPod3_Log3" not in text
    assert "OptionNext_3: Eden_PurgStartPod3_Log\n" in text


def test_collect_dialogue_stats_counts_refs_and_terminal(tmp_path):
    from core.ecf.cross_reference_check import collect_dialogue_stats
    f = tmp_path / "Dialogues.ecf"
    f.write_text(
        '{ +Dialogue Name: A\n'
        '  Next_1: B\n'
        '}\n'
        '{ +Dialogue Name: B\n'
        '  Output: un_texte\n'
        '}\n'
        '{ +Dialogue Name: C\n'
        '  OptionNext_1: A\n'
        '}\n', encoding="utf-8")
    stats = collect_dialogue_stats([f])
    assert stats["B"] == {"refs": 1, "terminal": True}
    assert stats["A"]["refs"] == 1 and stats["A"]["terminal"] is False
    assert stats["C"]["refs"] == 0 and stats["C"]["terminal"] is False


def test_pda_pool_includes_prefab_display_names(tmp_path, monkeypatch):
    """Vecu 03/11/2026 : `NearPoi: Ship Landing Site` fonctionne en jeu alors
    qu'aucun playfield ne porte ce nom — c'est le DisplayName (propriete 16)
    du prefab R2BA_FreighterStory.epb. Le pool doit l'inclure."""
    from core.ecf import cross_reference_check as crc

    prefabs = tmp_path / "Prefabs"
    prefabs.mkdir()
    (prefabs / "R2BA_FreighterStory.epb").write_bytes(b"x")
    (tmp_path / "Playfields" / "P1").mkdir(parents=True)
    (tmp_path / "Playfields" / "P1" / "playfield_static.yaml").write_text(
        "POIs:\n    Random:\n        - GroupName: MonGroupe\n", encoding="utf-8")
    (tmp_path / "Extras" / "PDA").mkdir(parents=True)
    (tmp_path / "Extras" / "PDA" / "PDA.yaml").write_text(
        "- ChapterTitle: c\n  Tasks:\n    - TaskTitle: t\n      Actions:\n"
        "        - ActionTitle: a\n          Check: NearPoi\n          Names:\n"
        "            - Ship Landing Site\n", encoding="utf-8")

    monkeypatch.setattr(crc, "_prefab_display_names",
                        lambda root: {"ship landing site"})
    crc._PREFAB_DISPLAY_CACHE.clear()
    ctx = CrossRefContext(ecf_files=[], yaml_files=[], scenario_root=tmp_path)
    assert _check_pda_poi_refs(ctx) == []


def test_pda_pool_includes_prefab_entity_names(tmp_path, monkeypatch):
    """Vecu 03/11/2026 : `NearPoi: Security Manager` vise un NPC habitant
    DANS un prefab (header .epb), pas un POI de playfield. Le pool doit
    inclure les noms d'entites des prefabs."""
    from core.ecf import cross_reference_check as crc

    (tmp_path / "Prefabs").mkdir()
    (tmp_path / "Prefabs" / "RBA_PolarisTradingStory.epb").write_bytes(b"x")
    (tmp_path / "Playfields" / "P1").mkdir(parents=True)
    (tmp_path / "Playfields" / "P1" / "playfield_static.yaml").write_text(
        "POIs:\n    Random:\n        - GroupName: MonGroupe\n", encoding="utf-8")
    (tmp_path / "Extras" / "PDA").mkdir(parents=True)
    (tmp_path / "Extras" / "PDA" / "PDA.yaml").write_text(
        "- ChapterTitle: c\n  Tasks:\n    - TaskTitle: t\n      Actions:\n"
        "        - ActionTitle: a\n          Check: NearPoi\n          Names:\n"
        "            - Security Manager\n", encoding="utf-8")

    monkeypatch.setattr(crc, "_prefab_entity_names",
                        lambda root: {"security manager"})
    crc._PREFAB_ENTITY_CACHE.clear()
    ctx = CrossRefContext(ecf_files=[], yaml_files=[], scenario_root=tmp_path)
    assert _check_pda_poi_refs(ctx) == []
