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

"""Arbre du WORKSPACE en vue web (chantier webapp, tranche finale, 02/11) :
la page gui/web/workspace/index.html remplace la QTreeWidget de la copie de
travail (panneau bas de la fenetre principale), meme repartition que les
autres vues web.

REPARTITION STRICTE :
  - l'arbre QTreeWidget RESTE la source de verite (recherche, menu
    contextuel, double-clic, filtre Qt : rien ne bouge) ; la vue web est
    empilee par-dessus dans un QStackedWidget ;
  - le pont lit l'arbre recursivement (dossiers puis fichiers, profondeur
    pour l'indentation) et seule interaction = `open_entry(idx)` qui rejoue
    le chemin EXACT du double-clic Qt (`_on_working_double_clicked`) ;
  - la page ne fait aucun acces fichier, pas d'edition.

Tests : pont seul (tests/test_workspace_web_view.py), jamais de
QWebEngineView reel sous offscreen.
"""
import json
from pathlib import Path

from PyQt6.QtCore import QObject, QUrl, QFile, QIODevice, pyqtSignal, pyqtSlot
from PyQt6.QtCore import Qt

from core.i18n import t

WEB_DIR = Path(__file__).resolve().parent / "web" / "workspace"

_AVAILABLE = None  # cache du test d'import (None = pas encore teste)


def is_available() -> bool:
    """True si le moteur web est utilisable (voir csv_web_view.is_available)."""
    global _AVAILABLE
    if _AVAILABLE is None:
        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
            from PyQt6.QtWebChannel import QWebChannel  # noqa: F401
            _AVAILABLE = (WEB_DIR / "index.html").is_file()
        except Exception:
            _AVAILABLE = False
    return _AVAILABLE


class WorkspaceWebBridge(QObject):
    """Objet expose a la page : lecture de l'arbre de la copie de travail et
    ouverture d'un fichier par le chemin du double-clic Qt."""

    data_changed = pyqtSignal(str)  # Python -> page : l'arbre a change

    def __init__(self, main_window, tree, parent=None):
        super().__init__(parent)
        self._mw = main_window
        self._tree = tree          # QTreeWidget (source de verite)
        self._items = []           # QTreeWidgetItem parallele a entries

    def _collect(self):
        """Parcours recursive de l'arbre Qt -> (items, entries) dans l'ordre
        d'affichage : kind = folder | file (UserRole ('folder'|'file', path))."""
        items, entries = [], []

        def walk(item, depth):
            data = item.data(0, Qt.ItemDataRole.UserRole)
            kind = data[0] if isinstance(data, tuple) and data else ""
            # l'entree racine porte ('folder', root) : affichee comme dossier
            k = "file" if kind == "file" else "folder"
            items.append(item)
            entries.append({"label": item.text(0), "kind": k,
                            "depth": depth,
                            "search": item.text(0).lower()})
            for i in range(item.childCount()):
                walk(item.child(i), depth + 1)

        for i in range(self._tree.topLevelItemCount()):
            walk(self._tree.topLevelItem(i), 0)
        return items, entries

    def _payload(self) -> str:
        items, entries = self._collect()
        self._items = items
        return json.dumps({
            "entries": entries,
            "labels": {
                "search": t("panel.filter_files"),
                "empty": t("panel.working_copy"),
            },
        }, ensure_ascii=False)

    def push_reset(self) -> None:
        """Re-pousse l'arbre par le CANAL (jamais runJavaScript : autre
        monde JS)."""
        self.data_changed.emit(self._payload())

    @pyqtSlot(result=str)
    def get_entries(self) -> str:
        return self._payload()

    @pyqtSlot(int)
    def open_entry(self, idx: int) -> None:
        """Double-clic d'un FICHIER de la page -> le chemin EXACT du
        double-clic Qt (_on_working_double_clicked : verifie que l'entree
        est bien un fichier puis open_working_file_tab). Les dossiers ne
        s'ouvrent pas (parite Qt)."""
        if not (0 <= idx < len(self._items)):
            return
        self._mw._on_working_double_clicked(self._items[idx], 0)


def make_web_view(main_window, tree, parent=None):
    """Construit (QWidget vue, bridge) — a n'appeler que si is_available()."""
    from PyQt6.QtWebChannel import QWebChannel
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWidgets import QWidget, QVBoxLayout

    bridge = WorkspaceWebBridge(main_window, tree)

    class _View(QWidget):
        def __init__(self):
            super().__init__(parent)
            self._bridge = bridge
            self.view = QWebEngineView(self)
            lay = QVBoxLayout(self)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.addWidget(self.view)
            channel = QWebChannel(self)
            channel.registerObject("wsbridge", bridge)
            self.view.page().setWebChannel(channel)
            html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
            f = QFile(":/qtwebchannel/qwebchannel.js")
            js = ""
            if f.open(QIODevice.OpenModeFlag.ReadOnly):
                js = bytes(f.readAll()).decode("utf-8")
            html = html.replace("__QWEBCHANNEL_JS__", js)
            self.view.setHtml(html, QUrl("http://localhost/"))

        def refresh(self) -> None:
            bridge.push_reset()

    return _View(), bridge
