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

"""TemplateRecipeEditor -- champ par champ. Etendu le 30/08/2026 (demande
explicite) : AJOUT d'une propriete scalaire via liste deroulante des noms
observes sur les autres Templates, VALEURS en liste deroulante des valeurs
courantes, QUANTITES d'ingredients en liste deroulante, SUPPRESSION de
propriete (bouton) -- la liste deroulante partout ou c'est possible."""
from gui.template_recipe_editor import TemplateRecipeEditor


def _make_editor():
    return TemplateRecipeEditor(
        [("CraftTime", "5"), ("Target", "SurvC")],
        [("RockDust", "25")],
        ["Electronics", "CobaltAlloy", "RockDust", "PlasticMaterial"],
        property_pool=["CraftTime", "Target", "OutputCount", "Group"],
        values_by_key={
            "CraftTime": ["5", "10", "30"],
            "Target": ["SurvC", "BaseC", "LargeC"],
            "OutputCount": ["1", "5"],
            "Group": ["Ammo", "Weapons"],
        },
        common_quantities=["25", "10", "5", "1"])


def test_no_changes_returns_empty(qapp):
    editor = _make_editor()
    assert editor.get_scalar_overrides() == {}
    assert editor.get_changed_or_added_ingredients() == {}
    assert editor.get_removed_scalars() == []
    assert editor.get_removed_ingredients() == []


def test_scalar_field_change_detected(qapp):
    editor = _make_editor()
    editor.scalar_table.cellWidget(0, 1).setCurrentText("10")
    assert editor.get_scalar_overrides() == {"CraftTime": "10"}


def test_existing_ingredient_quantity_change_detected(qapp):
    editor = _make_editor()
    editor.ingredients_table.cellWidget(0, 1).setCurrentText("50")
    assert editor.get_changed_or_added_ingredients() == {"RockDust": "50"}


def test_ingredient_name_column_not_editable(qapp):
    from PyQt6.QtCore import Qt
    editor = _make_editor()
    assert not (editor.ingredients_table.item(0, 0).flags() & Qt.ItemFlag.ItemIsEditable)


def test_scalar_name_column_not_editable(qapp):
    from PyQt6.QtCore import Qt
    editor = _make_editor()
    assert not (editor.scalar_table.item(0, 0).flags() & Qt.ItemFlag.ItemIsEditable)


def test_value_cells_are_dropdowns_of_common_values(qapp):
    """Demande du 30/08/2026 : liste deroulante des valeurs les plus
    courantes, y compris pour les proprietes DEJA presentes dans le tableau."""
    editor = _make_editor()
    craft_combo = editor.scalar_table.cellWidget(0, 1)
    assert craft_combo.currentText() == "5"
    items = [craft_combo.itemText(i) for i in range(craft_combo.count())]
    assert items == ["5", "10", "30"]


def test_add_property_dropdown_excludes_existing_and_keeps_frequency_order(qapp):
    """La liste deroulante de noms propose les proprietes des autres
    Templates, triees par frequence, SANS celles deja affichees."""
    editor = _make_editor()
    items = [editor.property_combo.itemText(i) for i in range(editor.property_combo.count())]
    assert "OutputCount" in items and "Group" in items
    assert "CraftTime" not in items and "Target" not in items


def test_value_dropdown_follows_selected_property(qapp):
    editor = _make_editor()
    editor.property_combo.setCurrentText("OutputCount")
    items = [editor.new_value_combo.itemText(i) for i in range(editor.new_value_combo.count())]
    assert items == ["1", "5"]


def test_add_new_property_via_dropdowns(qapp):
    editor = _make_editor()
    editor.property_combo.setCurrentText("OutputCount")
    editor.new_value_combo.setCurrentText("5")
    editor._on_add_scalar()

    assert editor.get_scalar_overrides() == {"OutputCount": "5"}
    # La propriete ajoutee quitte la liste deroulante (deja affichee).
    items = [editor.property_combo.itemText(i) for i in range(editor.property_combo.count())]
    assert "OutputCount" not in items


