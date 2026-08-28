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

"""Tests du glossaire de colonnes CSV (core/csv_column_glossary.py) et de
son cablage sur le vrai widget (gui/csv_edit_widget.py)."""
import shutil
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "pda_scenario" / "PDA.csv"


def test_key_column_recognized():
    from core.csv_column_glossary import get_csv_column_tooltip
    result = get_csv_column_tooltip("KEY")
    assert result != ""
    assert "identifiant" in result.lower() or "Identifiant" in result


def test_key_column_case_insensitive():
    from core.csv_column_glossary import get_csv_column_tooltip
    assert get_csv_column_tooltip("Key") != ""
    assert get_csv_column_tooltip("key") != ""


def test_english_column_recognized():
    from core.csv_column_glossary import get_csv_column_tooltip
    result = get_csv_column_tooltip("English")
    assert "anglais" in result.lower()


def test_french_column_recognized_with_accent():
    from core.csv_column_glossary import get_csv_column_tooltip
    result = get_csv_column_tooltip("Français")
    assert "français" in result.lower()


def test_language_code_recognized():
    from core.csv_column_glossary import get_csv_column_tooltip
    result = get_csv_column_tooltip("fr")
    assert "français" in result.lower()


def test_unknown_column_returns_empty():
    from core.csv_column_glossary import get_csv_column_tooltip
    assert get_csv_column_tooltip("ColonneInconnue") == ""


def test_empty_column_name_returns_empty():
    from core.csv_column_glossary import get_csv_column_tooltip
    assert get_csv_column_tooltip("") == ""


@pytest.fixture
def csv_widget(qapp, tmp_path):
    from gui.csv_edit_widget import CsvEditWidget
    working_copy = tmp_path / "PDA.csv"
    shutil.copy(FIXTURE, working_copy)
    return CsvEditWidget(working_copy)


def test_widget_sets_tooltip_on_key_header(csv_widget):
    """Verifie le cablage reel sur le widget Qt -- la colonne KEY doit
    recevoir une infobulle non vide."""
    header_item = csv_widget.table.horizontalHeaderItem(0)
    assert header_item is not None
    assert header_item.text().upper() == "KEY"
    assert header_item.toolTip() != ""


def test_widget_sets_tooltip_on_language_header(csv_widget):
    header_item = csv_widget.table.horizontalHeaderItem(1)
    assert header_item is not None
    assert header_item.toolTip() != ""
