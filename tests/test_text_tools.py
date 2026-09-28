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

"""Mise en forme BBCode (vecu 27/09) : la palette de couleurs generait du
BBCode STANDARD '[color=#0066FF]...[/color]' que le jeu n'accepte PAS --
le dialecte Empyrion est '[c][0066FF]...[/color]'. Desormais la palette
produit le format du jeu, et un bouton convertit les balises legacy
deja ecrites dans les textes."""
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QPushButton

from gui.text_tools import BBCodeToolDialog


@pytest.fixture
def dlg(qapp):
    return BBCodeToolDialog("texte de depart", parent=None)


def _select_all(dlg):
    cur = dlg.text_edit.textCursor()
    cur.select(QTextCursor.SelectionType.Document)
    dlg.text_edit.setTextCursor(cur)


def test_construction(qapp, dlg):
    assert dlg.result_text() == "texte de depart"


def test_color_button_uses_game_dialect(qapp, dlg):
    """Le bouton couleur doit produire [c][0066FF]...[/color] (dialecte
    Empyrion) et NON [color=#0066FF]...[/color] (BBCode standard que le
    jeu affiche brut)."""
    dlg.text_edit.setPlainText("Naquadah Building Blocks")
    _select_all(dlg)
    bleu = next(b for b in dlg.findChildren(QPushButton)
                if b.toolTip() == "Bleu")
    bleu.click()
    assert dlg.result_text() == "[c][0066FF]Naquadah Building Blocks[/color]"


def test_fix_legacy_color_tags(qapp, dlg):
    dlg.text_edit.setPlainText(
        "Avant [color=#0066FF]Naquadah Building Blocks[/color] apres "
        "[color=#ffcc00]Jaune[/color]")
    dlg._fix_legacy_color_tags()
    assert dlg.result_text() == (
        "Avant [c][0066FF]Naquadah Building Blocks[/color] apres "
        "[c][FFCC00]Jaune[/color]")


def test_fix_legacy_nothing_to_convert(qapp, dlg):
    dlg.text_edit.setPlainText("deja [c][0066FF]bon[/color]")
    dlg._fix_legacy_color_tags()
    assert dlg.result_text() == "deja [c][0066FF]bon[/color]"
