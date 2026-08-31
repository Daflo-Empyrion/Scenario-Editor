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
Vue graphique d'UNE categorie de l'arbre technologique (un onglet) --
reproduit la disposition confirmee par capture d'ecran F3 fournie par
l'utilisateur (session du 28/08/2026) : colonnes = niveaux de deblocage
reels, lignes calculees pour regrouper chaque noeud pres de son parent (voir
core/tech_tree_layout.py), icone verrouillee (cadenas) si le niveau simule du
joueur est inferieur au niveau requis.

Interactions confirmees aupres de l'utilisateur :
  - Glisser un noeud HORIZONTALEMENT dans son onglet -> change de colonne de
    niveau -> ecrit UnlockLevel (aimante sur le niveau reel le plus proche,
    voir core.tech_tree_layout.snap_to_nearest_level).
  - Glisser un noeud VERTICALEMENT (reorganisation manuelle de ligne,
    notamment pour faciliter la reorganisation lors de duplications --
    demande explicite de l'utilisateur, session du 29/08/2026) -> declenche
    un mode 'choix du nouveau parent' : la fenetre invite a cliquer sur le
    futur parent (ou choisir 'Aucun parent'/Annuler), et ecrit TechTreeParent
    UNIQUEMENT si l'utilisateur confirme un choix -- voir start_parent_pick/
    mousePressEvent. Si annule, le noeud reste positionne la ou il a ete
    depose (purement visuel, aucune ecriture), mais un rebuild() ulterieur de
    la vue (ex: apres un autre changement) recalculera sa position reelle.
  - Deplacer un noeud vers un AUTRE onglet -> ecrit TechTreeNames (remplace,
    ne cumule pas -- confirme explicitement : 'deplacer' pas 'ajouter').
    Implemente ici via menu contextuel ('Deplacer vers...'), une des deux
    methodes que l'utilisateur avait lui-meme listees comme equivalentes
    (menu contextuel OU glisser sur l'onglet) -- le menu contextuel est
    retenu pour la V1 (fiable, testable), le glisser-deposer inter-widgets
    pourra s'ajouter plus tard sans changer le modele de donnees.
  - Clic simple SANS deplacement OU double-clic sur un noeud -> active la
    FICHE D'INFORMATION editable (signal node_activated, cable par
    gui/tech_tree_dialog.py -- demande du 31/08/2026 : equilibrage rapide
    directement depuis l'arbre). Le menu contextuel garde l'edition rapide
    du cout par boite de saisie.

Mise en page ADAPTATIVE (demande du 31/08/2026) : la largeur de colonne est
recalculee = largeur utile / nombre de jalons, pour que TOUS les niveaux
(1 a 25) restent visibles sans defilement horizontal a toute resolution ;
icones, tuiles et badge du cout sont mis a l'echelle (bornes mini/maxi pour
rester lisibles d'un petit portable au 4K).

N'implemente PAS les barres de couleur "constructeur capable de crafter"
(Target: dans Templates.ecf) -- explicitement hors perimetre de la V1 a la
demande de l'utilisateur.
"""
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRect, QRectF
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QFont, QPainterPath, QLinearGradient
from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QGraphicsLineItem, QGraphicsPathItem, QMenu, QInputDialog,
)

from core.i18n import t
from core.tech_tree import TechTree, TechTreeNode
from core.tech_tree_icons import resolve_icon_path, load_icon_bytes
from core.tech_tree_layout import MILESTONE_LEVELS, level_to_x_fraction, x_fraction_to_level
from gui.theme import icon, BORDER, TEXT_GRAY, CARD_BG, BG, PRIMARY as PRIMARY_HIGHLIGHT

# Bornes de la mise en page adaptative (voir _compute_metrics) : en dessous
# de COL_MIN les colonnes seraient plus etroites que l'icone minimale (une
# fenetre minuscule garde donc un scroll horizontal, cas degrade assume) ;
# au-dela de COL_MAX, l'espace supplmentaire reste reparti entre les colonnes
# (les 9 jalons remplissent toujours la largeur, seules les icones plafonnent).
COL_MIN = 96.0
COL_MAX = 420.0
ICON_MIN = 44
ICON_MAX = 132
_DEFAULT_VIEW_WIDTH = 900.0
_GENERIC_ICON_NAME = "fa5s.cube"
_BACKGROUND_ASSET_NAME = "tech_tree_background.jpg"
_background_pixmap_cache: Optional[QPixmap] = None

# Tuile derriere chaque icone -- style 'bouton DORE' de la reference fournie
# par l'utilisateur (session du 31/08/2026, image 1) ADAPTE EN VERT : cadre
# exterieur en degrade (sombre en bas, plus clair en haut), filet clair
# interieur, face en degrade vertical + reflet brillant dans la moitie
# superieure. Dessin VECTORIEL (aucune image embarquee) : suit la mise en
# page adaptative a toute resolution.
_TILE_FRAME_TOP = "#5da23a"
_TILE_FRAME_BOTTOM = "#245414"
_TILE_INNER_STROKE = "#d6f5bd"
_TILE_FACE_TOP = "#b3e397"
_TILE_FACE_BOTTOM = "#5a9c3c"
_TILE_HIGHLIGHT = QColor(255, 255, 255, 70)
# Badge de cout (voir _TechNodeItem._paint_cost_badge) : chiffre dore sur
# pastille sombre, EN HAUT A GAUCHE et en grande police a l'echelle de
# l'icone -- demande du 31/08/2026 (l'ancien badge bas-droit etait trop
# petit sur grand ecran).
_BADGE_TEXT_COLOR = "#FFD34D"


def _load_background_pixmap() -> Optional[QPixmap]:
    """Charge UNE FOIS l'image de fond de l'arbre technologique (voir
    assets/tech_tree_background.jpg -- demande explicite de l'utilisateur,
    session du 29/08/2026). Retourne None si absente -- l'appelant retombe
    alors sur un simple remplissage de couleur unie, jamais de plantage."""
    global _background_pixmap_cache
    if _background_pixmap_cache is not None:
        return _background_pixmap_cache
    import sys
    from pathlib import Path
    if getattr(sys, 'frozen', False):
        path = Path(sys._MEIPASS) / "assets" / _BACKGROUND_ASSET_NAME
    else:
        path = Path(__file__).resolve().parent.parent / "assets" / _BACKGROUND_ASSET_NAME
    if path.is_file():
        pix = QPixmap(str(path))
        if not pix.isNull():
            _background_pixmap_cache = pix
            return pix
    return None


def _load_node_pixmap(icon_index: dict, node: TechTreeNode, icon_size: int) -> QPixmap:
    """Charge l'icone reelle du noeud si trouvee dans l'index (voir
    core.tech_tree_icons -- fichier sur disque OU membre d'archive .pak,
    toujours lu EN MEMOIRE, jamais extrait sur disque pour les icones
    d'archive), sinon une icone generique de repli -- ne laisse JAMAIS une
    case vide (comportement explicitement demande)."""
    ref = resolve_icon_path(icon_index, node.icon_key)
    if ref is not None:
        data = load_icon_bytes(ref)
        if data:
            pix = QPixmap()
            if pix.loadFromData(data) and not pix.isNull():
                return pix.scaled(icon_size, icon_size, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
    generic = icon(_GENERIC_ICON_NAME, color=TEXT_GRAY).pixmap(icon_size, icon_size)
    return generic


class _TechNodeItem(QGraphicsPixmapItem):
    """Icone d'un noeud, deplacable horizontalement (voir mouseMoveEvent).
    `view` est la TechTreeCategoryView proprietaire, utilisee pour les
    callbacks de persistance et la resolution des colonnes de niveau.

    `editable=False` (utilise par le mode previsualisation, voir
    gui/tech_tree_preview_dialog.py) desactive le glisser/menu contextuel/
    double-clic -- affiche le noeud comme simple repere de contexte parmi les
    noeuds reels, sans permettre de les modifier par erreur. `highlighted=True`
    dessine un contour colore -- utilise pour distinguer le noeud EN COURS DE
    CREATION parmi les noeuds reels deja existants."""

    def __init__(self, node: TechTreeNode, pixmap: QPixmap, view: "TechTreeCategoryView", row: int,
                 editable: bool = True, highlighted: bool = False):
        super().__init__(pixmap)
        self.node = node
        self._view = view
        self._row = row
        self._editable = editable
        self._highlighted = highlighted
        self._drag_start_pos: Optional[QPointF] = None
        self._press_button: Optional[Qt.MouseButton] = None
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        # QGraphicsPixmapItem ne compte par defaut que les pixels OPAQUES
        # pour la detection de clic (ShapeMode.MaskShape) -- une icone avec
        # une marge transparente autour du dessin (frequent) rate alors le
        # clic pres du bord, et itemAt() peut retomber sur un autre element
        # dessous (ex: la ligne de connexion, dont le trajet passe justement
        # par le CENTRE de chaque icone -- bug reel confirme : le choix du
        # nouveau parent apres un glisser vertical ne s'enregistrait jamais,
        # car le clic de selection du parent manquait systematiquement
        # l'icone ciblee). BoundingRectShape fait compter tout le carre.
        self.setShapeMode(QGraphicsPixmapItem.ShapeMode.BoundingRectShape)
        self.setCursor(Qt.CursorShape.OpenHandCursor if editable else Qt.CursorShape.ArrowCursor)
        self.setToolTip(self._tooltip_text())

    def _tooltip_text(self) -> str:
        return t("techtree.node_tooltip", name=self.node.name, level=self.node.unlock_level,
                  cost=self.node.unlock_cost)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        self._paint_tile(painter)
        super().paint(painter, option, widget)
        self._paint_cost_badge(painter)
        if self._highlighted:
            painter.save()
            pen = QPen(QColor(PRIMARY_HIGHLIGHT), 3)
            painter.setPen(pen)
            painter.drawRect(self.pixmap().rect().adjusted(1, 1, -1, -1))
            painter.restore()

    def _paint_tile(self, painter: QPainter) -> None:
        """Tuile 'bouton vert' sous l'icone -- adaptation DIRECTE de la
        reference doree fournie par l'utilisateur (31/08/2026) : cadre en
        degrade, filet clair, face brillante. Vectoriel : s'adapte a la
        taille d'icone calculee par la mise en page adaptative."""
        rect = QRectF(self.pixmap().rect())
        if rect.width() < 16:
            painter.save()
            painter.fillRect(rect, QColor(_TILE_FACE_BOTTOM))
            painter.restore()
            return
        radius = max(4.0, rect.width() * 0.16)
        frame = max(2.0, rect.width() * 0.055)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # Cadre exterieur (la 'bobine' doree de la reference, en vert).
        frame_grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        frame_grad.setColorAt(0.0, QColor(_TILE_FRAME_TOP))
        frame_grad.setColorAt(1.0, QColor(_TILE_FRAME_BOTTOM))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(frame_grad)
        painter.drawRoundedRect(rect, radius, radius)
        # Face interieure + filet clair juste a l'interieur du cadre.
        inner = rect.adjusted(frame, frame, -frame, -frame)
        face_grad = QLinearGradient(inner.topLeft(), inner.bottomLeft())
        face_grad.setColorAt(0.0, QColor(_TILE_FACE_TOP))
        face_grad.setColorAt(1.0, QColor(_TILE_FACE_BOTTOM))
        painter.setBrush(face_grad)
        painter.drawRoundedRect(inner, radius * 0.72, radius * 0.72)
        inner_stroke = QRectF(inner).adjusted(1.0, 1.0, -1.0, -1.0)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(_TILE_INNER_STROKE), 1.2))
        painter.drawRoundedRect(inner_stroke, radius * 0.72, radius * 0.72)
        # Reflet brillant dans la moitie superieure (l'effet 'verre' de la
        # reference doree).
        gloss = QRectF(inner).adjusted(2.0, 2.0, -2.0, -inner.height() * 0.45)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_TILE_HIGHLIGHT)
        painter.drawRoundedRect(gloss, radius * 0.6, radius * 0.6)
        painter.restore()

    def _paint_cost_badge(self, painter: QPainter) -> None:
        """Badge du cout de deblocage (UnlockCost) sur CHAQUE icone -- EN
        HAUT A GAUCHE et mis a l'ECHELLE DE L'ICONE (demande du 31/08/2026 :
        l'ancien badge bas-droit en police fixe 8pt etait illisible sur
        grand ecran). Pastille sombre semi-transparente + chiffre dore en
        gras : lisible sur la tuile verte comme sur les themes sombres."""
        rect = self.pixmap().rect()
        if rect.width() < 24:
            return  # icones minuscules (vignettes) : le badge serait illisible
        cost_text = str(self.node.unlock_cost)
        font = QFont()
        # setPixelSize : suit EXACTEMENT la taille d'icone calculee par la
        # mise en page adaptative, independamment du DPI systeme.
        font.setPixelSize(max(12, int(rect.width() * 0.17)))
        font.setBold(True)
        painter.save()
        painter.setFont(font)
        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(cost_text)
        pad = max(2, rect.width() // 22)
        badge_w = text_width + pad * 2
        badge_h = metrics.height() + pad // 2
        badge = QRect(rect.left() + 1, rect.top() + 1, badge_w, badge_h)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 170))
        painter.drawRoundedRect(badge, 3, 3)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setPen(QColor(_BADGE_TEXT_COLOR))
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, cost_text)
        painter.restore()

    def mousePressEvent(self, event) -> None:
        self._press_button = event.button()
        self._view.node_selected.emit(self.node.name)
        if self._editable and event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = self.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if not self._editable or self._drag_start_pos is None:
            return
        # Glisser libre en X ET Y -- horizontalement change le niveau de
        # deblocage (persiste, voir on_node_dropped) ; verticalement
        # reorganise la ligne d'affichage (JAMAIS persiste -- aucun champ de
        # position verticale n'existe dans les vrais fichiers -- mais utile
        # pour reorganiser visuellement, notamment lors de duplications,
        # demande explicite de l'utilisateur du 29/08/2026).
        delta = event.scenePos() - event.buttonDownScenePos(Qt.MouseButton.LeftButton)
        self.setPos(self._drag_start_pos + delta)
        self._view.update_connectors_for(self.node.name)

    def mouseReleaseEvent(self, event) -> None:
        if self._editable and self._drag_start_pos is not None:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            moved = (self.pos() - self._drag_start_pos).manhattanLength() > 4
            self._drag_start_pos = None
            if moved:
                self._view.on_node_dropped(self)
            else:
                self._view.snap_item_to_position(self, self.node.unlock_level, self._row)
                # Clic simple SANS deplacement = ouverture de la fiche
                # d'information editable (demande du 31/08/2026) -- apres le
                # snap, pour que la position soit deja correcte.
                if self._press_button == Qt.MouseButton.LeftButton:
                    self._view.node_activated.emit(self.node.name)
        self._press_button = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if self._editable:
            # Depuis le 31/08/2026, le double-clic ouvre LUI AUSSI la fiche
            # (le cout y est editable directement) ; l'ancienne boite de
            # saisie reste accessible via le menu contextuel.
            if event.button() == Qt.MouseButton.LeftButton:
                self._view.node_activated.emit(self.node.name)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event) -> None:
        if self._editable:
            self._view.show_node_context_menu(self.node.name, event.screenPos())


