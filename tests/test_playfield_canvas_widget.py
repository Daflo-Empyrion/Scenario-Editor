"""
Tests du widget GUI du canvas 2D (gui/playfield_canvas_widget.py).
"""
from pathlib import Path

import pytest

from core.yamllite.parser import parse_yaml_file

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "playfield_scenario"


@pytest.fixture
def akua_doc():
    return parse_yaml_file(FIXTURE_DIR / "playfield_akua.yaml")


def test_widget_extracts_entities_on_creation(qapp, akua_doc):
    from gui.theme import apply_theme
    from gui.playfield_canvas_widget import PlayfieldCanvasWidget
    apply_theme(qapp)
    widget = PlayfieldCanvasWidget(akua_doc)
    assert len(widget.entities) == 61


def test_widget_builds_filter_checkboxes_per_kind(qapp, akua_doc):
    from gui.theme import apply_theme
    from gui.playfield_canvas_widget import PlayfieldCanvasWidget
    apply_theme(qapp)
    widget = PlayfieldCanvasWidget(akua_doc)
    kinds_present = {e.kind for e in widget.entities}
    assert set(widget.filter_checkboxes.keys()) == kinds_present


def test_widget_only_draws_entities_with_position(qapp, akua_doc):
    from gui.theme import apply_theme
    from gui.playfield_canvas_widget import PlayfieldCanvasWidget
    apply_theme(qapp)
    widget = PlayfieldCanvasWidget(akua_doc)
    positioned_count = sum(1 for e in widget.entities if e.position is not None)
    assert len(widget._dots) == positioned_count == 6


def test_selecting_entity_updates_info_label(qapp, akua_doc):
    from gui.theme import apply_theme
    from gui.playfield_canvas_widget import PlayfieldCanvasWidget
    apply_theme(qapp)
    widget = PlayfieldCanvasWidget(akua_doc)
    fixed_dot = next(d for d in widget._dots if d.entity.kind == "poi_fixed")
    widget._on_entity_selected(fixed_dot.entity)
    assert fixed_dot.entity.name in widget.info_label.text()


def test_moving_fixed_poi_updates_yaml_and_emits_signal(qapp, akua_doc):
    from gui.theme import apply_theme
    from gui.playfield_canvas_widget import PlayfieldCanvasWidget
    apply_theme(qapp)
    widget = PlayfieldCanvasWidget(akua_doc)
    fixed_dot = next(d for d in widget._dots if d.entity.kind == "poi_fixed")

    received = []
    widget.modified.connect(lambda: received.append(True))
    widget._on_entity_moved(fixed_dot.entity, 777.0, 888.0)

    assert received == [True]
    assert "Pos: [ 777, 33, 888 ]" in akua_doc.render()


def test_random_poi_dot_not_movable(qapp, akua_doc):
    """Les POI aleatoires resolus n'ont pas de propriete de position
    modifiable directement -- ne doivent jamais etre deplacables."""
    from gui.theme import apply_theme
    from gui.playfield_canvas_widget import PlayfieldCanvasWidget, _EntityDot
    from PyQt6.QtWidgets import QGraphicsEllipseItem
    apply_theme(qapp)
    widget = PlayfieldCanvasWidget(akua_doc)
    random_dots = [d for d in widget._dots if d.entity.kind == "poi_random"]
    for dot in random_dots:
        assert not (dot.flags() & QGraphicsEllipseItem.GraphicsItemFlag.ItemIsMovable)


def test_refresh_reflects_external_document_changes(qapp, akua_doc):
    """Si le document est modifie ailleurs (ex: onglet YAML complet), refresh()
    doit re-extraire et refleter le changement."""
    from gui.theme import apply_theme
    from gui.playfield_canvas_widget import PlayfieldCanvasWidget
    from core.playfield_canvas import extract_canvas_entities, update_entity_position
    apply_theme(qapp)
    widget = PlayfieldCanvasWidget(akua_doc)

    entities = extract_canvas_entities(akua_doc)
    fixed = next(e for e in entities if e.kind == "poi_fixed")
    update_entity_position(fixed, 123.0, 456.0)

    widget.refresh()
    updated_dot = next(d for d in widget._dots if d.entity.kind == "poi_fixed" and d.entity.name == fixed.name)
    assert updated_dot.entity.position == (123.0, 33.0, 456.0)


def test_unchecking_filter_hides_kind(qapp, akua_doc):
    from gui.theme import apply_theme
    from gui.playfield_canvas_widget import PlayfieldCanvasWidget
    apply_theme(qapp)
    widget = PlayfieldCanvasWidget(akua_doc)
    widget.filter_checkboxes["poi_fixed"].setChecked(False)
    widget._redraw()
    assert not any(d.entity.kind == "poi_fixed" for d in widget._dots)
