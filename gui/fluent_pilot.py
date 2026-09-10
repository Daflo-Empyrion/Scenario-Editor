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

"""Pilote PyQt-Fluent-Widgets sur la fenetre principale (decision du 09/09/2026).

Branche qfluentwidgets (PyQt6-Fluent-Widgets, branche PyQt6, GPL v3) sur le
CHROME de la fenetre principale -- boutons de la barre d'outils, titres des
trois panneaux, palette du moteur de styles Fluent -- sans toucher au reste
de l'application (editeurs et dialogues restent en QSS existant). Objectif :
juger le rendu sur du concret avant toute generalisation.

REVERSIBILITE (deux niveaux) :
  - reglage persistant fluent_pilot_enabled (menu Options > Interface Fluent
    (pilote), pris en compte au prochain lancement) ;
  - DEGRADE GRACIEUX comme core/win_backdrop : si qfluentwidgets n'est pas
    importable (exe construit sans la dependance, installation cassee...),
    toutes les fabriques retournent les widgets QPushButton/QLabel d'origine
    -- mise en page strictement identique, aucune difference fonctionnelle.

PARTICULARITE DES ICONES : un bouton Fluent standard a un fond clair suivant
le theme systeme, les icones blanches y seraient invisibles -- icon_color()
donne la couleur d'icone adaptee au type de bouton fabrique.
"""
from __future__ import annotations
from typing import Optional, Union

_AVAILABLE: Optional[bool] = None  # cache du test d'import (None = pas encore teste)


def is_available() -> bool:
    """qfluentwidgets est-il importable ? Resultat mis en cache : un echec
    d'import ne doit pas etre retente a chaque construction de bouton."""
    global _AVAILABLE
    if _AVAILABLE is None:
        try:
            import qfluentwidgets  # noqa: F401
            _AVAILABLE = True
        except Exception:
            _AVAILABLE = False
    return _AVAILABLE


def is_enabled() -> bool:
    """Pilote actif = reglage persiste ET bibliotheque disponible."""
    if not is_available():
        return False
    from core import settings
    return settings.get_fluent_pilot_enabled()


def icon_color(accent: bool = False) -> str:
    """Couleur d'icone adaptee au bouton fabrique par make_toolbar_button :
    blanc sur fond accent (comme avant le pilote), texte principal sur bouton
    Fluent standard dont le fond clair suivrait sinon le theme systeme."""
    if is_enabled() and not accent:
        from gui import theme as _theme
        return _theme.TEXT_DARK
    return "#ffffff"


def _compact(btn) -> None:
    """Resserre un bouton Fluent : les paddings par defaut (12 px de chaque
    cote) font demander a la barre d'outils ~1640 px pour ses 10 boutons
    contre 1501 en vanilla (metriques relevees sur ecran reel), soit ~140 px
    de trop pour la largeur historique de la fenetre. Padding 2 px + bordure
    neutre + min-width 0 ramene la demande a ~1620 px, pris en charge par la
    largeur par defaut elargie (voir default_window_size). setCustomStyleSheet
    = API officielle de la bibliotheque pour surcharger la qss des widgets
    Fluent, appliquee aux variantes claire ET sombre."""
    try:
        from qfluentwidgets import setCustomStyleSheet
        # padding 4px horizontal : 2px collait l'initiale du libelle a
        # l'icone (constate sur capture ecran reel) ; 4px respire sans
        # casser le budget de largeur de la barre (1680 px par defaut).
        qss = "PushButton{padding:2px 4px;border:none;min-width:0px;}"
        setCustomStyleSheet(btn, qss, qss)
    except Exception:
        pass


def default_window_size() -> tuple:
    """Taille par defaut de la fenetre principale : elargie quand le pilote
    est actif pour que la barre d'outils Fluent y tienne sans chevron (la
    config vanilla tient a 1500 px pile, le chrome Fluent demande ~1600 px) ;
    la barre reste redimensionnable et revient au chevron si l'utilisateur
    rapetisse la fenetre."""
    return (1680, 850) if is_enabled() else (1500, 800)


