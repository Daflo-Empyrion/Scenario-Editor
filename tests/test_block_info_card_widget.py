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

import pytest

from core.block_info_card import BlockInfoCard, InfoCardField, InfoCardIngredient
from gui.block_info_card_widget import BlockInfoCardWidget


@pytest.fixture
def sample_card():
    return BlockInfoCard(
        title="Réservoir de carburant v2",
        icon_key="FuelTankMSLarge",
        description_html="<b>Description test</b>",
        stat_fields=[InfoCardField("Points dommages", "80"), InfoCardField("Poids", "2513 kg")],
        unlock_fields=[InfoCardField("Coût déblocage", "12"), InfoCardField("Niveau déblocage", "10")],
        crafting_header="FABRICATION",
        input_items_label="Composants requis",
        ingredients=[InfoCardIngredient("Composants électroniques", "8")],
        output_count_label="Volume de production", output_count_value="1",
        market_price=InfoCardField("Prix moyen du marché", "3845"),
    )


def test_hidden_by_default(qapp):
    w = BlockInfoCardWidget()
    assert w.isVisible() is False


def test_is_independent_top_level_window(qapp):
    """Bug reel signale par l'utilisateur (29/08/2026) : en tant que simple
    widget ENFANT, Qt decoupait la fiche aux limites de son parent
    (impossible de deplacer/redimensionner au-dela) -- doit maintenant etre
    une vraie fenetre-outil independante (Qt.WindowType.Tool)."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QWidget

    parent = QWidget()
    w = BlockInfoCardWidget(parent)
    assert bool(w.windowFlags() & Qt.WindowType.Tool)
    assert bool(w.windowFlags() & Qt.WindowType.FramelessWindowHint)


def test_can_move_beyond_parent_bounds(qapp, sample_card):
    """Verifie concretement que la fiche n'est plus decoupee aux limites de
    son widget parent -- reproduction directe du bug signale."""
    from PyQt6.QtCore import QPoint
    from PyQt6.QtWidgets import QWidget

    parent = QWidget()
    parent.resize(400, 300)
    w = BlockInfoCardWidget(parent)
    w.show_card("FuelTankMSLarge", sample_card, None)

    far_position = QPoint(1000, 1000)  # tres au-dela des 400x300 du parent
    w.move(far_position)

    assert w.pos() == far_position


def test_styled_background_attribute_set(qapp):
    """Bug reel trouve au rendu (29/08/2026) : QWidget ne peint pas son fond
    CSS par defaut -- sans WA_StyledBackground, le fond noir demande
    explicitement restait invisible."""
    from PyQt6.QtCore import Qt
    w = BlockInfoCardWidget()
    assert w.testAttribute(Qt.WidgetAttribute.WA_StyledBackground) is True


def test_show_card_makes_visible_and_sets_title(qapp, sample_card):
    w = BlockInfoCardWidget()
    w.show_card("FuelTankMSLarge", sample_card, None)
    assert w.isVisible() is True
    assert w.title_label.text() == "Réservoir de carburant v2"


def test_is_showing_tracks_current_block(qapp, sample_card):
    w = BlockInfoCardWidget()
    w.show_card("FuelTankMSLarge", sample_card, None)
    assert w.is_showing("FuelTankMSLarge") is True
    assert w.is_showing("OtherBlock") is False


def test_close_card_hides_and_clears_tracking(qapp, sample_card):
    w = BlockInfoCardWidget()
    w.show_card("FuelTankMSLarge", sample_card, None)
    w.close_card()
    assert w.isVisible() is False
    assert w.is_showing("FuelTankMSLarge") is False


def test_close_button_triggers_close_card(qapp, sample_card):
    w = BlockInfoCardWidget()
    w.show_card("FuelTankMSLarge", sample_card, None)
    w.btn_close.click()
    assert w.isVisible() is False


def test_show_card_replaces_content_for_different_block(qapp, sample_card):
    w = BlockInfoCardWidget()
    w.show_card("FuelTankMSLarge", sample_card, None)
    other_card = BlockInfoCard(title="Autre bloc", icon_key="Other")
    w.show_card("OtherBlock", other_card, None)
    assert w.title_label.text() == "Autre bloc"
    assert w.is_showing("OtherBlock") is True
    assert w.is_showing("FuelTankMSLarge") is False


def test_show_card_handles_minimal_card_without_crashing(qapp):
    """Carte avec le strict minimum (pas de description/stats/fabrication) --
    ne doit jamais planter, meme sans aucune section optionnelle."""
    w = BlockInfoCardWidget()
    minimal = BlockInfoCard(title="Bloc minimal", icon_key="Minimal")
    w.show_card("Minimal", minimal, None)
    assert w.isVisible() is True
    assert w.title_label.text() == "Bloc minimal"


def test_show_card_falls_back_to_generic_icon_when_pixmap_none(qapp, sample_card, monkeypatch):
    from PyQt6.QtGui import QPixmap, QColor
    import gui.block_info_card_widget as bicw

    from PyQt6.QtGui import QIcon

    class _FakeIcon(QIcon):
        """Vrai QIcon ( acceptable par setIcon de la croix) dont le pixmap
        est grise pour verifier le repli d'icone generique de show_card."""

        def __init__(self):
            super().__init__()
            pix = QPixmap(32, 32)
            pix.fill(QColor('gray'))
            self.addPixmap(pix)

    monkeypatch.setattr(bicw, "icon", lambda *a, **k: _FakeIcon())

    w = BlockInfoCardWidget()
    w.show_card("FuelTankMSLarge", sample_card, None)
    assert not w.icon_label.pixmap().isNull()


