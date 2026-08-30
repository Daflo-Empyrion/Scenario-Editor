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
    """La pastille sombre semi-transparente assombrit le coin bas-droit :
    sans elle, le chiffre dore serait illisible sur les icones claires."""
    image = _render_node(14, qapp)
    corner = image.pixelColor(46, 46)
    assert corner.red() < 120 and corner.green() < 120  # coin assombri


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
