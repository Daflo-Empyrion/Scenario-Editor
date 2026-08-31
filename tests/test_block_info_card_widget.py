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

from PyQt6.QtWidgets import QPushButton

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
        ingredients=[InfoCardIngredient("Composants électroniques", "8", "Composants électroniques", "8")],
        output_count=InfoCardField("Volume de production", "1", "OutputCount", "1"),
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


def test_clicking_row_with_source_starts_inline_edit_and_emits_on_enter(qapp):
    """Demande du 31/08/2026 (fiche editable) : un clic sur une valeur avec
    source ouvre une edition INLINE pre-remplie avec la valeur BRUTE du
    fichier ; la validation emet value_edit_requested (l'ancien clic ->
    navigation field_clicked est remplace par le menu contextuel)."""
    from core.block_info_card import InfoCardField
    w = BlockInfoCardWidget()
    card = BlockInfoCard(
        title="Test", icon_key="Test", root_identity="42",
        stat_fields=[InfoCardField("Dégâts", "70", source_key="Damage", source_raw_value="70")])
    w.show_card("Test", card, None)

    row = w._content_layout.itemAt(0).widget()
    from PyQt6.QtCore import Qt, QPointF, QEvent
    from PyQt6.QtGui import QMouseEvent
    press = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(5, 5), Qt.MouseButton.LeftButton,
                         Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    row.mousePressEvent(press)

    assert row._editor is not None
    assert row._editor.text() == "70"  # valeur BRUTE, pas le libelle traduit

    received = []
    w.value_edit_requested.connect(lambda key, old, new, tpl: received.append((key, old, new, tpl)))
    row._editor.setText("55")
    row._commit()
    assert received == [("Damage", "70", "55", False)]
    assert row._editor is None  # edition refermee


def test_row_without_source_is_not_editable(qapp):
    """Champ sans source (ex: ingredient sans paire brute) -- jamais
    editable, un clic ne fait rien."""
    from core.block_info_card import InfoCardIngredient
    w = BlockInfoCardWidget()
    card = BlockInfoCard(
        title="Test", icon_key="Test", root_identity="42",
        crafting_header="FABRICATION", input_items_label="Composants requis",
        ingredients=[InfoCardIngredient("Fer", "5")])
    w.show_card("Test", card, None)

    received = []
    w.value_edit_requested.connect(lambda key, old, new, tpl: received.append((key, old, new, tpl)))

    # Le row ingredient est apres le header 'FABRICATION' et 'Composants requis'
    row = w._content_layout.itemAt(2).widget()
    from PyQt6.QtCore import Qt, QPointF, QEvent
    from PyQt6.QtGui import QMouseEvent
    press = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(5, 5), Qt.MouseButton.LeftButton,
                         Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    row.mousePressEvent(press)

    assert row._editor is None
    assert received == []


def test_navigation_callback_invoked_from_row(qapp):
    """La navigation 'Aller a la ligne' (ancien comportement du clic gauche,
    29/08/2026) est preservee via set_navigation_callback + menu contextuel."""
    from core.block_info_card import InfoCardField
    w = BlockInfoCardWidget()
    card = BlockInfoCard(
        title="Test", icon_key="Test", root_identity="42",
        stat_fields=[InfoCardField("Dégâts", "70", source_key="Damage", source_raw_value="70")])
    w.show_card("Test", card, None)

    received = []
    w.set_navigation_callback(lambda root, key, val: received.append((root, key, val)))
    row = w._content_layout.itemAt(0).widget()
    row._request_goto()
    assert received == [("42", "Damage", "70")]


def test_game_view_toggle_calls_provider_and_hides_display_false_fields(qapp):
    """Bascule 'vue jeu (F3)' : cochee -> la fiche est reconstruite via le
    provider avec show_all=False ; decochee -> vue complete (defaut)."""
    from core.block_info_card import InfoCardField

    def provider(show_all: bool):
        fields = [InfoCardField("Points dommages", "80", "HitPoints", "80")]
        if show_all:
            fields.append(InfoCardField("Secret", "42", "SecretStat", "42"))
        return BlockInfoCard(title="Test", icon_key="Test", root_identity="42",
                             stat_fields=fields), None

    w = BlockInfoCardWidget()
    card, _pix = provider(True)
    w.show_card("Test", card, None, provider=provider)

    labels_complete = {w._content_layout.itemAt(i).widget()._label_html
                       for i in range(w._content_layout.count())
                       if isinstance(w._content_layout.itemAt(i).widget(), type(w._content_layout.itemAt(0).widget()))}
    assert any("Secret" in lbl for lbl in labels_complete)

    w.chk_game_view.setChecked(True)  # declenche refresh() -> show_all=False
    texts = [w._content_layout.itemAt(i).widget()._lbl.text()
             for i in range(w._content_layout.count())
             if hasattr(w._content_layout.itemAt(i).widget(), "_lbl")]
    assert not any("Secret" in txt for txt in texts)
    assert any("Points dommages" in txt for txt in texts)

    w.chk_game_view.setChecked(False)  # retour vue complete
    texts = [w._content_layout.itemAt(i).widget()._lbl.text()
             for i in range(w._content_layout.count())
             if hasattr(w._content_layout.itemAt(i).widget(), "_lbl")]
    assert any("Secret" in txt for txt in texts)


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
    row = widget._make_row("Volume de production:", "1", None, "", from_template=False)
    assert row._lbl.text() == "Volume de production : <b>1</b>"


