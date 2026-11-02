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

"""Infrastructure commune des vues web (chantier « webapp », 2026).

Toutes les pages web de l'application (arbre technologique, editeur CSV,
accueil...) partagent :
  - l'injection de qwebchannel.js depuis les ressources Qt (jamais de
    serveur local) ;
  - le fond nebuleuse (gui/web/bg.jpg, genere par _maquettes/make_bg.py)
    embarque en data-URI — une image RELATIVE ne se charge pas depuis
    setHtml (origine http://localhost) et une data-URI CSS ne s'affiche
    pas de facon fiable ;
  - l'origine http://localhost (requis par setHtml pour le canal).
"""
import base64
from pathlib import Path

from PyQt6.QtCore import QUrl

WEB_ROOT = Path(__file__).resolve().parent / "web"


def load_html(web_dir: Path, replacements: dict | None = None,
              with_background: bool = False) -> str:
    """Lit `web_dir/index.html`, injecte qwebchannel.js (placeholder
    __QWEBCHANNEL_JS__), le fond nebuleuse (__BG_DATA_URI__ si demande)
    et les remplacements supplementaires {placeholder: valeur}."""
    html = (Path(web_dir) / "index.html").read_text(encoding="utf-8")
    from PyQt6.QtCore import QFile, QIODevice
    f = QFile(":/qtwebchannel/qwebchannel.js")
    js = ""
    if f.open(QIODevice.OpenModeFlag.ReadOnly):
        js = bytes(f.readAll()).decode("utf-8")
    html = html.replace("__QWEBCHANNEL_JS__", js)
    if with_background:
        html = html.replace("__BG_DATA_URI__", bg_data_uri())
    for key, value in (replacements or {}).items():
        html = html.replace(key, value)
    return html


def bg_data_uri() -> str:
    """Fond nebuleuse embarque (data-URI base64) — fichier partage
    gui/web/bg.jpg ; vide si absent (la page garde son fond degrade)."""
    bg = WEB_ROOT / "bg.jpg"
    if not bg.is_file():
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(bg.read_bytes()).decode("ascii")


def local_origin() -> QUrl:
    """Origine a passer a setHtml (le canal QWebChannel exige une origine
    http ; 'file:' n'est pas navigable)."""
    return QUrl("http://localhost/")
