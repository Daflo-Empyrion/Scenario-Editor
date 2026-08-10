"""
Widget d'edition pour un fichier .ecf de la COPIE DE TRAVAIL : contrairement a
EcfViewWidget (lecture seule, dans main_window.py), celui-ci permet de modifier une
valeur, ajouter/supprimer une propriete, ajouter/supprimer un bloc -- avec annotation
automatique de tracabilite sur chaque modification.

Contient aussi CompareWidget : une vue cote a cote (copie de travail modifiable a
gauche, source(s) A/B en lecture seule a droite, dans des onglets si les deux sont
disponibles) pour editer en gardant la reference sous les yeux, sans perdre d'espace
d'affichage a switcher entre onglets separes.
"""
from pathlib import Path
from typing import Dict, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem, QTableWidget,
    QTableWidgetItem, QSplitter, QLabel, QLineEdit, QPushButton, QMenu, QMessageBox,
    QInputDialog, QTabWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QTreeWidgetItemIterator
from PyQt6.QtGui import QColor, QBrush

from core.ecf.parser import parse_ecf_file
from core.ecf.model import (
    EcfDocument, EcfBlock, EcfProperty, block_identity, normalized_kind,
    add_property_line, remove_property_line, remove_block, create_block, annotate_property,
)
from core import settings

COLOR_MODIFIED_ROW = QBrush(QColor(255, 250, 200))  # jaune clair : ligne modifiee dans cette session


