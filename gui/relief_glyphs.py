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

"""
Pack d'icones "Relief" (phase 2 du look 3D, 12/09/2026).

Glyphes SVG DESSINES POUR LE PROJET (aucune ressource tierce : meme licence
GPLv3 que le depot), rendus A LA DEMANDE avec un degrade biseaute derive de
la couleur demandee : haut eclaire, bas ombré, contour profond + couche
"profondeur" decalee vers le bas -- la meme icone reste lisible sur bouton
primaire (bleu), bouton secondaire, champ en creux ou fiche info noire, en
theme nuit comme en theme clair, sans dupliquer les fichiers par variante.

Consommation : gui/theme.icon() interroge relief_icon() AVANT qtawesome
quand un theme Relief est actif ; repli qtawesome si QtSvg manque ou nom
inconnu (aucun crash possible). Les glyphes sont en viewBox 24x24, style
trait rond (stroke-linecap round), sans texte.
"""
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap

try:
    from PyQt6.QtSvg import QSvgRenderer
    _HAS_SVG = True
except ImportError:  # PyInstaller : QtSvg normalement embarque avec QtGui
    _HAS_SVG = False

# --- Glyphes (24x24). mode "stroke" : trait degrade + ombre decalee ;
# mode "fill" : forme pleine degradee (contour + ombre). --------------------
_G = {
    "fa5s.arrow-up": {"mode": "stroke",
        "b": '<path d="M12 19 V5.4"/><path d="M5.6 11.6 L12 5.2 L18.4 11.6"/>'},
    "fa5s.balance-scale": {"mode": "stroke",
        "b": '<path d="M12 4 V19"/><path d="M6.4 19 H17.6"/><path d="M4 8.6 H20"/>'
             '<path d="M12 4.2 L4.2 8.4 M12 4.2 L19.8 8.4"/>'
             '<path d="M4.2 8.6 L1.8 14.4 M4.2 8.6 L6.6 14.4"/><path d="M1.8 14.4 A2.4 2.4 0 0 0 6.6 14.4"/>'
             '<path d="M19.8 8.6 L17.4 14.4 M19.8 8.6 L22.2 14.4"/><path d="M17.4 14.4 A2.4 2.4 0 0 0 22.2 14.4"/>'},
    "fa5s.ban": {"mode": "stroke",
        "b": '<circle cx="12" cy="12" r="8.2"/><path d="M6.3 6.3 L17.7 17.7"/>'},
    "fa5s.book-open": {"mode": "stroke",
        "b": '<path d="M12 6.2 C10.2 4.7 7.2 4.2 3.8 4.7 V18.2 C7.2 17.7 10.2 18.2 12 19.7 '
             'C13.8 18.2 16.8 17.7 20.2 18.2 V4.7 C16.8 4.2 13.8 4.7 12 6.2 Z"/>'
             '<path d="M12 6.4 V19.5"/>'},
    "fa5s.box-open": {"mode": "stroke",
        "b": '<path d="M3.8 10.4 L12 13.8 L20.2 10.4 V17.8 L12 21.2 L3.8 17.8 Z"/>'
             '<path d="M3.8 10.4 L8.2 6.9 M20.2 10.4 L15.8 6.9"/><path d="M12 13.8 V20.8"/>'},
    "fa5s.bug": {"mode": "stroke",
        "b": '<ellipse cx="12" cy="13.6" rx="4.5" ry="5.6"/><path d="M12 8.2 V19"/>'
             '<path d="M9.5 7.4 L7.9 4.9 M14.5 7.4 L16.1 4.9"/>'
             '<path d="M7.5 11.4 H4.3 M7.6 14.9 H4.8 M16.5 11.4 H19.7 M16.4 14.9 H19.2"/>'},
    "fa5s.calculator": {"mode": "stroke",
        "b": '<rect x="6" y="3.2" width="12" height="17.6" rx="2"/><path d="M9 6.8 H15"/>'
             '<path d="M9.1 11 H9.11 M12 11 H12.01 M14.9 11 H14.91 M9.1 14.3 H9.11 M12 14.3 H12.01 '
             'M14.9 14.3 H14.91 M9.1 17.6 H9.11 M12 17.6 H12.01 M14.9 17.6 H14.91"/>'},
    "fa5s.caret-down": {"mode": "fill",
        "b": '<path d="M6.4 9 L12 15.2 L17.6 9 Z"/>'},
    "fa5s.chart-bar": {"mode": "stroke",
        "b": '<path d="M3.6 20.4 H20.4"/><path d="M6.6 20.4 V13 M12 20.4 V5.6 M17.4 20.4 V9.6"/>'},
    "fa5s.check": {"mode": "stroke",
        "b": '<path d="M4.6 12.7 L9.8 17.9 L19.4 6.4"/>'},
    "fa5s.clipboard-check": {"mode": "stroke",
        "b": '<path d="M8.6 5.6 H6.5 A1.9 1.9 0 0 0 4.6 7.5 V18.9 A1.9 1.9 0 0 0 6.5 20.8 '
             'H17.5 A1.9 1.9 0 0 0 19.4 18.9 V7.5 A1.9 1.9 0 0 0 17.5 5.6 H15.4"/>'
             '<rect x="8.6" y="3.2" width="6.8" height="3.5" rx="1.1"/>'
             '<path d="M9.4 13 L11.5 15.4 L15.2 10.7"/>'},
    "fa5s.clone": {"mode": "stroke",
        "b": '<rect x="8.7" y="8.7" width="11.8" height="11.8" rx="2"/>'
             '<path d="M15.3 4.7 H6.7 A2 2 0 0 0 4.7 6.7 V15.3"/>'},
    "fa5s.copy": {"mode": "stroke",
        "b": '<rect x="8.9" y="8.9" width="11.6" height="11.6" rx="2"/>'
             '<path d="M14.5 5.1 H6.9 A2.2 2.2 0 0 0 4.7 7.3 V14.9"/>'},
    "fa5s.exchange-alt": {"mode": "stroke",
        "b": '<path d="M20 8.1 H6"/><path d="M16.4 4.5 L20 8.1 L16.4 11.7"/>'
             '<path d="M4 15.9 H18"/><path d="M7.6 12.3 L4 15.9 L7.6 19.5"/>'},
    "fa5s.external-link-alt": {"mode": "stroke",
        "b": '<path d="M10.4 5.3 H6 A2 2 0 0 0 4 7.3 V18 A2 2 0 0 0 6 20 H16.7 A2 2 0 0 0 18.7 18 V13.6"/>'
             '<path d="M14.2 3.7 H20.3 V9.8"/><path d="M20.1 3.9 L11.9 12.1"/>'},
    "fa5s.file-export": {"mode": "stroke",
        "b": '<path d="M13.4 3.5 H6.7 A1.8 1.8 0 0 0 4.9 5.3 V18.7 A1.8 1.8 0 0 0 6.7 20.5 '
             'H17.3 A1.8 1.8 0 0 0 19.1 18.7 V9.2 Z"/><path d="M13.4 3.5 V9.2 H19.1"/>'
             '<path d="M8.3 14.7 H14.7"/><path d="M12.3 12.1 L14.9 14.7 L12.3 17.3"/>'},
    "fa5s.filter": {"mode": "stroke",
        "b": '<path d="M4.2 4.9 H19.8 L14 12.3 V18.5 L10 20.8 V12.3 Z"/>'},
    "fa5s.folder-open": {"mode": "stroke",
        "b": '<path d="M20.3 18.4 H4.4 A1.4 1.4 0 0 1 3 17 V6.7 A1.6 1.6 0 0 1 4.6 5.1 H9 '
             'L11.2 7.9 H18.7 A1.6 1.6 0 0 1 20.3 9.5 V10.7"/>'
             '<path d="M3.5 18.2 L5.9 11.3 H21.3 L18.9 18.2 Z"/>'},
    "fa5s.globe": {"mode": "stroke",
        "b": '<circle cx="12" cy="12" r="8.3"/><ellipse cx="12" cy="12" rx="3.8" ry="8.3"/>'
             '<path d="M4 9.2 H20 M4 14.8 H20"/>'},
    "fa5s.info-circle": {"mode": "stroke",
        "b": '<circle cx="12" cy="12" r="8.3"/><path d="M12 11.2 V16.5"/><path d="M12 7.9 H12.01"/>'},
    "fa5s.language": {"mode": "stroke",
        "b": '<path d="M3.6 19.8 L8.3 8.4 L13 19.8"/><path d="M5.5 15.4 H11.1"/>'
             '<path d="M14.6 4.7 H20.2"/><path d="M17.4 4.7 C17.4 8 15.7 10.6 13.2 12.2"/>'
             '<path d="M14.3 7.1 C15.5 9.8 17.4 11.7 20.4 12.7"/>'
             '<path d="M13 13.5 C15 16.4 17.6 18.4 20.8 19.4"/>'},
    "fa5s.palette": {"mode": "stroke",
        "b": '<path d="M12 3.7 A8.3 8.3 0 1 0 12 20.3 C13.4 20.3 14 19.3 13.6 18.3 '
             'C13.2 17.1 14 15.9 15.6 15.9 H17.7 A2.7 2.7 0 0 0 20.3 13.2 C20.3 7.7 16.4 3.7 12 3.7 Z"/>'
             '<path d="M7.6 9.1 H7.61 M11 6.9 H11.01 M15.1 7.9 H15.11 M6.9 13.1 H6.91"/>'},
    "fa5s.paper-plane": {"mode": "stroke",
        "b": '<path d="M21 3.7 L3.3 10.6 L9.2 13"/><path d="M21 3.7 L15.3 20.6 L9.2 13"/><path d="M21 3.7 L9.2 13"/>'},
    "fa5s.pen": {"mode": "stroke",
        "b": '<path d="M15.6 4.6 L19.4 8.4 L8 19.8 H4.2 V16 Z"/><path d="M13.6 6.6 L17.4 10.4"/>'},
    "fa5s.plus": {"mode": "stroke",
        "b": '<path d="M12 5.2 V18.8 M5.2 12 H18.8"/>'},
    "fa5s.save": {"mode": "stroke",
        "b": '<path d="M5.5 3.6 H15.5 L20.4 8.5 V18.5 A1.9 1.9 0 0 1 18.5 20.4 H5.5 '
             'A1.9 1.9 0 0 1 3.6 18.5 V5.5 A1.9 1.9 0 0 1 5.5 3.6 Z"/>'
             '<path d="M7.7 3.6 V8.9 H15.3 V3.6"/><rect x="7.7" y="13.1" width="8.6" height="7.3"/>'},
    "fa5s.search": {"mode": "stroke",
        "b": '<circle cx="10.6" cy="10.6" r="6.4"/><path d="M15.4 15.4 L20.7 20.7"/>'},
    "fa5s.sync": {"mode": "stroke",
        "b": '<path d="M4.5 4.9 V9.7 H9.3"/><path d="M4.9 9.5 A7.5 7.5 0 0 1 18.2 6.7"/>'
             '<path d="M19.5 19.1 V14.3 H14.7"/><path d="M19.1 14.5 A7.5 7.5 0 0 1 5.8 17.3"/>'},
    "fa5s.sync-alt": {"mode": "stroke",
        "b": '<path d="M20 8.2 H6"/><path d="M9.8 4.4 L6 8.2 L9.8 12"/>'
             '<path d="M4 15.8 H18"/><path d="M14.2 12 L18 15.8 L14.2 19.6"/>'},
    "fa5s.times": {"mode": "stroke",
        "b": '<path d="M6.3 6.3 L17.7 17.7 M17.7 6.3 L6.3 17.7"/>'},
    "fa5s.trash": {"mode": "stroke",
        "b": '<path d="M4.6 6.7 H19.4"/><path d="M9.2 6.7 V4.9 A1.2 1.2 0 0 1 10.4 3.7 H13.6 '
             'A1.2 1.2 0 0 1 14.8 4.9 V6.7"/>'
             '<path d="M6.7 6.7 L7.5 19.2 A1.6 1.6 0 0 0 9.1 20.6 H14.9 A1.6 1.6 0 0 0 16.5 19.2 '
             'L17.3 6.7"/><path d="M10.1 10.5 V16.8 M13.9 10.5 V16.8"/>'},
    "fa5s.trash-alt": {"mode": "stroke",
        "b": '<path d="M4.6 6.8 H19.4"/>'
             '<path d="M6.7 6.8 L7.5 19.2 A1.6 1.6 0 0 0 9.1 20.6 H14.9 A1.6 1.6 0 0 0 16.5 19.2 '
             'L17.3 6.8"/><path d="M9.2 6.8 V4.9 A1.2 1.2 0 0 1 10.4 3.7 H13.6 A1.2 1.2 0 0 1 '
             '14.8 4.9 V6.8"/>'},
    "fa5s.undo": {"mode": "stroke",
        "b": '<path d="M8.2 4.7 L3.7 9.2 L8.2 13.7"/><path d="M3.9 9.2 H14.3 A5.7 5.7 0 0 1 14.3 20.6 H9.9"/>'},
    # glyphe generique de la fiche info (_GENERIC_ICON_NAME) : cube isometrique
    "fa5s.cube": {"mode": "stroke",
        "b": '<path d="M12 3.4 L20 7.8 V16.2 L12 20.6 L4 16.2 V7.8 Z"/><path d="M4.2 8 L12 12.3 '
             'L19.8 8"/><path d="M12 12.3 V20.4"/>'},
}

