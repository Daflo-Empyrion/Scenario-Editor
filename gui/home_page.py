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

"""Page d'accueil / launchpad de la fenetre principale (chantier webapp,
02/11) : premier onglet de la fenetre, projets recents cliquables, acces
rapides nouveau projet / gestionnaire.

Reversible par nature : si PyQt6-WebEngine manque ou plateforme offscreen
(tests/CI), make_home_view() retourne None et la fenetre se construit sans
l'onglet (aucune difference fonctionnelle).
"""
import json
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from gui.web_common import local_origin, load_html

WEB_DIR = Path(__file__).resolve().parent / "web" / "home"


def is_available() -> bool:
    """Page d'accueil possible : WebEngine importable, index present, et
    PAS sous la plateforme offscreen (la creation d'un QWebEngineView y
    bloque — piege verifie 01/11 ; les tests stubbent la vue)."""
    import os
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        return False
    try:
        from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
        from PyQt6.QtWebChannel import QWebChannel  # noqa: F401
        return (WEB_DIR / "index.html").is_file()
    except Exception:
        return False


class HomeBridge(QObject):
    """Pont de la page d'accueil : projets recents + actions (les actions
    deleguent aux methodes EXISTANTES de la fenetre principale)."""

    data_changed = pyqtSignal(str)   # Python -> page : recents re-pousses

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._mw = main_window

    def push_reset(self) -> None:
        """Re-pousse les donnees (apres l'ouverture d'un projet par exemple)."""
        self.data_changed.emit(self.get_home())

    @pyqtSlot(result=str)
    def get_home(self) -> str:
        from core.i18n import t
        from core import project_store
        recents = []
        try:
            for record in project_store.load_recent_projects():
                recents.append({"name": record.display_name(),
                                "path": record.working})
        except Exception:
            recents = []
        return json.dumps({
            "recents": recents,
            "labels": {
                "title": t("home.title"),
                "subtitle": t("home.subtitle"),
                "new_project": t("menu.file.new_project"),
                "manage": t("menu.file.recent_projects"),
                "recent": t("home.recent"),
                "open": t("home.open"),
                "no_recents": t("home.no_recents"),
                "footer": t("home.footer"),
            },
        }, ensure_ascii=False)

    @pyqtSlot(str)
    def open_recent(self, path: str) -> None:
        from core import project_store
        for record in project_store.load_recent_projects():
            if record.working == path:
                try:
                    self._mw.open_existing_project(record)
                except Exception:
                    pass
                return

    @pyqtSlot()
    def new_project(self) -> None:
        self._mw.new_project_dialog()

    @pyqtSlot()
    def manage_projects(self) -> None:
        self._mw.show_startup_dialog()


def make_home_view(main_window, parent=None):
    """Construit (QWidget, HomeBridge) — a n'appeler que si
    is_available() (garde offscreen incluse)."""
    from PyQt6.QtWebChannel import QWebChannel
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWidgets import QVBoxLayout, QWidget

    bridge = HomeBridge(main_window)

    class _View(QWidget):
        def refresh(self) -> None:
            bridge.push_reset()

    view = QWebEngineView()
    channel = QWebChannel(view)
    channel.registerObject("homebridge", bridge)
    view.page().setWebChannel(channel)
    view.setHtml(load_html(WEB_DIR, with_background=True), local_origin())
    w = _View(parent)
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.addWidget(view)
    return w, bridge
