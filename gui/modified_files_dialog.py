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

"""Vue « fichiers modifies » (demande du 10/09/2026) : liste des fichiers de
la copie de travail qui different du scENARIO A d'origine -- ajoutes ou
modifies. Comparaison par TAILLE puis par contenu (les fichiers identiques
re-ecrits a l'octet pres ne sont pas signales). Double-clic ou « Ouvrir » :
charge le fichier dans un onglet de la copie de travail."""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel,
)

from core.i18n import t


def _hash(path: Path) -> bytes:
    import hashlib
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.digest()


def list_changed_files(working_root: Path, source_root: Path):
    """Retourne [(chemin_copie, 'added'|'modified')] tries par chemin. Les
    fichiers presents seulement dans A sont ignores (suppressions
    volontaires rares -- et les signaler doublerait la liste)."""
    changes = []
    for path in sorted(Path(working_root).rglob('*')):
        if not path.is_file():
            continue
        rel = path.relative_to(working_root)
        counterpart = Path(source_root) / rel
        if not counterpart.exists():
            changes.append((path, 'added'))
            continue
        if path.stat().st_size != counterpart.stat().st_size or \
                _hash(path) != _hash(counterpart):
            changes.append((path, 'modified'))
    return changes


class ModifiedFilesDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self.main_window = main_window
        self.setWindowTitle(t("modfiles.title"))
        self.resize(720, 500)
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self.summary = QLabel("")
        layout.addWidget(self.summary)
        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self._open_selected)
        layout.addWidget(self.list_widget)
        buttons = QHBoxLayout()
        btn_open = QPushButton(t("modfiles.open"))
        btn_open.clicked.connect(self._open_selected)
        btn_refresh = QPushButton(t("dash.refresh"))
        btn_refresh.clicked.connect(self._refresh)
        buttons.addWidget(btn_open)
        buttons.addWidget(btn_refresh)
        layout.addLayout(buttons)

    def _refresh(self):
        self.list_widget.clear()
        ws = self.main_window.workspace
        if not ws:
            self.summary.setText(t("status.no_project"))
            return
        from gui.busy import busy_guard
        with busy_guard(self):
            changes = list_changed_files(ws.working_root, ws.source_a_root)
        for path, state in changes:
            key = "modfiles.state_added" if state == 'added' else "modfiles.state_modified"
            item = QListWidgetItem(f"[{t(key)}] {path.relative_to(ws.working_root)}")
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.list_widget.addItem(item)
        self.summary.setText(t("modfiles.summary", n=len(changes)))

    def _open_selected(self, *_args):
        item = self.list_widget.currentItem()
        if not item:
            return
        path = Path(item.data(Qt.ItemDataRole.UserRole))
        self.main_window.open_working_file_tab(path)
