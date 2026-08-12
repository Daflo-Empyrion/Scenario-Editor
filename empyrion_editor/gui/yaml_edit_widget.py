"""
Editeur de fichier .yaml (playfields Empyrion). Structure imbriquee (contrairement au
CSV/ECF plus "plats"), donc UX differente : arbre de navigation a gauche (cle + apercu
de la valeur), panneau de valeur editable a droite avec bouton "Appliquer" -- plus
adapte a une hierarchie profonde et a des valeurs parfois longues que l'edition directe
en cellule.
"""
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem, QTextEdit,
    QLabel, QLineEdit, QPushButton, QMenu, QMessageBox, QDialog, QInputDialog, QSplitter,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QTreeWidgetItemIterator

from core.yamllite.parser import parse_yaml_file, parse_yaml_text
from core.yamllite.model import YamlDocument, YamlEntry, create_entry, remove_entry
from core import translation, settings
from core.i18n import t
from gui.csv_edit_widget import TranslationResultDialog
from gui.text_tools import open_bbcode_tool


class YamlEditWidget(QWidget):
    """Editeur/visualiseur de fichier .yaml : arbre de navigation, panneau de valeur
    editable a droite (avec bouton Appliquer), traduction et BBCode disponibles sur la
    valeur en cours d'edition."""

    modified_changed = pyqtSignal(bool)
    saved = pyqtSignal()

    def __init__(self, path: Path, editable: bool = True, on_copy_entry=None, on_duplicate_entry=None):
        super().__init__()
        self.path = path
        self.editable = editable
        self.on_copy_entry = on_copy_entry
        self.on_duplicate_entry = on_duplicate_entry
        self.doc: YamlDocument = parse_yaml_file(path)
        self._modified = False
        self._current_entry: Optional[YamlEntry] = None
        self._undo_stack: list = []
        self._undo_max = 20

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)

        mode_text = t("status.editable") if editable else t("status.readonly")
        info_label = QLabel(f"{path.name}  ({mode_text})")
        info_label.setStyleSheet("font-size: 11px; color: gray;")
        layout.addWidget(info_label, 0)

        search_row = QHBoxLayout()
        search_row.setSpacing(4)
        search_row.addWidget(QLabel(t("label.search")))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Cle ou valeur...")
        self.search_box.returnPressed.connect(self._search_next)
        search_row.addWidget(self.search_box)
        self.search_status = QLabel("")
        search_row.addWidget(self.search_status)
        layout.addLayout(search_row, 0)

        if editable:
            toolbar = QHBoxLayout()
            toolbar.setSpacing(4)
            btn_add = QPushButton(t("btn.add_entry"))
            btn_add.clicked.connect(self._add_entry_dialog)
            toolbar.addWidget(btn_add)
            btn_del = QPushButton(t("btn.delete_selected_entry"))
            btn_del.clicked.connect(self._delete_selected_entry)
            toolbar.addWidget(btn_del)
            self.btn_undo = QPushButton(t("btn.undo"))
            self.btn_undo.clicked.connect(self.undo)
            self.btn_undo.setEnabled(False)
            toolbar.addWidget(self.btn_undo)
            btn_save = QPushButton(t("btn.save"))
            btn_save.clicked.connect(self.save)
            toolbar.addWidget(btn_save)
            toolbar.addStretch()
            layout.addLayout(toolbar, 0)
            from PyQt6.QtGui import QKeySequence, QShortcut
            QShortcut(QKeySequence.StandardKey.Undo, self, activated=self.undo)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Cle", "Apercu"])
        self._populate_tree()
        self.tree.itemClicked.connect(self._on_entry_selected)
        if self.on_copy_entry or self.on_duplicate_entry:
            self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.tree.customContextMenuRequested.connect(self._show_tree_context_menu)
        splitter.addWidget(self.tree)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel(t("label.value")))
        self.value_edit = QTextEdit()
        self.value_edit.setEnabled(False)
        self.value_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.value_edit.customContextMenuRequested.connect(self._show_value_context_menu)
        right_layout.addWidget(self.value_edit)
        if editable:
            btn_apply = QPushButton(t("btn.apply_value"))
            btn_apply.clicked.connect(self._apply_value)
            right_layout.addWidget(btn_apply)
        splitter.addWidget(right)

        splitter.setSizes([400, 400])
        layout.addWidget(splitter, 1)

        self._search_matches = []
        self._search_index = -1
        self._search_last_query = ""

    def _set_modified(self, value: bool):
        if value != self._modified:
            self._modified = value
            self.modified_changed.emit(value)

    def is_modified(self) -> bool:
        return self._modified

    def save(self):
        if not self.editable:
            return
        with open(self.path, 'w', encoding='utf-8', newline='') as f:
            f.write(self.doc.render())
        self._set_modified(False)
        self.saved.emit()

    def _snapshot_undo(self):
        """A appeler AVANT toute modification -- sauvegarde l'etat actuel du document
        (texte serialise) pour pouvoir l'annuler."""
        self._undo_stack.append(self.doc.render())
        if len(self._undo_stack) > self._undo_max:
            self._undo_stack.pop(0)
        self.btn_undo.setEnabled(True)

    def undo(self):
        if not self._undo_stack:
            return
        previous_text = self._undo_stack.pop()
        self.doc = parse_yaml_text(previous_text)
        self._current_entry = None
        self.value_edit.clear()
        self.value_edit.setEnabled(False)
        self._populate_tree()
        self._set_modified(True)
        if not self._undo_stack:
            self.btn_undo.setEnabled(False)

    def _populate_tree(self):
        self.tree.clear()
        for node in self.doc.nodes:
            if isinstance(node, YamlEntry):
                self.tree.addTopLevelItem(self._make_item(node))

    def _make_item(self, entry: YamlEntry) -> QTreeWidgetItem:
        label = entry.key if entry.key is not None else ("- " + (entry.value[:30] if entry.value else ""))
        preview = entry.value[:60] if entry.value else ""
        item = QTreeWidgetItem([label or "", preview])
        item.setData(0, Qt.ItemDataRole.UserRole, entry)
        for child in entry.children:
            if isinstance(child, YamlEntry):
                item.addChild(self._make_item(child))
        return item

    def _on_entry_selected(self, item: QTreeWidgetItem, column: int):
        entry = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(entry, YamlEntry):
            return
        self._current_entry = entry
        self.value_edit.blockSignals(True)
        self.value_edit.setPlainText(entry.value)
        self.value_edit.blockSignals(False)
        self.value_edit.setEnabled(self.editable)

    def _get_key_path_for_item(self, item: QTreeWidgetItem) -> list:
        """Chemin des cles ancetres (PAS l'entree elle-meme) menant a cet item -- pour
        savoir ou la reinserer au meme endroit dans un autre document (copie de
        travail)."""
        path = []
        parent = item.parent()
        while parent is not None:
            entry = parent.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(entry, YamlEntry) and entry.key:
                path.insert(0, entry.key)
            parent = parent.parent()
        return path

    def _show_tree_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        entry = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(entry, YamlEntry):
            return
        key_path = self._get_key_path_for_item(item)
        label = entry.key or (entry.value[:30] if entry.value else "?")

        menu = QMenu(self)
        action_copy = None
        if self.on_copy_entry:
            action_copy = menu.addAction(f"Copier cette entree ({label}) vers la copie de travail")
        action_dup = None
        if self.on_duplicate_entry:
            action_dup = menu.addAction(t("yaml.duplicate_action"))

        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if action_copy and chosen == action_copy:
            self.on_copy_entry(entry, key_path)
        elif action_dup and chosen == action_dup:
            self.on_duplicate_entry(entry, key_path)

    def _refresh_current_item_preview(self):
        it = QTreeWidgetItemIterator(self.tree)
        while it.value():
            item = it.value()
            if item.data(0, Qt.ItemDataRole.UserRole) is self._current_entry:
                item.setText(1, self._current_entry.value[:60] if self._current_entry.value else "")
                return
            it += 1

    def _apply_value(self):
        if not self._current_entry:
            return
        new_value = self.value_edit.toPlainText()
        if new_value != self._current_entry.value:
            self._snapshot_undo()
            old_value = self._current_entry.value
            self._current_entry.set_own_value(new_value)
            if settings.get_annotations_enabled():
                author = settings.get_author()
                note = f"# original: {old_value} -- Mod par {author}"
                if self._current_entry.comment:
                    self._current_entry.comment = self._current_entry.comment + "  " + note
                else:
                    self._current_entry.comment = note
                self._current_entry.dirty = True
            self._set_modified(True)
            self._refresh_current_item_preview()

    def _search_next(self):
        query = self.search_box.text().strip().lower()
        if not query:
            return
        if not self._search_matches or self._search_last_query != query:
            self._search_matches = []
            it = QTreeWidgetItemIterator(self.tree)
            while it.value():
                item = it.value()
                entry = item.data(0, Qt.ItemDataRole.UserRole)
                searchable = (item.text(0) + " " + item.text(1)).lower()
                if isinstance(entry, YamlEntry) and entry.value:
                    searchable += " " + entry.value.lower()
                if query in searchable:
                    self._search_matches.append(item)
                it += 1
            self._search_index = -1
            self._search_last_query = query

        if not self._search_matches:
            self.search_status.setText("Aucun resultat")
            return
        self._search_index = (self._search_index + 1) % len(self._search_matches)
        item = self._search_matches[self._search_index]
        self.tree.setCurrentItem(item)
        self.tree.scrollToItem(item)
        self._on_entry_selected(item, 0)
        self.search_status.setText(f"{self._search_index + 1} / {len(self._search_matches)}")

    def _add_entry_dialog(self):
        key, ok = QInputDialog.getText(self, t("yaml.add_entry_title"), t("yaml.key_label"))
        if not ok:
            return
        value, ok = QInputDialog.getText(self, t("yaml.add_entry_title"), t("yaml.value_label"))
        if not ok:
            return

        parent_entry = self._current_entry
        target_list = parent_entry.children if parent_entry else self.doc.nodes
        indent = (parent_entry.indent + "  ") if parent_entry else ""
        self._snapshot_undo()
        new_entry = create_entry(key.strip() or None, value.strip(), indent=indent)
        if settings.get_annotations_enabled():
            author = settings.get_author()
            new_entry.comment = f"# Ajoute par {author}"
        target_list.append(new_entry)
        self._set_modified(True)
        self._populate_tree()

    def _delete_selected_entry(self):
        if not self._current_entry:
            QMessageBox.information(self, t("yaml.no_selection_title"), t("yaml.no_selection_msg"))
            return
        confirm = QMessageBox.question(self, t("merge.confirm_title"),
                                        t("yaml.confirm_delete", name=self._current_entry.key or self._current_entry.value))
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._snapshot_undo()
        remove_entry(self.doc.nodes, self._current_entry)
        self._current_entry = None
        self.value_edit.clear()
        self.value_edit.setEnabled(False)
        self._set_modified(True)
        self._populate_tree()

    def _show_value_context_menu(self, pos):
        menu = self.value_edit.createStandardContextMenu()
        if not self.editable or not self._current_entry:
            menu.exec(self.value_edit.viewport().mapToGlobal(pos))
            return

        cursor = self.value_edit.textCursor()
        selected = cursor.selectedText().replace('\u2029', '\n')

        lang_actions = {}
        action_bbcode = None
        if selected.strip():
            menu.addSeparator()
            translate_menu = menu.addMenu(t("ctx.translate_selection_to"))
            for label, code in translation.COMMON_LANGUAGES:
                a = translate_menu.addAction(label)
                lang_actions[a] = code
            action_bbcode = menu.addAction(t("ctx.bbcode"))

        chosen = menu.exec(self.value_edit.viewport().mapToGlobal(pos))

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
