"""
Fenetre principale de l'editeur de scenario Empyrion.

Layout a 3 volets :
  - Gauche  : Scenario A (base), LECTURE SEULE
  - Centre  : Copie de travail (modifiable) + onglets des fichiers ouverts
  - Droite  : Scenario B (source pour la fusion, optionnel), LECTURE SEULE

Seule la copie de travail (une copie physique complete du scenario A, creee a un
nouvel emplacement) peut etre modifiee. Les scenarios A et B ne sont jamais touches.
Clic droit sur un fichier de A ou B -> "Copier vers la copie de travail" pour y
importer un fichier (mesh, icone, ECF, YAML...).
"""
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QTreeWidget, QTreeWidgetItem,
    QTabWidget, QSplitter, QTableWidget, QTableWidgetItem, QWidget, QVBoxLayout,
    QLabel, QStatusBar, QHeaderView, QMessageBox, QMenu, QProgressDialog,
)
from PyQt6.QtCore import Qt

from core.scanner import scan_scenario
from core.models import Scenario, FileEntry
from core.workspace import Workspace, open_workspace, copy_file_into_working
from core.ecf.parser import parse_ecf_file
from core.ecf.model import EcfDocument, EcfBlock, EcfProperty, block_identity
from core.yamllite.parser import parse_yaml_file
from core.yamllite.model import YamlDocument, YamlEntry

