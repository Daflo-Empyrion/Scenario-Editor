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

"""Vue 3D externe d'un .epb, facon EPD : cubes de surface colores avec la
palette du jeu, camera orbitale logicielle en QPainter (precedent : galaxy
viewer — pas de Qt3D dans le wheel PyQt6, aucune dependance ajoutee).

Fenetre NON MODALE ouverte par le controle EPB (bouton epb.view3d) ; une
seule instance par dialogue de controle, re-alimentee via set_blueprint().
Rendu a la demande (drag/zoom), blocs de surface seuls — les blocs
interieurs sont invisibles : garde-fou de performance sur les gros prefabs.
"""
import math

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton,
                             QTextBrowser, QVBoxLayout, QWidget)

from core.epb_blueprint import epb_palette_color
from core.i18n import t
from gui.window_geometry import track

# faces du cube unite : (normale, 4 sommets en coords 0/1)
_FACES = (
    ((1, 0, 0), ((1, 0, 0), (1, 0, 1), (1, 1, 1), (1, 1, 0))),
    ((-1, 0, 0), ((0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1))),
    ((0, 1, 0), ((0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0))),
    ((0, -1, 0), ((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1))),
    ((0, 0, 1), ((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1))),
    ((0, 0, -1), ((0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0))),
)
_CORNERS = tuple((x, y, z) for x in (0, 1) for y in (0, 1) for z in (0, 1))
_LIGHT = (0.36, 0.60, 0.72)          # direction lumiere en espace camera


class _OrbitView(QWidget):
    """Rendu 3D logiciel : cubes de surface, tri par profondeur, picking."""

    blockSelected = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(420, 320)
        self.setMouseTracking(False)
        self._yaw = 35.0
        self._pitch = 25.0
        self._zoom = 12.0
        self._pan = (0.0, 0.0)
        self._drag = None
        self._cubes = []             # (x, y, z, block_id, color, unknown)
        self._size = (1, 1, 1)
        self._total = 0
        self._pickable = []          # (depth, QPolygonF, block) par frame

    # ------------------------------------------------------------- donnees

    def set_blueprint(self, bp) -> None:
        sx, sy, sz = bp.size
        self._size = bp.size
        self._total = len(bp.blocks)
        occupied = {(b.x, b.y, b.z) for b in bp.blocks}
        self._cubes = []
        for b in bp.blocks:
            if ((b.x + 1, b.y, b.z) in occupied
                    and (b.x - 1, b.y, b.z) in occupied
                    and (b.x, b.y + 1, b.z) in occupied
                    and (b.x, b.y - 1, b.z) in occupied
                    and (b.x, b.y, b.z + 1) in occupied
                    and (b.x, b.y, b.z - 1) in occupied):
                continue                       # bloc interieur : invisible
            name = bp.block_name(b.block_id)
            self._cubes.append((b.x, b.y, b.z, b.block_id, b.color,
                                name.startswith("ID_Bloc_"), name))
        self.recenter()
        self.update()

    # ------------------------------------------------------------- camera

    def rotate_quarter(self) -> None:
        self._yaw = (self._yaw + 90.0) % 360.0
        self.update()

    def recenter(self) -> None:
        self._yaw = 35.0
        self._pitch = 25.0
        self._pan = (0.0, 0.0)
        self._fit_zoom()
        self.update()

    def _fit_zoom(self) -> None:
        w = max(1.0, self.width() - 20)
        h = max(1.0, self.height() - 20)
        sx, sy, sz = self._size
        self._zoom = max(2.0, min(w / (sx + 4), h / (sy + 4), 40.0))

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self._zoom = max(1.0, min(120.0, self._zoom * factor))
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag = ("orbit", event.position())
        elif event.button() == Qt.MouseButton.RightButton:
            self._drag = ("pan", event.position())
        else:
            self._pick(event.position())

    def mouseMoveEvent(self, event):
        if self._drag is None:
            return
        kind, last = self._drag
        dx = event.position().x() - last.x()
        dy = event.position().y() - last.y()
        self._drag = (kind, event.position())
        if kind == "orbit":
            self._yaw = (self._yaw + dx * 0.4) % 360.0
            self._pitch = max(-89.0, min(89.0, self._pitch + dy * 0.4))
        else:
            px, py = self._pan
            self._pan = (px + dx, py + dy)
        self.update()

    def mouseReleaseEvent(self, _event):
        self._drag = None

    def _pick(self, pos):
        point = QPointF(pos)
        # _pickable est trie du plus lointain au plus proche : la premiere
        # face contenant le point en parcourant a l'envers est la plus proche
        for _depth, polygons, block in reversed(self._pickable):
            for polygon in polygons:
                if polygon.containsPoint(point, Qt.FillRule.OddEvenFill):
                    self.blockSelected.emit(block)
                    return

    # ------------------------------------------------------------- rendu

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(30, 32, 38))
        self._pickable = []
        if not self._cubes:
            return
        cy = math.cos(math.radians(self._yaw))
        sy = math.sin(math.radians(self._yaw))
        cp = math.cos(math.radians(self._pitch))
        sp = math.sin(math.radians(self._pitch))

        def rotate(x, y, z):
            x1 = x * cy + z * sy
            z1 = -x * sy + z * cy
            y1 = y * cp - z1 * sp
            z2 = y * sp + z1 * cp
            return x1, y1, z2

        # normales des 6 faces en espace camera + offsets des 8 sommets
        face_data = []
        for normal, corners in _FACES:
            nx, ny, nz = rotate(*normal)
            face_data.append((nx, ny, nz, corners))
        corner_offsets = [rotate(x - 0.5, y - 0.5, z - 0.5)
                          for x, y, z in _CORNERS]
        face_corners = [
            tuple(_CORNERS.index(c) for c in corners)
            for _n, corners in _FACES
        ]
        light_norm = math.sqrt(sum(v * v for v in _LIGHT))

        cx = self.width() / 2 + self._pan[0]
        cyy = self.height() / 2 + self._pan[1]
        zoom = self._zoom
        drawn = []
        for x, y, z, bid, color, unknown, name in self._cubes:
            rx, ry, rz = rotate(x + 0.5 - self._size[0] / 2,
                                y + 0.5 - self._size[1] / 2,
                                z + 0.5 - self._size[2] / 2)
            sxp = cx + rx * zoom
            syp = cyy - ry * zoom
            base = QColor(220, 60, 60) if unknown \
                else QColor(*epb_palette_color(color))
            quads = []
            for fi, (nx, ny, nz, _corners) in enumerate(face_data):
                if nz <= 0:
                    continue                      # face dos
                light = max(0.0, (nx * _LIGHT[0] + ny * _LIGHT[1]
                                  + nz * _LIGHT[2]) / light_norm)
                shade = 0.55 + 0.45 * light
                poly = QPolygonF([
                    QPointF(sxp + corner_offsets[k][0] * zoom,
                            syp - corner_offsets[k][1] * zoom)
                    for k in face_corners[fi]])
                quads.append((poly, shade))
            if not quads:
                continue
            drawn.append((rz, quads, base,
                          (x, y, z, bid, color, unknown, name)))
        drawn.sort(key=lambda item: item[0])
        pen_off = QPen(Qt.PenStyle.NoPen)
        for rz, quads, base, block in drawn:
            for poly, shade in quads:
                painter.setPen(pen_off)
                painter.setBrush(QColor(
                    int(base.red() * shade), int(base.green() * shade),
                    int(base.blue() * shade)))
                painter.drawPolygon(poly)
            self._pickable.append((rz, [poly for poly, _s in quads], block))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_zoom()
        self.update()