def test_stat_label_keeps_normal_labels_untouched(qapp):
    widget = BlockInfoCardWidget()
    row = widget._make_row("Points dommages", "80", None, "", from_template=False)
    assert row._lbl.text() == "Points dommages : <b>80</b>"


def test_close_button_has_visible_icon(qapp):
    """Le glyphe unicode '\u2715' etait INVISIBLE dans certains environnements
    Windows (retour du 30/08/2026) : desormais icone fa5s.times de
    l'application, jamais vide."""
    from PyQt6.QtGui import QIcon
    widget = BlockInfoCardWidget()
    assert not widget.btn_close.icon().isNull()
    assert widget.btn_close.text() == ""
    assert isinstance(widget.btn_close.icon(), QIcon)


# --------------------------------------- retour utilisateur 31/08/2026 (2)
# Bug reel : cliquer '+ Ajouter une propriete' levait AttributeError (le
# signal clicked(bool) ecrasait le parametre du callback) + demande des
# listes deroulantes editables sur les champs de la fiche (meme regle que
# le tableau de proprietes : valeurs observees, tri frequence, saisie libre).

def test_add_button_shows_inline_form(qapp):
    """Regression du bug 'bool' has no attribute 'setVisible' : cliquer le
    bouton '+' doit AFFICHER le formulaire inline, jamais planter."""
    from core.block_info_card import InfoCardField
    from gui.block_info_card_widget import _AddRow
    w = BlockInfoCardWidget()
    card = BlockInfoCard(title="Test", icon_key="Test", root_identity="42",
                         stat_fields=[InfoCardField("Dégâts", "70", "Damage", "70")])
    w.show_card("Test", card, None)

    add_rows = [w._content_layout.itemAt(i).widget()
                for i in range(w._content_layout.count())
                if isinstance(w._content_layout.itemAt(i).widget(), _AddRow)]
    assert len(add_rows) == 1
    assert not add_rows[0].isVisible()

    buttons = [w._content_layout.itemAt(i).widget()
               for i in range(w._content_layout.count())
               if isinstance(w._content_layout.itemAt(i).widget(), QPushButton)]
    add_btn = next(b for b in buttons if "Ajouter" in b.text())
    add_btn.click()  # plantait avant le fix

    assert add_rows[0].isVisible()
    add_btn.click()
    assert not add_rows[0].isVisible()


def _values_provider_case_helper(qapp, with_history=True):
    """(widget, row) avec values_provider {"HitPoints": [...]} -- reutilisee
    par plusieurs tests d'edition inline."""
    return _values_provider_case(qapp, with_history)


def _values_provider_case(qapp, with_history=True):
    from core.block_info_card import InfoCardField
    w = BlockInfoCardWidget()

    def values_provider():
        return {"HitPoints": ["80", "120", "999"]} if with_history else {}

    card = BlockInfoCard(title="Test", icon_key="Test", root_identity="42",
                         stat_fields=[InfoCardField("Points dommages", "80", "HitPoints", "80")])
    w.show_card("Test", card, None, values_provider=values_provider)
    row = w._content_layout.itemAt(0).widget()
    return w, row


def test_row_edit_uses_observed_values_combo(qapp):
    """Champ avec historique dans le fichier -> liste deroulante EDITABLE
    pre-remplie avec les valeurs observees (tri frequence), valeur brute
    courante preselectionnee."""
    from PyQt6.QtWidgets import QComboBox
    w, row = _values_provider_case(qapp)
    row.start_edit()
    assert isinstance(row._editor, QComboBox)
    assert [row._editor.itemText(i) for i in range(row._editor.count())] == ["80", "120", "999"]
    assert row._editor.currentText() == "80"  # valeur brute courante

    received = []
    w.value_edit_requested.connect(lambda k, o, n, t: received.append((k, o, n, t)))
    row._editor.setCurrentText("999")  # choix dans la liste
    row._commit()
    assert received == [("HitPoints", "80", "999", False)]


def test_row_edit_allows_free_typing_in_combo(qapp):
    """La saisie libre reste toujours possible dans la combo (regle projet)."""
    w, row = _values_provider_case(qapp)
    row.start_edit()
    received = []
    w.value_edit_requested.connect(lambda k, o, n, t: received.append((k, o, n, t)))
    row._editor.setCurrentText("12345")  # pas dans la liste
    row._commit()
    assert received == [("HitPoints", "80", "12345", False)]


