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
    QHBoxLayout, QLineEdit, QLabel, QStatusBar, QHeaderView, QMessageBox, QMenu,
    QProgressDialog, QInputDialog, QPushButton, QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTreeWidgetItemIterator
from PyQt6.QtGui import QColor, QBrush

from core.scanner import scan_scenario
from core.models import Scenario, FileEntry
from core.workspace import (
    Workspace, open_workspace, load_existing_workspace, copy_file_into_working,
    merge_file_into_working, merge_folder_into_working, merge_block_into_working,
    merge_csv_row_into_working, translate_csv_cell_into_working, MergeHighlight,
)
from core.ecf.parser import parse_ecf_file
from core.ecf.dependency_check import check_references
from core.ecf.pending_conflicts import (
    find_pending_conflicts, activate_pending_conflict, parse_pending_block, find_used_ids,
)
from core.ecf.model import EcfDocument, EcfBlock, EcfProperty, block_identity, normalized_kind
from core.yamllite.parser import parse_yaml_file
from core.yamllite.model import YamlDocument, YamlEntry
from core import project_store, settings
from core.project_store import ProjectRecord

from gui.new_project_dialog import NewProjectDialog
from gui.startup_dialog import StartupDialog
from gui.ecf_edit_widget import EcfEditWidget, CompareWidget, PendingConflictsDialog, PropertyFilterDialog, _block_own_keys
from gui.csv_edit_widget import CsvEditWidget

