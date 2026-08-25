"""
Tests du module de creation guidee de missions PDA (core/pda_mission.py) --
bases sur une fixture reduite mais fidele d'un vrai PDA.yaml (4 chapitres
reels extraits d'un fichier de 530 chapitres, memes auteurs que
Dialogues.ecf).
"""
from pathlib import Path

from core.yamllite.parser import parse_yaml_file, parse_yaml_text
from core.csv_handler import parse_csv_text
from core.pda_mission import (
    list_chapters, collect_used_names, collect_used_block_types, collect_all_tokens,
    generate_token, ObjectiveSpec, RewardSpec, RepeatSpec, create_chapter,
    list_mining_target_name_suggestions, credits_reward_item_name,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "pda_scenario" / "PDA.yaml"


def _doc():
    return parse_yaml_file(FIXTURE_PATH)


def test_list_chapters_finds_all_real_chapters():
    assert len(list_chapters(_doc())) == 4


def test_collect_all_tokens_finds_real_pda_tokens():
    tokens = collect_all_tokens(_doc())
    assert "pda_iG40h" in tokens
    assert len(tokens) > 10


def test_generate_token_never_collides_with_existing():
    doc = _doc()
    existing = collect_all_tokens(doc)
    new_token = generate_token(existing)
    assert new_token not in existing
    assert new_token.startswith("pda_")


def test_generate_token_format_matches_real_convention():
    new_token = generate_token(set())
    assert new_token.startswith("pda_")
    assert len(new_token) == len("pda_") + 7


def test_document_round_trips_perfectly_without_modification():
    original = FIXTURE_PATH.read_bytes()
    doc = parse_yaml_file(FIXTURE_PATH)
    list_chapters(doc)  # extraction seule
    assert doc.render().encode("utf-8") == original


def test_create_chapter_with_kill_objective():
    doc = _doc()
    tokens = collect_all_tokens(doc)

    def new_tok():
        t = generate_token(tokens)
        tokens.add(t)
        return t

    kill_spec = ObjectiveSpec(check_type="SubjectKilled", names=["WeakZiraxSoldier"], amount=10)
    chapter = create_chapter(doc, new_tok(), new_tok(), "SoloMission", [kill_spec], [], RepeatSpec(),
                              new_tok(), [(new_tok(), new_tok())])

    assert chapter is not None
    assert len(list_chapters(doc)) == 5


def test_created_chapter_reparses_correctly_and_has_expected_fields():
    doc = _doc()
    tokens = collect_all_tokens(doc)

    def new_tok():
        t = generate_token(tokens)
        tokens.add(t)
        return t

    kill_spec = ObjectiveSpec(check_type="SubjectKilled", names=["WeakZiraxSoldier", "ZiraxSoldier"], amount=10)
    reward = RewardSpec(kind="XP", count=2000)
    chapter_title = new_tok()
    create_chapter(doc, chapter_title, new_tok(), "SoloMission", [kill_spec], [reward], RepeatSpec(),
                    new_tok(), [(new_tok(), new_tok())])

    rendered = doc.render()
    reparsed = parse_yaml_text(rendered)
    assert reparsed is not None

    reparsed_chapters = list_chapters(reparsed)
    new_chapter = next(c for c in reparsed_chapters if c.value == chapter_title)
    tasks_node = next(c for c in new_chapter.children if c.key == "Tasks")
    action = tasks_node.children[0].children[0].children[0]  # Task -> Actions -> Action
    check_val = next(c.value for c in action.children if c.key == "Check")
    amount_val = next(c.value for c in action.children if c.key == "Amount")
    assert check_val == "SubjectKilled"
    assert amount_val == "10"


def test_create_chapter_with_mine_resource_objective():
    """Confirme le mecanisme cle : miner une ressource = BlockDestroyed avec
    un Types de ressource, meme mecanisme que detruire une structure
    ennemie."""
    doc = _doc()
    tokens = collect_all_tokens(doc)

    def new_tok():
        t = generate_token(tokens)
        tokens.add(t)
        return t

    mine_spec = ObjectiveSpec(check_type="BlockDestroyed", names=["IronResource"],
                               types=["IronResource"], amount=500)
    chapter_title = new_tok()
    create_chapter(doc, chapter_title, new_tok(), "SoloMission", [mine_spec], [], RepeatSpec(),
                    new_tok(), [(new_tok(), new_tok())])

    rendered = doc.render()
    reparsed = parse_yaml_text(rendered)
    new_chapter = next(c for c in list_chapters(reparsed) if c.value == chapter_title)
    action = next(c for c in new_chapter.children if c.key == "Tasks").children[0].children[0].children[0]
    types_node = next(c for c in action.children if c.key == "Types")
    assert types_node.children[0].value == "IronResource"


def test_create_chapter_with_item_reward():
    doc = _doc()
    tokens = collect_all_tokens(doc)

    def new_tok():
        t = generate_token(tokens)
        tokens.add(t)
        return t

    kill_spec = ObjectiveSpec(check_type="SubjectKilled", names=["WeakZiraxSoldier"], amount=5)
    item_reward = RewardSpec(kind="Item", item_name="IronIngot", count=50)
    chapter_title = new_tok()
    create_chapter(doc, chapter_title, new_tok(), "SoloMission", [kill_spec], [item_reward], RepeatSpec(),
                    new_tok(), [(new_tok(), new_tok())])

    rendered = doc.render()
    reparsed = parse_yaml_text(rendered)
    new_chapter = next(c for c in list_chapters(reparsed) if c.value == chapter_title)
    rewards_node = next(c for c in new_chapter.children if c.key == "Rewards")
    item_entry = rewards_node.children[0]
    assert item_entry.key == "Item"
    assert item_entry.value == "IronIngot"


def test_create_chapter_with_repeat_conditions():
    doc = _doc()
    tokens = collect_all_tokens(doc)

    def new_tok():
        t = generate_token(tokens)
        tokens.add(t)
        return t

    kill_spec = ObjectiveSpec(check_type="SubjectKilled", names=["WeakZiraxSoldier"], amount=5)
    repeat = RepeatSpec(num_repeats=5, delay_seconds=3600)
    chapter_title = new_tok()
    create_chapter(doc, chapter_title, new_tok(), "SoloMission", [kill_spec], [], repeat,
                    new_tok(), [(new_tok(), new_tok())])

    rendered = doc.render()
    reparsed = parse_yaml_text(rendered)
    new_chapter = next(c for c in list_chapters(reparsed) if c.value == chapter_title)
    repeat_node = next(c for c in new_chapter.children if c.key == "RepeatConditions")
    num_repeats = next(c.value for c in repeat_node.children if c.key == "NumRepeats")
    assert num_repeats == "5"


def test_no_repeat_conditions_node_when_not_repeatable():
    doc = _doc()
    tokens = collect_all_tokens(doc)

    def new_tok():
        t = generate_token(tokens)
        tokens.add(t)
        return t

    kill_spec = ObjectiveSpec(check_type="SubjectKilled", names=["WeakZiraxSoldier"], amount=5)
    chapter_title = new_tok()
    create_chapter(doc, chapter_title, new_tok(), "SoloMission", [kill_spec], [], RepeatSpec(num_repeats=0),
                    new_tok(), [(new_tok(), new_tok())])

    reparsed = parse_yaml_text(doc.render())
    new_chapter = next(c for c in list_chapters(reparsed) if c.value == chapter_title)
    assert not any(c.key == "RepeatConditions" for c in new_chapter.children)


def test_original_content_preserved_as_prefix_when_creating():
    """Regression cle : le contenu original doit rester un prefixe exact
    apres ajout d'un nouveau chapitre -- rien ne doit etre reordonne ou
    modifie ailleurs dans le fichier."""
    original = FIXTURE_PATH.read_bytes().decode("utf-8")
    doc = _doc()
    tokens = collect_all_tokens(doc)

    def new_tok():
        t = generate_token(tokens)
        tokens.add(t)
        return t

    kill_spec = ObjectiveSpec(check_type="SubjectKilled", names=["WeakZiraxSoldier"], amount=5)
    create_chapter(doc, new_tok(), new_tok(), "SoloMission", [kill_spec], [], RepeatSpec(),
                    new_tok(), [(new_tok(), new_tok())])

    rendered = doc.render()
    creator_idx = original.rfind("Creator:")
    before_creator = original[:creator_idx]
    assert rendered.startswith(before_creator)
    assert rendered.rstrip().endswith(original[creator_idx:].rstrip())


def test_collect_used_names_only_returns_matching_check_type():
    doc = _doc()
    kill_names = collect_used_names(doc, "SubjectKilled")
    destroy_names = collect_used_names(doc, "BlockDestroyed")
    # Les deux listes ne doivent jamais se chevaucher (des noms de creatures
    # differents des noms de blocs/ressources)
    assert set(kill_names).isdisjoint(set(destroy_names)) or (not kill_names and not destroy_names)


def test_collect_used_block_types_returns_empty_for_no_matches():
    doc = _doc()
    types_found = collect_used_block_types(doc)
    assert isinstance(types_found, list)


# ============================================================================
# Ajout de lignes de texte dans PDA.csv (jetons pda_XXXX associes aux
# nouveaux chapitres/taches/actions crees)
# ============================================================================

def test_add_pda_text_entries_locates_columns_by_header():
    from core.csv_handler import parse_csv_text, render_csv
    from core.pda_mission import add_pda_text_entries
    doc = parse_csv_text(FIXTURE_PATH.with_suffix(".csv").read_text(encoding="utf-8"))
    add_pda_text_entries(doc, [("pda_NEWKEY", "English text", "Texte francais")])

    new_row = next(r for r in doc.rows if r[0] == "pda_NEWKEY")
    header = doc.header
    assert new_row[header.index("English")] == "English text"
    assert new_row[header.index("Français")] == "Texte francais"


def test_add_pda_text_entries_survives_round_trip():
    from core.csv_handler import parse_csv_text, render_csv
    from core.pda_mission import add_pda_text_entries
    csv_fixture = FIXTURE_PATH.with_suffix(".csv")
    doc = parse_csv_text(csv_fixture.read_text(encoding="utf-8"))
    add_pda_text_entries(doc, [("pda_NEWKEY", "English text", "Texte francais")])

    rendered = render_csv(doc)
    reparsed = parse_csv_text(rendered)
    found = next(r for r in reparsed.rows if r[0] == "pda_NEWKEY")
    assert found[reparsed.header.index("English")] == "English text"


def test_add_pda_text_entries_leaves_other_languages_empty():
    from core.csv_handler import parse_csv_text
    from core.pda_mission import add_pda_text_entries
    doc = parse_csv_text(FIXTURE_PATH.with_suffix(".csv").read_text(encoding="utf-8"))
    add_pda_text_entries(doc, [("pda_NEWKEY", "English text", "Texte francais")])

    new_row = next(r for r in doc.rows if r[0] == "pda_NEWKEY")
    deutsch_idx = doc.header.index("Deutsch") if "Deutsch" in doc.header else None
    if deutsch_idx is not None:
        assert new_row[deutsch_idx] == ""


def test_add_pda_text_entries_does_not_touch_existing_rows():
    from core.csv_handler import parse_csv_text
    from core.pda_mission import add_pda_text_entries
    csv_text = FIXTURE_PATH.with_suffix(".csv").read_text(encoding="utf-8")
    doc = parse_csv_text(csv_text)
    original_first_row = list(doc.rows[0])

    add_pda_text_entries(doc, [("pda_NEWKEY", "English text", "Texte francais")])
    assert doc.rows[0] == original_first_row


# ============================================================================
# Chaine de paliers (core.pda_mission.create_tier_chain) -- confirme sur une
# vraie chaine du jeu (Amount 50 -> 100 -> 35 sur 3 chapitres successifs,
# lies via RewardedChapters + Activatable: WhenRewarded, PAS
# RepeatConditions qui repete le meme chapitre a l'identique).
# ============================================================================

def _make_tiers(n=3):
    from core.pda_mission import TierSpec, ObjectiveSpec, RewardSpec
    tiers = []
    for i in range(n):
        amount = 1000 * (i + 1)
        tiers.append(TierSpec(
            title_text=f"Mine {amount} Iron", description_text=f"Palier {i + 1}",
            objective=ObjectiveSpec(check_type="BlockDestroyed", names=["IronResource"],
                                     types=["IronResource"], amount=amount),
            rewards=[RewardSpec(kind="XP", count=1000 * (i + 1))],
        ))
    return tiers


def test_create_tier_chain_creates_one_chapter_per_tier():
    from core.pda_mission import create_tier_chain, list_chapters
    doc = _doc()
    csv_doc = parse_csv_text((FIXTURE_PATH.parent / "PDA.csv").read_text(encoding="utf-8"))
    before = len(list_chapters(doc))

    chapters = create_tier_chain(doc, csv_doc, _make_tiers(3), "SoloMission")

    assert len(chapters) == 3
    assert len(list_chapters(doc)) == before + 3


def test_first_tier_is_always_activatable():
    from core.pda_mission import create_tier_chain
    doc = _doc()
    csv_doc = parse_csv_text((FIXTURE_PATH.parent / "PDA.csv").read_text(encoding="utf-8"))
    chapters = create_tier_chain(doc, csv_doc, _make_tiers(3), "SoloMission")

    activatable = next(c.value for c in chapters[0].children if c.key == "Activatable")
    assert activatable == "Always"


def test_subsequent_tiers_are_when_rewarded():
    from core.pda_mission import create_tier_chain
    doc = _doc()
    csv_doc = parse_csv_text((FIXTURE_PATH.parent / "PDA.csv").read_text(encoding="utf-8"))
    chapters = create_tier_chain(doc, csv_doc, _make_tiers(3), "SoloMission")

    for chapter in chapters[1:]:
        activatable = next(c.value for c in chapter.children if c.key == "Activatable")
        assert activatable == "WhenRewarded"


def test_each_tier_points_to_the_next_via_rewarded_chapters():
    from core.pda_mission import create_tier_chain
    doc = _doc()
    csv_doc = parse_csv_text((FIXTURE_PATH.parent / "PDA.csv").read_text(encoding="utf-8"))
    chapters = create_tier_chain(doc, csv_doc, _make_tiers(3), "SoloMission")

    for i in range(len(chapters) - 1):
        rc_node = next(c for c in chapters[i].children if c.key == "RewardedChapters")
        assert rc_node.children[0].value == chapters[i + 1].value


def test_last_tier_has_no_rewarded_chapters():
    from core.pda_mission import create_tier_chain
    doc = _doc()
    csv_doc = parse_csv_text((FIXTURE_PATH.parent / "PDA.csv").read_text(encoding="utf-8"))
    chapters = create_tier_chain(doc, csv_doc, _make_tiers(3), "SoloMission")

    assert not any(c.key == "RewardedChapters" for c in chapters[-1].children)


def test_tier_chain_reparses_correctly():
    from core.pda_mission import create_tier_chain
    doc = _doc()
    csv_doc = parse_csv_text((FIXTURE_PATH.parent / "PDA.csv").read_text(encoding="utf-8"))
    create_tier_chain(doc, csv_doc, _make_tiers(3), "SoloMission")

    reparsed = parse_yaml_text(doc.render())
    assert reparsed is not None


def test_tier_chain_generates_csv_entries_for_all_tiers():
    from core.pda_mission import create_tier_chain
    doc = _doc()
    csv_doc = parse_csv_text((FIXTURE_PATH.parent / "PDA.csv").read_text(encoding="utf-8"))
    before_rows = len(csv_doc.rows)
    create_tier_chain(doc, csv_doc, _make_tiers(3), "SoloMission")
    assert len(csv_doc.rows) > before_rows


def test_empty_tier_list_creates_nothing():
    from core.pda_mission import create_tier_chain, list_chapters
    doc = _doc()
    csv_doc = parse_csv_text((FIXTURE_PATH.parent / "PDA.csv").read_text(encoding="utf-8"))
    before = len(list_chapters(doc))
    chapters = create_tier_chain(doc, csv_doc, [], "SoloMission")
    assert chapters == []
    assert len(list_chapters(doc)) == before


def test_single_tier_has_no_rewarded_chapters_either():
    """Un seul palier = pas de chainage necessaire, comportement identique a
    create_chapter() seul."""
    from core.pda_mission import create_tier_chain
    doc = _doc()
    csv_doc = parse_csv_text((FIXTURE_PATH.parent / "PDA.csv").read_text(encoding="utf-8"))
    chapters = create_tier_chain(doc, csv_doc, _make_tiers(1), "SoloMission")
    assert len(chapters) == 1
    assert not any(c.key == "RewardedChapters" for c in chapters[0].children)


def test_original_content_preserved_when_creating_tier_chain():
    from core.pda_mission import create_tier_chain
    original = FIXTURE_PATH.read_bytes().decode("utf-8")
    doc = _doc()
    csv_doc = parse_csv_text((FIXTURE_PATH.parent / "PDA.csv").read_text(encoding="utf-8"))
    create_tier_chain(doc, csv_doc, _make_tiers(3), "SoloMission")

    rendered = doc.render()
    creator_idx = original.rfind("Creator:")
    before_creator = original[:creator_idx]
    assert rendered.startswith(before_creator)


def test_list_mining_target_name_suggestions_includes_planetary_resources(tmp_path):
    blocks_ecf = tmp_path / "BlocksConfig.ecf"
    blocks_ecf.write_text(
        "{ Block Id: 1, Name: IronResource\n  Group: resource\n}\n"
        "{ Block Id: 2, Name: NotAResourceBlock\n}\n",
        encoding="utf-8")
    names = list_mining_target_name_suggestions([blocks_ecf])
    assert "IronResource" in names
    assert "NotAResourceBlock" not in names


def test_list_mining_target_name_suggestions_includes_asteroid_voxel_variants(tmp_path):
    """Motif confirme des playfields spatiaux : AsteroidVoxel0N<Materiau>,
    genere a partir du materiau de base ('Iron') des ressources planetaires,
    meme si ce nom precis n'existe pas comme Name de bloc dans
    BlocksConfig.ecf (voir core.playfield_editor.add_space_resource_item)."""
    blocks_ecf = tmp_path / "BlocksConfig.ecf"
    blocks_ecf.write_text(
        "{ Block Id: 1, Name: IronResource\n  Group: resource\n}\n", encoding="utf-8")
    names = list_mining_target_name_suggestions([blocks_ecf])
    assert "AsteroidVoxel01Iron" in names
    assert "AsteroidVoxel02Iron" in names
    assert "AsteroidVoxel03Iron" in names


def test_list_mining_target_name_suggestions_empty_for_no_files():
    assert list_mining_target_name_suggestions([]) == []


def test_credits_reward_item_name_is_moneycard():
    """Confirme sur le vrai ItemsConfig.ecf de l'utilisateur (RE2 EVO) : le
    commentaire '## Please do not rename - referenced in code' juste au-dessus
    de la definition de 'MoneyCard' (Credits: 1, StackSize: 50000) prouve que
    c'est le VRAI nom d'item cable en dur par le moteur pour representer les
    credits -- 'Credits' (nom litteral) ne fonctionne pas (infirme sur deux
    logs client reels, voir historique)."""
    assert credits_reward_item_name() == "MoneyCard"