def make_toolbar_button(qicon, text: str, *, accent: bool = False):
    """Bouton de la barre d'outils principale. En mode pilote : PushButton /
    PrimaryPushButton de qfluentwidgets (sous-classes de QPushButton : meme
    API -- setIcon/setIconSize/setToolTip/clicked/setEnabled/setProperty) ;
    sinon QPushButton vanilla, comportement d'avant le pilote."""
    if is_enabled():
        try:
            from qfluentwidgets import PrimaryPushButton, PushButton
            btn = (PrimaryPushButton if accent else PushButton)(text)
            btn.setIcon(qicon)
            _compact(btn)
            # Verrou anti-ecrasement : contrairement au QPushButton vanilla
            # (minimumSizeHint == sizeHint), un PushButton Fluent accepte de
            # retrecir sous sa taille conseillee -- observe sur ecran reel,
            # la barre d'outils le comprimait alors JUSQU'A ROGNER SON TEXTE.
            # On fige le minimum au sizeHint : la barre repasse au chevron
            # d'extension plutot que de rogner.
            btn.ensurePolished()
            btn.setMinimumWidth(btn.sizeHint().width())
            return btn
        except Exception:
            pass
    from PyQt6.QtWidgets import QPushButton
    btn = QPushButton(qicon, text)
    return btn


def make_panel_label(text: str):
    """Titre de panneau (Scenario A / copie de travail / Scenario B) :
    StrongBodyLabel Fluent (typographie Segoe UI de la bibliotheque) sinon
    QLabel vanilla. La couleur/graisse themee est re-appliquee ensuite par
    _build_layout via setStyleSheet (prioritaire sur la qss Fluent)."""
    if is_enabled():
        try:
            from qfluentwidgets import StrongBodyLabel
            return StrongBodyLabel(text)
        except Exception:
            pass
    from PyQt6.QtWidgets import QLabel
    return QLabel(text)


def make_search_box():
    """Champ de filtrage des listes de fichiers : SearchLineEdit Fluent
    (loupe + bouton d'effacement natifs, retour de l'audit du 09/09/2026)
    sinon QLineEdit vanilla. Les deux exposent setPlaceholderText et
    textChanged(str) -- l'appelant branche identiquement."""
    if is_enabled():
        try:
            from qfluentwidgets import SearchLineEdit
            return SearchLineEdit()
        except Exception:
            pass
    from PyQt6.QtWidgets import QLineEdit
    return QLineEdit()


def _is_dark_bg(hex_color: str) -> bool:
    """Luminance simple d'un fond '#RRGGBB' (seuil 0.5) pour choisir le
    mode clair/sombre du moteur Fluent."""
    h = (hex_color or "").lstrip("#")
    if len(h) != 6:
        return False
    try:
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return False
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0 < 0.5


def sync_theme() -> None:
    """Pousse la couleur d'accent et le clair/sombre du theme courant dans le
    moteur Fluent -- a appeler APRES chaque gui.theme.apply_theme (premier
    lancement dans main(), puis chaque changement de theme). N'affecte que
    les widgets Fluent ; silencieux en mode pilote desactive."""
    if not is_enabled():
        return
    try:
        from qfluentwidgets import Theme, setTheme, setThemeColor
        from gui import theme as _theme
        # save=False : ne pas ecrire la config de qfluentwidgets (~/.config) --
        # la reference reste settings.json du projet.
        setTheme(Theme.DARK if _is_dark_bg(_theme.BG) else Theme.LIGHT, save=False)
        setThemeColor(_theme.PRIMARY, save=False)
    except Exception:
        # Le pilote ne doit JAMAIS empecher la fenetre de se construire
        # (meme philosophie que _apply_theme_backdrop).
        pass


def set_enabled(enabled: bool) -> None:
    from core import settings
    settings.set_fluent_pilot_enabled(enabled)