class Epb3dWindow(QDialog):
    """Fenetre externe : vue 3D orbitale d'un .epb (systeme EPD)."""

    def __init__(self, blueprint, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("epb3d.title"))
        self.setMinimumSize(860, 600)
        self._view = _OrbitView(self)

        layout = QHBoxLayout(self)
        layout.addWidget(self._view, 1)

        side = QVBoxLayout()
        self.lbl_summary = QLabel("")
        self.lbl_summary.setWordWrap(True)
        side.addWidget(self.lbl_summary)
        self.lbl_block = QTextBrowser()
        self.lbl_block.setMaximumHeight(160)
        side.addWidget(self.lbl_block, 1)
        self.lbl_hint = QLabel(t("epb3d.hint"))
        self.lbl_hint.setWordWrap(True)
        side.addWidget(self.lbl_hint)
        nav = QHBoxLayout()
        btn_rot = QPushButton(t("epb.rotate"))
        btn_rot.clicked.connect(self._view.rotate_quarter)
        nav.addWidget(btn_rot)
        btn_center = QPushButton(t("epb.recenter"))
        btn_center.clicked.connect(self._view.recenter)
        nav.addWidget(btn_center)
        nav.addStretch(1)
        side.addLayout(nav)
        layout.addLayout(side, 1)

        self._view.blockSelected.connect(self._show_block)
        self.set_blueprint(blueprint)
        track(self, "epb_3d", (1000, 680))

    # ------------------------------------------------------------- donnees

    def set_blueprint(self, bp) -> None:
        self._view.set_blueprint(bp)
        sx, sy, sz = bp.size
        self.lbl_summary.setText(t(
            "epb3d.summary", sx=sx, sy=sy, sz=sz, total=len(bp.blocks),
            surface=len(self._view._cubes)))
        self.lbl_block.setHtml(t("epb3d.no_selection"))

    def _show_block(self, block) -> None:
        unknown = block[5]
        name = block[6]
        if unknown:
            name += t("epb3d.unknown")
        r, g, b = epb_palette_color(block[4])
        self.lbl_block.setHtml(t(
            "epb3d.block_info", name=name, x=block[0], y=block[1],
            z=block[2], rot=block[3], col=block[4],
            color=f"#{r:02x}{g:02x}{b:02x}"))
