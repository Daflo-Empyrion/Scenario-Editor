"""
Widget d'edition CSV (tableau) pour la copie de travail, avec traduction par clic
droit (Google Translate via deep-translator) directement sur une cellule.
"""
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QLabel,
    QPushButton, QMenu, QMessageBox, QDialog, QTextEdit,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush

from core.csv_handler import CsvHandler, CsvDocument, render_csv
from core import translation

COLOR_MODIFIED_CELL = QBrush(QColor(255, 250, 200))


class TranslationResultDialog(QDialog):
    """Petite fenetre affichant le resultat d'une traduction, avec le choix de
    remplacer la cellule d'origine ou juste copier le resultat."""

    def __init__(self, original: str, translated: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Traduction")
        self.setMinimumWidth(500)
        self.accepted_replace = False

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Original :"))
        orig_view = QTextEdit()
        orig_view.setPlainText(original)
        orig_view.setReadOnly(True)
        orig_view.setMaximumHeight(80)
        layout.addWidget(orig_view)

        layout.addWidget(QLabel("Traduction :"))
        self.translated_view = QTextEdit()
        self.translated_view.setPlainText(translated)
        layout.addWidget(self.translated_view)

        buttons = QHBoxLayout()
        btn_replace = QPushButton("Remplacer la cellule par ce texte")
        btn_replace.clicked.connect(self._on_replace)
        buttons.addWidget(btn_replace)
        btn_close = QPushButton("Fermer (ne pas remplacer)")
        btn_close.clicked.connect(self.reject)
        buttons.addWidget(btn_close)
        layout.addLayout(buttons)

    def _on_replace(self):
        self.accepted_replace = True
        self.accept()

    def result_text(self) -> str:
        return self.translated_view.toPlainText()


def show_translate_context_menu(parent_widget, global_pos, text: str, on_apply):
    """Affiche un menu contextuel 'Traduire vers...' (sous-menu de langues) a la
    position donnee. Si l'utilisateur choisit une langue et confirme le remplacement
    dans la fenetre de resultat, appelle on_apply(texte_traduit)."""
    if not text or not text.strip():
        return

    menu = QMenu(parent_widget)
    translate_menu = menu.addMenu("Traduire vers...")
    lang_actions = {}
    for label, code in translation.COMMON_LANGUAGES:
        action = translate_menu.addAction(label)
        lang_actions[action] = code

    chosen = menu.exec(global_pos)
    if chosen not in lang_actions:
        return

    if not translation.is_available():
        QMessageBox.warning(parent_widget, "Traduction indisponible",
                             "deep-translator n'est pas installe.\nLance : pip install deep-translator")
        return

    target_lang = lang_actions[chosen]
    try:
        translated = translation.translate_text(text, target=target_lang)
    except Exception as e:
        QMessageBox.critical(parent_widget, "Erreur de traduction",
                              f"La traduction a echoue :\n{e}\n\nVerifie ta connexion internet.")
        return

    dialog = TranslationResultDialog(text, translated, parent_widget)
    if dialog.exec() == QDialog.DialogCode.Accepted and dialog.accepted_replace:
        on_apply(dialog.result_text())


class CsvEditWidget(QWidget):
    """Editeur de fichier .csv (copie de travail) : tableau editable, avec traduction
    par clic droit sur une cellule."""

    modified_changed = pyqtSignal(bool)
    saved = pyqtSignal()

    def __init__(self, path: Path):
        super().__init__()
        self.path = path
        self._modified = False

        handler = CsvHandler()
        raw = handler.load(path)
        self.doc: CsvDocument = handler.parse(raw)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)

        info_label = QLabel(f"{path.name}  (copie de travail -- modifiable) -- "
                             f"{len(self.doc.rows)} ligne(s), delimiteur '{self.doc.delimiter}'")
        info_label.setStyleSheet("font-size: 11px; color: gray;")
        layout.addWidget(info_label, 0)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)
        btn_add_row = QPushButton("+ Ligne")
        btn_add_row.clicked.connect(self._add_row)
        toolbar.addWidget(btn_add_row)
        btn_del_row = QPushButton("- Ligne selectionnee")
        btn_del_row.clicked.connect(self._delete_selected_row)
        toolbar.addWidget(btn_del_row)
        btn_save = QPushButton("Enregistrer (Ctrl+S)")
        btn_save.clicked.connect(self.save)
        toolbar.addWidget(btn_save)
        toolbar.addStretch()
        layout.addLayout(toolbar, 0)

        n_cols = len(self.doc.header) if self.doc.header else (len(self.doc.rows[0]) if self.doc.rows else 1)
        self.table = QTableWidget(len(self.doc.rows), n_cols)
        if self.doc.header:
            self.table.setHorizontalHeaderLabels(self.doc.header)
        self.table.horizontalHeader().setStretchLastSection(True)
        self._populate_table()
        self.table.itemChanged.connect(self._on_cell_changed)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.table, 1)

    def _populate_table(self):
        self.table.blockSignals(True)
        for r, row in enumerate(self.doc.rows):
            for c in range(self.table.columnCount()):
                val = row[c] if c < len(row) else ""
                self.table.setItem(r, c, QTableWidgetItem(val))
        self.table.blockSignals(False)

    def _set_modified(self, value: bool):
        if value != self._modified:
            self._modified = value
            self.modified_changed.emit(value)

    def is_modified(self) -> bool:
        return self._modified

    def save(self):
        self._sync_doc_from_table()
        rendered = render_csv(self.doc)
        with open(self.path, 'w', encoding='utf-8', newline='') as f:
            f.write(rendered)
        self._set_modified(False)
        self.saved.emit()

    def _sync_doc_from_table(self):
        rows = []
        for r in range(self.table.rowCount()):
            row = []
            for c in range(self.table.columnCount()):
                item = self.table.item(r, c)
                row.append(item.text() if item else "")
            rows.append(row)
        self.doc.rows = rows

    def _on_cell_changed(self, item: QTableWidgetItem):
        item.setBackground(COLOR_MODIFIED_CELL)
        self._set_modified(True)

    def _add_row(self):
        r = self.table.rowCount()
        self.table.insertRow(r)
        for c in range(self.table.columnCount()):
            self.table.setItem(r, c, QTableWidgetItem(""))
        self._set_modified(True)

    def _delete_selected_row(self):
        r = self.table.currentRow()
        if r < 0:
            return
        self.table.removeRow(r)
        self._set_modified(True)

    def _show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item:
            return
        global_pos = self.table.viewport().mapToGlobal(pos)
        show_translate_context_menu(self, global_pos, item.text(), lambda t: item.setText(t))
