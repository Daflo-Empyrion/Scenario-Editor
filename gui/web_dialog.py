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

"""Gabarit de dialogue web (chantier « application entiere en webapp »,
02/11) : le moule commun que les prochains dialogues converts utiliseront.

Principe : un dialogue web = une page HTML (gui/web/<nom>/index.html) + un
pont QObject expose via QWebChannel + une classe minuscule heritant de
WebDialog qui assemble les deux. Le gabarit fournit :
  - le chargement de page (qwebchannel + fond + origin locale) ;
  - l'injection des libelles t() (aucun texte en dur dans la page) ;
  - le style verre 2026 homogene ;
  - la geometry persistee (gui.window_geometry.track).

Usage type (voir les converts futurs) :
    class MonBridge(WebBridge):
        @pyqtSlot(result=str)
        def get_data(self): ...
    class MonDialog(WebDialog):
        WEB_DIR = Path(__file__).parent / "web" / "mon"
        BRIDGE_FACTORY = staticmethod(make_mon_bridge)
    dlg = MonDialog(parent); dlg.exec()

Testabilite : les tests ne construisent JAMAIS le QWebEngineView sous
offscreen (Chromium y bloque) — ils testent le pont seul (meme parti pris
que tech_tree_web/csv_web_view).
"""
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QDialog, QVBoxLayout

from gui.web_common import local_origin, load_html


class WebBridge(QObject):
    """Base des ponts de dialogues web : porteur du signal de mise a jour
    poussee Python -> page (le seul canal fiable — runJavaScript s'execute
    dans un autre monde JS, piege verifie deux fois)."""

    data_changed = pyqtSignal(str)

    def push_reset(self) -> None:
        self.data_changed.emit("")


class WebDialog(QDialog):
    """Assemble page web + pont dans un QDialog a geometry persistee.
    Les sous-classes definissent WEB_DIR, BRIDGE_FACTORY et construisent
    leur pont avant d'appeler super().__init__()."""

    WEB_DIR: Path = None
    BRIDGE_FACTORY = None          # callable(parent) -> (bridge, html_extras)
    DIALOG_KEY: str = ""           # cle de geometry persistee

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bridge = self.BRIDGE_FACTORY(self)
        self.view = self._make_view()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.view)
        if self.DIALOG_KEY:
            from gui.window_geometry import track
            track(self, self.DIALOG_KEY)

    def _make_view(self):
        from PyQt6.QtWebChannel import QWebChannel
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        view = QWebEngineView(self)
        channel = QWebChannel(view)
        channel.registerObject("bridge", self._bridge)
        view.page().setWebChannel(channel)
        html = load_html(self.WEB_DIR, with_background=True)
        view.setHtml(html, local_origin())
        return view

    def refresh(self) -> None:
        """Re-pousse les donnees vers la page (par le canal QWebChannel —
        JAMAIS runJavaScript : autre monde JS)."""
        self._bridge.push_reset()