COLOR_NEW_BLOCK = QBrush(QColor(200, 255, 200))       # vert clair : bloc entierement nouveau
COLOR_CHANGED_BLOCK = QBrush(QColor(255, 240, 200))   # orange clair : bloc complete partiellement
COLOR_NEW_PROPERTY = QBrush(QColor(200, 255, 200))    # vert clair : ligne de propriete ajoutee


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Empyrion Scenario Editor")
        self.resize(1500, 800)

        self.workspace: Optional[Workspace] = None
        self._highlights: dict = {}  # Path -> MergeHighlight, pour colorer les ajouts de fusion

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
        action_recent = menu.addAction("&Projets recents...")
        action_recent.triggered.connect(self.show_startup_dialog)
        menu.addSeparator()
        action_save = menu.addAction("&Enregistrer")
        action_save.setShortcut("Ctrl+S")
        action_save.triggered.connect(self._save_current_tab)
        menu.addSeparator()
        action_quit = menu.addAction("&Quitter")
        action_quit.triggered.connect(self.close)

        menu_check = self.menuBar().addMenu("&Verification")
        action_refs = menu_check.addAction("Verifier les references (Ref) de la copie de travail...")
        action_refs.triggered.connect(self.check_references_dialog)
        action_pending = menu_check.addAction("Blocs en attente (conflits d'Id)...")
        action_pending.triggered.connect(self.check_pending_conflicts_dialog)

        menu_options = self.menuBar().addMenu("&Options")
        action_author = menu_options.addAction("Nom pour les annotations...")
        action_author.triggered.connect(self._set_author_dialog)
        self.action_toggle_annotations = menu_options.addAction("Annoter les modifications automatiquement")
        self.action_toggle_annotations.setCheckable(True)
        self.action_toggle_annotations.setChecked(settings.get_annotations_enabled())
        self.action_toggle_annotations.toggled.connect(settings.set_annotations_enabled)

    def _save_current_tab(self):
        widget = self.tabs.currentWidget()
        if widget and hasattr(widget, 'save'):
            widget.save()
        else:
            self.statusBar().showMessage("Rien a enregistrer sur cet onglet.")

    def _set_author_dialog(self):
        current = settings.get_author()
        name, ok = QInputDialog.getText(self, "Nom pour les annotations",
                                         "Ce nom apparaitra dans les commentaires '# original: ... -- Mod par ...' :",
                                         text=current)
        if ok and name.strip():
            settings.set_author(name.strip())

    def check_pending_conflicts_dialog(self):
        if not self.workspace:
            QMessageBox.information(self, "Aucun projet", "Ouvre d'abord un projet.")
            return

        ecf_files = [f.path for f in self.workspace.working.configuration if f.extension == '.ecf']

        entries = []
        for path in ecf_files:
            try:
                doc = parse_ecf_file(path)
            except Exception:
                continue
            for c in find_pending_conflicts(doc):
                pending_block = parse_pending_block(c)
                base_block = None
                if pending_block:
                    ident = block_identity(pending_block)
                    if ident:
                        base_block = doc.find_block(normalized_kind(pending_block.kind), 'Id', ident) \
                                     or doc.find_block(normalized_kind(pending_block.kind), 'Name', ident)
                entries.append({'path': path, 'doc': doc, 'conflict': c,
                                 'pending_block': pending_block, 'base_block': base_block})

        if not entries:
            QMessageBox.information(self, "Blocs en attente",
                                     "Aucun bloc en attente (conflit d'Id) trouve dans la copie de travail.")
            return

        used_ids = find_used_ids(ecf_files)

        dialog = PendingConflictsDialog(entries, used_ids, self)
        if dialog.exec() != PendingConflictsDialog.DialogCode.Accepted:
            return
        if not dialog.chosen_entry or not dialog.chosen_new_id:
            return

        target_path = dialog.chosen_entry['path']
        target_conflict = dialog.chosen_entry['conflict']
        new_id = dialog.chosen_new_id

        try:
            doc = parse_ecf_file(target_path)
            fresh_conflicts = find_pending_conflicts(doc)
            match = next((c for c in fresh_conflicts if c.header_text == target_conflict.header_text), None)
            if match is None:
                QMessageBox.critical(self, "Erreur", "Le bloc en attente n'a plus ete retrouve (fichier modifie entre-temps ?).")
                return

            success = activate_pending_conflict(doc, match, new_id)
            if not success:
                QMessageBox.critical(self, "Erreur", "Impossible d'activer ce bloc (motif 'Id:' introuvable dans son texte).")
                return

            with open(target_path, 'w', encoding='utf-8', newline='') as f:
                f.write(doc.render())
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur pendant l'activation :\n{e}")
            return

        self.workspace.rescan_working()
        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(target_path):
                self.tabs.removeTab(i)

        self.statusBar().showMessage(f"Bloc active avec Id={new_id} dans {target_path.name}")
        QMessageBox.information(self, "Bloc active",
                                 f"Le bloc est maintenant actif avec Id={new_id} dans {target_path.name}.\n"
                                 f"Pense a relancer la verification des references si ce bloc en concernait.")

    def check_references_dialog(self):
        if not self.workspace:
            QMessageBox.information(self, "Aucun projet", "Ouvre d'abord un projet.")
            return

        ecf_files = [f.path for f in self.workspace.working.configuration if f.extension == '.ecf']
        if not ecf_files:
            QMessageBox.information(self, "Aucun fichier", "Aucun fichier .ecf trouve dans Configuration.")
            return

        progress = QProgressDialog(f"Verification de {len(ecf_files)} fichier(s)...", None, 0, 0, self)
        progress.setWindowTitle("Veuillez patienter")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()

        try:
            broken = check_references(ecf_files)
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "Erreur", f"Erreur pendant la verification :\n{e}")
            return
        progress.close()

        if not broken:
            QMessageBox.information(self, "Verification des references",
                                     f"Aucune reference cassee trouvee sur {len(ecf_files)} fichier(s) verifie(s).")
            return

        details = "\n".join(b.label() for b in broken[:100])
        more = f"\n... et {len(broken) - 100} autre(s)" if len(broken) > 100 else ""
        QMessageBox.warning(
            self, "References cassees detectees",
            f"{len(broken)} reference(s) 'Ref' ne correspondent a aucun 'Name' existant "
            f"dans la copie de travail (l'heritage attendu ne fonctionnera pas en jeu) :\n\n"
            f"{details}{more}"
        )

    def _build_layout(self):
        # Layout vertical : en HAUT les fichiers ouverts (l'espace de travail principal,
        # comparaison + edition -- ce qui merite le plus de place), en BAS une bande
        # compacte de navigation avec les 3 scenarios cote a cote (A | copie de travail | B).
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)

        # -- Haut : onglets des fichiers ouverts --
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(lambda i: self.tabs.removeTab(i))
        self.main_splitter.addWidget(self.tabs)

        # -- Bas : bande de navigation A | copie de travail | B --
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.panel_a = QWidget()
        layout_a = QVBoxLayout(self.panel_a)
        layout_a.setContentsMargins(4, 2, 4, 2)
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
        bottom_splitter.addWidget(self.panel_a)

        self.panel_working = QWidget()
        layout_w = QVBoxLayout(self.panel_working)
        layout_w.setContentsMargins(4, 2, 4, 2)
        self.label_working = QLabel("Copie de travail (modifiable)")
        self.label_working.setStyleSheet("font-weight: bold; color: #2a6;")
        self.tree_working = QTreeWidget()
        self.tree_working.setHeaderLabels(["Copie de travail"])
        self.tree_working.itemDoubleClicked.connect(self._on_working_double_clicked)
        layout_w.addWidget(self.label_working)
        layout_w.addWidget(self.tree_working)
        bottom_splitter.addWidget(self.panel_working)

        self.panel_b = QWidget()
        layout_b = QVBoxLayout(self.panel_b)
        layout_b.setContentsMargins(4, 2, 4, 2)
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
        bottom_splitter.addWidget(self.panel_b)
        self.panel_b.setVisible(False)

        bottom_splitter.setSizes([320, 320, 320])
        self.main_splitter.addWidget(bottom_splitter)

        # Le haut (onglets) prend la grande majorite de la hauteur ; le bas reste une
        # bande de navigation compacte, redimensionnable a la souris si besoin.
        self.main_splitter.setSizes([650, 220])
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 0)
        self.setCentralWidget(self.main_splitter)

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

        self._highlights = {}
        self._refresh_all_trees()
        self.tabs.clear()

        self._remember_current_project()

        mode = "FUSION" if self.workspace.is_merge_mode else "edition simple"
        self.statusBar().showMessage(
            f"Projet ouvert ({mode}) -- copie de travail : {self.workspace.working_root}"
        )

    def _remember_current_project(self):
        if not self.workspace:
            return
        record = ProjectRecord(
            source_a=str(self.workspace.source_a_root),
            working=str(self.workspace.working_root),
            source_b=str(self.workspace.source_b_root) if self.workspace.source_b_root else None,
        )
        project_store.add_recent_project(record)

    def show_startup_dialog(self, auto_at_launch: bool = False):
        projects = project_store.load_recent_projects()
        if not projects:
            if not auto_at_launch:
                QMessageBox.information(self, "Aucun projet recent",
                                         "Aucun projet recent enregistre -- utilise 'Nouveau projet...'")
            return

        dialog = StartupDialog(projects, self)
        if dialog.exec() != StartupDialog.DialogCode.Accepted:
            if dialog.project_to_remove:
                project_store.remove_project(dialog.project_to_remove.working)
            return

        if dialog.project_to_remove:
            project_store.remove_project(dialog.project_to_remove.working)

        if dialog.want_new_project:
            self.new_project_dialog()
            return

        if dialog.chosen_project:
            self.open_existing_project(dialog.chosen_project)

    def open_existing_project(self, record: ProjectRecord):
        source_a = Path(record.source_a)
        working = Path(record.working)
        source_b = Path(record.source_b) if record.source_b else None

        try:
            self.workspace = load_existing_workspace(source_a, working, source_b)
        except Exception as e:
            QMessageBox.critical(self, "Erreur",
                                  f"Impossible de reprendre ce projet :\n{e}\n\n"
                                  f"Il a peut-etre ete deplace ou supprime.")
            return

        self._highlights = {}
        self._refresh_all_trees()
        self.tabs.clear()
        self._remember_current_project()  # remonte ce projet en tete de la liste recente

        mode = "FUSION" if self.workspace.is_merge_mode else "edition simple"
        self.statusBar().showMessage(
            f"Projet repris ({mode}) -- copie de travail : {self.workspace.working_root}"
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
        """Reconstruit l'arborescence EXACTE du disque (comme un explorateur de
        fichiers classique), plutot qu'une vue categorisee -- plus previsible et plus
        facile a comparer visuellement entre Scenario A, B et la copie de travail,
        puisque les trois montrent la meme structure que sur le disque."""
        tree.clear()
        root_item = QTreeWidgetItem([scenario.root_path.name])
        root_item.setData(0, Qt.ItemDataRole.UserRole, ("folder", scenario.root_path))
        tree.addTopLevelItem(root_item)
        self._build_real_tree(root_item, scenario.root_path)
        root_item.setExpanded(True)

    def _build_real_tree(self, parent_item: QTreeWidgetItem, folder: Path):
        try:
            entries = list(folder.iterdir())
        except OSError:
            return
        dirs = sorted((e for e in entries if e.is_dir()), key=lambda p: p.name.lower())
        files = sorted((e for e in entries if e.is_file()), key=lambda p: p.name.lower())

        for d in dirs:
            item = QTreeWidgetItem([d.name])
            item.setData(0, Qt.ItemDataRole.UserRole, ("folder", d))
            parent_item.addChild(item)
            self._build_real_tree(item, d)

        for f in files:
            item = QTreeWidgetItem([f.name])
            item.setData(0, Qt.ItemDataRole.UserRole, ("file", f))
            parent_item.addChild(item)

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
        if not data:
            return

        source_label = "Scenario A" if source_root == self.workspace.source_a_root else "Scenario B"
        menu = QMenu(self)

        if data[0] == "file":
            path: Path = data[1]
            action = menu.addAction(f"Copier / fusionner '{path.name}' vers la copie de travail")
            chosen = menu.exec(tree.viewport().mapToGlobal(pos))
            if chosen == action:
                self._copy_into_working(path, source_root, source_label)

        elif data[0] == "folder":
            folder: Path = data[1]
            if not folder.exists():
                return
            action = menu.addAction(f"Fusionner le dossier '{folder.name}' (et sous-dossiers) vers la copie de travail")
            chosen = menu.exec(tree.viewport().mapToGlobal(pos))
            if chosen == action:
                self._merge_folder_into_working_ui(folder, source_root, source_label)

    def _merge_folder_into_working_ui(self, folder: Path, source_root: Path, source_label: str):
        nb_files = sum(1 for _ in folder.rglob('*') if _.is_file())
        if nb_files == 0:
            QMessageBox.information(self, "Dossier vide", "Aucun fichier a fusionner dans ce dossier.")
            return
        confirm = QMessageBox.question(
            self, "Confirmer",
            f"Fusionner {nb_files} fichier(s) de '{folder.name}' (et sous-dossiers) vers la copie de travail ?"
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        progress = QProgressDialog(f"Fusion de {nb_files} fichier(s)...", None, 0, 0, self)
        progress.setWindowTitle("Veuillez patienter")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()

        try:
            highlights, id_conflicts, csv_reports = merge_folder_into_working(
                self.workspace, folder, source_root, source_label)
            self.workspace.rescan_working()
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "Erreur", f"Impossible de fusionner le dossier :\n{e}")
            return
        progress.close()

        self._highlights.update(highlights)
        self._populate_tree(self.tree_working, self.workspace.working)

        for path_touched in list(highlights.keys()) + list(csv_reports.keys()):
            for i in range(self.tabs.count()):
                if self.tabs.tabToolTip(i) == str(path_touched):
                    self.tabs.removeTab(i)

        if id_conflicts:
            details = "\n".join(
                f"- {c.kind} [{c.identity}] : \"{c.base_name}\" (copie de travail) "
                f"vs \"{c.conflicting_name}\" ({c.conflicting_source})"
                for c in id_conflicts[:20]
            )
            more = f"\n... et {len(id_conflicts) - 20} autre(s)" if len(id_conflicts) > 20 else ""
            QMessageBox.warning(
                self, "Conflits d'Id detectes",
                f"{len(id_conflicts)} bloc(s) au total n'ont pas ete fusionnes (Id partage "
                f"avec un materiel different) -- ajoutes desactives dans leurs fichiers respectifs "
                f"pour revue manuelle :\n\n{details}{more}"
            )

        n_csv_rows = sum(len(r) for r in csv_reports.values())
        self.statusBar().showMessage(
            f"Dossier fusionne : {nb_files} fichier(s) traites, {len(highlights)} fichier(s) .ecf "
            f"avec des changements, {len(csv_reports)} fichier(s) .csv completes "
            f"({n_csv_rows} ligne(s)), {len(id_conflicts)} conflit(s) d'Id au total"
        )

    def _copy_into_working(self, path: Path, source_root: Path, source_label: str):
        try:
            dest, highlight, id_conflicts, csv_report = merge_file_into_working(
                self.workspace, path, source_root, source_label)
            self.workspace.rescan_working()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible de copier/fusionner {path.name} :\n{e}")
            return

        if highlight:
            self._highlights[dest] = highlight
        else:
            self._highlights.pop(dest, None)

        self._populate_tree(self.tree_working, self.workspace.working)

        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(dest):
                self.tabs.removeTab(i)
                self.open_file_tab(dest, read_only=False)
                break

        if id_conflicts:
            details = "\n".join(
                f"- {c.kind} [{c.identity}] : \"{c.base_name}\" (copie de travail) "
                f"vs \"{c.conflicting_name}\" ({c.conflicting_source})"
                for c in id_conflicts
            )
            QMessageBox.warning(
                self, "Conflits d'Id detectes",
                f"{len(id_conflicts)} bloc(s) partagent un Id deja utilise par un element "
                f"DIFFERENT dans la copie de travail. Ils n'ont PAS ete fusionnes -- ajoutes "
                f"en fin de fichier, desactives (commentes), a traiter manuellement "
                f"(reassigner un Id libre) :\n\n{details}"
            )

        if csv_report is not None:
            if csv_report:
                self.statusBar().showMessage(
                    f"Fusionne (CSV) dans la copie de travail : {dest.name} -- "
                    f"{len(csv_report)} ligne(s) ajoutee(s)/completee(s) "
                    f"(les lignes deja presentes n'ont pas ete ecrasees)"
                )
            else:
                self.statusBar().showMessage(f"Fusionne (CSV) : {dest.name} -- aucun changement (deja a jour)")
        elif highlight and (highlight.new_blocks or highlight.changed_blocks):
            n_new = len(highlight.new_blocks)
            n_changed = len(highlight.changed_blocks)
            msg = (f"Fusionne dans la copie de travail : {dest.name} -- "
                   f"{n_new} bloc(s) nouveau(x), {n_changed} bloc(s) complete(s)")
            if id_conflicts:
                msg += f", {len(id_conflicts)} conflit(s) d'Id a revoir"
            self.statusBar().showMessage(msg)
        else:
            self.statusBar().showMessage(f"Copie vers la copie de travail : {dest}")

    def _copy_block_into_working(self, block: EcfBlock, source_file_path: Path,
                                  source_root: Path, source_label: str):
        """Fusionne UN SEUL bloc (point 3 : mise a jour ciblee sans tout refusionner)."""
        rel = source_file_path.relative_to(source_root)
        try:
            dest, status, highlight = merge_block_into_working(self.workspace, rel, block, source_label)
            self.workspace.rescan_working()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible de copier ce bloc :\n{e}")
            return

        if highlight:
            self._highlights[dest] = highlight

        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(dest):
                self.tabs.removeTab(i)
                self.open_file_tab(dest, read_only=False)
                break

        if status == 'conflict':
            QMessageBox.warning(
                self, "Conflit d'Id",
                f"Ce bloc partage un Id deja utilise par un element DIFFERENT dans la "
                f"copie de travail. Il n'a PAS ete fusionne -- ajoute en fin de fichier, "
                f"desactive (commente), a traiter manuellement."
            )
            self.statusBar().showMessage(f"Conflit d'Id detecte sur {dest.name} -- bloc ajoute desactive")
        elif status == 'added':
            self.statusBar().showMessage(f"Bloc ajoute dans {dest.name}")
        else:
            self.statusBar().showMessage(f"Bloc fusionne (complete) dans {dest.name}")

    def _copy_csv_row_into_working(self, row: list, source_file_path: Path,
                                    source_root: Path, source_label: str):
        """Copie UNE SEULE ligne CSV (par cle) vers le fichier correspondant de la
        copie de travail, sans toucher au reste du fichier."""
        rel = source_file_path.relative_to(source_root)
        try:
            dest, status = merge_csv_row_into_working(self.workspace, rel, row)
            self.workspace.rescan_working()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible de copier cette ligne :\n{e}")
            return

        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(dest):
                self.tabs.removeTab(i)
                self.open_file_tab(dest, read_only=False)
                break

        key = row[0] if row else "?"
        if status == 'added':
            self.statusBar().showMessage(f"Ligne '{key}' ajoutee dans {dest.name}")
        elif status == 'merged':
            self.statusBar().showMessage(f"Ligne '{key}' completee (cellules vides) dans {dest.name}")
        else:
            self.statusBar().showMessage(f"Ligne '{key}' deja a jour dans {dest.name} -- rien a changer")

    def _translate_csv_cell_into_working(self, key: str, text: str, target_code: str, target_label: str,
                                          source_file_path: Path, source_root: Path, source_label: str):
        """Traduit une cellule d'une vue lecture seule (Scenario A/B) et applique le
        resultat directement dans la cellule correspondante (meme cle, colonne de la
        langue cible) de la copie de travail -- sans jamais ecraser une valeur deja
        presente."""
        from core import translation
        if not translation.is_available():
            QMessageBox.warning(self, "Traduction indisponible",
                                 "deep-translator n'est pas installe.\nLance : pip install deep-translator")
            return
        try:
            translated = translation.translate_text(text, target=target_code)
        except Exception as e:
            QMessageBox.critical(self, "Erreur de traduction",
                                  f"La traduction a echoue :\n{e}\n\nVerifie ta connexion internet.")
            return

        rel = source_file_path.relative_to(source_root)
        try:
            dest, status = translate_csv_cell_into_working(
                self.workspace, rel, key, target_code, target_label, translated)
            self.workspace.rescan_working()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible d'appliquer la traduction :\n{e}")
            return

        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(dest):
                self.tabs.removeTab(i)
                self.open_file_tab(dest, read_only=False)
                break

        if status == 'added':
            self.statusBar().showMessage(f"Ligne '{key}' ajoutee avec la traduction ({target_label}) dans {dest.name}")
        elif status == 'merged':
            self.statusBar().showMessage(f"Traduction ({target_label}) ajoutee pour '{key}' dans {dest.name}")
        else:
            self.statusBar().showMessage(
                f"'{key}' avait deja une valeur dans la colonne {target_label} -- "
                f"rien change (copie de travail prioritaire)"
            )

    # ------------------------------------------------------------------
    # Ouverture de fichiers (lecture seule pour A/B, meme vue pour l'instant sur
    # la copie de travail -- l'edition inline viendra dans une passe suivante)
    # ------------------------------------------------------------------

    def _on_source_double_clicked(self, item: QTreeWidgetItem, source_root):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data or data[0] != "file":
            return
        source_label = "Scenario A" if source_root == self.workspace.source_a_root else "Scenario B"
        self.open_file_tab(data[1], read_only=True, source_root=source_root, source_label=source_label)

    def _on_working_double_clicked(self, item: QTreeWidgetItem, column: int):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data or data[0] != "file":
            return
        self.open_working_file_tab(data[1])

    def open_working_file_tab(self, path: Path):
        """Ouvre un fichier de la copie de travail en edition, avec la (ou les) source(s)
        A/B correspondante(s) affichee(s) cote a cote si elles existent (uniquement
        pour les .ecf pour l'instant)."""
        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(path):
                self.tabs.setCurrentIndex(i)
                return

        ext = path.suffix.lower()

        if ext == '.csv':
            try:
                widget = CsvEditWidget(path)
            except Exception as e:
                QMessageBox.critical(self, "Erreur de lecture", f"Impossible d'ouvrir {path.name} :\n{e}")
                return
            index = self.tabs.addTab(widget, "✎ " + path.name)
            self.tabs.setTabToolTip(index, str(path))
            self.tabs.setCurrentIndex(index)
            widget.modified_changed.connect(lambda modified, w=widget: self._update_tab_title(w, modified))
            widget.saved.connect(lambda w=widget: self.statusBar().showMessage(f"Enregistre : {w.path}"))
            return

        if ext != '.ecf':
            # Pas encore d'edition pour les autres formats -- vue lecture seule standard
            self.open_file_tab(path, read_only=False)
            return

        try:
            rel = path.relative_to(self.workspace.working_root)
        except ValueError:
            rel = None

        compare_sources = {}
        if rel is not None:
            candidate_a = self.workspace.source_a_root / rel
            if candidate_a.exists() and candidate_a != path:
                compare_sources["Scenario A"] = (candidate_a, self.workspace.source_a_root)
            if self.workspace.is_merge_mode:
                candidate_b = self.workspace.source_b_root / rel
                if candidate_b.exists():
                    compare_sources["Scenario B"] = (candidate_b, self.workspace.source_b_root)

        def _copy_block_cb(block, source_path, source_root, source_label):
            self._copy_block_into_working(block, source_path, source_root, source_label)

        try:
            widget = CompareWidget(path, compare_sources, EcfViewWidget, copy_block_callback=_copy_block_cb)
        except Exception as e:
            QMessageBox.critical(self, "Erreur de lecture", f"Impossible d'ouvrir {path.name} :\n{e}")
            return

        index = self.tabs.addTab(widget, "✎ " + path.name)
        self.tabs.setTabToolTip(index, str(path))
        self.tabs.setCurrentIndex(index)

        widget.modified_changed.connect(lambda modified, w=widget: self._update_tab_title(w, modified))
        widget.saved.connect(lambda w=widget: self.statusBar().showMessage(f"Enregistre : {w.edit_widget.path}"))

    def _update_tab_title(self, widget, modified: bool):
        idx = self.tabs.indexOf(widget)
        if idx == -1:
            return
        inner = getattr(widget, 'edit_widget', widget)  # CompareWidget a un sous-widget, CsvEditWidget non
        base = inner.path.name
        self.tabs.setTabText(idx, ("✎ * " if modified else "✎ ") + base)

    def open_file_tab(self, path: Path, read_only: bool,
                       source_root: Optional[Path] = None, source_label: Optional[str] = None):
        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(path):
                self.tabs.setCurrentIndex(i)
                return

        ext = path.suffix.lower()
        try:
            if ext == '.ecf':
                highlight = self._highlights.get(path)
                on_copy_block = None
                if read_only and source_root and source_label:
                    on_copy_block = lambda block: self._copy_block_into_working(
                        block, path, source_root, source_label)
                widget = EcfViewWidget(path, highlight=highlight, on_copy_block=on_copy_block,
                                        copy_label=source_label)
            elif ext in ('.yaml', '.yml'):
                widget = YamlViewWidget(path)
            elif ext == '.csv':
                on_copy_row = None
                on_translate_cell = None
                if read_only and source_root and source_label:
                    on_copy_row = lambda row: self._copy_csv_row_into_working(
                        row, path, source_root, source_label)
                    on_translate_cell = lambda key, text, code, label: self._translate_csv_cell_into_working(
                        key, text, code, label, path, source_root, source_label)
                widget = CsvEditWidget(path, editable=False, on_copy_row=on_copy_row,
                                        copy_label=source_label, on_translate_cell=on_translate_cell)
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
    """Vue en lecture d'un fichier .ecf : arbre des blocs a gauche, proprietes a droite.
    Si `highlight` est fourni (suite a une fusion), colore les blocs/proprietes ajoutes.
    Si `on_copy_block` est fourni (vue d'une source A/B), un clic droit sur un bloc
    propose de le fusionner vers la copie de travail SANS toucher au reste du fichier."""

    def __init__(self, path: Path, highlight: Optional[MergeHighlight] = None,
                 on_copy_block=None, copy_label: Optional[str] = None):
        super().__init__()
        self.path = path
        self.highlight = highlight
        self.on_copy_block = on_copy_block
        self.copy_label = copy_label
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

        # -- Barre de recherche : indispensable des que le fichier a beaucoup de blocs
        # (certains ECF reels en ont plus de 5000 au niveau racine, impossible a
        # reperer en faisant defiler manuellement une liste non triee) --
        search_row = QHBoxLayout()
        search_row.setSpacing(4)
        search_row.addWidget(QLabel("Rechercher (Id / Name) :"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Tape un Id ou un nom, puis Entree pour sauter au suivant...")
        self.search_box.returnPressed.connect(self._search_next)
        search_row.addWidget(self.search_box)
        self.search_status = QLabel("")
        search_row.addWidget(self.search_status)
        btn_filter = QPushButton("Filtrer par propriete...")
        btn_filter.clicked.connect(self._open_property_filter)
        search_row.addWidget(btn_filter)
        layout.addLayout(search_row, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Bloc"])
        self._populate_tree()
        self.tree.itemClicked.connect(self._on_block_selected)
        if self.on_copy_block:
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
            self.search_status.setText("Aucun resultat")
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

        menu = QMenu(self)
        action = menu.addAction(f"Copier / fusionner ce bloc ({label}) vers la copie de travail")
        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen == action:
            self.on_copy_block(block)

    def _populate_tree(self):
        for node in self.doc.nodes:
            if isinstance(node, EcfBlock):
                self.tree.addTopLevelItem(self._make_block_item(node))

    def _make_block_item(self, block: EcfBlock) -> QTreeWidgetItem:
        ident = block_identity(block)
        label = f"{block.kind} [{ident}]" if ident else block.kind
        name = block.get_property('Name')
        if name and name != ident:
            label += f"  - {name}"
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


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    # Propose de reprendre un projet recent des le lancement, s'il y en a
    from PyQt6.QtCore import QTimer
    QTimer.singleShot(0, lambda: window.show_startup_dialog(auto_at_launch=True))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
