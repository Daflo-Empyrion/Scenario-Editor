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
Carte 3D des systemes solaires de Sectors/Sectors.yaml -- voir
core/galaxy_viewer.py pour l'extraction et les limitations honnetes
(aucune route de warp entre systemes n'est declaree dans ce fichier,
seule une carte spatiale par coordonnees reelles est proposee).

Vue 3D logicielle (consultation IA 19/10, pas de Qt3D/QML) : camera
orbitale dessinee en QPainter. Glisser gauche = orbite (azimut puis
elevation, dans cet ordre -- l'axe correct), droit/milieu = pan, molette
= zoom. Perspective en exploration ; le mode EDITION (MAP-009) fige
azimut=0 / elevation=90 et passe en ORTHOGRAPHIQUE : l'ecran redevient
(x, z) exact, la correspondance souris->fichier reste garantie.

Lecture seule hors mode edition : les coordonnees galactiques ne sont
pas pensees pour etre deplacees a la souris autrement."""
import math
from math import cos, sin, radians

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QBrush, QPen, QColor, QPainter, QFont, QFontMetrics
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QMessageBox, QLineEdit, QWidget, QToolTip,
)

from core.i18n import t
from core.galaxy_viewer import extract_solar_systems, classify_star_class
from core.workspace_undo import FileStateUndo
from gui.theme import icon, icon_size
from gui.results_window_helpers import export_text_to_file

_ROLE_COLOR = "#7b1fa2"

# Lisibilite : une couleur par lettre de classe spectrale (palette astronomy
# standard O bleu -> M rouge), l'etoile restant identifiable sans lire le nom.
_SPECTRAL_PALETTE = {
    "O": "#8b9dff", "B": "#4aa3ff", "A": "#dce8ff", "F": "#fff3b0",
    "G": "#ffd54f", "K": "#ff9e40", "M": "#ff6b57",
}
_SPECTRAL_ORDER = "OBAFGKM"


def _dot_color(star_class: str) -> QColor:
    if classify_star_class(star_class) == "role":
        return QColor(_ROLE_COLOR)
    letter = (star_class or "")[:1].upper()
    return QColor(_SPECTRAL_PALETTE.get(letter, "#9e9e9e"))


def _norm(v):
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / n, v[1] / n, v[2] / n)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


class _GalaxyCanvas(QWidget):
    """Le rendu 3D et TOUTE la navigation souris. Pas de QGraphicsView :
    les points sont repeints a chaque frame (80-300 points = trivial) et
    la camera reste une simple fonction projective testable hors ecran."""

    ELEV_MIN = -85.0  # orbite LIBRE des deux cotes du plan (vecu 19/10 :
    ELEV_MAX = 85.0   # le clamp [10;85] empechait de passer sous la galaxie).
    ELEV_TOP = 90.0   # vue de dessus exacte, reservee au verrou d'edition.

    def __init__(self, on_selected, on_moved=None):
        super().__init__()
        self._on_selected = on_selected
        self._on_moved = on_moved
        self.setMouseTracking(True)
        self.systems = []
        self.azim = 0.0        # degres, rotation autour de l'axe Y galactique
        self.elev = 35.0       # degres d'ouverture : le RELIEF se voit sans
        #                       manipuler (vecu : 90 par defaut = galaxie
        #                       "plate", toute la hauteur Y etait invisible).
        self.zoom = 1.0
        self.zoom_fit = 1.0
        self.center = (0.0, 0.0, 0.0)
        self.span = 400.0
        self.edit_mode = False
        self._filter_text = ""
        self._drag = None      # ('orbit'|'pan', x0, y0) ou ('move', system)
        self._drag_preview = None  # (sx, sy) : le point suit la souris (vecu)
        self._layout = []      # par frame : (system, sx, sy, r_px, depth)
        self._labels = []      # par frame : (nom, QRectF, visible, role)

    # ------------------------------------------------------------------
    # Camera / projection
    # ------------------------------------------------------------------
    def set_systems(self, systems):
        self.systems = systems
        self._fit()

    def _fit(self):
        pts = [s.coordinates for s in self.systems if s.coordinates]
        w = max(self.width(), 1)
        h = max(self.height(), 1)
        if not pts:
            self.center, self.span, self.zoom = (0.0, 0.0, 0.0), 400.0, w / 400.0
        else:
            xs, ys, zs = [p[0] for p in pts], [p[1] for p in pts], [p[2] for p in pts]
            self.center = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2,
                           (min(zs) + max(zs)) / 2)
            self.span = max(max(xs) - min(xs), max(ys) - min(ys),
                            max(zs) - min(zs), 1.0)
        self.zoom_fit = min(w, h) / (self.span * 1.15)
        self.zoom = self.zoom_fit

    def _basis(self):
        """Repere camera : right/down ecran en coordonnees monde + distance
        orbitale. En edition : base FIGEE (1,0,0)/(0,0,1) quelle que soit la
        camera courante -> l'ecran est exactement (x, z), MAP-009 garanti.
        Continuite avec l'ancienne carte 2D a l'ouverture explore."""
        if self.edit_mode:
            return (0.0, 1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), self.span * 1.5
        A, E = radians(self.azim), radians(self.elev)
        cam = (cos(E) * sin(A), sin(E), cos(E) * cos(A))
        right = _norm(_cross(cam, (0.0, 0.0, 1.0)))
        down = _cross(right, cam)
        dist = self.span * 1.5
        return cam, right, down, dist

    def project(self, coordinates):
        """World -> ecran. Retourne (sx, sy, factor) ; factor = grossissement
        perspective (1.0 au centre, < 1 au fond, > 1 devant). None si le
        point passe derriere la camera (impossible dans le clamp courant,
        garde par surete)."""
        if coordinates is None:
            return None
        cam, right, down, dist = self._basis()
        p = (coordinates[0] - self.center[0],
             coordinates[1] - self.center[1],
             coordinates[2] - self.center[2])
        if self.edit_mode:
            # Orthographique : ecran = (x, z) exact, inversible pour MAP-009.
            k = self.zoom
            return (self.width() / 2 + k * (p[0] * right[0] + p[1] * right[1] + p[2] * right[2]),
                    self.height() / 2 + k * (p[0] * down[0] + p[1] * down[1] + p[2] * down[2]),
                    1.0)
        depth = p[0] * cam[0] + p[1] * cam[1] + p[2] * cam[2]
        denom = dist + depth
        if denom < dist * 0.1:
            return None
        k = self.zoom * dist / denom
        sx = self.width() / 2 + k * (p[0] * right[0] + p[1] * right[1] + p[2] * right[2])
        sy = self.height() / 2 + k * (p[0] * down[0] + p[1] * down[1] + p[2] * down[2])
        return (sx, sy, dist / denom)

    def unproject_ground(self, sx, sy):
        """Inverse ORTHOGRAPHIQUE (mode edition seulement) : ecran -> (x, z),
        l'axe Y galactique n'est pas modifiable (continuite MAP-009)."""
        cam, right, down, _dist = self._basis()
        k = self.zoom
        vx = (sx - self.width() / 2) / k
        vy = (sy - self.height() / 2) / k
        return (self.center[0] + vx * right[0] + vy * down[0],
                self.center[2] + vx * right[2] + vy * down[2])

    # ------------------------------------------------------------------
    # Navigation souris
    # ------------------------------------------------------------------
    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        lo, hi = self.zoom_fit * 0.2, self.zoom_fit * 40.0
        self.zoom = max(lo, min(hi, self.zoom * factor))
        self.update()

    def mousePressEvent(self, event):
        pos = event.position()
        if event.button() == Qt.MouseButton.LeftButton:
            hit = self._hit_test(pos.x(), pos.y())
            if self.edit_mode and self._on_moved is not None \
                    and hit is not None and hit.coordinates is not None \
                    and hit.source_item is not None:
                self._drag = ("move", hit)
                self._drag_preview = (pos.x(), pos.y())
                self.update()
                return
            if hit is not None:
                self._on_selected(hit)
                if not self.edit_mode:
                    return  # cliquer un point ne doit pas orbiter par accident
            self._drag = ("orbit", pos.x(), pos.y())
        elif event.button() in (Qt.MouseButton.RightButton,
                                Qt.MouseButton.MiddleButton):
            self._drag = ("pan", pos.x(), pos.y())

    def mouseMoveEvent(self, event):
        pos = event.position()
        if self._drag is None:
            hit = self._hit_test(pos.x(), pos.y())
            if hit is not None:
                QToolTip.showText(event.globalPosition().toPoint(),
                                  f"{hit.name} ({hit.star_class})", self)
            return
        if self._drag[0] == "move":
            # Le point suit la souris EN DIRECT (regression vecue : sans lui,
            # le deplacement sautait seulement au relachement).
            self._drag_preview = (pos.x(), pos.y())
            self.update()
            return
        dx = pos.x() - self._drag[1]
        dy = pos.y() - self._drag[2]
        self._drag = (self._drag[0], pos.x(), pos.y())
        if self._drag[0] == "orbit":
            self.azim = (self.azim - dx * 0.4) % 360.0
            self.elev = max(self.ELEV_MIN,
                            min(self.ELEV_MAX, self.elev - dy * 0.25))
        else:  # pan : le centre suit les axes ECRAN exprimes en monde
            cam, right, down, dist = self._basis()
            step = (dist / max(self.zoom, 1e-6)) / max(self.height(), 1)
            self.center = (self.center[0] - (dx * right[0] + dy * down[0]) * step,
                           self.center[1] - (dx * right[1] + dy * down[1]) * step,
                           self.center[2] - (dx * right[2] + dy * down[2]) * step)
        self.update()

    def mouseReleaseEvent(self, event):
        if self._drag is not None and self._drag[0] == "move" \
                and self._on_moved is not None:
            system = self._drag[1]
            pos = event.position()
            wx, wz = self.unproject_ground(pos.x(), pos.y())
            if system.coordinates is not None and (
                    abs(wx - system.coordinates[0]) > 0.5
                    or abs(wz - system.coordinates[2]) > 0.5):
                self._on_moved(system, wx, wz)
        self._drag = None
        self._drag_preview = None
        self.update()

    def _hit_test(self, sx, sy):
        best, best_d = None, 1e9
        for system, px, py, r_px, _pf in self._layout:
            d = math.hypot(sx - px, sy - py)
            if d <= max(12.0, r_px + 4.0) and d < best_d:
                best, best_d = system, d
        return best

    # ------------------------------------------------------------------
    # Filtrage / etiquettes (logique de lisibilite du 18/10, repeinte ici)
    # ------------------------------------------------------------------
    def set_filter(self, text):
        self._filter_text = (text or "").strip().lower()
        self.update()

    def _alpha(self, system):
        return 1.0 if not self._filter_text or self._filter_text in system.name.lower() else 0.12

    def _layout_labels(self):
        """Etiquettes : priorite aux roles speciaux, puis aux systemes les
        plus riches ; TOUTES passent dans le filtre anti-chevauchement
        (vecu sur RE2 : les roles seuls empilaient une muraille de boites
        dans le centre dense). Les spectrales n'entrent en lice qu'a partir
        du zoom de cadrage. Testable hors paint."""
        candidates = []
        for system, sx, sy, r_px, _pf in self._layout:
            role = classify_star_class(system.star_class) == "role"
            if not (role or self.zoom >= self.zoom_fit):
                continue
            w = QFontMetrics(QFont("", 7)).horizontalAdvance(system.name) + 8
            candidates.append((-role, -system.sector_count,
                               system, QRectF(sx + r_px, sy - r_px - 14, w, 16)))
        candidates.sort(key=lambda c: (c[0], c[1]))
        placed, out = [], {id(c[2]): None for c in candidates}
        for _neg_role, _neg_count, system, rect in candidates:
            if any(rect.intersects(other) for other in placed):
                out[id(system)] = (system, rect, False,
                                   classify_star_class(system.star_class) == "role")
                continue
            placed.append(rect)
            out[id(system)] = (system, rect, True,
                               classify_star_class(system.star_class) == "role")
        # tout systeme du layout doit avoir une entree (visible ou masquee)
        self._labels = [out.get(id(s), (s, QRectF(), False, False))
                        for s, _x, _y, _r, _p in self._layout]
        return self._labels

    # ------------------------------------------------------------------
    # Rendu
    # ------------------------------------------------------------------
    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._layout = []
        drag_system = self._drag[1] if (self._drag and self._drag[0] == "move") else None
        entries = []
        for system in self.systems:
            if system.coordinates is None or system is drag_system:
                continue
            proj = self.project(system.coordinates)
            if proj is None:
                continue
            depth = math.hypot(system.coordinates[0] - self.center[0],
                               system.coordinates[2] - self.center[2])
            entries.append((depth, system, proj[0], proj[1], proj[2]))
        entries.sort(key=lambda e: -e[0])  # loin -> pres
        base = 4.0
        for _depth, system, sx, sy, pf in entries:
            radius = (base + min(system.sector_count, 20) * 0.4) \
                * max(pf * self.zoom / max(self.zoom_fit, 1e-9), 0.35)
            alpha = self._alpha(system)
            color = QColor(_dot_color(system.star_class))
            color.setAlphaF(alpha)
            painter.setBrush(QBrush(color))
            role = classify_star_class(system.star_class) == "role"
            painter.setPen(QPen(QColor(51, 51, 51, int(255 * alpha)),
                                2.5 if role else 1))
            painter.drawEllipse(QPointF(sx, sy), radius, radius)
            self._layout.append((system, sx, sy, radius, pf))

        if drag_system is not None and self._drag_preview is not None \
                and drag_system.coordinates is not None:
            # Apercu LIVE : le point suit la souris, coordonnees affichees --
            # rien n'est ecrit avant le relachement (MAP-009 intact).
            wx, wz = self.unproject_ground(*self._drag_preview)
            proj = self.project((wx, drag_system.coordinates[1], wz))
            if proj is not None:
                sx, sy = proj[0], proj[1]
                painter.setBrush(QBrush(QColor(_dot_color(drag_system.star_class))))
                painter.setPen(QPen(QColor("#4a7dfc"), 2.5))
                painter.drawEllipse(QPointF(sx, sy), 7.0, 7.0)
                painter.setPen(QColor("#4a7dfc"))
                painter.drawText(QPointF(sx + 10, sy - 10),
                                 f"{wx:.0f}, {wz:.0f}")
                # present dans _layout pour rester selectionnable/draggable
                self._layout.append((drag_system, sx, sy, 7.0, 1.0))

        font = QFont("", 7)
        painter.setFont(font)
        for system, rect, shown, _role in self._layout_labels():
            if not shown:
                continue
            alpha = self._alpha(system)
            painter.setPen(QPen(Qt.PenStyle.NoPen))
            painter.setBrush(QBrush(QColor(255, 255, 255, int(170 * alpha))))
            painter.drawRect(rect)
            painter.setPen(QColor(34, 34, 34, int(255 * alpha)))
            painter.drawText(rect.adjusted(4, 0, 0, 0),
                             Qt.AlignmentFlag.AlignVCenter, system.name)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.systems:
            self._fit()
        self.update()


class GalaxyViewerDialog(QDialog):
    def __init__(self, doc, parent=None, sectors_path=None, push_undo=None,
                 is_path_modified=None, reload_path=None):
        super().__init__(parent)
        self.doc = doc
        self.systems = []
        # MAP-009 : sans chemin de Sectors.yaml (ou sans callbacks), la carte
        # reste en lecture seule -- meme comportement qu'avant.
        self.sectors_path = sectors_path
        self._push_undo = push_undo
        self._is_path_modified = is_path_modified
        self._reload_path = reload_path
        self._move_enabled = False
        self.setWindowTitle(t("galaxy.title"))
        self.setMinimumSize(900, 650)

        layout = QVBoxLayout(self)

        info_row = QHBoxLayout()
        self.info_label = QLabel(t("canvas.no_selection"))
        self.info_label.setWordWrap(True)
        info_row.addWidget(self.info_label, 1)
        layout.addLayout(info_row)

        self.search = QLineEdit()
        self.search.setPlaceholderText(t("galaxy.search_placeholder"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        layout.addWidget(self.search)

        if self.sectors_path is not None:
            self.move_check = QCheckBox(t("galaxy.allow_move"))
            self.move_check.toggled.connect(self._on_move_toggled)
            layout.addWidget(self.move_check)

        self.canvas = _GalaxyCanvas(self._on_system_selected,
                                    on_moved=self._on_system_moved)
        layout.addWidget(self.canvas, 1)

        hint = QLabel(t("galaxy.mouse_help"))
        hint.setObjectName("mutedLabel")
        layout.addWidget(hint)

        layout.addWidget(self._build_legend())

        bottom_row = QHBoxLayout()
        self.summary_label = QLabel("")
        self.summary_label.setObjectName("mutedLabel")
        bottom_row.addWidget(self.summary_label)
        bottom_row.addStretch()

        btn_refresh = QPushButton(icon("fa5s.sync-alt", "#4a7dfc"), t("results_window.btn_refresh"))
        btn_refresh.setIconSize(icon_size())
        btn_refresh.setObjectName("secondaryButton")
        btn_refresh.clicked.connect(self.refresh)
        bottom_row.addWidget(btn_refresh)

        btn_export = QPushButton(icon("fa5s.file-export", "#4a7dfc"), t("results_window.btn_export"))
        btn_export.setIconSize(icon_size())
        btn_export.setObjectName("secondaryButton")
        btn_export.clicked.connect(self._export)
        bottom_row.addWidget(btn_export)

        btn_close = QPushButton(t("validation.close"))
        btn_close.setObjectName("secondaryButton")
        btn_close.clicked.connect(self.close)
        bottom_row.addWidget(btn_close)
        layout.addLayout(bottom_row)

        self.refresh()

    def _build_legend(self) -> QWidget:
        """Legende de lecture : puce violette = roles speciaux, puces
        O->M = classes spectrales. Construite une seule fois."""
        row = QHBoxLayout()
        row.addWidget(self._legend_chip(_ROLE_COLOR, t("galaxy.legend_role")))
        for letter in _SPECTRAL_ORDER:
            row.addWidget(self._legend_chip(_SPECTRAL_PALETTE[letter], letter))
        row.addStretch()
        wrap = QWidget()
        wrap.setLayout(row)
        return wrap

    @staticmethod
    def _legend_chip(color: str, text: str) -> QLabel:
        chip = QLabel(text)
        chip.setStyleSheet(
            f"background-color: {color}; color: #222222;"
            "border-radius: 4px; padding: 1px 6px;")
        return chip

    def refresh(self):
        self.systems = extract_solar_systems(self.doc)
        self.canvas.set_systems(self.systems)
        self.summary_label.setText(t("galaxy.n_systems", n=len(self.systems)))

    def _apply_filter(self, text):
        self.canvas.set_filter(text)

    def _on_move_toggled(self, checked: bool):
        """MAP-009 : active/desactive le mode edition. En mode edition la
        camera passe en vue de dessus ORTHOGRAPHIQUE et la navigation est
        figee : la correspondance ecran->coordonnees reste exacte."""
        self._move_enabled = checked
        self.canvas.edit_mode = checked
        if checked:
            self.canvas.azim = 0.0
            self.canvas.elev = _GalaxyCanvas.ELEV_TOP
        self.canvas.update()

    def _on_system_moved(self, system, screen_x: float, screen_y: float):
        """Ecrit la nouvelle position (X, Z) du systeme dans Sectors.yaml (Y
        conserve). Garde-fous : onglet Sectors.yaml modifie -> refus ; apres
        ecriture -> undo espace de travail + rechargement de l'onglet ouvert."""
        if not self._move_enabled or self.sectors_path is None:
            return
        if self._is_path_modified and self._is_path_modified(self.sectors_path):
            QMessageBox.warning(self, t("galaxy.title"), t("galaxy.move_locked", name=self.sectors_path.name))
            self.refresh()
            return
        x, y, _ = system.coordinates
        coords_prop = None
        if system.source_item is not None:
            coords_prop = next(
                (c for c in system.source_item.children if getattr(c, 'key', None) == "Coordinates"),
                None)
        if coords_prop is None:
            return
        coords_prop.set_own_value(f"[ {screen_x:g}, {y:g}, {screen_y:g} ]")
        try:
            from pathlib import Path
            from core.fsutil import atomic_write_text
            path = Path(self.sectors_path)
            prior = path.read_bytes() if path.exists() else None
            atomic_write_text(path, self.doc.render())
            if self._push_undo is not None:
                self._push_undo(FileStateUndo(path, prior, t("galaxy.move_undo", name=system.name)))
        except OSError as e:
            QMessageBox.critical(self, t("galaxy.title"), f"{t('save.error_title')} :\n{e}")
            return
        system.coordinates = (screen_x, y, screen_y)
        self._on_system_selected(system)
        if self._reload_path is not None:
            self._reload_path(self.sectors_path)

    def _on_system_selected(self, system):
        kind_label = t("galaxy.role") if classify_star_class(system.star_class) == "role" else t("galaxy.spectral")
        self.info_label.setText(
            f"<b>{system.name}</b> -- {system.star_class} ({kind_label}) -- "
            f"{t('galaxy.n_sectors', n=system.sector_count)}")

    def _export(self):
        lines = [t("galaxy.title"), "=" * len(t("galaxy.title")), ""]
        for s in self.systems:
            pos = f"({s.coordinates[0]:.0f}, {s.coordinates[1]:.0f}, {s.coordinates[2]:.0f})" if s.coordinates else "?"
            lines.append(f"{s.name} -- {s.star_class} -- {pos} -- {s.sector_count} secteurs")
        export_text_to_file(self, "galaxie.txt", "\n".join(lines))
