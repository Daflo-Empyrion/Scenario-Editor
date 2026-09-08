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
Carte 2D des systemes solaires de Sectors/Sectors.yaml -- voir
core/galaxy_viewer.py pour l'extraction et les limitations honnetes
(aucune route de warp entre systemes n'est declaree dans ce fichier,
seule une carte spatiale par coordonnees reelles est proposee).

Lecture seule (contrairement au canvas de playfield) : les coordonnees
galactiques ne sont pas pensees pour etre deplacees a la souris de la meme
facon qu'un POI -- edition possible via l'onglet YAML complet si besoin."""
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QBrush, QPen, QColor, QPainter, QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QGraphicsView, QGraphicsScene,
    QGraphicsEllipseItem, QGraphicsTextItem, QPushButton, QSlider, QCheckBox,
    QMessageBox,
)

from core.i18n import t
from core.galaxy_viewer import extract_solar_systems, classify_star_class
from core.workspace_undo import FileStateUndo
from gui.theme import icon, icon_size
from gui.results_window_helpers import export_text_to_file

_ROLE_COLOR = "#7b1fa2"
_SPECTRAL_COLOR = "#f9a825"


class _SystemDot(QGraphicsEllipseItem):
    def __init__(self, system, radius: float, on_selected, on_moved=None):
        super().__init__(-radius, -radius, radius * 2, radius * 2)
        self.system = system
        self._on_selected = on_selected
        self._on_moved = on_moved
        # MAP-009 : deplacable seulement en mode edition (case a cocher) ET si
        # le systeme a des coordonnees ecritables.
        if on_moved is not None and system.coordinates is not None and system.source_item is not None:
            self.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsMovable, True)
            self.setPen(QPen(QColor("#4a7dfc"), 1.5))
        self.setAcceptHoverEvents(True)
        kind = classify_star_class(system.star_class)
        color = QColor(_ROLE_COLOR if kind == "role" else _SPECTRAL_COLOR)
        self.setBrush(QBrush(color))
        self.setPen(QPen(QColor("#333333"), 1))
        self.setToolTip(f"{system.name} ({system.star_class})")

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self._on_selected(self.system)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self._on_moved is not None and (self.flags() & QGraphicsEllipseItem.GraphicsItemFlag.ItemIsMovable):
            new_pos = self.scenePos()
            if abs(new_pos.x() - self.system.coordinates[0]) > 0.5 or abs(new_pos.y() - self.system.coordinates[2]) > 0.5:
                self._on_moved(self.system, new_pos.x(), new_pos.y())


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

        if self.sectors_path is not None:
            self.move_check = QCheckBox(t("galaxy.allow_move"))
            self.move_check.toggled.connect(self._on_move_toggled)
            layout.addWidget(self.move_check)

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        # RubberBandDrag (et non ScrollHandDrag) : sans lui le glisser gauche
        # panne la carte et les systemes etaient inmoveables (meme cause que
        # MAP-002 sur le canvas de playfield).
        self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.view.wheelEvent = self._wheel_zoom
        layout.addWidget(self.view, 1)

        tilt_row = QHBoxLayout()
        tilt_row.addWidget(QLabel(t("galaxy.tilt_label")))
        self.tilt_slider = QSlider(Qt.Orientation.Horizontal)
        self.tilt_slider.setRange(0, 100)
        self.tilt_slider.setValue(0)
        self.tilt_slider.valueChanged.connect(self._redraw)
        tilt_row.addWidget(self.tilt_slider, 1)
        self.tilt_value_label = QLabel("0%")
        self.tilt_value_label.setFixedWidth(40)
        tilt_row.addWidget(self.tilt_value_label)
        layout.addLayout(tilt_row)

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

    def _wheel_zoom(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.view.scale(factor, factor)

    def _project(self, x: float, y: float, z: float) -> tuple:
        """Projection oblique (type 'cavaliere') : l'axe Y (hauteur galactique,
        ignore en vue du dessus pure) decale visuellement le point vers le
        haut de l'ecran proportionnellement a l'inclinaison choisie -- permet
        de separer deux systemes proches en X/Z mais distants en Y, qui se
        chevauchraient sinon (confirme sur un vrai Sectors.yaml : certains
        systemes ont un Y significatif, ex: 'Dying Sun' Y=500)."""
        tilt = (self.tilt_slider.value() / 100.0) * 2.0
        return (x, z - tilt * y)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.systems:
            rect = QRectF(*self._padded_rect())
            self.view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def refresh(self):
        self.systems = extract_solar_systems(self.doc)
        self._redraw()
        self.summary_label.setText(t("galaxy.n_systems", n=len(self.systems)))

    def _padded_rect(self):
        positioned = [s for s in self.systems if s.coordinates is not None]
        if not positioned:
            return (-200.0, -200.0, 400.0, 400.0)
        projected = [self._project(*s.coordinates) for s in positioned]
        xs = [p[0] for p in projected]
        ys = [p[1] for p in projected]
        min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
        pad = max(20.0, (max_x - min_x) * 0.1)
        return (min_x - pad, min_y - pad, (max_x - min_x) + pad * 2, (max_y - min_y) + pad * 2)

    def _redraw(self):
        self.tilt_value_label.setText(f"{self.tilt_slider.value()}%")
        self.scene.clear()
        for system in self.systems:
            if system.coordinates is None:
                continue
            screen_x, screen_y = self._project(*system.coordinates)
            radius = 4.0 + min(system.sector_count, 20) * 0.4
            on_moved = self._on_system_moved if self._move_enabled else None
            dot = _SystemDot(system, radius, self._on_system_selected, on_moved=on_moved)
            dot.setPos(screen_x, screen_y)
            self.scene.addItem(dot)

            label = QGraphicsTextItem(system.name)
            label.setDefaultTextColor(QColor("#222222"))
            label.setFont(QFont("", 7))
            label.setPos(screen_x + radius, screen_y - radius)
            self.scene.addItem(label)

        if self.systems:
            rect = QRectF(*self._padded_rect())
            self.view.setSceneRect(rect)
            self.view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def _on_move_toggled(self, checked: bool):
        """MAP-009 : active/desactive le mode edition. En mode edition,
        l'inclinaison est forcee a 0 et figee : la projection cavaliere melange
        Y et Z a l'ecran, l'inverse serait ambigu -- vue de dessus pure, la
        correspondance ecran->coordonnees reste exacte."""
        self._move_enabled = checked
        if checked:
            self.tilt_slider.setValue(0)
            self.tilt_slider.setEnabled(False)
        else:
            self.tilt_slider.setEnabled(True)
        self._redraw()

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
