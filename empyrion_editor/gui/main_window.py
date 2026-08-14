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
import shutil
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QTreeWidget, QTreeWidgetItem,
    QTabWidget, QSplitter, QTableWidget, QTableWidgetItem, QWidget, QVBoxLayout,
    QHBoxLayout, QLineEdit, QLabel, QStatusBar, QHeaderView, QMessageBox, QMenu,
    QProgressDialog, QInputDialog, QPushButton, QSizePolicy, QDialog, QCheckBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTreeWidgetItemIterator
from PyQt6.QtGui import QColor, QBrush

from core.scanner import scan_scenario
from core.models import Scenario, FileEntry
from core.workspace import (
    Workspace, open_workspace, load_existing_workspace, copy_file_into_working,
    merge_file_into_working, merge_folder_into_working, merge_block_into_working,
    merge_csv_row_into_working, translate_csv_cell_into_working,
    duplicate_ecf_block_into_working, duplicate_csv_row_into_working,
    copy_yaml_entry_into_working, duplicate_yaml_entry_into_working, MergeHighlight,
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
from core import i18n
from core.i18n import t
from core.project_store import ProjectRecord

from gui.new_project_dialog import NewProjectDialog
from gui.startup_dialog import StartupDialog
from gui.ecf_edit_widget import EcfEditWidget, CompareWidget, PendingConflictsDialog, PropertyFilterDialog, _block_own_keys
from gui.csv_edit_widget import CsvEditWidget
from gui.yaml_edit_widget import YamlEditWidget
from gui.txt_edit_widget import TxtEditWidget
from gui.wiki_viewer import open_wiki
from gui.theme import NAVY, PRIMARY_DARK, PRIMARY, icon, icon_size
from core.workspace_undo import WorkspaceUndoStack, FileStateUndo, MultiFileStateUndo, FolderStateUndo, capture_file, capture_folder

COLOR_NEW_BLOCK = QBrush(QColor(200, 255, 200))       # vert clair : bloc entierement nouveau
COLOR_CHANGED_BLOCK = QBrush(QColor(255, 240, 200))   # orange clair : bloc complete partiellement
COLOR_NEW_PROPERTY = QBrush(QColor(200, 255, 200))    # vert clair : ligne de propriete ajoutee


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Empyrion Scenario Editor")
        self.resize(1500, 800)
        self.workspace_undo = WorkspaceUndoStack()

        self.workspace: Optional[Workspace] = None
        self._highlights: dict = {}  # Path -> MergeHighlight, pour colorer les ajouts de fusion

        self._build_menu()
        self._build_toolbar()
        self._refresh_scenario_b_menu_text()
        self._build_layout()
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(t("status.no_project"))

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------

    def _build_menu(self):
        self.menu_file = self.menuBar().addMenu(t("menu.file"))
        self.action_new = self.menu_file.addAction(t("menu.file.new_project"))
        self.action_new.triggered.connect(self.new_project_dialog)
        self.action_recent = self.menu_file.addAction(t("menu.file.recent_projects"))
        self.action_recent.triggered.connect(self.show_startup_dialog)
        self.menu_file.addSeparator()
        self.action_save = self.menu_file.addAction(t("menu.file.save"))
        self.action_save.setShortcut("Ctrl+S")
        self.action_save.triggered.connect(self._save_current_tab)
        self.menu_file.addSeparator()
        self.action_compare = self.menu_file.addAction(t("menu.file.compare"))
        self.action_compare.triggered.connect(self._open_compare_dialog)
        self.action_manage_scenario_b = self.menu_file.addAction(t("menu.file.open_scenario_b"))
        self.action_manage_scenario_b.triggered.connect(self._open_or_change_scenario_b)
        self.action_remove_scenario_b = self.menu_file.addAction(t("menu.file.remove_scenario_b"))
        self.action_remove_scenario_b.triggered.connect(self._remove_scenario_b)
        self.action_remove_scenario_b.setEnabled(False)
        self.action_backup_scenario = self.menu_file.addAction(t("menu.file.backup_scenario"))
        self.action_backup_scenario.triggered.connect(lambda: self._open_backup_dialog('scenario'))
        self.action_manage_saves = self.menu_file.addAction(t("menu.file.manage_saves"))
        self.action_manage_saves.triggered.connect(lambda: self._open_backup_dialog('savegame'))
        self.action_repair_permissions = self.menu_file.addAction(t("menu.file.repair_permissions"))
        self.action_repair_permissions.triggered.connect(self._repair_working_copy_permissions)
        self.menu_file.addSeparator()
        self.action_quit = self.menu_file.addAction(t("menu.file.quit"))
        self.action_quit.triggered.connect(self.close)

        self.menu_check = self.menuBar().addMenu(t("menu.verification"))
        self.action_refs = self.menu_check.addAction(t("menu.verification.check_refs"))
        self.action_refs.triggered.connect(self.check_references_dialog)
        self.action_pending = self.menu_check.addAction(t("menu.verification.pending"))
        self.action_pending.triggered.connect(self.check_pending_conflicts_dialog)

        self.menu_options = self.menuBar().addMenu(t("menu.options"))
        self.action_author = self.menu_options.addAction(t("menu.options.author"))
        self.action_author.triggered.connect(self._set_author_dialog)
        self.action_toggle_annotations = self.menu_options.addAction(t("menu.options.annotations"))
        self.action_toggle_annotations.setCheckable(True)
        self.action_toggle_annotations.setChecked(settings.get_annotations_enabled())
        self.action_toggle_annotations.toggled.connect(settings.set_annotations_enabled)
        self.action_toggle_merge = self.menu_options.addAction(t("menu.options.merge_enabled"))
        self.action_toggle_merge.setCheckable(True)
        self.action_toggle_merge.setChecked(settings.get_merge_enabled())
        self.action_toggle_merge.toggled.connect(settings.set_merge_enabled)

        self.menu_help = self.menuBar().addMenu(t("menu.help"))
        self.action_wiki_app = self.menu_help.addAction(t("menu.help.wiki_app"))
        self.action_wiki_app.triggered.connect(
            lambda: open_wiki(self, t("menu.help.wiki_app").rstrip("."), "wiki_app"))
        self.action_wiki_empyrion = self.menu_help.addAction(t("menu.help.wiki_empyrion"))
        self.action_wiki_empyrion.triggered.connect(
            lambda: open_wiki(self, t("menu.help.wiki_empyrion").rstrip("."), "wiki_empyrion"))

    def _toggle_language(self):
        current = i18n.get_language()
        new_lang = "en" if current == "fr" else "fr"
        i18n.set_language(new_lang)
        self._apply_language()

    def _apply_language(self):
        """Reassigne le texte de tous les elements de menu traduits, sans reconstruire
        la structure (garde les connexions de signaux intactes)."""
        self.menu_file.setTitle(t("menu.file"))
        self.action_new.setText(t("menu.file.new_project"))
        self.action_recent.setText(t("menu.file.recent_projects"))
        self.action_save.setText(t("menu.file.save"))
        self.action_compare.setText(t("menu.file.compare"))
        self._refresh_scenario_b_menu_text()
        self.action_backup_scenario.setText(t("menu.file.backup_scenario"))
        self.action_manage_saves.setText(t("menu.file.manage_saves"))
        self.action_repair_permissions.setText(t("menu.file.repair_permissions"))
        self.action_quit.setText(t("menu.file.quit"))

        self.menu_check.setTitle(t("menu.verification"))
        self.action_refs.setText(t("menu.verification.check_refs"))
        self.action_pending.setText(t("menu.verification.pending"))

        self.menu_options.setTitle(t("menu.options"))
        self.action_author.setText(t("menu.options.author"))
        self.action_toggle_annotations.setText(t("menu.options.annotations"))
        self.action_toggle_merge.setText(t("menu.options.merge_enabled"))

        self.menu_help.setTitle(t("menu.help"))
        self.action_wiki_app.setText(t("menu.help.wiki_app"))
        self.action_wiki_empyrion.setText(t("menu.help.wiki_empyrion"))

        self.btn_language.setText(i18n.get_language().upper())
        self.btn_language.setToolTip(t("menu.options.language"))
        self.btn_workspace_undo.setText(t("wsundo.button"))
        self._refresh_workspace_undo_button()

    def _build_toolbar(self):
        toolbar = self.addToolBar("Langue / Language")
        toolbar.setMovable(False)
        self.btn_workspace_undo = QPushButton(icon("fa5s.undo", "#ffffff"), t("wsundo.button"))
        self.btn_workspace_undo.setIconSize(icon_size())
        self.btn_workspace_undo.setToolTip(t("wsundo.tooltip_empty"))
        self.btn_workspace_undo.setEnabled(False)
        self.btn_workspace_undo.clicked.connect(self._undo_workspace_action)
        toolbar.addWidget(self.btn_workspace_undo)
        from PyQt6.QtGui import QKeySequence, QShortcut
        QShortcut(QKeySequence.StandardKey.Undo, self, activated=self._undo_workspace_action)

        self.btn_language = QPushButton(icon("fa5s.globe", "#ffffff"), i18n.get_language().upper())
        self.btn_language.setIconSize(icon_size())
        self.btn_language.setFixedWidth(75)
        self.btn_language.setToolTip(t("menu.options.language"))
        self.btn_language.clicked.connect(self._toggle_language)
        toolbar.addWidget(self.btn_language)

    def _push_workspace_undo(self, action):
        self.workspace_undo.push(action)
        self._refresh_workspace_undo_button()

    def _refresh_workspace_undo_button(self):
        if self.workspace_undo.can_undo():
            self.btn_workspace_undo.setEnabled(True)
            self.btn_workspace_undo.setToolTip(
                t("wsundo.tooltip_action", label=self.workspace_undo.peek_label()))
        else:
            self.btn_workspace_undo.setEnabled(False)
            self.btn_workspace_undo.setToolTip(t("wsundo.tooltip_empty"))

    def _undo_workspace_action(self):
        if not self.workspace_undo.can_undo():
            return
        label = self.workspace_undo.undo()
        if not self.workspace:
            return
        self.workspace.rescan_working()
        self._populate_tree(self.tree_working, self.workspace.working)
        # Ferme tout onglet ouvert sur un fichier potentiellement touche par
        # l'annulation -- plus sur de le rouvrir a froid que de tenter de
        # rafraichir un editeur peut-etre desynchronise de son fichier.
        for i in reversed(range(self.tabs.count())):
            self.tabs.removeTab(i)
        self._refresh_workspace_undo_button()
        self.statusBar().showMessage(t("wsundo.status_done", label=label))

    def _save_current_tab(self):
        widget = self.tabs.currentWidget()
        if widget and hasattr(widget, 'save'):
            widget.save()
        else:
            self.statusBar().showMessage(t("status.nothing_to_save"))

    def _open_compare_dialog(self):
        from gui.scenario_compare_dialog import ScenarioCompareDialog
        dialog = ScenarioCompareDialog(self)
        dialog.exec()

    def _refresh_scenario_b_menu_text(self):
        """Met a jour le libelle du menu Scenario B selon l'etat actuel (aucun projet
        ouvert / pas de Scenario B / Scenario B deja defini) et active/desactive le
        retrait en consequence."""
        if self.workspace and self.workspace.is_merge_mode:
            self.action_manage_scenario_b.setText(t("menu.file.change_scenario_b"))
            self.action_remove_scenario_b.setEnabled(True)
        else:
            self.action_manage_scenario_b.setText(t("menu.file.open_scenario_b"))
            self.action_remove_scenario_b.setEnabled(False)
        self.action_remove_scenario_b.setText(t("menu.file.remove_scenario_b"))

    def _open_or_change_scenario_b(self):
        if not self.workspace:
            QMessageBox.information(self, t("err.missing_field"), t("status.no_project"))
            return
        folder = QFileDialog.getExistingDirectory(self, t("scenariob.choose_folder"))
        if not folder:
            return
        new_root = Path(folder)

        if self.workspace.is_merge_mode:
            confirm = QMessageBox.question(
                self, t("scenariob.confirm_change_title"),
                t("scenariob.confirm_change_msg", old=self.workspace.source_b_root.name, new=new_root.name)
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        self.workspace.set_scenario_b(new_root)
        self._refresh_all_trees()
        self._refresh_scenario_b_menu_text()
        self.statusBar().showMessage(t("status.scenario_b_set", name=new_root.name))

    def _remove_scenario_b(self):
        if not self.workspace or not self.workspace.is_merge_mode:
            return
        name = self.workspace.source_b_root.name
        confirm = QMessageBox.question(
            self, t("scenariob.confirm_remove_title"), t("scenariob.confirm_remove_msg", name=name))
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.workspace.set_scenario_b(None)
        self._refresh_all_trees()
        self._refresh_scenario_b_menu_text()
        self.statusBar().showMessage(t("status.scenario_b_removed"))

    def _open_backup_dialog(self, kind: str):
        from gui.backup_dialog import BackupManagerDialog
        dialog = BackupManagerDialog(kind, self)
        dialog.exec()

    def _repair_working_copy_permissions(self):
        if not self.workspace:
            QMessageBox.information(self, t("err.missing_field"), t("repair.no_project_msg"))
            return
        from core.fsutil import clear_readonly
        clear_readonly(self.workspace.working_root)
        QMessageBox.information(self, t("repair.done_title"), t("repair.done_msg"))

    def _set_author_dialog(self):
        current = settings.get_author()
        name, ok = QInputDialog.getText(self, t("author.title"), t("author.label"), text=current)
        if ok and name.strip():
            settings.set_author(name.strip())

    def check_pending_conflicts_dialog(self):
        if not self.workspace:
            QMessageBox.information(self, t("err.no_project_title"), t("err.no_project_msg"))
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
            QMessageBox.information(self, t("pending.none_title"), t("pending.none_msg"))
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
                QMessageBox.critical(self, t("err.title"), t("pending.not_found_msg"))
                return

            success = activate_pending_conflict(doc, match, new_id)
            if not success:
                QMessageBox.critical(self, t("err.title"), t("pending.cannot_activate_msg"))
                return

            prior = capture_file(target_path)
            with open(target_path, 'w', encoding='utf-8', newline='') as f:
                f.write(doc.render())
        except Exception as e:
            QMessageBox.critical(self, t("err.title"), f"{t('pending.activation_error')} :\n{e}")
            return

        self._push_workspace_undo(
            FileStateUndo(target_path, prior, t("wsundo.activate_pending", name=target_path.name)))

        self.workspace.rescan_working()
        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(target_path):
                self.tabs.removeTab(i)

        self.statusBar().showMessage(t("status.block_activated", id=new_id, file=target_path.name))
        QMessageBox.information(self, t("pending.activated_title"),
                                 t("pending.activated_msg", id=new_id, file=target_path.name))

    def check_references_dialog(self):
        if not self.workspace:
            QMessageBox.information(self, t("err.no_project_title"), t("err.no_project_msg"))
            return

        ecf_files = [f.path for f in self.workspace.working.configuration if f.extension == '.ecf']
        if not ecf_files:
            QMessageBox.information(self, t("err.no_file_title"), t("check.no_ecf_found"))
            return

        progress = QProgressDialog(f"Verification de {len(ecf_files)} fichier(s)...", None, 0, 0, self)
        progress.setWindowTitle(t("progress.please_wait"))
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()

        try:
            broken = check_references(ecf_files)
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, t("err.title"), f"{t('check.verification_error')} :\n{e}")
            return
        progress.close()

        if not broken:
            QMessageBox.information(self, t("check.refs_title"), t("check.refs_ok", n=len(ecf_files)))
            return

        details = "\n".join(b.label() for b in broken[:100])
        more = t("check.refs_more", n=len(broken) - 100) if len(broken) > 100 else ""
        QMessageBox.warning(
            self, t("check.refs_broken_title"),
            t("check.refs_broken_msg", n=len(broken), details=details, more=more)
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
        self.label_a = QLabel(t("panel.scenario_a"))
        self.label_a.setStyleSheet(f"font-weight: 700; color: {NAVY};")
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
        self.label_working = QLabel(t("panel.working_copy"))
        self.label_working.setStyleSheet(f"font-weight: 700; color: {PRIMARY_DARK};")
        self.tree_working = QTreeWidget()
        self.tree_working.setHeaderLabels(["Copie de travail"])
        self.tree_working.itemDoubleClicked.connect(self._on_working_double_clicked)
        self.tree_working.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_working.customContextMenuRequested.connect(self._show_working_context_menu)
        layout_w.addWidget(self.label_working)
        layout_w.addWidget(self.tree_working)
        bottom_splitter.addWidget(self.panel_working)

        self.panel_b = QWidget()
        layout_b = QVBoxLayout(self.panel_b)
        layout_b.setContentsMargins(4, 2, 4, 2)
        self.label_b = QLabel(t("panel.scenario_b"))
        self.label_b.setStyleSheet(f"font-weight: 700; color: {NAVY};")
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
        progress.setWindowTitle(t("progress.please_wait"))
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()

        try:
            self.workspace = open_workspace(dialog.source_a_path, dialog.dest_path, dialog.source_b_path)
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, t("err.title"), f"{t('err.create_project')} :\n{e}")
            return
        progress.close()

        self._highlights = {}
        self._refresh_all_trees()
        self.tabs.clear()

        self._remember_current_project()

        mode = t("status.mode_merge") if self.workspace.is_merge_mode else t("status.mode_simple")
        self.statusBar().showMessage(
            t("status.project_opened", mode=mode, path=self.workspace.working_root)
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
                QMessageBox.information(self, t("recent.none_title"), t("recent.none_msg"))
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
            QMessageBox.critical(self, t("err.title"),
                                  f"{t('recent.resume_error')} :\n{e}\n\n{t('recent.resume_error_hint')}")
            return

        self._highlights = {}
        self._refresh_all_trees()
        self.tabs.clear()
        self._remember_current_project()  # remonte ce projet en tete de la liste recente

        mode = t("status.mode_merge") if self.workspace.is_merge_mode else t("status.mode_simple")
        self.statusBar().showMessage(
            t("status.project_resumed", mode=mode, path=self.workspace.working_root)
        )

    def _refresh_all_trees(self):
        if not self.workspace:
            return
        self.label_a.setText(t("panel.scenario_a_named", name=self.workspace.source_a_root.name))
        self._populate_tree(self.tree_a, self.workspace.source_a)

        self.label_working.setText(t("panel.working_copy_named", name=self.workspace.working_root.name))
        self._populate_tree(self.tree_working, self.workspace.working)

        if self.workspace.is_merge_mode:
            self.panel_b.setVisible(True)
            self.label_b.setText(t("panel.scenario_b_named", name=self.workspace.source_b_root.name))
            self._populate_tree(self.tree_b, self.workspace.source_b)
        else:
            self.panel_b.setVisible(False)

        self._refresh_scenario_b_menu_text()

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
        merge_enabled = settings.get_merge_enabled()

        if data[0] == "file":
            path: Path = data[1]
            action_merge = menu.addAction(t("file.merge_action", name=path.name))
            if not merge_enabled:
                action_merge.setEnabled(False)
                action_merge.setToolTip(t("merge.disabled_msg"))
            action_dup = menu.addAction(t("file.duplicate_action", name=path.name))
            chosen = menu.exec(tree.viewport().mapToGlobal(pos))
            if chosen == action_merge and merge_enabled:
                self._copy_into_working(path, source_root, source_label)
            elif chosen == action_dup:
                self._duplicate_file_into_working(path, source_root, source_label)

        elif data[0] == "folder":
            folder: Path = data[1]
            if not folder.exists():
                return
            action = menu.addAction(t("folder.merge_action", name=folder.name))
            if not merge_enabled:
                action.setEnabled(False)
                action.setToolTip(t("merge.disabled_msg"))
            chosen = menu.exec(tree.viewport().mapToGlobal(pos))
            if chosen == action and merge_enabled:
                self._merge_folder_into_working_ui(folder, source_root, source_label)

    def _show_working_context_menu(self, pos):
        if not self.workspace:
            return
        item = self.tree_working.itemAt(pos)
        if not item:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        menu = QMenu(self)

        if data[0] == "file":
            path: Path = data[1]
            action_delete = menu.addAction(t("file.delete_action", name=path.name))
            chosen = menu.exec(self.tree_working.viewport().mapToGlobal(pos))
            if chosen == action_delete:
                self._delete_working_file(path)

        elif data[0] == "folder":
            folder: Path = data[1]
            action_delete = menu.addAction(t("folder.delete_action", name=folder.name))
            chosen = menu.exec(self.tree_working.viewport().mapToGlobal(pos))
            if chosen == action_delete:
                self._delete_working_folder(folder)

    def _delete_working_file(self, path: Path):
        confirm = QMessageBox.question(
            self, t("backup.confirm_delete_title"), t("delete.confirm_file_msg", name=path.name))
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            prior = capture_file(path)
            from core.fsutil import clear_readonly
            clear_readonly(path)
            path.unlink()
            self.workspace.rescan_working()
        except Exception as e:
            QMessageBox.critical(self, t("delete.error"), str(e))
            return

        self._push_workspace_undo(FileStateUndo(path, prior, t("wsundo.delete_file", name=path.name)))

        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(path):
                self.tabs.removeTab(i)
                break

        self._populate_tree(self.tree_working, self.workspace.working)
        self.statusBar().showMessage(t("status.file_deleted", name=path.name))

    def _delete_working_folder(self, folder: Path):
        confirm = QMessageBox.question(
            self, t("backup.confirm_delete_title"), t("delete.confirm_folder_msg", name=folder.name))
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            existed, prior_files = capture_folder(folder)
            from core.fsutil import clear_readonly
            clear_readonly(folder)
            shutil.rmtree(folder)
            self.workspace.rescan_working()
        except Exception as e:
            QMessageBox.critical(self, t("delete.error"), str(e))
            return

        self._push_workspace_undo(
            FolderStateUndo(folder, existed, prior_files, t("wsundo.delete_folder", name=folder.name)))

        folder_str = str(folder)
        for i in reversed(range(self.tabs.count())):
            tooltip = self.tabs.tabToolTip(i)
            if tooltip and tooltip.startswith(folder_str):
                self.tabs.removeTab(i)

        self._populate_tree(self.tree_working, self.workspace.working)
        self.statusBar().showMessage(t("status.folder_deleted", name=folder.name))

    def _merge_folder_into_working_ui(self, folder: Path, source_root: Path, source_label: str):
        nb_files = sum(1 for _ in folder.rglob('*') if _.is_file())
        if nb_files == 0:
            QMessageBox.information(self, t("merge.empty_folder_title"), t("merge.empty_folder_msg"))
            return
        confirm = QMessageBox.question(
            self, t("merge.confirm_title"),
            t("merge.confirm_folder_msg", n=nb_files, folder=folder.name)
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        rel = folder.relative_to(source_root)
        working_folder = self.workspace.working_root / rel
        existed_before, prior_files = capture_folder(working_folder)

        progress = QProgressDialog(f"Fusion de {nb_files} fichier(s)...", None, 0, 0, self)
        progress.setWindowTitle(t("progress.please_wait"))
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
            QMessageBox.critical(self, t("err.title"), f"{t('merge.folder_error')} :\n{e}")
            return
        progress.close()

        self._push_workspace_undo(
            FolderStateUndo(working_folder, existed_before, prior_files,
                             t("wsundo.merge_folder", name=folder.name)))

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
            more = t("merge.id_conflicts_more", n=len(id_conflicts) - 20) if len(id_conflicts) > 20 else ""
            QMessageBox.warning(
                self, t("merge.id_conflicts_title"),
                t("merge.id_conflicts_folder_msg", n=len(id_conflicts), details=details, more=more)
            )

        n_csv_rows = sum(len(r) for r in csv_reports.values())
        self.statusBar().showMessage(
            t("status.folder_merged", n=nb_files, ecf=len(highlights), csv=len(csv_reports),
              rows=n_csv_rows, conflicts=len(id_conflicts))
        )

    def _copy_into_working(self, path: Path, source_root: Path, source_label: str):
        rel = path.relative_to(source_root)
        dest_before = self.workspace.working_root / rel
        prior = capture_file(dest_before)
        try:
            dest, highlight, id_conflicts, csv_report = merge_file_into_working(
                self.workspace, path, source_root, source_label)
            self.workspace.rescan_working()
        except Exception as e:
            QMessageBox.critical(self, t("err.title"), f"{t('merge.file_error', file=path.name)} :\n{e}")
            return

        self._push_workspace_undo(FileStateUndo(dest, prior, t("wsundo.merge_file", name=dest.name)))

        if highlight:
            self._highlights[dest] = highlight
        else:
            self._highlights.pop(dest, None)

        self._populate_tree(self.tree_working, self.workspace.working)

        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(dest):
                self.tabs.removeTab(i)
                self.open_working_file_tab(dest)
                break

        if id_conflicts:
            details = "\n".join(
                f"- {c.kind} [{c.identity}] : \"{c.base_name}\" (copie de travail) "
                f"vs \"{c.conflicting_name}\" ({c.conflicting_source})"
                for c in id_conflicts
            )
            QMessageBox.warning(
                self, t("merge.id_conflicts_title"),
                t("merge.id_conflicts_file_msg", n=len(id_conflicts), details=details)
            )

        if csv_report is not None:
            if csv_report:
                self.statusBar().showMessage(
                    t("status.csv_merged_rows", file=dest.name, n=len(csv_report))
                )
            else:
                self.statusBar().showMessage(t("status.csv_merged_none", file=dest.name))
        elif highlight and (highlight.new_blocks or highlight.changed_blocks):
            n_new = len(highlight.new_blocks)
            n_changed = len(highlight.changed_blocks)
            msg = t("status.merged_working", file=dest.name, new=n_new, changed=n_changed)
            if id_conflicts:
                msg += t("status.id_conflicts_suffix", n=len(id_conflicts))
            self.statusBar().showMessage(msg)
        else:
            self.statusBar().showMessage(t("status.copied_to_working", dest=dest))

    def _duplicate_file_into_working(self, path: Path, source_root: Path, source_label: str):
        """Copie un fichier depuis Scenario A/B vers la copie de travail sous un
        NOUVEAU nom, comme fichier independant -- ne fusionne PAS avec un fichier de
        meme nom deja present. Utile pour garder deux versions distinctes d'un meme
        fichier (ex: comparer manuellement Templates.ecf de A et de B cote a cote)."""
        rel = path.relative_to(source_root)
        suffix_letter = "A" if source_label == "Scenario A" else "B"
        suggestion = f"{rel.stem}_{suffix_letter}{rel.suffix}"

        new_name, ok = QInputDialog.getText(
            self, t("dupfile.title"), t("dupfile.new_name_label"), text=suggestion)
        if not ok or not new_name.strip():
            return
        new_name = new_name.strip()

        dest = self.workspace.working_root / rel.parent / new_name
        if dest.exists():
            QMessageBox.warning(self, t("dupfile.exists_title"), t("dupfile.exists_msg", name=new_name))
            return

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            from core.fsutil import clear_readonly
            clear_readonly(dest)
            self.workspace.rescan_working()
        except Exception as e:
            QMessageBox.critical(self, t("err.title"), f"{t('merge.file_error', file=path.name)} :\n{e}")
            return

        self._push_workspace_undo(FileStateUndo(dest, None, t("wsundo.duplicate_file", name=new_name)))
        self._populate_tree(self.tree_working, self.workspace.working)
        self.statusBar().showMessage(t("status.file_duplicated", name=new_name))

    def _duplicate_ecf_block_dialog(self, block: EcfBlock, parent_chain: list, source_file_path: Path,
                                     source_root: Path, source_label: str):
        """Duplique un bloc en lui donnant un nouvel Id et/ou un nouveau Name, comme un
        element independant (pas une fusion) -- utile pour partir d'un bloc existant
        comme modele pour en creer un nouveau distinct (ex: variante d'un item).
        L'utilisateur choisit librement : nouvel Id, nouveau Name, les deux, ou
        abandonner l'Id pour n'identifier le nouveau bloc que par Name (certains blocs
        reels n'ont pas d'Id du tout, ex: '{ Block Name: LegacyForcefield ...}')."""
        from core.ecf.pending_conflicts import find_used_ids, suggest_free_ids

        rel = source_file_path.relative_to(source_root)
        dest_path = self.workspace.working_root / rel
        if not dest_path.exists():
            QMessageBox.warning(self, t("dup.file_missing_title"), t("dup.file_missing_msg", file=dest_path.name))
            return

        used_ids = find_used_ids([dest_path])
        suggestions = suggest_free_ids(used_ids, 5)

        dialog = DuplicateBlockDialog(block, suggestions, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        prior = capture_file(dest_path)
        annotation = None
        if settings.get_annotations_enabled():
            annotation = f"# Duplique par {settings.get_author()}"
        try:
            dest, status = duplicate_ecf_block_into_working(
                self.workspace, rel, block,
                dialog.result_new_id, dialog.result_new_name, dialog.result_remove_id,
                source_label, parent_chain=parent_chain, annotation=annotation)
            self.workspace.rescan_working()
        except Exception as e:
            QMessageBox.critical(self, t("err.title"), f"{t('dup.block_error')} :\n{e}")
            return

        if status == 'parent_not_found':
            QMessageBox.warning(self, t("dup.parent_not_found_title"),
                                 t("dup.parent_not_found_msg", file=dest.name))
            return

        if status == 'exists':
            QMessageBox.warning(self, t("dup.already_used_title"), t("dup.already_used_msg", file=dest.name))
            return

        self._push_workspace_undo(FileStateUndo(dest, prior, t("wsundo.duplicate_block", name=dest.name)))

        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(dest):
                self.tabs.removeTab(i)
                self.open_working_file_tab(dest)
                break

        details = []
        if dialog.result_new_id:
            details.append(f"Id={dialog.result_new_id}")
        if dialog.result_remove_id:
            details.append("Id abandonne")
        if dialog.result_new_name:
            details.append(f"Name={dialog.result_new_name}")
        self.statusBar().showMessage(t("status.block_duplicated", details=', '.join(details), file=dest.name))

    def _copy_block_into_working(self, block: EcfBlock, source_file_path: Path,
                                  source_root: Path, source_label: str):
        """Fusionne UN SEUL bloc (point 3 : mise a jour ciblee sans tout refusionner)."""
        rel = source_file_path.relative_to(source_root)
        dest_before = self.workspace.working_root / rel
        prior = capture_file(dest_before)
        try:
            dest, status, highlight = merge_block_into_working(self.workspace, rel, block, source_label)
            self.workspace.rescan_working()
        except Exception as e:
            QMessageBox.critical(self, t("err.title"), f"{t('copy.block_error')} :\n{e}")
            return

        self._push_workspace_undo(FileStateUndo(dest, prior, t("wsundo.copy_block", name=dest.name)))

        if highlight:
            self._highlights[dest] = highlight

        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(dest):
                self.tabs.removeTab(i)
                self.open_working_file_tab(dest)
                break

        if status == 'conflict':
            QMessageBox.warning(
                self, t("ecf.single_block_conflict_title"),
                t("ecf.single_block_conflict_msg")
            )
            self.statusBar().showMessage(t("status.id_conflict_detected", file=dest.name))
        elif status == 'added':
            self.statusBar().showMessage(t("status.block_added", file=dest.name))
        else:
            self.statusBar().showMessage(t("status.block_merged", file=dest.name))

    def _copy_csv_row_into_working(self, row: list, source_file_path: Path,
                                    source_root: Path, source_label: str):
        """Copie UNE SEULE ligne CSV (par cle) vers le fichier correspondant de la
        copie de travail, sans toucher au reste du fichier."""
        rel = source_file_path.relative_to(source_root)
        dest_before = self.workspace.working_root / rel
        prior = capture_file(dest_before)
        try:
            dest, status = merge_csv_row_into_working(self.workspace, rel, row)
            self.workspace.rescan_working()
        except Exception as e:
            QMessageBox.critical(self, t("err.title"), f"{t('copy.row_error')} :\n{e}")
            return

        self._push_workspace_undo(FileStateUndo(dest, prior, t("wsundo.copy_row", name=dest.name)))

        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(dest):
                self.tabs.removeTab(i)
                self.open_working_file_tab(dest)
                break

        key = row[0] if row else "?"
        if status == 'added':
            self.statusBar().showMessage(t("status.row_added", key=key, file=dest.name))
        elif status == 'merged':
            self.statusBar().showMessage(t("status.row_merged", key=key, file=dest.name))
        else:
            self.statusBar().showMessage(t("status.row_unchanged", key=key, file=dest.name))

    def _duplicate_csv_row_dialog(self, row: list, source_file_path: Path,
                                   source_root: Path, source_label: str):
        """Duplique une ligne CSV avec une NOUVELLE cle, comme un enregistrement
        independant (pas une fusion) -- utile pour partir d'une ligne existante comme
        modele pour en creer une nouvelle."""
        rel = source_file_path.relative_to(source_root)
        old_key = row[0] if row else "?"

        new_key, ok = QInputDialog.getText(
            self, t("csv.duplicate_title"),
            t("csv.duplicate_current_key", key=old_key)
        )
        if not ok:
            return
        if not new_key.strip():
            QMessageBox.warning(self, t("dup.key_required_title"), t("dup.key_required_msg"))
            return

        dest_before = self.workspace.working_root / rel
        prior = capture_file(dest_before)
        try:
            dest, status = duplicate_csv_row_into_working(self.workspace, rel, row, new_key.strip())
            self.workspace.rescan_working()
        except Exception as e:
            QMessageBox.critical(self, t("err.title"), f"{t('dup.row_error')} :\n{e}")
            return

        if status == 'key_exists':
            QMessageBox.warning(self, t("dup.key_exists_title"),
                                 t("dup.key_exists_msg", key=new_key.strip(), file=dest.name))
            return

        self._push_workspace_undo(FileStateUndo(dest, prior, t("wsundo.duplicate_row", name=dest.name)))

        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(dest):
                self.tabs.removeTab(i)
                self.open_working_file_tab(dest)
                break

        self.statusBar().showMessage(t("status.row_duplicated", key=new_key.strip(), file=dest.name))

    def _copy_yaml_entry_into_working(self, entry, key_path: list, source_file_path: Path,
                                       source_root: Path, source_label: str):
        rel = source_file_path.relative_to(source_root)
        dest_before = self.workspace.working_root / rel
        prior = capture_file(dest_before)
        try:
            dest, status = copy_yaml_entry_into_working(self.workspace, rel, entry, key_path)
            self.workspace.rescan_working()
        except Exception as e:
            QMessageBox.critical(self, t("err.title"), f"{t('copy.entry_error')} :\n{e}")
            return

        self._push_workspace_undo(FileStateUndo(dest, prior, t("wsundo.copy_entry", name=dest.name)))

        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(dest):
                self.tabs.removeTab(i)
                self.open_working_file_tab(dest)
                break

        if status == 'added_at_root':
            self.statusBar().showMessage(
                t("status.entry_copied_root", file=dest.name)
            )
        else:
            self.statusBar().showMessage(t("status.entry_copied", file=dest.name))

    def _duplicate_yaml_entry_dialog(self, entry, key_path: list, source_file_path: Path,
                                      source_root: Path, source_label: str):
        """Duplique une entree YAML avec une NOUVELLE cle/valeur, comme une entree
        independante -- utile pour partir d'une entree existante comme modele."""
        rel = source_file_path.relative_to(source_root)

        current = entry.value if (entry.key and entry.key.strip().lower() in ('name', 'id')) \
            else (entry.key or entry.value)

        new_value, ok = QInputDialog.getText(
            self, t("yaml.duplicate_title"),
            t("yaml.duplicate_current_value", value=current)
        )
        if not ok:
            return
        if not new_value.strip():
            QMessageBox.warning(self, t("dup.value_required_title"), t("dup.value_required_msg"))
            return

        dest_before = self.workspace.working_root / rel
        prior = capture_file(dest_before)
        annotation = None
        if settings.get_annotations_enabled():
            annotation = f"# Duplique par {settings.get_author()}"
        try:
            dest, status = duplicate_yaml_entry_into_working(
                self.workspace, rel, entry, key_path, new_value.strip(), annotation=annotation)
            self.workspace.rescan_working()
        except Exception as e:
            QMessageBox.critical(self, t("err.title"), f"{t('dup.entry_error')} :\n{e}")
            return

        if status == 'key_exists':
            QMessageBox.warning(self, t("dup.value_exists_title"),
                                 t("dup.value_exists_msg", value=new_value.strip(), file=dest.name))
            return

        self._push_workspace_undo(FileStateUndo(dest, prior, t("wsundo.duplicate_entry", name=dest.name)))

        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(dest):
                self.tabs.removeTab(i)
                self.open_working_file_tab(dest)
                break

        note = t("status.entry_duplicated_note") if status == 'added_at_root' else ""
        self.statusBar().showMessage(t("status.entry_duplicated", value=new_value.strip(), file=dest.name, note=note))

    def _translate_csv_cell_into_working(self, key: str, text: str, target_code: str, target_label: str,
                                          source_file_path: Path, source_root: Path, source_label: str):
        """Traduit une cellule d'une vue lecture seule (Scenario A/B) et applique le
        resultat directement dans la cellule correspondante (meme cle, colonne de la
        langue cible) de la copie de travail -- sans jamais ecraser une valeur deja
        presente."""
        from core import translation
        if not translation.is_available():
            QMessageBox.warning(self, t("trans.unavailable_title"), t("trans.unavailable_msg"))
            return
        try:
            translated = translation.translate_text(text, target=target_code)
        except Exception as e:
            QMessageBox.critical(self, t("trans.error_title"), t("trans.error_msg", error=e))
            return

        rel = source_file_path.relative_to(source_root)
        dest_before = self.workspace.working_root / rel
        prior = capture_file(dest_before)
        try:
            dest, status = translate_csv_cell_into_working(
                self.workspace, rel, key, target_code, target_label, translated)
            self.workspace.rescan_working()
        except Exception as e:
            QMessageBox.critical(self, t("err.title"), f"{t('trans.apply_error')} :\n{e}")
            return

        self._push_workspace_undo(FileStateUndo(dest, prior, t("wsundo.translate_cell", name=dest.name)))

        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(dest):
                self.tabs.removeTab(i)
                self.open_working_file_tab(dest)
                break

        if status == 'added':
            self.statusBar().showMessage(t("status.row_translated", key=key, lang=target_label, file=dest.name))
        elif status == 'merged':
            self.statusBar().showMessage(t("status.cell_translated", lang=target_label, key=key, file=dest.name))
        else:
            self.statusBar().showMessage(
                t("status.cell_already_has_value", key=key, lang=target_label)
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
        pour les .ecf pour l'instant -- les autres formats s'ouvrent seuls)."""
        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(path):
                self.tabs.setCurrentIndex(i)
                return

        ext = path.suffix.lower()

        simple_editors = {
            '.csv': CsvEditWidget,
            '.yaml': YamlEditWidget,
            '.yml': YamlEditWidget,
            '.txt': TxtEditWidget,
        }
        if ext in simple_editors:
            try:
                widget = simple_editors[ext](path)
            except Exception as e:
                QMessageBox.critical(self, t("err.read_title"), f"{t('open.error', file=path.name)} :\n{e}")
                return
            index = self.tabs.addTab(widget, "✎ " + path.name)
            self.tabs.setTabToolTip(index, str(path))
            self.tabs.setCurrentIndex(index)
            widget.modified_changed.connect(lambda modified, w=widget: self._update_tab_title(w, modified))
            widget.saved.connect(lambda w=widget: self.statusBar().showMessage(t("status.saved", path=w.path)))
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

        def _duplicate_block_cb(block, parent_chain, source_path, source_root, source_label):
            self._duplicate_ecf_block_dialog(block, parent_chain, source_path, source_root, source_label)

        try:
            widget = CompareWidget(path, compare_sources, EcfViewWidget,
                                    copy_block_callback=_copy_block_cb if settings.get_merge_enabled() else None,
                                    duplicate_block_callback=_duplicate_block_cb)
        except Exception as e:
            QMessageBox.critical(self, t("err.read_title"), f"{t('open.error', file=path.name)} :\n{e}")
            return

        index = self.tabs.addTab(widget, "✎ " + path.name)
        self.tabs.setTabToolTip(index, str(path))
        self.tabs.setCurrentIndex(index)

        widget.modified_changed.connect(lambda modified, w=widget: self._update_tab_title(w, modified))
        widget.saved.connect(lambda w=widget: self.statusBar().showMessage(t("status.saved", path=w.edit_widget.path)))

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
                on_duplicate_block = None
                if read_only and source_root and source_label:
                    if settings.get_merge_enabled():
                        on_copy_block = lambda block: self._copy_block_into_working(
                            block, path, source_root, source_label)
                    on_duplicate_block = lambda block, parent_chain: self._duplicate_ecf_block_dialog(
                        block, parent_chain, path, source_root, source_label)
                widget = EcfViewWidget(path, highlight=highlight, on_copy_block=on_copy_block,
                                        copy_label=source_label, on_duplicate_block=on_duplicate_block)
            elif ext in ('.yaml', '.yml'):
                on_copy_entry = None
                on_duplicate_entry = None
                if read_only and source_root and source_label:
                    if settings.get_merge_enabled():
                        on_copy_entry = lambda entry, key_path: self._copy_yaml_entry_into_working(
                            entry, key_path, path, source_root, source_label)
                    on_duplicate_entry = lambda entry, key_path: self._duplicate_yaml_entry_dialog(
                        entry, key_path, path, source_root, source_label)
                widget = YamlEditWidget(path, editable=False, on_copy_entry=on_copy_entry,
                                        on_duplicate_entry=on_duplicate_entry)
            elif ext == '.txt':
                widget = TxtEditWidget(path, editable=False)
            elif ext == '.csv':
                on_copy_row = None
                on_translate_cell = None
                on_duplicate_row = None
                if read_only and source_root and source_label:
                    if settings.get_merge_enabled():
                        on_copy_row = lambda row: self._copy_csv_row_into_working(
                            row, path, source_root, source_label)
                    on_translate_cell = lambda key, text, code, label: self._translate_csv_cell_into_working(
                        key, text, code, label, path, source_root, source_label)
                    on_duplicate_row = lambda row: self._duplicate_csv_row_dialog(
                        row, path, source_root, source_label)
                widget = CsvEditWidget(path, editable=False, on_copy_row=on_copy_row,
                                        copy_label=source_label, on_translate_cell=on_translate_cell,
                                        on_duplicate_row=on_duplicate_row)
            else:
                QMessageBox.information(self, t("open.not_supported_title"), t("open.not_supported_msg", ext=ext))
                return
        except Exception as e:
            QMessageBox.critical(self, t("err.read_title"), f"{t('open.error', file=path.name)} :\n{e}")
            return

        prefix = "🔒 " if read_only else "✎ "
        index = self.tabs.addTab(widget, prefix + path.name)
        self.tabs.setTabToolTip(index, str(path))
        self.tabs.setCurrentIndex(index)


class DuplicateBlockDialog(QDialog):
    """Fenetre de duplication d'un bloc ECF : les deux champs (Id, Name) sont visibles
    en meme temps, avec une case a cocher pour abandonner completement l'Id (certains
    blocs reels n'ont pas d'Id du tout, identifies seulement par Name)."""

    def __init__(self, block: EcfBlock, suggestions: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("dup.title"))
        self.setMinimumWidth(450)

        current_id = block.get('Id')
        current_name = block.get_property('Name')

        layout = QVBoxLayout(self)
        none_placeholder = t("dup.none_placeholder")
        layout.addWidget(QLabel(
            t("dup.current_block", id=current_id or none_placeholder, name=current_name or none_placeholder) +
            "\n\n" + t("dup.instructions")
        ))

        id_row = QHBoxLayout()
        id_row.addWidget(QLabel(t("dup.new_id")))
        self.id_edit = QLineEdit(str(suggestions[0]) if current_id and suggestions else "")
        id_row.addWidget(self.id_edit)
        layout.addLayout(id_row)
        if suggestions:
            sugg_label = QLabel(t("dup.suggestions_label", ids=', '.join(str(s) for s in suggestions)))
            sugg_label.setStyleSheet("color: gray; font-size: 11px;")
            layout.addWidget(sugg_label)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel(t("dup.new_name")))
        self.name_edit = QLineEdit(current_name or "")
        name_row.addWidget(self.name_edit)
        layout.addLayout(name_row)

        self.remove_id_checkbox = None
        if current_id:
            self.remove_id_checkbox = QCheckBox(t("dup.remove_id"))
            layout.addWidget(self.remove_id_checkbox)

        buttons = QHBoxLayout()
        btn_ok = QPushButton(t("dup.duplicate"))
        btn_ok.clicked.connect(self._on_accept)
        buttons.addWidget(btn_ok)
        btn_cancel = QPushButton(t("btn.cancel"))
        btn_cancel.setObjectName("secondaryButton")
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_cancel)
        layout.addLayout(buttons)

        self._current_id = current_id
        self._current_name = current_name

    def _on_accept(self):
        new_id = self.id_edit.text().strip() or None
        new_name = self.name_edit.text().strip() or None
        remove_id = self.remove_id_checkbox.isChecked() if self.remove_id_checkbox else False

        if remove_id and not new_name:
            QMessageBox.warning(self, t("dup.name_required"), t("dup.name_required_msg"))
            return

        id_changed = new_id is not None and new_id != self._current_id
        name_changed = new_name is not None and new_name != self._current_name
        if not remove_id and not id_changed and not name_changed:
            QMessageBox.warning(self, t("dup.no_change"), t("dup.no_change_msg"))
            return

        self.result_new_id = new_id
        self.result_new_name = new_name
        self.result_remove_id = remove_id
        self.accept()


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

        # -- Barre de recherche : indispensable des que le fichier a beaucoup de blocs
        # (certains ECF reels en ont plus de 5000 au niveau racine, impossible a
        # reperer en faisant defiler manuellement une liste non triee) --
        search_row = QHBoxLayout()
        search_row.setSpacing(4)
        search_row.addWidget(QLabel(t("label.search")))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Id / Name...")
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
    from gui.theme import apply_theme
    apply_theme(app)
    window = MainWindow()
    window.show()

    # Propose de reprendre un projet recent des le lancement, s'il y en a
    from PyQt6.QtCore import QTimer
    QTimer.singleShot(0, lambda: window.show_startup_dialog(auto_at_launch=True))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