def test_add_existing_property_name_updates_value_instead_of_duplicating(qapp):
    editor = _make_editor()
    editor.property_combo.setCurrentText("CraftTime")  # tapee a la main (absente de la liste)
    editor.new_value_combo.setCurrentText("30")
    editor._on_add_scalar()

    assert editor.scalar_table.rowCount() == 2  # pas de ligne en double
    assert editor.get_scalar_overrides() == {"CraftTime": "30"}


def test_add_property_with_empty_value_does_nothing(qapp):
    editor = _make_editor()
    editor.property_combo.setCurrentText("OutputCount")
    editor.new_value_combo.setCurrentText("")
    editor._on_add_scalar()
    assert editor.scalar_table.rowCount() == 2


def test_remove_property_tracked_and_reoffered(qapp):
    editor = _make_editor()
    editor.scalar_table.selectRow(1)  # Target
    editor._on_remove_scalar()

    assert editor.get_removed_scalars() == ["Target"]
    # La propriete retiree retourne dans la liste d'ajout : elle existe dans
    # le fichier, on doit pouvoir revenir en arriere.
    items = [editor.property_combo.itemText(i) for i in range(editor.property_combo.count())]
    assert "Target" in items
    assert editor.get_scalar_overrides() == {}


def test_remove_added_property_reoffers_it(qapp):
    editor = _make_editor()
    editor.property_combo.setCurrentText("OutputCount")
    editor.new_value_combo.setCurrentText("2")
    editor._on_add_scalar()
    editor.scalar_table.selectRow(2)  # OutputCount, ligne ajoutee
    editor._on_remove_scalar()

    assert editor.get_removed_scalars() == []
    assert editor.get_scalar_overrides() == {}
    items = [editor.property_combo.itemText(i) for i in range(editor.property_combo.count())]
    assert "OutputCount" in items  # de nouveau proposee


def test_quantity_dropdown_prefilled_with_common_quantities(qapp):
    editor = _make_editor()
    items = [editor.quantity_combo.itemText(i) for i in range(editor.quantity_combo.count())]
    assert items == ["25", "10", "5", "1"]
    assert editor.quantity_combo.currentText() == "1"


def test_add_new_ingredient_via_dropdown(qapp):
    editor = _make_editor()
    editor.ingredient_combo.setCurrentText("Electronics")
    editor.quantity_combo.setCurrentText("4")
    editor._on_add_ingredient()

    assert editor.ingredients_table.rowCount() == 2
    assert editor.get_changed_or_added_ingredients() == {"Electronics": "4"}


def test_adding_existing_ingredient_name_updates_quantity_instead_of_duplicating(qapp):
    """Ajouter un ingredient DEJA present (meme nom) doit mettre a jour sa
    quantite plutot que creer une ligne en double."""
    editor = _make_editor()
    editor.ingredient_combo.setCurrentText("RockDust")
    editor.quantity_combo.setCurrentText("77")
    editor._on_add_ingredient()

    assert editor.ingredients_table.rowCount() == 1
    assert editor.get_changed_or_added_ingredients() == {"RockDust": "77"}


def test_add_ingredient_clears_input_fields_after(qapp):
    editor = _make_editor()
    editor.ingredient_combo.setCurrentText("Electronics")
    editor.quantity_combo.setCurrentText("4")
    editor._on_add_ingredient()

    assert editor.ingredient_combo.currentText() == ""
    assert editor.quantity_combo.currentText() == "1"


def test_add_ingredient_with_empty_name_does_nothing(qapp):
    editor = _make_editor()
    editor.ingredient_combo.setCurrentText("")
    editor.quantity_combo.setCurrentText("4")
    editor._on_add_ingredient()

    assert editor.ingredients_table.rowCount() == 1  # inchange


def test_empty_template_starts_with_no_ingredient_rows(qapp):
    editor = TemplateRecipeEditor([("CraftTime", "5")], [], ["Electronics"])
    assert editor.ingredients_table.rowCount() == 0
    editor.ingredient_combo.setCurrentText("Electronics")
    editor.quantity_combo.setCurrentText("2")
    editor._on_add_ingredient()
    assert editor.get_changed_or_added_ingredients() == {"Electronics": "2"}


