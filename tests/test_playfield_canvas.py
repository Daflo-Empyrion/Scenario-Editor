"""
Tests du module d'extraction pour le canvas 2D (core/playfield_canvas.py) --
bases sur les vraies fixtures playfield_static.yaml/playfield_akua.yaml deja
utilisees par test_playfield_editor.py. Trois hypotheses structurelles ont
ete infirmees lors de l'analyse d'un patch propose puis corrigees ici : la
section 'Fixed' des POI, la position via RadialInfo pour les ressources
spatiales, et l'imbrication de FixedPlayerStart -- voir les commentaires de
tete de core/playfield_canvas.py pour le detail de chaque verification.
"""
from pathlib import Path

import pytest

from core.yamllite.parser import parse_yaml_file, parse_yaml_text
from core.playfield_canvas import (
    extract_canvas_entities, update_entity_position, compute_bounding_box, CanvasEntity,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "playfield_scenario"


@pytest.fixture
def static_doc():
    return parse_yaml_file(FIXTURE_DIR / "playfield_static.yaml")


@pytest.fixture
def akua_doc():
    return parse_yaml_file(FIXTURE_DIR / "playfield_akua.yaml")


def test_extract_entities_on_static_playfield(static_doc):
    entities = extract_canvas_entities(static_doc)
    kinds = {e.kind for e in entities}
    assert "poi_random" in kinds
    assert "player_start" in kinds
    assert "poi_fixed" not in kinds  # ce fichier n'a pas de section Fixed


def test_extract_entities_on_akua_playfield(akua_doc):
    entities = extract_canvas_entities(akua_doc)
    fixed = [e for e in entities if e.kind == "poi_fixed"]
    assert len(fixed) == 2
    names = {e.name for e in fixed}
    assert names == {"Reforged Creative Library", "Platform"}


def test_fixed_poi_has_real_absolute_position(akua_doc):
    entities = extract_canvas_entities(akua_doc)
    fixed = next(e for e in entities if e.name == "Reforged Creative Library")
    assert fixed.position == (-1460.0, 33.0, 1555.0)
    assert fixed.pos_property_key == "Pos"


def test_space_resources_never_get_a_fake_position_from_radial_info():
    """Regression cle : RadialInfo n'est PAS une position X,Y,Z (confirme sur
    un vrai space_dynamic.yaml, toujours [0,0,0,...]) -- ne doit jamais
    produire une position fabriquee, meme approximative."""
    space_path = Path(__file__).parent / "fixtures" / "space_scenario" / "space_dynamic.yaml"
    doc = parse_yaml_file(space_path)
    entities = extract_canvas_entities(doc)
    resources = [e for e in entities if e.kind == "resource"]
    assert len(resources) > 0
    assert all(r.position is None for r in resources)


def test_player_start_entities_have_position_when_available(static_doc):
    entities = extract_canvas_entities(static_doc)
    starts = [e for e in entities if e.kind == "player_start"]
    assert len(starts) == 4
    with_pos = [s for s in starts if s.position is not None]
    assert len(with_pos) >= 1  # au moins le "Debug" a un Pos reel


def test_random_poi_without_resolvable_spawn_near_has_no_position(akua_doc):
    """Cas attendu, pas un bug : la plupart des POI Random ne referencent pas
    un POI Fixed via SpawnPOINear (ils referencent generalement un autre
    Random) -- doivent rester position=None plutot que d'inventer une
    approximation."""
    entities = extract_canvas_entities(akua_doc)
    random_pois = [e for e in entities if e.kind == "poi_random"]
    assert len(random_pois) == 32
    unresolved = [r for r in random_pois if r.position is None]
    assert len(unresolved) > 0  # confirme : la majorite reste non resolue


def test_update_entity_position_writes_to_source_yaml(akua_doc):
    entities = extract_canvas_entities(akua_doc)
    fixed = next(e for e in entities if e.kind == "poi_fixed")
    ok = update_entity_position(fixed, 42.0, 84.0)
    assert ok is True
    assert fixed.position == (42.0, 33.0, 84.0)
    assert "Pos: [ 42, 33, 84 ]" in akua_doc.render()


def test_update_entity_position_preserves_y_height(akua_doc):
    entities = extract_canvas_entities(akua_doc)
    fixed = next(e for e in entities if e.kind == "poi_fixed")
    original_y = fixed.position[1]
    update_entity_position(fixed, 0.0, 0.0)
    assert fixed.position[1] == original_y


def test_update_entity_position_fails_gracefully_without_pos_key():
    """Une entite sans pos_property_key (ex: POI Random non resolu) ne doit
    jamais planter -- juste refuser proprement le deplacement."""
    entity = CanvasEntity(kind="poi_random", name="Test", position=None)
    assert update_entity_position(entity, 1.0, 2.0) is False


def test_reparsed_document_stays_valid_after_move(akua_doc):
    entities = extract_canvas_entities(akua_doc)
    fixed = next(e for e in entities if e.kind == "poi_fixed")
    update_entity_position(fixed, 111.0, 222.0)
    rendered = akua_doc.render()
    reparsed = parse_yaml_text(rendered)
    assert reparsed is not None


def test_document_unchanged_without_modification_round_trips_perfectly(akua_doc):
    original = (FIXTURE_DIR / "playfield_akua.yaml").read_bytes()
    extract_canvas_entities(akua_doc)  # extraction seule, aucune modification
    assert akua_doc.render().encode("utf-8") == original


def test_compute_bounding_box_with_real_positions(akua_doc):
    entities = extract_canvas_entities(akua_doc)
    min_x, max_x, min_z, max_z = compute_bounding_box(entities)
    assert min_x < max_x
    assert min_z < max_z


def test_compute_bounding_box_fallback_when_nothing_positioned():
    entities = [CanvasEntity(kind="resource", name="Test", position=None)]
    bbox = compute_bounding_box(entities)
    assert bbox == (-1000.0, 1000.0, -1000.0, 1000.0)


def test_drone_spawning_extracted_without_fabricating_incomplete_position(akua_doc):
    """Confirme sur un vrai playfield_akua.yaml : DroneSpawning n'a QUE
    CenterX (jamais CenterZ) -- position doit rester None plutot que de
    fabriquer une coordonnee avec un seul axe connu, coherent avec le
    principe general du module (ne jamais inventer une position)."""
    entities = extract_canvas_entities(akua_doc)
    drones = [e for e in entities if e.kind == "drone_spawning"]
    assert len(drones) == 2
    assert all(d.position is None for d in drones)
    assert all(d.extra.get("CenterX") for d in drones)
