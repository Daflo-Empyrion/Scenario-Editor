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
    QMessageBox,
)

from core.i18n import t


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

    def __init__(self, items: list, parent=None, title: Optional[str] = None,
                 intro: Optional[str] = None, translated_column_label: Optional[str] = None):
        """items : liste de dicts {'label': str, 'original': str, 'translated': str,
        'failed': bool (optionnel, defaut False)} -- une entree 'failed' est affichee
        decochee par defaut et surlignee en rouge clair, pour ne jamais l'appliquer
        par erreur (ex: le service de traduction a echoue/bloque sur cette cellule).

        title/intro/translated_column_label : personnalisation optionnelle du texte
        affiche -- ce dialogue est reutilise tel quel pour Rechercher/Remplacer (voir
        _open_find_replace_dialog), pas seulement pour la traduction."""
        super().__init__(parent)
        self.setWindowTitle(title or t("trans.batch_review_title"))
        self.resize(750, 450)

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
            check_item = QTableWidgetItem()
            check_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            check_item.setCheckState(Qt.CheckState.Unchecked if failed else Qt.CheckState.Checked)
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
        btn_row.addStretch()
        initial_checked = sum(1 for it in items if not it.get('failed'))
        self.btn_apply = QPushButton(t("trans.apply_checked", count=initial_checked))
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


class FindReplaceDialog(QDialog):
    """Recherche/remplacement de texte sur une colonne (ou toutes) d'un fichier CSV --
    typiquement utilise pour corriger a la volee une traduction automatique
    approximative repetee sur plusieurs lignes (ex: 'Dos' pour 'Back' quand le sens
    voulu etait 'Retour'). Ne remplace jamais directement : chaque correspondance
    trouvee passe par le meme tableau de revue que la traduction, une par une."""

    def __init__(self, column_headers: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("csv.find_replace_title"))

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
