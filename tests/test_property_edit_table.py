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


# ------------------------------------------------ values_by_key (30/08/2026)
def test_values_by_key_creates_editable_dropdown(qapp):
    """Demande du 30/08/2026 : liste deroulante PARTOUT ou c'est possible --
    les valeurs observees dans le fichier pre-remplissent la cellule."""
    from gui.property_edit_table import PropertyEditTable
    table = PropertyEditTable([("Material", "resourcehard")],
                              values_by_key={"Material": ["resourcehard", "metal", "wood"]})
    combo = table.cellWidget(0, 1)
    assert combo is not None
    assert [combo.itemText(i) for i in range(combo.count())] == ["resourcehard", "metal", "wood"]
    assert combo.currentText() == "resourcehard"
    assert table.get_changed_values() == {}


def test_values_by_key_change_detected_via_dropdown(qapp):
    from gui.property_edit_table import PropertyEditTable
    table = PropertyEditTable([("Material", "resourcehard")],
                              values_by_key={"Material": ["resourcehard", "metal"]})
    table.cellWidget(0, 1).setCurrentText("metal")
    assert table.get_changed_values() == {"Material": "metal"}


def test_unknown_key_stays_free_text_cell(qapp):
    """Une cle absente du pool garde la saisie libre classique."""
    from gui.property_edit_table import PropertyEditTable
    table = PropertyEditTable([("Material", "resourcehard"), ("Obscure", "x")],
                              values_by_key={"Material": ["resourcehard"]})
    assert table.cellWidget(0, 1) is not None
    assert table.cellWidget(1, 1) is None
    table.item(1, 1).setText("y")
    assert table.get_changed_values() == {"Obscure": "y"}
