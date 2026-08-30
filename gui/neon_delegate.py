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
Selection « neon » (halo lumineux + liseré + texte eclaire) pour les themes
qui la demandent (palette core/themes.py, cle optionnelle "neon_selection" --
theme "h" Verrière néon uniquement).

Principe : un QStyledItemDelegate installe UNE FOIS sur une vue ; a chaque
paint, il consulte l'etat courant du theme (gui.theme.CURRENT_THEME_ID) :
- theme sans "neon_selection" (ou item non selectionne) -> rendu standard
  STRICTEMENT identique (super().paint avec l'option d'origine, aucun
  changement visible, aucun cout) ;
- theme neon + selection -> trois traits concentriques d'opacite
  decroissante (effet bloom autour de la ligne), un liseré net, un
  remplissage translucide (la ligne reste lisible, le halo s'AJOUTE a la
  surbrillance), puis le texte est dessine en clair via l'option modifiee
  (l'etat Selected est retire pour neutraliser le fond standard).

Le delegue est installe inconditionnellement sur les vues principales
(ecf_edit_widget, bandeau A/copie/B de main_window) : basculer de theme
dans Options ne demande AUCUN rebranchement, le changement est immediat.
"""
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPalette
from PyQt6.QtWidgets import QStyledItemDelegate, QStyle, QStyleOptionViewItem

_NEON = QColor(0, 229, 255)          # #00E5FF -- accent du theme Verriere
_NEON_BRIGHT = QColor("#7DF6FF")     # liseré et texte

# (largeur du trait, alpha) du plus large au plus fin -- l'empilement crée
# l'effet de halo lumineux (bloom) autour de la selection.
_BLOOM_STROKES = ((7.0, 26), (4.5, 55), (2.5, 120))


def neon_selection_active() -> bool:
    """True si le theme COURANT demande la selection neon. Lu a chaque
    paint (dictionnaire Python : coût negligeable face au rendu)."""
    from core.themes import get_palette
    from gui.theme import CURRENT_THEME_ID
    return bool(get_palette(CURRENT_THEME_ID).get("neon_selection"))


class NeonItemDelegate(QStyledItemDelegate):
    """Delegue de selection neon -- voir docstring du module."""

    def paint(self, painter, option, index) -> None:
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        if not (selected and neon_selection_active()):
            super().paint(painter, option, index)
            return

        rect = QRectF(option.rect.adjusted(1, 0, -1, 0))
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for width_f, alpha in _BLOOM_STROKES:
            pen = QPen(_NEON)
            pen.setWidthF(width_f)
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            pen.setColor(QColor(_NEON.red(), _NEON.green(), _NEON.blue(), alpha))
            painter.setPen(pen)
            painter.drawRoundedRect(rect, 6, 6)
        painter.setPen(QPen(_NEON_BRIGHT, 1.2))
        painter.setBrush(QColor(_NEON.red(), _NEON.green(), _NEON.blue(), 34))
        painter.drawRoundedRect(rect, 5, 5)
        painter.restore()

        # Texte par-dessus le halo : l'etat Selected est retire pour que le
        # style standard ne repeigne PAS son fond de surbrillance par-dessus.
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.state &= ~QStyle.StateFlag.State_Selected
        opt.palette.setColor(QPalette.ColorRole.Text, _NEON_BRIGHT)
        opt.font = QFont(opt.font)
        opt.font.setBold(True)
        super().paint(painter, opt, index)
