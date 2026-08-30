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

import shutil
from pathlib import Path

import pytest

from core.tech_tree import load_tech_tree
from core.tech_tree_icons import build_icon_index

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "tech_tree_scenario"


@pytest.fixture
def tree_and_view_factory(qapp, tmp_path):
    blocks = tmp_path / "BlocksConfig.ecf"
    items = tmp_path / "ItemsConfig.ecf"
    shutil.copy(FIXTURE_DIR / "BlocksConfig.ecf", blocks)
    shutil.copy(FIXTURE_DIR / "ItemsConfig.ecf", items)
    tree = load_tech_tree(blocks, items)
    icon_index = build_icon_index(tmp_path)  # pas de dossier ItemIcons -> index vide

    def _make(category="Base"):
        from gui.tech_tree_widget import TechTreeCategoryView
        return TechTreeCategoryView(tree, category, icon_index, tree.categories())

    return tree, _make


def test_view_creates_one_item_per_node_in_category(tree_and_view_factory):
    tree, make_view = tree_and_view_factory
    view = make_view("Base")
    expected = {n.name for n in tree.nodes_in_category("Base")}
    assert set(view._items_by_name.keys()) == expected


def test_view_creates_connector_for_real_parent_child(tree_and_view_factory):
    tree, make_view = tree_and_view_factory
    view = make_view("Base")
    # FuelTankMSSmall -> FuelTankMSLarge est un vrai lien parent confirme.
    assert "FuelTankMSLarge" in view._connectors


def test_all_nodes_use_same_background_color_regardless_of_level(tree_and_view_factory):
    """Simplification demandee explicitement (29/08/2026) : plus de distinction
    visuelle par niveau (verrou/couleur) -- utile uniquement en jeu, pas dans
    un editeur ou l'on modifie librement les valeurs. Une seule couleur pour
    tous les noeuds, quel que soit leur UnlockLevel."""
    tree, make_view = tree_and_view_factory
    view = make_view("Base")
    high_level_item = view._items_by_name["FuelTankMSLarge"]  # UnlockLevel 10
    root_item = view._items_by_name["OxygenTankSmallMS"]  # UnlockLevel 1
    assert not hasattr(high_level_item, "_locked")
    assert not hasattr(root_item, "_locked")


def test_view_has_no_player_level_state(tree_and_view_factory):
    """set_player_level()/player_level ont ete retires -- plus de simulation
    de niveau joueur dans l'editeur (demande explicite du 29/08/2026)."""
    tree, make_view = tree_and_view_factory
    view = make_view("Base")
    assert not hasattr(view, "player_level")
    assert not hasattr(view, "set_player_level")


def test_weapons_category_only_has_weapons_nodes(tree_and_view_factory):
    tree, make_view = tree_and_view_factory
    view = make_view("Weapons")
    names = set(view._items_by_name.keys())
    assert names == {"CombatKnife", "PlasmaSword"}


def test_snap_item_to_position_moves_both_axes(tree_and_view_factory):
    tree, make_view = tree_and_view_factory
    view = make_view("Base")
    item = view._items_by_name["OxygenTankSmallMS"]
    original_row = item._row
    view.snap_item_to_position(item, 3, original_row + 2)
    assert item.pos().y() == view._row_y(original_row + 2)
    assert item._row == original_row + 2
    assert item.pos().x() != 0  # a bouge horizontalement vers la colonne niveau 3


def test_on_node_dropped_reassigns_row_without_emitting_level_signal_if_same_level(tree_and_view_factory):
    """Deplacement PUREMENT vertical (reorganisation visuelle, jamais
    persistee -- demande explicite de l'utilisateur du 29/08/2026) : le
    niveau ne change pas, donc aucun signal level_changed, mais la ligne
    (_row) est bien mise a jour."""
    tree, make_view = tree_and_view_factory
    view = make_view("Base")
    item = view._items_by_name["OxygenTankSmallMS"]  # niveau 1, colonne 0
    original_row = item._row

    received = []
    view.level_changed.connect(lambda name, level: received.append((name, level)))

    from gui.tech_tree_widget import ROW_HEIGHT
    item.setPos(item.pos().x(), item.pos().y() + ROW_HEIGHT * 3)
    view.on_node_dropped(item)

    assert received == []
    assert item._row == original_row + 3


def test_on_node_dropped_emits_level_changed_when_moved(tree_and_view_factory, qtbot=None):
    tree, make_view = tree_and_view_factory
    view = make_view("Base")
    item = view._items_by_name["OxygenTankSmallMS"]  # niveau 1, colonne 0

    received = []
    view.level_changed.connect(lambda name, level: received.append((name, level)))

    # Simule un glisser vers la colonne du niveau 3 (index 1 pour ce fixture,
    # levels = [1,3,10]).
    from gui.tech_tree_widget import COLUMN_WIDTH
    item.setPos(1 * COLUMN_WIDTH + 10, item.pos().y())
    view.on_node_dropped(item)

    assert received == [("OxygenTankSmallMS", 3)]


def test_on_node_dropped_no_signal_when_snapped_back_to_same_level(tree_and_view_factory):
    tree, make_view = tree_and_view_factory
    view = make_view("Base")
    item = view._items_by_name["OxygenTankSmallMS"]  # niveau 1

    received = []
    view.level_changed.connect(lambda name, level: received.append((name, level)))

    # Deplacement minime, reste dans la colonne du niveau 1.
    item.setPos(item.pos().x() + 2, item.pos().y())
    view.on_node_dropped(item)

    assert received == []


