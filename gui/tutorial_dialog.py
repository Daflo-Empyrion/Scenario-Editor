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
Fenetre des tutoriels -- extraite de gui/main_window.py (fichier historiquement
tres volumineux) pour reduire sa taille. Comportement inchange, voir
TutorialDialog ci-dessous."""
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QDialog, QCheckBox,
    QListWidget, QListWidgetItem, QTextBrowser, QPushButton,
)

from core.i18n import t


class TutorialDialog(QDialog):
    """Fenetre des tutoriels : liste a gauche (lue dynamiquement depuis
    core/tutorials.py -- aucune modification necessaire ici pour ajouter un nouveau
    tutoriel), navigation pas a pas a droite (titre d'etape, contenu, Precedent/
    Suivant, compteur).

    Peut s'ouvrir automatiquement au demarrage (auto_opened=True, voir main()) :
    dans ce cas, un bandeau rappelle ou retrouver ce tutoriel plus tard (chemin de
    menu exact), avec une case a cocher pour ne plus l'ouvrir automatiquement aux
    prochains lancements -- jamais affiche quand ouvert manuellement depuis le
    menu Aide, ou l'utilisateur sait deja qu'il vient de choisir de le voir."""

    def __init__(self, parent=None, auto_opened: bool = False):
        super().__init__(parent)
        from core.tutorials import TUTORIALS
        from core import i18n, settings as _settings
        self.tutorials = TUTORIALS
        self.current_tutorial = None
        self.current_step_index = 0
        self._lang = i18n.get_language()

        self.setWindowTitle(t("tutorials.dialog_title"))
        self.resize(800, 620 if auto_opened else 550)

        outer = QVBoxLayout(self)

        if auto_opened:
            banner = QLabel(t("tutorials.auto_open_banner"))
            banner.setWordWrap(True)
            banner.setStyleSheet(
                "background: #eef1f6; border: 1px solid #d0d7e5; border-radius: 6px; padding: 8px;")
            outer.addWidget(banner)
            self.checkbox_dont_show = QCheckBox(t("tutorials.dont_show_again"))
            self.checkbox_dont_show.toggled.connect(
                lambda checked: _settings.set_auto_open_tutorial(not checked))
            outer.addWidget(self.checkbox_dont_show)

        layout = QHBoxLayout()
        outer.addLayout(layout, 1)

        left_col = QVBoxLayout()
        left_col.addWidget(QLabel(t("tutorials.list_title")))
        self.list_widget = QListWidget()
        self.list_widget.setMaximumWidth(220)
        for tut in self.tutorials:
            item = QListWidgetItem(tut.title(self._lang))
            item.setToolTip(tut.summary(self._lang))
            self.list_widget.addItem(item)
        self.list_widget.currentRowChanged.connect(self._on_tutorial_selected)
        left_col.addWidget(self.list_widget, 1)
        layout.addLayout(left_col)

        right_col = QVBoxLayout()
        self.step_counter_label = QLabel("")
        self.step_counter_label.setStyleSheet("color: gray; font-size: 11px;")
        right_col.addWidget(self.step_counter_label)

        self.step_title_label = QLabel("")
        title_font = self.step_title_label.font()
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 2)
        self.step_title_label.setFont(title_font)
        right_col.addWidget(self.step_title_label)

        self.content_browser = QTextBrowser()
        self.content_browser.setOpenExternalLinks(True)
        self.content_browser.setHtml(t("tutorials.select_prompt"))
        right_col.addWidget(self.content_browser, 1)

        nav_row = QHBoxLayout()
        self.btn_previous = QPushButton(t("tutorials.btn_previous"))
        self.btn_previous.setObjectName("secondaryButton")
        self.btn_previous.clicked.connect(self._go_previous)
        self.btn_previous.setEnabled(False)
        nav_row.addWidget(self.btn_previous)
        nav_row.addStretch()
        self.btn_next = QPushButton(t("tutorials.btn_next"))
        self.btn_next.clicked.connect(self._go_next)
        self.btn_next.setEnabled(False)
        nav_row.addWidget(self.btn_next)
        right_col.addLayout(nav_row)

        layout.addLayout(right_col, 1)

        if self.tutorials:
            self.list_widget.setCurrentRow(0)

    def _on_tutorial_selected(self, row: int):
        if row < 0 or row >= len(self.tutorials):
            return
        self.current_tutorial = self.tutorials[row]
        self.current_step_index = 0
        self._refresh_step()

    def _refresh_step(self):
        if not self.current_tutorial or not self.current_tutorial.steps:
            return
        steps = self.current_tutorial.steps
        step = steps[self.current_step_index]
        self.step_counter_label.setText(
            t("tutorials.step_counter", current=self.current_step_index + 1, total=len(steps)))
        self.step_title_label.setText(step.title(self._lang))
        self.content_browser.setHtml(step.content_html(self._lang))
        self.btn_previous.setEnabled(self.current_step_index > 0)
        self.btn_next.setEnabled(self.current_step_index < len(steps) - 1)

    def _go_previous(self):
        if self.current_step_index > 0:
            self.current_step_index -= 1
            self._refresh_step()

    def _go_next(self):
        if self.current_tutorial and self.current_step_index < len(self.current_tutorial.steps) - 1:
            self.current_step_index += 1
            self._refresh_step()
