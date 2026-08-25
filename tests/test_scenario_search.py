"""
Tests du module de recherche a travers tout le scenario
(core/scenario_search.py) -- bases sur des fixtures compactes representatives
des 3 formats geres (ECF, YAML, CSV).
"""
from pathlib import Path

from core.scenario_search import (
    search_ecf_files, search_yaml_files, search_csv_files, search_scenario,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "search_scenario"


def test_search_ecf_finds_match_in_header_pair():
    """Confirme que la recherche trouve un terme dans une paire d'en-tete de
    bloc (Name), pas seulement dans les proprietes enfants."""
    results = search_ecf_files([FIXTURE_DIR / "ItemsConfig.ecf"], "IronOre")
    assert len(results) == 1
    assert results[0].identity == "201"
    assert results[0].prop_key == "Name"


def test_search_ecf_finds_match_in_nested_property():
    results = search_ecf_files([FIXTURE_DIR / "ItemsConfig.ecf"], "Ores/Copper")
    assert len(results) == 1
    assert results[0].identity == "202"
    assert results[0].prop_key == "Meshfile"


def test_search_ecf_case_insensitive_by_default():
    results = search_ecf_files([FIXTURE_DIR / "ItemsConfig.ecf"], "ironore")
    assert len(results) == 1


def test_search_ecf_case_sensitive_when_requested():
    results = search_ecf_files([FIXTURE_DIR / "ItemsConfig.ecf"], "ironore", case_sensitive=True)
    assert len(results) == 0


def test_search_ecf_one_result_per_block_max():
    """Un bloc dont le terme apparait plusieurs fois (ex: dans Id ET Name) ne
    doit produire qu'un seul resultat, pas un par occurrence."""
    results = search_ecf_files([FIXTURE_DIR / "ItemsConfig.ecf"], "Item")
    identities = [r.identity for r in results]
    assert len(identities) == len(set(identities))


def test_search_yaml_finds_entry_and_exposes_exact_value_for_navigation():
    results = search_yaml_files([FIXTURE_DIR / "test.yaml"], "Akua")
    assert len(results) == 1
    assert results[0].entry_key == "Description"
    assert "Akua" in results[0].entry_value


def test_search_yaml_context_is_truncated_and_flat():
    """Une description longue sur plusieurs lignes doit etre aplatie et
    tronquee pour l'affichage -- confirme le comportement sur une vraie
    description de playfield (voir test_search_context_truncation_on_real_data)."""
    results = search_yaml_files([FIXTURE_DIR / "test.yaml"], "Akua")
    assert "\n" not in results[0].match_context
    assert len(results[0].match_context) <= 110


def test_search_csv_finds_match_across_row():
    results = search_csv_files([FIXTURE_DIR / "Dialogues.csv"], "Akua")
    assert len(results) == 1
    assert "Greeting_Akua" in results[0].match_context


def test_search_csv_no_precise_navigation_fields():
    """Documente la limitation connue : aucune navigation precise vers la
    ligne CSV, contrairement a ECF/YAML."""
    results = search_csv_files([FIXTURE_DIR / "Dialogues.csv"], "Akua")
    assert results[0].entry_key is None
    assert results[0].identity is None


def test_search_scenario_combines_all_three_formats():
    results = search_scenario(
        [FIXTURE_DIR / "ItemsConfig.ecf"], [FIXTURE_DIR / "test.yaml"], [FIXTURE_DIR / "Dialogues.csv"],
        "Akua")
    kinds = {r.file_kind for r in results}
    assert kinds == {"yaml", "csv"}  # "Akua" n'apparait pas dans ItemsConfig.ecf


def test_search_scenario_empty_query_returns_nothing():
    results = search_scenario(
        [FIXTURE_DIR / "ItemsConfig.ecf"], [FIXTURE_DIR / "test.yaml"], [FIXTURE_DIR / "Dialogues.csv"],
        "   ")
    assert results == []


def test_search_handles_unparseable_file_gracefully(tmp_path):
    bad_ecf = tmp_path / "Broken.ecf"
    bad_ecf.write_text("{{{ not valid", encoding="utf-8")
    assert search_ecf_files([bad_ecf], "anything") == []

    bad_yaml = tmp_path / "Broken.yaml"
    bad_yaml.write_bytes(b"\x00\x01\x02invalid")
    # Ne doit pas lever d'exception, resultat vide ou ignore selon le parseur
    search_yaml_files([bad_yaml], "anything")
