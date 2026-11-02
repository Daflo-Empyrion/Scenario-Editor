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

"""Comparateur de bundles Unity en vue web (chantier webapp, 02/11) : la
page gui/web/bundles/index.html remplace le dialogue Qt (conserve en
repli). Moteur : core/unity_bundles.compare_bundles (deja une fonction
module, rien a extraire), comparaison hors thread GUI via async_call,
choix des fichiers et export CSV par QFileDialog natifs cote Python.

Tests : pont seul (tests/test_bundles_web.py), compare_bundles monkeypatche.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWidgets import QFileDialog

from core.i18n import t
from gui.ewa_async import async_call
from gui.web_dialog import WebBridge, WebDialog

WEB_DIR = Path(__file__).resolve().parent / "web" / "bundles"

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


class BundlesWebBridge(WebBridge):
    """Pont de la page bundles : deux chemins, comparaison async, table
    statut/chemin/type A/type B, export CSV."""

    def __init__(self, dialog=None, parent=None):
        super().__init__(parent)
        self._dialog = dialog
        self._paths = {"a": "", "b": ""}
        self._diff = None
        self._rows = []               # [(statut, chemin, type_a, type_b, sev)]
        self._status = ""
        self._running = False

    def _payload(self) -> str:
        return json.dumps({
            "labels": {
                "intro": t("bundles.intro"),
                "path_a": t("bundles.path_a"),
                "path_b": t("bundles.path_b"),
                "path_hint": t("bundles.path_hint"),
                "browse": t("bundles.browse"),
                "compare": t("bundles.compare"),
                "col_status": t("bundles.col_status"),
                "col_path": t("bundles.col_path"),
                "col_type_a": t("bundles.col_type_a"),
                "col_type_b": t("bundles.col_type_b"),
                "export": t("bundles.export"),
                "close": t("btn.close"),
                "info": t("module.info"),
            },
            "paths": self._paths,
            "rows": [{"status": s, "path": p, "ta": ta, "tb": tb,
                      "sev": sev}
                     for s, p, ta, tb, sev in self._rows],
            "status": self._status,
            "running": self._running,
            "export_enabled": bool(self._rows) and not self._running,
        }, ensure_ascii=False)

    def push_reset(self) -> None:
        self.data_changed.emit(self._payload())

    @pyqtSlot(result=str)
    def get_init(self) -> str:
        return self._payload()

    @pyqtSlot(str, str)
    def set_path(self, key: str, path: str) -> None:
        if key in self._paths:
            self._paths[key] = path

    @pyqtSlot(str)
    def browse(self, key: str) -> None:
        if key not in self._paths:      # jamais de dialogue natif sur une
            return                      # cle inconnue venue de la page
        path, _ = QFileDialog.getOpenFileName(
            self._dialog, t("bundles.browse"),
            self._paths.get(key) or ".", t("bundles.filter"))
        if path:
            self._paths[key] = path
            self.push_reset()

    # -- comparaison (meme _compute que le dialogue Qt : ne leve JAMAIS,
    #    l'exception serait un crash natif si relancee dans un slot) ------
    def _compute(self, pa: str, pb: str):
        from core.unity_bundles import compare_bundles
        try:
            return compare_bundles(pa, pb), ""
        except ValueError as e:
            if str(e) == "UnityPy":
                return None, "UnityPy"
            return None, str(e)
        except Exception as e:  # noqa: BLE001 - affiche et continue
            return None, str(e)

    @pyqtSlot()
    def run(self):
        if self._running:
            return
        pa, pb = self._paths["a"].strip(), self._paths["b"].strip()
        if not pa or not pb:
            self._status = t("bundles.need_paths")
            self.push_reset()
            return
        self._running = True
        self._rows = []
        self._diff = None
        self._status = ""
        self.push_reset()
        async_call(self, lambda: self._compute(pa, pb),
                   on_done=self._done, on_fail=self._fail, name="bundles-web")

    def _done(self, result):
        diff, err = result
        self._running = False
        if err:
            self._status = (t("bundles.need_unitypy") if err == "UnityPy"
                            else t("bundles.err_read", err=err))
            self.push_reset()
            return
        self._diff = diff
        self._rows = [(t("bundles.added"), p, "", ty, "added")
                      for p, ty in sorted(diff.added.items())] \
            + [(t("bundles.removed"), p, ty, "", "removed")
               for p, ty in sorted(diff.removed.items())] \
            + [(t("bundles.changed"), p, ta, tb, "changed")
               for p, (ta, tb) in sorted(diff.changed.items())]
        # UnityPy ne leve PAS sur un non-bundle : il rend un container vide
        summary = t("bundles.summary", na=diff.na, nb=diff.nb,
                    added=len(diff.added), removed=len(diff.removed),
                    changed=len(diff.changed), same=diff.same)
        if diff.na == 0 or diff.nb == 0:
            summary = t("bundles.empty") + " " + summary
        self._status = summary
        self.push_reset()

    def _fail(self, exc: Exception):
        self._running = False
        self._status = t("bundles.err_read", err=str(exc))
        self.push_reset()

    @pyqtSlot()
    def export(self):
        if not self._diff:
            return
        default = Path(self._paths["a"].strip()).stem or "bundle"
        path, _ = QFileDialog.getSaveFileName(
            self._dialog, t("bundles.export"), f"{default}_diff.csv",
            "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow([t("bundles.col_status"), t("bundles.col_path"),
                        t("bundles.col_type_a"), t("bundles.col_type_b")])
            for s, p, ta, tb, _sev in self._rows:
                w.writerow([s, p, ta, tb])
        self._status = t("bundles.exported", path=path)
        self.push_reset()

    def _info(self):
        from gui.module_info import show_module_info
        show_module_info(self._dialog, "bundles.info_html")

    def _close(self):
        if self._dialog is not None:
            self._dialog.reject()

    _ACTIONS = {"run": "run", "export": "export", "info": "_info",
                "close": "_close"}

    @pyqtSlot(str)
    def run_action(self, name: str) -> None:
        method = self._ACTIONS.get(name)
        if method is not None:
            getattr(self, method)()


class BundlesWebDialog(WebDialog):
    WEB_DIR = WEB_DIR
    DIALOG_KEY = "bundles"     # meme cle que le dialogue Qt : geometrie
    BRIDGE_FACTORY = staticmethod(
        lambda dialog: BundlesWebBridge(dialog, dialog))

    def __init__(self, parent=None):
        self.setWindowTitle(t("bundles.title"))
        self.resize(900, 580)
        super().__init__(parent)
