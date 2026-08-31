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
Fiche d'information flottante d'un bloc/item (voir core/block_info_card.py
pour l'assemblage des donnees), DEVENUE EDITABLE -- demande explicite de
l'utilisateur du 31/08/2026 : "chaque valeur puisse etre modifiee directement
sur la fiche sans ouvrir un fichier, meme le Template" (equilibrage rapide
d'un scenario). La fiche n'ECRIT JAMAIS elle-meme : elle emet des signaux
(value_edit_requested, property_add_requested, ...) que l'hote transforme en
ecriture reelle (chemin d'edition de l'editeur ECF, ou ecriture disque +
annulation globale du dialogue d'arbre technologique), puis appelle
refresh() pour re-afficher des donnees fraiches.

Comportement (sessions du 29-31/08/2026) :
  - S'ouvre sur un DOUBLE-clic dans l'editeur ECF, sur un SIMPLE clic dans
    l'arbre technologique (voir les hotes) ; se referme via la croix.
  - BASCULE "vue jeu (F3)" / "vue complete" : par defaut TOUTES les
    proprietes sont affichees (y compris 'display: false') ; la case a
    cocher retombe sur la fiche fidele au jeu. La bascule n'est visible que
    si l'hote a fourni un `provider` capable de reconstruire la fiche.
  - EDITION INLINE : un clic gauche sur une valeur ouvre un champ de saisie
    pre-rempli avec la valeur BRUTE du fichier (jamais la valeur traduite/
    formatee) ; Entree valide, Echap annule. Clic droit : menu (Modifier,
    Supprimer, Aller a la ligne si l'hote fournit la navigation).
  - AJOUT : boutons "+ " sous les statistiques (propriete du bloc) et sous
    les ingredients (Child Inputs du Template).
  - Se rafraichit EN DIRECT si le bloc affiche est modifie ailleurs (voir
    refresh_if_showing cote hotes) -- refresh() reconstruit via provider.
  - Fond NOIR / texte BLANC (retour utilisateur du 29/08/2026, fidele a la
    fiche en jeu), DEPLACABLE par l'en-tete, REDIMENSIONNABLE par la
    poignee en coin, texte grossissant avec la largeur.
"""
from typing import Callable, Optional, Tuple

from PyQt6.QtCore import Qt, QPoint, QSize, pyqtSignal
from PyQt6.QtGui import QPixmap, QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QFrame, QApplication,
    QLineEdit, QComboBox, QMenu, QCheckBox,
)

from core.block_info_card import BlockInfoCard, InfoCardField, card_to_markdown
from core.i18n import t
from gui.theme import icon

_GENERIC_ICON_NAME = "fa5s.cube"
_ICON_SIZE = 40

# Fond noir / texte blanc -- demande explicite (29/08/2026), independant du
# theme clair/sombre de l'application pour ressembler a la vraie fiche F3.
_CARD_BG = "#111111"
_CARD_BORDER = "#3a3a3a"
_CARD_TEXT = "#ffffff"
_CARD_SEPARATOR = "#3a3a3a"
_ROW_HOVER_BG = "#262626"
_EDIT_BORDER = "#ffd34d"
_COMBO_ARROW_COLOR = "#c8c8c8"


def _attach_popup_button(combo: QComboBox) -> None:
    """Fleche d'ouverture de la liste, DESSINEE PAR L'APPLICATION : la fleche
    native du style Windows est un glyphe sombre, invisible sur le fond noir
    de la fiche (retour utilisateur du 31/08/2026) -- on masque la zone
    native (qss width:0) et on pose a la place une action d'icone qtawesome
    au bord droit du champ, qui ouvre la liste (showPopup)."""
    from gui.theme import icon as _icon
    combo.lineEdit().addAction(
        _icon("fa5s.caret-down", color=_COMBO_ARROW_COLOR),
        QLineEdit.ActionPosition.TrailingPosition).triggered.connect(combo.showPopup)

# Redimensionnement -- largeur de reference pour le calcul du facteur
# d'echelle du texte (voir _current_scale), et bornes min/max pour eviter une
# fiche illisible (trop petite) ou demesuree (trop grande).
_BASE_WIDTH = 340
_BASE_HEIGHT = 320
_MIN_WIDTH = 220
_MIN_HEIGHT = 150
_MAX_WIDTH = 1000
_MAX_HEIGHT = 1400
_RESIZE_GRIP_SIZE = 16


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


class _InlineValueRow(QWidget):
    """UNE ligne editable de la fiche : libelle + valeur. Clic gauche sur la
    ligne -> edition INLINE (QLineEdit pre-rempli avec la valeur BRUTE) ;
    clic droit -> menu (Modifier / Supprimer / Aller a la ligne). La ligne
    n'ecrit rien : elle emet les callbacks de la fiche (voir
    BlockInfoCardWidget). `from_template` distingue une propriete du bloc
    lui-meme d'un ingredient/OutputCount vivant dans Templates.ecf."""

    def __init__(self, label_html: str, value_html: str, raw_value: str,
                 card_widget: "BlockInfoCardWidget", source_key: Optional[str],
                 source_raw_value: Optional[str], from_template: bool = False,
                 deletable: bool = True, parent=None):
        super().__init__(parent)
        self._card = card_widget
        self._source_key = source_key
        self._source_raw_value = source_raw_value or ""
        self._from_template = from_template
        self._deletable = deletable
        self._label_html = label_html
        self._value_html = value_html
        self._base_point_size = QApplication.font().pointSizeF() or 9.0
        self._editor: Optional[QLineEdit] = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(2, 1, 2, 1)
        lay.setSpacing(4)
        self._lbl = QLabel()
        self._lbl.setTextFormat(Qt.TextFormat.RichText)
        self._lbl.setWordWrap(True)
        self._set_value_display()
        lay.addWidget(self._lbl, 1)

        editable = card_widget.editable and source_key is not None
        if editable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip(t("block_info.click_to_edit_tooltip"))
        elif source_key is None:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)

    # -- rendu -------------------------------------------------------------

    def _set_value_display(self) -> None:
        label = (self._label_html or "").rstrip().rstrip(':').rstrip()
        self._lbl.setText(f"{label} : <b>{self._value_html}</b>")

    def apply_scale(self, scale: float) -> None:
        f = self._lbl.font()
        f.setPointSizeF(self._base_point_size * scale)
        self._lbl.setFont(f)
        if self._editor is not None:
            fe = self._editor.font()
            fe.setPointSizeF(self._base_point_size * scale)
            self._editor.setFont(fe)

    # -- edition inline ------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if (event.button() == Qt.MouseButton.LeftButton
                and self._card.editable and self._source_key is not None
                and self._editor is None):
            self.start_edit()
            return
        super().mousePressEvent(event)

    def start_edit(self) -> None:
        if self._editor is not None or self._source_key is None:
            return
        # Liste deroulante EDITABLE quand la propriete a un historique dans
        # le fichier (valeurs observees, tri frequence -- meme regle que le
        # tableau de proprietes, demande du 31/08/2026) ; saisie libre
        # toujours possible (combo editable, et QLineEdit pur sinon).
        values = self._card.values_for_key(self._source_key)
        base_qss = (f"QComboBox, QComboBox:editable, QComboBox QAbstractItemView, "
                    f"QLineEdit {{ background: #000000; color: {_CARD_TEXT}; "
                    f"border: 1px solid {_EDIT_BORDER}; border-radius: 3px; padding: 1px 3px; }}"
                    f"QComboBox::drop-down {{ border: none; width: 0px; }}")
        if values:
            editor = QComboBox(self)
            editor.setEditable(True)
            editor.addItems(values)
            editor.setCurrentText(self._source_raw_value)
            editor.setStyleSheet(base_qss)
            editor.lineEdit().setStyleSheet(
                f"QLineEdit {{ background: #000000; color: {_CARD_TEXT}; "
                f"border: none; padding: 1px 3px; }}")
            # editingFinished couvre Entree ET perte de focus (comportement
            # standard des tableaux Qt) ; Escape seul annule (eventFilter).
            editor.lineEdit().editingFinished.connect(self._commit)
            editor.installEventFilter(self)
            editor.lineEdit().installEventFilter(self)
            _attach_popup_button(editor)
        else:
            editor = QLineEdit(self._source_raw_value, self)
            editor.setStyleSheet(
                f"QLineEdit {{ background: #000000; color: {_CARD_TEXT}; "
                f"border: 1px solid {_EDIT_BORDER}; border-radius: 3px; padding: 1px 3px; }}")
            editor.editingFinished.connect(self._commit)
            editor.installEventFilter(self)
        f = editor.font()
        f.setPointSizeF(self._base_point_size * self._card._current_scale())
        editor.setFont(f)
        self._editor = editor
        self.layout().addWidget(editor, 2)
        self._lbl.setVisible(False)
        editor.setFocus()
        if isinstance(editor, QLineEdit):
            editor.selectAll()

    def eventFilter(self, obj, event) -> bool:
        if event.type() == event.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            line_edit = getattr(self._editor, "lineEdit", None)
            targets = {self._editor, line_edit() if callable(line_edit) else None}
            if obj in targets:
                self._cancel()
                return True
        return super().eventFilter(obj, event)

    def _commit(self) -> None:
        if self._editor is None:
            return
        if isinstance(self._editor, QComboBox):
            new_value = self._editor.currentText()
        else:
            new_value = self._editor.text()
        self._stop_edit()
        if new_value != self._source_raw_value:
            self._card.value_edit_requested.emit(
                self._source_key, self._source_raw_value, new_value, self._from_template)

    def _cancel(self) -> None:
        self._stop_edit()

    def _stop_edit(self) -> None:
        if self._editor is not None:
            self._editor.deleteLater()
            self._editor = None
        self._lbl.setVisible(True)

    # -- menu contextuel -----------------------------------------------------

    def _show_menu(self, pos) -> None:
        if self._source_key is None or not self._card.editable:
            return
        menu = QMenu(self)
        act_edit = menu.addAction(t("block_info.menu_edit"))
        act_edit.triggered.connect(self.start_edit)
        if self._deletable:
            act_del = menu.addAction(t("block_info.menu_delete"))
            act_del.triggered.connect(self._request_delete)
        if self._card._navigation_callback is not None:
            act_nav = menu.addAction(t("block_info.menu_goto"))
            act_nav.triggered.connect(self._request_goto)
        menu.exec(self.mapToGlobal(pos))

    def _request_delete(self) -> None:
        if self._from_template:
            self._card.ingredient_remove_requested.emit(self._source_key, self._source_raw_value)
        else:
            self._card.property_remove_requested.emit(self._source_key, self._source_raw_value)

    def _request_goto(self) -> None:
        if self._card._navigation_callback is not None:
            self._card._navigation_callback(self._card.root_identity,
                                            self._source_key, self._source_raw_value)

    def mouseDoubleClickEvent(self, event) -> None:
        # Double-clic = meme action qu'un simple clic (edition) : sans cela,
        # le deuxieme clic retombe apres la premiere edition et seleccione du
        # texte du QLabel.
        if (event.button() == Qt.MouseButton.LeftButton
                and self._card.editable and self._source_key is not None):
            self.start_edit()
            return
        super().mouseDoubleClickEvent(event)


