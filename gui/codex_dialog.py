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

"""Fenetre Codex : navigateur d'objets/blocs/jetons, comparateur, marchands
(ventes, rachats, opportunites, lieux, routes) et matrice de degats.
Donnees construites dans un thread (build_codex_data) : ~2 s sur RE2-FR."""
from __future__ import annotations

from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton,
                             QTabWidget, QVBoxLayout)

from core.codex import build_codex_data
from core.i18n import t
from gui.busy import run_long
from gui.codex_export import export_rows
from gui.codex_items import CompareTab, ItemsTab
from gui.codex_traders import TradersTab
from gui.codex_weapons import WeaponsTab
from gui.msgboxes import info
from gui.window_geometry import track


class CodexDialog(QDialog):
    """Codex du scenario ouvert : lecture seule, aucune ecriture dans le jeu."""

    def __init__(self, parent, working_root: str, vanilla_root: str = ""):
        super().__init__(parent)
        self.setWindowTitle(t("codex.title"))
        self.setMinimumSize(1000, 640)
        self.working_root = str(working_root)
        self.vanilla_root = vanilla_root
        self.data = None

        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.lbl_path = QLabel(self.working_root)
        self.lbl_path.setWordWrap(True)
        top.addWidget(self.lbl_path, 1)
        self.btn_info = QPushButton(t("codex.info"))
        self.btn_info.setToolTip(t("codex.info_html"))
        self.btn_info.clicked.connect(
            lambda: info(self, t("codex.title"), t("codex.info_html")))
        top.addWidget(self.btn_info)
        self.btn_export = QPushButton(t("codex.export"))
        self.btn_export.setToolTip(t("codex.export.tip"))
        self.btn_export.clicked.connect(self._export)
        top.addWidget(self.btn_export)
        self.btn_reload = QPushButton(t("codex.reload"))
        self.btn_reload.clicked.connect(self.load)
        top.addWidget(self.btn_reload)
        lay.addLayout(top)

        self.tabs = QTabWidget()
        self.items = ItemsTab()
        self.compare = CompareTab()
        self.traders = TradersTab(self.working_root)
        self.weapons = WeaponsTab()
        self.tabs.addTab(self.items, t("codex.tab.items"))
        self.tabs.addTab(self.compare, t("codex.tab.compare"))
        self.tabs.addTab(self.traders, t("codex.tab.traders"))
        self.tabs.addTab(self.weapons, t("codex.tab.weapons"))
        lay.addWidget(self.tabs, 1)

        self.items.pinsChanged.connect(self._pins_changed)
        self.items.pinFull.connect(self._pins_full)
        track(self, "codex", (1180, 760))
        self.load()

    # ------------------------------------------------------------- donnees

    def load(self) -> None:
        self.btn_reload.setEnabled(False)
        try:
            data = run_long(
                self,
                lambda: build_codex_data(self.working_root, self.vanilla_root),
                "codex.loading")
        except Exception as exc:                     # noqa: BLE001 - affiche, pas de crash
            self.lbl_path.setText(t("codex.load_error", error=str(exc)))
            return
        finally:
            self.btn_reload.setEnabled(True)
        self.data = data
        self.lbl_path.setText(t(
            "codex.summary", root=self.working_root, items=len(data.items),
            blocks=len(data.blocks), tokens=len(data.tokens),
            traders=len(data.traders)))
        self.items.set_data(data)
        self.compare.set_data(data)
        self.traders.set_data(data)
        self.weapons.set_data(data)

    def _pins_changed(self) -> None:
        """La colonne de cases a coche : le comparateur suit, sans voler le
        focus (on coche souvent 3-4 objets avant d'aller comparer)."""
        pinned = self.items.pinned()
        self.compare.set_items(pinned)
        label = t("codex.tab.compare")
        self.tabs.setTabText(self.tabs.indexOf(self.compare),
                             f"{label} ({len(pinned)})" if pinned else label)

    def _pins_full(self) -> None:
        self.lbl_path.setText(t("codex.pin.full"))

    def _export(self) -> None:
        """Exporte la vue affichee (onglet et sous-onglet actifs) en CSV."""
        pane = self.tabs.currentWidget()
        payload = pane.export_payload() if hasattr(pane, "export_payload") else None
        if payload is None:
            self.lbl_path.setText(t("codex.export_empty"))
            return
        headers, rows = payload
        path = export_rows(self, headers, rows, "codex")
        if path is not None:
            self.lbl_path.setText(t("codex.export_done", path=str(path)))


def open_codex(parent, main_window=None) -> bool:
    """Entree du menu Outils > Balance (non modal : la fenetre principale
    garde la reference, sinon le dialogue serait collecte aussitot)."""
    ws = getattr(main_window, "workspace", None)
    root = getattr(ws, "working_root", None) if ws is not None else None
    if root is None:
        info(parent, t("codex.title"), t("codex.no_workspace"))
        return False
    from core.settings import get_vanilla_content_path
    dialog = CodexDialog(parent, str(root), get_vanilla_content_path())
    if main_window is not None:
        main_window._codex_dialog = dialog
    dialog.show()
    return True
