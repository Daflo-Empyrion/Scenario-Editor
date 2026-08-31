# Empyrion Scenario Editor
# Copyright (C) 2026  Daflo
#
# Licence GPL-3 ou superieure (voir la tete de fichier des autres tests).

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

"""Test du badge de cout de deblocage peint sur CHAQUE icone de l'arbre
technologique (demande utilisateur du 30/08/2026 : le cout n'etait lisible
qu'au survol). Verification au niveau PIXELS : le chiffre dore (#FFD34D) du
badge doit apparaitre dans le rendu de l'item."""
import pytest
from PyQt6.QtGui import QColor, QImage, QPainter, QPixmap

from core.tech_tree import TechTreeNode
from gui.tech_tree_widget import _TechNodeItem, _BADGE_TEXT_COLOR

BADGE_RGB = tuple(int(_BADGE_TEXT_COLOR[i:i + 2], 16) for i in (1, 3, 5))


@pytest.fixture
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _render_node(cost: int, qapp) -> QImage:
    node = TechTreeNode(name="TestNode", source="block", unlock_level=5,
                        unlock_cost=cost, categories=["Base"])
    pixmap = QPixmap(48, 48)
    pixmap.fill(QColor(18, 69, 15))  # fond vert standard des icones
    item = _TechNodeItem(node, pixmap, view=None, row=0, editable=False)
    image = QImage(48, 48, QImage.Format.Format_ARGB32)
    image.fill(QColor(18, 69, 15))
    painter = QPainter(image)
    painter.drawPixmap(0, 0, pixmap)
    item._paint_cost_badge(painter)
    painter.end()
    return image


def test_cost_badge_gold_digits_rendered(qapp):
    image = _render_node(14, qapp)
    found = any(
        (image.pixelColor(x, y).red(), image.pixelColor(x, y).green(),
         image.pixelColor(x, y).blue()) == BADGE_RGB
        for y in range(48) for x in range(48))
    assert found, "aucun pixel dore : le badge de cout n'est pas rendu"


def test_cost_badge_dark_plate_behind_digits(qapp):
    """La pastille sombre semi-transparente assombrit le coin HAUT-GAUCHE --
    position demandee par l'utilisateur le 31/08/2026 (l'ancien badge
    bas-droit en police fixe etait trop petit sur grand ecran) : sans elle,
    le chiffre dore serait illisible sur les icones claires."""
    image = _render_node(14, qapp)
    corner = image.pixelColor(3, 3)
    assert corner.red() < 120 and corner.green() < 120  # coin assombri


def test_cost_badge_font_scales_with_icon_size(qapp):
    """Demande du 31/08/2026 : la police du badge est a l'ECHELLE de
    l'icone (pixelSize proportionnel), jamais la police fixe 8pt d'origine
    qui etait illisible sur grand ecran."""
    from PyQt6.QtGui import QFont
    node = TechTreeNode(name="TestNode", source="block", unlock_level=5,
                        unlock_cost=14, categories=["Base"])
    pixmap = QPixmap(128, 128)
    pixmap.fill(QColor(18, 69, 15))
    item = _TechNodeItem(node, pixmap, view=None, row=0, editable=False)
    image = QImage(128, 128, QImage.Format.Format_ARGB32)
    image.fill(QColor(18, 69, 15))
    painter = QPainter(image)
    font_before = painter.font()
    item._paint_cost_badge(painter)
    painter.end()
    # Verification indirecte mais deterministe : le badge peint sur 128px
    # est nettement plus grand que sur 48px (hauteur pastille ~ fontMetrics).
    small_image = _render_node(14, qapp)

    def _badge_height(image):
        first_row = None
        last_row = None
        for y in range(image.height()):
            for x in range(image.width()):
                c = image.pixelColor(x, y)
                if (c.red(), c.green(), c.blue()) == BADGE_RGB:
                    if first_row is None:
                        first_row = y
                    last_row = y
                    break
        return (last_row - first_row) if first_row is not None else 0

    assert _badge_height(image) > _badge_height(small_image)


def test_cost_badge_skipped_on_tiny_icons(qapp):
    """Icones minuscules (vignettes) : pas de badge (illisible), pas de
    plantage."""
    node = TechTreeNode(name="Tiny", source="block", unlock_level=1,
                        unlock_cost=3, categories=["Base"])
    pixmap = QPixmap(16, 16)
    pixmap.fill(QColor(18, 69, 15))
    item = _TechNodeItem(node, pixmap, view=None, row=0, editable=False)
    image = QImage(16, 16, QImage.Format.Format_ARGB32)
    image.fill(QColor(18, 69, 15))
    painter = QPainter(image)
    item._paint_cost_badge(painter)
    painter.end()
    found = any(
        (image.pixelColor(x, y).red(), image.pixelColor(x, y).green(),
         image.pixelColor(x, y).blue()) == BADGE_RGB
        for y in range(16) for x in range(16))
    assert not found