_SIZES = (64, 128)          # pixmaps rendus (devicePixelRatio 2 -> 32/64 logiques)
_cache = {}                 # (nom, couleur) -> QIcon


def _build_svg(body: str, mode: str, color: QColor) -> str:
    """Assemble le SVG complet : couche 'profondeur' (decalee vers le bas,
    contour fonce translucide) puis couche dessus (degrade haut eclaire ->
    bas ombre). Les nuances derivees de `color` gardent la logique biseau
    du theme Relief quelle que soit la couleur demandee."""
    top = color.lighter(165).name()
    bottom = color.darker(122).name()
    edge = color.darker(185).name()
    if mode == "fill":
        base = (f'<g fill="url(#rg)" stroke="{edge}" stroke-width="1.1" '
                f'stroke-opacity="0.75" stroke-linejoin="round">{body}</g>')
        under = (f'<g fill="{edge}" fill-opacity="0.6" stroke="none" '
                 f'transform="translate(0,1)">{body}</g>')
    else:
        base = (f'<g fill="none" stroke="url(#rg)" stroke-width="2.2" '
                f'stroke-linecap="round" stroke-linejoin="round">{body}</g>')
        under = (f'<g fill="none" stroke="{edge}" stroke-opacity="0.55" stroke-width="2.4" '
                 f'stroke-linecap="round" stroke-linejoin="round" '
                 f'transform="translate(0,1)">{body}</g>')
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        f'<defs><linearGradient id="rg" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{top}"/>'
        f'<stop offset="1" stop-color="{bottom}"/>'
        '</linearGradient></defs>'
        f'{under}{base}</svg>'
    )


