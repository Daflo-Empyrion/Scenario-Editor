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

"""Creation de Templates depuis une source OU depuis les valeurs les plus
courantes (gui/template_tools.py + scan_template_defaults +
remove_template_ingredient) -- demande du 30/08/2026 : pouvoir doter d'une
recette un bloc cree/duplique/fusionne qui n'en avait pas d'origine, avec
ajout ET suppression d'ingredients dans tous les modes."""
from core.ecf.parser import parse_ecf_text
from core.ecf.block_creation import scan_template_defaults, create_new_block, add_child_inputs
from core.ecf.variants import (
    remove_template_ingredient, list_template_ingredients, set_template_ingredient,
)

TEMPLATES_TEXT = """
{ Template Name: Fusil
  CraftTime: 10
  Target: "AdvC,LargeC"
  { Child Inputs
    SteelPlate: 5
    Electronics: 2
  }
}

{ Template Name: Pere
  CraftTime: 30
  Target: "BaseC"
  { Child Inputs
    SteelPlate: 5
    Concrete: 10
    Glass: 3
  }
}

{ Template Name: Mere
  CraftTime: 30
  Target: "BaseC"
  { Child Inputs
    Electronics: 4
  }
}
"""


def make_templates_doc():
    return parse_ecf_text(TEMPLATES_TEXT)


# ------------------------------------------------- scan_template_defaults
def test_defaults_most_common_scalars():
    defaults = scan_template_defaults(make_templates_doc())
    # CraftTime le plus frequent : 30 (2/3) ; Target le plus frequent : BaseC
    scalars = dict(defaults["scalars"])
    assert scalars["CraftTime"] == "30"
    assert scalars["Target"] == '"BaseC"' or scalars["Target"] == "BaseC"


def test_defaults_most_common_ingredients_with_qty():
    defaults = scan_template_defaults(make_templates_doc())
    ingredients = dict(defaults["ingredients"])
    # SteelPlate present dans 2 templates sur 3 : l'ingredient le plus frequent,
    # avec sa quantite LA PLUS COMMUNE (5, pas 2).
    assert list(ingredients)[0] == "SteelPlate"
    assert ingredients["SteelPlate"] == "5"


def test_defaults_empty_doc_returns_none():
    doc = parse_ecf_text("# rien\n")
    assert scan_template_defaults(doc) is None


def test_defaults_kind_most_frequent():
    defaults = scan_template_defaults(make_templates_doc())
    assert defaults["kind"] == "Template"


# ------------------------------------------------- remove_template_ingredient
def test_remove_template_ingredient():
    doc = make_templates_doc()
    template = next(b for b in doc.iter_blocks() if b.get_property('Name') == "Fusil")
    assert remove_template_ingredient(template, "SteelPlate") is True
    assert "SteelPlate" not in dict(list_template_ingredients(template))
    assert remove_template_ingredient(template, "SteelPlate") is False  # deja retire
    # Les autres ingredients restent intacts
    assert "Electronics" in dict(list_template_ingredients(template))


def test_remove_on_template_without_inputs_returns_false():
    doc = parse_ecf_text("{ Template Name: Vide\n  CraftTime: 5\n}\n")
    template = doc.iter_blocks().__next__()
    assert remove_template_ingredient(template, "SteelPlate") is False


def test_set_then_remove_roundtrip():
    doc = make_templates_doc()
    template = next(b for b in doc.iter_blocks() if b.get_property('Name') == "Fusil")
    set_template_ingredient(template, "Cobblestone", "9")
    assert "Cobblestone" in dict(list_template_ingredients(template))
    remove_template_ingredient(template, "Cobblestone")
    assert "Cobblestone" not in dict(list_template_ingredients(template))


# --------------------------------------- creation from scratch + entries
def test_create_from_defaults_then_apply_entries():
    """Le cas 'pas de source' : bloc de base depuis les valeurs courantes,
    puis ajustements (changement scalaire, ingredient modifie/ajoute/retire)."""
    doc = make_templates_doc()
    defaults = scan_template_defaults(doc)
    template = create_new_block(defaults["kind"], None, "MaVariante",
                                 list(defaults["scalars"]))
    add_child_inputs(template, list(defaults["ingredients"]))
    # Simule les entries du TemplateAdjustDialog
    for key, value in {"CraftTime": "12"}.items():
        from core.ecf.variants import set_block_field
        set_block_field(template, key, value)
    set_template_ingredient(template, "Electronics", "7")   # modifie la qté courante
    remove_template_ingredient(template, "Concrete")         # retire un pre-rempli
    from core.ecf.variants import list_template_scalar_fields
    scalars = dict(list_template_scalar_fields(template))
    assert scalars["CraftTime"] == "12"
    ingredients = dict(list_template_ingredients(template))
    assert ingredients.get("Electronics") == "7"
    assert "Concrete" not in ingredients
    assert template.get('Name') == "MaVariante"
