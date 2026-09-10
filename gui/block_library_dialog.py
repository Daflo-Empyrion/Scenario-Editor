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

"""Bibliotheque de blocs reutilisables (demande du 10/09/2026) : export d'un
bloc ECF de la copie de travail vers ~/.empyrion_editor/block_library/, et
reinserable dans n'importe quel scenario ouvert. Dialogue NON MODAL (meme
raisonnement que le comparateur : consultable pendant l'edition)."""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPlainTextEdit, QPushButton, QLabel, QFileDialog, QMessageBox, QInputDialog,
)

from core import block_library
from core.i18n import t


class BlockLibraryDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self.main_window = main_window
        self.setWindowTitle(t("lib.title"))
        self.resize(760, 520)
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._on_selected)
        self.list_widget.itemDoubleClicked.connect(self._insert_selected)

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)

        buttons = QHBoxLayout()
        self.btn_insert = QPushButton(t("lib.insert"))
        self.btn_insert.clicked.connect(self._insert_selected)
        self.btn_delete = QPushButton(t("lib.delete"))
        self.btn_delete.clicked.connect(self._delete_selected)
        self.btn_export = QPushButton(t("lib.export"))
        self.btn_export.clicked.connect(self._export_block)
        self.btn_refresh = QPushButton(t("lib.refresh"))
        self.btn_refresh.clicked.connect(self._refresh)
        for b in (self.btn_insert, self.btn_delete, self.btn_export, self.btn_refresh):
            buttons.addWidget(b)

        self.hint = QLabel(t("lib.hint"))
        self.hint.setWordWrap(True)

        layout.addWidget(self.hint)
        row = QHBoxLayout()
        row.addWidget(self.list_widget, 2)
        row.addWidget(self.preview, 3)
        layout.addLayout(row)
        layout.addLayout(buttons)

    def _refresh(self):
        self.list_widget.clear()
        for snippet in block_library.list_snippets():
            item = QListWidgetItem(snippet["name"])
            item.setData(Qt.ItemDataRole.UserRole, snippet["path"])
            self.list_widget.addItem(item)

    def _selected_path(self):
        item = self.list_widget.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _on_selected(self, current, _previous=None):
        path = current.data(Qt.ItemDataRole.UserRole) if current else None
        self.preview.setPlainText(
            block_library.load_snippet(path) if path else "")

    def _delete_selected(self):
        path = self._selected_path()
        if not path:
            return
        if QMessageBox.question(
                self, t("lib.delete"),
                t("lib.confirm_delete", name=Path(path).stem)) != QMessageBox.StandardButton.Yes:
            return
        block_library.delete_snippet(path)
        self.preview.setPlainText("")
        self._refresh()

    def _export_block(self):
        """Exporte un bloc d'un fichier ECF de la copie de travail : choix du
        fichier, puis du bloc (identite), puis enregistrement du texte brut."""
        workspace = self.main_window.workspace
        if not workspace:
            QMessageBox.information(self, t("lib.title"), t("status.no_project"))
            return
        ecf_files = sorted(str(f.path) for f in workspace.working.configuration
                           if f.extension == '.ecf')
        if not ecf_files:
            QMessageBox.information(self, t("lib.title"), t("lib.no_ecf"))
            return
        from PyQt6.QtWidgets import QComboBox, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle(t("lib.export"))
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel(t("lib.pick_file")))
        v.addWidget(combo)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        v.addWidget(bb)
        if not dlg.exec() or not combo.currentText():
            return
        from core.ecf.parser import parse_ecf_file
        from core.ecf.model import EcfBlock
        path = Path(combo.currentText())
        try:
            doc = parse_ecf_file(path)
        except Exception as e:
            QMessageBox.critical(self, t("err.title"), str(e))
            return
        blocks = [n for n in doc.nodes if isinstance(n, EcfBlock)]
        if not blocks:
            QMessageBox.information(self, t("lib.title"), t("lib.no_block"))
            return
        names = []
        for b in blocks:
            ident = b.get('Id') or b.get_property('Name') or '?'
            names.append(f"{b.kind} -- {ident}")
        name, ok = QInputDialog.getItem(self, t("lib.export"),
                                        t("lib.pick_block"), names, 0, False)
        if not ok:
            return
        block = blocks[names.index(name)]
        raw = block.render()
        snippet_name = f"{block.kind} -- {block.get('Id') or block.get_property('Name') or '?'}"
        block_library.save_snippet(snippet_name, raw)
        self._refresh()
        self.status_ok()

    def status_ok(self):
        self.main_window.statusBar().showMessage(t("lib.saved"), 5000)

    def _insert_selected(self, *_args):
        path = self._selected_path()
        if not path:
            return
        mw = self.main_window
        if not mw.workspace:
            QMessageBox.information(self, t("lib.title"), t("status.no_project"))
            return
        dest_str = mw.tabs.tabToolTip(mw.tabs.currentIndex()) if mw.tabs.count() else ""
        if not dest_str:
            QMessageBox.information(self, t("lib.title"), t("lib.no_tab"))
            return
        from pathlib import Path as _Path
        dest = _Path(dest_str)
        if dest.suffix.lower() != '.ecf':
            QMessageBox.information(self, t("lib.title"), t("lib.not_ecf"))
            return
        rel = dest.relative_to(mw.workspace.working_root)
        raw = block_library.load_snippet(path)
        from core.ecf.parser import parse_ecf_text
        try:
            doc = parse_ecf_text(raw)
        except Exception as e:
            QMessageBox.critical(self, t("err.title"), str(e))
            return
        from core.ecf.model import EcfBlock
        block = next((n for n in doc.nodes if isinstance(n, EcfBlock)), None)
        if block is None:
            QMessageBox.information(self, t("lib.title"), t("lib.no_block"))
            return
        from core.workspace import insert_ecf_block_into_working
        from core.workspace_undo import capture_file, FileStateUndo
        prior = capture_file(dest)
        dest_path, status = insert_ecf_block_into_working(
            mw.workspace, rel, block, t("lib.title"))
        if status == 'exists':
            QMessageBox.warning(self, t("lib.title"), t("lib.already_exists"))
            return
        if status == 'parent_not_found':
            QMessageBox.warning(self, t("lib.title"), t("lib.parent_missing"))
            return
        mw._push_workspace_undo(FileStateUndo(dest_path, prior,
                                              t("wsundo.insert_block", name=path.stem)))
        mw.workspace.rescan_working()
        mw.statusBar().showMessage(t("lib.insert_ok", name=path.stem, file=dest_path.name), 6000)
