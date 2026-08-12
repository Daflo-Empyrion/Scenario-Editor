"""
Editeur de fichier .txt (texte brut, ex: description.txt, SqlQueries.txt...). Utilise
QTextEdit nativement (copier/couper/coller/annuler deja geres par Qt), avec en plus la
traduction de la selection et l'outil de mise en forme BBCode, coherents avec les
autres editeurs de l'appli.
"""
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLabel, QMenu, QMessageBox, QDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal

from core import translation
from core.i18n import t
from gui.csv_edit_widget import TranslationResultDialog
from gui.text_tools import open_bbcode_tool


class TxtEditWidget(QWidget):
    """Editeur/visualiseur de fichier .txt. Preserve l'encodage (BOM eventuel) et le
    style de fin de ligne (CRLF/LF) d'origine, comme les autres formats de l'appli."""

    modified_changed = pyqtSignal(bool)
    saved = pyqtSignal()

    def __init__(self, path: Path, editable: bool = True):
        super().__init__()
        self.path = path
        self.editable = editable
        self._modified = False

        with open(path, 'rb') as f:
            raw = f.read()
        self._had_bom = raw.startswith(b'\xef\xbb\xbf')
        text = raw.decode('utf-8-sig')
        self._newline = '\r\n' if '\r\n' in text else '\n'

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)

        mode_text = t("status.editable") if editable else t("status.readonly")
        info_label = QLabel(f"{path.name}  ({mode_text})")
        info_label.setStyleSheet("font-size: 11px; color: gray;")
        layout.addWidget(info_label, 0)

        if editable:
            toolbar = QHBoxLayout()
            toolbar.setSpacing(4)
            btn_undo = QPushButton(t("btn.undo"))
            btn_undo.clicked.connect(lambda: self.text_edit.undo())
            toolbar.addWidget(btn_undo)
            btn_save = QPushButton(t("btn.save"))
            btn_save.clicked.connect(self.save)
            toolbar.addWidget(btn_save)
            toolbar.addStretch()
            layout.addLayout(toolbar, 0)

        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(text)
        self.text_edit.setReadOnly(not editable)
        self.text_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.text_edit.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.text_edit, 1)

        self._loaded = False
        self.text_edit.textChanged.connect(self._on_text_changed)
        self._loaded = True

    def _on_text_changed(self):
        if self.editable and self._loaded:
            self._set_modified(True)

    def _set_modified(self, value: bool):
        if value != self._modified:
            self._modified = value
            self.modified_changed.emit(value)

    def is_modified(self) -> bool:
        return self._modified

    def save(self):
        if not self.editable:
            return
        content = self.text_edit.toPlainText()
        if self._newline == '\r\n':
            content = content.replace('\r\n', '\n').replace('\n', '\r\n')
        with open(self.path, 'w', encoding='utf-8', newline='') as f:
            if self._had_bom:
                f.write('\ufeff')
            f.write(content)
        self._set_modified(False)
        self.saved.emit()

    def _show_context_menu(self, pos):
        menu = self.text_edit.createStandardContextMenu()

        cursor = self.text_edit.textCursor()
        selected = cursor.selectedText().replace('\u2029', '\n')

        lang_actions = {}
        action_bbcode = None
        if self.editable and selected.strip():
            menu.addSeparator()
            translate_menu = menu.addMenu(t("ctx.translate_selection_to"))
            for label, code in translation.COMMON_LANGUAGES:
                a = translate_menu.addAction(label)
                lang_actions[a] = code
            action_bbcode = menu.addAction(t("ctx.bbcode"))

        chosen = menu.exec(self.text_edit.viewport().mapToGlobal(pos))

        if action_bbcode is not None and chosen == action_bbcode:
            new_text = open_bbcode_tool(self, selected)
            if new_text is not None:
                cursor.insertText(new_text)
            return

        if chosen not in lang_actions:
            return
        target_code = lang_actions[chosen]

        if not translation.is_available():
            QMessageBox.warning(self, t("trans.unavailable_title"), t("trans.unavailable_msg"))
            return
        try:
            translated = translation.translate_text(selected, target=target_code)
        except Exception as e:
            QMessageBox.critical(self, t("trans.error_title"), t("trans.error_msg", error=e))
            return

        dialog = TranslationResultDialog(selected, translated, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.accepted_replace:
            cursor.insertText(dialog.result_text())
