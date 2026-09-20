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
Dialogues de traduction et de recherche/remplacement -- extraits de
gui/csv_edit_widget.py (fichier historiquement volumineux, voir audit de code
v1.3.3) pour reduire sa taille. Comportement inchange.

TranslationResultDialog est reutilise par plusieurs autres editeurs (ECF, YAML,
TXT, menu contextuel generique) -- voir gui/translate_context_menu.py. Les 3
autres (BatchTranslationReviewDialog, FillMissingTranslationsDialog,
FindReplaceDialog) restent pour l'instant specifiques a l'editeur CSV.
"""
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton, QDialog,
    QTextEdit, QLineEdit, QComboBox, QCheckBox, QTableWidget, QTableWidgetItem,
    QMessageBox, QMenu,
)

from core.i18n import t
from core import spellcheck as _spellcheck
from gui import theme as _theme


def confirm_review_save(dialog, count: int) -> str:
    """Boite commune aux revues interruptibles (traduction, orthographe) :
    fermer sans rien perdre ? Retourne 'save' (sauvegarder et quitter),
    'discard' (quitter sans sauvegarder) ou 'cancel' (rester ouvert).
    QMessageBox de l'appelant patchable en test (le VRAI bloquerait pytest)."""
    box = QMessageBox(dialog)
    box.setWindowTitle(dialog.windowTitle())
    box.setText(t("trans.review_close_ask", count=count))
    btn_save = box.addButton(t("trans.review_save_quit"),
                             QMessageBox.ButtonRole.AcceptRole)
    box.addButton(t("trans.review_discard_btn"),
                  QMessageBox.ButtonRole.DestructiveRole)
    btn_cancel = box.addButton(t("btn.cancel"), QMessageBox.ButtonRole.RejectRole)
    box.exec()
    if box.clickedButton() is btn_save:
        return "save"
    if box.clickedButton() is btn_cancel:
        return "cancel"
    return "discard"


# Fond des traductions issues de la localisation officielle (vanille) --
# vert pale distinct du jaune 'modifie' et du rouge 'echec'.
VANILLA_COLOR = QColor(228, 243, 232)