class EcfEditWidget(QWidget):
    """Editeur d'un fichier .ecf de la copie de travail. Emet `modified_changed(bool)`
    quand l'etat 'modifications non enregistrees' change, pour que le conteneur (onglet)
    puisse afficher un indicateur."""

    modified_changed = pyqtSignal(bool)
    saved = pyqtSignal()

    def __init__(self, path: Path):
        super().__init__()
        self.path = path
        self.doc: EcfDocument = parse_ecf_file(path)
        self._modified = False
        self._current_block: Optional[EcfBlock] = None
        self._edited_prop_nodes = set()  # ids Python des EcfProperty touches cette session

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"{path.name}  (copie de travail -- modifiable)"))

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Rechercher :"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Id / Name / CustomIcon... puis Entree")
        self.search_box.returnPressed.connect(self._search_next)
        search_row.addWidget(self.search_box)
        self.search_status = QLabel("")
        search_row.addWidget(self.search_status)
        layout.addLayout(search_row)

        toolbar = QHBoxLayout()
        btn_add_block = QPushButton("+ Bloc")
        btn_add_block.clicked.connect(self._add_block_dialog)
        toolbar.addWidget(btn_add_block)
        btn_add_prop = QPushButton("+ Propriete")
        btn_add_prop.clicked.connect(self._add_property_dialog)
        toolbar.addWidget(btn_add_prop)
        btn_save = QPushButton("Enregistrer (Ctrl+S)")
        btn_save.clicked.connect(self.save)
        toolbar.addWidget(btn_save)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Bloc"])
        self._populate_tree()
        self.tree.itemClicked.connect(self._on_block_selected)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_tree_context_menu)
        splitter.addWidget(self.tree)

        self.props_table = QTableWidget(0, 2)
        self.props_table.setHorizontalHeaderLabels(["Propriete", "Valeur"])
        self.props_table.horizontalHeader().setStretchLastSection(True)
        self.props_table.itemChanged.connect(self._on_cell_changed)
        self.props_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.props_table.customContextMenuRequested.connect(self._show_table_context_menu)
        splitter.addWidget(self.props_table)

        splitter.setSizes([400, 500])
        layout.addWidget(splitter)

        self._search_matches: list = []
        self._search_index = -1
        self._search_last_query = ""

    # ------------------------------------------------------------------
    # Etat modifie / enregistrement
    # ------------------------------------------------------------------

    def _set_modified(self, value: bool):
        if value != self._modified:
            self._modified = value
            self.modified_changed.emit(value)

    def is_modified(self) -> bool:
        return self._modified

    def save(self):
        with open(self.path, 'w', encoding='utf-8', newline='') as f:
            f.write(self.doc.render())
        self._set_modified(False)
        self.saved.emit()

    # ------------------------------------------------------------------
    # Arbre des blocs
    # ------------------------------------------------------------------

    def _populate_tree(self):
        self.tree.clear()
        for node in self.doc.nodes:
            if isinstance(node, EcfBlock):
                self.tree.addTopLevelItem(self._make_block_item(node))

    def _make_block_item(self, block: EcfBlock) -> QTreeWidgetItem:
        ident = block_identity(block)
        label = f"{block.kind} [{ident}]" if ident else block.kind
        item = QTreeWidgetItem([label])
        item.setData(0, Qt.ItemDataRole.UserRole, block)
        for child in block.children:
            if isinstance(child, EcfBlock):
                item.addChild(self._make_block_item(child))
        return item

    def _search_next(self):
        query = self.search_box.text().strip().lower()
        if not query:
            return
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
            self.search_status.setText("Aucun resultat")
            return
        self._search_index = (self._search_index + 1) % len(self._search_matches)
        item = self._search_matches[self._search_index]
        self.tree.setCurrentItem(item)
        self.tree.scrollToItem(item)
        self._on_block_selected(item, 0)
        self.search_status.setText(f"{self._search_index + 1} / {len(self._search_matches)}")

    # ------------------------------------------------------------------
    # Table des proprietes (editable)
    # ------------------------------------------------------------------

    def _on_block_selected(self, item: QTreeWidgetItem, column: int):
        block = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(block, EcfBlock):
            return
        self._current_block = block
        self._refresh_props_table()

    def _refresh_props_table(self):
        if not self._current_block:
            return
        block = self._current_block
        self.props_table.blockSignals(True)
        rows = []
        # Proprietes declarees sur la ligne d'ouverture du bloc (Id, Name, Ref...) --
        # marquees avec le bloc lui-meme comme reference, distinct des lignes enfants.
        for k, v in block.pairs:
            if k:
                rows.append((k, v, block))
        for child in block.children:
            if isinstance(child, EcfProperty):
                for k, v in child.pairs:
                    if k:
                        rows.append((k, v, child))
        self.props_table.setRowCount(len(rows))
        for i, (k, v, prop_node) in enumerate(rows):
            item_k = QTableWidgetItem(k)
            item_k.setFlags(item_k.flags() & ~Qt.ItemFlag.ItemIsEditable)  # la cle n'est pas editable ici
            item_v = QTableWidgetItem(v)
            item_v.setData(Qt.ItemDataRole.UserRole, prop_node)
            if prop_node is block:
                item_k.setToolTip("Propriete d'en-tete du bloc (ex: Id, Name)")
            if id(prop_node) in self._edited_prop_nodes:
                item_k.setBackground(COLOR_MODIFIED_ROW)
                item_v.setBackground(COLOR_MODIFIED_ROW)
            self.props_table.setItem(i, 0, item_k)
            self.props_table.setItem(i, 1, item_v)
        self.props_table.blockSignals(False)

    def _on_cell_changed(self, item: QTableWidgetItem):
        if item.column() != 1:
            return
        prop_node = item.data(Qt.ItemDataRole.UserRole)
        row = item.row()
        key_item = self.props_table.item(row, 0)
        key = key_item.text()
        new_value = item.text()

        if isinstance(prop_node, EcfBlock):
            # Propriete d'en-tete (Id, Name...) -- vit sur block.pairs, pas sur une
            # ligne enfant. Attention particuliere : modifier l'Id peut casser des
            # references ailleurs dans le fichier -- on laisse faire (l'utilisateur est
            # averti via le tooltip) mais on ne l'empeche pas.
            old_value = prop_node.get(key)
            if old_value == new_value:
                return
            prop_node.set(key, new_value)
            annotate_target = None  # les proprietes d'en-tete n'ont pas de 'comment' individuel simple a annoter
        else:
            if not isinstance(prop_node, EcfProperty):
                return
            old_value = None
            idx = None
            for i, (k, v) in enumerate(prop_node.pairs):
                if k == key:
                    old_value = v
                    idx = i
                    break
            if idx is None or old_value == new_value:
                return
            prop_node.pairs[idx] = (key, new_value)
            prop_node.dirty = True
            annotate_target = prop_node

        if settings.get_annotations_enabled() and annotate_target is not None:
            author = settings.get_author()
            annotate_property(annotate_target, f"# original {key}: {old_value} -- Mod par {author}")

        self._edited_prop_nodes.add(id(prop_node))
        self._set_modified(True)
        self.props_table.blockSignals(True)
        item.setBackground(COLOR_MODIFIED_ROW)
        key_item.setBackground(COLOR_MODIFIED_ROW)
        self.props_table.blockSignals(False)

    def _show_table_context_menu(self, pos):
        item = self.props_table.itemAt(pos)
        if not item or not self._current_block:
            return
        row = item.row()
        prop_node = self.props_table.item(row, 1).data(Qt.ItemDataRole.UserRole)

        if isinstance(prop_node, EcfBlock):
            # Propriete d'en-tete (Id, Name...) -- pas de suppression proposee ici,
            # trop risque de casser la structure du bloc sans passer par une action dediee.
            return

        menu = QMenu(self)
        action_del = menu.addAction("Supprimer cette propriete")
        chosen = menu.exec(self.props_table.viewport().mapToGlobal(pos))
        if chosen == action_del and isinstance(prop_node, EcfProperty):
            remove_property_line(self._current_block, prop_node)
            self._set_modified(True)
            self._refresh_props_table()

    def _add_property_dialog(self):
        if not self._current_block:
            QMessageBox.information(self, "Aucun bloc", "Selectionne d'abord un bloc dans l'arbre.")
            return
        key, ok = QInputDialog.getText(self, "Ajouter une propriete", "Nom de la propriete :")
        if not ok or not key.strip():
            return
        value, ok = QInputDialog.getText(self, "Ajouter une propriete", f"Valeur de '{key}' :")
        if not ok:
            return
        add_property_line(self._current_block, [(key.strip(), value.strip())])
        self._set_modified(True)
        self._refresh_props_table()

    # ------------------------------------------------------------------
    # Blocs : ajout / suppression
    # ------------------------------------------------------------------

    def _show_tree_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        block = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(block, EcfBlock):
            return
        menu = QMenu(self)
        action_del = menu.addAction("Supprimer ce bloc")
        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen == action_del:
            confirm = QMessageBox.question(self, "Confirmer",
                                            f"Supprimer le bloc {item.text(0)} ?")
            if confirm == QMessageBox.StandardButton.Yes:
                remove_block(self.doc.nodes, block)
                self._set_modified(True)
                if self._current_block is block:
                    self._current_block = None
                    self.props_table.setRowCount(0)
                self._populate_tree()

    def _add_block_dialog(self):
        kind, ok = QInputDialog.getText(self, "Ajouter un bloc", "Genre du bloc (ex: Block) :")
        if not ok or not kind.strip():
            return
        block_id, ok = QInputDialog.getText(self, "Ajouter un bloc", "Id :")
        if not ok or not block_id.strip():
            return
        name, ok = QInputDialog.getText(self, "Ajouter un bloc", "Name (optionnel) :")
        if not ok:
            name = ""
        pairs = [('Id', block_id.strip())]
        if name.strip():
            pairs.append(('Name', name.strip()))
        new_block = create_block(kind.strip(), pairs)
        self.doc.nodes.append(new_block)
        self._set_modified(True)
        self._populate_tree()


