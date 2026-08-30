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

from gui.template_adjust_dialog import TemplateAdjustDialog


def _make_dialog(names):
    return TemplateAdjustDialog(
        names, [("CraftTime", "5")], [("RockDust", "25")], ["Electronics", "RockDust"],
        property_pool=["CraftTime", "OutputCount"],
        values_by_key={"CraftTime": ["5", "10"], "OutputCount": ["1"]},
        common_quantities=["25", "10"])


def test_one_tab_per_template_name(qapp):
    dialog = _make_dialog(["T1", "T2", "T3"])
    assert dialog.tabs.count() == 3
    assert [dialog.tabs.tabText(i) for i in range(3)] == ["T1", "T2", "T3"]


def test_get_entries_empty_when_no_changes(qapp):
    dialog = _make_dialog(["T1", "T2"])
    assert dialog.get_entries() == {}


def test_editing_one_tab_does_not_affect_others(qapp):
    """Coeur de la demande explicite (29/08/2026) : edition INDIVIDUELLE,
    pas uniforme."""
    dialog = _make_dialog(["T1", "T2"])
    dialog._editors["T1"].scalar_table.cellWidget(0, 1).setCurrentText("10")

    entries = dialog.get_entries()
    assert "T1" in entries
    assert "T2" not in entries
    assert entries["T1"]["scalar"] == {"CraftTime": "10"}


def test_adding_ingredient_to_one_tab_only(qapp):
    dialog = _make_dialog(["T1", "T2"])
    editor = dialog._editors["T1"]
    editor.ingredient_combo.setCurrentText("Electronics")
    editor.quantity_combo.setCurrentText("4")
    editor._on_add_ingredient()

    entries = dialog.get_entries()
    assert entries["T1"]["ingredients"] == {"Electronics": "4"}
    assert "T2" not in entries


def test_different_changes_per_tab(qapp):
    dialog = _make_dialog(["T1", "T2"])
    dialog._editors["T1"].scalar_table.cellWidget(0, 1).setCurrentText("10")
    dialog._editors["T2"].ingredients_table.cellWidget(0, 1).setCurrentText("99")

    entries = dialog.get_entries()
    assert entries["T1"] == {"scalar": {"CraftTime": "10"}, "ingredients": {},
                             "removed": [], "removed_scalars": []}
    assert entries["T2"] == {"scalar": {}, "ingredients": {"RockDust": "99"},
                             "removed": [], "removed_scalars": []}


def test_removed_property_reported_per_tab(qapp):
    """Demande du 30/08/2026 : le Template de base contient TOUTES les
    proprietes des autres Templates -- l'onglet doit permettre d'en SUPPRIMER
    et le resultat doit le signaler ('removed_scalars')."""
    dialog = _make_dialog(["T1", "T2"])
    dialog._editors["T1"].scalar_table.selectRow(0)
    dialog._editors["T1"]._on_remove_scalar()

    entries = dialog.get_entries()
    assert entries["T1"]["removed_scalars"] == ["CraftTime"]
    assert "T2" not in entries


def test_added_property_reported_per_tab(qapp):
    dialog = _make_dialog(["T1"])
    editor = dialog._editors["T1"]
    editor.property_combo.setCurrentText("OutputCount")
    editor.new_value_combo.setCurrentText("1")
    editor._on_add_scalar()

    entries = dialog.get_entries()
    assert entries["T1"]["scalar"] == {"OutputCount": "1"}


def test_single_template_name(qapp):
    dialog = _make_dialog(["OnlyOne"])
    assert dialog.tabs.count() == 1
    dialog._editors["OnlyOne"].scalar_table.cellWidget(0, 1).setCurrentText("20")
    assert dialog.get_entries() == {"OnlyOne": {"scalar": {"CraftTime": "20"},
                                                "ingredients": {}, "removed": [],
                                                "removed_scalars": []}}
