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

"""Tests de core.ecf.variants -- duplication multi-variantes (blocs
entiers et lignes de structure repetitive en mode tableau)."""
from core.ecf.parser import parse_ecf_text
from core.ecf.model import EcfProperty
from core.ecf.variants import (
    is_numeric_value, compute_variant_values,
    detect_numeric_fields_block, generate_block_variants,
    detect_numeric_fields_row, generate_row_variants,
    list_editable_fields_block,
)


# ---------------------------------------------------------------------
# is_numeric_value
# ---------------------------------------------------------------------

def test_is_numeric_value_integer():
    assert is_numeric_value("10") is True


def test_is_numeric_value_decimal():
    assert is_numeric_value("2.5") is True


def test_is_numeric_value_range_is_not_numeric():
    assert is_numeric_value("1,4") is False


def test_is_numeric_value_text_is_not_numeric():
    assert is_numeric_value("Concrete") is False


def test_is_numeric_value_none():
    assert is_numeric_value(None) is False


# ---------------------------------------------------------------------
# compute_variant_values
# ---------------------------------------------------------------------

def test_compute_variant_values_first_is_original_starts_at_zero_percent():
    values = compute_variant_values("2.0", 3, 20.0, first_is_original=True)
    assert values[0] == "2.0"
    assert values[-1] == "2.4"


def test_compute_variant_values_centered_mode():
    values = compute_variant_values("2.0", 3, 20.0, first_is_original=False)
    assert values[0] == "1.8"
    assert values[1] == "2.0"  # milieu = valeur d'origine exacte
    assert values[2] == "2.2"


def test_compute_variant_values_preserves_decimal_precision():
    values = compute_variant_values("2.00", 2, 10.0, first_is_original=True)
    assert values[0] == "2.00"
    assert values[1] == "2.20"


def test_compute_variant_values_integer_stays_integer():
    values = compute_variant_values("10", 5, 40.0, first_is_original=True)
    assert values == ["10", "11", "12", "13", "14"]


def test_compute_variant_values_non_numeric_repeated_unchanged():
    values = compute_variant_values("1,4", 3, 20.0, first_is_original=True)
    assert values == ["1,4", "1,4", "1,4"]


def test_compute_variant_values_single_variant_no_division_by_zero():
    values = compute_variant_values("5.0", 1, 20.0, first_is_original=True)
    assert values == ["5.0"]


def test_compute_variant_values_negative_percent():
    values = compute_variant_values("100", 3, -20.0, first_is_original=True)
    assert values == ["100", "90", "80"]


# ---------------------------------------------------------------------
# Variantes de bloc entier
# ---------------------------------------------------------------------

def _make_block():
    text = (
        "{ Block Id: 81, Name: IronResource\n"
        "  Material: resourcesoft\n"
        "  XpFactor: 2.0\n"
        "  Texture: 173\n"
        "}\n"
    )
    doc = parse_ecf_text(text)
    return next(doc.iter_blocks())


def test_detect_numeric_fields_block_finds_child_properties():
    block = _make_block()
    fields = detect_numeric_fields_block(block)
    assert "XpFactor" in fields
    assert "Texture" in fields
    assert "Material" not in fields  # non numerique


def test_detect_numeric_fields_block_excludes_id():
    """Id est toujours retire lors de la generation des variantes
    (identifiees par Name seul) -- le proposer a cocher serait trompeur,
    et le cocher n'aurait de toute facon aucun effet."""
    block = _make_block()
    fields = detect_numeric_fields_block(block)
    assert "Id" not in fields


def _make_block_with_nested_child():
    """Motif reel confirme sur BlocksConfig.ecf : un sous-bloc imbrique
    '{ Child DropOnDestroy ... }' porte des champs numeriques (Prob) qui
    ne sont PAS des enfants directs du bloc parent."""
    text = (
        "{ Block Id: 53, Name: SathiumResource\n"
        "  Material: resourcehard\n"
        "  XpFactor: 6.0\n"
        "  { Child DropOnDestroy\n"
        "    Item: SathiumOre\n"
        "    Count: \"1,2\"\n"
        "    Prob: 0.5\n"
        "  }\n"
        "}\n"
    )
    doc = parse_ecf_text(text)
    return next(doc.iter_blocks())


def test_detect_numeric_fields_block_finds_nested_sub_block_properties():
    block = _make_block_with_nested_child()
    fields = detect_numeric_fields_block(block)
    assert "Prob" in fields
    assert "XpFactor" in fields
    assert "Count" not in fields  # "1,2" n'est pas un scalaire numerique