class TechTreeCategoryView(QGraphicsView):
    """Vue d'UNE categorie -- une instance par onglet du dialogue parent
    (voir gui/tech_tree_dialog.py)."""

    node_selected = pyqtSignal(str)
    node_activated = pyqtSignal(str)         # node_name : clic simple/double-clic -> fiche d'info
    level_changed = pyqtSignal(str, int)     # node_name, new_level
    cost_changed = pyqtSignal(str, int)      # node_name, new_cost
    category_changed = pyqtSignal(str, str)  # node_name, new_category
    parent_changed = pyqtSignal(str, str)    # node_name, new_parent ("" = aucun parent/racine)
    parent_pick_started = pyqtSignal(str)    # node_name dont on choisit le nouveau parent
    parent_pick_finished = pyqtSignal()      # fin (choisi, annule, ou "aucun parent")

    def __init__(self, tech_tree: TechTree, category: str, icon_index: dict,
                 all_categories: List[str], parent=None,
                 editable_node_name: Optional[str] = None, highlight_node_name: Optional[str] = None):
        super().__init__(parent)
        self.tech_tree = tech_tree
        self.category = category
        self.icon_index = icon_index
        self.all_categories = all_categories
        self._pending_parent_pick_for: Optional[str] = None
        # Mode previsualisation (voir gui/tech_tree_preview_dialog.py) : si
        # renseigne, SEUL le noeud de ce nom reste deplacable/editable -- les
        # autres (noeuds reels deja existants) restent des reperes visuels
        # statiques. None (par defaut) = comportement normal, tout est
        # editable (dialogue reel, voir gui/tech_tree_dialog.py).
        self.editable_node_name = editable_node_name
        self.highlight_node_name = highlight_node_name
        self._items_by_name: Dict[str, _TechNodeItem] = {}
        self._connectors: Dict[str, QGraphicsPathItem] = {}  # child_name -> chemin (droit ou coude)
        self._connector_branches: Dict[str, bool] = {}  # child_name -> branches_from_parent
        self._bg_scaled_cache: Optional[QPixmap] = None
        self._bg_scaled_cache_size = None
        # Metriques ADAPTATIVES (voir _compute_metrics) -- recalculees au
        # redimensionnement ; remplacent les anciennes constantes module
        # COLUMN_WIDTH/ROW_HEIGHT/HEADER_HEIGHT/ICON_SIZE.
        self._col_w, self._row_h, self._header_h, self._icon_size = _compute_metrics(_DEFAULT_VIEW_WIDTH)

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.rebuild()

    # -- metriques adaptatives ------------------------------------------------

    def _current_metrics(self):
        return _compute_metrics(float(max(1, self.viewport().width())))

    def resizeEvent(self, event) -> None:
        """Recalcule la mise en page adaptative quand la largeur change
        (demande du 31/08/2026 : les 9 jalons restent visibles a toute
        resolution) -- ne reconstruit la scene que si la largeur de colonne
        a reellement bouge (epsilon 1.5 px) pour eviter des rebuilds en
        rafale pendant un redimensionnement interactif."""
        super().resizeEvent(event)
        col_w, row_h, header_h, icon_size = self._current_metrics()
        if (abs(col_w - self._col_w) > 1.5 or row_h != self._row_h
                or header_h != self._header_h or icon_size != self._icon_size):
            self._col_w, self._row_h, self._header_h, self._icon_size = col_w, row_h, header_h, icon_size
            self._bg_scaled_cache = None
            self._bg_scaled_cache_size = None
            self.rebuild()

    # -- fond d'ecran + en-tete FIXE (ne defilent pas avec le contenu) -------

    def drawBackground(self, painter: QPainter, rect) -> None:
        """Image de fond (voir _load_background_pixmap) dessinee en
        coordonnees VIEWPORT fixes (painter.resetTransform()), pas en
        coordonnees de scene -- reste statique quel que soit le defilement,
        demande explicite de l'utilisateur (session du 29/08/2026). Voile
        semi-transparent superpose pour garder icones/lignes lisibles
        par-dessus, meme principe que le fond flou du vrai jeu."""
        painter.save()
        painter.resetTransform()
        viewport_rect = self.viewport().rect()
        bg = _load_background_pixmap()
        if bg is not None:
            if self._bg_scaled_cache is None or self._bg_scaled_cache_size != viewport_rect.size():
                self._bg_scaled_cache = bg.scaled(
                    viewport_rect.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation)
                self._bg_scaled_cache_size = viewport_rect.size()
            scaled = self._bg_scaled_cache
            x = (viewport_rect.width() - scaled.width()) // 2
            y = (viewport_rect.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
            painter.fillRect(viewport_rect, QColor(0, 0, 0, 110))
        else:
            painter.fillRect(viewport_rect, QColor(BG))
        painter.restore()

    def paintEvent(self, event) -> None:
        """Dessine la bande d'en-tete ('Niveau X') APRES le rendu normal de
        la scene, directement sur le viewport (coordonnees fixes, pas la
        scene) -- reste visible en permanence pendant le defilement
        VERTICAL, demande explicite de l'utilisateur. L'abscisse de chaque
        libelle suit en revanche le defilement HORIZONTAL (via mapFromScene)
        pour rester alignee avec sa colonne."""
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        band_rect = self.viewport().rect()
        band_rect.setHeight(self._header_h)
        painter.fillRect(band_rect, QColor(CARD_BG))
        painter.setPen(QPen(QColor(TEXT_GRAY)))
        font = QFont()
        font.setBold(True)
        font.setPixelSize(max(12, int(self._header_h * 0.42)))
        painter.setFont(font)
        for i, level in enumerate(MILESTONE_LEVELS):
            scene_x = i * self._col_w + 8
            view_point = self.mapFromScene(scene_x, 0)
            painter.drawText(view_point.x(), int(self._header_h * 0.62),
                             t("techtree.level_header", level=level))
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawLine(0, self._header_h, self.viewport().width(), self._header_h)
        painter.end()

    # -- construction -----------------------------------------------------

    def rebuild(self) -> None:
        """Reconstruit entierement la scene -- appele a l'ouverture, apres
        tout changement affectant la liste des noeuds de cette categorie
        (deplacement d'un noeud VERS ou DEPUIS cette categorie) et au
        redimensionnement (mise en page adaptative)."""
        from core.tech_tree_layout import compute_node_positions

        self.scene.clear()
        self._items_by_name.clear()
        self._connectors.clear()
        self._connector_branches.clear()

        nodes = self.tech_tree.nodes_in_category(self.category)
        positions = compute_node_positions(nodes)

        # Grille de niveaux FIXE (voir core.tech_tree_layout.MILESTONE_LEVELS)
        # -- confirmee identique sur 10 captures d'ecran F3 reelles, ne varie
        # pas selon les donnees du scenario. Les LIBELLES ('Niveau X') ne sont
        # PLUS des items de scene (ils scrolleraient avec le contenu) -- voir
        # paintEvent() ci-dessus, qui les dessine en surimpression FIXE du
        # viewport (demande explicite : rester visibles pendant le defilement
        # vertical). Seules les lignes verticales en pointilles (reperes de
        # colonne) restent dans la scene, elles doivent bien defiler avec le
        # contenu.
        for i in range(len(MILESTONE_LEVELS)):
            line = QGraphicsLineItem(i * self._col_w + self._col_w / 2, self._header_h,
                                      i * self._col_w + self._col_w / 2, self._header_h + 5000)
            line.setPen(QPen(QColor(BORDER), 1, Qt.PenStyle.DotLine))
            line.setZValue(-10)
            self.scene.addItem(line)

        by_name = {n.name: n for n in nodes}
        for node in nodes:
            pos = positions[node.name]
            pixmap = _load_node_pixmap(self.icon_index, node, self._icon_size)
            editable = self.editable_node_name is None or node.name == self.editable_node_name
            highlighted = node.name == self.highlight_node_name
            item = _TechNodeItem(node, pixmap, self, pos.row, editable=editable, highlighted=highlighted)
            x = pos.x_fraction * self._col_w + (self._col_w - pixmap.width()) / 2
            y = self._row_y(pos.row)
            item.setPos(x, y)
            self.scene.addItem(item)
            self._items_by_name[node.name] = item

        for node in nodes:
            if node.parent_name and node.parent_name in by_name:
                branches = positions[node.name].branches_from_parent
                self._add_connector(node.parent_name, node.name, branches)

        # La marge superieure ne doit JAMAIS remonter au-dessus de y=0 : le
        # bandeau d'en-tete fixe (voir paintEvent) occupe les _header_h
        # premiers pixels du VIEWPORT, pas de la scene -- si sceneRect.top()
        # est negatif, la premiere ligne de noeuds se retrouve partiellement
        # sous le bandeau au defilement initial (bug reel signale par
        # l'utilisateur, capture d'ecran du 29/08/2026).
        bounds = self.scene.itemsBoundingRect().adjusted(-20, 0, 60, 60)
        top = min(0.0, bounds.top())
        self.scene.setSceneRect(bounds.x(), top, bounds.width(), bounds.height() - top)
        self.verticalScrollBar().setValue(self.verticalScrollBar().minimum())
        self.horizontalScrollBar().setValue(self.horizontalScrollBar().minimum())

    def _add_connector(self, parent_name: str, child_name: str, branches: bool) -> None:
        parent_item = self._items_by_name.get(parent_name)
        child_item = self._items_by_name.get(child_name)
        if parent_item is None or child_item is None:
            return
        path_item = QGraphicsPathItem()
        path_item.setPen(QPen(QColor(BORDER), 2))
        path_item.setZValue(-5)
        self.scene.addItem(path_item)
        self._connectors[child_name] = path_item
        self._connector_branches[child_name] = branches
        self._update_connector_geometry(parent_name, child_name)

    def _update_connector_geometry(self, parent_name: str, child_name: str) -> None:
        """Trace soit une ligne droite (le noeud continue la MEME voie que
        son parent -- meme ligne horizontale, cas le plus courant, voir
        core.tech_tree_layout), soit un COUDE en equerre (segment vertical a
        l'abscisse du parent, puis segment horizontal jusqu'a l'enfant) quand
        l'enfant demarre une NOUVELLE voie -- reproduit la disposition
        observee sur de vraies captures F3 (session du 28/08/2026)."""
        path_item = self._connectors.get(child_name)
        parent_item = self._items_by_name.get(parent_name)
        child_item = self._items_by_name.get(child_name)
        if path_item is None or parent_item is None or child_item is None:
            return
        p1 = parent_item.pos() + parent_item.boundingRect().center()
        p2 = child_item.pos() + child_item.boundingRect().center()
        path = QPainterPath()
        path.moveTo(p1)
        if self._connector_branches.get(child_name, False):
            path.lineTo(p1.x(), p2.y())
        path.lineTo(p2)
        path_item.setPath(path)

    def update_connectors_for(self, node_name: str) -> None:
        """Met a jour toute ligne connectee a ce noeud (comme parent OU comme
        enfant) pendant un glisser -- feedback visuel immediat."""
        node = self.tech_tree.get(node_name)
        if node and node.parent_name in self._items_by_name:
            self._update_connector_geometry(node.parent_name, node_name)
        for other in self.tech_tree.nodes_in_category(self.category):
            if other.parent_name == node_name:
                self._update_connector_geometry(node_name, other.name)

    # -- interactions -------------------------------------------------------

    def _column_x_for_level(self, level: int) -> float:
        return level_to_x_fraction(level) * self._col_w + self._col_w / 2

    def _row_y(self, row: int) -> float:
        return self._header_h + row * self._row_h + 10

    def _row_for_y(self, y: float) -> int:
        """Ligne la plus proche d'une position Y -- jamais negative (la ligne
        0 est la plus haute possible, juste sous le bandeau d'en-tete)."""
        return max(0, round((y - self._header_h - 10) / self._row_h))

    def snap_item_to_position(self, item: "_TechNodeItem", level: int, row: int) -> None:
        target_x = self._column_x_for_level(level) - item.pixmap().width() / 2
        target_y = self._row_y(row)
        item.setPos(target_x, target_y)
        item._row = row
        self.update_connectors_for(item.node.name)
        self._extend_scene_rect_if_needed()

    def _extend_scene_rect_if_needed(self) -> None:
        """Un glisser vertical (voir docstring de _TechNodeItem) peut placer
        un noeud plus bas que la zone actuellement visible/scrollable --
        agrandit la scene en consequence, sans jamais reduire la marge
        superieure fixe (voir rebuild(), meme raisonnement anti-chevauchement
        avec le bandeau d'en-tete)."""
        bounds = self.scene.itemsBoundingRect().adjusted(-20, 0, 60, 60)
        current = self.scene.sceneRect()
        top = min(0.0, current.top())
        new_bottom = max(current.bottom(), bounds.bottom())
        self.scene.setSceneRect(min(current.left(), bounds.left()), top,
                                 max(current.width(), bounds.width()), new_bottom - top)

    def on_node_dropped(self, item: "_TechNodeItem") -> None:
        """Fin de glisser horizontal ET/OU vertical (voir docstring de
        _TechNodeItem) :
        - X -> convertit en niveau reel le plus proche PARMI LES JALONS FIXES
          du jeu (voir core.tech_tree_layout.x_fraction_to_level -- grille de
          9 niveaux confirmee sur de vraies captures F3), persiste via
          level_changed si le niveau a change.
        - Y -> convertit en numero de ligne le plus proche. Si la ligne a
          reellement change (reorganisation manuelle), declenche le mode
          'choix du nouveau parent' (voir start_parent_pick) -- demande
          explicite de l'utilisateur du 29/08/2026 : deplacer verticalement
          propose desormais d'ecrire TechTreeParent, pas seulement un
          rearrangement visuel ephemere."""
        old_row = item._row
        center_x = item.pos().x() + item.pixmap().width() / 2
        x_fraction = (center_x - self._col_w / 2) / self._col_w
        new_level = x_fraction_to_level(x_fraction)
        new_row = self._row_for_y(item.pos().y())

        self.snap_item_to_position(item, new_level, new_row)
        if new_level != item.node.unlock_level:
            self.level_changed.emit(item.node.name, new_level)
        if new_row != old_row:
            self.start_parent_pick(item.node.name)

    # -- choix du nouveau parent (suite a un glisser vertical) --------------

    def start_parent_pick(self, node_name: str) -> None:
        self._pending_parent_pick_for = node_name
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.parent_pick_started.emit(node_name)

    def cancel_parent_pick(self) -> None:
        if self._pending_parent_pick_for is None:
            return
        self._pending_parent_pick_for = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.parent_pick_finished.emit()

    def set_no_parent_for_pending_pick(self) -> None:
        if self._pending_parent_pick_for is None:
            return
        node_name = self._pending_parent_pick_for
        self._pending_parent_pick_for = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.parent_changed.emit(node_name, "")
        self.parent_pick_finished.emit()

    def _is_descendant(self, candidate_name: str, of_node_name: str) -> bool:
        """True si candidate_name est of_node_name lui-meme, ou un de ses
        descendants dans CETTE categorie -- evite de creer un cycle
        (un noeud ne peut pas devenir son propre parent, directement ou
        indirectement)."""
        if candidate_name == of_node_name:
            return True
        for child in self.tech_tree.children_of(of_node_name):
            if self._is_descendant(candidate_name, child.name):
                return True
        return False

    def mousePressEvent(self, event) -> None:
        if self._pending_parent_pick_for is not None:
            # self.items(pos) (TOUS les elements a ce point, tries par pile)
            # plutot que self.itemAt(pos) (seulement le tout premier) --
            # bug reel trouve et corrige (29/08/2026) : une ligne de
            # connexion passe exactement par le CENTRE de chaque icone (la
            # ou elle se rattache), et itemAt() y retournait parfois la
            # ligne au lieu de l'icone malgre un Z-value plus bas, faisant
            # totalement echouer le clic de selection du parent (rien ne se
            # passait, et donc rien n'etait jamais enregistre dans le
            # fichier). Filtrer par TYPE plutot que se fier au sommet de
            # pile est fiable quel que soit l'ordre de peinture exact.
            clicked_node_item = next(
                (candidate for candidate in self.items(event.pos()) if isinstance(candidate, _TechNodeItem)), None)
            if clicked_node_item is not None:
                node_name = self._pending_parent_pick_for
                chosen = clicked_node_item.node.name
                if not self._is_descendant(chosen, node_name):
                    self._pending_parent_pick_for = None
                    self.setCursor(Qt.CursorShape.ArrowCursor)
                    self.parent_changed.emit(node_name, chosen)
                    self.parent_pick_finished.emit()
            return  # ne jamais laisser passer un clic normal pendant le choix
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:
        if self._pending_parent_pick_for is not None and event.key() == Qt.Key.Key_Escape:
            self.cancel_parent_pick()
            return
        super().keyPressEvent(event)

    def edit_unlock_cost(self, node_name: str) -> None:
        node = self.tech_tree.get(node_name)
        if node is None:
            return
        new_cost, ok = QInputDialog.getInt(
            self, t("techtree.edit_cost_title"), t("techtree.edit_cost_label", name=node.name),
            value=node.unlock_cost, min=0, max=9999)
        if ok and new_cost != node.unlock_cost:
            self.cost_changed.emit(node_name, new_cost)

    def show_node_context_menu(self, node_name: str, screen_pos) -> None:
        node = self.tech_tree.get(node_name)
        if node is None:
            return
        menu = QMenu(self)
        move_menu = menu.addMenu(t("techtree.move_to_category"))
        for cat in self.all_categories:
            if cat == self.category:
                continue
            action = move_menu.addAction(cat)
            action.triggered.connect(lambda checked=False, c=cat: self.category_changed.emit(node_name, c))
        edit_cost_action = menu.addAction(t("techtree.edit_cost_action"))
        edit_cost_action.triggered.connect(lambda: self.edit_unlock_cost(node_name))
        # PyQt6 : QGraphicsSceneContextMenuEvent.screenPos() retourne deja un
        # QPoint ENTIER (pas un QPointF) -- normaliser pour accepter les deux,
        # selon que l'appelant passe la position d'un evenement scene ou widget.
        if hasattr(screen_pos, "toPoint"):
            screen_pos = screen_pos.toPoint()
        menu.exec(screen_pos)


def _compute_metrics(view_width: float):
    """Metriques de la mise en page ADAPTATIVE (demande du 31/08/2026) :
    (largeur_colonne, hauteur_ligne, hauteur_bandeau, taille_icone).
    Largeur de colonne = largeur utile / 9 jalons (bornee) -> les niveaux
    1 a 25 restent TOUS visibles sans scroll horizontal a toute resolution ;
    icone ~45% de la colonne (bornée), ligne et bandeau proportionnels --
    lisible du petit portable au 4K. Fonction libre pour rester testable
    sans PyQt6 (meme principe que core/tech_tree_layout.py)."""
    col_w = max(COL_MIN, min(COL_MAX, view_width / len(MILESTONE_LEVELS)))
    icon_size = int(max(ICON_MIN, min(ICON_MAX, col_w * 0.45)))
    row_h = int(icon_size * 1.55) + 12
    header_h = max(32, int(icon_size * 0.5))
    return col_w, row_h, header_h, icon_size
