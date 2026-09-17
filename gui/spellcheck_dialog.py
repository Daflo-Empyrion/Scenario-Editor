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
Revue des corrections orthographe/grammaire + anomalies de langue (look
Relief compatible) : meme philosophie que la revue de traduction -- RIEN
n'est applique sans cochage explicite.

Lignes du tableau :
  - une erreur Grammalecte (orthographe, confusion, typographie) avec une
    QComboBox de suggestions ; pre-cochee pour les types surs (typo, conf) ;
  - une anomalie "texte encore en anglais" (detecteur core/lang_detect.py)
    : INFORMATIONNEL, non cochable -- la correction passe par le bouton
    Traduire de la barre d'outils.

"Ignorer ce mot partout" alimente le lexique persistant
(~/.empyrion_editor/spell_ignore.json, via core.spellcheck).
"""
from typing import List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QHBoxLayout, QHeaderView, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QComboBox,
)

from core.i18n import t
from core import spellcheck

NO_FIX = "(none)"  # marqueur interne du combo : ne pas corriger

# Types Grammalecte consideres comme SURES (pre-coches) : le GRAMMATICAL
# (accords, conjugaisons, confusions de mots...). Les regles typographiques
# (typo : points de suspension, signes) restent proposees NON cochees --
# le jeu utilise volontairement '...' et l'apostrophe droite (apos/nbsp/esp
# sont desactivees dans le moteur, voir core/spellcheck.py).
_SAFE_TYPES = {"conf", "conj", "ppas", "gn", "infi", "vmode", "imp",
               "inte", "loc", "tu", "bs", "date"}

COL_CHECK, COL_KEY, COL_CONTEXT, COL_PROBLEM, COL_FIX = 0, 1, 2, 3, 4


class SpellcheckReviewDialog(QDialog):
    """Tableau de revue des corrections proposees. `issues` : liste de dicts
    produits par le scan (voir CsvEditWidget._collect_spellcheck_issues) :
      {'row','col','key','cell_text','start','end','orig','s_type','message',
       'suggestions', 'is_lang'}"""

    def __init__(self, issues: List[dict], parent=None, scope_label: str = ""):
        super().__init__(parent)
        self.setWindowTitle(t("spellcheck.title"))
        self.resize(980, 520)
        self._issues = issues

        layout = QVBoxLayout(self)
        intro = QLabel(t("spellcheck.intro", scope=scope_label, n=len(issues)))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.table = QTableWidget(len(issues), 5)
        self.table.setHorizontalHeaderLabels([
            "", t("spellcheck.col_key"), t("spellcheck.col_context"),
            t("spellcheck.col_problem"), t("spellcheck.col_fix")])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_CHECK, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_KEY, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_CONTEXT, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_PROBLEM, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_FIX, QHeaderView.ResizeMode.Stretch)

        for r, issue in enumerate(issues):
            check = QCheckBox()
            has_fix = bool(issue["suggestions"]) and not issue.get("is_lang")
            if has_fix:
                # pre-coche pour les types surs (faute de frappe, confusion)
                check.setChecked(issue.get("s_type") in _SAFE_TYPES)
            check.setEnabled(has_fix)
            check.toggled.connect(self._update_apply_count)
            self.table.setCellWidget(r, COL_CHECK, check)

            self.table.setItem(r, COL_KEY, QTableWidgetItem(issue["key"]))

            ctx = self._context_snippet(issue)
            item_ctx = QTableWidgetItem(ctx)
            item_ctx.setToolTip(ctx)
            self.table.setItem(r, COL_CONTEXT, item_ctx)

            problem = (t("spellcheck.type_lang") if issue.get("is_lang")
                       else issue["message"])
            self.table.setItem(r, COL_PROBLEM, QTableWidgetItem(problem))

            combo = QComboBox()
            if has_fix:
                combo.addItem(t("spellcheck.no_correction"), NO_FIX)
                for s in issue["suggestions"]:
                    combo.addItem(s, s)
                if check.isChecked() and combo.count() > 1:
                    combo.setCurrentIndex(1)
                check.toggled.connect(combo.setEnabled)
            combo.setEnabled(has_fix and check.isChecked())
            self.table.setCellWidget(r, COL_FIX, combo)

        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        btn_check_all = QPushButton(t("spellcheck.check_all"))
        btn_check_all.clicked.connect(lambda: self._set_all_checks(True))
        buttons.addWidget(btn_check_all)
        btn_uncheck_all = QPushButton(t("spellcheck.uncheck_all"))
        btn_uncheck_all.setObjectName("secondaryButton")
        btn_uncheck_all.clicked.connect(lambda: self._set_all_checks(False))
        buttons.addWidget(btn_uncheck_all)
        btn_ignore_word = QPushButton(t("spellcheck.ignore_word_btn"))
        btn_ignore_word.setObjectName("secondaryButton")
        btn_ignore_word.clicked.connect(self._ignore_current_word)
        buttons.addWidget(btn_ignore_word)
        buttons.addStretch()
        self.btn_apply = QPushButton(t("spellcheck.apply", n=0))
        self.btn_apply.clicked.connect(self.accept)
        buttons.addWidget(self.btn_apply)
        btn_close = QPushButton(t("btn.cancel"))
        btn_close.setObjectName("secondaryButton")
        btn_close.clicked.connect(self.reject)
        buttons.addWidget(btn_close)
        layout.addLayout(buttons)
        self._update_apply_count()

    @staticmethod
    def _context_snippet(issue: dict, width: int = 56) -> str:
        """Extrait du texte de la cellule centre sur l'erreur, ou debut du
        texte pour une anomalie de langue."""
        cell_text = issue["cell_text"]
        if issue.get("is_lang"):
            return cell_text[:width] + ("..." if len(cell_text) > width else "")
        start, end = issue["start"], issue["end"]
        left = max(0, start - 18)
        right = min(len(cell_text), end + 18)
        snippet = cell_text[left:start] + "[" + cell_text[start:end] + "]" \
            + cell_text[end:right]
        prefix = "..." if left > 0 else ""
        suffix = "..." if right < len(cell_text) else ""
        return prefix + snippet.replace("\n", "\\n") + suffix

    def _set_all_checks(self, checked: bool) -> None:
        for r in range(self.table.rowCount()):
            check = self.table.cellWidget(r, COL_CHECK)
            if check is not None and check.isEnabled():
                check.setChecked(checked)

    def _update_apply_count(self) -> None:
        self.btn_apply.setText(t("spellcheck.apply", n=self.checked_issues_count()))

    def _current_issue(self) -> Optional[dict]:
        r = self.table.currentRow()
        return self._issues[r] if 0 <= r < len(self._issues) else None

    def _ignore_current_word(self) -> None:
        issue = self._current_issue()
        if issue is None or not issue.get("orig", "").strip():
            return
        spellcheck.add_ignored_word(issue["orig"])
        # decoche (et retire la correction de) toute ligne du meme mot
        for r, it in enumerate(self._issues):
            if it.get("orig", "").lower() == issue["orig"].lower().strip():
                check = self.table.cellWidget(r, COL_CHECK)
                if check is not None:
                    check.setChecked(False)
                combo = self.table.cellWidget(r, COL_FIX)
                if combo is not None and combo.currentData() != NO_FIX:
                    combo.setCurrentIndex(0)

    def checked_issues_count(self) -> int:
        return sum(1 for r in range(self.table.rowCount())
                   if (w := self.table.cellWidget(r, COL_CHECK)) is not None
                   and w.isChecked())

    def checked_issues(self) -> List[dict]:
        """Issues cochees avec une correction choisie (l'anomalie de langue,
        informationnelle, n'est jamais retournee)."""
        result = []
        for r, issue in enumerate(self._issues):
            check = self.table.cellWidget(r, COL_CHECK)
            combo = self.table.cellWidget(r, COL_FIX)
            if check is None or not check.isChecked():
                continue
            choice = combo.currentData() if combo else None
            if choice and choice != NO_FIX:
                issue["chosen"] = choice
                result.append(issue)
        return result
