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

"""Contrôle de cohérence global en vue web (chantier webapp, tranche 4,
02/11) : la page gui/web/coherence/index.html remplace le tableau Qt du
dialogue historique (gui/coherence_dialog.py, conserve en repli si
WebEngine manque).

Meme repartition que bbcode_web : le moteur reste core/coherence_audit.py
(LECTURE SEULE), l'analyse tourne hors du thread GUI via gui.ewa_async
(async_call — le pont QObject est le proprietaire, reponse en signal
queued), la page ne touche aucun fichier (export et choix de dossier pas
les QFileDialog natifs ouverts par le pont). Le tableau n'a que quelques
dizaines de lignes : pas de virtualisation, chaque push est un payload
complet (contrairement au pont BBCode et son etat leger).

Tests : pont seul (tests/test_coherence_web.py), async_call monkeypatche
en synchrone comme dans tests/test_coherence_dialog.py.
"""
from __future__ import annotations

import csv
import datetime
import json
from pathlib import Path

from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWidgets import QFileDialog

from core.coherence_audit import run_coherence_audit
from core.i18n import t
from gui.ewa_async import async_call
from gui.web_dialog import WebBridge, WebDialog

WEB_DIR = Path(__file__).resolve().parent / "web" / "coherence"

_AVAILABLE = None  # cache du test d'import (None = pas encore teste)

_SEV_KEY = {"error": "coh.sev_error", "warning": "coh.sev_warning",
            "info": "coh.sev_info"}
_SEV_ORDER = {"error": 0, "warning": 1, "info": 2}


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


class CoherenceWebBridge(WebBridge):
    """Pont de la page coherence : chemin du scenario, analyse async,
    export CSV (les QFileDialog sont ouverts cote Python, jamais depuis la
    page)."""

    def __init__(self, dialog=None, working_root: str = "", parent=None):
        super().__init__(parent)
        self._dialog = dialog
        self._path = working_root or ""
        self._report = None
        self._running = False
        self._status = ""             # vide = texte d'accueil (coh.hint)

    # -- payload ---------------------------------------------------------
    def _payload(self) -> str:
        rows = []
        if self._report is not None:
            for f in sorted(self._report.findings,
                            key=lambda f: _SEV_ORDER[f.severity]):
                rows.append({
                    "section": t(f.section),
                    "sev": t(_SEV_KEY[f.severity]),
                    "sev_key": f.severity,
                    "count": f.count,
                    "detail": f.detail[:300],
                    "fix_tool": t(f.fix_tool),
                })
        return json.dumps({
            "labels": {
                "scenario": t("yamlcheck.scenario"),
                "scenario_hint": t("yamlcheck.scenario_hint"),
                "browse": t("yamlcheck.browse"),
                "analyze": t("coh.analyze"),
                "analyze_tip": t("coh.analyze.tip"),
                "export": t("market.export"),
                "col_domain": t("coh.col_domain"),
                "col_severity": t("coh.col_severity"),
                "col_count": t("coh.col_count"),
                "col_examples": t("coh.col_examples"),
                "col_module": t("coh.col_module"),
            },
            "path": self._path,
            "rows": rows,
            "status": self._status or t("coh.hint"),
            "running": self._running,
            "export_enabled": self._report is not None and not self._running,
        }, ensure_ascii=False)

    def push_reset(self) -> None:
        """Re-pousse l'etat complet par le CANAL (jamais runJavaScript :
        autre monde JS)."""
        self.data_changed.emit(self._payload())

    # -- slots -----------------------------------------------------------
    @pyqtSlot(result=str)
    def get_init(self) -> str:
        """Premier chargement de la page (elle TIRE ses donnees : un
        push_reset emis pendant le chargement serait perdu)."""
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
            self._status = t("yamlcheck.need_scenario")
            self.push_reset()
            return
        self._running = True
        self._report = None
        self._status = t("coh.running")
        self.push_reset()
        vanilla = ""
        try:
            from core.settings import get_vanilla_content_path
            vanilla = get_vanilla_content_path()
        except Exception:                    # noqa: BLE001 - optionnel
            pass
        async_call(self, lambda: run_coherence_audit(root, vanilla),
                   on_done=self._done, on_fail=self._fail,
                   name="coherence-web")

    def _done(self, rep):
        self._running = False
        self._report = rep
        self._status = t("coh.done", e=rep.errors, w=rep.warnings,
                         s=f"{rep.seconds:.0f}")
        self.push_reset()

    def _fail(self, exc: Exception):
        self._running = False
        self._status = f"{t('yamlcheck.failed')} ({exc})"
        self.push_reset()

    @pyqtSlot()
    def export(self):
        if self._report is None:
            return
        base = (self._path or "").strip() or str(Path.home())
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
        out, _ = QFileDialog.getSaveFileName(
            self._dialog, t("market.export"),
            str(Path(base) / f"coherence_{stamp}.csv"), "CSV (*.csv)")
        if not out:
            return
        with open(out, "w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh, delimiter=";")
            writer.writerow([t("coh.col_domain"), t("coh.col_severity"),
                             t("coh.col_count"), t("coh.col_examples"),
                             t("coh.col_module")])
            for f in self._report.findings:
                writer.writerow([t(f.section), t(_SEV_KEY[f.severity]),
                                 f.count, " ; ".join(f.items[:12]),
                                 t(f.fix_tool)])
        self._status = t("market.csv_done", path=out)
        self.push_reset()

    # -- actions (liste blanche, meme forme que les autres ponts) --------
    _ACTIONS = {"run": "run", "export": "export", "browse": "browse",
                "close": "_close"}

    @pyqtSlot(str)
    def run_action(self, name: str) -> None:
        method = self._ACTIONS.get(name)
        if method is not None:
            getattr(self, method)()

    def _close(self):
        if self._dialog is not None:
            self._dialog.reject()


class CoherenceWebDialog(WebDialog):
    """Fenetre du controle de coherence en vue web (gabarit web_dialog)."""

    WEB_DIR = WEB_DIR
    DIALOG_KEY = "coherence"   # meme cle que le dialogue Qt : geometrie partagee
    BRIDGE_FACTORY = staticmethod(
        lambda dialog: CoherenceWebBridge(dialog, dialog._working_root, dialog))

    def __init__(self, parent=None, working_root: str = ""):
        self._working_root = working_root or ""
        self.setWindowTitle(t("coh.title"))
        self.resize(1150, 640)
        super().__init__(parent)
