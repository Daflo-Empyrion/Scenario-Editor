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
Widget d'edition CSV (tableau) pour la copie de travail, avec traduction par clic
droit (Google Translate via deep-translator) directement sur une cellule.
"""
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QLabel,
    QPushButton, QMenu, QMessageBox, QDialog, QLineEdit, QComboBox,
    QApplication,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QBrush

from core.csv_handler import CsvHandler, CsvDocument, render_csv
from core import vanilla_memory
from core.translation import find_language_aliases, _normalize, repair_mojibake
from core import translation, settings, translation_memory
from core.i18n import t
from core.csv_column_glossary import get_csv_column_tooltip
from gui.theme import icon, icon_size
from gui.text_tools import (
    copy_selection, cut_selection, paste_into_selection, delete_selection, delete_selected_rows,
    install_clipboard_shortcuts, add_clipboard_menu_actions, open_bbcode_tool,
)
from gui.csv_dialogs import (
    TranslationResultDialog, BatchTranslationReviewDialog,
    FillMissingTranslationsDialog, FindReplaceDialog,
)

COLOR_MODIFIED_CELL = QBrush(QColor(255, 250, 200))
# ECF-003 : le texte herite du theme (clair sur fond noir en theme sombre)
# devenait ILLISIBLE sur le jaune pale. Avant-plan brun fonce pose avec chaque
# surlignage => lisible sur les deux familles de themes.
FOREGROUND_MODIFIED = QBrush(QColor(74, 54, 0))


def mark_modified(item, column: int = None):
    """Surlignage de modification cohérent : fond jaune pale + avant-plan
    sombre, quelle que soit la famille de thème. `column=None` pour un
    QTableWidgetItem (une colonne implicite), sinon un QTreeWidgetItem."""
    if column is None:
        item.setBackground(COLOR_MODIFIED_CELL)
        item.setForeground(FOREGROUND_MODIFIED)
    else:
        item.setBackground(column, COLOR_MODIFIED_CELL)
        item.setForeground(column, FOREGROUND_MODIFIED)


# Traduction issue de la localisation officielle (vanille) : vert pale
# distinct du jaune 'modifie' -- demande 17/09/2026.
COLOR_VANILLA_CELL = QBrush(QColor(228, 243, 232))
FOREGROUND_VANILLA = QBrush(QColor(24, 66, 40))


def mark_vanilla(item):
    """Cellule traduite avec la localisation officielle Eleon (memoire
    vanille) : fond vert pale + avant-plan vert fonce lisible sur les deux
    familles de themes."""
    item.setBackground(COLOR_VANILLA_CELL)
    item.setForeground(FOREGROUND_VANILLA)


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
        self._batch_worker = None  # traduction en lot en cours (ref forte : sinon le GC tue le QThread en vol)
        self._highlighted_keys: set = set()  # cles CSV modifiees en memoire par l'editeur PDA

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
            # Presse-papiers en barre (demande 12/09/2026) : les memes actions
            # que le menu contextuel de cellule, accessibles d'un clic.
            btn_copy = QPushButton(icon("fa5s.copy", "#4a7dfc"), t("btn.clipboard_copy"))
            btn_copy.setIconSize(icon_size())
            btn_copy.setObjectName("secondaryButton")
            btn_copy.clicked.connect(lambda: copy_selection(self.table))
            toolbar.addWidget(btn_copy)
            btn_cut = QPushButton(icon("fa5s.cut", "#4a7dfc"), t("btn.clipboard_cut"))
            btn_cut.setIconSize(icon_size())
            btn_cut.setObjectName("secondaryButton")
            btn_cut.clicked.connect(self._do_cut)
            toolbar.addWidget(btn_cut)
            btn_paste = QPushButton(icon("fa5s.paste", "#4a7dfc"), t("btn.clipboard_paste"))
            btn_paste.setIconSize(icon_size())
            btn_paste.setObjectName("secondaryButton")
            btn_paste.clicked.connect(self._do_paste)
            toolbar.addWidget(btn_paste)
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
            btn_spellcheck = QPushButton(icon("fa5s.spell-check", "#4a7dfc"), t("btn.spellcheck"))
            btn_spellcheck.setIconSize(icon_size())
            btn_spellcheck.setObjectName("secondaryButton")
            btn_spellcheck.clicked.connect(self._open_spellcheck_menu)
            toolbar.addWidget(btn_spellcheck)
            # Revision persistable (17/09/2026) : visible seulement si une
            # revision interrompue existe pour ce fichier (refresh a l'ouverture
            # et apres chaque sauvegarde/application de la revue).
            self.btn_resume_review = QPushButton(icon("fa5s.history", "#4a7dfc"),
                                                 t("btn.resume_review"))
            self.btn_resume_review.setIconSize(icon_size())
            self.btn_resume_review.setObjectName("secondaryButton")
            self.btn_resume_review.setToolTip(t("btn.resume_review_tooltip"))
            self.btn_resume_review.clicked.connect(
                lambda checked=False: self._resume_any_session())
            self.btn_resume_review.setVisible(False)
            toolbar.addWidget(self.btn_resume_review)
            btn_find_replace = QPushButton(icon("fa5s.exchange-alt", "#4a7dfc"), t("btn.find_replace"))
            btn_find_replace.setIconSize(icon_size())
            btn_find_replace.setObjectName("secondaryButton")
            btn_find_replace.clicked.connect(self._open_find_replace_dialog)
            toolbar.addWidget(btn_find_replace)
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
            # Infobulles d'en-tete de colonne (apparition apres une courte pause
            # du curseur, comportement standard Qt) -- coherentes avec le format
            # REEL des fichiers CSV de ce projet (KEY + colonnes de langues, voir
            # core/csv_column_glossary.py).
            for col_idx, col_name in enumerate(self.doc.header):
                tooltip = get_csv_column_tooltip(col_name)
                if tooltip:
                    header_item = self.table.horizontalHeaderItem(col_idx)
                    if header_item:
                        header_item.setToolTip(tooltip)
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
            # Pas de QShortcut Undo ici : gere par le raccourci UNIQUE de la
            # fenetre principale (main_window._global_undo) -- un doublon le
            # rendrait ambigu (CSV-010).
        layout.addWidget(self.table, 1)
        # Proposition de reprise apres la construction (jamais un dialogue
        # modal pendant __init__) : lit la session de revision du fichier.
        if editable:
            QTimer.singleShot(0, self._offer_review_resume)

    def _populate_table(self):
        """Remplit la table depuis self.doc.rows -- redimensionne D'ABORD la
        table sur len(self.doc.rows) (setRowCount) avant de placer les
        cellules. BUG CORRIGE (confirme sur un vrai PDA.csv utilisateur,
        9268 lignes) : sans ce redimensionnement, quand self.doc.rows est
        agrandi APRES la creation initiale de la table (ex: nouvelles lignes
        ajoutees par PdaMissionDialog via core.pda_mission.add_pda_text_entries,
        puis cette methode rappelee), QTableWidget.setItem() sur des index de
        ligne au-dela de l'ancien rowCount() ne fait RIEN silencieusement --
        les nouvelles lignes n'apparaissent jamais dans la table. Pire :
        save()/_get_content_for_autosave() appellent ensuite
        _sync_doc_from_table(), qui ne relit que range(self.table.rowCount())
        -- l'ancien compte -- et ECRASE self.doc.rows en perdant les lignes
        ajoutees, avant meme l'export vers le fichier reel. Resultat observe
        en jeu : la mission PDA nouvellement creee affiche son jeton brut
        (pda_XXXX) au lieu du texte, le fichier PDA.csv sur disque ne
        contenant jamais les nouvelles entrees malgre un 'Enregistrer'
        explicite sur cet onglet."""
        if self.table.rowCount() != len(self.doc.rows):
            self.table.setRowCount(len(self.doc.rows))
        self.table.blockSignals(True)
        for r, row in enumerate(self.doc.rows):
            for c in range(self.table.columnCount()):
                val = row[c] if c < len(row) else ""
                self.table.setItem(r, c, QTableWidgetItem(val))
        self.table.blockSignals(False)
        self._apply_row_highlights()
        self._apply_vanilla_highlights()

    def _apply_vanilla_highlights(self):
        """Colore en vert les cellules cibles dont le contenu est
        EXACTEMENT la traduction officielle Eleon (memoire vanille) --
        au CHARGEMENT du fichier : les couleurs ne sont pas persistees
        dans le CSV, sans ceci le vert disparaissait a chaque
        reouverture (retour 19/09/2026). Couvre aussi les cellules
        traduites par le passe dont la traduction validee coincide avec
        la vanille. Signaux bloques pendant la coloration (setBackground
        declenche itemChanged -> jaune 'modifie')."""
        target_code, _label = settings.get_default_translation_language()
        if target_code != "fr":
            return  # la memoire vanille n'est generee qu'en EN->FR
        header = self.doc.header or []
        en_col = fr_col = None
        en_aliases = set(find_language_aliases("en", "English"))
        fr_aliases = set(find_language_aliases("fr", "Francais"))
        for i, name in enumerate(header):
            norm = _normalize(repair_mojibake(name.strip()))
            if en_col is None and norm in en_aliases:
                en_col = i
            elif fr_col is None and norm in fr_aliases:
                fr_col = i
        if en_col is None or fr_col is None:
            return
        # TOUTES les paires vanille en memoire UNE fois (9 267 lignes x
        # vanilla_matches = 158 s mesurees sinon -- lenteur generale vecue
        # 19/09/2026) ; par ligne, ce ne sont plus que des acces dict.
        pairs = vanilla_memory.vanilla_pairs("fr")
        if not pairs:
            return
        self.table.blockSignals(True)
        try:
            for r, row in enumerate(self.doc.rows):
                src = row[en_col] if en_col < len(row) else ""
                dst = row[fr_col] if fr_col < len(row) else ""
                if not src.strip() or not dst.strip():
                    continue
                official = pairs.get(" ".join(src.split()))
                if official is not None \
                        and " ".join(dst.split()) == official:
                    item = self.table.item(r, fr_col)
                    if item is not None:
                        mark_vanilla(item)
                        item.setToolTip(t("trans.vanilla_cell_tooltip"))
        finally:
            self.table.blockSignals(False)

    def highlight_touched_rows(self, keys: set):
        """Surligne les lignes dont la KEY est dans `keys` -- jetons crees ou
        modifies EN MEMOIRE par l'editeur PDA (core/pda/model.py) ; rend
        visible ce qui a change dans PDA.csv sans parcourir 9000 lignes.
        Reapplique automatiquement par _populate_table()."""
        if not keys:
            return
        self._highlighted_keys = {k.strip() for k in keys}
        self._apply_row_highlights()

    def _apply_row_highlights(self):
        if not self._highlighted_keys:
            return
        for r, row in enumerate(self.doc.rows):
            if row and row[0].strip() in self._highlighted_keys:
                for c in range(self.table.columnCount()):
                    item = self.table.item(r, c)
                    if item is not None:
                        mark_modified(item)

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
            from core.fsutil import atomic_write_text
            atomic_write_text(self.path, rendered)
        except OSError as e:
            QMessageBox.critical(self, t("save.error_title"),
                                  t("save.error_msg", name=self.path.name, error=str(e)))
            return
        self._set_modified(False)
        self.saved.emit()

    def _get_content_for_autosave(self) -> str:
        """Voir core/autosave.py -- meme raisonnement que
        EcfEditWidget._get_content_for_autosave()."""
        if not self.editable:
            return render_csv(self.doc)
        self._sync_doc_from_table()
        return render_csv(self.doc)

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
        mark_modified(item)
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
        insensible aux accents et a la casse (voir core.translation.find_language_aliases).
        L'en-tete est AUSSI compare apres reparation mojibake : les scenarios d'origine
        russe (Atlantis, RE2) contiennent des en-tetes 'FranГ§ais' (UTF-8 decode par
        erreur en CP1251) qui masquaient la colonne FR -- la traduction ecrasait alors
        la cellule source au lieu de remplir la colonne française (bug vecu 12/09/2026)."""
        aliases = translation.find_language_aliases(target_code, target_label)
        for c in range(self.table.columnCount()):
            header_item = self.table.horizontalHeaderItem(c)
            if not header_item:
                continue
            header_text = header_item.text().strip()
            if translation._normalize(header_text) in aliases:
                return c
            repaired = translation._normalize(translation.repair_mojibake(header_text))
            if repaired != translation._normalize(header_text) and repaired in aliases:
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
        action_spell = None
        if item and text.strip():
            translate_menu = menu.addMenu(t("ctx.translate_to"))
            for label, code in translation.COMMON_LANGUAGES:
                a = translate_menu.addAction(label)
                lang_actions[a] = (code, label)
            action_bbcode = menu.addAction(t("ctx.bbcode"))
            action_spell = menu.addAction(t("spellcheck.cell_action"))

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

        if action_spell is not None and chosen == action_spell:
            self._run_spellcheck("cell")
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
            QMessageBox.warning(self, t("trans.unavailable_title"), t("trans.unavailable_msg", error=translation.get_import_error()))
            return
        try:
            translated, src = translation.translate_text_with_source(
                text, target=target_code)
        except Exception as e:
            QMessageBox.critical(self, t("trans.error_title"), t("trans.error_msg", error=e))
            return

        # Correction grammaticale Grammalecte AVANT l'apercu (demande du
        # 12/09/2026) : l'utilisateur valide une version deja corrigee, qui
        # alimente ensuite memoire/glossaire a l'application.
        from core import spellcheck as _sp
        translated, _fixed = _sp.auto_fix(translated)

        target_col = self._find_language_column(target_code, target_label)
        dest_label = None
        destination_warning = None
        if target_col is not None and target_col != item.column():
            header = self.table.horizontalHeaderItem(target_col)
            dest_label = f"la colonne '{header.text() if header else target_label}' (meme ligne)"
        elif target_col is None:
            # Colonne de la langue cible introuvable dans l'en-tete (inexistante,
            # non standard ou mojibake) : le remplacement va dans la cellule
            # d'origine -- a annoncer EXPLICITEMENT dans le dialogue, sinon
            # l'utilisateur croit a un bug (vecu 12/09/2026).
            destination_warning = t("trans.no_target_column", lang=target_label)

        dialog = TranslationResultDialog(text, translated, self, destination_label=dest_label,
                                         destination_warning=destination_warning)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.accepted_replace:
            return
        result_text = dialog.result_text()

        self._snapshot_undo()
        if result_text == text:
            # Le moteur n'a rien traduit (identique a l'original) : a annoncer
            # dans le dialogue, ne jamais faire croire a une traduction (vecu
            # 12/09/2026 avec Argos avant le fix fragments).
            QMessageBox.information(self, t("trans.dialog_title"),
                                    t("trans.engine_no_change", lang=target_label))
        # Memoire + glossaire alimentes a la VALIDATION seulement (demande du
        # 12/09/2026) : une cellule validee et courte devient une entree de
        # glossaire, toutes vont en memoire de traduction.
        from core import glossary
        translation_memory.store(text, "auto", target_code, result_text)
        if glossary.auto_feed_ok(text):
            glossary.add_entry(text, result_text, target=target_code)
        if target_col is not None and target_col != item.column():
            dest_item = self.table.item(row, target_col)
            if dest_item is None:
                dest_item = QTableWidgetItem("")
                self.table.setItem(row, target_col, dest_item)
            dest_item.setText(result_text)
            if src == "vanilla":
                self.table.blockSignals(True)
                try:
                    mark_vanilla(dest_item)
                    dest_item.setToolTip(t("trans.vanilla_cell_tooltip"))
                finally:
                    self.table.blockSignals(False)
        else:
            # Pas de colonne correspondant a cette langue trouvee dans l'en-tete ->
            # on remplace la cellule d'origine par defaut, comme avant.
            item.setText(result_text)
            if src == "vanilla":
                self.table.blockSignals(True)
                try:
                    mark_vanilla(item)
                    item.setToolTip(t("trans.vanilla_cell_tooltip"))
                finally:
                    self.table.blockSignals(False)

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

    # ------------------------------------------------------------------
    # Correcteur orthographe/grammaire (Grammalecte) + detection de texte
    # encore en anglais -- aide a la traduction phase 2 (12/09/2026).
    # ------------------------------------------------------------------
    def _open_spellcheck_menu(self):
        menu = QMenu(self)
        item = self.table.currentItem()
        action_cell = menu.addAction(t("spellcheck.scope_cell"))
        # bool() obligatoire : 'and' retourne le str de item.text().strip()
        # quand il n'est pas vide -> TypeError dans setEnabled (vecu reel).
        action_cell.setEnabled(item is not None and bool(item.text().strip()))
        action_column = menu.addAction(t("spellcheck.scope_column"))
        action_file = menu.addAction(t("spellcheck.scope_file"))
        chosen = menu.exec(self.cursor().pos())
        if chosen == action_cell:
            self._run_spellcheck("cell")
        elif chosen == action_column:
            self._run_spellcheck("column")
        elif chosen == action_file:
            self._run_spellcheck("file")

    def _french_columns(self) -> list:
        """Colonnes dont l'en-tete designe le francais (tolerant mojibake,
        meme reconnaissance que la traduction)."""
        from core.translation import find_language_aliases, _normalize, repair_mojibake
        aliases = find_language_aliases("fr", "Francais")
        cols = []
        for c in range(self.table.columnCount()):
            header = self.table.horizontalHeaderItem(c)
            if not header:
                continue
            ht = header.text().strip()
            if _normalize(ht) in aliases:
                cols.append(c)
            else:
                repaired = _normalize(repair_mojibake(ht))
                if repaired != _normalize(ht) and repaired in aliases:
                    cols.append(c)
        return cols

    def _row_key(self, row: int) -> str:
        key_item = self.table.item(row, 0)
        return key_item.text() if key_item else str(row + 1)

    def _header_language_code(self, col: Optional[int]) -> str:
        """Code de langue d'une colonne d'apres son en-tete ('en', 'fr'...),
        tolerant mojibake ; 'auto' si non reconnu (index memoire par defaut)."""
        from core.translation import COMMON_LANGUAGES, _normalize, repair_mojibake
        if col is None or col < 0:
            return "auto"
        header = self.table.horizontalHeaderItem(col)
        if not header:
            return "auto"
        ht = _normalize(repair_mojibake(header.text().strip()))
        for label, code in translation.COMMON_LANGUAGES:
            if ht in translation.find_language_aliases(code, label):
                return code
        return "auto"

    def _collect_spellcheck_targets(self, scope: str) -> list:
        """[(row, col, key, text)] des cellules non vides selon le scope."""
        targets = []
        if scope == "cell":
            item = self.table.currentItem()
            if item and item.text().strip():
                targets.append((item.row(), item.column(),
                                self._row_key(item.row()), item.text()))
            return targets
        col_filter = None if scope == "file" else self.table.currentColumn()
        for r in range(self.table.rowCount()):
            for c in range(self.table.columnCount()):
                if col_filter is not None and c != col_filter:
                    continue
                it = self.table.item(r, c)
                if it and it.text().strip():
                    targets.append((r, c, self._row_key(r), it.text()))
        return targets

    def _run_spellcheck(self, scope: str) -> None:
        """Scan (Grammalecte + detection EN sur les colonnes francaises) puis
        revue cochable et application des corrections."""
        from core import spellcheck as sp
        from core import lang_detect
        from core.translation import find_language_aliases, _normalize, repair_mojibake
        from gui.busy import run_long

        if not sp.is_available():
            answer = QMessageBox.question(
                self, t("spellcheck.title"),
                t("spellcheck.not_installed", version=sp.GRAMMALECTE_VERSION),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if answer == QMessageBox.StandardButton.Yes:
                run_long(self, sp.download_and_install, "busy.downloading")
            return

        targets = self._collect_spellcheck_targets(scope)
        fr_cols = set(self._french_columns())

        def _scan():
            found = []
            for row, col, key, text in targets:
                for iss in sp.check_text(text):
                    iss.update({"row": row, "col": col, "key": key,
                                "cell_text": text, "is_lang": False})
                    found.append(iss)
            # Detection "encore en anglais" : uniquement sur les colonnes
            # francaises (les colonnes sources EN sont supposement voulues).
            for row, col, key, text in targets:
                if col in fr_cols and lang_detect.is_likely_english(text):
                    found.append({"row": row, "col": col, "key": key,
                                  "cell_text": text, "start": 0, "end": 0,
                                  "orig": "", "s_type": "lang",
                                  "message": "", "suggestions": [],
                                  "is_lang": True})
            return found

        issues = run_long(self, _scan)

        if not issues:
            QMessageBox.information(self, t("spellcheck.title"), t("spellcheck.no_issues"))
            return
        issues.sort(key=lambda i: (i["row"], i["col"]))
        scope_label = {"cell": t("spellcheck.scope_cell"),
                       "column": t("spellcheck.scope_column"),
                       "file": t("spellcheck.scope_file")}[scope]
        self._open_spellcheck_review(issues, scope_label)

    def _make_spell_applier(self):
        """Callback on_apply_batch de la revue Grammalecte : applique les
        corrections cochees cellule par cellule (du plus grand offset au plus
        petit, comme l'ancien flux tout-ou-rien) et retourne le texte final de
        chaque cellule touchee -- la revue ajuste alors les offsets des lignes
        restantes de ces cellules."""
        def apply(pairs):
            self._snapshot_undo()
            by_cell: dict = {}
            for issue, choice in pairs:
                issue["chosen"] = choice
                by_cell.setdefault((issue["row"], issue["col"]), []).append(issue)
            new_texts = {}
            for (row, col), cell_issues in by_cell.items():
                item = self.table.item(row, col)
                if item is None:
                    continue
                text = item.text()
                for iss in sorted(cell_issues, key=lambda i: i["start"], reverse=True):
                    if 0 <= iss["start"] < iss["end"] <= len(text):
                        text = text[:iss["start"]] + iss["chosen"] + text[iss["end"]:]
                item.setText(text)
                new_texts[(row, col)] = text
            self._set_modified(True)
            return new_texts
        return apply

    def _open_spellcheck_review(self, issues: list, scope_label: str):
        """Ouvre la revue Grammalecte en mode revision persistable (demande du
        17/09/2026 : controler plusieurs milliers de corrections se fait en
        plusieurs fois) -- application au fil de l'eau + sauvegarde/reprise."""
        from core import review_session
        from gui.spellcheck_dialog import SpellcheckReviewDialog
        dialog = SpellcheckReviewDialog(
            issues, self, scope_label=scope_label,
            on_apply_batch=self._make_spell_applier(),
            on_save_session=lambda state: review_session.save_session(
                self.path, {'items': state}, kind='spellcheck'))
        dialog.exec()
        if dialog.remaining() == 0:
            review_session.delete_session(self.path, kind='spellcheck')
        self._refresh_review_resume_btn()

    def _resume_spellcheck_session(self, data: Optional[dict] = None):
        """Reprend une correction orthographique interrompue : les issues dont
        la cellule n'a pas change depuis la sauvegarde sont restaurees a
        l'identique (coches + choix conserves) ; celles dont la cellule a
        evolue sont re-scannees sur le texte courant (offsets frais)."""
        from core import review_session
        from core import lang_detect
        from core import spellcheck as sp
        if data is None:
            data = review_session.load_session(self.path, kind='spellcheck')
        if not data:
            return
        items = data.get('items') or []
        if not items:
            return
        by_key: dict = {}
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 0)
            key = it.text() if it else str(r + 1)
            by_key.setdefault(key, []).append(r)
        saved_by_cell: dict = {}
        missing = 0
        for saved in items:
            rows = by_key.get(saved.get('row_key', ''))
            col = saved.get('col')
            if not rows or not isinstance(col, int) \
                    or not (0 <= col < self.table.columnCount()):
                missing += 1
                continue
            row = rows.pop(0)
            saved_by_cell.setdefault((row, col), []).append(saved)
        issues = []
        fr_cols = set(self._french_columns())
        for (row, col), saved_list in saved_by_cell.items():
            item = self.table.item(row, col)
            text = item.text() if item else ""
            if all(s.get('cell_text') == text for s in saved_list):
                # cellule intacte : restauration exacte
                for s in saved_list:
                    s['row'], s['col'] = row, col
                    s['key'] = self._row_key(row)
                    issues.append(s)
                continue
            # cellule modifiee depuis la sauvegarde : re-scan de la cellule
            for iss in sp.check_text(text):
                iss.update({'row': row, 'col': col,
                            'key': self._row_key(row), 'cell_text': text,
                            'is_lang': False})
                issues.append(iss)
            if col in fr_cols and text and lang_detect.is_likely_english(text):
                issues.append({'row': row, 'col': col,
                               'key': self._row_key(row), 'cell_text': text,
                               'start': 0, 'end': 0, 'orig': '',
                               's_type': 'lang', 'message': '',
                               'suggestions': [], 'is_lang': True})
        issues.sort(key=lambda i: (i['row'], i['col']))
        if missing:
            self.search_status.setText(t("trans.review_resumed_missing", count=missing))
        if not issues:
            review_session.delete_session(self.path, kind='spellcheck')
            self._refresh_review_resume_btn()
            return
        self._open_spellcheck_review(issues, t("spellcheck.scope_file"))

    def _batch_translate_selection(self, selected_items: list, target_code: str, target_label: str):
        """Traduit toutes les cellules non vides de la selection vers la langue
        choisie, avec une barre de progression (la memoire de traduction -- voir
        core/translation_memory.py -- rend les repetitions quasi instantanees), puis
        propose une revue avant d'appliquer quoi que ce soit."""
        if not translation.is_available():
            QMessageBox.warning(self, t("trans.unavailable_title"), t("trans.unavailable_msg", error=translation.get_import_error()))
            return

        candidates = [it for it in selected_items if it.text().strip()]
        if not candidates:
            QMessageBox.information(self, t("err.missing_field"), t("trans.no_cells_selected"))
            return

        # ---- Phase 1 (thread interface, rapide) : planification ----
        # Toute lecture/ecriture de la table a lieu ICI, AVANT le demarrage du
        # worker -- le thread de traduction ne touche jamais a aucun widget. La
        # barre de progression etant modale, la table ne peut pas changer pendant
        # le lot. Comme pour la traduction cellule par cellule : si une colonne
        # correspond deja a la langue cible, le resultat y va (meme ligne) plutot
        # que d'ecraser la cellule source qui a servi de texte d'origine.
        target_col = self._find_language_column(target_code, target_label)
        source_code = self._header_language_code(
            self.table.currentColumn() if self.table.currentColumn() >= 0 else None)
        plan = []
        for it in candidates:
            header = self.table.horizontalHeaderItem(it.column())
            header_text = header.text() if header else str(it.column())
            key_item = self.table.item(it.row(), 0)
            row_key = key_item.text() if key_item else str(it.row() + 1)
            if target_col is not None and target_col != it.column():
                dst_col = target_col
                dest_item = self.table.item(it.row(), target_col)
                if dest_item is None:
                    dest_item = QTableWidgetItem("")
                    self.table.setItem(it.row(), target_col, dest_item)
            else:
                dst_col = it.column()
                dest_item = it
            plan.append({'label': f"{row_key} / {header_text}",
                         'original': it.text(), 'dest_item': dest_item,
                         'target_code': target_code, 'source_code': source_code,
                         # Identification durable pour la session de revision
                         # (jamais l'index de ligne : l'ordre peut changer entre
                         # deux ouvertures du fichier).
                         'row_key': row_key, 'src_col': it.column(),
                         'dst_col': dst_col, 'header': header_text})

        self._run_batch_translation(
            [p['original'] for p in plan], target_code,
            lambda i, n: t("trans.translating_progress", done=i, total=n),
            lambda results, stopped_by_failures, consecutive_failures, processed:
                self._finish_batch_review(
                    plan, results, stopped_by_failures, consecutive_failures, processed))

    def _run_batch_translation(self, texts: list, target_code: str, progress_text,
                               on_finished):
        """Traduit `texts` via le worker d'arriere-plan (gui/translation_worker.py)
        avec une barre de progression modale -- l'interface reste entierement
        fluide, plus aucun processEvents ni gel pendant chaque requete Google.

        A la fin (liste terminee OU arret demande), appelle
        on_finished(results, stopped_by_failures, consecutive_failures, processed)
        sur le thread interface : results[i] decrit le sort du i-eme texte (None
        si jamais traite -- les None ne peuvent etre qu'en QUEUE, le worker
        traitant dans l'ordre) ; processed = nombre de resultats en prefixe."""
        from PyQt6.QtWidgets import QProgressDialog
        from gui.translation_worker import BatchTranslationWorker

        if self._batch_worker is not None and self._batch_worker.isRunning():
            QMessageBox.information(self, t("err.title"), t("trans.batch_already_running"))
            return

        progress = QProgressDialog(progress_text(0, len(texts)),
                                   t("btn.cancel"), 0, len(texts), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(300)

        results = [None] * len(texts)
        state = {'consecutive_failures': 0, 'stopped_by_failures': False}
        MAX_CONSECUTIVE_FAILURES = 5
        # Correction Grammalecte de chaque traduction DANS le thread worker
        # (jamais de gel interface) -- la revue affiche la version corrigee.
        from core import spellcheck as _spellcheck
        worker = BatchTranslationWorker(texts, target_code, parent=self,
                                        autofix=_spellcheck.is_available())
        self._batch_worker = worker

        def _on_progress(index, total):
            progress.setValue(index)
            label = progress_text(index, total)
            if settings.get_translation_engine() == "groq":
                # Compteur de limites du tier gratuit Groq (demande du
                # 18/09/2026) : requetes/tokens restants d'apres les
                # en-tetes de la derniere reponse (vide pour les autres
                # moteurs).
                from core import groq_provider
                label += groq_provider.limits_text()
            # Bascule automatique (v1.10.0) : rendre VISIBLE le moteur de
            # secours qui sert reellement ("" tant que le principal tient).
            from core import translation as _tr
            note = _tr.last_fallback_note()
            if note:
                label += "  -- " + note
            progress.setLabelText(label)

        def _on_item_done(index, translated, error, source=""):
            failed = bool(error)
            results[index] = {
                'translated': translated if not failed else f"[{t('trans.error_title')}: {error}]",
                'failed': failed,
                'source': source,
            }
            if failed:
                state['consecutive_failures'] += 1
                # Arret automatique si le service semble en panne -- sans ca, un
                # gros lot martelerait un service indisponible pendant des heures
                # (comportement identique a l'ancienne boucle synchrone).
                if state['consecutive_failures'] >= MAX_CONSECUTIVE_FAILURES:
                    state['stopped_by_failures'] = True
                    worker.stop()
            else:
                state['consecutive_failures'] = 0

        def _on_finished():
            progress.cancel()
            worker.deleteLater()
            if self._batch_worker is worker:
                self._batch_worker = None
            processed = 0
            for r in results:  # les None ne peuvent etre qu'en queue (traitement ordonne)
                if r is None:
                    break
                processed += 1
            on_finished(results, state['stopped_by_failures'],
                        state['consecutive_failures'], processed)

        worker.progress.connect(_on_progress)
        worker.item_done.connect(_on_item_done)
        worker.finished_all.connect(_on_finished)
        progress.canceled.connect(worker.stop)
        worker.start()

    def _finish_batch_review(self, plan: list, results: list, stopped_by_failures: bool,
                             consecutive_failures: int, processed: int):
        """Suite commune des lots de traduction : avertissement d'arret anticipe,
        puis fenetre de revue en mode revision persistable (application au fil
        de l'eau + sauvegarde/reprise -- demande du 17/09/2026 : controler
        plusieurs milliers de lignes se fait en plusieurs fois). `plan` est
        parallele a `results` ; les resultats non traites (queue de la liste)
        sont simplement ignores."""
        if stopped_by_failures and processed:
            QMessageBox.warning(
                self, t("trans.batch_stopped_early_title"),
                t("trans.batch_stopped_early_msg", failed=consecutive_failures,
                  done=processed, remaining=len(plan) - processed))

        if not processed:
            return

        metas = []
        for i in range(processed):
            metas.append({**{k: plan[i].get(k) for k in
                             ('row_key', 'src_col', 'dst_col', 'header',
                              'target_code', 'source_code')},
                          'plan_idx': i,
                          'failed': results[i]['failed'],
                          'translated': results[i]['translated'],
                          'source': results[i].get('source', '')})
        self._open_review_dialog(plan[:processed], metas)

    def _open_review_dialog(self, plan: list, metas: list):
        """Ouvre la revue de revision (BatchTranslationReviewDialog en mode
        persistable) : chaque lot coche est applique immediatement, l'etat
        restant peut etre sauvegarde pour reprendre a la prochaine ouverture
        du fichier. `metas` est parallele a `plan` et porte l'identification
        durable des destinations + failed/translated (et checked a la reprise)."""
        from core import review_session
        items_for_review = [{
            'label': m.get('label', plan[i]['label']),
            'original': m.get('original', plan[i]['original']),
            'translated': m['translated'],
            'failed': m['failed'],
            'source': m.get('source', ''),
            **({'checked': m['checked']} if 'checked' in m else {}),
        } for i, m in enumerate(metas)]
        dialog = BatchTranslationReviewDialog(
            items_for_review, self, metas=metas,
            on_apply_batch=self._make_review_applier(plan),
            on_save_session=lambda state: review_session.save_session(
                self.path, {'items': state}))
        dialog.exec()
        if dialog.remaining() == 0:
            review_session.delete_session(self.path)
        self._refresh_review_resume_btn()

    def _make_review_applier(self, plan: list):
        """Callback on_apply_batch de la revue : ecrit les textes valides dans
        les destinations et alimente memoire/glossaire a CHAQUE lot (la memoire
        est alimentee a la validation -- demande du 12/09/2026 ; en revision
        persistable, validation = chaque lot coche, d'ou des snapshots undo
        par lot aussi)."""
        def apply(results):
            self._snapshot_undo()
            from core import glossary
            for meta, final_text in results:
                p = plan[meta['plan_idx']]
                p['dest_item'].setText(final_text)
                if meta.get('source') == 'vanilla':
                    # Traduction officielle Eleon : cellule distinguishable
                    # (demande 17/09/2026). Signaux bloques pendant la
                    # coloration : setBackground declenche itemChanged ->
                    # mark_modified ecraserait le vert par le jaune 'modifie'.
                    self.table.blockSignals(True)
                    try:
                        mark_vanilla(p['dest_item'])
                        p['dest_item'].setToolTip(t("trans.vanilla_cell_tooltip"))
                    finally:
                        self.table.blockSignals(False)
                translation_memory.store(p['original'], p.get('source_code', 'auto'),
                                         p.get('target_code', 'auto'), final_text)
                if glossary.auto_feed_ok(p['original']):
                    glossary.add_entry(p['original'], final_text,
                                       target=p.get('target_code', 'auto'))
            self._set_modified(True)
        return apply

    def _refresh_review_resume_btn(self):
        """Bouton 'Reprendre la revision' visible seulement si une session
        (traduction OU correction orthographique) existe pour ce fichier."""
        from core import review_session
        pending = self._pending_review_kinds()
        self.btn_resume_review.setVisible(bool(pending))
        return pending[0][1] if pending else None

    def _pending_review_kinds(self) -> list:
        """[(kind, data)] des revisions interrompues du fichier."""
        from core import review_session
        kinds = []
        for kind in ('translation', 'spellcheck'):
            d = review_session.load_session(self.path, kind=kind)
            if d:
                kinds.append((kind, d))
        return kinds

    def _offer_review_resume(self):
        """Au chargement d'un CSV : proposer la reprise d'une revision
        interrompue (traduction et/ou correction orthographique)."""
        if not self.editable:
            return
        self._refresh_review_resume_btn()
        kinds = self._pending_review_kinds()
        if not kinds:
            return
        if len(kinds) == 1:
            self._ask_resume_review(kinds[0][0])
            return
        # les deux : un menu plutot qu'une boite arbitraire
        menu = QMenu(self)
        a_trad = menu.addAction(t("btn.resume_review"))
        a_spell = menu.addAction(t("btn.resume_spellcheck"))
        chosen = menu.exec(self.cursor().pos())
        if chosen is a_trad:
            self._ask_resume_review('translation')
        elif chosen is a_spell:
            self._ask_resume_review('spellcheck')

    def _ask_resume_review(self, kind: str):
        """Boite Reprendre / Plus tard / Supprimer pour une revision."""
        from core import review_session
        data = review_session.load_session(self.path, kind=kind)
        if not data:
            return
        msg_key = ("trans.review_resume_msg" if kind == 'translation'
                   else "trans.review_resume_spell_msg")
        box = QMessageBox(self)
        box.setWindowTitle(t("trans.review_resume_title"))
        box.setText(t(msg_key, count=len(data['items']), name=self.path.name))
        btn_resume = box.addButton(t("trans.review_resume_btn"),
                                   QMessageBox.ButtonRole.AcceptRole)
        box.addButton(t("trans.review_later_btn"), QMessageBox.ButtonRole.RejectRole)
        btn_delete = box.addButton(t("trans.review_delete_btn"),
                                   QMessageBox.ButtonRole.DestructiveRole)
        box.exec()
        if box.clickedButton() is btn_resume:
            if kind == 'translation':
                self._resume_review_session(data)
            else:
                self._resume_spellcheck_session(data)
        elif box.clickedButton() is btn_delete:
            review_session.delete_session(self.path, kind=kind)
            self._refresh_review_resume_btn()

    def _resume_any_session(self):
        """Slot du bouton barre : reprise directe si une seule revision en
        attente, menu de choix sinon."""
        kinds = self._pending_review_kinds()
        if not kinds:
            return
        if len(kinds) == 1:
            kind = kinds[0][0]
        else:
            menu = QMenu(self)
            a_trad = menu.addAction(t("btn.resume_review"))
            a_spell = menu.addAction(t("btn.resume_spellcheck"))
            chosen = menu.exec(self.cursor().pos())
            if chosen not in (a_trad, a_spell):
                return
            kind = 'translation' if chosen is a_trad else 'spellcheck'
        if kind == 'translation':
            self._resume_review_session()
        else:
            self._resume_spellcheck_session()

    def _resume_review_session(self, data: Optional[dict] = None):
        """Reprend une revision interrompue : retrouve la destination de chaque
        ligne restante par sa cle (colonne 0) et ses colonnes source/destination
        persistees (JAMAIS l'index de ligne), puis rouvre la revue a l'etat
        sauvegarde (coches + corrections manuelles conserves)."""
        from core import review_session
        if data is None:
            data = review_session.load_session(self.path)
        if not data:
            return
        items = data.get('items') or []
        if not items:
            return
        by_key: dict = {}
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 0)
            key = it.text() if it else str(r + 1)
            by_key.setdefault(key, []).append(r)
        plan, metas = [], []
        missing = 0
        for saved in items:
            rows = by_key.get(saved.get('row_key', ''))
            if not rows:
                missing += 1
                continue
            row = rows.pop(0)
            dst_col = saved.get('dst_col')
            if not isinstance(dst_col, int) or not (0 <= dst_col < self.table.columnCount()):
                dst_col = saved.get('src_col') or 0
            dest_item = self.table.item(row, dst_col)
            if dest_item is None:
                dest_item = QTableWidgetItem("")
                self.table.setItem(row, dst_col, dest_item)
            plan.append({'label': saved.get('label', ''),
                         'original': saved.get('original', ''),
                         'dest_item': dest_item,
                         'source_code': saved.get('source_code', 'auto'),
                         'target_code': saved.get('target_code', 'auto')})
            metas.append({**saved, 'plan_idx': len(plan) - 1})
        if missing:
            self.search_status.setText(t("trans.review_resumed_missing", count=missing))
        if not plan:
            review_session.delete_session(self.path)
            self._refresh_review_resume_btn()
            return
        self._open_review_dialog(plan, metas)

    def _open_fill_missing_dialog(self):
        """Combler les traductions manquantes : choisit une colonne source (deja
        remplie) et une colonne cible (a completer), scanne TOUT le fichier pour les
        lignes ou la cible est vide mais la source ne l'est pas, traduit, et propose
        une revue avant application -- comme la traduction en lot, mais sur tout le
        fichier plutot que sur une selection."""
        if not translation.is_available():
            QMessageBox.warning(self, t("trans.unavailable_title"), t("trans.unavailable_msg", error=translation.get_import_error()))
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

        # Planification cote interface (meme principe que la traduction de
        # selection) : lecture de la table AVANT le demarrage du worker.
        plan = []
        for row in missing_rows:
            key_item = self.table.item(row, 0)
            row_key = key_item.text() if key_item else str(row + 1)
            source_text = self.table.item(row, source_col).text()
            dest_item = self.table.item(row, target_col)
            if dest_item is None:
                dest_item = QTableWidgetItem("")
                self.table.setItem(row, target_col, dest_item)
            plan.append({'label': row_key, 'original': source_text, 'dest_item': dest_item,
                         'target_code': target_code,
                         'source_code': self._header_language_code(source_col),
                         'row_key': row_key, 'src_col': source_col,
                         'dst_col': target_col, 'header': headers[source_col]})

        self._run_batch_translation(
            [p['original'] for p in plan], target_code,
            lambda i, n: t("trans.fill_found_count", count=n),
            lambda results, stopped_by_failures, consecutive_failures, processed:
                self._finish_batch_review(
                    plan, results, stopped_by_failures, consecutive_failures, processed))

    def _open_find_replace_dialog(self):
        """Recherche/remplacement avec revue individuelle -- utile par exemple pour
        corriger a la volee une traduction automatique repetee sur plusieurs lignes
        (ex: 'Dos' utilise a tort pour 'Back' au sens de 'Retour'), sans avoir a
        remplacer chaque cellule a la main ni a tout ecraser en aveugle."""
        import re as _re
        headers = [self.table.horizontalHeaderItem(c).text() if self.table.horizontalHeaderItem(c) else str(c)
                   for c in range(self.table.columnCount())]
        dialog = FindReplaceDialog(headers, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        find_text = dialog.find_edit.text()
        replace_text = dialog.replace_edit.text()
        scope_col = dialog.column_combo.currentData()
        case_sensitive = dialog.case_sensitive_check.isChecked()
        whole_word = dialog.whole_word_check.isChecked()

        flags = 0 if case_sensitive else _re.IGNORECASE
        pattern_text = _re.escape(find_text)
        if whole_word:
            pattern_text = r'\b' + pattern_text + r'\b'
        try:
            pattern = _re.compile(pattern_text, flags)
        except _re.error:
            return

        columns = [scope_col] if scope_col is not None else list(range(self.table.columnCount()))
        items_for_review = []
        dest_items = []
        for row in range(self.table.rowCount()):
            key_item = self.table.item(row, 0)
            row_key = key_item.text() if key_item else str(row + 1)
            for col in columns:
                cell = self.table.item(row, col)
                if cell is None or not cell.text():
                    continue
                if not pattern.search(cell.text()):
                    continue
                new_text = pattern.sub(replace_text, cell.text())
                header = self.table.horizontalHeaderItem(col)
                header_text = header.text() if header else str(col)
                items_for_review.append({
                    'label': f"{row_key} / {header_text}",
                    'original': cell.text(),
                    'translated': new_text,
                })
                dest_items.append(cell)

        if not items_for_review:
            QMessageBox.information(self, t("csv.find_replace_title"), t("csv.find_replace_none_found"))
            return

        review = BatchTranslationReviewDialog(
            items_for_review, self,
            title=t("csv.find_replace_review_title"),
            intro=t("csv.find_replace_review_intro"),
            translated_column_label=t("csv.col_after_replace"),
        )
        if review.exec() != QDialog.DialogCode.Accepted:
            return
        accepted = review.get_accepted_results()
        if not accepted:
            return

        self._snapshot_undo()
        for idx, final_text in accepted:
            dest_items[idx].setText(final_text)
