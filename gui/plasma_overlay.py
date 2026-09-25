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

"""Fenetre-overlay « plasma » animee pour les operations longues (retour
utilisateur du 23/09/2026 : le QProgressDialog fige ne suffit plus — gerbe
d'etincelles bleue radiante sur fond noir, style warp, peinte en QPainter
pur). Deux usages :
- run_long (gui/busy.py) : fenetre visible des l'entree (bouclier d'entree,
  modale application — l'utilisateur ne peut rien declencher ailleurs) mais
  INVISIBLE a l'oeil pendant la 1re seconde (phase fantome, peinture vide) ;
  la gerbe n'apparait que si l'operation depasse le delai, avec fondu.
- busy_guard : phase gerbe immediate (le travail est synchrone et figera
  l'image apres quelques frames pompees — l'overlay sert d'ecran d'attente).
"""
import math
import random

from PyQt6.QtCore import QElapsedTimer, QLineF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPen, QRadialGradient
from PyQt6.QtWidgets import QApplication, QWidget

_FRAME_MS = 33          # ~30 i/s : fluide et leger
_FADE_S = 0.35          # fondu d'apparition de la gerbe
_RAYS = 150
_PARTICLES = 70
_NEBULAE = 6


class PlasmaWindow(QWidget):
    """Fenetre frameless modale application, couvrant la fenetre appelante,
    qui peint la gerbe plasma. `start(delay_ms=0)` : visible immédiatement
    (bouclier d'entree), peinture vide jusqu'au delai puis fondu + animation.
    `finish()` : arret propre (timer + hide + deleteLater)."""

    def __init__(self, parent=None, message: str = ""):
        super().__init__(
            None, Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self._burst = False          # False = phase fantome (bouclier seul)
        self._message = message or ""
        self._clock = QElapsedTimer()
        self._anim = QTimer(self)
        self._anim.setInterval(_FRAME_MS)
        self._anim.timeout.connect(self.update)
        # Determinisme : aspect stable d'une execution a l'autre (et tests)
        rng = random.Random(20260923)
        self._rays = [{
            "phase": rng.uniform(0, 2 * math.pi),
            "speed": rng.uniform(0.6, 2.1),
            "len": rng.uniform(0.35, 0.95),
            "w": rng.uniform(0.8, 2.6),
            "tint": rng.random(),
        } for _ in range(_RAYS)]
        self._particles = [{
            "angle": rng.uniform(0, 2 * math.pi),
            "speed": rng.uniform(0.10, 0.55),
            "r0": rng.random(),
            "drift": rng.uniform(-0.15, 0.15),
        } for _ in range(_PARTICLES)]
        self._nebulae = [{
            "cx": rng.uniform(0.1, 0.9), "cy": rng.uniform(0.1, 0.9),
            "r": rng.uniform(0.25, 0.55),
            "phase": rng.uniform(0, 2 * math.pi),
        } for _ in range(_NEBULAE)]
        self._place(parent)

    # ------------------------------------------------------------- cycle vie

    def _place(self, parent):
        """Couvre la fenetre appelante (sinon boite centree sur l'ecran)."""
        win = parent.window() if parent is not None else None
        if win is not None:
            geo = win.frameGeometry()
            self.setGeometry(geo.x(), geo.y(), geo.width(), geo.height())
        else:
            screen = (QApplication.primaryScreen()
                      if QApplication.instance() else None)
            geo = screen.availableGeometry() if screen else QRectF(0, 0, 800, 600).toRect()
            w, h = 460, 420
            self.setGeometry(geo.x() + (geo.width() - w) // 2,
                             geo.y() + (geo.height() - h) // 2, w, h)

    def start(self, delay_ms: int = 0):
        self.show()
        self._clock.start()
        if delay_ms <= 0:
            self._burst = True
        else:
            # QTimer ENFANT du widget (pas singleShot global) : si l'overlay
            # est detruit avant le delai (finish/deleteLater), le timer meurt
            # avec lui — un singleShot global tirerait sur un objet C++
            # supprime = crash natif (vecu : exit 127 en suite complete)
            self._ignite_timer = QTimer(self)
            self._ignite_timer.setSingleShot(True)
            self._ignite_timer.timeout.connect(self._ignite)
            self._ignite_timer.start(delay_ms)
        self._anim.start()

    def _ignite(self):
        self._burst = True

    def is_bursting(self) -> bool:
        return self._burst

    def finish(self):
        self._anim.stop()
        self.hide()
        self.deleteLater()

    # ------------------------------------------------------------- peinture

    def paintEvent(self, _event):
        if not self._burst:
            return          # phase fantome : rien (bouclier d'entree seul)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        t = self._clock.elapsed() / 1000.0
        fade = min(1.0, t / _FADE_S)
        p.setOpacity(fade)
        p.fillRect(0, 0, w, h, QColor(2, 4, 10, 238))
        cx, cy, radius = w / 2.0, h / 2.0, min(w, h) * 0.5
        self._paint_nebulae(p, cx, cy, radius, t)
        self._paint_glow(p, cx, cy, radius, t)
        self._paint_rays(p, cx, cy, radius, t)
        self._paint_particles(p, cx, cy, radius, t)
        self._paint_core(p, cx, cy, radius, t)
        self._paint_message(p, w, h, fade)
        p.end()

    def _paint_glow(self, p, cx, cy, radius, t):
        """Diffusion large autour du coeur : remplit la gerbe comme la
        reference video (halo bleu dont l'intensite respire)."""
        r = radius * (0.42 + 0.05 * math.sin(t * 1.1))
        g = QRadialGradient(cx, cy, r)
        g.setColorAt(0.0, QColor(70, 150, 255, 110))
        g.setColorAt(0.45, QColor(40, 100, 230, 55))
        g.setColorAt(1.0, QColor(20, 60, 180, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.fillRect(QRectF(cx - r, cy - r, 2 * r, 2 * r), g)

    def _paint_message(self, p, w, h, fade):
        """Libelle optionnel (ex « telechargement du modele... ») sous la
        gerbe, discret."""
        if not self._message:
            return
        p.setOpacity(0.85 * fade)
        font = p.font()
        font.setPointSize(max(10, font.pointSize()))
        p.setFont(font)
        fm = p.fontMetrics()
        elided = fm.elidedText(self._message, Qt.TextElideMode.ElideRight,
                               max(80, int(w * 0.8)))
        p.setPen(QColor(150, 180, 220, 220))
        p.drawText(QRectF(0, h - fm.height() - 18, w, fm.height() + 4),
                   Qt.AlignmentFlag.AlignHCenter
                   | Qt.AlignmentFlag.AlignVCenter, elided)

    def _paint_nebulae(self, p, cx, cy, radius, t):
        for n in self._nebulae:
            x = cx + (n["cx"] - 0.5) * 2 * radius \
                + math.sin(t * 0.22 + n["phase"]) * radius * 0.06
            y = cy + (n["cy"] - 0.5) * 2 * radius \
                + math.cos(t * 0.18 + n["phase"]) * radius * 0.06
            r = n["r"] * radius
            g = QRadialGradient(x, y, r)
            g.setColorAt(0.0, QColor(8, 34, 96, 52))
            g.setColorAt(1.0, QColor(8, 34, 96, 0))
            p.fillRect(QRectF(x - r, y - r, 2 * r, 2 * r), g)

    def _paint_rays(self, p, cx, cy, radius, t):
        swirl = t * 0.05
        for i, ray in enumerate(self._rays):
            angle = (i * 2 * math.pi / _RAYS) + swirl \
                + math.sin(t * 0.4 + ray["phase"]) * 0.015
            pulse = 0.5 + 0.5 * math.sin(t * ray["speed"] + ray["phase"])
            length = radius * ray["len"] * (0.72 + 0.28 * pulse)
            r0 = radius * 0.055
            x0 = cx + math.cos(angle) * r0
            y0 = cy + math.sin(angle) * r0
            x1 = cx + math.cos(angle) * length
            y1 = cy + math.sin(angle) * length
            k = ray["tint"]
            color = QColor(
                int(60 + 110 * k), int(120 + 70 * k), 255,
                int(34 + 150 * pulse * pulse))
            pen = QPen(color)
            pen.setWidthF(ray["w"])
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawLine(QLineF(x0, y0, x1, y1))

    def _paint_particles(self, p, cx, cy, radius, t):
        pen = QPen()
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        for part in self._particles:
            r = (part["r0"] + t * part["speed"]) % 1.0
            angle = part["angle"] + part["drift"] * r
            tail = 0.05 + 0.06 * r
            r_in = (0.06 + 0.9 * r) * radius
            r_out = (0.06 + 0.9 * min(1.0, r + tail)) * radius
            x0 = cx + math.cos(angle) * r_in
            y0 = cy + math.sin(angle) * r_in
            x1 = cx + math.cos(angle) * r_out
            y1 = cy + math.sin(angle) * r_out
            alpha = int(210 * math.sin(math.pi * r))
            pen.setColor(QColor(150, 210, 255, alpha))
            pen.setWidthF(1.0 + 1.6 * r)
            p.setPen(pen)
            p.drawLine(QLineF(x0, y0, x1, y1))

    def _paint_core(self, p, cx, cy, radius, t):
        r = radius * (0.16 + 0.03 * math.sin(t * 2.4))
        g = QRadialGradient(cx, cy, r)
        g.setColorAt(0.0, QColor(255, 255, 255, 235))
        g.setColorAt(0.25, QColor(170, 220, 255, 190))
        g.setColorAt(0.6, QColor(70, 140, 255, 90))
        g.setColorAt(1.0, QColor(30, 80, 220, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.fillRect(QRectF(cx - r, cy - r, 2 * r, 2 * r), g)
