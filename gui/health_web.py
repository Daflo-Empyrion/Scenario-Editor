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

"""Bilan de santé (F5, Centre de vérification) en vue web (chantier
webapp, tranche 5, 02/11) : la page gui/web/health/index.html remplace le
tableau de bord Qt (gui/health_check_dialog.py, conserve en repli).

Meme contrat que le dialogue Qt : NE REIMPLEMENTE AUCUN affichage
detaille — les boutons « Voir le detail » ouvrent les VRAIES fenetres de
la fenetre principale (cross references, validation, blocs en attente,
jetons, bilan lancement). La collecte est la fonction partagee
`collect_all_checks(workspace)` du module Qt, executee hors thread GUI
via async_call (l'attente est affichee par la page elle-meme).

Tests : pont seul (tests/test_health_web.py), async_call monkeypatche en
synchrone ; jamais de QWebEngineView sous offscreen.
"""
from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import pyqtSlot

from core.i18n import t
from gui.ewa_async import async_call
from gui.web_dialog import WebBridge, WebDialog

WEB_DIR = Path(__file__).resolve().parent / "web" / "health"

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


class HealthWebBridge(WebBridge):
    """Pont de la page bilan F5 : « Tout verifier » (collecte hors thread
    GUI), boutons de detail -> VRAIES fenetres de la fenetre principale."""

    def __init__(self, main_window, dialog=None, parent=None):
        super().__init__(parent)
        self._mw = main_window
        self._dialog = dialog
        self._counts = None           # dernier resultat de collecte
        self._running = False
        self._status = ""             # message d'erreur eventuel

    # -- payload ----------------------------------------------------------
    def _categories(self):
        """(cle, titre, action run_action, compteur) — meme regroupement que
        le dialogue Qt (orphans = informatif, hors total)."""
        mw = self._mw
        return [
            ("refs", t("health.category_refs"), "open_refs", "refs",
             mw.check_cross_references_dialog),
            ("validation", t("health.category_validation"), "open_validation",
             "validation", mw.validate_scenario_dialog),
            ("pending", t("health.category_pending"), "open_pending",
             "pending", mw.check_pending_conflicts_dialog),
            ("orphans", t("health.category_orphans"), "open_orphans",
             "orphans", mw._open_orphan_dialog),
            ("launch", t("health.category_launch"), "open_launch",
             "launch_errors", self._open_launch_detail),
        ]

    def _payload(self) -> str:
        counts = self._counts
        rows = []
        total = 0
        if counts is not None:
            for key, title, action, field, _opener in self._categories():
                n = counts.get(field, 0)
                ok = n == 0
                if key != "orphans":      # informatif : jamais dans le total
                    total += n
                rows.append({
                    "key": key, "action": action, "title": title,
                    "ok": ok,
                    "text": t("health.all_ok") if ok
                            else t("health.n_issues", n=n),
                })
        if self._status:
            summary, state = self._status, "ko"
        elif counts is None:
            summary, state = "", ""
        elif total == 0:
            summary, state = t("health.overall_ok"), "ok"
        else:
            summary, state = t("health.overall_problems", n=total), "ko"
        return json.dumps({
            "labels": {
                "intro": t("health.intro"),
                "view_detail": t("health.btn_view_detail"),
                "check_all": t("health.check_all"),
                "close": t("validation.close"),
            },
            "rows": rows,
            "summary": summary,
            "summary_state": state,
            "running": self._running,
            "has_run": counts is not None,
        }, ensure_ascii=False)

    def push_reset(self) -> None:
        self.data_changed.emit(self._payload())

    # -- slots -------------------------------------------------------------
    @pyqtSlot(result=str)
    def get_init(self) -> str:
        """Premier chargement de la page (elle TIRE ses donnees)."""
        return self._payload()

    @pyqtSlot()
    def run(self):
        """« Tout verifier » — meme garde que l'entree du menu : un espace
        de travail est requis ; la collecte passe par la fonction partagee
        du module Qt, hors thread GUI."""
        if self._running:
            return
        if not getattr(self._mw, "workspace", None):
            self._status = t("err.no_project_msg")
            self.push_reset()
            return
        self._running = True
        self._status = ""
        self.push_reset()
        # VERIF-001/VERIF-009 : proposer d'abord d'enregistrer les onglets
        # modifies (lecture disque ensuite) — appel GUI, meme contrat que le
        # dialogue Qt dans refresh().
        self._mw.ensure_analysis_fresh_tabs()
        from gui.health_check_dialog import collect_all_checks
        workspace = self._mw.workspace
        async_call(self, lambda: collect_all_checks(workspace),
                   on_done=self._done, on_fail=self._fail, name="health-web")

    def _done(self, counts):
        self._running = False
        self._counts = counts
        self.push_reset()

    def _fail(self, exc: Exception):
        self._running = False
        self._status = f"{t('yamlcheck.failed')} ({exc})"
        self.push_reset()

    # -- actions (liste blanche) -------------------------------------------
    def _open_launch_detail(self):
        """Le detail du bilan lancement : la VRAIE fenetre dediee, sur la
        copie de travail (meme code que le dialogue Qt)."""
        from gui.launch_check_dialog import LaunchCheckDialog
        dlg = LaunchCheckDialog(self._mw,
                                working_root=str(self._mw.workspace.working_root))
        dlg.show()

    _DETAIL_ACTIONS = {"open_refs", "open_validation", "open_pending",
                       "open_orphans", "open_launch"}

    @pyqtSlot(str)
    def run_action(self, name: str) -> None:
        if name == "check_all":
            self.run()
            return
        if name == "close":
            if self._dialog is not None:
                self._dialog.close()
            return
        if name in self._DETAIL_ACTIONS:
            counts = self._counts
            for key, _title, action, field, opener in self._categories():
                if action != name:
                    continue
                # parite Qt : le bouton « Voir le detail » est inactive
                # quand la categorie ne montre aucun probleme
                if counts is None or counts.get(field, 0) == 0:
                    return
                opener()
            return


class HealthWebDialog(WebDialog):
    """Fenetre du bilan F5 en vue web (gabarit gui/web_dialog.py)."""

    WEB_DIR = WEB_DIR
    BRIDGE_FACTORY = staticmethod(
        lambda dialog: HealthWebBridge(dialog.main_window, dialog, dialog))

    def __init__(self, main_window, parent=None):
        self.main_window = main_window
        self.setWindowTitle(t("verification.center_title"))
        self.resize(680, 420)
        super().__init__(parent)
