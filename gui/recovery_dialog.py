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
Propose de restaurer des instantanes de recuperation trouves pour le
scenario qui vient d'etre ouvert -- voir core/autosave.py. Affiche uniquement
si des instantanes existent reellement (voir MainWindow._check_for_recovery,
appele juste apres l'ouverture d'un projet, avant que le moindre onglet ne
soit ouvert -- la restauration peut donc ecrire directement dans les vrais
fichiers de la copie de travail sans risque de conflit avec un onglet deja
ouvert sur le meme fichier)."""
from pathlib import Path
from typing import List

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
)

from core.i18n import t
from core import autosave


class RecoveryDialog(QDialog):
    def __init__(self, working_root: Path, encoded_files: List[str], parent=None):
        super().__init__(parent)
        self.working_root = working_root
        self.encoded_files = encoded_files
        self.setWindowTitle(t("recovery.title"))
        self.setMinimumSize(560, 360)

        layout = QVBoxLayout(self)
        intro = QLabel(t("recovery.intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.files_list = QListWidget()
        for encoded in encoded_files:
            self.files_list.addItem(QListWidgetItem(str(autosave.decode_relative_name(encoded))))
        layout.addWidget(self.files_list, 1)

        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        btn_discard = QPushButton(t("recovery.btn_discard"))
        btn_discard.setObjectName("secondaryButton")
        btn_discard.clicked.connect(self._on_discard)
        bottom_row.addWidget(btn_discard)
        btn_restore = QPushButton(t("recovery.btn_restore"))
        btn_restore.setObjectName("primaryButton")
        btn_restore.clicked.connect(self._on_restore)
        bottom_row.addWidget(btn_restore)
        layout.addLayout(bottom_row)

    def _on_restore(self):
        for encoded in self.encoded_files:
            content = autosave.read_recovery_content(self.working_root, encoded)
            if content is None:
                continue
            real_path = self.working_root / autosave.decode_relative_name(encoded)
            real_path.parent.mkdir(parents=True, exist_ok=True)
            real_path.write_text(content, encoding="utf-8", newline="")
        autosave.clear_recovery_for_scenario(self.working_root)
        self.accept()

    def _on_discard(self):
        autosave.clear_recovery_for_scenario(self.working_root)
        self.reject()
