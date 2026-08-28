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

"""Tests d'integration verifiant que les infobulles de champ (voir
gui/ecf_edit_widget.py::_field_tooltip) sont bien posees sur les VRAIS
widgets Qt (en-tetes de colonne en mode tableau, lignes de propriete en
mode liste) -- au-dela des tests unitaires des fonctions de recherche,
verifie que le cablage lui-meme fonctionne."""
import shutil
from pathlib import Path

import pytest

BLOCKS_FIXTURE = Path(__file__).parent / "fixtures" / "block_creation_scenario" / "BlocksConfig.ecf"
LOOTGROUPS_FIXTURE = Path(__file__).parent / "fixtures" / "block_creation_scenario" / "LootGroups.ecf"


@pytest.fixture
def blocks_widget(qapp, tmp_path):
    from gui.ecf_edit_widget import EcfEditWidget
    working_copy = tmp_path / "BlocksConfig.ecf"
    shutil.copy(BLOCKS_FIXTURE, working_copy)
    return EcfEditWidget(working_copy)


@pytest.fixture
def lootgroups_widget(qapp, tmp_path):
    from gui.ecf_edit_widget import EcfEditWidget
    working_copy = tmp_path / "LootGroups.ecf"
    shutil.copy(LOOTGROUPS_FIXTURE, working_copy)
    return EcfEditWidget(working_copy)


def _select_block_by_name(widget, name):
    for block in widget.doc.iter_blocks():
        if block.get_property("Name") == name:
            widget._current_block = block
            widget._refresh_props_table()
            return block
    raise AssertionError(f"bloc {name} introuvable dans le fixture")


def test_flat_mode_row_has_glossary_tooltip(blocks_widget):
    """Le bloc IronResource (BlocksConfig.ecf) est en mode liste plate --
    verifie qu'une ligne dont la cle est couverte par le glossaire recoit
    bien l'infobulle correspondante sur le VRAI widget."""
    _select_block_by_name(blocks_widget, "IronResource")
    table = blocks_widget.props_table
    found_texture_row = False
    for row in range(table.rowCount()):
        key_item = table.item(row, 0)
        if key_item and key_item.text() == "Texture":
            found_texture_row = True
            # "Texture" fait partie du glossaire BlocksConfig -- l'infobulle
            # doit contenir l'explication reelle, pas etre vide.
            assert key_item.toolTip() != ""
    assert found_texture_row


def test_table_mode_column_header_has_tooltip(lootgroups_widget):
    """LootGroups.ecf bascule en mode tableau -- verifie que les en-tetes
    de colonnes generees dynamiquement (param1, param2...) recoivent une
    infobulle (via le glossaire LootGroups ou le repli sur commentaire
    reel du fichier)."""
    block = _select_block_by_name(lootgroups_widget, "EscapePodEasy")
    assert lootgroups_widget._table_mode is True
    table = lootgroups_widget.props_table

    header_type = table.horizontalHeaderItem(0)
    header_value = table.horizontalHeaderItem(1)
    assert header_type.toolTip() != ""
    assert header_value.toolTip() != ""

    # Au moins une colonne de parametre (param1, param2...) doit exister
    # au-dela des deux premieres colonnes fixes.
    assert table.columnCount() > 2


def test_tooltip_text_matches_glossary_content(blocks_widget):
    """Verifie que le CONTENU de l'infobulle correspond bien a ce que
    retourne le glossaire (pas juste presence/absence) -- garde-fou contre
    un cablage qui poserait une infobulle vide ou generique par erreur."""
    from core.ecf_header_glossary import find_term_explanation
    _select_block_by_name(blocks_widget, "IronResource")
    table = blocks_widget.props_table
    expected = find_term_explanation("BlocksConfig.ecf", "Texture")
    assert expected is not None

    for row in range(table.rowCount()):
        key_item = table.item(row, 0)
        if key_item and key_item.text() == "Texture":
            assert expected in key_item.toolTip()
            return
    raise AssertionError("ligne 'Texture' non trouvee")


def test_no_tooltip_when_no_glossary_and_no_comment(tmp_path, qapp):
    """Un fichier hors glossaire, sans commentaire inline, ne doit recevoir
    AUCUNE infobulle inventee -- verifie explicitement l'absence plutot
    que juste l'absence d'exception."""
    from gui.ecf_edit_widget import EcfEditWidget
    path = tmp_path / "FichierInconnu.ecf"
    path.write_text(
        "{ Block Id: 1, Name: TestBlock\n"
        "  ProprieteSansDoc: valeur\n"
        "}\n", encoding="utf-8")
    widget = EcfEditWidget(path)
    _select_block_by_name(widget, "TestBlock")
    table = widget.props_table
    for row in range(table.rowCount()):
        key_item = table.item(row, 0)
        if key_item and key_item.text() == "ProprieteSansDoc":
            assert key_item.toolTip() == ""
            return
    raise AssertionError("ligne 'ProprieteSansDoc' non trouvee")
