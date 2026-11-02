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

"""Vue web de l'EDITEUR ECF (chantier webapp, tranche « editeurs », 02/11)
: premier pas du couple editeur ECF — CONSULTATION/NAVIGATION seulement,
sur le modele de la vue web CSV (gui/csv_web_view.py).

REPARTITION STRICTE :
  - l'arbre QTreeWidget de EcfEditWidget RESTE la source de verite : le
    pont n'y ecrit JAMAIS, il lit les entrees (blocs, enfants, entetes de
    groupe, blocs commentes nativement) et renvoie la selection ;
  - un clic dans la page selectionne le meme item dans l'arbre Qt
    (setCurrentItem + scrollToItem + _on_block_selected, le chemin exact
    de la recherche Qt) : la table de proprietes et tout l'outillage
    existant suivent sans changement ;
  - la page ne fait AUCUN acces fichier ; pas d'edition dans cette
    tranche (elle viendra apres, miroir comme le CSV).

Tests : le pont et la bascule sont testes hors ligne (stub make_web_view
— un QWebEngineView reel sous offscreen bloque) ; le rendu Chromium ne
l'est pas.
"""
import json
from pathlib import Path

from PyQt6.QtCore import QObject, QUrl, QFile, QIODevice, pyqtSignal, pyqtSlot
from PyQt6.QtCore import Qt

from core.i18n import t

WEB_DIR = Path(__file__).resolve().parent / "web" / "ecf"

_AVAILABLE = None  # cache du test d'import (None = pas encore teste)

# cles de recherche d'un bloc (meme liste que _search_next du dialogue Qt)
_SEARCH_KEYS = ("Name", "CustomIcon", "TemplateRoot", "IndexName")


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


class EcfWebBridge(QObject):
    """Objet expose a la page : lecture des entrees de l'arbre ECF (blocs,
    enfants indentes, entetes de groupe, blocs commentes nativement) et
    selection miroiree dans l'arbre Qt (source de verite)."""

    data_changed = pyqtSignal(str)  # Python -> page : l'arbre a change

    def __init__(self, widget, parent=None):
        super().__init__(parent)
        self._widget = widget   # EcfEditWidget (l'arbre Qt reste la source)
        self._items = []        # QTreeWidgetItem parallele a entries

    def _collect(self):
        """Parcours recursive de l'arbre Qt (source de verite) ->
        (items, entries) : entries[kind, label, depth, search] dans l'ordre
        d'affichage ; kind = block (selectionnable) | header (repere de
        groupe) | gray (bloc commente nativement)."""
        from core.ecf.model import EcfBlock
        items, entries = [], []

        def push(item, depth):
            block = item.data(0, Qt.ItemDataRole.UserRole)
            selectable = bool(item.flags() & Qt.ItemFlag.ItemIsSelectable)
            label = item.text(0)
            if selectable:
                kind, search = "block", label
                if isinstance(block, EcfBlock):
                    for key in _SEARCH_KEYS:
                        val = block.get_property(key)
                        if val:
                            search += " " + val
            elif block is not None:
                kind, search = "gray", label
            else:
                kind, search = "header", ""
            items.append(item)
            entries.append({"label": label, "kind": kind,
                            "depth": depth, "search": search.lower()})

        def walk(item, depth):
            push(item, depth)
            for i in range(item.childCount()):
                walk(item.child(i), depth + 1)

        tree = self._widget.tree
        for i in range(tree.topLevelItemCount()):
            walk(tree.topLevelItem(i), 0)
        return items, entries

    def _payload(self) -> str:
        items, entries = self._collect()
        self._items = items
        current = self._widget.tree.currentItem()
        selected = -1
        for i, item in enumerate(items):
            if item is current:
                selected = i
                break
        return json.dumps({
            "name": self._widget.path.name,
            "entries": entries,
            "selected": selected,
            "labels": {"search": t("label.search")},
        }, ensure_ascii=False)

    def push_reset(self) -> None:
        """Re-pousse les entrees par le CANAL (jamais runJavaScript :
        autre monde JS, piege verifie deux fois)."""
        self.data_changed.emit(self._payload())

    @pyqtSlot(result=str)
    def get_entries(self) -> str:
        """Premier chargement de la page (elle TIRE ses donnees : un push
        emis pendant le chargement serait perdu)."""
        return self._payload()

    @pyqtSlot(int)
    def select_entry(self, idx: int) -> None:
        """Clic dans la page -> selection du MEME item dans l'arbre Qt :
        parents re-plies, setCurrentItem + scrollToItem + le meme chemin
        que itemClicked (_on_block_selected) pour la table de proprietes.
        Les entetes et blocs commentes ne sont pas selectionnables (parite
        avec les flags Qt)."""
        if not (0 <= idx < len(self._items)):
            return
        item = self._items[idx]
        if not (item.flags() & Qt.ItemFlag.ItemIsSelectable):
            return
        parent = item.parent()
        while parent is not None:
            parent.setExpanded(True)
            parent = parent.parent()
        w = self._widget
        w.tree.setCurrentItem(item)
        w.tree.scrollToItem(item)
        w._on_block_selected(item, 0)


def make_web_view(widget, parent=None):
    """Construit (QWidget vue, bridge) — a n'appeler que si is_available().
    Meme recette que la vue web CSV (qwebchannel.js injecte, origine
    http://localhost)."""
    from PyQt6.QtWebChannel import QWebChannel
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWidgets import QWidget, QVBoxLayout

    bridge = EcfWebBridge(widget)

    class _View(QWidget):
        def __init__(self):
            super().__init__(parent)
            self._bridge = bridge
            self.view = QWebEngineView(self)
            lay = QVBoxLayout(self)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.addWidget(self.view)
            channel = QWebChannel(self)
            channel.registerObject("ecfbridge", bridge)
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
