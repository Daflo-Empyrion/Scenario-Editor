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
Vue 2D top-down (axe X/Z) des entites positionnables d'un playfield -- POI
fixes (deplacables par glisser-deposer), POI aleatoires resolus, points
d'apparition joueur, zones de spawn de drones. Voir core/playfield_canvas.py
pour l'extraction (et les limitations honnetes : ressources spatiales et
POI aleatoires non resolus n'ont pas de position exploitable, jamais
affiches plutot que d'inventer une position)."""
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtGui import QBrush, QPen, QColor, QPainter, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGraphicsView, QGraphicsScene,
    QGraphicsEllipseItem, QGraphicsTextItem, QCheckBox, QPushButton, QGroupBox,
)

from core.i18n import t
from core.playfield_canvas import (
    extract_canvas_entities, update_entity_position, compute_bounding_box,
    FACTION_COLORS, CanvasEntity,
)

_KIND_LABELS_FR = {
    "poi_fixed": "POI fixe", "poi_random": "POI aleatoire", "player_start": "Depart joueur",
    "resource": "Ressource", "spawn_zone": "Zone de spawn", "spawn_rate_zone": "Zone de taux",
    "drone_spawning": "Patrouille de drones",
}
_KIND_LABELS_EN = {
    "poi_fixed": "Fixed POI", "poi_random": "Random POI", "player_start": "Player start",
    "resource": "Resource", "spawn_zone": "Spawn zone", "spawn_rate_zone": "Rate zone",
    "drone_spawning": "Drone patrol",
}


class _EntityDot(QGraphicsEllipseItem):
    """Un point representant une entite sur le canvas. Deplacable uniquement
    si l'entite a une propriete de position modifiable directement (voir
    CanvasEntity.pos_property_key) -- sinon la souris reste un simple curseur
    de survol/selection."""

    def __init__(self, entity: CanvasEntity, radius: float, on_moved, on_selected):
        super().__init__(-radius, -radius, radius * 2, radius * 2)
        self.entity = entity
        self._on_moved = on_moved
        self._on_selected = on_selected
        movable = entity.pos_property_key is not None
        if movable:
            self.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        color = QColor(FACTION_COLORS.get(entity.faction, FACTION_COLORS["None"]))
        self.setBrush(QBrush(color))
        pen_color = QColor("#ffffff") if movable else QColor("#555555")
        self.setPen(QPen(pen_color, 2 if movable else 1))
        self.setToolTip(f"{entity.name} ({entity.kind}, {entity.faction})")
        self.setZValue(1 if movable else 0)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.entity.pos_property_key is not None:
            new_pos = self.scenePos()
            self._on_moved(self.entity, new_pos.x(), new_pos.y())

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self._on_selected(self.entity)