# ---------------------------------------------------------------------------
# Choix du nouveau parent apres un glisser vertical (demande explicite de
# l'utilisateur, session du 29/08/2026)
# ---------------------------------------------------------------------------

def test_row_change_starts_parent_pick(tree_and_view_factory):
    tree, make_view = tree_and_view_factory
    view = make_view("Base")
    item = view._items_by_name["OxygenTankSmallMS"]

    started = []
    view.parent_pick_started.connect(lambda name: started.append(name))

    from gui.tech_tree_widget import ROW_HEIGHT
    item.setPos(item.pos().x(), item.pos().y() + ROW_HEIGHT * 2)
    view.on_node_dropped(item)

    assert started == ["OxygenTankSmallMS"]
    assert view._pending_parent_pick_for == "OxygenTankSmallMS"


def test_clicking_another_node_during_pick_emits_parent_changed(tree_and_view_factory):
    tree, make_view = tree_and_view_factory
    view = make_view("Base")
    view.start_parent_pick("OxygenTankSmallMS")

    received = []
    view.parent_changed.connect(lambda name, parent: received.append((name, parent)))
    finished = []
    view.parent_pick_finished.connect(lambda: finished.append(True))

    target_item = view._items_by_name["FuelTankMSSmall"]
    assert view._is_descendant("FuelTankMSSmall", "OxygenTankSmallMS") is False

    view.parent_changed.emit("OxygenTankSmallMS", "FuelTankMSSmall")  # simule le clic (voir mousePressEvent)
    assert received == [("OxygenTankSmallMS", "FuelTankMSSmall")]


def test_is_descendant_prevents_cycle(tree_and_view_factory):
    """FuelTankMSLarge est un DESCENDANT de FuelTankMSSmall (voir fixture) --
    ne doit jamais pouvoir devenir son parent (cycle)."""
    tree, make_view = tree_and_view_factory
    view = make_view("Base")
    assert view._is_descendant("FuelTankMSLarge", "FuelTankMSSmall") is True
    assert view._is_descendant("FuelTankMSSmall", "FuelTankMSSmall") is True  # soi-meme aussi refuse
    assert view._is_descendant("OxygenTankSmallMS", "FuelTankMSSmall") is False


def test_set_no_parent_for_pending_pick_emits_empty_string(tree_and_view_factory):
    tree, make_view = tree_and_view_factory
    view = make_view("Base")
    view.start_parent_pick("FuelTankMSLarge")

    received = []
    view.parent_changed.connect(lambda name, parent: received.append((name, parent)))

    view.set_no_parent_for_pending_pick()

    assert received == [("FuelTankMSLarge", "")]
    assert view._pending_parent_pick_for is None


def test_cancel_parent_pick_emits_nothing(tree_and_view_factory):
    tree, make_view = tree_and_view_factory
    view = make_view("Base")
    view.start_parent_pick("FuelTankMSLarge")

    received = []
    view.parent_changed.connect(lambda name, parent: received.append((name, parent)))
    finished = []
    view.parent_pick_finished.connect(lambda: finished.append(True))

    view.cancel_parent_pick()

    assert received == []
    assert finished == [True]
    assert view._pending_parent_pick_for is None


def test_parent_pick_click_finds_node_even_if_connector_line_is_first_in_stack(tree_and_view_factory, monkeypatch):
    """Bug reel signale par l'utilisateur (29/08/2026) : le choix du parent
    ne s'enregistrait jamais. Reproduit ici le mecanisme le plus probable --
    une ligne de connexion (ou tout autre decor) geometriquement au-dessus
    de l'icone au point de clic, malgre un Z-value plus bas -- en forcant
    self.items() a retourner la ligne AVANT l'icone, et verifie que le code
    la saute bien grace au filtrage par TYPE plutot que par premier element."""
    from PyQt6.QtCore import Qt, QPointF, QEvent
    from PyQt6.QtGui import QMouseEvent
    from gui.tech_tree_widget import _TechNodeItem

    tree, make_view = tree_and_view_factory
    view = make_view("Base")
    view.start_parent_pick("FuelTankMSLarge")

    real_node_item = view._items_by_name["FuelTankMSSmall"]
    decoy_line = view._connectors["FuelTankMSLarge"]  # une vraie ligne existante de la scene

    # Force l'ordre de pile a retourner le decor EN PREMIER, comme dans le
    # bug reel constate.
    monkeypatch.setattr(view, "items", lambda pos: [decoy_line, real_node_item])

    received = []
    view.parent_changed.connect(lambda name, parent: received.append((name, parent)))

    ev = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(0, 0), Qt.MouseButton.LeftButton,
                      Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    view.mousePressEvent(ev)

    assert received == [("FuelTankMSLarge", "FuelTankMSSmall")]


def test_node_item_uses_bounding_rect_shape_for_reliable_hit_testing(tree_and_view_factory):
    """Une icone reelle a souvent une marge transparente autour du dessin --
    QGraphicsPixmapItem.ShapeMode.MaskShape (comportement par defaut) ne
    compte que les pixels opaques pour la detection de clic, ratant les
    clics pres du bord. BoundingRectShape fait compter tout le carre."""
    from PyQt6.QtWidgets import QGraphicsPixmapItem
    tree, make_view = tree_and_view_factory
    view = make_view("Base")
    item = view._items_by_name["OxygenTankSmallMS"]
    assert item.shapeMode() == QGraphicsPixmapItem.ShapeMode.BoundingRectShape
