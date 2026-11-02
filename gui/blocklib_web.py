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

"""Bibliotheque de blocs en vue web (chantier webapp, 02/11) : la page
gui/web/blocklib/index.html remplace le dialogue Qt (conserve en repli).
La logique metier (insertion, export, suppression confirmee) est partagee
avec le dialogue Qt (fonctions module de gui/block_library_dialog.py) — le
pont ne fait que la rejouer, les boites natives (confirmation, choix du
fichier/bloc) s'ouvrent cote Python et dialog_policy les rend non modales.

Tests : pont seul (tests/test_blocklib_web.py), jamais de QWebEngineView
reel sous offscreen.
"""
import json
from pathlib import Path

from PyQt6.QtCore import pyqtSlot

from core import block_library
from core.i18n import t
from gui.web_dialog import WebBridge, WebDialog

WEB_DIR = Path(__file__).resolve().parent / "web" / "blocklib"

_AVAILABLE = None  # cache du test d'import (None = pas encore teste)


def is_available() -> bool:
    global _AVAILABLE
    if _AVAILABLE is None:
        try:
            from PyQt6.QtWebChannel import QWebChannel  # noqa: F401
            from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
            _AVAILABLE = (WEB_DIR / "index.html").is_file()
        except Exception:
            _AVAILABLE = False
    return _AVAILABLE


class BlocklibWebBridge(WebBridge):
    """Pont de la page bibliotheque : liste des extraits, apercu, insertion
    / suppression / export par les fonctions PARTAGEES du module Qt."""

    def __init__(self, main_window, dialog=None, parent=None):
        super().__init__(parent)
        self._mw = main_window
        self._dialog = dialog
        self._paths: list = []
        self._selected = -1
        self._preview = ""

    def _payload(self) -> str:
        snippets = block_library.list_snippets()
        self._paths = [s["path"] for s in snippets]
        if self._selected >= len(self._paths):
            self._selected = -1
            self._preview = ""
        return json.dumps({
            "snippets": [{"name": s["name"], "path": s["path"]}
                         for s in snippets],
            "selected": self._selected,
            "preview": self._preview,
            "labels": {
                "hint": t("lib.hint"),
                "search": t("lib.search"),
                "insert": t("lib.insert"),
                "delete": t("lib.delete"),
                "export": t("lib.export"),
                "refresh": t("lib.refresh"),
                "info": t("module.info"),
            },
        }, ensure_ascii=False)

    def push_reset(self) -> None:
        self.data_changed.emit(self._payload())

    @pyqtSlot(result=str)
    def get_init(self) -> str:
        return self._payload()

    @pyqtSlot(int)
    def select(self, idx: int) -> None:
        """Selection d'un extrait : l'apercu charge le texte brut (comme
        _on_selected du dialogue Qt)."""
        if not (0 <= idx < len(self._paths)):
            return
        self._selected = idx
        self._preview = block_library.load_snippet(self._paths[idx])
        self.data_changed.emit(json.dumps(
            {"selected": self._selected, "preview": self._preview},
            ensure_ascii=False))

    # -- actions (liste blanche) ------------------------------------------
    def _insert(self):
        if 0 <= self._selected < len(self._paths):
            from gui.block_library_dialog import insert_snippet
            insert_snippet(self._mw, self._paths[self._selected],
                           self._dialog)
            self.push_reset()

    def _delete(self):
        if not (0 <= self._selected < len(self._paths)):
            return
        from gui.block_library_dialog import delete_snippet_confirmed
        if delete_snippet_confirmed(self._dialog, self._paths[self._selected]):
            self._selected = -1
            self._preview = ""
            self.push_reset()

    def _export(self):
        from gui.block_library_dialog import export_block
        export_block(self._mw, self._dialog)
        self.push_reset()

    def _info(self):
        from gui.module_info import show_module_info
        show_module_info(self._dialog, "blocklib.info_html")

    def _close(self):
        if self._dialog is not None:
            self._dialog.reject()

    _ACTIONS = {"insert": "_insert", "delete": "_delete",
                "export": "_export", "refresh": "push_reset",
                "info": "_info", "close": "_close"}

    @pyqtSlot(str)
    def run_action(self, name: str) -> None:
        method = self._ACTIONS.get(name)
        if method is not None:
            getattr(self, method)()


class BlocklibWebDialog(WebDialog):
    WEB_DIR = WEB_DIR
    DIALOG_KEY = "block_library"   # meme cle que le dialogue Qt : geometrie
    BRIDGE_FACTORY = staticmethod(
        lambda dialog: BlocklibWebBridge(dialog.main_window, dialog, dialog))

    def __init__(self, main_window, parent=None):
        self.main_window = main_window
        self.setWindowTitle(t("lib.title"))
        self.resize(760, 520)
        super().__init__(parent)