class TranslationResultDialog(QDialog):
    """Petite fenetre affichant le resultat d'une traduction, avec le choix de
    remplacer la cellule d'origine (ou une cellule destination precise) ou juste
    copier le resultat."""

    def __init__(self, original: str, translated: str, parent=None,
                 destination_label: Optional[str] = None,
                 destination_warning: Optional[str] = None):
        super().__init__(parent)
        self.setWindowTitle(t("trans.dialog_title"))
        from gui.window_geometry import track
        track(self, "translation_result", default_size=(520, 420))
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

        # Avertissement explicite quand la colonne de la langue cible n'a PAS
        # ete trouvee dans l'en-tete (non standard ou mojibake) : le remplacement
        # se fera dans la cellule d'origine -- ne jamais laisser croire a un bug
        # (retour utilisateur 12/09/2026 : la trad FR avait ecrase la cellule EN
        # sans explication, la cellule FR restant vide).
        if destination_warning:
            warn = QLabel(destination_warning)
            warn.setWordWrap(True)
            warn.setStyleSheet(f"color: {_theme.ORANGE}; font-size: 11px;")
            layout.addWidget(warn)

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
    traduction (modifiable avant validation).

    Mode "revision persistable" (demande 17/09/2026 : controler 5000+ lignes se
    fait en plusieurs fois) : si `on_apply_batch` est fourni, le bouton d'
    application VALIDE les lignes cochees au fil de l'eau (callback) sans fermer
    le dialogue, et "Sauvegarder et quitter"/la fermeture persistent l'etat
    restant via `on_save_session(current_state())`. Sans ces callbacks
    (Rechercher/Remplacer), le comportement historique tout-ou-rien est
    conserve."""

    def __init__(self, items: list, parent=None, title: Optional[str] = None,
                 intro: Optional[str] = None, translated_column_label: Optional[str] = None,
                 metas: Optional[list] = None, on_apply_batch=None,
                 on_save_session=None):
        """items : liste de dicts {'label': str, 'original': str, 'translated': str,
        'failed': bool (optionnel, defaut False), 'checked': bool (optionnel, defaut
        not failed -- etat de coche restaure a la reprise d'une revision)} -- une
        entree 'failed' est affichee decochee par defaut et surlignee en rouge clair,
        pour ne jamais l'appliquer par erreur (ex: le service de traduction a
        echoue/bloque sur cette cellule).

        metas : liste parallele a `items` de dicts libres (row_key, colonnes,
        codes de langue...) maintenus alignes aux lignes courantes du tableau
        et retournes par current_state() -- sert a retrouver les destinations
        a la reprise. on_apply_batch(results) recoit [(meta, texte_final)].

        title/intro/translated_column_label : personnalisation optionnelle du texte
        affiche -- ce dialogue est reutilise tel quel pour Rechercher/Remplacer (voir
        _open_find_replace_dialog), pas seulement pour la traduction."""
        super().__init__(parent)
        self.setWindowTitle(title or t("trans.batch_review_title"))
        self.resize(750, 450)
        from gui.window_geometry import track
        track(self, "batch_review")
        self.on_apply_batch = on_apply_batch
        self.on_save_session = on_save_session
        self.saved_session = False
        self._metas: list = list(metas) if metas else [{} for _ in items]

        layout = QVBoxLayout(self)
        intro_label = QLabel(intro or t("trans.batch_review_intro"))
        intro_label.setWordWrap(True)
        layout.addWidget(intro_label)

        failed_count = sum(1 for it in items if it.get('failed'))
        if failed_count:
            warn = QLabel(t("trans.batch_some_failed", count=failed_count))
            warn.setStyleSheet("color: #b02a2a; font-weight: 600;")
            warn.setWordWrap(True)
            layout.addWidget(warn)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["", t("trans.col_key"), t("trans.col_original"), translated_column_label or t("trans.col_translated")])
        self.table.setRowCount(len(items))
        for i, item in enumerate(items):
            failed = item.get('failed', False)
            checked = item.get('checked', not failed)
            check_item = QTableWidgetItem()
            check_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            check_item.setCheckState(Qt.CheckState.Checked if checked
                                     else Qt.CheckState.Unchecked)
            self.table.setItem(i, 0, check_item)

            key_item = QTableWidgetItem(item['label'])
            key_item.setFlags(key_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 1, key_item)

            orig_item = QTableWidgetItem(item['original'])
            orig_item.setFlags(orig_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 2, orig_item)

            trans_item = QTableWidgetItem(item['translated'])
            if failed:
                trans_item.setBackground(QBrush(QColor(255, 220, 220)))
            elif item.get('source') == 'vanilla':
                # Traduction officielle Eleon (memoire vanille) : distinguishable
                # au premier coup d'oeil (demande 17/09/2026).
                trans_item.setBackground(QBrush(VANILLA_COLOR))
                trans_item.setToolTip(t("trans.vanilla_cell_tooltip"))
            self.table.setItem(i, 3, trans_item)

        # Largeurs FIXES plutot que resizeColumnsToContents() : un texte source long
        # (frequent dans un vrai Localization.csv -- phrases completes, descriptions)
        # ferait sinon deborder la colonne 'Original' sur toute la largeur de la
        # fenetre, poussant la colonne 'Traduction' hors du champ visible (seul un
        # ascenseur horizontal, facile a manquer, permettait alors de la voir). Le
        # retour a la ligne dans les cellules compense en gardant tout le texte
        # visible verticalement.
        self.table.setColumnWidth(0, 30)
        self.table.setColumnWidth(1, 90)
        self.table.setColumnWidth(2, 280)
        self.table.setColumnWidth(3, 280)
        self.table.setWordWrap(True)
        self.table.resizeRowsToContents()
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
        # Correction grammaticale Grammalecte sur les traductions de la revue
        # (demande du 12/09/2026 : corriger les bizarries du moteur AVANT
        # validation, pour que memoire/glossaire recoivent la version propre).
        self._spellcheck_ok = _spellcheck.is_packaged()
        btn_fix_all = QPushButton(t("spellcheck.fix_all_btn"))
        btn_fix_all.setObjectName("secondaryButton")
        btn_fix_all.setEnabled(self._spellcheck_ok)
        btn_fix_all.setToolTip("" if self._spellcheck_ok
                               else t("spellcheck.not_installed_short"))
        btn_fix_all.clicked.connect(self._fix_all)
        btn_row.addWidget(btn_fix_all)
        btn_row.addStretch()
        initial_checked = sum(1 for it in items if it.get('checked', not it.get('failed', False)))
        self.btn_apply = QPushButton(t("trans.apply_checked", count=initial_checked))
        if self.on_apply_batch:
            # Revision persistable : applique les cochees SANS fermer -- le
            # dialogue se vide au fil de l'eau et se ferme seul quand il est vide.
            self.btn_apply.clicked.connect(self._consume_checked)
        else:
            self.btn_apply.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_apply)
        if self.on_save_session:
            btn_save_quit = QPushButton(t("trans.review_save_quit"))
            btn_save_quit.setObjectName("secondaryButton")
            btn_save_quit.clicked.connect(self._save_and_close)
            btn_row.addWidget(btn_save_quit)
        btn_cancel = QPushButton(t("btn.cancel"))
        btn_cancel.setObjectName("secondaryButton")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

        self.table.itemChanged.connect(self._update_apply_count)
        # clic droit sur une ligne : corriger cette ligne seulement
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._row_context_menu)

    def _fix_row(self, row: int) -> bool:
        """Corrige la cellule Traduction de la ligne (Grammalecte). Retourne
        True si le texte a change."""
        trans_item = self.table.item(row, 3)
        if trans_item is None or not trans_item.text().strip():
            return False
        corrected, applied = _spellcheck.auto_fix(trans_item.text())
        if corrected != trans_item.text():
            trans_item.setText(corrected)
            return True
        return False

    def _fix_all(self) -> None:
        from gui.busy import busy_guard
        with busy_guard(self, "spellcheck.correcting"):
            fixed = sum(1 for r in range(self.table.rowCount())
                        if self._fix_row(r))
        if fixed:
            self.table.resizeRowsToContents()

    def _row_context_menu(self, pos) -> None:
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        menu = QMenu(self)
        action = menu.addAction(t("spellcheck.fix_row_btn"))
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen == action and self._fix_row(row):
            self.table.resizeRowsToContents()

    def _set_all_checked(self, checked: bool):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self.table.rowCount()):
            self.table.item(i, 0).setCheckState(state)

    def _update_apply_count(self, item):
        if item.column() == 0:
            self._refresh_apply_text()

    def _refresh_apply_text(self):
        count = sum(1 for i in range(self.table.rowCount())
                    if self.table.item(i, 0).checkState() == Qt.CheckState.Checked)
        self.btn_apply.setText(t("trans.apply_checked", count=count))

    def _consume_checked(self):
        """Mode revision : applique les lignes cochees via on_apply_batch puis
        les retire du tableau (les destinations restent valides : la table
        hote ne change pas pendant la revue). Se ferme seul quand il n'y a
        plus rien a controler."""
        results, rows = [], []
        for r in range(self.table.rowCount()):
            if self.table.item(r, 0).checkState() == Qt.CheckState.Checked:
                results.append((self._metas[r], self.table.item(r, 3).text()))
                rows.append(r)
        if not rows:
            return
        self.on_apply_batch(results)
        for r in reversed(rows):
            self.table.removeRow(r)
            del self._metas[r]
        self._refresh_apply_text()
        if not self.table.rowCount():
            self.accept()

    def current_state(self) -> list:
        """Etat persistable des lignes restantes : meta de chaque ligne
        (row_key, colonnes, codes...) + label/original/traduction/failed/checked
        -- on_save_session l'ecrit tel quel dans la session de revision."""
        state = []
        for r in range(self.table.rowCount()):
            entry = {k: v for k, v in self._metas[r].items()}
            entry.update({
                'label': self.table.item(r, 1).text(),
                'original': self.table.item(r, 2).text(),
                'translated': self.table.item(r, 3).text(),
                'failed': bool(entry.get('failed', False)),
                'checked': self.table.item(r, 0).checkState() == Qt.CheckState.Checked,
            })
            state.append(entry)
        return state

    def remaining(self) -> int:
        return self.table.rowCount()

    def _save_and_close(self):
        if self.on_save_session:
            self.on_save_session(self.current_state())
            self.saved_session = True
        self.accept()

    def reject(self):
        """Fermeture (Annuler, Echap, croix) : sur une revision non vide,
        proposer de sauvegarder pour reprendre plus tard au lieu de tout
        perdre -- la demande d'origine de cette fonctionnalite."""
        if self.on_save_session and self.table.rowCount():
            answer = confirm_review_save(self, self.table.rowCount())
            if answer == "cancel":
                return
            if answer == "save":
                self._save_and_close()
                return
        super().reject()

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
        from gui.window_geometry import track
        track(self, "fill_missing", default_size=(420, 220))

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


class FindReplaceDialog(QDialog):
    """Recherche/remplacement de texte sur une colonne (ou toutes) d'un fichier CSV --
    typiquement utilise pour corriger a la volee une traduction automatique
    approximative repetee sur plusieurs lignes (ex: 'Dos' pour 'Back' quand le sens
    voulu etait 'Retour'). Ne remplace jamais directement : chaque correspondance
    trouvee passe par le meme tableau de revue que la traduction, une par une."""

    def __init__(self, column_headers: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("csv.find_replace_title"))
        from gui.window_geometry import track
        track(self, "find_replace", default_size=(520, 260))

        layout = QFormLayout(self)
        self.find_edit = QLineEdit()
        layout.addRow(t("csv.find_label"), self.find_edit)
        self.replace_edit = QLineEdit()
        layout.addRow(t("csv.replace_label"), self.replace_edit)

        self.column_combo = QComboBox()
        self.column_combo.addItem(t("search.column_all"), None)
        for i, h in enumerate(column_headers):
            self.column_combo.addItem(h, i)
        layout.addRow(t("csv.find_replace_column_label"), self.column_combo)

        self.case_sensitive_check = QCheckBox(t("csv.find_replace_case_sensitive"))
        layout.addRow("", self.case_sensitive_check)
        self.whole_word_check = QCheckBox(t("csv.find_replace_whole_word"))
        layout.addRow("", self.whole_word_check)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton(t("csv.find_replace_search_btn"))
        btn_ok.clicked.connect(self._on_accept)
        btn_row.addWidget(btn_ok)
        btn_cancel = QPushButton(t("btn.cancel"))
        btn_cancel.setObjectName("secondaryButton")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        layout.addRow(btn_row)

    def _on_accept(self):
        if not self.find_edit.text():
            QMessageBox.warning(self, t("err.missing_field"), t("csv.find_replace_empty_search"))
            return
        self.accept()