def test_row_edit_falls_back_to_line_edit_without_history(qapp):
    """Sans historique pour cette cle (ou sans provider) : saisie libre
    simple (QLineEdit), jamais de plantage."""
    from PyQt6.QtWidgets import QLineEdit
    w, row = _values_provider_case(qapp, with_history=False)
    row.start_edit()
    assert isinstance(row._editor, QLineEdit)
    assert row._editor.text() == "80"


def test_add_row_key_and_value_combos_follow_observed_values(qapp):
    """Formulaire d'ajout : la combo de cles propose les cles observees, et
    celle des valeurs suit la cle tapee (saisie libre conservee)."""
    from PyQt6.QtWidgets import QComboBox
    from core.block_info_card import InfoCardField
    from gui.block_info_card_widget import _AddRow
    w = BlockInfoCardWidget()

    def values_provider():
        return {"HitPoints": ["80", "120"], "Mass": ["2513"]}

    card = BlockInfoCard(title="Test", icon_key="Test", root_identity="42",
                         stat_fields=[InfoCardField("Points dommages", "80", "HitPoints", "80")])
    w.show_card("Test", card, None, values_provider=values_provider)

    add_row = next(w._content_layout.itemAt(i).widget()
                   for i in range(w._content_layout.count())
                   if isinstance(w._content_layout.itemAt(i).widget(), _AddRow))
    assert isinstance(add_row.ed_key, QComboBox)
    assert set(add_row.ed_key.itemText(i) for i in range(add_row.ed_key.count())) == {"HitPoints", "Mass"}

    add_row.ed_key.setCurrentText("Mass")
    assert [add_row.ed_value.itemText(i) for i in range(add_row.ed_value.count())] == ["2513"]
    add_row.ed_key.setCurrentText("Inconnu")
    assert add_row.ed_value.count() == 0  # saisie libre, liste vide

    received = []
    w.property_add_requested.connect(lambda k, v: received.append((k, v)))
    add_row.ed_key.setCurrentText("HitPoints")
    add_row.ed_value.setCurrentText("42")
    add_row._commit()
    assert received == [("HitPoints", "42")]


def test_add_ingredient_row_lists_item_names_not_properties(qapp):
    """Retour utilisateur du 31/08/2026 : l'ajout d'INGREDIENT doit proposer
    les noms d'items/blocs (meme pool que la creation de Template), pas des
    cles de proprietes. Saisie libre conservee."""
    from core.block_info_card import InfoCardIngredient
    from gui.block_info_card_widget import _AddRow
    w = BlockInfoCardWidget()

    def values_provider():
        return {"HitPoints": ["80", "120"]}

    def ingredients_provider():
        return ["OxygenTankSmall", "FuelTankMSLarge", "SteelPlate"]

    card = BlockInfoCard(title="Test", icon_key="Test", root_identity="42",
                         crafting_header="FABRICATION", input_items_label="Composants requis",
                         ingredients=[InfoCardIngredient("Electronics", "8", "Electronics", "8")])
    w.show_card("Test", card, None, values_provider=values_provider,
                ingredients_provider=ingredients_provider)

    add_rows = [w._content_layout.itemAt(i).widget()
                for i in range(w._content_layout.count())
                if isinstance(w._content_layout.itemAt(i).widget(), _AddRow)]
    # La carte de test n'a pas de stat_fields : seule la section fabrication
    # porte son formulaire d'ajout, dedie AUX INGREDIENTS.
    assert len(add_rows) == 1
    ing = add_rows[0]
    assert ing._from_template is True

    assert set(ing.ed_key.itemText(i) for i in range(ing.ed_key.count())) == \
        {"OxygenTankSmall", "FuelTankMSLarge", "SteelPlate"}
    # La combo de valeur d'un ingredient ne suit PAS les valeurs de
    # proprietes (une quantite se tape librement).
    assert ing.ed_value.count() == 0

    received = []
    w.ingredient_add_requested.connect(lambda k, v: received.append((k, v)))
    ing.ed_key.setCurrentText("CustomItem")  # saisie libre
    ing.ed_value.setCurrentText("3")
    ing._commit()
    assert received == [("CustomItem", "3")]


def test_combo_editors_have_visible_popup_action(qapp):
    """La fleche native du style Windows est invisible sur le fond noir de
    la fiche : une action 'caret-down' dessinee par l'application doit etre
    posee au bord du champ et ouvrir la liste."""
    from PyQt6.QtWidgets import QComboBox
    w, row = _values_provider_case(qapp)
    row.start_edit()
    assert isinstance(row._editor, QComboBox)
    assert len(row._editor.lineEdit().actions()) == 1  # l'action fleche