def test_works_without_optional_pools(qapp):
    """Appel minimal (compatibilite anciens appelants) : pas de liste de
    valeurs, la combo reste editable et affiche la valeur de depart."""
    editor = TemplateRecipeEditor([("CraftTime", "5")], [], ["Electronics"])
    combo = editor.scalar_table.cellWidget(0, 1)
    assert combo.currentText() == "5"
    assert combo.count() == 0
    assert editor.property_combo.count() == 0  # pool vide : pas de proposition
    # ... mais JAMAIS une liste vide sans explication (retour du 30/08/2026)
    from core.i18n import t
    assert editor.property_combo.placeholderText() == t("dup.property_add_empty")


def test_property_pool_explains_why_empty_when_base_has_everything(qapp):
    """Flux 'sans Template source' : le bloc de base possede DEJA toutes les
    proprietes observees du fichier -- la liste d'ajout est vide ET le
    placeholder l'explique."""
    editor = TemplateRecipeEditor(
        [("CraftTime", "5"), ("Target", "BaseC")], [], ["RockDust"],
        property_pool=["CraftTime", "Target"])
    assert editor.property_combo.count() == 0
    from core.i18n import t
    assert editor.property_combo.placeholderText() == t("dup.property_add_empty")


def test_property_pool_lists_only_file_properties(qapp):
    """Le pool ne contient QUE des proprietes du fichier Templates.ecf --
    jamais les proprietes des fichiers blocs/items (demande explicite du
    30/08/2026)."""
    editor = TemplateRecipeEditor(
        [("CraftTime", "5")], [], ["RockDust"],
        property_pool=["CraftTime", "Target", "OutputCount"])
    items = [editor.property_combo.itemText(i) for i in range(editor.property_combo.count())]
    assert items == ["Target", "OutputCount"]
    from core.i18n import t
    assert editor.property_combo.placeholderText() == t("dup.property_add_placeholder")


# ----------------------------- separation scalaires / ingredients (30/08)
def test_ingredient_quantity_combo_uses_per_ingredient_values(qapp):
    """La colonne quantite propose les quantites observees pour CET
    ingredient, pas les valeurs des proprietes scalaires."""
    editor = TemplateRecipeEditor(
        [("CraftTime", "5")],
        [("RockDust", "25"), ("Electronics", "2")],
        ["RockDust", "Electronics"],
        values_by_key={"CraftTime": ["5", "10"]},
        ingredient_values_by_key={"RockDust": ["25", "50"], "Electronics": ["2", "4"]})
    rock_combo = editor.ingredients_table.cellWidget(0, 1)
    elec_combo = editor.ingredients_table.cellWidget(1, 1)
    assert [rock_combo.itemText(i) for i in range(rock_combo.count())] == ["25", "50"]
    assert [elec_combo.itemText(i) for i in range(elec_combo.count())] == ["2", "4"]


def test_ingredient_quantity_combo_falls_back_to_common_quantities(qapp):
    """Ingredient sans historique : repli sur les quantites courantes
    globales du fichier."""
    editor = TemplateRecipeEditor(
        [("CraftTime", "5")], [("RockDust", "25")], ["RockDust"],
        common_quantities=["25", "10"], ingredient_values_by_key={})
    combo = editor.ingredients_table.cellWidget(0, 1)
    assert [combo.itemText(i) for i in range(combo.count())] == ["25", "10"]


def test_property_pool_never_receives_ingredient_names(qapp):
    """La liste deroulante d'ajout de propriete ne propose JAMAIS un nom
    d'ingredient (separation stricte demandee le 30/08/2026)."""
    editor = TemplateRecipeEditor(
        [("CraftTime", "5")], [("RockDust", "25")], ["RockDust"],
        property_pool=["CraftTime", "Target"],
        values_by_key={"CraftTime": ["5"], "Target": ["BaseC"]})
    items = [editor.property_combo.itemText(i) for i in range(editor.property_combo.count())]
    assert "RockDust" not in items
