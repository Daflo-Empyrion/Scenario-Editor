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

"""Controle BBCode en vue web (chantier webapp, tranche 3, 02/11) : la page
gui/web/bbcode/index.html remplace le tableau QTableWidget du dialogue Qt
(gui/bbcode_check_dialog.py, conserve en repli si WebEngine manque).

REPARTITION STRICTE (meme parti pris que csv_web_view) :
  - la logique reste dans core/bbcode_check.py (check_table) et le widget
    CsvEditWidget reste la source de verite (apply_bbcode_fixes) ;
  - la page ne fait AUCUN acces fichier : rapports demandes au pont,
    edition « Apres » et cases a cocher renvoyees au pont ;
  - les regles d'applicabilite (case cochee, bouton Appliquer) vivent ICI
    en Python — jamais en JS — pour rester testeables.

Tests : pont seul (tests/test_bbcode_web.py) ; le rendu Chromium ne l'est
pas (un QWebEngineView reel sous offscreen bloque, piege verifie 31/10).
"""
from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import pyqtSlot

from core.bbcode_check import check_table, language_columns, source_column
from core.fsutil import central_backup
from core.i18n import t
from gui.bbcode_check_dialog import _KIND_KEYS
from gui.msgboxes import info
from gui.web_dialog import WebBridge, WebDialog

WEB_DIR = Path(__file__).resolve().parent / "web" / "bbcode"

_AVAILABLE = None  # cache du test d'import (None = pas encore teste)


def is_available() -> bool:
    """Page possible : WebEngine importable et page presente (meme garde
    que csv_web_view.is_available)."""
    global _AVAILABLE
    if _AVAILABLE is None:
        try:
            from PyQt6.QtWebChannel import QWebChannel  # noqa: F401
            from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
            _AVAILABLE = (WEB_DIR / "index.html").is_file()
        except Exception:
            _AVAILABLE = False
    return _AVAILABLE


