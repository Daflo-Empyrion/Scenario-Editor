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

"""Fiche du scenario (digest) en vue web (chantier webapp, tranche 6,
02/11) : la page gui/web/digest/index.html remplace le dialogue Qt
(gui/scenario_digest_dialog.py, conserve en repli si WebEngine manque).

Meme repartition que coherence_web : le moteur reste core/scenario_digest
(collect_digest + render_markdown, deja des fonctions module — rien a
extraire), generation hors thread GUI via async_call, choix de dossier et
export .md par QFileDialog natifs ouverts cote Python. L'aprescu montre
le Markdown BRUT (meme contrat que le QPlainTextEdit du dialogue Qt).
Le bouton info ouvre la VRAIE fenetre « Comprendre le module »
(gui/module_info.show_module_info).

Tests : pont seul (tests/test_digest_web.py), async_call monkeypatche en
synchrone, fixture _scenario de test_scenario_digest.
"""
from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWidgets import QFileDialog

from core.i18n import t
from core.scenario_digest import collect_digest, render_markdown
from core.settings import get_vanilla_content_path
from gui.ewa_async import async_call
from gui.web_dialog import WebBridge, WebDialog

WEB_DIR = Path(__file__).resolve().parent / "web" / "digest"

_AVAILABLE = None  # cache du test d'import (None = pas encore teste)


def is_available() -> bool:
    """Page possible : WebEngine importable et page presente."""
    global _AVAILABLE
    if _AVAILABLE is None:
        try:
            from PyQt6.QtWebChannel import QWebChannel  # noqa: F401
            from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
            _AVAILABLE = (WEB_DIR / "index.html").is_file()
        except Exception:
            _AVAILABLE = False
    return _AVAILABLE


class DigestWebBridge(WebBridge):
    """Pont de la page digest : generation async de la fiche Markdown,
    export .md (QFileDialog cote Python), fenetre info module."""

    def __init__(self, dialog=None, working_root: str = "", parent=None):
        super().__init__(parent)
        self._dialog = dialog
        self._path = working_root or ""
        self._text = ""
        self._running = False
        self._status = ""

    # -- payload -----------------------------------------------------------
    def _payload(self) -> str:
        return json.dumps({
            "labels": {
                "scenario": t("yamlcheck.scenario"),
                "scenario_hint": t("yamlcheck.scenario_hint"),
                "browse": t("yamlcheck.browse"),
                "run": t("digest.run"),
                "export": t("digest.export"),
                "info": t("module.info"),
                "info_tip": t("module.info.tip"),
            },
            "path": self._path,
            "text": self._text,
            "status": self._status,
            "running": self._running,
            "export_enabled": bool(self._text) and not self._running,
        }, ensure_ascii=False)

    def push_reset(self) -> None:
        self.data_changed.emit(self._payload())

    # -- slots ---------------------------------------------------------------
    @pyqtSlot(result=str)
    def get_init(self) -> str:
        """Premier chargement de la page (elle TIRE ses donnees)."""
        return self._payload()

    @pyqtSlot(str)
    def set_path(self, path: str) -> None:
        self._path = path            # la page sait ce qu'elle tape

    @pyqtSlot()
    def browse(self):
        path = QFileDialog.getExistingDirectory(
            self._dialog, t("yamlcheck.scenario"), self._path or ".")
        if path:
            self._path = path
            self.push_reset()

    @pyqtSlot()
    def run(self):
        if self._running:
            return
        root = (self._path or "").strip()
        if not root:
            self._status = t("digest.need_scenario")
            self.push_reset()
            return
        self._running = True
        self._text = ""
        self._status = t("digest.running")
        self.push_reset()
        vanilla = get_vanilla_content_path() or ""
        async_call(self, lambda: render_markdown(collect_digest(Path(root),
                                                                vanilla)),
                   on_done=self._done, on_fail=self._fail,
                   name="scenario-digest-web")

    def _done(self, text: str):
        self._running = False
        self._text = text
        self._status = t("digest.done")
        self.push_reset()

    def _fail(self, exc: BaseException):
        self._running = False
        self._status = t("digest.error", msg=str(exc))
        self.push_reset()

    @pyqtSlot()
    def export(self):
        if not self._text:
            return
        root = Path((self._path or "").strip() or ".")
        default = root / f"{root.name}_fiche.md"
        path, _filter = QFileDialog.getSaveFileName(
            self._dialog, t("digest.save_title"), str(default),
            "Markdown (*.md)")
        if not path:
            return
        try:
            Path(path).write_text(self._text, encoding="utf-8")
        except OSError as exc:
            self._status = t("digest.error", msg=str(exc))
            self.push_reset()
            return
        self._status = t("digest.exported", path=path)
        self.push_reset()

    # -- actions (liste blanche) --------------------------------------------
    def _info(self):
        from gui.module_info import show_module_info
        show_module_info(self._dialog, "digest.info_html")

    def _close(self):
        if self._dialog is not None:
            self._dialog.reject()

    _ACTIONS = {"run": "run", "export": "export", "browse": "browse",
                "info": "_info", "close": "_close"}

    @pyqtSlot(str)
    def run_action(self, name: str) -> None:
        method = self._ACTIONS.get(name)
        if method is not None:
            getattr(self, method)()


class DigestWebDialog(WebDialog):
    """Fenetre de la fiche scenario en vue web (gabarit web_dialog)."""

    WEB_DIR = WEB_DIR
    DIALOG_KEY = "scenario_digest"   # meme cle que le dialogue Qt : geometrie
    BRIDGE_FACTORY = staticmethod(
        lambda dialog: DigestWebBridge(dialog, dialog._working_root, dialog))

    def __init__(self, parent=None, working_root: str = ""):
        self._working_root = working_root or ""
        self.setWindowTitle(t("digest.title"))
        self.resize(950, 680)
        super().__init__(parent)
