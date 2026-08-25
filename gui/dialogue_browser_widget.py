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
Navigateur de dialogues -- vue structuree et navigable de Dialogues.ecf,
complementaire (pas remplacante) a l'edition ECF generique classique
(l'onglet "Edition ECF" reste toujours disponible pour modifier le
fichier -- voir gui/dialogue_edit_widget.py). Lecture seule : montre la
structure d'un dialogue (Output, Options, Next/NextIf, Variables, Execute)
de facon lisible, avec navigation en un clic vers les dialogues cibles et la
liste des dialogues qui menent vers celui affiche -- voir
core/dialogue_browser.py pour l'extraction.

Reutilise les memes sentinelles (End, GotoAndReset, Return) que la
verification croisee -- jamais traitees comme des cibles de navigation."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QSplitter, QScrollArea, QGroupBox, QPushButton,
)

from core.i18n import t
from core.dialogue_browser import build_dialogue_index, build_incoming_links_index
from core.ecf.cross_reference_check import _DIALOGUE_REF_SENTINELS


class _ClickableLabel(QLabel):
    """Un label qui se comporte comme un lien -- clique pour naviguer vers un
    autre dialogue. Grise et non cliquable pour les sentinelles (End...) ou
    les cibles qui n'existent pas dans ce fichier (lien casse -- signale en
    rouge, la verification croisee existante reste la source de verite pour
    une liste exhaustive de ces cas)."""

    def __init__(self, target_name: str, on_click, exists: bool, parent=None):
        display = target_name
        if target_name in _DIALOGUE_REF_SENTINELS:
            super().__init__(f"<i>{display}</i>", parent)
            self.setStyleSheet("color: #888888;")
        elif not exists:
            super().__init__(f"<span style='color:#c62828'>{display} ⚠</span>", parent)
        else:
            super().__init__(f"<a href='#'>{display}</a>", parent)
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.linkActivated.connect(lambda _: on_click(target_name))


class DialogueBrowserWidget(QWidget):
    def __init__(self, doc, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.dialogue_index = {}
        self.incoming_index = {}
        self._current_name = None

        layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(t("dialogue_browser.search_placeholder"))
        self.search_edit.textChanged.connect(self._filter_list)
        left_layout.addWidget(self.search_edit)
        self.name_list = QListWidget()
        self.name_list.currentTextChanged.connect(self._on_name_selected)
        left_layout.addWidget(self.name_list, 1)
        btn_refresh = QPushButton(t("results_window.btn_refresh"))
        btn_refresh.setObjectName("secondaryButton")
        btn_refresh.clicked.connect(self.refresh)
        left_layout.addWidget(btn_refresh)
        splitter.addWidget(left)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        self.detail_widget = QWidget()
        self.detail_layout = QVBoxLayout(self.detail_widget)
        self.detail_layout.addStretch()
        right_scroll.setWidget(self.detail_widget)
        splitter.addWidget(right_scroll)
        splitter.setSizes([280, 700])

        self.refresh()

    def refresh(self):
        current = self._current_name
        self.dialogue_index = build_dialogue_index(self.doc)
        self.incoming_index = build_incoming_links_index(self.dialogue_index)
        self.name_list.clear()
        for name in sorted(self.dialogue_index.keys()):
            self.name_list.addItem(QListWidgetItem(name))
        if current and current in self.dialogue_index:
            self._select_name(current)

    def _filter_list(self, text: str):
        text_lower = text.strip().lower()
        for i in range(self.name_list.count()):
            item = self.name_list.item(i)
            item.setHidden(text_lower not in item.text().lower())

    def _select_name(self, name: str):
        items = self.name_list.findItems(name, Qt.MatchFlag.MatchExactly)
        if items:
            self.name_list.setCurrentItem(items[0])

    def _on_name_selected(self, name: str):
        if not name or name not in self.dialogue_index:
            return
        self._current_name = name
        self._render_detail(name)

    def _clear_detail(self):
        while self.detail_layout.count() > 1:
            item = self.detail_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _navigate(self, name: str):
        if name in self.dialogue_index:
            self.search_edit.clear()
            self._select_name(name)

    def _add_row(self, label_text: str, value_text: str):
        row = QLabel(f"<b>{label_text} :</b> {value_text}")
        row.setWordWrap(True)
        self.detail_layout.insertWidget(self.detail_layout.count() - 1, row)

    def _add_widget(self, widget):
        self.detail_layout.insertWidget(self.detail_layout.count() - 1, widget)

    def _render_detail(self, name: str):
        self._clear_detail()
        info = self.dialogue_index[name]

        title = QLabel(f"<h2>{info.name}</h2>")
        self._add_widget(title)

        if info.npc_name:
            self._add_row(t("dialogue_browser.npc_name"), info.npc_name)
        if info.output:
            self._add_row(t("dialogue_browser.output"), info.output)

        if info.variables:
            box = QGroupBox(t("dialogue_browser.variables"))
            box_layout = QVBoxLayout(box)
            for v in info.variables:
                box_layout.addWidget(QLabel(f"{v.name} : {v.var_type}"))
            self._add_widget(box)

        if info.executes:
            box = QGroupBox(t("dialogue_browser.executes"))
            box_layout = QVBoxLayout(box)
            for e in info.executes:
                lbl = QLabel(e)
                lbl.setWordWrap(True)
                box_layout.addWidget(lbl)
            self._add_widget(box)

        if info.transitions:
            box = QGroupBox(t("dialogue_browser.transitions"))
            box_layout = QVBoxLayout(box)
            for tr in info.transitions:
                row = QHBoxLayout()
                condition_text = tr.condition if tr.condition else t("dialogue_browser.always")
                row.addWidget(QLabel(condition_text), 1)
                row.addWidget(QLabel("→"))
                exists = tr.target in self.dialogue_index or tr.target in _DIALOGUE_REF_SENTINELS
                row.addWidget(_ClickableLabel(tr.target, self._navigate, exists))
                row_widget = QWidget()
                row_widget.setLayout(row)
                box_layout.addWidget(row_widget)
            self._add_widget(box)

        if info.options:
            box = QGroupBox(t("dialogue_browser.options"))
            box_layout = QVBoxLayout(box)
            for opt in info.options:
                text_label = QLabel(opt.text)
                text_label.setWordWrap(True)
                box_layout.addWidget(text_label)
                row = QHBoxLayout()
                if opt.condition:
                    row.addWidget(QLabel(t("dialogue_browser.condition_prefix") + opt.condition))
                row.addWidget(QLabel("→"))
                if opt.next_target:
                    exists = opt.next_target in self.dialogue_index or opt.next_target in _DIALOGUE_REF_SENTINELS
                    row.addWidget(_ClickableLabel(opt.next_target, self._navigate, exists))
                if opt.next_return_to:
                    row.addWidget(QLabel(t("dialogue_browser.return_to") + opt.next_return_to))
                row.addStretch()
                row_widget = QWidget()
                row_widget.setLayout(row)
                box_layout.addWidget(row_widget)
            self._add_widget(box)

        incoming = self.incoming_index.get(name, [])
        if incoming:
            box = QGroupBox(t("dialogue_browser.referenced_by", n=len(incoming)))
            box_layout = QVBoxLayout(box)
            for source_name in sorted(set(incoming)):
                box_layout.addWidget(_ClickableLabel(source_name, self._navigate, True))
            self._add_widget(box)