class CompareWidget(QWidget):
    """Vue cote a cote : copie de travail (editable) a gauche, source(s) A/B en
    lecture seule a droite (dans des onglets si plusieurs sont disponibles).
    Le clic droit "copier ce bloc" fonctionne aussi depuis les panneaux source ici."""

    def __init__(self, working_path: Path, compare_sources: Dict[str, tuple], view_widget_factory,
                 copy_block_callback=None):
        """
        compare_sources : {label: (chemin_source, racine_source)}
        view_widget_factory(path, on_copy_block=None) doit retourner un widget de
        lecture seule (typiquement EcfViewWidget de main_window.py) -- injecte pour
        eviter un import circulaire entre ce module et main_window.py.
        copy_block_callback(block, source_path, source_root, source_label) : appele
        quand l'utilisateur choisit "copier ce bloc" depuis un panneau source.
        """
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.edit_widget = EcfEditWidget(working_path)
        splitter.addWidget(self.edit_widget)

        if compare_sources:
            right_side = QTabWidget()
            for label, (src_path, src_root) in compare_sources.items():
                on_copy = None
                if copy_block_callback:
                    on_copy = (lambda block, p=src_path, r=src_root, l=label:
                               copy_block_callback(block, p, r, l))
                right_side.addTab(view_widget_factory(src_path, on_copy_block=on_copy, copy_label=label), label)
            splitter.addWidget(right_side)
            splitter.setSizes([600, 500])
        else:
            splitter.setSizes([1])

        layout.addWidget(splitter)

        self.modified_changed = self.edit_widget.modified_changed
        self.saved = self.edit_widget.saved

    def is_modified(self) -> bool:
        return self.edit_widget.is_modified()

    def save(self):
        self.edit_widget.save()
