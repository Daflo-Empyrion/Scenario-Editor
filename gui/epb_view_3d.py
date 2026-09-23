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

"""Vue 3D isometrique d'une structure de blocs .epb (voxels).

QAbstractScrollArea : le contenu virtuel peut depasser la fenetre, les
barres de defilement deplacent la vue, la molette zoome (centree sur la
vue), Pivoter tourne de 90 deg. Les blocs inconnus du catalogue sont
dessines en rouge. Seuls les blocs visibles sont dessines (48k blocs OK)."""

import colorsys

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QAbstractScrollArea, QSizePolicy


def block_color(bid: int, unknown: bool = False) -> QColor:
    """Couleur stable par id (hachage or/teinte) ; rouge pour les inconnus."""
    if unknown:
        return QColor(220, 60, 60)
    h = ((bid * 2654435761) % 360) / 360.0
    r, g, b = colorsys.hsv_to_rgb(h, 0.55, 0.95)
    return QColor(int(r * 255), int(g * 255), int(b * 255))


class EpbView3D(QAbstractScrollArea):
    """Vue voxel : set_data(size, blocks, known_ids), Pivoter, molette = zoom,
    barres = deplacement. signal blockClicked(dict) au clic sur un voxel."""

    blockClicked = pyqtSignal(object)

    MARGIN = 24

    def __init__(self, parent=None):
        super().__init__(parent)
        self._size = (0, 0, 0)
        self._blocks = []            # [(x, y, z, id)]
        self._known = None           # set d'ids connus (None = tous connus)
        self._quarter = 0            # rotation 0..3 (90 deg par pas)
        self._zoom = 3.0
        self._proj = []              # [(rx, ry, z, profondeur, id)]
        self._zmax = 0
        self._content_w = 0
        self._content_h = 0
        self._origin = (self.MARGIN, self.MARGIN)
        self.viewport().setStyleSheet("background-color: rgb(24, 26, 32);")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    # ---------------------------------------------------------------- donnees

    def set_data(self, size, blocks, known_ids=None):
        self._size = tuple(size)
        self._blocks = [(b.x, b.y, b.z, b.block_id) if not isinstance(b, tuple)
                        else (b[0], b[1], b[2], b[3]) for b in blocks]
        self._known = known_ids
        self._project()
        self._center_view()
        self.viewport().update()

    def set_quarter(self, quarter: int):
        self._quarter = int(quarter) % 4
        self._project()
        self._center_view()
        self.viewport().update()

    def get_quarter(self) -> int:
        return self._quarter

    def recenter(self):
        """Zoom ajuste a la fenetre + centrage (bouton Recentrer)."""
        self._center_view()
        self.viewport().update()

    # ------------------------------------------------------------- projection

    def _project(self):
        """Projection isometrique : rotation d'un quart de tour autour de z,
        puis ecran x = rx, ecran y = ry/2 - z (z vertical Empyrion)."""
        sx, sy, sz = self._size
        quarter = self._quarter % 4
        self._proj = []
        self._zmax = sz
        for x, y, z, bid in self._blocks:
            if quarter == 0:
                rx, ry = x, y
            elif quarter == 1:
                rx, ry = sy - 1 - y, x
            elif quarter == 2:
                rx, ry = sx - 1 - x, sy - 1 - y
            else:
                rx, ry = y, sx - 1 - x
            depth = rx + ry + z
            self._proj.append((rx, ry, z, depth, bid))

    def _content_bounds(self, zoom):
        """Bornes du contenu projete au zoom donne (xmin, ymin, w, h)."""
        if not self._proj:
            return 0, 0, 0, 0
        xs, ys = [], []
        for rx, ry, z, _depth, _bid in self._proj:
            xs.append((rx - ry) * zoom * 0.87)
            ys.append((rx + ry) * zoom * 0.5 - z * zoom * 0.9)
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        return x0, y0, x1 - x0, y1 - y0

    def _content_points(self, zoom, ox, oy):
        """Points ecran (contenu) au zoom donne, origine translatee."""
        pts = []
        for rx, ry, z, depth, bid in self._proj:
            sx = ox + (rx - ry) * zoom * 0.87
            sy = oy + (rx + ry) * zoom * 0.5 - z * zoom * 0.9
            pts.append((sx, sy, depth, bid))
        pts.sort(key=lambda p: p[2])            # profondeur croissante
        return pts

    # ------------------------------------------------------- centrage / zoom

    def _center_view(self):
        """Recentre le contenu : zoom ajuste si trop grand pour la fenetre."""
        if not self._proj:
            self.viewport().update()
            return
        vp_w = max(1, self.viewport().width())
        vp_h = max(1, self.viewport().height())
        _x0, _y0, w1, h1 = self._content_bounds(1.0)
        fit = min(vp_w / (w1 + 2 * self.MARGIN), vp_h / (h1 + 2 * self.MARGIN))
        if fit < self._zoom or self._zoom == 0:
            self._zoom = max(0.5, min(40.0, fit))
        self._apply_scroll_range(center=True)

    def _apply_scroll_range(self, center=False):
        x0, y0, w, h = self._content_bounds(self._zoom)
        self._origin = (self.MARGIN - x0, self.MARGIN - y0)
        content_w = int(w + 2 * self.MARGIN)
        content_h = int(h + 2 * self.MARGIN)
        vp_w = max(1, self.viewport().width())
        vp_h = max(1, self.viewport().height())
        hb, vb = self.horizontalScrollBar(), self.verticalScrollBar()
        hb.setRange(0, max(0, content_w - vp_w))
        hb.setPageStep(vp_w)
        vb.setRange(0, max(0, content_h - vp_h))
        vb.setPageStep(vp_h)
        if center:
            hb.setValue(max(0, (content_w - vp_w) // 2))
            vb.setValue(max(0, (content_h - vp_h) // 2))

    # ------------------------------------------------------------------ Qt

    def paintEvent(self, event):
        painter = QPainter(self.viewport())
        painter.fillRect(self.viewport().rect(), QColor(24, 26, 32))
        if not self._proj:
            painter.setPen(QPen(QColor(120, 120, 120)))
            painter.drawText(self.viewport().rect(),
                             Qt.AlignmentFlag.AlignCenter, "-")
            return
        hx = self.horizontalScrollBar().value()
        vy = self.verticalScrollBar().value()
        ox, oy = getattr(self, "_origin", (self.MARGIN, self.MARGIN))
        pts = self._content_points(self._zoom, ox, oy)
        painter.translate(-hx, -vy)
        vp = self.viewport().rect()
        visible = (hx - 32, vy - 32, hx + vp.width() + 32, vy + vp.height() + 32)
        half = max(1.0, self._zoom * 0.55)
        known = self._known
        for sx, sy, _depth, bid in pts:
            if not (visible[0] <= sx <= visible[2] and visible[1] <= sy <= visible[3]):
                continue
            unknown = known is not None and bid not in known
            painter.fillRect(int(sx - half), int(sy - half),
                             int(2 * half), int(2 * half),
                             block_color(bid, unknown))
        painter.end()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta:
            factor = 1.25 if delta > 0 else 0.8
            self._zoom = max(0.5, min(40.0, self._zoom * factor))
            self._apply_scroll_range()
            self.viewport().update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._proj:
            self._apply_scroll_range()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            hx = self.horizontalScrollBar().value()
            vy = self.verticalScrollBar().value()
            bid = self.block_at(pos.x() + hx, pos.y() + vy)
            self.blockClicked.emit({"id": bid} if bid is not None else None)
        super().mousePressEvent(event)

    def block_at(self, x: float, y: float):
        """Id du bloc le plus proche du point ecran (x, y) en coordonnees
        VUE (barres de defilement comprises), ou None."""
        hx = self.horizontalScrollBar().value()
        vy = self.verticalScrollBar().value()
        ox, oy = getattr(self, "_origin", (self.MARGIN, self.MARGIN))
        pts = self._content_points(self._zoom, ox, oy)
        radius2 = max(9.0, (self._zoom * 1.2) ** 2)
        best, best_d = None, radius2
        for sx, sy, _depth, bid in reversed(pts):
            d = (sx - x - hx) ** 2 + (sy - y - vy) ** 2
            if d <= best_d:
                best_d, best = d, bid
        return best

    def sizeHint(self):
        return QSize(360, 360)