def relief_icon(name: str, color):
    """QIcon relief pour `name` (cle fa5s.*), ou None si QtSvg manque, nom
    inconnu ou SVG invalide -- le repli qtawesome est gere par l'appelant
    (gui.theme.icon), jamais d'exception remontee a l'UI. `color` accepte
    une chaine hex ou un QColor (l'app existe : fiche info passe QColor)."""
    if not _HAS_SVG:
        return None
    spec = _G.get(name)
    if spec is None:
        return None
    try:
        qcolor = color if isinstance(color, QColor) else QColor(color)
        hex_color = qcolor.name()
    except Exception:
        return None
    key = (name, hex_color)
    cached = _cache.get(key)
    if cached is not None:
        return cached
    try:
        svg_bytes = _build_svg(spec["b"], spec["mode"], qcolor).encode("utf-8")
        renderer = QSvgRenderer(svg_bytes)
        if not renderer.isValid():
            return None
        # Pixmaps BRUTS (pas de setDevicePixelRatio : ses infos dpr ne sont
        # pas honorees par QIcon.paint sur toutes les plateformes -- sonde
        # 12/09/2026 : icone peinte 2x trop grande puis rogee). QIcon
        # redimensionne lui-meme le pixmap le plus proche de la taille
        # demandee par chaque bouton.
        icon = QIcon()
        for px in _SIZES:
            pm = QPixmap(px, px)
            pm.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pm)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            renderer.render(painter, QRectF(0, 0, px, px))
            painter.end()
            icon.addPixmap(pm)
    except Exception:
        return None
    _cache[key] = icon
    return icon
