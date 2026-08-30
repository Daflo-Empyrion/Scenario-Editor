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
Tests du scan RECURSIF (fixture derivee d'un vrai AssaultRifle,
ItemsConfig.ecf, session du 29/08/2026) -- bug reel corrige : les
statistiques d'une arme sont declarees dans des sous-blocs imbriques
('{ Child 0 ... }'), pas directement sur le bloc racine.
"""
from pathlib import Path

from core.ecf.parser import parse_ecf_file
from core.localization_lookup import _parse_csv_text, LocalizationIndex
from core.block_info_card import build_block_info_card

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "block_info_card_nested_scenario"


def _load_loc_index() -> LocalizationIndex:
    text = (FIXTURE_DIR / "Localization.csv").read_text(encoding='utf-8')
    return LocalizationIndex(_parse_csv_text(text))


def _get_item(name: str):
    doc = parse_ecf_file(FIXTURE_DIR / "ItemsConfig.ecf")
    for b in doc.iter_blocks():
        if b.get('Name') == name:
            return b
    raise AssertionError(f"item {name} introuvable dans la fixture")


def test_nested_child_block_fields_are_included():
    item = _get_item("AssaultRifle")
    loc = _load_loc_index()
    card = build_block_info_card(item, loc, "fr")
    labels = {f.label for f in card.stat_fields}
    assert "Dégâts" in labels     # Damage, dans '{ Child 0 ... }'
    assert "Munition" in labels   # AmmoType, dans '{ Child 0 ... }'


def test_nested_field_values_match_real_data():
    item = _get_item("AssaultRifle")
    loc = _load_loc_index()
    card = build_block_info_card(item, loc, "fr")
    by_label = {f.label: f.value for f in card.stat_fields}
    assert by_label["Dégâts"] == "70"
    assert by_label["Capacité du chargeur"] == "20"
    assert by_label["Munition"] == "5.8mmBullet"


def test_top_level_and_nested_fields_both_present():
    """Les proprietes du bloc racine (Mass) ET des sous-blocs (Damage)
    doivent coexister dans la meme liste."""
    item = _get_item("AssaultRifle")
    loc = _load_loc_index()
    card = build_block_info_card(item, loc, "fr")
    labels = {f.label for f in card.stat_fields}
    assert "Poids" in labels   # Mass, racine
    assert "Dégâts" in labels  # Damage, Child 0


def test_item_without_nested_children_still_works():
    """Non-regression : un item SANS sous-bloc continue de fonctionner
    normalement (scan recursif = simple scan plat quand rien a descendre)."""
    item = _get_item("ItemWithoutChildren")
    loc = _load_loc_index()
    card = build_block_info_card(item, loc, "fr")
    labels = {f.label for f in card.stat_fields}
    assert len(labels) >= 1


def test_field_carries_raw_source_for_navigation():
    """Chaque champ garde sa cle/valeur BRUTE (non traduite/formatee) pour
    permettre de retrouver la ligne exacte dans le fichier (voir
    gui/block_info_card_widget.py -- clic pour modifier, demande explicite
    de l'utilisateur du 29/08/2026)."""
    item = _get_item("AssaultRifle")
    loc = _load_loc_index()
    card = build_block_info_card(item, loc, "fr")
    damage_field = next(f for f in card.stat_fields if f.label == "Dégâts")
    assert damage_field.source_key == "Damage"
    assert damage_field.source_raw_value == "70"


def test_root_identity_present():
    item = _get_item("AssaultRifle")
    loc = _load_loc_index()
    card = build_block_info_card(item, loc, "fr")
    assert card.root_identity == "15"  # Id du bloc reel


def test_unlock_and_market_price_fields_also_carry_raw_source():
    item = _get_item("AssaultRifle")
    loc = _load_loc_index()
    card = build_block_info_card(item, loc, "fr")
    cost_field = next(f for f in card.unlock_fields if f.source_key == "UnlockCost")
    assert cost_field.source_raw_value == "6"
    assert card.market_price.source_key == "MarketPrice"
    assert card.market_price.source_raw_value == "2538"


# ---------------------------------------------------------------------------
# Integration GUI (EcfEditWidget) -- sous-blocs imbriques, fabrication,
# navigation par clic (demandes explicites du 29/08/2026)
# ---------------------------------------------------------------------------

import shutil

import pytest
from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QTreeWidgetItemIterator


@pytest.fixture
def widget_with_nested_scenario(qapp, tmp_path):
    from gui.ecf_edit_widget import EcfEditWidget

    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    shutil.copy(FIXTURE_DIR / "ItemsConfig.ecf", config_dir / "ItemsConfig.ecf")
    shutil.copy(FIXTURE_DIR / "Templates.ecf", config_dir / "Templates.ecf")
    extras_dir = tmp_path / "Extras"
    extras_dir.mkdir(parents=True)
    shutil.copy(FIXTURE_DIR / "Localization.csv", extras_dir / "Localization.csv")

    return EcfEditWidget(
        config_dir / "ItemsConfig.ecf",
        sibling_ecf_files=[config_dir / "ItemsConfig.ecf", config_dir / "Templates.ecf"],
        working_root=tmp_path)


def _find_tree_item(widget, block_name: str):
    from core.ecf.model import EcfBlock
    it = QTreeWidgetItemIterator(widget.tree)
    while it.value():
        item = it.value()
        block = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(block, EcfBlock) and block.get('Name') == block_name:
            return item
        it += 1
    return None


def _label_containing(widget, text: str):
    for i in range(widget._info_card._content_layout.count()):
        w = widget._info_card._content_layout.itemAt(i).widget()
        if w is not None and hasattr(w, 'text') and text in w.text():
            return w
    return None


def test_nested_child_stats_visible_in_widget(widget_with_nested_scenario):
    widget = widget_with_nested_scenario
    item = _find_tree_item(widget, "AssaultRifle")
    widget._on_tree_item_clicked_for_info_card(item, 0)

    assert _label_containing(widget, "Dégâts") is not None
    assert _label_containing(widget, "Munition") is not None


def test_crafting_section_visible_in_widget(widget_with_nested_scenario):
    widget = widget_with_nested_scenario
    item = _find_tree_item(widget, "AssaultRifle")
    widget._on_tree_item_clicked_for_info_card(item, 0)

    assert _label_containing(widget, "FABRICATION") is not None
    assert _label_containing(widget, "Composants mécaniques") is not None


def test_clicking_nested_field_navigates_to_correct_row(widget_with_nested_scenario):
    """Clic sur 'Dégâts' (Damage, dans '{ Child 0 ... }') doit selectionner
    le sous-bloc Child 0 et afficher sa ligne Damage dans le tableau de
    proprietes -- demande explicite de l'utilisateur (29/08/2026)."""
    widget = widget_with_nested_scenario
    item = _find_tree_item(widget, "AssaultRifle")
    widget._on_block_selected(item, 0)
    widget._on_tree_item_clicked_for_info_card(item, 0)

    damage_label = _label_containing(widget, "Dégâts")
    assert damage_label is not None

    press = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(5, 5), Qt.MouseButton.LeftButton,
                         Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    damage_label.mousePressEvent(press)

    found = any(widget.props_table.item(r, 0) and widget.props_table.item(r, 0).text() == "Damage"
                for r in range(widget.props_table.rowCount()))
    assert found is True


def test_clicking_top_level_field_navigates_to_root_row(widget_with_nested_scenario):
    """Clic sur un champ du bloc RACINE (pas un sous-bloc) doit aussi
    fonctionner -- ici 'Poids' (Mass)."""
    widget = widget_with_nested_scenario
    item = _find_tree_item(widget, "AssaultRifle")
    widget._on_block_selected(item, 0)
    widget._on_tree_item_clicked_for_info_card(item, 0)

    mass_label = _label_containing(widget, "Poids")
    assert mass_label is not None

    press = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(5, 5), Qt.MouseButton.LeftButton,
                         Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    mass_label.mousePressEvent(press)

    found = any(widget.props_table.item(r, 0) and widget.props_table.item(r, 0).text() == "Mass"
                for r in range(widget.props_table.rowCount()))
    assert found is True


# ---------------------------------------------------------------------------
# Bug reel signale par l'utilisateur (29/08/2026) : la fiche d'information
# ne montrait pas la recette d'un bloc juste apres la creation de son
# Template par duplication -- l'ancien code mettait Templates.ecf en cache
# apres une lecture DISQUE unique, jamais rafraichie ; un Template cree par
# duplication vit d'abord en MEMOIRE dans l'onglet Templates.ecf tant qu'il
# n'est pas enregistre.
# ---------------------------------------------------------------------------

def test_info_card_sees_unsaved_template_in_open_tab(qapp, tmp_path):
    from gui.ecf_edit_widget import EcfEditWidget
    BLOCKS_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "block_info_card_scenario"

    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    shutil.copy(BLOCKS_FIXTURE_DIR / "BlocksConfig.ecf", config_dir / "BlocksConfig.ecf")
    (config_dir / "Templates.ecf").write_text("", encoding='utf-8')  # vide sur disque

    blocks_widget = EcfEditWidget(
        config_dir / "BlocksConfig.ecf",
        sibling_ecf_files=[config_dir / "BlocksConfig.ecf", config_dir / "Templates.ecf"])
    templates_widget = EcfEditWidget(config_dir / "Templates.ecf")

    # Simule un Template cree EN MEMOIRE (ex: via duplication), jamais
    # enregistre sur disque -- exactement le cas reel signale.
    from core.ecf.parser import parse_ecf_text
    new_doc = parse_ecf_text(
        "{ Template Name: AssaultRifle\n  CraftTime: 5\n  { Child Inputs\n    Electronics: 8\n  }\n}\n")
    templates_widget.doc.nodes.extend(new_doc.nodes)

    class _FakeMainWindow:
        class _FakeTabs:
            def count(self):
                return 1

            def tabToolTip(self, i):
                return str(config_dir / "Templates.ecf")

            def widget(self, i):
                return templates_widget

        tabs = _FakeTabs()

    blocks_widget.window = lambda: _FakeMainWindow()

    doc = blocks_widget._get_info_card_templates_doc()
    names = [b.get_property('Name') for b in doc.iter_blocks() if b.get_property('Name') == 'AssaultRifle']
    assert names == ['AssaultRifle']  # trouve dans l'onglet EN MEMOIRE, pas sur le disque (vide)


def test_info_card_falls_back_to_disk_when_no_tab_open(qapp, tmp_path):
    from gui.ecf_edit_widget import EcfEditWidget
    BLOCKS_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "block_info_card_scenario"

    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    shutil.copy(BLOCKS_FIXTURE_DIR / "BlocksConfig.ecf", config_dir / "BlocksConfig.ecf")
    shutil.copy(BLOCKS_FIXTURE_DIR / "Templates.ecf", config_dir / "Templates.ecf")

    blocks_widget = EcfEditWidget(
        config_dir / "BlocksConfig.ecf",
        sibling_ecf_files=[config_dir / "BlocksConfig.ecf", config_dir / "Templates.ecf"])

    doc = blocks_widget._get_info_card_templates_doc()
    assert doc is not None
    names = [b.get_property('Name') for b in doc.iter_blocks() if b.get_property('Name') == 'FuelTankMSLarge']
    assert names == ['FuelTankMSLarge']
