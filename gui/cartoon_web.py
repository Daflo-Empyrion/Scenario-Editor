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

"""Look cartoon en vue web (chantier webapp, 02/11) : la page
gui/web/cartoon/index.html remplace le dialogue Qt (conserve en repli).
Moteur : core/cartoon_look (fonctions module deja partageables). L'etat
pousse est TOUJOURS le payload complet (tailles modestes : 8 facteurs,
20 lignes d'apercu) — pas de distinction full/light. Les travaux longs
(meta, couleurs, application, restauration) passent par async_call ; les
choix natifs (dossier) et la confirmation de restauration s'ouvrent cote
Python (dialog_policy les rend non modaux).

Tests : pont seul (tests/test_cartoon_web.py), async_call monkeypatche en
synchrone, core.cartoon_look monkeypatche (jamais le disque reel).
"""
from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from core.cartoon_look import DEFAULT_PRESET, PRESET_SPECS
from core.i18n import t
from gui.cartoon_dialog import _PRESET_UI, _PREVIEW_MAX
from gui.ewa_async import async_call
from gui.web_dialog import WebBridge, WebDialog

WEB_DIR = Path(__file__).resolve().parent / "web" / "cartoon"

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


class CartoonWebBridge(WebBridge):
    """Pont de la page cartoon : facteurs editables, apercu couleurs,
    previsualisation / application / restauration (chemins async du
    dialogue Qt, memes reponses)."""

    def __init__(self, dialog=None, working_root: str = "", parent=None):
        super().__init__(parent)
        self._dialog = dialog
        self._path = working_root or ""
        self._force = False
        self._factors: dict = dict(DEFAULT_PRESET)
        self._playfields: list = []
        self._pf = ""
        self._backups: dict = {}      # nom -> chemin
        self._backup = ""
        self._colors: dict = {}
        self._status = ""
        self._report = ""
        self._running = False

    # -- payload complet ---------------------------------------------------
    def _payload(self) -> str:
        from core.cartoon_look import list_backups, load_stored_preset
        backups = {b.name: str(b) for b in list_backups()}
        return json.dumps({
            "labels": {
                "scenario": t("yamlcheck.scenario"),
                "scenario_hint": t("yamlcheck.scenario_hint"),
                "browse": t("yamlcheck.browse"),
                "force": t("cartoon.force"),
                "preset": t("cartoon.preset"),
                "preview": t("cartoon.preview"),
                "apply": t("cartoon.apply"),
                "defaults": t("cartoon.preset_defaults"),
                "colors": t("cartoon.colors"),
                "col_property": t("cartoon.col_property"),
                "col_origin": t("cartoon.col_origin"),
                "col_new": t("cartoon.col_new"),
                "backups": t("cartoon.backups"),
                "restore": t("cartoon.restore"),
                "info": t("module.info"),
                "none": t("cartoon.colors_none"),
                "section_ciel": t("cartoon.section_ciel"),
                "section_terrain": t("cartoon.section_terrain"),
            },
            "path": self._path,
            "force": self._force,
            "factors": [{"key": k, "label": t(lk), "tip": t(lk + ".tip"),
                         "value": self._factors.get(k, dflt),
                         "min": lo, "max": hi, "step": step, "dec": dec}
                        for k, (lk, dec, step) in _PRESET_UI.items()
                        for dflt, lo, hi in [PRESET_SPECS[k]]],
            "playfields": self._playfields,
            "pf": self._pf,
            "backups": sorted(backups),
            "backup": self._backup,
            "colors": self._colors,
            "status": self._status,
            "report": self._report,
            "running": self._running,
        }, ensure_ascii=False)

    def push_reset(self) -> None:
        self.data_changed.emit(self._payload())

    @pyqtSlot(result=str)
    def get_init(self) -> str:
        """Chargement initial : la page TIRE, puis le pont relance la meta
        (liste playfields + passes sauvegardees + preset stocke) comme le
        dialogue Qt dans son __init__."""
        return self._payload()

    @pyqtSlot()
    def refresh_meta(self):
        self._refresh_meta()

    # -- champs -------------------------------------------------------------
    @pyqtSlot(str)
    def set_path(self, path: str) -> None:
        self._path = path

    @pyqtSlot(bool)
    def set_force(self, on: bool) -> None:
        self._force = bool(on)

    @pyqtSlot(str, float)
    def set_factor(self, key: str, value: float) -> None:
        if key in PRESET_SPECS:
            _dflt, lo, hi = PRESET_SPECS[key]
            self._factors[key] = max(lo, min(hi, float(value)))

    @pyqtSlot()
    def set_defaults(self):
        self._factors = dict(DEFAULT_PRESET)
        self.push_reset()

    @pyqtSlot(str)
    def set_pf(self, name: str) -> None:
        self._pf = name
        self._refresh_colors()

    @pyqtSlot(str)
    def set_backup(self, name: str) -> None:
        self._backup = name

    @pyqtSlot()
    def browse(self):
        path = QFileDialog.getExistingDirectory(
            self._dialog, t("yamlcheck.scenario"), self._path or ".")
        if path:
            self._path = path
            self._refresh_meta()

    # -- meta (liste playfields + passes sauvegardees + preset stocke) ------
    def _refresh_meta(self):
        if self._running:
            return
        scenario = self._path.strip()

        def _load():
            from core.cartoon_look import TARGET_NAMES, list_backups, \
                load_stored_preset
            names = []
            pfs = Path(scenario) / "Playfields"
            if pfs.is_dir():
                for pf in sorted(p for p in pfs.iterdir()
                                 if p.is_dir() and not p.name.startswith('+')):
                    if any((pf / n).is_file() for n in TARGET_NAMES):
                        names.append(pf.name)
            backups = {b.name: str(b) for b in list_backups()}
            return names, backups, load_stored_preset()

        async_call(self, _load, on_done=self._meta_done, name="cartoon-meta")

    def _meta_done(self, result):
        names, backups, preset = result
        self._playfields = names
        self._pf = names[0] if names else ""
        self._backups = backups
        self._backup = sorted(backups)[0] if backups else ""
        for key, value in preset.items():
            if key in PRESET_SPECS:
                self._factors[key] = value
        if names:
            self._refresh_colors()
        else:
            self.push_reset()

    # -- apercu des couleurs -------------------------------------------------
    def _refresh_colors(self):
        scenario = self._path.strip()
        if not scenario or not self._pf:
            return
        from core.cartoon_look import preview_colors
        preset = dict(self._factors)
        async_call(self, lambda: preview_colors(scenario, self._pf, preset),
                   on_done=self._colors_done, name="cartoon-colors")

    def _colors_done(self, rows: dict):
        self._colors = rows
        self.push_reset()

    # -- previsualisation / application (meme _launch que le dialogue Qt) ---
    def _launch(self, dry_run: bool):
        if self._running:
            return
        if not self._path.strip():
            self._status = t("digest.need_scenario")
            self.push_reset()
            return
        self._running = True
        self._status = t("cartoon.running")
        self.push_reset()
        from core.cartoon_look import run_preset, save_preset
        scenario = self._path.strip()
        force = self._force and not dry_run
        preset = dict(self._factors)

        def _worker():
            if not dry_run:
                save_preset(preset)   # reglage persiste a l'application
            return run_preset(scenario, dry_run=dry_run, force=force,
                              preset=preset)

        async_call(self, _worker, on_done=self._done, on_fail=self._fail,
                   name="cartoon-look")

    @pyqtSlot()
    def preview(self):
        self._launch(dry_run=True)

    @pyqtSlot()
    def apply(self):
        self._launch(dry_run=False)

    def _done(self, rep: dict):
        self._running = False
        if rep.get("error"):
            self._status = t("cartoon.missing")
            self.push_reset()
            return
        if rep.get("marker_blocked"):
            self._status = t("cartoon.blocked")
            self.push_reset()
            return
        touched = rep["touched"]
        lines = [f"+ {rel}  ({n})" for rel, n in touched[:_PREVIEW_MAX]]
        rest = len(touched) - len(lines)
        if rest > 0:
            lines.append(f"+ \u2026 ({rest})")
        for line in rep["invalid"][:_PREVIEW_MAX]:
            lines.append(f"! {line}")
        self._report = "\n".join(lines)
        if rep.get("dry_run"):
            self._status = t("cartoon.dry").format(n=len(touched),
                                                   total=rep["total"])
            self.push_reset()
            return
        status = t("cartoon.done").format(n=len(touched), total=rep["total"],
                                          backup=rep["backup_dir"])
        if rep.get("invalid"):
            status += " " + t("cartoon.invalid").format(n=len(rep["invalid"]))
        if rep.get("prod"):
            status += " " + t("cartoon.synced").format(
                copied=rep["copied"], bins=rep["bins"])
        else:
            status += " " + t("cartoon.noprod")
        self._status = status
        self.push_reset()
        self._refresh_meta()          # une nouvelle passe sauvegardee

    # -- restauration --------------------------------------------------------
    @pyqtSlot()
    def restore(self):
        name = self._backup
        if self._running or not name:
            return
        backup_dir = self._backups.get(name, "")
        if not backup_dir:
            return
        answer = QMessageBox.question(
            self._dialog, t("cartoon.restore"),
            t("cartoon.confirm_restore").format(name=name))
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._running = True
        self._status = t("cartoon.running")
        self.push_reset()
        from core.cartoon_look import restore_backup
        scenario = self._path.strip()
        async_call(self, lambda: restore_backup(scenario, backup_dir),
                   on_done=self._restore_done, on_fail=self._fail,
                   name="cartoon-restore")

    def _restore_done(self, rep: dict):
        self._running = False
        if rep.get("error"):
            self._status = t("cartoon.backup_missing")
            self.push_reset()
            return
        status = t("cartoon.restored").format(n=rep["copied"])
        if rep.get("prod"):
            status += " " + t("cartoon.synced").format(
                copied=rep["copied"], bins=rep["bins"])
        else:
            status += " " + t("cartoon.noprod")
        status += " " + t("cartoon.marker_removed")
        self._status = status
        self.push_reset()
        self._refresh_meta()
        self._refresh_colors()

    def _fail(self, exc: Exception):
        self._running = False
        self._status = f"{type(exc).__name__}: {exc}"
        self.push_reset()

    # -- divers ---------------------------------------------------------------
    def _info(self):
        from gui.module_info import show_module_info
        show_module_info(self._dialog, "cartoon.info_html")

    def _close(self):
        if self._dialog is not None:
            self._dialog.reject()

    _ACTIONS = {"preview": "preview", "apply": "apply",
                "defaults": "set_defaults", "browse": "browse",
                "refresh_meta": "refresh_meta", "restore": "restore",
                "info": "_info", "close": "_close"}

    @pyqtSlot(str)
    def run_action(self, name: str) -> None:
        method = self._ACTIONS.get(name)
        if method is not None:
            getattr(self, method)()


class CartoonWebDialog(WebDialog):
    WEB_DIR = WEB_DIR
    DIALOG_KEY = "cartoon_look"   # meme cle que le dialogue Qt : geometrie
    BRIDGE_FACTORY = staticmethod(
        lambda dialog: CartoonWebBridge(dialog, dialog._working_root, dialog))

    def __init__(self, parent=None, working_root: str = ""):
        self._working_root = working_root or ""
        self.setWindowTitle(t("cartoon.title"))
        self.resize(860, 660)
        super().__init__(parent)
        # comme le dialogue Qt : la meta ne se charge que sur un scenario
        if self._working_root:
            self._bridge.refresh_meta()
