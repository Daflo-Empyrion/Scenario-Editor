"""
Widget d'edition CSV (tableau) pour la copie de travail, avec traduction par clic
droit (Google Translate via deep-translator) directement sur une cellule.
"""
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QLabel,
    QPushButton, QMenu, QMessageBox, QDialog, QTextEdit, QLineEdit, QComboBox,
    QApplication, QFormLayout,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush

from core.csv_handler import CsvHandler, CsvDocument, render_csv
from core import translation, settings
from core.i18n import t
from gui.theme import icon, icon_size
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
        self.setWindowTitle(t("trans.dialog_title"))
        self.setMinimumWidth(500)
        self.accepted_replace = False

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(t("trans.original_label")))
        orig_view = QTextEdit()
        orig_view.setPlainText(original)
        orig_view.setReadOnly(True)
        orig_view.setMaximumHeight(80)
        layout.addWidget(orig_view)

        layout.addWidget(QLabel(t("trans.translation_label")))
        self.translated_view = QTextEdit()
        self.translated_view.setPlainText(translated)
        layout.addWidget(self.translated_view)

        buttons = QHBoxLayout()
        replace_label = t("trans.place_in", destination=destination_label) if destination_label else t("trans.replace_cell")
        btn_replace = QPushButton(replace_label)
        btn_replace.clicked.connect(self._on_replace)
        buttons.addWidget(btn_replace)
        btn_close = QPushButton(t("trans.close_no_apply"))
        btn_close.setObjectName("secondaryButton")
        btn_close.clicked.connect(self.reject)
        buttons.addWidget(btn_close)
        layout.addLayout(buttons)

    def _on_replace(self):
        self.accepted_replace = True
        self.accept()

    def result_text(self) -> str:
        return self.translated_view.toPlainText()


class BatchTranslationReviewDialog(QDialog):
    """Revue et validation d'un lot de traductions avant application -- reutilise pour
    la traduction en lot (selection multiple) et le comblement des langues manquantes.
    Chaque ligne : case a cocher pour l'inclure ou non, cle/reference, texte original,
    traduction (modifiable avant validation)."""

    def __init__(self, items: list, parent=None):
        """items : liste de dicts {'label': str, 'original': str, 'translated': str}"""
        super().__init__(parent)
        self.setWindowTitle(t("trans.batch_review_title"))
        self.resize(750, 450)

        layout = QVBoxLayout(self)
        intro = QLabel(t("trans.batch_review_intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["", t("trans.col_key"), t("trans.col_original"), t("trans.col_translated")])
        self.table.setRowCount(len(items))
        for i, item in enumerate(items):
            check_item = QTableWidgetItem()
            check_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            check_item.setCheckState(Qt.CheckState.Checked)
            self.table.setItem(i, 0, check_item)

            key_item = QTableWidgetItem(item['label'])
            key_item.setFlags(key_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 1, key_item)

            orig_item = QTableWidgetItem(item['original'])
            orig_item.setFlags(orig_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 2, orig_item)

            self.table.setItem(i, 3, QTableWidgetItem(item['translated']))

        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        btn_check_all = QPushButton(t("trans.check_all"))
        btn_check_all.setObjectName("secondaryButton")
        btn_check_all.clicked.connect(lambda: self._set_all_checked(True))
        btn_row.addWidget(btn_check_all)
        btn_uncheck_all = QPushButton(t("trans.uncheck_all"))
        btn_uncheck_all.setObjectName("secondaryButton")
        btn_uncheck_all.clicked.connect(lambda: self._set_all_checked(False))
        btn_row.addWidget(btn_uncheck_all)
        btn_row.addStretch()
        self.btn_apply = QPushButton(t("trans.apply_checked", count=len(items)))
        self.btn_apply.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_apply)
        btn_cancel = QPushButton(t("btn.cancel"))
        btn_cancel.setObjectName("secondaryButton")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

        self.table.itemChanged.connect(self._update_apply_count)

    def _set_all_checked(self, checked: bool):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self.table.rowCount()):
            self.table.item(i, 0).setCheckState(state)

    def _update_apply_count(self, item):
        if item.column() == 0:
            count = sum(1 for i in range(self.table.rowCount())
                        if self.table.item(i, 0).checkState() == Qt.CheckState.Checked)
            self.btn_apply.setText(t("trans.apply_checked", count=count))

    def get_accepted_results(self) -> list:
        """Retourne [(index_dans_la_liste_items_d_origine, texte_final), ...] pour les
        lignes cochees -- le texte final tient compte d'un eventuel ajustement manuel
        de l'utilisateur dans le tableau avant validation."""
        results = []
        for i in range(self.table.rowCount()):
            if self.table.item(i, 0).checkState() == Qt.CheckState.Checked:
                results.append((i, self.table.item(i, 3).text()))
        return results


