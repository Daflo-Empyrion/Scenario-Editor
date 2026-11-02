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

"""Reintegration de playfields orphelins en vue web (chantier webapp,
02/11) : la page gui/web/reintegrate/index.html remplace le dialogue Qt
(conserve en repli). Le moteur reste core/playfield_reintegrate (fonctions
module) ; la lecture (legacy + arrivals + orphelins) passe par run_long sur
la fenetre — comme le dialogue Qt — et l'application rejoue le chemin EXACT
(confirm ask_yes_no native, central_backup, undo workspace, rescan, bilan
launch_check en async).

Tests : pont seul (tests/test_reintegrate_web.py), moteurs monkeypatches.
"""
from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import pyqtSlot

from core.i18n import t
from gui.busy import run_long
from gui.ewa_async import async_call
from gui.web_dialog import WebBridge, WebDialog

WEB_DIR = Path(__file__).resolve().parent / "web" / "reintegrate"

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


class ReintegrateWebBridge(WebBridge):
    """Pont de la page reintegrate : orphelins cochables par famille, lot
    par systeme, apercu, application avec backup + undo + bilan."""

    def __init__(self, root, main_window=None, dialog=None, parent=None):
        super().__init__(parent)
        self._root = Path(root)
        self._main = main_window
        self._dialog = dialog
        self._legacy: list = []
        self._arrivals: list = []
        self._groups: list = []       # [{key,label,items:[{name,kind,desc}]}]
        self._checked: set = set()
        self._per_system = 2
        self._legacy_on = False
        self._arrival_on = False
        self._preview = ""
        self._status = ""
        self._apply_enabled = False
        self.applied = 0

    # -- payload complet -----------------------------------------------------
    def _payload(self) -> str:
        from core.playfield_reintegrate import find_legacy, \
            find_missing_arrivals, find_orphans
        # les listes legaces/arrivals sont rechargees a chaque push : cheap
        # (un find_orphans complet est fait par _load, pas ici)
        return json.dumps({
            "labels": {
                "per_system": t("reintegrate.per_system"),
                "per_system_tip": t("reintegrate.per_system.tip"),
                "preview_label": t("reintegrate.preview"),
                "preview_btn": t("reintegrate.preview_btn"),
                "apply": t("reintegrate.apply"),
                "close": t("reintegrate.close"),
                "info": t("module.info"),
                "col_type": t("reintegrate.col_type"),
                "col_category": t("reintegrate.col_category"),
                "col_description": t("reintegrate.col_description"),
            },
            "per_system": self._per_system,
            "legacy": {"n": len(self._legacy), "on": self._legacy_on,
                       "text": t("reintegrate.legacy", n=len(self._legacy))},
            "arrivals": {"n": len(self._arrivals), "on": self._arrival_on,
                         "text": t("reintegrate.arrivals",
                                   n=len(self._arrivals))},
            "groups": [{"key": g["key"], "label": g["label"],
                        "items": [{"name": it["name"], "kind": it["kind"],
                                   "desc": it["desc"],
                                   "checked": it["name"] in self._checked}
                                  for it in g["items"]]}
                       for g in self._groups],
            "preview": self._preview,
            "status": self._status,
            "running": self._running,
            "apply_enabled": self._apply_enabled,
        }, ensure_ascii=False)

    _running = False

    def push_reset(self) -> None:
        self.data_changed.emit(self._payload())

    @pyqtSlot(result=str)
    def get_init(self) -> str:
        return self._payload()

    @pyqtSlot()
    def load(self):
        """Lecture disque (orphelins + legacy + arrivals) — run_long sur la
        fenetre, meme garde que le dialogue Qt."""
        from core.playfield_reintegrate import find_legacy, \
            find_missing_arrivals, find_orphans
        self._legacy = run_long(self._parent_widget(),
                                lambda: find_legacy(self._root))
        self._legacy_on = bool(self._legacy)
        self._arrivals = run_long(self._parent_widget(),
                                  lambda: find_missing_arrivals(self._root))
        self._arrival_on = bool(self._arrivals)
        orphans = run_long(self._parent_widget(),
                           lambda: find_orphans(self._root))
        self._groups = []
        for family, key in (("surface", "surface"), ("space", "space")):
            subset = [o for o in orphans if o.family == family]
            if not subset:
                continue
            self._groups.append({
                "key": key,
                "label": t("reintegrate.group_surface" if family == "surface"
                           else "reintegrate.group_space", n=len(subset)),
                "items": [{"name": o.type_name, "kind": t(o.kind_key),
                           "desc": o.description} for o in subset],
            })
        self._checked = set()
        self._preview = ""
        self._apply_enabled = False
        if not orphans and not self._legacy:
            self._status = t("reintegrate.none")
        self.push_reset()

    def _parent_widget(self):
        return self._dialog if self._dialog is not None else self._main

    # -- champs ----------------------------------------------------------------
    @pyqtSlot(int)
    def set_per_system(self, n: int) -> None:
        self._per_system = max(1, min(20, int(n)))
        self._invalidate()

    @pyqtSlot(bool)
    def set_legacy(self, on: bool) -> None:
        self._legacy_on = bool(on)
        self._invalidate()

    @pyqtSlot(bool)
    def set_arrival(self, on: bool) -> None:
        self._arrival_on = bool(on)
        self._invalidate()

    @pyqtSlot(str, bool)
    def set_checked(self, name: str, on: bool) -> None:
        if on:
            self._checked.add(name)
        else:
            self._checked.discard(name)
        self._invalidate()

    def _invalidate(self):
        self._apply_enabled = False
        self._preview = ""
        self.push_reset()

    # -- actions ------------------------------------------------------------------
    def _selected(self) -> list:
        return [n for n in self._checked]

    @pyqtSlot()
    def preview(self):
        from core.playfield_reintegrate import plan_placements, render_preview
        picks = self._selected()
        plan = plan_placements(self._root, picks, self._per_system) \
            if picks else []
        plan = list(plan) + (self._arrivals if self._arrival_on else [])
        removals = self._legacy if self._legacy_on else []
        if not plan and not removals:
            self._status = t("reintegrate.none_selected")
            self.push_reset()
            return
        text = render_preview(plan, removals)
        if len(plan) < len(picks):
            text += "\n" + t("reintegrate.skipped", n=len(picks) - len(plan))
        self._preview = text
        self._apply_enabled = True
        self._status = (t("reintegrate.plan_ready", n=len(plan),
                          r=len(removals))
                        + "\n" + t("reintegrate.new_game"))
        self.push_reset()

    @pyqtSlot()
    def apply(self):
        from core.playfield_reintegrate import apply_placements, \
            plan_placements, remove_legacy, sectors_yaml
        picks = self._selected()
        plan = plan_placements(self._root, picks, self._per_system) \
            if picks else []
        plan = list(plan) + (self._arrivals if self._arrival_on else [])
        removals = self._legacy if self._legacy_on else []
        if not plan and not removals:
            self._status = t("reintegrate.none_selected")
            self.push_reset()
            return
        from gui.msgboxes import ask_yes_no
        if not ask_yes_no(self._parent_widget(), t("reintegrate.title"),
                          t("reintegrate.confirm", n=len(plan),
                            r=len(removals))):
            return
        path = sectors_yaml(self._root)
        if path is None:
            self._status = t("reintegrate.no_sectors")
            self.push_reset()
            return
        from core.fsutil import central_backup
        from core.workspace_undo import FileStateUndo, capture_file
        prior = capture_file(path)
        removed = run_long(self._parent_widget(),
                           lambda: remove_legacy(self._root, removals)) \
            if removals else 0
        applied, details = run_long(
            self._parent_widget(),
            lambda: apply_placements(self._root, plan))
        if not applied and not removed:
            self._status = "\n".join(details) or t("reintegrate.empty_plan")
            self.push_reset()
            return
        central_backup(path)
        self.applied += applied
        main = self._main
        if main is not None:
            undo = getattr(main, "_push_workspace_undo", None)
            if undo is not None:
                undo(FileStateUndo(path, prior,
                                   t("reintegrate.undo",
                                     n=applied + removed)))
            reload_tab = getattr(main, "_reload_tab_if_open_and_unmodified",
                                 None)
            if reload_tab is not None:
                reload_tab(path)
            ws = getattr(main, "workspace", None)
            if ws is not None:
                ws.rescan_working()
        message = (t("reintegrate.done", n=applied, r=removed) + "\n"
                   + t("reintegrate.new_game"))
        if details:
            message += "\n" + "\n".join(details[:5])
        self._status = message
        self.push_reset()
        self.load()
        self._run_bilan(message)

    def _run_bilan(self, message: str) -> None:
        from core import settings
        vanilla = settings.get_vanilla_content_path() or ""

        def work():
            from core.launch_check import run_launch_checks
            return run_launch_checks(str(self._root), vanilla)

        def done(issues):
            errors = sum(1 for i in issues if i.severity == "error")
            warnings = len(issues) - errors
            self._status = (message + "\n"
                            + t("reintegrate.bilan", e=errors, w=warnings))
            self.push_reset()

        def failed(error):
            self._status = (message + "\n"
                            + t("reintegrate.bilan_failed", msg=str(error)))
            self.push_reset()

        async_call(self, work, on_done=done, on_fail=failed,
                   name="reintegrate-bilan")

    def _info(self):
        from gui.module_info import show_module_info
        show_module_info(self._parent_widget(), "reintegrate.info_html")

    def _close(self):
        if self._dialog is not None:
            self._dialog.reject()

    _ACTIONS = {"load": "load", "preview": "preview", "apply": "apply",
                "info": "_info", "close": "_close"}

    @pyqtSlot(str)
    def run_action(self, name: str) -> None:
        method = self._ACTIONS.get(name)
        if method is not None:
            getattr(self, method)()


class ReintegrateWebDialog(WebDialog):
    WEB_DIR = WEB_DIR
    DIALOG_KEY = "playfield_reintegrate"   # meme cle que le dialogue Qt
    BRIDGE_FACTORY = staticmethod(
        lambda dialog: ReintegrateWebBridge(dialog._root, dialog._main,
                                            dialog, dialog))

    def __init__(self, root, parent=None, main_window=None):
        self._root = Path(root)
        self._main = main_window
        self.setWindowTitle(t("reintegrate.title"))
        self.resize(860, 680)
        super().__init__(parent)
        self._bridge.load()