def test_get_and_set_block_field_reach_into_nested_sub_blocks():
    from core.ecf.variants import get_block_field, set_block_field
    block = _make_block_with_nested_child()
    assert get_block_field(block, "Prob") == "0.5"
    assert set_block_field(block, "Prob", "0.9") is True
    assert get_block_field(block, "Prob") == "0.9"


def test_generate_block_variants_varies_nested_sub_block_field():
    block = _make_block_with_nested_child()
    variants = generate_block_variants(block, "SathiumResource", 3, ["Prob"], 100.0, first_is_original=True)
    from core.ecf.variants import get_block_field
    values = [get_block_field(v, "Prob") for v in variants]
    # decimals preserves 1 chiffre apres la virgule (comme la valeur d'origine "0.5")
    assert values == ["0.5", "0.8", "1.0"]
    # le bloc source ne doit pas etre mute
    assert get_block_field(block, "Prob") == "0.5"


# ---------------------------------------------------------------------
# Valeurs numeriques entre guillemets
# ---------------------------------------------------------------------

def test_is_numeric_value_accepts_quoted_number():
    assert is_numeric_value('"600"') is True


def test_is_numeric_value_quoted_range_still_not_numeric():
    assert is_numeric_value('"1,4"') is False


def test_compute_variant_values_preserves_quotes():
    values = compute_variant_values('"600"', 3, 20.0, first_is_original=True)
    assert values == ['"600"', '"660"', '"720"']


# ---------------------------------------------------------------------
# compute_single_variant_value / apply_percent_to_block / apply_percent_to_row
# ---------------------------------------------------------------------

def test_compute_single_variant_value_positive_percent():
    from core.ecf.variants import compute_single_variant_value
    assert compute_single_variant_value("0.5", 20.0) == "0.6"


def test_compute_single_variant_value_negative_percent():
    from core.ecf.variants import compute_single_variant_value
    assert compute_single_variant_value("100", -20.0) == "80"


def test_compute_single_variant_value_preserves_quotes():
    from core.ecf.variants import compute_single_variant_value
    assert compute_single_variant_value('"600"', -10.0) == '"540"'


def test_compute_single_variant_value_non_numeric_unchanged():
    from core.ecf.variants import compute_single_variant_value
    assert compute_single_variant_value("Concrete", 20.0) == "Concrete"


def test_apply_percent_to_block_modifies_only_selected_fields():
    from core.ecf.variants import apply_percent_to_block, get_block_field
    block = _make_block()
    new_block = apply_percent_to_block(block, ["XpFactor"], 50.0)
    assert get_block_field(new_block, "XpFactor") == "3.0"
    assert get_block_field(new_block, "Texture") == "173"  # non selectionne, inchange
    # le bloc source ne doit pas etre mute
    assert get_block_field(block, "XpFactor") == "2.0"


def test_apply_percent_to_block_reaches_nested_sub_block():
    from core.ecf.variants import apply_percent_to_block, get_block_field
    block = _make_block_with_nested_child()
    new_block = apply_percent_to_block(block, ["Prob"], 100.0)
    assert get_block_field(new_block, "Prob") == "1.0"
    assert get_block_field(block, "Prob") == "0.5"


def test_apply_percent_to_row_modifies_only_selected_fields():
    from core.ecf.variants import apply_percent_to_row
    row = _make_row()
    new_row = apply_percent_to_row(row, ["param1"], 100.0)
    assert new_row.get("param1") == "10"
    assert row.get("param1") == "5"  # source inchangee


def test_generate_block_variants_names_and_removes_id():
    block = _make_block()
    variants = generate_block_variants(block, "IronResource", 3, ["XpFactor"], 20.0, first_is_original=True)
    assert [v.get("Name") for v in variants] == ["IronResourceT1", "IronResourceT2", "IronResourceT3"]
    assert all(v.get("Id") is None for v in variants)


def _child_value(block, key):
    """Aide de test : cherche une valeur dans les proprietes enfants
    directes du bloc (EcfBlock.get() ne cherche QUE la ligne d'ouverture,
    pas les enfants -- voir core/ecf/variants.py::_get_block_field pour
    la meme logique utilisee par le code reel)."""
    for child in block.children:
        value = child.get(key)
        if value is not None:
            return value
    return None


