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
ajout ET suppression d'ingredients dans tous les modes. Etendu le 30/08
(demande explicite) : le Template de base doit contenir TOUTES les
proprietes presentes sur les autres Templates (pas seulement CraftTime/
Target), avec suppression de propriete (remove_template_scalar) et pools de
valeurs/quantites courantes pour les listes deroulantes."""
from core.ecf.parser import parse_ecf_text
from core.ecf.block_creation import scan_template_defaults, create_new_block, add_child_inputs
from core.ecf.variants import (
    remove_template_ingredient, list_template_ingredients, set_template_ingredient,
    remove_template_scalar, list_template_scalar_fields,
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
  OutputCount: 2
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


def test_defaults_include_ALL_properties_from_other_templates():
    """Demande explicite du 30/08/2026 : le Template de base doit contenir
    TOUTES les proprietes observees sur les autres Templates -- OutputCount
    n'existe que sur 'Pere' mais doit ETRE dans le pre-remplissage."""
    defaults = scan_template_defaults(make_templates_doc())
    scalars = dict(defaults["scalars"])
    assert "OutputCount" in scalars
    assert scalars["OutputCount"] == "2"


def test_defaults_scalar_keys_explicit_keeps_only_those():
    """Compatibilite : une liste de cles explicite filtre le resultat."""
    defaults = scan_template_defaults(make_templates_doc(),
                                      scalar_keys=("CraftTime",))
    assert [k for k, _v in defaults["scalars"]] == ["CraftTime"]


def test_defaults_values_by_key_for_dropdowns():
    defaults = scan_template_defaults(make_templates_doc())
    assert defaults["values_by_key"]["CraftTime"] == ["30", "10"]
    assert set(defaults["values_by_key"]["Target"]) == {'"BaseC"', '"AdvC,LargeC"'}


def test_defaults_quantities_for_dropdowns():
    defaults = scan_template_defaults(make_templates_doc())
    # Toutes les quantites observees, triees par frequence decroissante
    # (5 observe 2x : SteelPlate dans Fusil ET Pere).
    assert defaults["quantities"][0] == "5"
    assert set(defaults["quantities"]) == {"5", "2", "10", "3", "4"}


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


# ------------------------------------------------- remove_template_scalar
def test_remove_template_scalar_property_line():
    doc = parse_ecf_text("{ Template Name: X\n  CraftTime: 5\n  Target: BaseC\n}\n")
    template = next(doc.iter_blocks())
    assert remove_template_scalar(template, "CraftTime") is True
    keys = [k for k, _v in list_template_scalar_fields(template)]
    assert keys == ["Target"]
    assert remove_template_scalar(template, "CraftTime") is False  # deja retire


def test_remove_template_scalar_never_touches_child_inputs():
    """Les ingredients vivent dans Child Inputs : remove_template_scalar ne
    doit JAMAIS y descendre (retrait dedie = remove_template_ingredient)."""
    doc = make_templates_doc()
    template = next(b for b in doc.iter_blocks() if b.get_property('Name') == "Fusil")
    assert remove_template_scalar(template, "SteelPlate") is False
    assert "SteelPlate" in dict(list_template_ingredients(template))


def test_remove_template_scalar_multi_pair_line_keeps_other_pairs():
    # NB : list_template_scalar_fields n'expose que la PREMIERE paire de
    # chaque ligne enfant -- on verifie ici que le retrait d'une paire
    # suivante preserve la premiere (et ne supprime pas la ligne entiere).
    doc = parse_ecf_text("{ Template Name: X\n  Item: SteelPlate, Count: 5\n}\n")
    template = next(doc.iter_blocks())
    assert remove_template_scalar(template, "Count") is True
    assert dict(list_template_scalar_fields(template)) == {"Item": "SteelPlate"}
    assert remove_template_scalar(template, "Count") is False  # deja retire


