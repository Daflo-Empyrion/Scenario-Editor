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
Vues de LECTURE SEULE embarquees (v1.9.0, extraites de gui/main_window.py
sans aucun changement de comportement) :

- EcfViewWidget : arbre + proprietes d'un fichier .ecf (utilise par les
  onglets de la copie de travail ET par les vues Scenario A/B du comparateur
  avec menus de fusion/duplication) ;
- YamlViewWidget : arbre cles/valeurs d'un .yaml.

Extraites pour alléger main_window (fenetre principale) : ces deux classes
sont auto-suffisantes, aucune n'a besoin de l'etat de MainWindow.
"""
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSplitter, QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem,
    QTreeWidgetItemIterator, QHeaderView, QSizePolicy, QMenu,
)

from core.i18n import t
from core.ecf.parser import parse_ecf_file
from core.ecf.model import (
    EcfBlock, EcfProperty, EcfDocument, block_identity, normalized_kind,
)
from core.yamllite.parser import parse_yaml_file
from core.yamllite.model import YamlDocument, YamlEntry
from gui.ecf_edit_widget import (
    PropertyFilterDialog, _block_own_keys, EcfHeaderExplanationPanel,
)
from core.workspace import MergeHighlight
from gui import theme as _theme

# Couleurs de surlignage des fusions (ex-main_window, utilisees par les
# vues ; re-exportees par main_window pour compatibilite).
COLOR_NEW_BLOCK = QBrush(QColor(200, 255, 200))       # vert clair : bloc entierement nouveau
COLOR_CHANGED_BLOCK = QBrush(QColor(255, 240, 200))   # orange clair : bloc complete partiellement
COLOR_NEW_PROPERTY = QBrush(QColor(200, 255, 200))    # vert clair : ligne de propriete ajoutee


class EcfViewWidget(QWidget):
    """Vue en lecture d'un fichier .ecf : arbre des blocs a gauche, proprietes a droite.
    Si `highlight` est fourni (suite a une fusion), colore les blocs/proprietes ajoutes.
    Si `on_copy_block` est fourni (vue d'une source A/B), un clic droit sur un bloc
    propose de le fusionner vers la copie de travail SANS toucher au reste du fichier."""

    def __init__(self, path: Path, highlight: Optional[MergeHighlight] = None,
                 on_copy_block=None, copy_label: Optional[str] = None, on_duplicate_block=None):
        super().__init__()
        self.path = path
        self.highlight = highlight
        self.on_copy_block = on_copy_block
        self.copy_label = copy_label
        self.on_duplicate_block = on_duplicate_block
        self.doc: EcfDocument = parse_ecf_file(path)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)
        title = f"{path.name}  --  {sum(1 for _ in self.doc.iter_blocks())} blocs"
        if highlight and (highlight.new_blocks or highlight.changed_blocks):
            title += "   [vert = nouveau depuis la fusion, orange = complete depuis la fusion]"
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 11px; color: gray; padding: 0px;")
        title_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(title_label, 0)

        self.header_panel = EcfHeaderExplanationPanel(self.doc, path.name)
        layout.addWidget(self.header_panel, 0)

        # -- Barre de recherche : indispensable des que le fichier a beaucoup de blocs
        # (certains ECF reels en ont plus de 5000 au niveau racine, impossible a
        # reperer en faisant defiler manuellement une liste non triee) --
        search_row = QHBoxLayout()
        search_row.setSpacing(4)
        search_row.addWidget(QLabel(t("label.search")))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(t("search.identity_placeholder"))
        self.search_box.returnPressed.connect(self._search_next)
        search_row.addWidget(self.search_box)
        self.search_status = QLabel("")
        search_row.addWidget(self.search_status)
        btn_filter = QPushButton(t("btn.filter_by_property"))
        btn_filter.clicked.connect(self._open_property_filter)
        search_row.addWidget(btn_filter)
        layout.addLayout(search_row, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Bloc"])
        self._populate_tree()
        self.tree.itemClicked.connect(self._on_block_selected)
        if self.on_copy_block or self.on_duplicate_block:
            self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.tree.customContextMenuRequested.connect(self._show_block_context_menu)
        splitter.addWidget(self.tree)

        self.props_table = QTableWidget(0, 2)
        self.props_table.setHorizontalHeaderLabels(["Propriete", "Valeur"])
        self.props_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        splitter.addWidget(self.props_table)

        splitter.setSizes([400, 500])
        layout.addWidget(splitter, 1)

        self._search_matches: list = []
        self._search_index = -1
        self._search_last_query = ""

    def _open_property_filter(self):
        dialog = PropertyFilterDialog(self.doc, on_filter_changed=self._apply_property_filter, parent=self)
        dialog.exec()

    def _apply_property_filter(self, keys):
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            block = item.data(0, Qt.ItemDataRole.UserRole)
            if not keys or not isinstance(block, EcfBlock):
                item.setHidden(False)
                continue
            item.setHidden(not all(k in _block_own_keys(block) for k in keys))

    def _search_next(self):
        query = self.search_box.text().strip().lower()
        if not query:
            return

        # Reconstruit la liste des correspondances seulement si la recherche a change
        if not self._search_matches or self._search_last_query != query:
            self._search_matches = []
            it = QTreeWidgetItemIterator(self.tree)
            while it.value():
                item = it.value()
                block = item.data(0, Qt.ItemDataRole.UserRole)
                searchable = item.text(0).lower()
                if isinstance(block, EcfBlock):
                    for key in ('Name', 'CustomIcon', 'TemplateRoot', 'IndexName'):
                        val = block.get_property(key)
                        if val:
                            searchable += " " + val.lower()
                if query in searchable:
                    self._search_matches.append(item)
                it += 1
            self._search_index = -1
            self._search_last_query = query

        if not self._search_matches:
            self.search_status.setText(t("search.no_results"))
            return

        self._search_index = (self._search_index + 1) % len(self._search_matches)
        item = self._search_matches[self._search_index]
        self.tree.setCurrentItem(item)
        self.tree.scrollToItem(item)
        self._on_block_selected(item, 0)
        self.search_status.setText(f"{self._search_index + 1} / {len(self._search_matches)}")

    def _show_block_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        block = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(block, EcfBlock):
            return
        ident = block_identity(block)
        label = f"{block.kind} [{ident}]" if ident else block.kind

        # Chaine des ancetres (kind, identite) menant a ce bloc -- vide si le bloc est
        # deja au niveau racine. Indispensable pour un sous-bloc imbrique (ex: 'Mode'
        # dans un 'Item') : sans ca, une duplication le placerait a tort au niveau
        # racine, isole de son parent.
        parent_chain = []
        parent_item = item.parent()
        while parent_item is not None:
            parent_block = parent_item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(parent_block, EcfBlock):
                parent_chain.insert(0, (normalized_kind(parent_block.kind), block_identity(parent_block)))
            parent_item = parent_item.parent()

        menu = QMenu(self)
        action_merge = None
        if self.on_copy_block:
            action_merge = menu.addAction(t("ecf.merge_block_action", label=label))
        action_dup = None
        if self.on_duplicate_block:
            if parent_chain:
                action_dup = menu.addAction(t("ecf.duplicate_subblock_action"))
            else:
                action_dup = menu.addAction(t("ecf.duplicate_block_action"))
        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if action_merge and chosen == action_merge:
            self.on_copy_block(block)
        elif action_dup and chosen == action_dup:
            self.on_duplicate_block(block, parent_chain)

    def _populate_tree(self):
        group_before, label_by_block_id = self.doc.scan_section_groups_and_labels()
        self._label_by_block_id = label_by_block_id
        for index, node in enumerate(self.doc.nodes):
            if index in group_before:
                self.tree.addTopLevelItem(self._make_group_header_item(group_before[index]))
            if isinstance(node, EcfBlock):
                self.tree.addTopLevelItem(self._make_block_item(node))

    def _make_group_header_item(self, title: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem([f"\u25a0 {title}"])
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setForeground(0, QBrush(QColor(_theme.PRIMARY_DARK)))
        font = item.font(0)
        font.setBold(True)
        item.setFont(0, font)
        return item

    def _make_block_item(self, block: EcfBlock) -> QTreeWidgetItem:
        ident = block_identity(block)
        label = f"{block.kind} [{ident}]" if ident else block.kind
        name = block.get_property('Name')
        if name and name != ident:
            label += f"  - {name}"
        friendly = self._label_by_block_id.get(id(block)) if hasattr(self, '_label_by_block_id') else None
        if friendly:
            label += f"   ({friendly})"
        item = QTreeWidgetItem([label])
        item.setData(0, Qt.ItemDataRole.UserRole, block)

        if self.highlight:
            key = (normalized_kind(block.kind), ident)
            if key in self.highlight.new_blocks:
                item.setBackground(0, COLOR_NEW_BLOCK)
                item.setText(0, label + "  (nouveau)")
            elif key in self.highlight.changed_blocks:
                item.setBackground(0, COLOR_CHANGED_BLOCK)
                item.setText(0, label + "  (complete)")

        for child in block.children:
            if isinstance(child, EcfBlock):
                item.addChild(self._make_block_item(child))
        return item

    def _on_block_selected(self, item: QTreeWidgetItem, column: int):
        block = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(block, EcfBlock):
            return
        rows = []
        for k, v in block.pairs:
            if k:
                rows.append((k, v))
        for child in block.children:
            if isinstance(child, EcfProperty):
                for k, v in child.pairs:
                    if k:
                        rows.append((k, v))

        added_keys = set()
        if self.highlight:
            key = (normalized_kind(block.kind), block_identity(block))
            added_keys = self.highlight.changed_blocks.get(key, set())

        self.props_table.setRowCount(len(rows))
        for i, (k, v) in enumerate(rows):
            item_k = QTableWidgetItem(k)
            item_v = QTableWidgetItem(v)
            if k in added_keys:
                item_k.setBackground(COLOR_NEW_PROPERTY)
                item_v.setBackground(COLOR_NEW_PROPERTY)
            self.props_table.setItem(i, 0, item_k)
            self.props_table.setItem(i, 1, item_v)


class YamlViewWidget(QWidget):
    """Vue en lecture d'un fichier .yaml : arbre des cles/entrees."""

    def __init__(self, path: Path):
        super().__init__()
        self.path = path
        self.doc: YamlDocument = parse_yaml_file(path)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"{path.name}"))

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Cle", "Valeur"])
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._populate_tree()
        layout.addWidget(self.tree)

    def _populate_tree(self):
        for node in self.doc.nodes:
            if isinstance(node, YamlEntry):
                self.tree.addTopLevelItem(self._make_entry_item(node))

    def _make_entry_item(self, entry: YamlEntry) -> QTreeWidgetItem:
        label = entry.key if entry.key is not None else "-"
        item = QTreeWidgetItem([label, entry.value])
        for child in entry.children:
            if isinstance(child, YamlEntry):
                item.addChild(self._make_entry_item(child))
        return item