class _AddRow(QWidget):
    """Formulaire inline d'AJOUT (propriete ou ingredient) : deux champs
    (cle, valeur) + validation, en listes deroulantes EDITABLES pre-remplies
    avec les cles/valeurs observees dans le fichier (meme regle que le
    reste de l'application : tri frequence, saisie libre toujours possible).
    Cache par defaut, affiche par le bouton "+" correspondant. N'ecrit rien :
    emet ingredient_add_requested ou property_add_requested de la fiche hote."""

    def __init__(self, card_widget: "BlockInfoCardWidget", from_template: bool, parent=None):
        super().__init__(parent)
        self._card = card_widget
        self._from_template = from_template
        lay = QHBoxLayout(self)
        lay.setContentsMargins(2, 1, 2, 1)
        lay.setSpacing(4)
        base_qss = (f"QComboBox, QComboBox:editable, QComboBox QAbstractItemView, "
                    f"QLineEdit {{ background: #000000; color: {_CARD_TEXT}; "
                    f"border: 1px solid {_CARD_SEPARATOR}; border-radius: 3px; padding: 1px 3px; }}"
                    f"QComboBox::drop-down {{ border: none; width: 0px; }}")
        self.ed_key = QComboBox()
        self.ed_key.setEditable(True)
        if from_template:
            # Un ingredient est un ITEM ou un BLOC : la combo propose les noms
            # reellement definis dans ItemsConfig.ecf/BlocksConfig.ecf (meme
            # pool que la creation de Template, voir list_craftable_names) --
            # PAS des cles de proprietes (retour utilisateur du 31/08/2026).
            for name in card_widget.ingredient_choices():
                self.ed_key.addItem(name)
        else:
            for key in card_widget.known_keys():
                self.ed_key.addItem(key)
        self.ed_key.setCurrentText("")
        self.ed_key.setStyleSheet(base_qss)
        self.ed_key.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        # Placeholders : QComboBox editable expose un QLineEdit interne qui
        # les supporte (guide l'utilisateur, n'empeche pas la saisie libre).
        self.ed_key.lineEdit().setPlaceholderText(t("block_info.add_key_placeholder"))
        _attach_popup_button(self.ed_key)
        lay.addWidget(self.ed_key, 1)
        self.ed_value = QComboBox()
        self.ed_value.setEditable(True)
        self.ed_value.setStyleSheet(base_qss)
        self.ed_value.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.ed_value.lineEdit().setPlaceholderText(t("block_info.add_value_placeholder"))
        _attach_popup_button(self.ed_value)
        lay.addWidget(self.ed_value, 1)
        if not from_template:
            # La liste des valeurs suit la cle tapee (valeurs observees pour
            # CETTE propriete) -- NoInsert garde le texte libre sans polluer
            # la liste pour les champs suivants. Sans objet pour un
            # ingredient (la valeur est une quantite, saisie libre).
            self.ed_key.editTextChanged.connect(self._refresh_value_choices)
        self.btn_ok = QPushButton()
        self.btn_ok.setFixedSize(22, 22)
        self.btn_ok.setIcon(icon("fa5s.check", color=_CARD_TEXT))
        self.btn_ok.setIconSize(QSize(12, 12))
        self.btn_ok.setToolTip(t("btn.ok"))
        self.btn_ok.clicked.connect(self._commit)
        lay.addWidget(self.btn_ok)
        self.btn_cancel = QPushButton()
        self.btn_cancel.setFixedSize(22, 22)
        self.btn_cancel.setIcon(icon("fa5s.times", color=_CARD_TEXT))
        self.btn_cancel.setIconSize(QSize(12, 12))
        self.btn_cancel.setToolTip(t("btn.cancel"))
        self.btn_cancel.clicked.connect(self.hide)
        lay.addWidget(self.btn_cancel)
        self.hide()

    def _refresh_value_choices(self, key_text: str) -> None:
        values = self._card.values_for_key(key_text.strip())
        self.ed_value.blockSignals(True)
        self.ed_value.clear()
        if values:
            self.ed_value.addItems(values)
        self.ed_value.blockSignals(False)

    def _commit(self) -> None:
        key = self.ed_key.currentText().strip()
        if not key:
            return
        value = self.ed_value.currentText()
        if self._from_template:
            self._card.ingredient_add_requested.emit(key, value)
        else:
            self._card.property_add_requested.emit(key, value)
        self.ed_key.setCurrentText("")
        self.ed_value.setCurrentText("")
        self.hide()


