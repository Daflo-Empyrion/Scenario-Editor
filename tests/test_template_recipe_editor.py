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

from gui.template_recipe_editor import TemplateRecipeEditor


def _make_editor():
    return TemplateRecipeEditor(
        [("CraftTime", "5"), ("Target", "SurvC")],
        [("RockDust", "25")],
        ["Electronics", "CobaltAlloy", "RockDust", "PlasticMaterial"])


def test_no_changes_returns_empty(qapp):
    editor = _make_editor()
    assert editor.get_scalar_overrides() == {}
    assert editor.get_changed_or_added_ingredients() == {}


def test_scalar_field_change_detected(qapp):
    editor = _make_editor()
    editor.scalar_table.item(0, 1).setText("10")
    assert editor.get_scalar_overrides() == {"CraftTime": "10"}


def test_existing_ingredient_quantity_change_detected(qapp):
    editor = _make_editor()
    editor.ingredients_table.item(0, 1).setText("50")
    assert editor.get_changed_or_added_ingredients() == {"RockDust": "50"}


def test_ingredient_name_column_not_editable(qapp):
    from PyQt6.QtCore import Qt
    editor = _make_editor()
    assert not (editor.ingredients_table.item(0, 0).flags() & Qt.ItemFlag.ItemIsEditable)


def test_add_new_ingredient_via_dropdown(qapp):
    editor = _make_editor()
    editor.ingredient_combo.setCurrentText("Electronics")
    editor.quantity_edit.setText("4")
    editor._on_add_ingredient()

    assert editor.ingredients_table.rowCount() == 2
    assert editor.get_changed_or_added_ingredients() == {"Electronics": "4"}


def test_adding_existing_ingredient_name_updates_quantity_instead_of_duplicating(qapp):
    """Ajouter un ingredient DEJA present (meme nom) doit mettre a jour sa
    quantite plutot que creer une ligne en double."""
    editor = _make_editor()
    editor.ingredient_combo.setCurrentText("RockDust")
    editor.quantity_edit.setText("77")
    editor._on_add_ingredient()

    assert editor.ingredients_table.rowCount() == 1
    assert editor.get_changed_or_added_ingredients() == {"RockDust": "77"}


def test_add_ingredient_clears_input_fields_after(qapp):
    editor = _make_editor()
    editor.ingredient_combo.setCurrentText("Electronics")
    editor.quantity_edit.setText("4")
    editor._on_add_ingredient()

    assert editor.ingredient_combo.currentText() == ""
    assert editor.quantity_edit.text() == "1"


def test_add_ingredient_with_empty_name_does_nothing(qapp):
    editor = _make_editor()
    editor.ingredient_combo.setCurrentText("")
    editor.quantity_edit.setText("4")
    editor._on_add_ingredient()

    assert editor.ingredients_table.rowCount() == 1  # inchange


def test_empty_template_starts_with_no_ingredient_rows(qapp):
    editor = TemplateRecipeEditor([("CraftTime", "5")], [], ["Electronics"])
    assert editor.ingredients_table.rowCount() == 0
    editor.ingredient_combo.setCurrentText("Electronics")
    editor.quantity_edit.setText("2")
    editor._on_add_ingredient()
    assert editor.get_changed_or_added_ingredients() == {"Electronics": "2"}