def test_header_drag_moves_card(qapp, sample_card):
    """Fiche deplacable comme une fenetre en glissant l'en-tete -- demande
    explicite de l'utilisateur (29/08/2026)."""
    from PyQt6.QtCore import Qt, QPoint, QPointF
    from PyQt6.QtGui import QMouseEvent
    from PyQt6.QtCore import QEvent

    w = BlockInfoCardWidget()
    w.show_card("FuelTankMSLarge", sample_card, None)
    w.move(100, 100)

    header = w.layout().itemAt(0).widget()

    start_global = QPoint(150, 110)
    press = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(10, 10), QPointF(start_global),
                         Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    header.mousePressEvent(press)

    move_global = QPoint(200, 160)
    move_event = QMouseEvent(QEvent.Type.MouseMove, QPointF(60, 60), QPointF(move_global),
                              Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    header.mouseMoveEvent(move_event)

    assert w.pos() == QPoint(100, 100) + (move_global - start_global)


def test_icon_and_title_transparent_to_mouse_so_clicks_reach_header(qapp, sample_card):
    """Bug reel signale par l'utilisateur (29/08/2026) : cliquer sur l'icone
    ou le texte du titre (qui occupent la QUASI-TOTALITE de la largeur de
    l'en-tete) interceptait le clic avant qu'il n'atteigne _DraggableHeader,
    empechant tout glisser -- childAt() (qui respecte
    WA_TransparentForMouseEvents, contrairement a QTest.mousePress en
    environnement headless) doit desormais resoudre sur l'en-tete lui-meme,
    pas sur l'icone/le titre."""
    w = BlockInfoCardWidget()
    long_title_card = BlockInfoCard(
        title="Un titre suffisamment long pour occuper toute la largeur de l'en-tete",
        icon_key="Test")
    w.show_card("Test", long_title_card, None)

    header = w.layout().itemAt(0).widget()

    title_point = w.title_label.mapTo(w, w.title_label.rect().center())
    assert w.childAt(title_point) is header

    icon_point = w.icon_label.mapTo(w, w.icon_label.rect().center())
    assert w.childAt(icon_point) is header


def test_resize_grip_resizes_card(qapp, sample_card):
    """Redimensionnement en glissant le coin -- demande explicite de
    l'utilisateur (29/08/2026)."""
    from PyQt6.QtCore import Qt, QPoint, QPointF, QEvent
    from PyQt6.QtGui import QMouseEvent

    w = BlockInfoCardWidget()
    w.show_card("FuelTankMSLarge", sample_card, None)
    original_size = w.size()

    grip = w._resize_grip
    start_global = QPoint(500, 500)
    press = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(5, 5), QPointF(start_global),
                         Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    grip.mousePressEvent(press)

    move_global = QPoint(600, 560)  # +100 largeur, +60 hauteur
    move_event = QMouseEvent(QEvent.Type.MouseMove, QPointF(5, 5), QPointF(move_global),
                              Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    grip.mouseMoveEvent(move_event)

    assert w.width() == original_size.width() + 100
    assert w.height() == original_size.height() + 60


def test_resize_respects_minimum_size(qapp, sample_card):
    from PyQt6.QtCore import Qt, QPoint, QPointF, QEvent
    from PyQt6.QtGui import QMouseEvent
    from gui.block_info_card_widget import _MIN_WIDTH, _MIN_HEIGHT

    w = BlockInfoCardWidget()
    w.show_card("FuelTankMSLarge", sample_card, None)

    grip = w._resize_grip
    start_global = QPoint(500, 500)
    press = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(5, 5), QPointF(start_global),
                         Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    grip.mousePressEvent(press)

    move_global = QPoint(0, 0)  # tentative de reduction massive
    move_event = QMouseEvent(QEvent.Type.MouseMove, QPointF(5, 5), QPointF(move_global),
                              Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    grip.mouseMoveEvent(move_event)

    assert w.width() >= _MIN_WIDTH
    assert w.height() >= _MIN_HEIGHT


def test_growing_card_increases_font_size(qapp, sample_card):
    """Le texte doit grossir avec la fiche -- demande explicite de
    l'utilisateur (29/08/2026)."""
    w = BlockInfoCardWidget()
    w.show_card("FuelTankMSLarge", sample_card, None)
    original_pt = w.title_label.font().pointSizeF()

    w.resize(w.width() * 2, w.height() * 2)

    assert w.title_label.font().pointSizeF() > original_pt


def test_shrinking_card_decreases_font_size(qapp, sample_card):
    w = BlockInfoCardWidget()
    w.show_card("FuelTankMSLarge", sample_card, None)
    w.resize(w.width() * 2, w.height() * 2)
    grown_pt = w.title_label.font().pointSizeF()

    w.resize(int(w.width() / 2), int(w.height() / 2))

    assert w.title_label.font().pointSizeF() < grown_pt


def test_font_scale_clamped_within_bounds(qapp, sample_card):
    w = BlockInfoCardWidget()
    w.show_card("FuelTankMSLarge", sample_card, None)

    w.resize(10000, 10000)  # au-dela du maximum autorise (borne par setMaximumSize)
    assert w._current_scale() <= 3.0

    w.resize(1, 1)  # en-dessous du minimum autorise (borne par setMinimumSize)
    assert w._current_scale() >= 0.7


def test_clicking_stat_label_with_source_emits_field_clicked(qapp):
    """Clic pour naviguer/modifier directement dans le fichier -- demande
    explicite de l'utilisateur (29/08/2026)."""
    from core.block_info_card import InfoCardField
    w = BlockInfoCardWidget()
    card = BlockInfoCard(
        title="Test", icon_key="Test", root_identity="42",
        stat_fields=[InfoCardField("Dégâts", "70", source_key="Damage", source_raw_value="70")])
    w.show_card("Test", card, None)

    received = []
    w.field_clicked.connect(lambda root, key, val: received.append((root, key, val)))

    label = w._content_layout.itemAt(0).widget()
    from PyQt6.QtCore import Qt, QPointF, QEvent
    from PyQt6.QtGui import QMouseEvent
    press = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(5, 5), Qt.MouseButton.LeftButton,
                         Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    label.mousePressEvent(press)

    assert received == [("42", "Damage", "70")]


def test_clicking_stat_label_without_source_emits_nothing(qapp):
    """Champ sans source (ex: ingredient de Templates.ecf, fichier different)
    -- pas de navigation, voir docstring de _ClickableStatLabel."""
    from core.block_info_card import InfoCardIngredient
    w = BlockInfoCardWidget()
    card = BlockInfoCard(
        title="Test", icon_key="Test", root_identity="42",
        crafting_header="FABRICATION", input_items_label="Composants requis",
        ingredients=[InfoCardIngredient("Fer", "5")])
    w.show_card("Test", card, None)

    received = []
    w.field_clicked.connect(lambda root, key, val: received.append((root, key, val)))

    # Le label ingredient est apres le header 'FABRICATION' et 'Composants requis'
    label = w._content_layout.itemAt(2).widget()
    from PyQt6.QtCore import Qt, QPointF, QEvent
    from PyQt6.QtGui import QMouseEvent
    press = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(5, 5), Qt.MouseButton.LeftButton,
                         Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    label.mousePressEvent(press)

    assert received == []


# --------------------------------------- retours utilisateur 30/08/2026
def test_close_button_uses_arrow_cursor(qapp):
    """La croix heritait du curseur 'main ouverte' de l'en-tete draggable --
    un curseur fleche est explicite (retour utilisateur du 30/08/2026)."""
    from PyQt6.QtCore import Qt
    widget = BlockInfoCardWidget()
    assert widget.btn_close.cursor().shape() == Qt.CursorShape.ArrowCursor


def test_stat_label_strips_trailing_colon(qapp):
    """biwOutputCount = 'Volume de production:' (deux-points inclus dans la
    chaine du jeu) : la ligne composée ne doit pas afficher un double
    deux-points ('Volume de production: : 1')."""
    widget = BlockInfoCardWidget()
    lbl = widget._make_stat_label("Volume de production:", "1")
    assert lbl.text() == "Volume de production : <b>1</b>"


def test_stat_label_keeps_normal_labels_untouched(qapp):
    widget = BlockInfoCardWidget()
    lbl = widget._make_stat_label("Points dommages", "80")
    assert lbl.text() == "Points dommages : <b>80</b>"


def test_close_button_has_visible_icon(qapp):
    """Le glyphe unicode '\u2715' etait INVISIBLE dans certains environnements
    Windows (retour du 30/08/2026) : desormais icone fa5s.times de
    l'application, jamais vide."""
    from PyQt6.QtGui import QIcon
    widget = BlockInfoCardWidget()
    assert not widget.btn_close.icon().isNull()
    assert widget.btn_close.text() == ""
    assert isinstance(widget.btn_close.icon(), QIcon)
