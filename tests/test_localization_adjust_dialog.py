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

from PyQt6.QtCore import Qt

from gui.localization_adjust_dialog import LocalizationAdjustDialog


def test_populates_one_row_per_new_name(qapp):
    dlg = LocalizationAdjustDialog(["T1", "T2", "T3"], ("Fer", "Iron"))
    assert dlg.table.rowCount() == 3
    for row in range(3):
        assert dlg.table.item(row, 1).text() == "Fer"
        assert dlg.table.item(row, 2).text() == "Iron"


def test_name_column_not_editable(qapp):
    dlg = LocalizationAdjustDialog(["T1"], ("Fer", "Iron"))
    assert not (dlg.table.item(0, 0).flags() & Qt.ItemFlag.ItemIsEditable)


def test_get_entries_returns_all_prefilled_by_default(qapp):
    dlg = LocalizationAdjustDialog(["T1", "T2"], ("Fer", "Iron"))
    entries = dlg.get_entries()
    assert entries == {
        "T1": {"Français": "Fer", "English": "Iron"},
        "T2": {"Français": "Fer", "English": "Iron"},
    }


def test_get_entries_reflects_per_row_edits_independently(qapp):
    """Chaque variante garde SA PROPRE traduction -- contrairement au
    tableau de proprietes du bloc, pas d'application uniforme ici."""
    dlg = LocalizationAdjustDialog(["T1", "T2"], ("Fer", "Iron"))
    dlg.table.item(0, 1).setText("Fer T1")
    dlg.table.item(1, 1).setText("Fer T2")

    entries = dlg.get_entries()
    assert entries["T1"]["Français"] == "Fer T1"
    assert entries["T2"]["Français"] == "Fer T2"


def test_get_entries_excludes_fully_emptied_rows(qapp):
    """Vider completement les deux colonnes d'une ligne = 'je ne veux pas
    d'entree pour celle-ci' -- exclue du resultat."""
    dlg = LocalizationAdjustDialog(["T1", "T2"], ("Fer", "Iron"))
    dlg.table.item(0, 1).setText("")
    dlg.table.item(0, 2).setText("")

    entries = dlg.get_entries()
    assert "T1" not in entries
    assert "T2" in entries


def test_get_entries_keeps_row_with_only_one_language_filled(qapp):
    dlg = LocalizationAdjustDialog(["T1"], ("Fer", "Iron"))
    dlg.table.item(0, 2).setText("")  # anglais vide, francais garde

    entries = dlg.get_entries()
    assert entries["T1"]["Français"] == "Fer"
    assert entries["T1"]["English"] == ""


def test_single_name(qapp):
    dlg = LocalizationAdjustDialog(["OnlyOne"], ("Source FR", "Source EN"))
    assert dlg.table.rowCount() == 1
    assert dlg.get_entries() == {"OnlyOne": {"Français": "Source FR", "English": "Source EN"}}