from gui.new_project_dialog import NewProjectDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Empyrion Scenario Editor")
        self.resize(1500, 800)

        self.workspace: Optional[Workspace] = None

        self._build_menu()
        self._build_layout()
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Aucun projet ouvert -- Fichier > Nouveau projet...")

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------

    def _build_menu(self):
        menu = self.menuBar().addMenu("&Fichier")
        action_new = menu.addAction("&Nouveau projet...")
        action_new.triggered.connect(self.new_project_dialog)
        menu.addSeparator()
        action_quit = menu.addAction("&Quitter")
        action_quit.triggered.connect(self.close)

    def _build_layout(self):
        self.outer_splitter = QSplitter(Qt.Orientation.Horizontal)

        # -- Volet gauche : Scenario A (lecture seule) --
        self.panel_a = QWidget()
        layout_a = QVBoxLayout(self.panel_a)
        layout_a.setContentsMargins(4, 4, 4, 4)
        self.label_a = QLabel("Scenario A (lecture seule)")
        self.label_a.setStyleSheet("font-weight: bold;")
        self.tree_a = QTreeWidget()
        self.tree_a.setHeaderLabels(["Scenario A"])
        self.tree_a.itemDoubleClicked.connect(lambda item, col: self._on_source_double_clicked(item, self._root_a))
        self.tree_a.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_a.customContextMenuRequested.connect(
            lambda pos: self._show_source_context_menu(self.tree_a, pos, self._root_a))
        layout_a.addWidget(self.label_a)
        layout_a.addWidget(self.tree_a)
        self.outer_splitter.addWidget(self.panel_a)

        # -- Volet central : copie de travail + onglets --
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(4, 4, 4, 4)
        self.label_working = QLabel("Copie de travail (modifiable)")
        self.label_working.setStyleSheet("font-weight: bold; color: #2a6;")
        center_layout.addWidget(self.label_working)

        center_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.tree_working = QTreeWidget()
        self.tree_working.setHeaderLabels(["Copie de travail"])
        self.tree_working.itemDoubleClicked.connect(self._on_working_double_clicked)
        center_splitter.addWidget(self.tree_working)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(lambda i: self.tabs.removeTab(i))
        center_splitter.addWidget(self.tabs)
        center_splitter.setSizes([280, 700])

        center_layout.addWidget(center_splitter)
        self.outer_splitter.addWidget(center_widget)

        # -- Volet droit : Scenario B (lecture seule, cache si pas en mode fusion) --
        self.panel_b = QWidget()
        layout_b = QVBoxLayout(self.panel_b)
        layout_b.setContentsMargins(4, 4, 4, 4)
        self.label_b = QLabel("Scenario B (lecture seule)")
        self.label_b.setStyleSheet("font-weight: bold;")
        self.tree_b = QTreeWidget()
        self.tree_b.setHeaderLabels(["Scenario B"])
        self.tree_b.itemDoubleClicked.connect(lambda item, col: self._on_source_double_clicked(item, self._root_b))
        self.tree_b.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_b.customContextMenuRequested.connect(
            lambda pos: self._show_source_context_menu(self.tree_b, pos, self._root_b))
        layout_b.addWidget(self.label_b)
        layout_b.addWidget(self.tree_b)
        self.outer_splitter.addWidget(self.panel_b)
        self.panel_b.setVisible(False)

        self.outer_splitter.setSizes([320, 880, 320])
        self.setCentralWidget(self.outer_splitter)

    @property
    def _root_a(self) -> Optional[Path]:
        return self.workspace.source_a_root if self.workspace else None

    @property
    def _root_b(self) -> Optional[Path]:
        return self.workspace.source_b_root if self.workspace else None

    # ------------------------------------------------------------------
    # Nouveau projet (creation du workspace)
    # ------------------------------------------------------------------

    def new_project_dialog(self):
        dialog = NewProjectDialog(self)
        if dialog.exec() != NewProjectDialog.DialogCode.Accepted:
            return

        progress = QProgressDialog("Copie du scenario de base en cours...", None, 0, 0, self)
        progress.setWindowTitle("Veuillez patienter")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()

        try:
            self.workspace = open_workspace(dialog.source_a_path, dialog.dest_path, dialog.source_b_path)
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "Erreur", f"Impossible de creer le projet :\n{e}")
            return
        progress.close()

        self._refresh_all_trees()
        self.tabs.clear()

        mode = "FUSION" if self.workspace.is_merge_mode else "edition simple"
        self.statusBar().showMessage(
            f"Projet ouvert ({mode}) -- copie de travail : {self.workspace.working_root}"
        )

    def _refresh_all_trees(self):
        if not self.workspace:
            return
        self.label_a.setText(f"Scenario A (lecture seule) -- {self.workspace.source_a_root.name}")
        self._populate_tree(self.tree_a, self.workspace.source_a)

        self.label_working.setText(f"Copie de travail (modifiable) -- {self.workspace.working_root.name}")
        self._populate_tree(self.tree_working, self.workspace.working)

        if self.workspace.is_merge_mode:
            self.panel_b.setVisible(True)
            self.label_b.setText(f"Scenario B (lecture seule) -- {self.workspace.source_b_root.name}")
            self._populate_tree(self.tree_b, self.workspace.source_b)
        else:
            self.panel_b.setVisible(False)

    def _populate_tree(self, tree: QTreeWidget, scenario: Scenario):
        tree.clear()
        root_item = QTreeWidgetItem([scenario.name])
        tree.addTopLevelItem(root_item)
        self._add_file_category(root_item, "Configuration", scenario.configuration)
        self._add_playfields_category(root_item, scenario)
        self._add_file_category(root_item, "Sectors", scenario.sectors)
        self._add_file_category(root_item, "RandomPresets", scenario.random_presets)
        self._add_file_category(root_item, "Extras", scenario.extras)
        self._add_file_category(root_item, "Autres (non structures)", scenario.other_files)
        root_item.setExpanded(True)

    def _add_file_category(self, parent_item: QTreeWidgetItem, label: str, entries: list):
        if not entries:
            return
        cat_item = QTreeWidgetItem([f"{label} ({len(entries)})"])
        parent_item.addChild(cat_item)
        for entry in sorted(entries, key=lambda e: e.name):
            leaf = QTreeWidgetItem([entry.name])
            leaf.setData(0, Qt.ItemDataRole.UserRole, ("file", entry.path))
            cat_item.addChild(leaf)

    def _add_playfields_category(self, parent_item: QTreeWidgetItem, scenario: Scenario):
        if not scenario.playfields:
            return
        cat_item = QTreeWidgetItem([f"Playfields ({len(scenario.playfields)})"])
        parent_item.addChild(cat_item)
        for name, pf in sorted(scenario.playfields.items()):
            pf_item = QTreeWidgetItem([name])
            cat_item.addChild(pf_item)
            for role, path in sorted(pf.role_files.items()):
                leaf = QTreeWidgetItem([f"{role} : {path.name}"])
                leaf.setData(0, Qt.ItemDataRole.UserRole, ("file", path))
                pf_item.addChild(leaf)

    # ------------------------------------------------------------------
    # Copier depuis une source (A ou B) vers la copie de travail
    # ------------------------------------------------------------------

    def _show_source_context_menu(self, tree: QTreeWidget, pos, source_root: Optional[Path]):
        if not self.workspace or not source_root:
            return
        item = tree.itemAt(pos)
        if not item:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data or data[0] != "file":
            return
        path: Path = data[1]

        menu = QMenu(self)
        action = menu.addAction(f"Copier '{path.name}' vers la copie de travail")
        chosen = menu.exec(tree.viewport().mapToGlobal(pos))
        if chosen == action:
            self._copy_into_working(path, source_root)

    def _copy_into_working(self, path: Path, source_root: Path):
        try:
            dest = copy_file_into_working(self.workspace, path, source_root)
            self.workspace.rescan_working()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible de copier {path.name} :\n{e}")
            return

        self._populate_tree(self.tree_working, self.workspace.working)
        self.statusBar().showMessage(f"Copie vers la copie de travail : {dest}")

    # ------------------------------------------------------------------
    # Ouverture de fichiers (lecture seule pour A/B, meme vue pour l'instant sur
    # la copie de travail -- l'edition inline viendra dans une passe suivante)
    # ------------------------------------------------------------------

    def _on_source_double_clicked(self, item: QTreeWidgetItem, source_root):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data or data[0] != "file":
            return
        self.open_file_tab(data[1], read_only=True)

    def _on_working_double_clicked(self, item: QTreeWidgetItem, column: int):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data or data[0] != "file":
            return
        self.open_file_tab(data[1], read_only=False)

    def open_file_tab(self, path: Path, read_only: bool):
        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(path):
                self.tabs.setCurrentIndex(i)
                return

        ext = path.suffix.lower()
        try:
            if ext == '.ecf':
                widget = EcfViewWidget(path)
            elif ext in ('.yaml', '.yml'):
                widget = YamlViewWidget(path)
            else:
                QMessageBox.information(self, "Non supporte",
                                         f"Pas encore de vue pour les fichiers {ext}")
                return
        except Exception as e:
            QMessageBox.critical(self, "Erreur de lecture", f"Impossible d'ouvrir {path.name} :\n{e}")
            return

        prefix = "🔒 " if read_only else "✎ "
        index = self.tabs.addTab(widget, prefix + path.name)
        self.tabs.setTabToolTip(index, str(path))
        self.tabs.setCurrentIndex(index)


class EcfViewWidget(QWidget):
    """Vue en lecture d'un fichier .ecf : arbre des blocs a gauche, proprietes a droite."""

    def __init__(self, path: Path):
        super().__init__()
        self.path = path
        self.doc: EcfDocument = parse_ecf_file(path)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"{path.name}  --  {sum(1 for _ in self.doc.iter_blocks())} blocs"))

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Bloc"])
        self._populate_tree()
        self.tree.itemClicked.connect(self._on_block_selected)
        splitter.addWidget(self.tree)

        self.props_table = QTableWidget(0, 2)
        self.props_table.setHorizontalHeaderLabels(["Propriete", "Valeur"])
        self.props_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        splitter.addWidget(self.props_table)

        splitter.setSizes([400, 500])
        layout.addWidget(splitter)

    def _populate_tree(self):
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

        self.props_table.setRowCount(len(rows))
        for i, (k, v) in enumerate(rows):
            self.props_table.setItem(i, 0, QTableWidgetItem(k))
            self.props_table.setItem(i, 1, QTableWidgetItem(v))


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


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
