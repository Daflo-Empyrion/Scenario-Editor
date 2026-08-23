"""
Tests du module de statistiques POI (core/poi_inspector.py) -- bases sur les
vraies fixtures playfield_static.yaml/playfield_akua.yaml. Champs
CountMinMax/DroneProb/DronesMinMax verifies sur de vraies donnees (DroneProb
confirme etre une fraction 0.0-1.0, jamais un pourcentage).
"""
from pathlib import Path

import pytest

from core.yamllite.parser import parse_yaml_file
from core.poi_inspector import compute_poi_stats, aggregate_by_faction, PoiStats

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "playfield_scenario"


@pytest.fixture
def static_doc():
    return parse_yaml_file(FIXTURE_DIR / "playfield_static.yaml")


@pytest.fixture
def akua_doc():
    return parse_yaml_file(FIXTURE_DIR / "playfield_akua.yaml")


def test_compute_poi_stats_matches_random_poi_count(static_doc):
    stats = compute_poi_stats(static_doc)
    assert len(stats) == 41  # meme total que find_random_poi_items() etabli


def test_poi_stats_have_real_names_not_none(static_doc):
    """Regression : GroupName est la cle de tete de l'item (pas un enfant),
    doit venir de item.value, pas de get_item_params() seul (qui renverrait
    None pour cette cle precise)."""
    stats = compute_poi_stats(static_doc)
    assert all(s.name and s.name != "?" for s in stats)
    names = {s.name for s in stats}
    assert "R2DroneBase" in names


def test_drone_prob_parsed_as_fraction_not_percentage(static_doc):
    stats = compute_poi_stats(static_doc)
    r2xenu = next(s for s in stats if s.name == "R2XenuDefenseT3")
    assert 0.0 <= r2xenu.drone_prob <= 1.0


def test_estimated_drones_min_max_are_non_negative(static_doc):
    stats = compute_poi_stats(static_doc)
    assert all(s.estimated_drones_min >= 0 for s in stats)
    assert all(s.estimated_drones_max >= 0 for s in stats)


def test_estimated_drones_max_never_below_min_when_probability_full():
    """Avec DroneProb=1.0, min et max ne doivent pas s'inverser de facon
    absurde -- verifie la coherence de la formule sur un cas limpide."""
    s = PoiStats(name="Test", faction="Zirax", count_min=2, count_max=2,
                 drone_prob=1.0, drones_min=3, drones_max=3)
    assert s.estimated_drones_min == 6
    assert s.estimated_drones_max == 6


def test_aggregate_by_faction_groups_correctly(static_doc):
    stats = compute_poi_stats(static_doc)
    by_faction = aggregate_by_faction(stats)
    assert "Zirax" in by_faction
    zirax = by_faction["Zirax"]
    assert zirax.poi_count == sum(1 for s in stats if s.faction == "Zirax")
    assert len(zirax.poi_names) == zirax.poi_count


def test_aggregate_totals_match_sum_of_individual_estimates(static_doc):
    stats = compute_poi_stats(static_doc)
    by_faction = aggregate_by_faction(stats)
    total_max = sum(agg.total_drones_max for agg in by_faction.values())
    expected = sum(s.estimated_drones_max for s in stats)
    assert total_max == expected


def test_fixed_poi_never_included_in_stats(akua_doc):
    """Les POI Fixed (positions absolues, placements uniques) n'ont pas les
    champs de comptage/probabilite -- ne doivent jamais apparaitre dans les
    statistiques, qui portent uniquement sur Random."""
    stats = compute_poi_stats(akua_doc)
    names = {s.name for s in stats}
    assert "Reforged Creative Library" not in names
    assert "Platform" not in names


def test_empty_playfield_produces_no_stats():
    from core.yamllite.parser import parse_yaml_text
    doc = parse_yaml_text("PlayfieldType: Space\r\n")
    assert compute_poi_stats(doc) == []
