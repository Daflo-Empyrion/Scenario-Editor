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
Tests de core.tech_tree -- fixtures derivees d'un vrai BlocksConfig.ecf/
ItemsConfig.ecf uploade et verifie manuellement (session du 28/08/2026, voir
docstring de core/tech_tree.py pour le detail des champs confirmes).
"""
import shutil
from pathlib import Path

import pytest

from core.tech_tree import (
    load_tech_tree, set_unlock_level, set_unlock_cost, move_to_category, set_tech_tree_parent, parse_quoted_list,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "tech_tree_scenario"


@pytest.fixture
def working_files(tmp_path):
    blocks = tmp_path / "BlocksConfig.ecf"
    items = tmp_path / "ItemsConfig.ecf"
    shutil.copy(FIXTURE_DIR / "BlocksConfig.ecf", blocks)
    shutil.copy(FIXTURE_DIR / "ItemsConfig.ecf", items)
    return blocks, items


def test_parse_quoted_list():
    assert parse_quoted_list('"Base,Capital Vessel"') == ["Base", "Capital Vessel"]
    assert parse_quoted_list("Weapons") == ["Weapons"]
    assert parse_quoted_list(None) == []
    assert parse_quoted_list("") == []
    assert parse_quoted_list('""') == []


def test_load_tech_tree_includes_valid_nodes(working_files):
    blocks, items = working_files
    tree = load_tech_tree(blocks, items)
    names = {n.name for n in tree.nodes}
    assert "OxygenTankSmallMS" in names
    assert "FuelTankMSLarge" in names
    assert "CombatKnife" in names
    assert "PlasmaSword" in names


def test_load_tech_tree_includes_plus_block_and_plus_item(working_files):
    """Bug reel trouve sur le vrai BlocksConfig.ecf/ItemsConfig.ecf Steam
    vanilla (session du 29/08/2026) : les blocs/items '+Block'/'+Item'
    (patch officiel qui modifie une entree existante par Id/Ref plutot que
    de la redefinir integralement) etaient exclus a tort par un filtre sur
    le genre exact 'Block'/'Item' -- faisait chuter 367 noeuds reels a 13."""
    blocks, items = working_files
    tree = load_tech_tree(blocks, items)
    n = tree.get("PatchedBlockWithTechTree")
    assert n is not None
    assert n.unlock_level == 5
    assert n.unlock_cost == 8
    assert n.categories == ["Tools"]


def test_load_tech_tree_excludes_hidden_even_with_unlock_level(working_files):
    """Cas reel confirme : HeavyPistol a TechTreeNames=Hidden ET UnlockLevel=1
    simultanement -- doit rester exclu (voir docstring du module)."""
    blocks, items = working_files
    tree = load_tech_tree(blocks, items)
    names = {n.name for n in tree.nodes}
    assert "HeavyPistol" not in names
    assert "TurretMSPlasma" not in names  # Hidden, sans UnlockLevel


def test_load_tech_tree_excludes_node_without_tech_tree_names(working_files):
    blocks, items = working_files
    tree = load_tech_tree(blocks, items)
    names = {n.name for n in tree.nodes}
    assert "SomeAlienBlock" not in names


def test_node_fields_match_real_values(working_files):
    blocks, items = working_files
    tree = load_tech_tree(blocks, items)
    n = tree.get("FuelTankMSLarge")
    assert n.unlock_level == 10
    assert n.unlock_cost == 12
    assert n.parent_name == "FuelTankMSSmall"
    assert n.categories == ["Base", "Capital Vessel"]
    assert n.source == "block"
    assert n.icon_key == "FuelTankMSLarge"  # pas de CustomIcon -> repli sur Name


def test_root_node_has_no_parent(working_files):
    blocks, items = working_files
    tree = load_tech_tree(blocks, items)
    n = tree.get("OxygenTankSmallMS")
    assert n.parent_name is None
    assert n.unlock_cost == 0
    assert n.unlock_level == 1


def test_custom_icon_used_as_icon_key(working_files):
    blocks, items = working_files
    tree = load_tech_tree(blocks, items)
    n = tree.get("PlasmaSword")
    assert n.icon_key == "PlasmaSwordIcon"


def test_categories_known_order_first(working_files):
    blocks, items = working_files
    tree = load_tech_tree(blocks, items)
    cats = tree.categories()
    # Base avant Capital Vessel avant Weapons, cohérent avec KNOWN_CATEGORY_ORDER
    assert cats.index("Base") < cats.index("Capital Vessel") < cats.index("Weapons")


def test_levels_are_sorted_and_deduplicated(working_files):
    blocks, items = working_files
    tree = load_tech_tree(blocks, items)
    assert tree.levels() == sorted(set(tree.levels()))


def test_children_of_returns_direct_children_only(working_files):
    blocks, items = working_files
    tree = load_tech_tree(blocks, items)
    children = tree.children_of("FuelTankMSSmall")
    assert {c.name for c in children} == {"FuelTankMSLarge"}


def test_set_unlock_level_writes_and_persists(working_files):
    blocks, items = working_files
    ok = set_unlock_level(blocks, "FuelTankMSLarge", 12)
    assert ok is True
    tree = load_tech_tree(blocks, items)
    assert tree.get("FuelTankMSLarge").unlock_level == 12


def test_set_unlock_level_returns_false_for_missing_node(working_files):
    blocks, items = working_files
    assert set_unlock_level(blocks, "DoesNotExist", 5) is False


def test_set_unlock_cost_writes_and_persists(working_files):
    blocks, items = working_files
    ok = set_unlock_cost(blocks, "FuelTankMSLarge", 20)
    assert ok is True
    tree = load_tech_tree(blocks, items)
    assert tree.get("FuelTankMSLarge").unlock_cost == 20


def test_move_to_category_replaces_not_appends(working_files):
    """Comportement confirme aupres de l'utilisateur : deplacer = remplacer,
    pas ajouter (voir docstring de move_to_category)."""
    blocks, items = working_files
    ok = move_to_category(blocks, "FuelTankMSLarge", "Weapons")
    assert ok is True
    tree = load_tech_tree(blocks, items)
    n = tree.get("FuelTankMSLarge")
    assert n.categories == ["Weapons"]
    assert "Base" not in n.categories


def test_set_tech_tree_parent_creates_property_when_absent(working_files):
    """OxygenTankSmallMS est racine (pas de TechTreeParent du tout) --
    lui affecter un parent doit CREER la propriete (action explicite de
    l'utilisateur via glisser-deposer, pas une supposition)."""
    blocks, items = working_files
    ok = set_tech_tree_parent(blocks, "OxygenTankSmallMS", "FuelTankMSSmall")
    assert ok is True
    tree = load_tech_tree(blocks, items)
    assert tree.get("OxygenTankSmallMS").parent_name == "FuelTankMSSmall"


def test_set_tech_tree_parent_changes_existing_value(working_files):
    blocks, items = working_files
    ok = set_tech_tree_parent(blocks, "FuelTankMSLarge", "OxygenTankSmallMS")
    assert ok is True
    tree = load_tech_tree(blocks, items)
    assert tree.get("FuelTankMSLarge").parent_name == "OxygenTankSmallMS"


def test_set_tech_tree_parent_none_removes_property(working_files):
    """Bug reel trouve et corrige (session du 29/08/2026) : la propriete
    TechTreeParent est presque toujours sa PROPRE ligne (EcfProperty enfant),
    pas une paire sur la ligne d'ouverture du bloc -- une suppression basee
    uniquement sur EcfBlock.remove() semblait reussir sans rien persister."""
    blocks, items = working_files
    set_tech_tree_parent(blocks, "OxygenTankSmallMS", "FuelTankMSSmall")
    ok = set_tech_tree_parent(blocks, "OxygenTankSmallMS", None)
    assert ok is True
    tree = load_tech_tree(blocks, items)
    assert tree.get("OxygenTankSmallMS").parent_name is None


def test_set_tech_tree_parent_none_when_already_root_is_harmless(working_files):
    blocks, items = working_files
    ok = set_tech_tree_parent(blocks, "OxygenTankSmallMS", None)
    assert ok is True
    tree = load_tech_tree(blocks, items)
    assert tree.get("OxygenTankSmallMS").parent_name is None


def test_set_tech_tree_parent_does_not_corrupt_rest_of_file(working_files):
    blocks, items = working_files
    original_names = {n.name for n in load_tech_tree(blocks, items).nodes}
    set_tech_tree_parent(blocks, "OxygenTankSmallMS", "FuelTankMSSmall")
    from core.ecf.parser import parse_ecf_file
    doc = parse_ecf_file(blocks)
    assert doc.render()  # ne leve pas, round-trip coherent
    new_names = {n.name for n in load_tech_tree(blocks, items).nodes}
    assert original_names == new_names


def test_writes_do_not_corrupt_rest_of_file(working_files):
    """Round-trip global : seules les lignes concernees changent, tout le
    reste du fichier reste identique octet pres."""
    blocks, items = working_files
    original = blocks.read_text(encoding='utf-8')
    set_unlock_level(blocks, "FuelTankMSLarge", 12)
    modified = blocks.read_text(encoding='utf-8')

    from core.ecf.parser import parse_ecf_text
    doc_orig = parse_ecf_text(original)
    doc_mod = parse_ecf_text(modified)
    assert len(list(doc_orig.iter_blocks())) == len(list(doc_mod.iter_blocks()))
    # Le bloc OxygenTankSmallMS (non touche) doit rester identique
    assert doc_orig.iter_blocks().__iter__()
    orig_o2 = next(b for b in doc_orig.iter_blocks() if b.get('Name') == 'OxygenTankSmallMS')
    mod_o2 = next(b for b in doc_mod.iter_blocks() if b.get('Name') == 'OxygenTankSmallMS')
    assert orig_o2.get_property('UnlockLevel') == mod_o2.get_property('UnlockLevel')


# ---------------------------------------------------------------------------
# Regression sur le VRAI BlocksConfig.ecf/ItemsConfig.ecf Steam vanilla
# (session du 29/08/2026) -- verrouille le bug '+Block'/'+Item' (13 -> 241
# noeuds detectes) trouve sur ce fichier reel.
# ---------------------------------------------------------------------------

VANILLA_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "tech_tree_vanilla_real"


def test_vanilla_real_file_yields_hundreds_of_nodes_not_a_dozen():
    tree = load_tech_tree(VANILLA_FIXTURE_DIR / "BlocksConfig.ecf", VANILLA_FIXTURE_DIR / "ItemsConfig.ecf")
    assert len(tree.nodes) > 200


def test_vanilla_real_file_includes_known_plus_block_chain():
    tree = load_tech_tree(VANILLA_FIXTURE_DIR / "BlocksConfig.ecf", VANILLA_FIXTURE_DIR / "ItemsConfig.ecf")
    n = tree.get("FuelTankMSLarge")
    assert n is not None
    assert n.unlock_level == 10
    assert n.unlock_cost == 12
    assert n.parent_name == "FuelTankMSSmall"
    assert n.categories == ["Base", "Capital Vessel"]


def test_vanilla_real_file_all_seven_known_categories_present():
    tree = load_tech_tree(VANILLA_FIXTURE_DIR / "BlocksConfig.ecf", VANILLA_FIXTURE_DIR / "ItemsConfig.ecf")
    cats = set(tree.categories())
    for expected in ["Base", "Capital Vessel", "Small Vessel", "Hover Vessel", "Misc", "Tools", "Weapons"]:
        assert expected in cats


# ---------------------------------------------------------------------------
# Edition GENERIQUE depuis la fiche d'information de l'arbre (demande du
# 31/08/2026 : equilibrage rapide directement dans l'arbre technologique).
# ---------------------------------------------------------------------------

def test_find_block_by_name_returns_block_or_none(working_files):
    from core.tech_tree import find_block_by_name
    blocks, items = working_files
    b = find_block_by_name(blocks, "OxygenTankSmallMS")
    assert b is not None and b.kind in ("Block", "+Block")
    assert find_block_by_name(blocks, "InconnuIntrouvable") is None


def test_set_block_property_edits_scalar_and_persists(working_files):
    from core.tech_tree import set_block_property, find_block_by_name
    blocks, items = working_files
    assert set_block_property(blocks, "OxygenTankSmallMS", "UnlockCost", "55") is True
    assert find_block_by_name(blocks, "OxygenTankSmallMS").get_property("UnlockCost") == "55"
    # round-trip : le reste du fichier est intact (le niveau n'a pas bouge)
    assert find_block_by_name(blocks, "OxygenTankSmallMS").get_property("UnlockLevel") is not None


def test_set_block_property_returns_false_for_unknown_property(working_files):
    from core.tech_tree import set_block_property
    blocks, _ = working_files
    assert set_block_property(blocks, "OxygenTankSmallMS", "ProprieteInexistante", "1") is False


def test_add_and_remove_block_property_roundtrip(working_files):
    from core.tech_tree import add_block_property, remove_block_property, find_block_by_name
    blocks, _ = working_files
    assert add_block_property(blocks, "OxygenTankSmallMS", "TestStat", "42") is True
    assert find_block_by_name(blocks, "OxygenTankSmallMS").get_property("TestStat") == "42"
    assert remove_block_property(blocks, "OxygenTankSmallMS", "TestStat", "42") is True
    assert find_block_by_name(blocks, "OxygenTankSmallMS").get_property("TestStat") is None


def test_remove_block_property_never_touches_opening_line_pairs(working_files):
    """Id/Name vivent sur la ligne d'ouverture : structurels, jamais
    supprimables depuis la fiche (le scanner ne cible que les lignes
    enfants)."""
    from core.tech_tree import remove_block_property, find_block_by_name
    blocks, _ = working_files
    assert remove_block_property(blocks, "OxygenTankSmallMS", "Name", "OxygenTankSmallMS") is False
    assert find_block_by_name(blocks, "OxygenTankSmallMS") is not None


def _template_ingredient_qty(tpl, template_name, key):
    """Quantite d'un ingredient : la paire vit dans le SOUS-BLOC 'Child
    Inputs', pas sur le Template lui-meme."""
    from core.tech_tree import find_block_by_name
    template = find_block_by_name(tpl, template_name)
    for child in template.children:
        if getattr(child, 'kind', None) == 'Child Inputs':
            for prop in child.children:
                if prop.get(key) is not None:
                    return prop.get(key)
    return None


def test_template_ingredient_edit_add_remove_roundtrip(tmp_path):
    """Edition d'ingredients du Template dans Templates.ecf (fixture derive
    du vrai fichier) : modification, ajout, suppression."""
    import shutil
    from core.tech_tree import (set_template_ingredient, add_template_ingredient,
                                 remove_template_ingredient, find_block_by_name)
    tpl_src = Path(__file__).parent / "fixtures" / "block_info_card_scenario" / "Templates.ecf"
    tpl = tmp_path / "Templates.ecf"
    shutil.copy(tpl_src, tpl)
    template_name = "FuelTankMSLarge"

    assert set_template_ingredient(tpl, template_name, "Electronics", "12", "8") is True
    assert _template_ingredient_qty(tpl, template_name, "Electronics") == "12"

    assert add_template_ingredient(tpl, template_name, "TestOre", "7") is True
    assert _template_ingredient_qty(tpl, template_name, "TestOre") == "7"

    assert remove_template_ingredient(tpl, template_name, "TestOre", "7") is True
    assert _template_ingredient_qty(tpl, template_name, "TestOre") is None

    # quantite absente / Template absent : False, jamais de creation aveugle
    assert set_template_ingredient(tpl, template_name, "Electronics", "99", "MISMATCH") is False
    assert set_template_ingredient(tpl, "TemplateInconnu", "Electronics", "99", "12") is False


TEMPLATE_WITH_OUTPUT_COUNT = """{ Template Name: WithOutput
  CraftTime: 30
  OutputCount: 2
  { Child Inputs
    SteelPlate: 5
  }
}
"""


def test_set_template_output_count(tmp_path):
    import shutil
    from core.tech_tree import set_template_output_count, find_block_by_name
    tpl_src = Path(__file__).parent / "fixtures" / "block_info_card_scenario" / "Templates.ecf"
    tpl = tmp_path / "Templates.ecf"
    shutil.copy(tpl_src, tpl)
    # Le fixture reel n'a PAS d'OutputCount : False, jamais de creation
    # aveugle (coherent avec set_unlock_level).
    assert set_template_output_count(tpl, "FuelTankMSLarge", "3") is False

    tpl.write_text(TEMPLATE_WITH_OUTPUT_COUNT, encoding='utf-8')
    assert set_template_output_count(tpl, "WithOutput", "3") is True
    assert find_block_by_name(tpl, "WithOutput").get_property("OutputCount") == "3"
