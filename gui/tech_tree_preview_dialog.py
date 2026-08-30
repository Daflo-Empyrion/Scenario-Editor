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
Previsualisation de la position dans l'arbre technologique d'un bloc/item PAS
ENCORE cree (ou en cours de duplication) -- ouverte depuis
gui/add_block_dialog.py (creation) et gui/duplicate_variants_dialog.py
(duplication), voir ces modules pour les points d'entree.

N'ecrit RIEN sur disque : construit une copie INDEPENDANTE de l'arbre reel
(rechargee depuis les memes fichiers), y ajoute un noeud synthetique
representant le bloc/item en attente, et laisse l'utilisateur le deplacer
(seul noeud editable, voir TechTreeCategoryView.editable_node_name) parmi les
noeuds reels affiches en repere. Retourne (niveau, cout, categorie, parent)
choisis a la fermeture -- c'est l'appelant qui ecrit ensuite ces valeurs dans
les proprietes du NOUVEAU bloc lors de sa creation reelle, pas ce dialogue.
"""
from pathlib import Path
from typing import List, Optional, Tuple

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel, QPushButton

from core.i18n import t
from core.tech_tree import load_tech_tree, TechTreeNode, KNOWN_CATEGORY_ORDER
from core.tech_tree_icons import build_icon_index
from gui.tech_tree_widget import TechTreeCategoryView

_PENDING_NODE_NAME = "\x00__pending_preview__"  # improbable en pratique comme vrai Name ECF


class TechTreePreviewDialog(QDialog):
    def __init__(self, blocks_path: Optional[Path], items_path: Optional[Path],
                 working_root: Optional[Path], source: str,
                 initial_level: int = 1, initial_cost: int = 0,
                 initial_categories: Optional[List[str]] = None,
                 initial_parent: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("techtree.preview_title"))
        self.setMinimumSize(1000, 700)

        self.tech_tree = load_tech_tree(blocks_path, items_path)
        # Contrairement au dialogue reel (gui/tech_tree_dialog.py), qui
        # n'affiche que les categories ayant deja au moins un noeud reel, la
        # previsualisation propose TOUJOURS toutes les categories canoniques
        # connues -- un nouveau bloc/item doit pouvoir viser une categorie
        # meme si elle est vide dans les fichiers actuels (bug reel trouve
        # par test_result_values_reflects_all_changes : la categorie
        # 'Tools' n'existe dans aucun vrai noeud d'une petite fixture de
        # test, mais doit rester une destination valide).
        found_categories = self.tech_tree.categories()
        categories = list(KNOWN_CATEGORY_ORDER)
        for c in found_categories:
            if c not in categories:
                categories.append(c)
        start_category = None
        for c in (initial_categories or []):
            if c in categories:
                start_category = c
                break
        if start_category is None and categories:
            start_category = categories[0]

        self.pending_node = TechTreeNode(
            name=_PENDING_NODE_NAME, source=source, unlock_level=initial_level, unlock_cost=initial_cost,
            categories=[start_category] if start_category else [], parent_name=initial_parent,
            icon_key="",  # jamais trouve dans l'index -> icone generique, coherent (pas encore cree)
        )
        self.tech_tree.nodes.append(self.pending_node)
        self.tech_tree._by_name[self.pending_node.name] = self.pending_node

        icon_index = build_icon_index(working_root) if working_root else {}

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(t("techtree.preview_instructions")))

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        self._views = {}
        for category in categories:
            view = TechTreeCategoryView(
                self.tech_tree, category, icon_index, categories,
                editable_node_name=_PENDING_NODE_NAME, highlight_node_name=_PENDING_NODE_NAME)
            view.level_changed.connect(self._on_level_changed)
            view.cost_changed.connect(self._on_cost_changed)
            view.category_changed.connect(self._on_category_changed)
            self._views[category] = view
            self.tabs.addTab(view, category)

        if start_category and start_category in self._views:
            self.tabs.setCurrentWidget(self._views[start_category])

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_ok = QPushButton(t("btn.ok"))
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_ok)
        btn_cancel = QPushButton(t("btn.cancel"))
        btn_cancel.setObjectName("secondaryButton")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

    # -- callbacks locaux (aucune ecriture disque) ---------------------------

    def _on_level_changed(self, node_name: str, new_level: int) -> None:
        if node_name == _PENDING_NODE_NAME:
            self.pending_node.unlock_level = new_level

    def _on_cost_changed(self, node_name: str, new_cost: int) -> None:
        if node_name == _PENDING_NODE_NAME:
            self.pending_node.unlock_cost = new_cost

    def _on_category_changed(self, node_name: str, new_category: str) -> None:
        if node_name != _PENDING_NODE_NAME:
            return
        old_categories = list(self.pending_node.categories)
        self.pending_node.categories = [new_category]
        for cat in set(old_categories) | {new_category}:
            view = self._views.get(cat)
            if view is not None:
                view.rebuild()
        self.tabs.setCurrentWidget(self._views[new_category])

    # -- resultat -------------------------------------------------------------

    def result_values(self) -> Tuple[int, int, List[str], Optional[str]]:
        """(niveau, cout, categories, parent) choisis -- a n'appeler qu'apres
        exec() == Accepted."""
        return (self.pending_node.unlock_level, self.pending_node.unlock_cost,
                list(self.pending_node.categories), self.pending_node.parent_name)
