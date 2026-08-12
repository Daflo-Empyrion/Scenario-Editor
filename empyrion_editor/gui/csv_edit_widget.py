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
from core.i18n import t
from gui.text_tools import (
    copy_selection, cut_selection, paste_into_selection, delete_selection, delete_selected_rows,
    install_clipboard_shortcuts, add_clipboard_menu_actions, open_bbcode_tool,
)

COLOR_MODIFIED_CELL = QBrush(QColor(255, 250, 200))


class TranslationResultDialog(QDialog):
    """Petite fenetre affichant le resultat d'une traduction, avec le choix de
    remplacer la cellule d'origine (ou une cellule destination precise) ou juste
    copier le resultat."""

    def __init__(self, original: str, translated: str, parent=None, destination_label: Optional[str] = None):
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
        replace_label = f"Placer dans {destination_label}" if destination_label else "Remplacer la cellule par ce texte"
        btn_replace = QPushButton(replace_label)
        btn_replace.clicked.connect(self._on_replace)
        buttons.addWidget(btn_replace)
        btn_close = QPushButton("Fermer (ne pas appliquer)")
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
    translate_menu = menu.addMenu(t("ctx.translate_to"))
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
    """Editeur/visualiseur de fichier .csv : tableau editable si `editable=True` (copie
    de travail), ou lecture seule sinon (Scenario A/B). La traduction par clic droit
    reste disponible dans les deux cas. En lecture seule, si `on_copy_row` est fourni,
    un clic droit propose de copier la ligne (par cle) vers la copie de travail."""

    modified_changed = pyqtSignal(bool)
    saved = pyqtSignal()

    def __init__(self, path: Path, editable: bool = True, on_copy_row=None, copy_label: Optional[str] = None,
                 on_translate_cell=None, on_duplicate_row=None):
        super().__init__()
        self.path = path
        self.editable = editable
        self.on_copy_row = on_copy_row
        self.copy_label = copy_label
        self.on_translate_cell = on_translate_cell
        self.on_duplicate_row = on_duplicate_row
        self._modified = False
        self._undo_stack: list = []
        self._undo_max = 20
        self._pre_edit_snapshot = None  # capture avant edition en double-clic

        handler = CsvHandler()
        raw = handler.load(path)
        self.doc: CsvDocument = handler.parse(raw)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)

        mode_text = t("status.editable") if editable else t("status.readonly")
        info_label = QLabel(f"{path.name}  ({mode_text}) -- "
                             f"{len(self.doc.rows)} ligne(s), delimiteur '{self.doc.delimiter}'")
        info_label.setStyleSheet("font-size: 11px; color: gray;")
        layout.addWidget(info_label, 0)

        if editable:
            toolbar = QHBoxLayout()
            toolbar.setSpacing(4)
            btn_add_row = QPushButton(t("btn.add_row"))
            btn_add_row.clicked.connect(self._add_row)
            toolbar.addWidget(btn_add_row)
            btn_del_row = QPushButton(t("btn.delete_selected_row"))
            btn_del_row.clicked.connect(self._delete_selected_row)
            toolbar.addWidget(btn_del_row)
            self.btn_undo = QPushButton(t("btn.undo"))
            self.btn_undo.clicked.connect(self.undo)
            self.btn_undo.setEnabled(False)
            toolbar.addWidget(self.btn_undo)
            btn_save = QPushButton(t("btn.save"))
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
        if not editable:
            from PyQt6.QtWidgets import QAbstractItemView
            self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemChanged.connect(self._on_cell_changed)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        if editable:
            self.table.setSelectionMode(self.table.SelectionMode.ContiguousSelection)
            self.table.itemDoubleClicked.connect(lambda item: self._snapshot_undo())
            from PyQt6.QtGui import QKeySequence, QShortcut
            QShortcut(QKeySequence.StandardKey.Copy, self.table,
                      activated=lambda: copy_selection(self.table))
            QShortcut(QKeySequence.StandardKey.Cut, self.table,
                      activated=self._do_cut)
            QShortcut(QKeySequence.StandardKey.Paste, self.table,
                      activated=self._do_paste)
            QShortcut(QKeySequence(Qt.Key.Key_Delete), self.table,
                      activated=self._do_delete_content)
            QShortcut(QKeySequence.StandardKey.Undo, self, activated=self.undo)
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
        if not self.editable:
            return
        self._sync_doc_from_table()
        rendered = render_csv(self.doc)
        with open(self.path, 'w', encoding='utf-8', newline='') as f:
            f.write(rendered)
        self._set_modified(False)
        self.saved.emit()

    def _snapshot_table(self) -> list:
        return [[self.table.item(r, c).text() if self.table.item(r, c) else ""
                 for c in range(self.table.columnCount())]
                for r in range(self.table.rowCount())]

    def _snapshot_undo(self):
        """A appeler AVANT toute modification (edition, coller, ajout/suppression de
        ligne...) -- capture le tableau tel qu'il est maintenant, pour pouvoir y revenir."""
        self._undo_stack.append(self._snapshot_table())
        if len(self._undo_stack) > self._undo_max:
            self._undo_stack.pop(0)
        self.btn_undo.setEnabled(True)

    def undo(self):
        if not self._undo_stack:
            return
        snapshot = self._undo_stack.pop()
        self.table.blockSignals(True)
        self.table.setRowCount(len(snapshot))
        for r, row_vals in enumerate(snapshot):
            for c, val in enumerate(row_vals):
                item = self.table.item(r, c)
                if item is None:
                    item = QTableWidgetItem("")
                    self.table.setItem(r, c, item)
                item.setText(val)
        self.table.blockSignals(False)
        self._set_modified(True)
        if not self._undo_stack:
            self.btn_undo.setEnabled(False)

    def _do_cut(self):
        self._snapshot_undo()
        cut_selection(self.table)

    def _do_paste(self):
        self._snapshot_undo()
        paste_into_selection(self.table, allow_new_rows=True)

    def _do_delete_content(self):
        self._snapshot_undo()
        delete_selection(self.table)

    def _do_delete_rows(self):
        self._snapshot_undo()
        delete_selected_rows(self.table)
        self._set_modified(True)

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
        self._snapshot_undo()
        r = self.table.rowCount()
        self.table.insertRow(r)
        for c in range(self.table.columnCount()):
            self.table.setItem(r, c, QTableWidgetItem(""))
        self._set_modified(True)

    def _delete_selected_row(self):
        r = self.table.currentRow()
        if r < 0:
            return
        self._snapshot_undo()
        self.table.removeRow(r)
        self._set_modified(True)

    def _find_language_column(self, target_code: str, target_label: str) -> Optional[int]:
        """Trouve la colonne dont l'en-tete correspond a la langue cible -- via une
        liste d'alias (code ISO, nom anglais, nom natif, libelle du menu), comparaison
        insensible aux accents et a la casse (voir core.translation.find_language_aliases)."""
        aliases = translation.find_language_aliases(target_code, target_label)
        for c in range(self.table.columnCount()):
            header_item = self.table.horizontalHeaderItem(c)
            if not header_item:
                continue
            if translation._normalize(header_item.text().strip()) in aliases:
                return c
        return None

    def _show_context_menu(self, pos):
        if not self.editable:
            # Vue lecture seule (Scenario A/B) : copier la ligne entiere, ET/OU
            # traduire directement cette cellule vers la colonne de la langue
            # choisie dans la copie de travail (meme ligne, cle identique).
            item = self.table.itemAt(pos)
            if not item:
                return
            row_idx = item.row()
            row_values = [self.table.item(row_idx, c).text() if self.table.item(row_idx, c) else ""
                          for c in range(self.table.columnCount())]
            key = row_values[0] if row_values else "?"
            text = item.text()

            menu = QMenu(self)
            action_copy = None
            if self.on_copy_row:
                action_copy = menu.addAction(f"Copier cette ligne (cle '{key}') vers la copie de travail")
            action_dup = None
            if self.on_duplicate_row:
                action_dup = menu.addAction(f"Dupliquer avec une nouvelle cle vers la copie de travail...")

            lang_actions = {}
            if self.on_translate_cell and text.strip():
                translate_menu = menu.addMenu(t("ctx.translate_cell_to"))
                for label, code in translation.COMMON_LANGUAGES:
                    a = translate_menu.addAction(label)
                    lang_actions[a] = (code, label)

            if not action_copy and not action_dup and not lang_actions:
                return

            chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
            if action_copy and chosen == action_copy:
                self.on_copy_row(row_values)
            elif action_dup and chosen == action_dup:
                self.on_duplicate_row(row_values)
            elif chosen in lang_actions:
                target_code, target_label = lang_actions[chosen]
                self.on_translate_cell(key, text, target_code, target_label)
            return

        item = self.table.itemAt(pos)
        if item is None:
            item = self.table.currentItem()

        menu = QMenu(self)
        menu.addAction(t("ctx.copy"), lambda: copy_selection(self.table))
        menu.addAction(t("ctx.cut"), self._do_cut)
        menu.addAction(t("ctx.paste"), self._do_paste)
        menu.addAction(t("ctx.clear_content"), self._do_delete_content)
        action_del_row = menu.addAction(t("ctx.delete_rows"))
        menu.addSeparator()

        text = item.text() if item else ""
        translate_menu = None
        lang_actions = {}
        action_bbcode = None
        if item and text.strip():
            translate_menu = menu.addMenu(t("ctx.translate_to"))
            for label, code in translation.COMMON_LANGUAGES:
                a = translate_menu.addAction(label)
                lang_actions[a] = (code, label)
            action_bbcode = menu.addAction(t("ctx.bbcode"))

        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))

        if chosen == action_del_row:
            self._do_delete_rows()
            return

        if item is None:
            return
        row = item.row()

        if action_bbcode is not None and chosen == action_bbcode:
            new_text = open_bbcode_tool(self, text)
            if new_text is not None:
                self._snapshot_undo()
                item.setText(new_text)
            return

        if chosen not in lang_actions:
            return
        target_code, target_label = lang_actions[chosen]

        if not translation.is_available():
            QMessageBox.warning(self, t("trans.unavailable_title"), t("trans.unavailable_msg"))
            return
        try:
            translated = translation.translate_text(text, target=target_code)
        except Exception as e:
            QMessageBox.critical(self, t("trans.error_title"), t("trans.error_msg", error=e))
            return

        target_col = self._find_language_column(target_code, target_label)
        dest_label = None
        if target_col is not None and target_col != item.column():
            header = self.table.horizontalHeaderItem(target_col)
            dest_label = f"la colonne '{header.text() if header else target_label}' (meme ligne)"

        dialog = TranslationResultDialog(text, translated, self, destination_label=dest_label)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.accepted_replace:
            return
        result_text = dialog.result_text()

        self._snapshot_undo()
        if target_col is not None and target_col != item.column():
            dest_item = self.table.item(row, target_col)
            if dest_item is None:
                dest_item = QTableWidgetItem("")
                self.table.setItem(row, target_col, dest_item)
            dest_item.setText(result_text)
        else:
            # Pas de colonne correspondant a cette langue trouvee dans l'en-tete ->
            # on remplace la cellule d'origine par defaut, comme avant.
            item.setText(result_text)
