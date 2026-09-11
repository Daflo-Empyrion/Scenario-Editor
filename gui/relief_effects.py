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
Utilitaires du look Relief niveau 2 : VRAIES ombres portees sur les
elements flottants de l'application (fiche info v1.6.7, zoom d'icone
phase 2, tout futur element frameless).

Principe valide sur la fiche info (11/09/2026) : QSS ne connait PAS
box-shadow, et un QGraphicsDropShadowEffect applique au widget d'une
fenetre frameless est ROGNE aux limites de la fenetre. Il faut donc :
fenetre WA_TranslucentBackground + marge transparente tout autour
(SHADOW_MARGINS, plus large en bas pour l'offset de l'ombre) + cadre
interne portant fond/bordure biseauee + effet sur le cadre.

Les couleurs du biseau viennent de la palette du theme ACTIF (cle
optionnelle "bevel_card" des themes Relief, posee sur "k" et "l") -- pas
de valeurs codees en dur, le cadre suit le theme clair comme nuit.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QVBoxLayout

# gauche, haut, droite, bas -- valeurs validees sur la fiche info (v1.6.7).
SHADOW_MARGINS = (12, 10, 16, 26)
_BLUR, _DY, _ALPHA = 34, 12, 185

# Repli si une palette Relief future oubliait "bevel_card" : biseau nuit.
_DEFAULT_BEVEL = ("#4c4c57", "#45454f", "#0b0b0f", "#101014")


def is_relief_active() -> bool:
    from gui.theme import is_relief_theme
    return is_relief_theme()


def card_bevel() -> tuple:
    """(haut, gauche, bas, droite) du cadre biseaute, relus dans la palette
    du theme ACTIF a chaque appel (l'utilisateur peut changer de theme a
    l'execution ; une fiche/zoom cree APRES voit le nouveau biseau)."""
    from core.themes import get_palette
    from gui import theme
    return get_palette(theme.CURRENT_THEME_ID).get("bevel_card", _DEFAULT_BEVEL)


def bevel_qss(bg: str, border: str) -> str:
    """Fragment QSS du cadre biseaute (bord haut/gauche eclaires, bas/droite
    profonds) sur fond `bg`, bordure de base `border`."""
    top, left, bottom, right = card_bevel()
    return (f"QFrame {{ background: {bg}; border: 1px solid {border}; "
            f"border-top-color: {top}; border-left-color: {left}; "
            f"border-bottom-color: {bottom}; border-right-color: {right}; "
            f"border-radius: 8px; }}")


def apply_window_shadow(window, frame) -> None:
    """Pose l'effet d'ombre sur `frame`. L'appelant doit AU PREALABLE avoir
    mis la fenetre translucide et installe `frame` derriere des marges de
    layout = SHADOW_MARGINS (voir shadow_container pour la combinaison
    complete) -- sinon l'ombre est rogee aux limites de la fenetre."""
    window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    effect = QGraphicsDropShadowEffect(window)
    effect.setBlurRadius(_BLUR)
    effect.setOffset(0, _DY)
    effect.setColor(QColor(0, 0, 0, _ALPHA))
    frame.setGraphicsEffect(effect)


def shadow_container(window, bg: str, border: str, content_margins=(6, 6, 6, 6)):
    """Fabrique le conteneur d'un element flottant : HORS Relief, la fenetre
    elle-meme avec ses marges de contenu (rendu identique a l'ancien) ; EN
    Relief, cadre interne biseaute + ombre portee reelle. Retourne
    (widget_a_peupler, layout_a_remplir) -- le code appelant est identique
    dans les deux cas."""
    if not is_relief_active():
        lay = QVBoxLayout(window)
        lay.setContentsMargins(*content_margins)
        return window, lay
    frame = QFrame(window)
    frame.setStyleSheet(bevel_qss(bg, border))
    outer = QVBoxLayout(window)
    outer.setContentsMargins(*SHADOW_MARGINS)
    outer.addWidget(frame)
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(*content_margins)
    apply_window_shadow(window, frame)
    return frame, lay
