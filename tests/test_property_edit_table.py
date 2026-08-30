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

from gui.property_edit_table import PropertyEditTable


def test_populates_rows_from_fields(qapp):
    table = PropertyEditTable([("Material", "resourcehard"), ("XpFactor", "6.0")])
    assert table.rowCount() == 2
    assert table.item(0, 0).text() == "Material"
    assert table.item(0, 1).text() == "resourcehard"
    assert table.item(1, 0).text() == "XpFactor"
    assert table.item(1, 1).text() == "6.0"


def test_key_column_not_editable(qapp):
    from PyQt6.QtCore import Qt
    table = PropertyEditTable([("Material", "resourcehard")])
    assert not (table.item(0, 0).flags() & Qt.ItemFlag.ItemIsEditable)


def test_value_column_editable(qapp):
    from PyQt6.QtCore import Qt
    table = PropertyEditTable([("Material", "resourcehard")])
    assert table.item(0, 1).flags() & Qt.ItemFlag.ItemIsEditable


def test_get_changed_values_empty_when_untouched(qapp):
    table = PropertyEditTable([("Material", "resourcehard"), ("XpFactor", "6.0")])
    assert table.get_changed_values() == {}


def test_get_changed_values_only_includes_actually_changed(qapp):
    table = PropertyEditTable([("Material", "resourcehard"), ("XpFactor", "6.0")])
    table.item(1, 1).setText("12.0")
    assert table.get_changed_values() == {"XpFactor": "12.0"}


def test_get_changed_values_retyping_same_value_not_counted(qapp):
    """Retaper exactement la meme valeur ne doit pas la faire apparaitre
    comme 'changee' -- voir docstring du module."""
    table = PropertyEditTable([("Material", "resourcehard")])
    table.item(0, 1).setText("resourcehard")
    assert table.get_changed_values() == {}


def test_empty_fields_list(qapp):
    table = PropertyEditTable([])
    assert table.rowCount() == 0
    assert table.get_changed_values() == {}