class BlockInfoCardWidget(QWidget):
    """Fiche flottante EDITABLE -- enfant direct du widget qui l'affiche (voir
    gui/ecf_edit_widget.py et gui/tech_tree_dialog.py). La fiche n'ecrit
    JAMAIS elle-meme : elle emet des signaux que l'hote transforme en
    ecritures reelles, puis appelle refresh(). `provider`, fourni par l'hote,
    reconstruit (BlockInfoCard, QPixmap) pour l'etat ACTUEL du fichier -- il
    alimente la bascule vue jeu/vue complete et refresh().
    Chaque ligne de statistique (issue du fichier COURAMMENT ouvert, pas de
    Templates.ecf) est editable inline -- voir _InlineValueRow."""

    field_clicked = pyqtSignal(str, str, str)          # root_identity, source_key, source_raw_value (navigation)
    value_edit_requested = pyqtSignal(str, str, str, bool)  # source_key, old_value, new_value, from_template
    property_add_requested = pyqtSignal(str, str)      # key, value
    property_remove_requested = pyqtSignal(str, str)   # source_key, old_value
    ingredient_add_requested = pyqtSignal(str, str)    # key, quantity
    ingredient_remove_requested = pyqtSignal(str, str) # key, old_quantity

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_block_name: Optional[str] = None
        self._current_card: Optional[BlockInfoCard] = None
        self._provider: Optional[Callable[[bool], Tuple[BlockInfoCard, Optional[QPixmap]]]] = None
        self._values_provider: Optional[Callable[[], dict]] = None
        self._ingredients_provider: Optional[Callable[[], list]] = None
        self._navigation_callback: Optional[Callable[[str, str, str], None]] = None
        self.editable: bool = True
        self._show_all: bool = True  # vue COMPLETE par defaut (demande du 31/08/2026)
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
        # Glyphe unicode '\u2715' INVISIBLE dans certains environnements
        # Windows (retour utilisateur du 30/08/2026 : croix absente) --
        # icone qtawesome fa5s.times de l'application, rendue partout, comme
        # les autres boutons de l'interface.
        self.btn_close = QPushButton()
        self.btn_close.setFixedSize(22, 22)
        self.btn_close.setIcon(icon("fa5s.times", color=_CARD_TEXT))
        self.btn_close.setIconSize(QSize(13, 13))
        self.btn_close.setText("")
        # Curseur FLECHE explicite : l'en-tete parent utilise le curseur
        # 'main ouverte' (deplacement de la fiche) et les enfants heritent
        # -- la croix heritait d'un curseur main absurde (retour utilisateur
        # du 30/08/2026). Style plat SANS bord ni fond : discrete au repos,
        # legere pastille grise au survol uniquement.
        self.btn_close.setCursor(Qt.CursorShape.ArrowCursor)
        self.btn_close.setToolTip(t("btn.close"))
        self.btn_close.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; "
            f"border-radius: 4px; }}"
            f"QPushButton:hover {{ background: #3a3a3a; }}"
            f"QPushButton:pressed {{ background: #4a4a4a; }}"
        )
        self.btn_close.clicked.connect(self.close_card)
        header_row.addWidget(self.btn_close, 0, Qt.AlignmentFlag.AlignTop)
        # Export Markdown de la fiche (ajout suite a l'audit du 30/08/2026) :
        # meme rendu que la fiche affichee, deplace vers un fichier .md.
        self.btn_export = QPushButton()
        self.btn_export.setFixedSize(22, 22)
        self.btn_export.setIcon(icon("fa5s.file-export", color=_CARD_TEXT))
        self.btn_export.setIconSize(QSize(13, 13))
        self.btn_export.setText("")
        self.btn_export.setCursor(Qt.CursorShape.ArrowCursor)
        self.btn_export.setToolTip(t("block_info.export_title"))
        self.btn_export.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; "
            f"border-radius: 4px; }}"
            f"QPushButton:hover {{ background: #3a3a3a; }}"
            f"QPushButton:pressed {{ background: #4a4a4a; }}"
        )
        self.btn_export.clicked.connect(self._export_card)
        header_row.addWidget(self.btn_export, 0, Qt.AlignmentFlag.AlignTop)
        outer.addWidget(header)

        # Bascule VUE JEU / VUE COMPLETE (demande du 31/08/2026) -- cochee =
        # fiche fidele au F3 du jeu (les 'display: false' sont masques),
        # decochee = TOUTES les proprietes. N'est visible que si l'hote a
        # fourni un provider capable de reconstruire la fiche.
        self._toggle_row = QHBoxLayout()
        self._toggle_row.setContentsMargins(0, 0, 0, 0)
        self._toggle_row.addStretch(1)
        self.chk_game_view = QCheckBox(t("block_info.game_view_toggle"))
        self.chk_game_view.setCursor(Qt.CursorShape.ArrowCursor)
        self.chk_game_view.setStyleSheet(f"QCheckBox {{ color: #c8c8c8; font-size: 11px; }}")
        self.chk_game_view.toggled.connect(self._on_toggle_game_view)
        self._toggle_row.addWidget(self.chk_game_view)
        outer.addLayout(self._toggle_row)

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

    # -- API hote ------------------------------------------------------------

    def set_navigation_callback(self, callback: Optional[Callable[[str, str, str], None]]) -> None:
        """Callback optionnel (root_identity, source_key, source_raw_value)
        appele par 'Aller a la ligne' du menu contextuel -- l'editeur ECF y
        branche sa navigation ; l'arbre technologique laisse None."""
        self._navigation_callback = callback

    def values_for_key(self, key: Optional[str]) -> list:
        """Valeurs observees dans le fichier pour UNE cle de propriete, tri
        frequence (regle projet 'liste deroulante editable partout') --
        fournies par le `values_provider` de l'hote ; liste vide = la ligne
        retombe sur une saisie libre simple."""
        if self._values_provider is None or not key:
            return []
        try:
            mapping = self._values_provider() or {}
        except Exception:
            return []
        return list(mapping.get(key, []))

    def known_keys(self) -> list:
        """Toutes les cles de propriete connues de l'hote (pour le formulaire
        d'ajout de propriete) -- meme source, ordre fourni par l'hote."""
        if self._values_provider is None:
            return []
        try:
            mapping = self._values_provider() or {}
        except Exception:
            return []
        return list(mapping.keys())

    def ingredient_choices(self) -> list:
        """Noms d'items/blocs proposables comme ingredient (formulaire
        d'ajout d'ingredient) -- fournis par l'`ingredients_provider` de
        l'hote (list_craftable_names des deux fichiers de configuration)."""
        if self._ingredients_provider is None:
            return []
        try:
            return list(self._ingredients_provider() or [])
        except Exception:
            return []

    def is_showing(self, block_name: str) -> bool:
        """Utilise isHidden() (etat propre de CE widget) plutot que
        isVisible() (qui depend de toute la chaine de widgets parents et
        renverrait False si le widget englobant n'est pas lui-meme affiche,
        meme si show()/hide() a bien ete appele explicitement sur cette
        fiche -- comportement Qt standard, non desirable ici)."""
        return not self.isHidden() and self._current_block_name == block_name

    def show_card(self, block_name: str, card: BlockInfoCard, icon_pixmap: Optional[QPixmap],
                  provider: Optional[Callable[[bool], Tuple[BlockInfoCard, Optional[QPixmap]]]] = None,
                  editable: bool = True,
                  values_provider: Optional[Callable[[], dict]] = None,
                  ingredients_provider: Optional[Callable[[], list]] = None) -> None:
        self._current_block_name = block_name
        self._current_card = card
        self.root_identity = card.root_identity
        # providers/editable : conserves entre deux ouvertures seulement si
        # l'hote ne les repasse pas (None = garder l'existant).
        if provider is not None:
            self._provider = provider
        if values_provider is not None:
            self._values_provider = values_provider
        if ingredients_provider is not None:
            self._ingredients_provider = ingredients_provider
        self.editable = editable
        self.chk_game_view.setVisible(self._provider is not None)

        if icon_pixmap is not None and not icon_pixmap.isNull():
            self.icon_label.setPixmap(icon_pixmap.scaled(
                _ICON_SIZE, _ICON_SIZE, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.icon_label.setPixmap(icon(_GENERIC_ICON_NAME, color=QColor(_CARD_TEXT)).pixmap(_ICON_SIZE, _ICON_SIZE))
        self.title_label.setText(card.title)
        self.title_label.setTextFormat(Qt.TextFormat.RichText)

        self._rebuild_content()
        self.show()
        self.raise_()
        self._resize_grip.raise_()

    def refresh(self) -> None:
        """Reconstruit la fiche depuis le provider de l'hote (donnees
        fraiches apres une ecriture reelle). Sans provider, ne fait rien --
        l'hote doit alors rappeler show_card() avec une fiche deja construite."""
        if self._provider is None or self._current_block_name is None:
            return
        try:
            card, pixmap = self._provider(self._show_all)
        except Exception:
            return  # bloc disparu (suppression) : garder l'affichage actuel
        self._current_card = card
        self.root_identity = card.root_identity
        if pixmap is not None and not pixmap.isNull():
            self.icon_label.setPixmap(pixmap.scaled(
                _ICON_SIZE, _ICON_SIZE, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.title_label.setText(card.title)
        self._rebuild_content()

    def close_card(self) -> None:
        self._current_block_name = None
        self._current_card = None
        self.hide()

    # -- construction du contenu ---------------------------------------------

    def _clear_content(self) -> None:
        while self._content_layout.count():
            child = self._content_layout.takeAt(0)
            w = child.widget()
            if w is not None:
                w.deleteLater()

    def _rebuild_content(self) -> None:
        card = self._current_card
        self._clear_content()
        if card is None:
            return

        if card.description_html:
            desc = QLabel(card.description_html)
            desc.setTextFormat(Qt.TextFormat.RichText)
            desc.setWordWrap(True)
            self._content_layout.addWidget(desc)
            self._add_separator()

        if card.stat_fields:
            for f in card.stat_fields:
                self._content_layout.addWidget(self._make_row(f.label, f.value, f.source_key,
                                                               f.source_raw_value, from_template=False))
            self._add_add_row(from_template=False)
            self._add_separator()

        if card.unlock_fields:
            for f in card.unlock_fields:
                self._content_layout.addWidget(self._make_row(f.label, f.value, f.source_key,
                                                               f.source_raw_value, from_template=False))
            self._add_separator()

        if card.crafting_header:
            self._content_layout.addWidget(self._make_bold_label(card.crafting_header))
            if card.input_items_label and card.ingredients:
                self._content_layout.addWidget(self._make_bold_label(card.input_items_label))
                for ing in card.ingredients:
                    self._content_layout.addWidget(self._make_row(
                        ing.name, ing.quantity, ing.source_key, ing.source_raw_value,
                        from_template=True))
            if card.output_count is not None:
                self._content_layout.addWidget(self._make_row(
                    card.output_count.label, card.output_count.value,
                    card.output_count.source_key, card.output_count.source_raw_value,
                    from_template=True, deletable=False))
            self._add_add_row(from_template=True)
            self._add_separator()

        if card.market_price:
            self._content_layout.addWidget(self._make_row(
                card.market_price.label, card.market_price.value,
                card.market_price.source_key, card.market_price.source_raw_value,
                from_template=False))

        self._content_layout.addStretch(1)
        self._apply_font_scale()

    def _make_row(self, label: str, value: str, source_key: Optional[str],
                   source_raw_value: Optional[str], from_template: bool,
                   deletable: bool = True) -> _InlineValueRow:
        # Certaines chaines du jeu se terminent par ':' (ex: biwOutputCount ->
        # 'Volume de production:') -- sans ce retrait, l'etiquette composée
        # affichait un double deux-points ('Volume de production: : 1'),
        # constate le 30/08/2026.
        label = label.rstrip().rstrip(':').rstrip()
        return _InlineValueRow(label, value, source_raw_value or "", self,
                               source_key, source_raw_value, from_template=from_template,
                               deletable=deletable)

    def _add_add_row(self, from_template: bool) -> None:
        """Bouton '+' + formulaire inline d'ajout (demande du 31/08/2026 :
        ajout de proprietes ET d'ingredients directement depuis la fiche).
        Inactif si la fiche n'est pas editable."""
        if not self.editable:
            return
        add_row = _AddRow(self, from_template=from_template)
        btn = QPushButton(t("block_info.add_button") if not from_template
                          else t("block_info.add_ingredient_button"))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #9aa4b2; "
            "text-align: left; padding: 1px 2px; font-size: 11px; }"
            "QPushButton:hover { color: #ffffff; }")

        def _toggle(checked: bool = False, w=add_row):
            # ATTENTION : clicked(bool) passe son booleen en 1er argument --
            # sans ce parametre explicite, il ecrasait `w` (bug reel du
            # 31/08/2026 : AttributeError 'bool' has no attribute
            # 'setVisible' a l'ouverture du formulaire).
            w.setVisible(not w.isVisible())
            if w.isVisible():
                w.ed_key.setFocus()

        btn.clicked.connect(_toggle)
        self._content_layout.addWidget(btn)
        self._content_layout.addWidget(add_row)

    def _make_bold_label(self, text: str) -> QLabel:
        lbl = QLabel(f"<b>{text}</b>")
        lbl.setTextFormat(Qt.TextFormat.RichText)
        return lbl

    def _add_separator(self) -> None:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {_CARD_SEPARATOR}; background: {_CARD_SEPARATOR};")
        self._content_layout.addWidget(line)

    # -- bascule vue jeu / vue complete ---------------------------------------

    def _on_toggle_game_view(self, checked: bool) -> None:
        self._show_all = not checked
        self.refresh()

    # -- mise en page ----------------------------------------------------------

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
            if isinstance(w, _InlineValueRow):
                w.apply_scale(scale)
            elif isinstance(w, QLabel):
                f = w.font()
                f.setPointSizeF(self._base_point_size * scale)
                w.setFont(f)

    # -- export -----------------------------------------------------------------

    def _export_card(self) -> None:
        """Exporte la fiche ACTUELLEMENT AFFICHEE en Markdown (voir
        core.block_info_card.card_to_markdown) via l'utilitaire d'export
        partage des fenetres de resultats -- meme comportement de selection
        de fichier, d'ecriture atomique et de confirmation que partout."""
        if self._current_card is None:
            return
        from gui.results_window_helpers import export_text_to_file
        export_text_to_file(
            self, f"{self.root_identity or 'block'}.md",
            card_to_markdown(self._current_card),
            title_key="block_info.export_title",
            file_filter="Markdown (*.md)")