class PlayfieldCanvasWidget(QWidget):
    """Widget complet : vue graphique + filtres par genre d'entite + panneau
    d'information sur l'entite selectionnee."""

    modified = pyqtSignal()

    def __init__(self, doc, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.entities: List[CanvasEntity] = []
        self._dots: List[_EntityDot] = []
        self.selected_entity: Optional[CanvasEntity] = None

        layout = QVBoxLayout(self)

        info_row = QHBoxLayout()
        self.info_label = QLabel(t("canvas.no_selection"))
        self.info_label.setWordWrap(True)
        info_row.addWidget(self.info_label, 1)
        btn_refresh = QPushButton(t("results_window.btn_refresh"))
        btn_refresh.clicked.connect(self.refresh)
        info_row.addWidget(btn_refresh)
        layout.addLayout(info_row)

        filters_box = QGroupBox(t("canvas.filters_label"))
        filters_layout = QHBoxLayout(filters_box)
        self.filter_checkboxes: Dict[str, QCheckBox] = {}
        layout.addWidget(filters_box)

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.wheelEvent = self._wheel_zoom
        layout.addWidget(self.view, 1)

        self._filters_layout = filters_layout
        self.refresh()

    def resizeEvent(self, event):
        """Reajuste le cadrage a chaque redimensionnement -- necessaire car
        fitInView() calcule le zoom a partir de la taille actuelle du
        viewport, qui n'est pas encore definitive au moment du premier
        _redraw() (widget cree mais pas encore affiche a sa taille finale,
        ex: integre comme onglet)."""
        super().resizeEvent(event)
        if self.entities:
            rect = QRectF(*self._padded_rect())
            self.view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def _wheel_zoom(self, event):
        """Zoom a la molette, centre sur le curseur -- comportement standard
        pour ce genre de vue carte."""
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.view.scale(factor, factor)

    def _kind_label(self, kind: str) -> str:
        from core import i18n
        labels = _KIND_LABELS_FR if i18n.get_language() == "fr" else _KIND_LABELS_EN
        return labels.get(kind, kind)

    def refresh(self):
        """Ré-extrait les entités depuis le document (utile après une
        modification faite ailleurs, ex: dans l'onglet YAML complet) et
        redessine la scène."""
        self.entities = extract_canvas_entities(self.doc)
        self._rebuild_filters()
        self._redraw()

    def _rebuild_filters(self):
        # Reconstruit les cases de filtre seulement si le jeu de genres a
        # change (evite de perdre l'etat coche/decoche a chaque actualisation
        # anodine)
        kinds_present = sorted({e.kind for e in self.entities})
        if set(self.filter_checkboxes.keys()) == set(kinds_present):
            return
        for box in self.filter_checkboxes.values():
            box.deleteLater()
        self.filter_checkboxes.clear()
        for kind in kinds_present:
            box = QCheckBox(self._kind_label(kind))
            box.setChecked(True)
            box.stateChanged.connect(self._redraw)
            self._filters_layout.addWidget(box)
            self.filter_checkboxes[kind] = box

    def _redraw(self):
        self.scene.clear()
        self._dots = []
        visible_entities = [
            e for e in self.entities
            if e.position is not None and self.filter_checkboxes.get(e.kind, QCheckBox()).isChecked()
        ]
        for entity in visible_entities:
            x, _, z = entity.position
            radius = 8.0
            dot = _EntityDot(entity, radius, self._on_entity_moved, self._on_entity_selected)
            dot.setPos(x, z)
            self.scene.addItem(dot)
            self._dots.append(dot)

            if entity.radius:
                zone = QGraphicsEllipseItem(-entity.radius, -entity.radius,
                                             entity.radius * 2, entity.radius * 2)
                zone.setPos(x, z)
                zone.setPen(QPen(QColor(FACTION_COLORS.get(entity.faction, "#9e9e9e")), 1, Qt.PenStyle.DashLine))
                zone.setBrush(QBrush(Qt.BrushStyle.NoBrush))
                zone.setZValue(-1)
                self.scene.addItem(zone)

            label = QGraphicsTextItem(entity.name)
            label.setDefaultTextColor(QColor("#222222"))
            label.setFont(QFont("", 7))
            label.setPos(x + radius, z - radius)
            self.scene.addItem(label)

        unplottable = len(self.entities) - len(visible_entities)
        skipped_note = t("canvas.n_without_position", n=len([e for e in self.entities if e.position is None]))
        count_text = t("canvas.n_shown", n=len(visible_entities)) + " -- " + skipped_note
        self.info_label.setText(self.info_label.text() if self.selected_entity else count_text)
        self._last_count_text = count_text
        if not self.selected_entity:
            self.info_label.setText(count_text)

        if visible_entities:
            rect = QRectF(*self._padded_rect())
            self.view.setSceneRect(rect)
            self.view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def _padded_rect(self):
        min_x, max_x, min_z, max_z = compute_bounding_box(self.entities)
        pad = max(50.0, (max_x - min_x) * 0.1)
        return (min_x - pad, min_z - pad, (max_x - min_x) + pad * 2, (max_z - min_z) + pad * 2)

    def _on_entity_selected(self, entity: CanvasEntity):
        self.selected_entity = entity
        pos_text = f"({entity.position[0]:.0f}, {entity.position[1]:.0f}, {entity.position[2]:.0f})" if entity.position else "?"
        self.info_label.setText(
            f"<b>{entity.name}</b> -- {self._kind_label(entity.kind)} -- {entity.faction} -- {pos_text}")

    def _on_entity_moved(self, entity: CanvasEntity, new_x: float, new_z: float):
        if update_entity_position(entity, new_x, new_z):
            self.modified.emit()
            self._on_entity_selected(entity)
