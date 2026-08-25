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
Conteneur ouvert pour Dialogues.ecf -- combine le navigateur de dialogues
(gui/dialogue_browser_widget.py, nouveau, lecture seule) et l'edition ECF
classique deja construite par open_working_file_tab() (CompareWidget avec
comparaison A/B et fusion, ou EcfEditWidget seul si aucune source) --
injectee plutot que reconstruite ici, pour ne jamais dupliquer cette
logique.

IMPORTANT -- self.edit_widget pointe directement vers l'EcfEditWidget le
PLUS INTERNE (aplati, pas le CompareWidget) : le motif
getattr(widget, 'edit_widget', widget) est utilise partout ailleurs dans
l'application (titre d'onglet, navigation de recherche globale, sauvegarde
automatique) en supposant UN SEUL niveau d'imbrication -- exposer ici le
CompareWidget aurait casse ce motif partout (deux niveaux d'imbrication)."""
from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget

from core.i18n import t
from gui.dialogue_browser_widget import DialogueBrowserWidget


class DialogueEditWidget(QWidget):
    modified_changed = pyqtSignal(bool)
    saved = pyqtSignal()

    def __init__(self, path: Path, ecf_widget, parent=None):
        super().__init__(parent)
        self.path = path
        # Aplati -- voir avertissement de tete de module.
        self.edit_widget = getattr(ecf_widget, "edit_widget", ecf_widget)
        self.sibling_ecf_files = getattr(self.edit_widget, "sibling_ecf_files", None)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        self.browser_widget = DialogueBrowserWidget(self.edit_widget.doc)
        self.tab_widget.addTab(self.browser_widget, t("playfield.tab_dialogue_browser"))
        self.tab_widget.addTab(ecf_widget, t("dialogue_edit.tab_edit"))

        ecf_widget.modified_changed.connect(self.modified_changed.emit)
        ecf_widget.saved.connect(self.saved.emit)
        # Le navigateur doit refleter les modifications faites depuis l'onglet
        # Edition ECF -- re-parcourt le MEME document en memoire (pas de
        # reparse disque) des qu'on revient sur l'onglet navigateur, ou juste
        # apres un enregistrement reussi.
        ecf_widget.saved.connect(self.browser_widget.refresh)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, index: int):
        if self.tab_widget.widget(index) is self.browser_widget:
            self.browser_widget.refresh()

    def save(self):
        self.edit_widget.save()

    def is_modified(self) -> bool:
        return self.edit_widget.is_modified()

    def _get_content_for_autosave(self) -> str:
        return self.edit_widget._get_content_for_autosave()

    def undo(self):
        if hasattr(self.edit_widget, "undo"):
            self.edit_widget.undo()
            self.browser_widget.refresh()
