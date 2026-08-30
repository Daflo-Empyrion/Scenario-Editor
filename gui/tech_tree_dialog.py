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
Fenetre de l'arbre technologique -- un onglet par categorie (voir
gui/tech_tree_widget.py pour la vue de chaque onglet), avec un curseur de
niveau joueur SIMULE (jamais lu ni ecrit dans un fichier -- aucune propriete
de ce type n'existe dans le scenario, uniquement pour previsualiser les
verrous) et un panneau d'information sur le noeud selectionne.

Toute ecriture (niveau, cout, categorie) passe par core/tech_tree.py, qui
reecrit directement BlocksConfig.ecf/ItemsConfig.ecf sur disque -- comme les
autres operations d'ecriture directe de l'application (fusion, duplication),
elle est enregistree dans la pile d'annulation GLOBALE de l'espace de travail
(voir core/workspace_undo.py) via le callback `push_undo`.
"""
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel, QMessageBox,
    QWidget, QPushButton,
)

from core.i18n import t
from core.ecf.block_creation import find_file_by_name
from core.tech_tree import load_tech_tree, set_unlock_level, set_unlock_cost, move_to_category, set_tech_tree_parent
from core.tech_tree_icons import build_icon_index
from core.workspace import Workspace
from core.workspace_undo import FileStateUndo, capture_file
from gui.tech_tree_widget import TechTreeCategoryView


class TechTreeDialog(QDialog):
    def __init__(self, workspace: Workspace, parent=None,
                 push_undo: Optional[Callable] = None,
                 is_path_modified: Optional[Callable[[Path], bool]] = None,
                 reload_path: Optional[Callable[[Path], None]] = None):
        super().__init__(parent)
        self.workspace = workspace
        self._push_undo = push_undo
        self._is_path_modified = is_path_modified or (lambda p: False)
        # Rappelee apres CHAQUE ecriture reussie -- recharge l'onglet ouvert
        # (s'il existe et n'a pas de modification en attente) pour que
        # l'utilisateur voie la valeur changer EN DIRECT dans le fichier
        # ouvert de la copie de travail -- demande explicite de
        # l'utilisateur (session du 29/08/2026).
        self._reload_path = reload_path or (lambda p: None)
        self._active_pick_view = None

        ecf_files = [f.path for f in workspace.working.configuration if f.extension == '.ecf']
        self.blocks_path = find_file_by_name(ecf_files, "BlocksConfig.ecf")
        self.items_path = find_file_by_name(ecf_files, "ItemsConfig.ecf")

        self.setWindowTitle(t("techtree.dialog_title"))
        self.setMinimumSize(1000, 700)
        # QDialog n'affiche par defaut que le bouton fermer sur certains
        # environnements (signale par l'utilisateur, capture du 29/08/2026) --
        # fenetre assez grande pour meriter agrandir/reduire comme une
        # fenetre normale.
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinMaxButtonsHint)

        self.tech_tree = load_tech_tree(self.blocks_path, self.items_path)
        icon_index = build_icon_index(workspace.working_root)

        layout = QVBoxLayout(self)

        top_row = QHBoxLayout()
        top_row.addStretch()
        self.selected_info_label = QLabel(t("techtree.no_selection"))
        top_row.addWidget(self.selected_info_label)
        layout.addLayout(top_row)

        # Bandeau affiche pendant le choix du nouveau parent (voir
        # TechTreeCategoryView.start_parent_pick) -- cache par defaut.
        self.parent_pick_banner = QWidget()
        banner_layout = QHBoxLayout(self.parent_pick_banner)
        banner_layout.setContentsMargins(0, 0, 0, 0)
        self.parent_pick_label = QLabel("")
        self.parent_pick_label.setStyleSheet(
            "background: #eef1f6; border: 1px solid #d0d7e5; border-radius: 6px; padding: 6px;")
        banner_layout.addWidget(self.parent_pick_label, 1)
        btn_no_parent = QPushButton(t("techtree.no_parent_button"))
        btn_no_parent.clicked.connect(self._on_no_parent_clicked)
        banner_layout.addWidget(btn_no_parent)
        btn_cancel_pick = QPushButton(t("btn.cancel"))
        btn_cancel_pick.setObjectName("secondaryButton")
        btn_cancel_pick.clicked.connect(self._on_cancel_parent_pick_clicked)
        banner_layout.addWidget(btn_cancel_pick)
        self.parent_pick_banner.setVisible(False)
        layout.addWidget(self.parent_pick_banner)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        categories = self.tech_tree.categories()
        self._views = {}
        for category in categories:
            view = TechTreeCategoryView(self.tech_tree, category, icon_index, categories)
            view.node_selected.connect(self._on_node_selected)
            view.level_changed.connect(self._on_level_changed)
            view.cost_changed.connect(self._on_cost_changed)
            view.category_changed.connect(self._on_category_changed)
            view.parent_changed.connect(self._on_parent_changed)
            view.parent_pick_started.connect(self._on_parent_pick_started)
            view.parent_pick_finished.connect(self._on_parent_pick_finished)
            self._views[category] = view
            self.tabs.addTab(view, category)

    # -- selection ----------------------------------------------------------

    def _on_node_selected(self, node_name: str) -> None:
        node = self.tech_tree.get(node_name)
        if node is None:
            return
        self.selected_info_label.setText(
            t("techtree.selected_info", name=node.name, level=node.unlock_level, cost=node.unlock_cost))

    # -- simulation niveau joueur --------------------------------------------

    # -- ecriture disque ------------------------------------------------------

    def _path_for_node(self, node_name: str) -> Optional[Path]:
        node = self.tech_tree.get(node_name)
        if node is None:
            return None
        return self.blocks_path if node.source == 'block' else self.items_path

    def _guard_file_writable(self, path: Path) -> bool:
        """Refuse d'ecrire UNIQUEMENT si ce fichier est ouvert dans un onglet
        AVEC des modifications non enregistrees -- si ouvert mais SANS
        modification, l'ecriture est autorisee et l'onglet est recharge
        automatiquement ensuite (voir _reload_path) pour rester synchronise."""
        if self._is_path_modified(path):
            QMessageBox.warning(self, t("techtree.file_locked_title"),
                                 t("techtree.file_locked_msg", name=path.name))
            return False
        return True

    def _on_level_changed(self, node_name: str, new_level: int) -> None:
        path = self._path_for_node(node_name)
        if path is None or not self._guard_file_writable(path):
            self._rebuild_all()
            return
        prior = capture_file(path)
        if not set_unlock_level(path, node_name, new_level):
            QMessageBox.critical(self, t("err.title"), t("techtree.write_error", name=node_name))
            self._rebuild_all()
            return
        node = self.tech_tree.get(node_name)
        node.unlock_level = new_level
        if self._push_undo:
            self._push_undo(FileStateUndo(path, prior, t("wsundo.techtree_level", name=node_name)))
        self._reload_path(path)
        if node_name in self.selected_info_label.text():
            self._on_node_selected(node_name)

    def _on_cost_changed(self, node_name: str, new_cost: int) -> None:
        path = self._path_for_node(node_name)
        if path is None or not self._guard_file_writable(path):
            return
        prior = capture_file(path)
        if not set_unlock_cost(path, node_name, new_cost):
            QMessageBox.critical(self, t("err.title"), t("techtree.write_error", name=node_name))
            return
        node = self.tech_tree.get(node_name)
        node.unlock_cost = new_cost
        if self._push_undo:
            self._push_undo(FileStateUndo(path, prior, t("wsundo.techtree_cost", name=node_name)))
        self._reload_path(path)
        self._on_node_selected(node_name)

    def _on_category_changed(self, node_name: str, new_category: str) -> None:
        path = self._path_for_node(node_name)
        if path is None or not self._guard_file_writable(path):
            return
        node = self.tech_tree.get(node_name)
        old_categories = list(node.categories)
        prior = capture_file(path)
        if not move_to_category(path, node_name, new_category):
            QMessageBox.critical(self, t("err.title"), t("techtree.write_error", name=node_name))
            return
        node.categories = [new_category]
        if self._push_undo:
            self._push_undo(FileStateUndo(
                path, prior, t("wsundo.techtree_category", name=node_name, category=new_category)))
        self._reload_path(path)
        # Le noeud change d'onglet : reconstruit les deux vues affectees
        # (celle qu'il quitte ET celle qu'il rejoint).
        for cat in set(old_categories) | {new_category}:
            view = self._views.get(cat)
            if view is not None:
                view.rebuild()

    def _rebuild_all(self) -> None:
        for view in self._views.values():
            view.rebuild()

    # -- choix du nouveau parent (glisser vertical, demande explicite du -----
    # -- 29/08/2026) ----------------------------------------------------------

    def _on_parent_pick_started(self, node_name: str) -> None:
        self._active_pick_view = self.sender()
        self.parent_pick_label.setText(t("techtree.parent_pick_instructions", name=node_name))
        self.parent_pick_banner.setVisible(True)

    def _on_parent_pick_finished(self) -> None:
        self._active_pick_view = None
        self.parent_pick_banner.setVisible(False)

    def _on_no_parent_clicked(self) -> None:
        if self._active_pick_view is not None:
            self._active_pick_view.set_no_parent_for_pending_pick()

    def _on_cancel_parent_pick_clicked(self) -> None:
        if self._active_pick_view is not None:
            self._active_pick_view.cancel_parent_pick()

    def _on_parent_changed(self, node_name: str, new_parent: str) -> None:
        """new_parent == "" signifie 'aucun parent' (racine) -- voir
        TechTreeCategoryView.parent_changed."""
        path = self._path_for_node(node_name)
        if path is None or not self._guard_file_writable(path):
            self._rebuild_all()
            return
        actual_new_parent = new_parent or None
        prior = capture_file(path)
        if not set_tech_tree_parent(path, node_name, actual_new_parent):
            QMessageBox.critical(self, t("err.title"), t("techtree.write_error", name=node_name))
            self._rebuild_all()
            return
        node = self.tech_tree.get(node_name)
        node.parent_name = actual_new_parent
        if self._push_undo:
            label_key = "wsundo.techtree_parent_removed" if actual_new_parent is None else "wsundo.techtree_parent_set"
            self._push_undo(FileStateUndo(
                path, prior, t(label_key, name=node_name, parent=actual_new_parent or "")))
        self._reload_path(path)
        # Le lien parent-enfant a change : la disposition en voies de TOUTE
        # categorie affichant ce noeud doit etre recalculee (voir
        # core.tech_tree_layout.compute_node_positions).
        for view in self._views.values():
            if view.category in node.categories:
                view.rebuild()