def test_remove_template_scalar_header_pair():
    doc = parse_ecf_text("{ Template Name: X, Class: Foo\n  CraftTime: 5\n}\n")
    template = next(doc.iter_blocks())
    assert remove_template_scalar(template, "Class") is True
    assert template.get("Class") is None


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
    """Le cas 'pas de source' : bloc de base depuis les valeurs courantes
    (avec TOUTES les proprietes des autres Templates), puis ajustements
    (changement scalaire, ingredient modifie/ajoute/retire)."""
    doc = make_templates_doc()
    defaults = scan_template_defaults(doc)
    template = create_new_block(defaults["kind"], None, "MaVariante",
                                 list(defaults["scalars"]))
    add_child_inputs(template, list(defaults["ingredients"]))
    # Simule les entries du TemplateAdjustDialog
    from core.ecf.variants import set_block_field
    for key, value in {"CraftTime": "12"}.items():
        set_block_field(template, key, value)
    set_template_ingredient(template, "Electronics", "7")   # modifie la qté courante
    remove_template_ingredient(template, "Concrete")         # retire un pre-rempli
    scalars = dict(list_template_scalar_fields(template))
    assert scalars["CraftTime"] == "12"
    assert "OutputCount" in scalars  # herite des autres Templates
    ingredients = dict(list_template_ingredients(template))
    assert ingredients.get("Electronics") == "7"
    assert "Concrete" not in ingredients
    assert template.get('Name') == "MaVariante"


def test_create_from_defaults_then_remove_scalar_property():
    """Le cas 'suppression d'une propriete pre-remplie' (removed_scalars du
    TemplateAdjustDialog) : la propriete retiree ne doit plus figurer nulle
    part sur le Template cree."""
    doc = make_templates_doc()
    defaults = scan_template_defaults(doc)
    template = create_new_block(defaults["kind"], None, "SansOutput",
                                 list(defaults["scalars"]))
    remove_template_scalar(template, "OutputCount")
    remove_template_scalar(template, "Target")
    scalars = dict(list_template_scalar_fields(template))
    assert "OutputCount" not in scalars
    assert "Target" not in scalars
    assert scalars["CraftTime"] == "30"


# --------------------------------- separation scalaires / Child Inputs
# (bug signale par l'utilisateur le 30/08/2026 : iter_blocks est RECURSIF,
# les ingredients des Child Inputs polluaient les proprietes scalaires du
# Template de base -- et reciproquement)

def test_defaults_scalars_never_contain_ingredient_names():
    """Les noms d'ingredients (Child Inputs) ne doivent JAMAIS apparaitre
    dans les proprietes scalaires du Template de base."""
    defaults = scan_template_defaults(make_templates_doc())
    scalar_keys = {k for k, _v in defaults["scalars"]}
    assert "SteelPlate" not in scalar_keys
    assert "Electronics" not in scalar_keys
    assert "Concrete" not in scalar_keys
    assert "SteelPlate" not in defaults["values_by_key"]


def test_defaults_ingredients_never_contain_scalar_properties():
    """Sens inverse : les proprietes scalaires (CraftTime, Target...) ne
    doivent JAMAIS apparaitre dans les ingredients pre-remplis."""
    defaults = scan_template_defaults(make_templates_doc())
    ingredient_names = {name for name, _qty in defaults["ingredients"]}
    assert "CraftTime" not in ingredient_names
    assert "Target" not in ingredient_names
    assert "OutputCount" not in ingredient_names


def test_defaults_ingredient_values_by_key_per_ingredient():
    """Quantites observees PER-INGREDIENT, pour les listes deroulantes de
    quantite -- separees des valeurs des proprietes scalaires."""
    defaults = scan_template_defaults(make_templates_doc())
    per_ingredient = defaults["ingredient_values_by_key"]
    assert per_ingredient["SteelPlate"] == ["5"]
    assert per_ingredient["Electronics"] == ["2", "4"]
    assert "CraftTime" not in per_ingredient  # pas de scalaire ici
