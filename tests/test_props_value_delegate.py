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

"""Liste deroulante (editable) sur CHAQUE valeur du tableau de proprietes
d'un bloc/item/Template selectionne a gauche -- demande explicite de
l'utilisateur du 30/08/2026. Valeurs proposees = celles reellement observees
dans le fichier ouvert pour la propriete de la ligne, triees par frequence ;
saisie libre toujours possible ; l'ecriture reutilise le mecanisme existant
(itemChanged -> _on_cell_changed)."""
import shutil
from pathlib import Path

import pytest
from PyQt6.QtCore import Qt, QModelIndex
from PyQt6.QtWidgets import QComboBox

from gui.ecf_edit_widget import EcfEditWidget, _PropertyValueDelegate

BLOCKS_TEXT = """{ Block Name: Fusee
  CraftTime: 10
  Target: "SurvC"
  Material: rock
  WeirdProp: x
}

{ Block Name: Fusee2
  CraftTime: 30
  Target: "SurvC"
  Material: metal
  OutputCount: 2
}
"""


@pytest.fixture
def widget(qapp, tmp_path):
    path = tmp_path / "BlocksConfig.ecf"
    path.write_text(BLOCKS_TEXT, encoding="utf-8")
    return EcfEditWidget(path)


def _select_block(widget, name):
    from core.ecf.model import EcfBlock
    it = QTreeWidgetItemIteratorHelper(widget.tree, name)
    return it


class QTreeWidgetItemIteratorHelper:
    pass  # remplace par la fonction ci-dessous


def _find_item(widget, name):
    from PyQt6.QtWidgets import QTreeWidgetItemIterator
    from core.ecf.model import EcfBlock
    it = QTreeWidgetItemIterator(widget.tree)
    while it.value():
        item = it.value()
        block = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(block, EcfBlock) and block.get_property("Name") == name:
            return item
        it += 1
    return None


def test_flat_table_installs_value_delegate(widget):
    widget.tree.setCurrentItem(_find_item(widget, "Fusee"))
    widget._on_block_selected(widget.tree.currentItem(), 0)
    delegate = widget.props_table.itemDelegateForColumn(1)
    assert isinstance(delegate, _PropertyValueDelegate)


def test_delegate_offers_values_observed_in_file(widget):
    widget.tree.setCurrentItem(_find_item(widget, "Fusee"))
    widget._on_block_selected(widget.tree.currentItem(), 0)
    delegate = widget.props_table.itemDelegateForColumn(1)

    table = widget.props_table
    # ligne de la propriete Target
    target_row = next(r for r in range(table.rowCount())
                      if table.item(r, 0).text() == "Target")
    index = table.model().index(target_row, 1)
    editor = delegate.createEditor(table, QModelIndex(), index)
    assert isinstance(editor, QComboBox)
    items = [editor.itemText(i) for i in range(editor.count())]
    assert items == ['"SurvC"']  # valeur observee, tri frequence
    assert editor.currentText() == '"SurvC"'


def test_delegate_values_are_per_property(widget):
    widget.tree.setCurrentItem(_find_item(widget, "Fusee"))
    widget._on_block_selected(widget.tree.currentItem(), 0)
    delegate = widget.props_table.itemDelegateForColumn(1)
    table = widget.props_table
    material_row = next(r for r in range(table.rowCount())
                        if table.item(r, 0).text() == "Material")
    index = table.model().index(material_row, 1)
    editor = delegate.createEditor(table, QModelIndex(), index)
    items = [editor.itemText(i) for i in range(editor.count())]
    assert items == ["rock", "metal"]


def test_picking_value_writes_through_existing_mechanism(widget, monkeypatch):
    """Choisir une valeur dans la liste doit ecrire la modification via
    _on_cell_changed (mecanisme existant) : le document devient modifie et
    la valeur change reellement."""
    widget.tree.setCurrentItem(_find_item(widget, "Fusee"))
    widget._on_block_selected(widget.tree.currentItem(), 0)
    delegate = widget.props_table.itemDelegateForColumn(1)
    table = widget.props_table
    target_row = next(r for r in range(table.rowCount())
                      if table.item(r, 0).text() == "Target")

    editor = QComboBox()
    editor.setEditable(True)
    editor.addItem('"BaseC"')
    editor.setCurrentText('"BaseC"')
    index = table.model().index(target_row, 1)
    delegate.setModelData(editor, table.model(), index)

    assert table.item(target_row, 1).text() == '"BaseC"'
    block = next(b for b in widget.doc.iter_blocks()
                 if b.get_property("Name") == "Fusee")
    assert block.get_property("Target") == '"BaseC"'


def test_free_text_still_possible_with_empty_history(widget):
    """Cle sans historique dans le fichier (ex: la paire d'EN-TETE 'Name',
    que scan_properties_for_kind ne collecte pas) : combo vide mais
    editable -- la saisie libre n'est jamais bloquee."""
    widget.tree.setCurrentItem(_find_item(widget, "Fusee"))
    widget._on_block_selected(widget.tree.currentItem(), 0)
    delegate = widget.props_table.itemDelegateForColumn(1)
    table = widget.props_table
    name_row = next(r for r in range(table.rowCount())
                    if table.item(r, 0).text() == "Name")
    editor = delegate.createEditor(table, QModelIndex(), table.model().index(name_row, 1))
    assert isinstance(editor, QComboBox)
    assert editor.count() == 0
    assert editor.currentText() == "Fusee"