class BbcodeWebBridge(WebBridge):
    """Pont de la page BBCode : rapports (get_reports), edition « Apres »
    (set_after), cases (set_checked), actions (select_all / apply / close).

    Etat : self._edited (texte « Apres » saisi) et self._checked (case) —
    par defaut une ligne reparable est cochee, exactement comme le
    dialogue Qt ; le texte saisi remplace toujours la proposition calculee.
    """

    def __init__(self, widget, dialog=None, parent=None):
        super().__init__(parent)
        self._widget = widget
        self._dialog = dialog
        self._reports = []    # [(ligne, colonne, CellReport)], trie comme Qt
        self._edited: dict[int, str] = {}
        self._checked: dict[int, bool] = {}
        self._payload = "{}"

    # -- regles d'applicabilite (une seule source : Python) -------------
    def _after(self, idx: int, report) -> str:
        return self._edited.get(idx, report.after)

    def _applicable(self, idx: int, report) -> bool:
        text = self._after(idx, report)
        return bool(text.strip()) and text != report.before

    def _is_checked(self, idx: int, report) -> bool:
        return self._checked.get(idx, report.repairable)

    # -- etats pousses a la page ----------------------------------------
    def _full_payload(self, rows, header, source, col: int) -> str:
        cols = language_columns(header)
        scope = [{"col": c, "name": header[c] if c < len(header) else str(c)}
                 for c in cols if c != source]
        out = []
        for idx, (r, c, report) in enumerate(self._reports):
            source_text = rows[r][source] if source < len(rows[r]) else ""
            out.append({
                "idx": idx,
                "line": r + 2,          # +1 entete, +1 base 1 (comme Qt)
                "col": c,
                "col_name": header[c] if c < len(header) else str(c),
                "kinds": ", ".join(t(_KIND_KEYS[k]) for k in report.kinds),
                "details": report.details,
                "source": source_text,
                "before": report.before,
                "after": report.after,
                "repairable": report.repairable,
                "applicable": self._applicable(idx, report),
                "checked": self._is_checked(idx, report)
                           and self._applicable(idx, report),
            })
        repairable = sum(1 for row in out if row["repairable"])
        apply_enabled = any(row["checked"] for row in out)
        return json.dumps({
            "labels": {
                "scope_label": t("bbcheck.scope_label"),
                "scope_all": t("bbcheck.scope_all"),
                "col_line": t("bbcheck.col_line"),
                "col_column": t("bbcheck.col_column"),
                "col_problem": t("bbcheck.col_problem"),
                "col_source": t("bbcheck.col_source"),
                "col_before": t("bbcheck.col_before"),
                "col_after": t("bbcheck.col_after"),
                "select_all": t("bbcheck.select_all"),
                "apply": t("bbcheck.apply"),
                "close": t("bbcheck.close"),
                "not_repairable": t("bbcheck.not_repairable"),
                "columns_tooltip": t("bbcheck.columns_tooltip"),
                "source_tooltip": t("bbcheck.source_tooltip"),
                "after_tooltip": t("bbcheck.after_tooltip"),
                "found": t("bbcheck.found", n=len(out), fixable=repairable),
            },
            "scope": scope,
            "col": col,              # colonne resolue (-1 = toutes)
            "rows": out,
            "apply_enabled": apply_enabled,
        }, ensure_ascii=False)

    def _state(self) -> str:
        """Etat LEGER apres une edition/case (jamais le payload complet :
        5 000 rapports x textes seraient repousses a chaque clic)."""
        checked = {}
        applicable = {}
        for idx, (_r, _c, report) in enumerate(self._reports):
            checked[str(idx)] = self._is_checked(idx, report) \
                and self._applicable(idx, report)
            applicable[str(idx)] = self._applicable(idx, report)
        apply_enabled = any(checked.values())
        return json.dumps({"checked": checked, "applicable": applicable,
                           "apply_enabled": apply_enabled})

    def _push_state(self) -> None:
        self.data_changed.emit(self._state())

    def push_reset(self) -> None:
        """Re-pousse le dernier payload complet par le CANAL (signal) —
        jamais runJavaScript : autre monde JS (piege verifie deux fois)."""
        self.data_changed.emit(self._payload)

    # -- slots de la page ------------------------------------------------
    @pyqtSlot(int, result=str)
    def get_reports(self, col: int) -> str:
        """Controle des colonnes de langue. col >= 0 : cette colonne seule ;
        -1 : toutes ; -2 : preselection du dialogue (colonne courante de
        l'editeur si c'est une langue controlee)."""
        rows = self._widget._snapshot_table()
        header = self._widget.doc.header or [str(i) for i in range(len(rows[0]) if rows else 0)]
        if col == -2:
            current = self._widget.table.currentColumn()
            cols = language_columns(header)
            source = source_column(header, cols)
            col = current if current in cols and current != source else -1
        if not rows:
            self._reports = []
            self._payload = self._full_payload(rows, header, 0, col)
            return self._payload
        only = [col] if col >= 0 else None
        reports, source, _cols = check_table(rows, header, only=only)
        # reparables d'abord : ce sur quoi l'utilisateur peut agir (comme Qt)
        reports.sort(key=lambda item: (not item[2].repairable, item[0], item[1]))
        self._reports = reports
        self._edited = {}
        self._checked = {}
        self._payload = self._full_payload(rows, header, source, col)
        return self._payload

    @pyqtSlot(int, str)
    def set_after(self, idx: int, text: str) -> None:
        """Edition « Apres » depuis la page : le texte SAISI remplace la
        proposition ; une saisie exploitable coche la ligne (regle du
        dialogue Qt, y compris sur une ligne non reparable)."""
        if not (0 <= idx < len(self._reports)):
            return
        self._edited[idx] = text
        report = self._reports[idx][2]
        self._checked[idx] = self._applicable(idx, report)
        self._push_state()

    @pyqtSlot(int, bool)
    def set_checked(self, idx: int, on: bool) -> None:
        if 0 <= idx < len(self._reports):
            self._checked[idx] = bool(on)
            self._push_state()

    # -- actions (liste blanche, meme forme que CsvWebBridge) -----------
    _ACTIONS = {"select_all": "_select_all", "apply": "_apply",
                "close": "_close"}

    @pyqtSlot(str)
    def run_action(self, name: str) -> None:
        method = self._ACTIONS.get(name)
        if method is not None:
            getattr(self, method)()

    def _select_all(self):
        for idx, (_r, _c, report) in enumerate(self._reports):
            if self._applicable(idx, report):
                self._checked[idx] = True
        self._push_state()

    def _checked_fixes(self) -> list:
        fixes = []
        for idx, (r, c, report) in enumerate(self._reports):
            if not self._is_checked(idx, report):
                continue
            text = self._after(idx, report)
            if not text.strip() or text == report.before:
                continue          # aucune correction a ecrire
            fixes.append((r, c, text))
        return fixes

    def _apply(self):
        fixes = self._checked_fixes()
        box_parent = self._dialog if self._dialog is not None else self._widget
        if not fixes:
            info(box_parent, t("bbcheck.title"), t("bbcheck.nothing_selected"))
            return
        path = Path(self._widget.path)
        try:
            # sauvegarde CENTRALISEE : jamais un .bak a cote du fichier, il
            # partirait dans l'archive Workshop du scenario
            backup = central_backup(path, kind="localization") \
                if path.exists() else None
            self._widget.apply_bbcode_fixes(fixes)
        except OSError as e:
            info(box_parent, t("bbcheck.title"),
                 t("bbcheck.error", error=str(e)))
            return
        if self._dialog is not None:
            self._dialog.accept()
        info(box_parent, t("bbcheck.title"),
             t("bbcheck.applied", n=len(fixes),
               backup=backup.name if backup else "-"))

    def _close(self):
        if self._dialog is not None:
            self._dialog.reject()


class BbcodeWebDialog(WebDialog):
    """Fenetre du controle BBCode en vue web (gabarit gui/web_dialog.py)."""

    WEB_DIR = WEB_DIR
    DIALOG_KEY = "bbcode_check"   # meme cle que le dialogue Qt : geometrie partagee
    BRIDGE_FACTORY = staticmethod(
        lambda dialog: BbcodeWebBridge(dialog._widget, dialog, dialog))

    def __init__(self, widget, parent=None):
        self._widget = widget
        self.setWindowTitle(t("bbcheck.title"))
        self.resize(1240, 700)
        super().__init__(parent)
