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

"""
Tableau de proprietes editable (cle | valeur) -- reutilise dans deux
contextes de duplication (demande explicite de l'utilisateur, session du
29/08/2026 : pouvoir ajuster les proprietes du duplicata EN MEME TEMPS que
la duplication elle-meme, au lieu de devoir rouvrir le fichier apres coup) :

1. gui/duplicate_variants_dialog.py -- proprietes du bloc/ligne dupliquee
   (voir core.ecf.variants.list_editable_fields_block).
2. gui/ecf_edit_widget.py::_create_templates_for_variants -- proprietes du
   Template auto-cree associe (CraftTime, quantites d'ingredients...).

N'affiche QUE les valeurs realistes a ajuster (pas Id/Name, geres par des
champs dedies ailleurs dans le dialogue) -- voir l'appelant pour la liste
exacte fournie. Ne renvoie QUE les valeurs reellement MODIFIEES par
l'utilisateur (voir get_changed_values), pour ne jamais ecraser un champ non
touche avec une valeur re-tapee identique par erreur d'arrondi d'affichage.

`values_by_key` (optionnel) : {cle: [valeurs observees triees par
frequence]} -- chaque cellule de valeur devient une liste deroulante
EDITABLE pre-remplie avec ces valeurs (demande du 30/08/2026 : liste
deroulante PARTOUT ou c'est possible) ; une cle absente du pool garde une
saisie libre classique.
"""
from typing import Dict, List, Optional, Tuple

from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QComboBox
from PyQt6.QtCore import Qt

from core.i18n import t


class PropertyEditTable(QTableWidget):
    def __init__(self, fields: List[Tuple[str, str]], parent=None,
                 values_by_key: Optional[Dict[str, List[str]]] = None):
        super().__init__(parent)
        self._original_values: Dict[str, str] = {k: v for k, v in fields}
        self._values_by_key: Dict[str, List[str]] = dict(values_by_key or {})
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels([t("dup.preview_col_property"), t("dup.preview_col_value")])
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.verticalHeader().setVisible(False)
        self.setRowCount(len(fields))
        for row, (key, value) in enumerate(fields):
            key_item = QTableWidgetItem(key)
            key_item.setFlags(key_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.setItem(row, 0, key_item)
            observed = self._values_by_key.get(key)
            if observed:
                combo = QComboBox()
                combo.setEditable(True)  # saisie libre toujours permise
                combo.addItems(observed)
                combo.setCurrentText(value)
                self.setCellWidget(row, 1, combo)
            else:
                self.setItem(row, 1, QTableWidgetItem(value))
        self.setMaximumHeight(220)

    def _row_value(self, row: int) -> str:
        """Valeur courante de la ligne : liste deroulante si la cellule en
        est une, sinon l'item texte classique."""
        combo = self.cellWidget(row, 1)
        if combo is not None:
            return combo.currentText()
        item = self.item(row, 1)
        return item.text() if item is not None else ""

    def get_changed_values(self) -> Dict[str, str]:
        """Ne retourne QUE les cles dont la valeur a reellement change par
        rapport a l'original -- voir docstring du module."""
        changed: Dict[str, str] = {}
        for row in range(self.rowCount()):
            key_item = self.item(row, 0)
            if key_item is None:
                continue
            key = key_item.text()
            new_value = self._row_value(row)
            if new_value != self._original_values.get(key):
                changed[key] = new_value
        return changed