def test_generate_block_variants_applies_percentage_to_child_property():
    block = _make_block()
    variants = generate_block_variants(block, "IronResource", 3, ["XpFactor"], 20.0, first_is_original=True)
    assert _child_value(variants[0], "XpFactor") == "2.0"
    assert _child_value(variants[1], "XpFactor") == "2.2"
    assert _child_value(variants[2], "XpFactor") == "2.4"


def test_generate_block_variants_untouched_fields_stay_identical():
    block = _make_block()
    variants = generate_block_variants(block, "IronResource", 3, ["XpFactor"], 20.0, first_is_original=True)
    assert all(_child_value(v, "Material") == "resourcesoft" for v in variants)
    assert all(_child_value(v, "Texture") == "173" for v in variants)


def test_generate_block_variants_does_not_mutate_source_block():
    block = _make_block()
    generate_block_variants(block, "IronResource", 3, ["XpFactor"], 20.0, first_is_original=True)
    assert block.get("Name") == "IronResource"
    assert _child_value(block, "XpFactor") == "2.0"


# ---------------------------------------------------------------------
# Variantes de ligne (mode tableau)
# ---------------------------------------------------------------------

def _make_row():
    text = (
        "{ Block Id: 1, Name: EscapePodEasy\n"
        "  Item_1: WaterBottle, param1: 5\n"
        "}\n"
    )
    doc = parse_ecf_text(text)
    block = next(doc.iter_blocks())
    return next(c for c in block.children if isinstance(c, EcfProperty))


def test_detect_numeric_fields_row_excludes_first_pair():
    row = _make_row()
    fields = detect_numeric_fields_row(row)
    assert fields == ["param1"]


def test_generate_row_variants_renames_first_pair_value():
    row = _make_row()
    variants = generate_row_variants(row, 3, ["param1"], 100.0, first_is_original=True)
    names = [v.pairs[0][1] for v in variants]
    assert names == ["WaterBottleT1", "WaterBottleT2", "WaterBottleT3"]
    # la cle du premier couple (Item_1) doit rester inchangee
    assert all(v.pairs[0][0] == "Item_1" for v in variants)


def test_generate_row_variants_applies_percentage():
    row = _make_row()
    variants = generate_row_variants(row, 3, ["param1"], 100.0, first_is_original=True)
    values = [v.get("param1") for v in variants]
    assert values == ["5", "8", "10"]


def test_generate_row_variants_does_not_mutate_source_row():
    row = _make_row()
    generate_row_variants(row, 3, ["param1"], 100.0, first_is_original=True)
    assert row.pairs[0][1] == "WaterBottle"
    assert row.get("param1") == "5"


def test_generate_row_variants_empty_pairs_returns_empty_list():
    empty_row = EcfProperty(raw="", indent="", pairs=[], comment=None, eol="\n")
    assert generate_row_variants(empty_row, 3, [], 20.0, True) == []


# ---------------------------------------------------------------------
# list_editable_fields_block -- apercu editable pendant la duplication
# (demande explicite de l'utilisateur, session du 29/08/2026)
# ---------------------------------------------------------------------

def test_list_editable_fields_block_excludes_id_and_name():
    block = _make_block()
    fields = list_editable_fields_block(block)
    keys = [k for k, v in fields]
    assert "Id" not in keys
    assert "Name" not in keys


def test_list_editable_fields_block_includes_text_and_numeric():
    block = _make_block()
    fields = dict(list_editable_fields_block(block))
    assert "Material" in fields  # texte
    assert "XpFactor" in fields  # numerique


def test_list_editable_fields_block_excludes_metadata_attributes():
    """'display'/'type'/'formatter' sont des attributs d'UNE AUTRE propriete
    sur la meme ligne (ex: 'HitPoints: 80, type: int, display: true'),
    jamais des champs autonomes -- ne doivent jamais apparaitre comme
    lignes editables independantes."""
    text = (
        "{ Block Id: 1, Name: Test\n"
        "  HitPoints: 80, type: int, display: true\n"
        "}\n"
    )
    doc = parse_ecf_text(text)
    block = next(doc.iter_blocks())
    fields = dict(list_editable_fields_block(block))
    assert "HitPoints" in fields
    assert "type" not in fields
    assert "display" not in fields


def test_list_editable_fields_block_reaches_nested_sub_blocks():
    block = _make_block_with_nested_child()
    fields = dict(list_editable_fields_block(block))
    assert "Prob" in fields
    assert fields["Prob"] == "0.5"
    assert "Item" in fields
    assert fields["Item"] == "SathiumOre"


