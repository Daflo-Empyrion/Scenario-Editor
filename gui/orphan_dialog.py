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
Fenetre listant les jetons potentiellement inutilises -- voir
core/ecf/orphan_check.py pour la portee (jetons uniquement, jamais les blocs/
items generiques) et le raisonnement complet. TOUJOURS informatif, jamais
une erreur : certains jetons peuvent etre utilises implicitement par le jeu
lui-meme (menus, systemes internes) sans reference explicite dans les
fichiers de scenario.

Fenetre NON MODALE (meme motif que les autres verifications) -- reste
ouverte pendant qu'on decide quoi faire de chaque jeton."""
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
)

from gui.busy import busy_guard
from core.i18n import t
from core.ecf.orphan_check import find_unused_tokens
from gui.theme import icon, icon_size
from gui.results_window_helpers import export_text_to_file


class OrphanDialog(QDialog):
    def __init__(self, ecf_files: list, parent=None):
        super().__init__(parent)
        self.ecf_files = ecf_files
        self.unused = []
        self.setWindowTitle(t("orphan.title"))
        self.setMinimumSize(640, 480)

        layout = QVBoxLayout(self)
        intro = QLabel(t("orphan.intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.results_list = QListWidget()
        layout.addWidget(self.results_list, 1)

        bottom_row = QHBoxLayout()
        self.summary_label = QLabel("")
        self.summary_label.setObjectName("mutedLabel")
        bottom_row.addWidget(self.summary_label)
        bottom_row.addStretch()

        btn_refresh = QPushButton(icon("fa5s.sync-alt", "#4a7dfc"), t("results_window.btn_refresh"))
        btn_refresh.setIconSize(icon_size())
        btn_refresh.setObjectName("secondaryButton")
        btn_refresh.clicked.connect(self.refresh)
        bottom_row.addWidget(btn_refresh)

        btn_export = QPushButton(icon("fa5s.file-export", "#4a7dfc"), t("results_window.btn_export"))
        btn_export.setIconSize(icon_size())
        btn_export.setObjectName("secondaryButton")
        btn_export.clicked.connect(self._export)
        bottom_row.addWidget(btn_export)

        btn_close = QPushButton(t("validation.close"))
        btn_close.setObjectName("secondaryButton")
        btn_close.clicked.connect(self.close)
        bottom_row.addWidget(btn_close)
        layout.addLayout(bottom_row)

        self.refresh()

    def refresh(self):
        with busy_guard(self):
            self.unused = find_unused_tokens(self.ecf_files)
        self.results_list.clear()
        for orphan in self.unused:
            self.results_list.addItem(QListWidgetItem(orphan.display()))
        if not self.unused:
            self.summary_label.setText(t("orphan.all_used"))
        else:
            self.summary_label.setText(t("orphan.n_found", n=len(self.unused)))

    def _export(self):
        lines = [t("orphan.title"), "=" * len(t("orphan.title")), ""]
        if not self.unused:
            lines.append(t("orphan.all_used"))
        else:
            for orphan in self.unused:
                lines.append(orphan.display())
        export_text_to_file(self, "jetons_non_utilises.txt", "\n".join(lines))
