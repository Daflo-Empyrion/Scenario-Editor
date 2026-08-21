"""
Tests du module de creation guidee de blocs/items (core/ecf/block_creation.py)
-- bases sur de vrais extraits de Templates.ecf/BlocksConfig.ecf/ItemsConfig.ecf,
avec verification de round-trip et de coherence sur le vrai jeu de format
'Child Inputs' (confirme different du motif numerote Name_N utilise ailleurs).
"""
from pathlib import Path

import pytest

from core.ecf.block_creation import (
    scan_kind_frequency, scan_properties_for_kind, most_common_value,
    create_new_block, add_child_inputs, find_file_by_name, list_craftable_names,
)
from core.ecf.parser import parse_ecf_file, parse_ecf_text

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "block_creation_scenario"
BLOCKS_FIXTURE = Path(__file__).parent / "fixtures" / "playfield_scenario" / "BlocksConfig.ecf"


@pytest.fixture
def templates_doc():
    return parse_ecf_file(FIXTURE_DIR / "Templates.ecf")


@pytest.fixture
def blocks_doc():
    return parse_ecf_file(BLOCKS_FIXTURE)


def test_scan_kind_frequency_on_real_templates(templates_doc):
    counts = scan_kind_frequency(templates_doc)
    assert counts["+Template"] == 3
    assert counts["Template"] == 1


def test_scan_properties_for_kind_on_real_blocks(blocks_doc):
    props = scan_properties_for_kind(blocks_doc, "Block")
    assert "Material" in props
    assert "Shape" in props


def test_most_common_value_picks_majority():
    from collections import Counter
    c = Counter({"Device": 5, "Wood": 1})
    assert most_common_value(c) == "Device"


def test_most_common_value_empty_counter_returns_empty_string():
    from collections import Counter
    assert most_common_value(Counter()) == ""


def test_create_new_block_with_id_and_name():
    block = create_new_block("Block", "500", "TestBlock", [("Material", "Concrete")])
    assert block.get("Id") == "500"
    assert block.get("Name") == "TestBlock"
    assert block.get_property("Material") == "Concrete"


def test_create_new_block_name_only():
    block = create_new_block("Block", None, "TestBlock", [])
    assert block.get("Id") is None
    assert block.get("Name") == "TestBlock"


def test_created_block_round_trips_after_reparse():
    block = create_new_block("Block", "500", "TestBlock", [("Material", "Concrete"), ("Mass", "10")])
    rendered = block.render()
    reparsed = parse_ecf_text(rendered)
    reparsed_block = list(reparsed.iter_blocks())[0]
    assert reparsed_block.get("Id") == "500"
    assert reparsed_block.get_property("Material") == "Concrete"
    # Deuxieme rendu identique (stable, pas de derive)
    assert reparsed.render() == rendered


def test_add_child_inputs_creates_correct_structure():
    block = create_new_block("+Template", None, "NewCraftable", [("CraftTime", "10")])
    add_child_inputs(block, [("IronOre", "5"), ("CopperOre", "3")])

    rendered = block.render()
    reparsed = parse_ecf_text(rendered)
    reparsed_block = list(reparsed.iter_blocks())[0]

    from core.ecf.model import EcfBlock
    child_inputs = [c for c in reparsed_block.children if isinstance(c, EcfBlock) and c.kind == "Child Inputs"]
    assert len(child_inputs) == 1
    ingredient_pairs = []
    for prop in child_inputs[0].children:
        if hasattr(prop, "pairs"):
            ingredient_pairs.extend(prop.pairs)
    assert ("IronOre", "5") in ingredient_pairs
    assert ("CopperOre", "3") in ingredient_pairs


def test_child_inputs_indentation_matches_real_file_format():
    """Regression : add_property_line() (indent fixe 2 espaces) ne convient
    pas a une structure imbriquee -- confirme sur un vrai Templates.ecf que
    Child Inputs doit etre a 2 espaces et ses lignes d'ingredients a 4."""
    block = create_new_block("+Template", None, "NewCraftable", [])
    add_child_inputs(block, [("IronOre", "5")])
    rendered = block.render()
    assert "\r\n  { Child Inputs\r\n" in rendered
    assert "\r\n    IronOre: 5\r\n" in rendered
    assert "\r\n  }\r\n}\r\n" in rendered  # fermeture Child Inputs a 2 espaces, PAS 0


def test_add_child_inputs_appends_to_existing_child_inputs():
    """Si Child Inputs existe deja (rare mais possible si on complete un
    Template deja partiellement cree), les nouveaux ingredients s'ajoutent
    plutot que de dupliquer le sous-bloc."""
    block = create_new_block("+Template", None, "NewCraftable", [])
    add_child_inputs(block, [("IronOre", "5")])
    add_child_inputs(block, [("CopperOre", "3")])

    from core.ecf.model import EcfBlock
    child_inputs_blocks = [c for c in block.children if isinstance(c, EcfBlock) and c.kind == "Child Inputs"]
    assert len(child_inputs_blocks) == 1  # un seul sous-bloc, pas deux
    assert len(child_inputs_blocks[0].children) == 2  # les deux ingredients dedans


def test_inserted_block_preserves_rest_of_real_document(templates_doc):
    original_render = templates_doc.render()
    new_block = create_new_block("+Template", None, "MyNewCraftableItem", [("CraftTime", "10")])
    add_child_inputs(new_block, [("IronOre", "5")])
    templates_doc.nodes.append(new_block)

    new_render = templates_doc.render()
    assert new_render.startswith(original_render)
    assert "MyNewCraftableItem" in new_render[len(original_render):]


def test_find_file_by_name_case_insensitive():
    files = [Path("/x/Templates.ecf"), Path("/x/BlocksConfig.ecf")]
    found = find_file_by_name(files, "templates.ecf")
    assert found == Path("/x/Templates.ecf")


def test_find_file_by_name_returns_none_if_missing():
    files = [Path("/x/BlocksConfig.ecf")]
    assert find_file_by_name(files, "Templates.ecf") is None


def test_list_craftable_names_combines_items_and_blocks():
    names = list_craftable_names(
        FIXTURE_DIR / "ItemsConfig.ecf", BLOCKS_FIXTURE)
    assert "IronOre" in names  # vient d'ItemsConfig.ecf
    assert len(names) > 0


def test_list_craftable_names_handles_missing_files_gracefully():
    names = list_craftable_names(None, None)
    assert names == []