class FillMissingTranslationsDialog(QDialog):
    """Choix de la colonne source (deja remplie) et de la colonne cible (a completer)
    parmi les colonnes REELLEMENT presentes dans le fichier -- pas une liste generique
    de langues, pour eviter de proposer une langue absente du fichier."""

    def __init__(self, column_headers: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("trans.fill_missing_title"))

        layout = QFormLayout(self)
        self.source_combo = QComboBox()
        self.source_combo.addItems(column_headers)
        layout.addRow(t("trans.fill_source_label"), self.source_combo)

        self.target_combo = QComboBox()
        self.target_combo.addItems(column_headers)
        if len(column_headers) > 1:
            self.target_combo.setCurrentIndex(1)
        layout.addRow(t("trans.fill_target_label"), self.target_combo)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton(t("trans.fill_scan_btn"))
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_ok)
        btn_cancel = QPushButton(t("btn.cancel"))
        btn_cancel.setObjectName("secondaryButton")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        layout.addRow(btn_row)


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
        QMessageBox.warning(parent_widget, t("trans.unavailable_title"), t("trans.unavailable_msg"))
        return

    target_lang = lang_actions[chosen]
    try:
        translated = translation.translate_text(text, target=target_lang)
    except Exception as e:
        QMessageBox.critical(parent_widget, t("trans.error_title"), t("trans.error_msg", error=e))
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
        self._search_matches = []
        self._search_index = -1
        self._search_last_scope_key = None

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

        n_cols = len(self.doc.header) if self.doc.header else (len(self.doc.rows[0]) if self.doc.rows else 1)

        search_row = QHBoxLayout()
        search_row.setSpacing(4)
        search_row.addWidget(QLabel(t("label.search")))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(t("csv.search_placeholder"))
        self.search_box.addAction(icon("fa5s.search", color="#7c859c"), QLineEdit.ActionPosition.LeadingPosition)
        self.search_box.returnPressed.connect(self._search_next)
        search_row.addWidget(self.search_box, 1)
        search_row.addWidget(QLabel(t("csv.search_scope_label")))
        self.search_scope = QComboBox()
        self.search_scope.addItem(t("search.column_all"), None)
        header_labels = self.doc.header or [str(i) for i in range(n_cols)]
        for col_index, col_name in enumerate(header_labels):
            self.search_scope.addItem(col_name, col_index)
        search_row.addWidget(self.search_scope)
        self.search_status = QLabel("")
        search_row.addWidget(self.search_status)
        layout.addLayout(search_row, 0)

        if editable:
            toolbar = QHBoxLayout()
            toolbar.setSpacing(4)
            btn_add_row = QPushButton(icon("fa5s.plus", "#ffffff"), t("btn.add_row"))
            btn_add_row.setIconSize(icon_size())
            btn_add_row.clicked.connect(self._add_row)
            toolbar.addWidget(btn_add_row)
            btn_del_row = QPushButton(icon("fa5s.trash-alt", "#4a7dfc"), t("btn.delete_selected_row"))
            btn_del_row.setIconSize(icon_size())
            btn_del_row.setObjectName("secondaryButton")
            btn_del_row.clicked.connect(self._delete_selected_row)
            toolbar.addWidget(btn_del_row)
            btn_fill_missing = QPushButton(icon("fa5s.language", "#4a7dfc"), t("btn.fill_missing_translations"))
            btn_fill_missing.setIconSize(icon_size())
            btn_fill_missing.setObjectName("secondaryButton")
            btn_fill_missing.clicked.connect(self._open_fill_missing_dialog)
            toolbar.addWidget(btn_fill_missing)
            btn_quick_translate = QPushButton(icon("fa5s.globe", "#4a7dfc"), t("btn.quick_translate"))
            btn_quick_translate.setIconSize(icon_size())
            btn_quick_translate.setObjectName("secondaryButton")
            btn_quick_translate.clicked.connect(self._quick_translate)
            toolbar.addWidget(btn_quick_translate)
            self.btn_undo = QPushButton(icon("fa5s.undo", "#7c859c"), t("btn.undo"))
            self.btn_undo.setIconSize(icon_size())
            self.btn_undo.setObjectName("secondaryButton")
            self.btn_undo.clicked.connect(self.undo)
            self.btn_undo.setEnabled(False)
            toolbar.addWidget(self.btn_undo)
            btn_save = QPushButton(icon("fa5s.save", "#ffffff"), t("btn.save"))
            btn_save.setIconSize(icon_size())
            btn_save.clicked.connect(self.save)
            toolbar.addWidget(btn_save)
            toolbar.addStretch()
            layout.addLayout(toolbar, 0)

        self.table = QTableWidget(len(self.doc.rows), n_cols)
        if self.doc.header:
            self.table.setHorizontalHeaderLabels(self.doc.header)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.horizontalHeader().customContextMenuRequested.connect(self._show_header_context_menu)
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

    def _show_header_context_menu(self, pos):
        col = self.table.horizontalHeader().logicalIndexAt(pos)
        if col < 0:
            return
        col_name = self.doc.header[col] if self.doc.header and col < len(self.doc.header) else str(col)
        menu = QMenu(self)
        action_search = menu.addAction(t("search.in_column_action", name=col_name))
        chosen = menu.exec(self.table.horizontalHeader().viewport().mapToGlobal(pos))
        if chosen == action_search:
            idx = self.search_scope.findData(col)
            if idx >= 0:
                self.search_scope.setCurrentIndex(idx)
            self._search_matches = []  # force un recalcul avec la nouvelle portee
            self.search_box.setFocus()
            self.search_box.selectAll()

    def _search_next(self):
        query = self.search_box.text().strip().lower()
        if not query:
            self.search_status.setText("")
            return

        scope_col = self.search_scope.currentData()  # None = toutes les colonnes
        scope_key = (query, scope_col)

        if not self._search_matches or self._search_last_scope_key != scope_key:
            self._search_matches = []
            n_rows = self.table.rowCount()
            cols = [scope_col] if scope_col is not None else list(range(self.table.columnCount()))
            for r in range(n_rows):
                for c in cols:
                    item = self.table.item(r, c)
                    if item and query in item.text().lower():
                        self._search_matches.append((r, c))
            self._search_index = -1
            self._search_last_scope_key = scope_key

        if not self._search_matches:
            self.search_status.setText(t("search.no_results"))
            return

        self._search_index = (self._search_index + 1) % len(self._search_matches)
        r, c = self._search_matches[self._search_index]
        self.table.setCurrentCell(r, c)
        self.table.scrollToItem(self.table.item(r, c))
        self.search_status.setText(f"{self._search_index + 1} / {len(self._search_matches)}")

    def save(self):
        if not self.editable:
            return
        self._sync_doc_from_table()
        rendered = render_csv(self.doc)
        try:
            from core.fsutil import clear_readonly
            clear_readonly(self.path)
            with open(self.path, 'w', encoding='utf-8', newline='') as f:
                f.write(rendered)
        except OSError as e:
            QMessageBox.critical(self, t("save.error_title"),
                                  t("save.error_msg", name=self.path.name, error=str(e)))
            return
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
                action_copy = menu.addAction(t("csv.copy_row_action", key=key))
            action_dup = None
            if self.on_duplicate_row:
                action_dup = menu.addAction(t("csv.duplicate_row_action"))

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

        selected_items = self.table.selectedItems()
        batch_menu = None
        batch_lang_actions = {}
        if len(selected_items) > 1 and any(it.text().strip() for it in selected_items):
            batch_menu = menu.addMenu(t("trans.batch_title"))
            for label, code in translation.COMMON_LANGUAGES:
                a = batch_menu.addAction(label)
                batch_lang_actions[a] = (code, label)

        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))

        if chosen == action_del_row:
            self._do_delete_rows()
            return

        if chosen in batch_lang_actions:
            target_code, target_label = batch_lang_actions[chosen]
            self._batch_translate_selection(selected_items, target_code, target_label)
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
        self._translate_single_cell(item, text, target_code, target_label)

    def _translate_single_cell(self, item: QTableWidgetItem, text: str, target_code: str, target_label: str):
        """Traduit une cellule et propose de remplacer soit la cellule elle-meme, soit
        la colonne correspondant a la langue cible sur la meme ligne si elle existe --
        logique partagee entre le menu contextuel (clic droit -> Traduire vers) et le
        bouton 'Traduire' rapide de la barre d'outils."""
        row = item.row()
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

    def _quick_translate(self):
        """Bouton 'Traduire' de la barre d'outils : traduit directement la selection
        actuelle vers la langue par defaut (Options > 'Langue de traduction par
        defaut...'), sans passer par le sous-menu de choix de langue -- une seule
        cellule utilise le flux normal (avec apercu avant remplacement), plusieurs
        cellules basculent automatiquement sur la traduction en lot avec revue."""
        selected = self.table.selectedItems()
        target_code, target_label = settings.get_default_translation_language()

        if len(selected) > 1:
            self._batch_translate_selection(selected, target_code, target_label)
            return

        item = selected[0] if selected else self.table.currentItem()
        if not item or not item.text().strip():
            QMessageBox.information(self, t("err.missing_field"), t("trans.no_cells_selected"))
            return
        self._translate_single_cell(item, item.text(), target_code, target_label)

    def _batch_translate_selection(self, selected_items: list, target_code: str, target_label: str):
        """Traduit toutes les cellules non vides de la selection vers la langue
        choisie, avec une barre de progression (la memoire de traduction -- voir
        core/translation_memory.py -- rend les repetitions quasi instantanees), puis
        propose une revue avant d'appliquer quoi que ce soit."""
        if not translation.is_available():
            QMessageBox.warning(self, t("trans.unavailable_title"), t("trans.unavailable_msg"))
            return

        candidates = [it for it in selected_items if it.text().strip()]
        if not candidates:
            QMessageBox.information(self, t("err.missing_field"), t("trans.no_cells_selected"))
            return

        from PyQt6.QtWidgets import QProgressDialog
        progress = QProgressDialog(t("trans.translating_progress", done=0, total=len(candidates)),
                                    t("btn.cancel"), 0, len(candidates), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(300)

        items_for_review = []
        source_items = []
        dest_items = []
        for i, it in enumerate(candidates):
            progress.setValue(i)
            progress.setLabelText(t("trans.translating_progress", done=i, total=len(candidates)))
            QApplication.processEvents()
            if progress.wasCanceled():
                break
            header = self.table.horizontalHeaderItem(it.column())
            header_text = header.text() if header else str(it.column())
            key_item = self.table.item(it.row(), 0)
            row_key = key_item.text() if key_item else str(it.row() + 1)
            try:
                translated = translation.translate_text(it.text(), target=target_code)
            except Exception as e:
                translated = f"[{t('trans.error_title')}: {e}]"
            items_for_review.append({
                'label': f"{row_key} / {header_text}",
                'original': it.text(),
                'translated': translated,
            })
            source_items.append(it)
            # Comme pour la traduction cellule par cellule : si une colonne correspond
            # deja a la langue cible, le resultat y va (meme ligne) plutot que
            # d'ecraser la cellule source qui a servi de texte d'origine.
            target_col = self._find_language_column(target_code, target_label)
            if target_col is not None and target_col != it.column():
                dest_item = self.table.item(it.row(), target_col)
                if dest_item is None:
                    dest_item = QTableWidgetItem("")
                    self.table.setItem(it.row(), target_col, dest_item)
                dest_items.append(dest_item)
            else:
                dest_items.append(it)
        progress.setValue(len(candidates))

        if not items_for_review:
            return

        dialog = BatchTranslationReviewDialog(items_for_review, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        accepted = dialog.get_accepted_results()
        if not accepted:
            return

        self._snapshot_undo()
        for idx, final_text in accepted:
            dest_items[idx].setText(final_text)

    def _open_fill_missing_dialog(self):
        """Combler les traductions manquantes : choisit une colonne source (deja
        remplie) et une colonne cible (a completer), scanne TOUT le fichier pour les
        lignes ou la cible est vide mais la source ne l'est pas, traduit, et propose
        une revue avant application -- comme la traduction en lot, mais sur tout le
        fichier plutot que sur une selection."""
        if not translation.is_available():
            QMessageBox.warning(self, t("trans.unavailable_title"), t("trans.unavailable_msg"))
            return
        headers = [self.table.horizontalHeaderItem(c).text() if self.table.horizontalHeaderItem(c) else str(c)
                   for c in range(self.table.columnCount())]
        if len(headers) < 2:
            return

        dialog = FillMissingTranslationsDialog(headers, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        source_col = dialog.source_combo.currentIndex()
        target_col = dialog.target_combo.currentIndex()
        if source_col == target_col:
            return
        target_label = headers[target_col]
        target_code = None
        for label, code in translation.COMMON_LANGUAGES:
            if translation._normalize(label) == translation._normalize(target_label):
                target_code = code
                break
        if target_code is None:
            target_code = target_label  # tente le libelle brut comme code -- deep-translator
                                         # accepte aussi certains noms de langue directement

        missing_rows = []
        for row in range(self.table.rowCount()):
            source_item = self.table.item(row, source_col)
            target_item = self.table.item(row, target_col)
            source_text = source_item.text().strip() if source_item else ""
            target_text = target_item.text().strip() if target_item else ""
            if source_text and not target_text:
                missing_rows.append(row)

        if not missing_rows:
            QMessageBox.information(self, t("trans.fill_missing_title"), t("trans.fill_none_found"))
            return

        from PyQt6.QtWidgets import QProgressDialog
        progress = QProgressDialog(t("trans.fill_found_count", count=len(missing_rows)),
                                    t("btn.cancel"), 0, len(missing_rows), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(300)

        items_for_review = []
        dest_items = []
        for i, row in enumerate(missing_rows):
            progress.setValue(i)
            QApplication.processEvents()
            if progress.wasCanceled():
                break
            key_item = self.table.item(row, 0)
            row_key = key_item.text() if key_item else str(row + 1)
            source_text = self.table.item(row, source_col).text()
            try:
                translated = translation.translate_text(source_text, target=target_code)
            except Exception as e:
                translated = f"[{t('trans.error_title')}: {e}]"
            items_for_review.append({
                'label': row_key,
                'original': source_text,
                'translated': translated,
            })
            dest_item = self.table.item(row, target_col)
            if dest_item is None:
                dest_item = QTableWidgetItem("")
                self.table.setItem(row, target_col, dest_item)
            dest_items.append(dest_item)
        progress.setValue(len(missing_rows))

        if not items_for_review:
            return

        review = BatchTranslationReviewDialog(items_for_review, self)
        if review.exec() != QDialog.DialogCode.Accepted:
            return
        accepted = review.get_accepted_results()
        if not accepted:
            return

        self._snapshot_undo()
        for idx, final_text in accepted:
            dest_items[idx].setText(final_text)
