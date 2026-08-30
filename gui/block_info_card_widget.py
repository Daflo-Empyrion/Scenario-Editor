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
Fiche d'information flottante d'un bloc/item, reproduisant la fiche affichee
EN JEU (voir core/block_info_card.py pour l'assemblage des donnees et sa
verification detaillee contre une vraie capture d'ecran F3).

Comportement confirme aupres de l'utilisateur (session du 29/08/2026) :
  - S'ouvre UNIQUEMENT sur un clic explicite sur un bloc (jamais au survol,
    contrairement aux tooltips de l'arbre technologique) -- voir
    gui/ecf_edit_widget.py::_on_block_selected, seul point d'appel.
  - Se rafraichit EN DIRECT si le bloc affiche est modifie pendant que la
    fiche est ouverte -- voir refresh_if_showing().
  - Se ferme via la croix.
  - Fond NOIR / texte BLANC (retour utilisateur du 29/08/2026 -- pas le theme
    clair de l'application, pour ressembler a la vraie fiche en jeu).
  - DEPLACABLE a la souris comme une fenetre (glisser depuis l'en-tete).
  - REDIMENSIONNABLE en glissant le coin inferieur droit (poignee
    _ResizeGrip), le texte grossit proportionnellement a la largeur --
    demande explicite de l'utilisateur (29/08/2026).
"""
from typing import Optional

from PyQt6.QtCore import Qt, QPoint, QSize, pyqtSignal
from PyQt6.QtGui import QPixmap, QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QFrame, QApplication,
)

from core.block_info_card import BlockInfoCard
from gui.theme import icon

_GENERIC_ICON_NAME = "fa5s.cube"
_ICON_SIZE = 40

# Fond noir / texte blanc -- demande explicite (29/08/2026), independant du
# theme clair/sombre de l'application pour ressembler a la vraie fiche F3.
_CARD_BG = "#111111"
_CARD_BORDER = "#3a3a3a"
_CARD_TEXT = "#ffffff"
_CARD_SEPARATOR = "#3a3a3a"

# Redimensionnement -- largeur de reference pour le calcul du facteur
# d'echelle du texte (voir _current_scale), et bornes min/max pour eviter une
# fiche illisible (trop petite) ou demesuree (trop grande).
_BASE_WIDTH = 340
_BASE_HEIGHT = 320
_MIN_WIDTH = 220
_MIN_HEIGHT = 150
_MAX_WIDTH = 1000
_MAX_HEIGHT = 1000
_RESIZE_GRIP_SIZE = 16


class _ClickableStatLabel(QLabel):
    """Ligne de statistique cliquable -- clic gauche emet
    BlockInfoCardWidget.field_clicked(root_identity, source_key,
    source_raw_value) pour naviguer directement vers la ligne correspondante
    dans le fichier source et permettre sa modification -- demande explicite
    de l'utilisateur (29/08/2026). Non cliquable (curseur normal, pas de
    signal) si source_key est None (ex: ingredients de Templates.ecf --
    fichier different, navigation non geree pour l'instant, voir docstring
    du module)."""

    def __init__(self, text: str, card_widget: "BlockInfoCardWidget",
                 source_key: Optional[str], source_raw_value: Optional[str], parent=None):
        super().__init__(text, parent)
        self._card_widget = card_widget
        self._source_key = source_key
        self._source_raw_value = source_raw_value
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setWordWrap(True)
        if source_key is not None:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._source_key is not None:
            self._card_widget.field_clicked.emit(
                self._card_widget.root_identity, self._source_key, self._source_raw_value or "")
        super().mousePressEvent(event)


class _DraggableHeader(QWidget):
    """Zone d'en-tete (icone + titre + croix) qui deplace toute la fiche
    quand on la glisse -- demande explicite de l'utilisateur (29/08/2026)."""

    def __init__(self, card_widget: "BlockInfoCardWidget", parent=None):
        super().__init__(parent)
        self._card_widget = card_widget
        self._drag_offset: Optional[QPoint] = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self._card_widget.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None:
            self._card_widget.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)


class _ResizeGrip(QWidget):
    """Poignee de redimensionnement (coin inferieur droit) -- QSizeGrip standard
    de Qt redimensionne la FENETRE de plus haut niveau, pas ce widget-ci (simple
    enfant, pas une fenetre independante) : implementation directe necessaire,
    meme principe que _DraggableHeader mais pour resize() plutot que move().
    Demande explicite de l'utilisateur (29/08/2026)."""

    def __init__(self, card_widget: "BlockInfoCardWidget", parent=None):
        super().__init__(parent)
        self._card_widget = card_widget
        self._drag_start_global: Optional[QPoint] = None
        self._drag_start_size: Optional[QSize] = None
        self.setFixedSize(_RESIZE_GRIP_SIZE, _RESIZE_GRIP_SIZE)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setPen(QPen(QColor(_CARD_TEXT), 1))
        for offset in (2, 6, 10):
            painter.drawLine(self.width() - 2 - offset, self.height() - 2,
                              self.width() - 2, self.height() - 2 - offset)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_global = event.globalPosition().toPoint()
            self._drag_start_size = self._card_widget.size()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start_global is not None:
            delta = event.globalPosition().toPoint() - self._drag_start_global
            new_width = max(_MIN_WIDTH, min(_MAX_WIDTH, self._drag_start_size.width() + delta.x()))
            new_height = max(_MIN_HEIGHT, min(_MAX_HEIGHT, self._drag_start_size.height() + delta.y()))
            self._card_widget.resize(new_width, new_height)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_start_global = None
        super().mouseReleaseEvent(event)


class BlockInfoCardWidget(QWidget):
    """Fiche flottante -- enfant direct du widget qui l'affiche (voir
    gui/ecf_edit_widget.py). Position initiale geree par l'appelant (voir
    _position_info_card cote EcfEditWidget), deplacable ensuite librement a
    la souris via son en-tete (voir _DraggableHeader), redimensionnable via
    la poignee en coin (voir _ResizeGrip) -- le texte grossit avec la taille.
    Chaque ligne de statistique (issue du fichier COURAMMENT ouvert, pas de
    Templates.ecf) est cliquable -- voir field_clicked."""

    field_clicked = pyqtSignal(str, str, str)  # root_identity, source_key, source_raw_value

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_block_name: Optional[str] = None
        self.root_identity: str = ""
        self._base_point_size = QApplication.font().pointSizeF() or 9.0
        # Fenetre-outil INDEPENDANTE plutot qu'un simple widget enfant --
        # bug reel signale par l'utilisateur (29/08/2026) : en tant que
        # simple enfant, Qt decoupait strictement la fiche aux limites de la
        # fenetre d'edition (impossible de deplacer/redimensionner au-dela).
        # Qt.WindowType.Tool = fenetre flottante sans entree dans la barre
        # des taches, reste au-dessus de son parent ; FramelessWindowHint
        # retire la barre de titre native (deja notre propre en-tete/croix).
        # `parent` est conserve pour la duree de vie (fermee avec l'onglet)
        # SANS clipper son affichage aux limites du parent.
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        # QWidget ne peint PAS son arriere-plan CSS par defaut (contrairement
        # a QFrame/QLabel) -- sans cet attribut, le fond noir demande
        # explicitement par l'utilisateur (29/08/2026) reste invisible (le
        # widget parent transparait a travers, bug reel trouve au rendu).
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"BlockInfoCardWidget {{ background: {_CARD_BG}; border: 1px solid {_CARD_BORDER}; "
            f"border-radius: 8px; }} QLabel {{ color: {_CARD_TEXT}; background: transparent; }}"
        )
        self.setMinimumSize(_MIN_WIDTH, _MIN_HEIGHT)
        self.setMaximumSize(_MAX_WIDTH, _MAX_HEIGHT)
        self.resize(_BASE_WIDTH, _BASE_HEIGHT)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 10)
        outer.setSpacing(6)

        header = _DraggableHeader(self)
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(0, 0, 0, 0)
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(_ICON_SIZE, _ICON_SIZE)
        # Transparent aux evenements souris -- sans cela, cliquer sur
        # l'icone ou le titre (qui occupe presque toute la largeur de
        # l'en-tete via le facteur d'etirement 1 ci-dessous) intercepte le
        # clic AVANT qu'il n'atteigne _DraggableHeader, empechant tout
        # glisser -- bug reel signale par l'utilisateur (29/08/2026).
        self.icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        header_row.addWidget(self.icon_label)
        self.title_label = QLabel()
        title_font = self.title_label.font()
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setWordWrap(True)
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        header_row.addWidget(self.title_label, 1)
        self.btn_close = QPushButton("\u2715")
        self.btn_close.setFixedSize(22, 22)
        self.btn_close.setStyleSheet(
            f"QPushButton {{ background: #2a2a2a; color: {_CARD_TEXT}; border: 1px solid {_CARD_BORDER}; "
            f"border-radius: 4px; }} QPushButton:hover {{ background: #3a3a3a; }}"
        )
        self.btn_close.clicked.connect(self.close_card)
        header_row.addWidget(self.btn_close, 0, Qt.AlignmentFlag.AlignTop)
        outer.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        self._content_widget = QWidget()
        self._content_widget.setStyleSheet("background: transparent;")
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(3)
        scroll.setWidget(self._content_widget)
        outer.addWidget(scroll, 1)

        self._resize_grip = _ResizeGrip(self, self)
        self._resize_grip.raise_()
        self._position_resize_grip()

        self.hide()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_resize_grip()
        self._apply_font_scale()

    def _position_resize_grip(self) -> None:
        self._resize_grip.move(self.width() - _RESIZE_GRIP_SIZE - 2, self.height() - _RESIZE_GRIP_SIZE - 2)

    def _current_scale(self) -> float:
        """Facteur d'echelle du texte, derive de la LARGEUR actuelle par
        rapport a la largeur de reference -- borne entre 0.7x et 3x pour
        rester lisible sans jamais devenir absurde."""
        return max(0.7, min(3.0, self.width() / _BASE_WIDTH))

    def _apply_font_scale(self) -> None:
        scale = self._current_scale()
        title_font = self.title_label.font()
        title_font.setPointSizeF(self._base_point_size * scale * 1.15)
        self.title_label.setFont(title_font)
        for i in range(self._content_layout.count()):
            w = self._content_layout.itemAt(i).widget()
            if isinstance(w, QLabel):
                f = w.font()
                f.setPointSizeF(self._base_point_size * scale)
                w.setFont(f)

    def close_card(self) -> None:
        self._current_block_name = None
        self.hide()

    def is_showing(self, block_name: str) -> bool:
        """Utilise isHidden() (etat propre de CE widget) plutot que
        isVisible() (qui depend de toute la chaine de widgets parents et
        renverrait False si le widget englobant n'est pas lui-meme affiche,
        meme si show()/hide() a bien ete appele explicitement sur cette
        fiche -- comportement Qt standard, non desirable ici)."""
        return not self.isHidden() and self._current_block_name == block_name

    def show_card(self, block_name: str, card: BlockInfoCard, icon_pixmap: Optional[QPixmap]) -> None:
        self._current_block_name = block_name
        self.root_identity = card.root_identity

        if icon_pixmap is not None and not icon_pixmap.isNull():
            self.icon_label.setPixmap(icon_pixmap.scaled(
                _ICON_SIZE, _ICON_SIZE, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.icon_label.setPixmap(icon(_GENERIC_ICON_NAME, color=QColor(_CARD_TEXT)).pixmap(_ICON_SIZE, _ICON_SIZE))
        self.title_label.setText(card.title)
        self.title_label.setTextFormat(Qt.TextFormat.RichText)

        while self._content_layout.count():
            child = self._content_layout.takeAt(0)
            w = child.widget()
            if w is not None:
                w.deleteLater()

        if card.description_html:
            desc = QLabel(card.description_html)
            desc.setTextFormat(Qt.TextFormat.RichText)
            desc.setWordWrap(True)
            self._content_layout.addWidget(desc)
            self._add_separator()

        if card.stat_fields:
            for f in card.stat_fields:
                self._content_layout.addWidget(self._make_stat_label(f.label, f.value, f.source_key, f.source_raw_value))
            self._add_separator()

        if card.unlock_fields:
            for f in card.unlock_fields:
                self._content_layout.addWidget(self._make_stat_label(f.label, f.value, f.source_key, f.source_raw_value))
            self._add_separator()

        if card.crafting_header:
            self._content_layout.addWidget(self._make_bold_label(card.crafting_header))
            if card.input_items_label and card.ingredients:
                self._content_layout.addWidget(self._make_bold_label(card.input_items_label))
                for ing in card.ingredients:
                    # Ingredients viennent de Templates.ecf (fichier DIFFERENT
                    # de celui actuellement ouvert) -- navigation non geree
                    # pour l'instant, voir docstring de _ClickableStatLabel.
                    self._content_layout.addWidget(self._make_stat_label(ing.name, ing.quantity, None, None))
            if card.output_count_value is not None:
                self._content_layout.addWidget(
                    self._make_stat_label(card.output_count_label, card.output_count_value, None, None))
            self._add_separator()

        if card.market_price:
            self._content_layout.addWidget(self._make_stat_label(
                card.market_price.label, card.market_price.value,
                card.market_price.source_key, card.market_price.source_raw_value))

        self._content_layout.addStretch(1)
        self._apply_font_scale()
        self.show()
        self.raise_()
        self._resize_grip.raise_()

    def _make_stat_label(self, label: str, value: str, source_key: Optional[str] = None,
                          source_raw_value: Optional[str] = None) -> QLabel:
        text = f"{label} : <b>{value}</b>"
        lbl = _ClickableStatLabel(text, self, source_key, source_raw_value)
        return lbl

    def _make_bold_label(self, text: str) -> QLabel:
        lbl = QLabel(f"<b>{text}</b>")
        lbl.setTextFormat(Qt.TextFormat.RichText)
        return lbl

    def _add_separator(self) -> None:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {_CARD_SEPARATOR}; background: {_CARD_SEPARATOR};")
        self._content_layout.addWidget(line)