def test_list_editable_fields_block_preserves_file_order():
    block = _make_block()
    fields = list_editable_fields_block(block)
    keys = [k for k, v in fields]
    assert keys.index("Material") < keys.index("XpFactor")


# ---------------------------------------------------------------------
# list_template_scalar_fields / list_template_ingredients /
# set_template_ingredient (demande explicite de l'utilisateur, session du
# 29/08/2026) -- edition individuelle des Templates + ajout d'ingredients
# ---------------------------------------------------------------------

def _make_template():
    text = (
        "{ Template Name: TestTemplate\n"
        "  CraftTime: 5\n"
        "  Target: \"SurvC\"\n"
        "  { Child Inputs\n"
        "    RockDust: 25\n"
        "  }\n"
        "}\n"
    )
    doc = parse_ecf_text(text)
    return next(doc.iter_blocks())


def test_list_template_scalar_fields_excludes_ingredients():
    from core.ecf.variants import list_template_scalar_fields
    fields = dict(list_template_scalar_fields(_make_template()))
    assert fields == {"CraftTime": "5", "Target": '"SurvC"'}
    assert "RockDust" not in fields


def test_list_template_ingredients_excludes_scalar_fields():
    from core.ecf.variants import list_template_ingredients
    ingredients = dict(list_template_ingredients(_make_template()))
    assert ingredients == {"RockDust": "25"}
    assert "CraftTime" not in ingredients


def test_list_template_ingredients_empty_when_no_child_inputs():
    from core.ecf.variants import list_template_ingredients
    text = "{ Template Name: Empty\n  CraftTime: 5\n}\n"
    doc = parse_ecf_text(text)
    tpl = next(doc.iter_blocks())
    assert list_template_ingredients(tpl) == []


def test_set_template_ingredient_updates_existing():
    from core.ecf.variants import set_template_ingredient, list_template_ingredients
    tpl = _make_template()
    set_template_ingredient(tpl, "RockDust", "99")
    assert dict(list_template_ingredients(tpl))["RockDust"] == "99"


def test_set_template_ingredient_adds_new_to_existing_child_inputs():
    from core.ecf.variants import set_template_ingredient, list_template_ingredients
    tpl = _make_template()
    set_template_ingredient(tpl, "Electronics", "4")
    ingredients = dict(list_template_ingredients(tpl))
    assert ingredients == {"RockDust": "25", "Electronics": "4"}


def test_set_template_ingredient_creates_child_inputs_when_absent():
    from core.ecf.variants import set_template_ingredient, list_template_ingredients
    text = "{ Template Name: Empty\n  CraftTime: 5\n}\n"
    doc = parse_ecf_text(text)
    tpl = next(doc.iter_blocks())
    set_template_ingredient(tpl, "Electronics", "4")
    assert dict(list_template_ingredients(tpl)) == {"Electronics": "4"}


def test_set_template_ingredient_round_trip_indentation_when_creating(): # bug reel corrige
    from core.ecf.variants import set_template_ingredient
    text = "{ Template Name: Empty\n  CraftTime: 5\n}\n"
    doc = parse_ecf_text(text)
    tpl = next(doc.iter_blocks())
    set_template_ingredient(tpl, "Electronics", "4")
    rendered = doc.render()
    assert "  { Child Inputs\n" in rendered
    assert "    Electronics: 4\n" in rendered
    assert "  }\n" in rendered


def test_set_template_ingredient_round_trip_when_existing_preserved():
    from core.ecf.variants import set_template_ingredient
    tpl = _make_template()
    set_template_ingredient(tpl, "RockDust", "99")
    set_template_ingredient(tpl, "Electronics", "4")
    doc = tpl  # deja le bloc, verifions juste que le rendu du DOCUMENT complet fonctionne
    from core.ecf.parser import parse_ecf_text as _p
    # reconstruit un doc autour pour tester le rendu complet
    wrapper_doc = _p("")
    wrapper_doc.nodes = [tpl]
    rendered = wrapper_doc.render()
    assert rendered == (
        "{ Template Name: TestTemplate\n"
        "  CraftTime: 5\n"
        "  Target: \"SurvC\"\n"
        "  { Child Inputs\n"
        "    RockDust: 99\n"
        "    Electronics: 4\n"
        "  }\n"
        "}\n"
    )
