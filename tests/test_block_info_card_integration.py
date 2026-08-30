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
Tests d'integration de la fiche d'information flottante (voir
gui/block_info_card_widget.py, core/block_info_card.py) dans EcfEditWidget --
bases sur le VRAI bloc FuelTankMSLarge (fixture derivee d'un vrai
BlocksConfig.ecf/Templates.ecf/Localization.csv, voir
tests/fixtures/block_info_card_scenario/, session du 29/08/2026).
"""
import shutil
from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTreeWidgetItemIterator

from core.ecf.model import EcfBlock

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "block_info_card_scenario"


@pytest.fixture
def widget_with_scenario(qapp, tmp_path):
    from gui.ecf_edit_widget import EcfEditWidget

    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    shutil.copy(FIXTURE_DIR / "BlocksConfig.ecf", config_dir / "BlocksConfig.ecf")
    shutil.copy(FIXTURE_DIR / "Templates.ecf", config_dir / "Templates.ecf")
    extras_dir = tmp_path / "Extras"
    extras_dir.mkdir(parents=True)
    shutil.copy(FIXTURE_DIR / "Localization.csv", extras_dir / "Localization.csv")

    widget = EcfEditWidget(
        config_dir / "BlocksConfig.ecf",
        sibling_ecf_files=[config_dir / "BlocksConfig.ecf", config_dir / "Templates.ecf"],
        working_root=tmp_path)
    return widget


def _find_tree_item(widget, block_name: str):
    it = QTreeWidgetItemIterator(widget.tree)
    while it.value():
        item = it.value()
        block = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(block, EcfBlock) and block.get('Name') == block_name:
            return item
        it += 1
    return None


def test_clicking_block_opens_info_card(widget_with_scenario):
    widget = widget_with_scenario
    item = _find_tree_item(widget, "FuelTankMSLarge")
    assert item is not None

    widget._on_tree_item_double_clicked_for_info_card(item, 0)

    assert widget._info_card is not None
    assert widget._info_card.isHidden() is False
    assert widget._info_card.title_label.text() == "Réservoir de carburant v2"


def test_programmatic_selection_does_not_open_info_card(widget_with_scenario):
    """select_block_by_identity() (recherche, navigation) ne doit PAS ouvrir
    la fiche -- seul un vrai clic (_on_tree_item_double_clicked_for_info_card) le
    fait. Voir docstring de la methode."""
    widget = widget_with_scenario
    widget.select_block_by_identity("FuelTankMSLarge")

    assert widget._info_card is None or widget._info_card.isHidden() is True


def test_close_button_hides_card(widget_with_scenario):
    widget = widget_with_scenario
    item = _find_tree_item(widget, "FuelTankMSLarge")
    widget._on_tree_item_double_clicked_for_info_card(item, 0)

    widget._info_card.btn_close.click()

    assert widget._info_card.isHidden() is True


def test_editing_property_refreshes_open_card_live(widget_with_scenario):
    widget = widget_with_scenario
    item = _find_tree_item(widget, "FuelTankMSLarge")
    widget._on_block_selected(item, 0)
    widget._on_tree_item_double_clicked_for_info_card(item, 0)

    row = next(r for r in range(widget.props_table.rowCount())
               if widget.props_table.item(r, 0).text() == "HitPoints")
    value_item = widget.props_table.item(row, 1)
    value_item.setText("999")
    widget._on_cell_changed(value_item)

    card_text = " ".join(
        widget._info_card._content_layout.itemAt(i).widget().text()
        for i in range(widget._info_card._content_layout.count())
        if widget._info_card._content_layout.itemAt(i).widget() is not None
        and hasattr(widget._info_card._content_layout.itemAt(i).widget(), 'text')
    )
    assert "999" in card_text


def test_editing_property_does_not_reopen_closed_card(widget_with_scenario):
    """Le rafraichissement live ne doit jamais ROUVRIR une fiche fermee --
    seulement mettre a jour celle deja ouverte pour CE bloc precis."""
    widget = widget_with_scenario
    item = _find_tree_item(widget, "FuelTankMSLarge")
    widget._on_block_selected(item, 0)
    widget._on_tree_item_double_clicked_for_info_card(item, 0)
    widget._info_card.close_card()

    row = next(r for r in range(widget.props_table.rowCount())
               if widget.props_table.item(r, 0).text() == "HitPoints")
    value_item = widget.props_table.item(row, 1)
    value_item.setText("777")
    widget._on_cell_changed(value_item)

    assert widget._info_card.isHidden() is True


def test_selecting_different_block_does_not_refresh_stale_card(widget_with_scenario):
    """Editer un bloc B pendant que la fiche affiche un bloc A different ne
    doit pas toucher la fiche (elle n'affiche que A)."""
    widget = widget_with_scenario
    item_a = _find_tree_item(widget, "FuelTankMSLarge")
    widget._on_tree_item_double_clicked_for_info_card(item_a, 0)
    original_title = widget._info_card.title_label.text()

    item_b = _find_tree_item(widget, "BlockWithoutInfoOrTemplate")
    widget._on_block_selected(item_b, 0)  # selection SANS clic sur la fiche (simule navigation)

    row = next(r for r in range(widget.props_table.rowCount())
               if widget.props_table.item(r, 0).text() == "HitPoints")
    value_item = widget.props_table.item(row, 1)
    value_item.setText("42")
    widget._on_cell_changed(value_item)

    assert widget._info_card.title_label.text() == original_title


def test_missing_working_root_does_not_crash(qapp, tmp_path):
    """Widget ouvert sans contexte de scenario complet (working_root=None) --
    la fiche doit quand meme fonctionner (repli sur icone generique, pas de
    Templates.ecf, traduction vanilla uniquement si le pack existe)."""
    from gui.ecf_edit_widget import EcfEditWidget
    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    shutil.copy(FIXTURE_DIR / "BlocksConfig.ecf", config_dir / "BlocksConfig.ecf")

    widget = EcfEditWidget(config_dir / "BlocksConfig.ecf")  # pas de working_root ni sibling_ecf_files
    item = _find_tree_item(widget, "FuelTankMSLarge")
    widget._on_tree_item_double_clicked_for_info_card(item, 0)

    assert widget._info_card.isHidden() is False


def test_manual_drag_position_survives_live_refresh(widget_with_scenario):
    """Deplacer la fiche a la souris (demande explicite du 29/08/2026) ne
    doit jamais etre annule par un rafraichissement en direct (edition d'une
    propriete du MEME bloc affiche) -- seule une VRAIE nouvelle ouverture
    (fiche fermee, ou bloc different) doit repositionner la fiche."""
    from PyQt6.QtCore import QPoint

    widget = widget_with_scenario
    item = _find_tree_item(widget, "FuelTankMSLarge")
    widget._on_block_selected(item, 0)
    widget._on_tree_item_double_clicked_for_info_card(item, 0)

    # Simule un deplacement manuel de l'utilisateur.
    moved_pos = QPoint(5, 5)
    widget._info_card.move(moved_pos)
    assert widget._info_card.pos() == moved_pos

    row = next(r for r in range(widget.props_table.rowCount())
               if widget.props_table.item(r, 0).text() == "HitPoints")
    value_item = widget.props_table.item(row, 1)
    value_item.setText("555")
    widget._on_cell_changed(value_item)

    assert widget._info_card.pos() == moved_pos


def test_reopening_same_block_does_not_reset_manual_position(widget_with_scenario):
    from PyQt6.QtCore import QPoint

    widget = widget_with_scenario
    item = _find_tree_item(widget, "FuelTankMSLarge")
    widget._on_tree_item_double_clicked_for_info_card(item, 0)

    moved_pos = QPoint(7, 7)
    widget._info_card.move(moved_pos)

    widget._on_tree_item_double_clicked_for_info_card(item, 0)  # re-clic sur le MEME bloc

    assert widget._info_card.pos() == moved_pos


def test_opening_different_block_repositions_card(widget_with_scenario):
    """A l'inverse, un bloc DIFFERENT doit bien re-positionner la fiche
    (comportement par defaut, pas de position perimee heritee)."""
    widget = widget_with_scenario
    item_a = _find_tree_item(widget, "FuelTankMSLarge")
    widget._on_tree_item_double_clicked_for_info_card(item_a, 0)
    widget._info_card.move(5, 5)

    item_b = _find_tree_item(widget, "BlockWithoutInfoOrTemplate")
    widget._on_tree_item_double_clicked_for_info_card(item_b, 0)

    assert widget._info_card.pos().x() != 5 or widget._info_card.pos().y() != 5


# -------------------------------------- double-clic (demande du 30/08/2026)
def test_simple_click_does_not_open_info_card(widget_with_scenario):
    """Demande explicite du 30/08/2026 : la fiche s'ouvrait a CHAQUE clic
    simple -- desormais seul le DOUBLE-clic l'ouvre. itemClicked ne doit plus
    etre branche sur la fiche."""
    widget = widget_with_scenario
    item = _find_tree_item(widget, "FuelTankMSLarge")

    # L'ancien gestionnaire de clic simple a ete remplace (renommé) : plus
    # aucun branchement itemClicked -> fiche. Un clic simple ne doit declencher
    # AUCUNE ouverture.
    from gui.ecf_edit_widget import EcfEditWidget
    assert not hasattr(EcfEditWidget, "_on_tree_item_clicked_for_info_card")
    widget.tree.itemClicked.emit(item, 0)

    assert widget._info_card is None or widget._info_card.isHidden() is True


def test_double_click_opens_info_card(widget_with_scenario):
    widget = widget_with_scenario
    item = _find_tree_item(widget, "FuelTankMSLarge")

    widget.tree.itemDoubleClicked.emit(item, 0)

    assert widget._info_card is not None
    assert widget._info_card.isHidden() is False


def test_double_click_same_block_toggles_card_closed(widget_with_scenario):
    """Double-clic sur le bloc DEJA affiche = referme la fiche (bascule) --
    evite l'effet 'se rouvre en boucle' que l'utilisateur voulait supprimer."""
    widget = widget_with_scenario
    item = _find_tree_item(widget, "FuelTankMSLarge")

    widget.tree.itemDoubleClicked.emit(item, 0)
    assert widget._info_card.isHidden() is False

    widget.tree.itemDoubleClicked.emit(item, 0)
    assert widget._info_card.isHidden() is True


def test_double_click_does_not_expand_tree_node(widget_with_scenario):
    """L'expansion par double-clic est desactivee : le double-clic n'ouvre
    QUE la fiche, l'arborescence reste stable."""
    widget = widget_with_scenario
    assert widget.tree.expandsOnDoubleClick() is False


def test_created_template_card_shows_scalars_and_craft(widget_with_scenario):
    """Retour utilisateur du 30/08/2026 : apres creation, la fiche d'un
    Template n'affichait que le nom et les ingredients. Sur un Template
    fraichement cree (proprietes sans attribut 'display'), la fiche doit
    desormais montrer CraftTime/Target/etc. ET la section craft."""
    widget = widget_with_scenario
    templates_doc = widget._get_info_card_templates_doc()
    assert templates_doc is not None
    from core.ecf.parser import parse_ecf_text
    created = parse_ecf_text(
        "{ Template Name: NouvelleVariante\n"
        "  CraftTime: 12\n"
        "  Target: \"BaseC\"\n"
        "  OutputCount: 1\n"
        "  { Child Inputs\n"
        "    SteelPlate: 5\n"
        "  }\n"
        "}\n")
    template_block = next(created.iter_blocks())
    # Simule un Template cree dans l'onglet Templates.ecf ouvert :
    templates_doc.nodes.append(template_block)
    try:
        widget._show_info_card_for(template_block)
        assert widget._info_card is not None
        assert widget._info_card.isHidden() is False
        texts = _card_label_texts(widget._info_card)
        joined = " ".join(texts)
        from core.i18n import t
        craft_label = t("ecfprop.CraftTime")
        assert (craft_label if craft_label != "ecfprop.CraftTime" else "CraftTime") in joined
        basec_label = t("ecfprop.BaseC")
        assert (basec_label if basec_label != "ecfprop.BaseC" else "BaseC") in joined
        # Les ingredients restent confinees a la section craft : l'ingredient
        # SteelPlate (traduit 'Plaque acier' par la localisation) n'y figure
        # qu'UNE seule fois, jamais en doublon dans les statistiques.
        assert joined.count("Plaque acier") == 1
    finally:
        templates_doc.nodes.remove(template_block)


def _card_label_texts(card_widget):
    """Textes de tous les QLabel du contenu de la fiche (section deroulante)
    -- _ClickableStatLabel est une SOUS-CLASSE de QLabel : isinstance, pas
    de comparaison de nom de classe."""
    from PyQt6.QtWidgets import QLabel
    layout = card_widget._content_layout
    texts = []
    for i in range(layout.count()):
        w = layout.itemAt(i).widget()
        if isinstance(w, QLabel):
            texts.append(w.text())
    return texts
