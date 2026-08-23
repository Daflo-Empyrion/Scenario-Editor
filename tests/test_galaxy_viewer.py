"""
Tests du module d'extraction de la galaxie (core/galaxy_viewer.py) -- bases
sur une fixture reduite mais fidele d'un vrai Sectors.yaml (4 systemes
reels, structure imbriquee SolarSystems > Sectors > Playfields preservee).

Chaque hypothese structurelle de ce module a ete verifiee contre le vrai
fichier complet (82 systemes, 817 playfields) avant d'etre codee -- voir le
commentaire de tete de core/galaxy_viewer.py pour le detail complet des
ecarts trouves par rapport a une premiere proposition non verifiee (cle
racine, noms de champs, absence totale de donnees de connexion entre
systemes).
"""
from pathlib import Path

from core.yamllite.parser import parse_yaml_file
from core.galaxy_viewer import (
    extract_solar_systems, compute_bounding_box, classify_star_class,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "galaxy_scenario" / "Sectors.yaml"


def _doc():
    return parse_yaml_file(FIXTURE_PATH)


def test_extract_solar_systems_finds_all_real_systems():
    systems = extract_solar_systems(_doc())
    names = {s.name for s in systems}
    assert names == {"Alpha", "Beta", "Rogue System", "Alphalan"}


def test_solar_system_has_real_galaxy_coordinates():
    systems = extract_solar_systems(_doc())
    alpha = next(s for s in systems if s.name == "Alpha")
    assert alpha.coordinates == (190.0, 15.0, 50.0)


def test_solar_system_uses_coordinates_field_not_position():
    """Regression cle : le champ reel est 'Coordinates', pas 'Position' comme
    suppose initialement -- confirme sur un vrai fichier."""
    systems = extract_solar_systems(_doc())
    assert all(s.coordinates is not None for s in systems)


def test_star_class_field_captured_with_real_vocabulary():
    systems = extract_solar_systems(_doc())
    alpha = next(s for s in systems if s.name == "Alpha")
    assert alpha.star_class == "GStartingSystem"
    alphalan = next(s for s in systems if s.name == "Alphalan")
    assert alphalan.star_class == "A3"


def test_classify_star_class_distinguishes_role_from_spectral():
    """Confirme sur les 27 valeurs reelles observees dans un vrai Sectors.yaml
    : melange de roles de systeme (Gate, Anomaly, XxxStartingSystem...) et de
    vraies classes spectrales (A3, K2V, M2...)."""
    assert classify_star_class("GStartingSystem") == "role"
    assert classify_star_class("ZiraxHomeSystem") == "role"
    assert classify_star_class("Gate") == "role"
    assert classify_star_class("Anomaly3") == "role"
    assert classify_star_class("A3") == "spectral"
    assert classify_star_class("K2V") == "spectral"
    assert classify_star_class("M") == "spectral"


def test_local_sectors_correctly_attributed_to_own_system_not_neighbor():
    """Regression cle : chaque systeme a ses PROPRES secteurs locaux
    correctement rattaches, sans melange avec le systeme voisin -- verifie
    que le suivi par valeur de Name (pas par nom de cle) fonctionne."""
    systems = extract_solar_systems(_doc())
    # Les 4 systemes de la fixture ont chacun 6 secteurs locaux (extrait
    # complet et coherent, verifie manuellement contre le vrai fichier)
    assert all(s.sector_count == 6 for s in systems)


def test_no_system_has_negative_or_missing_sector_count():
    systems = extract_solar_systems(_doc())
    assert all(s.sector_count >= 0 for s in systems)


def test_extract_returns_empty_list_for_non_galaxy_file():
    from core.yamllite.parser import parse_yaml_text
    doc = parse_yaml_text("PlayfieldType: Space\r\n")
    assert extract_solar_systems(doc) == []


def test_compute_bounding_box_with_real_systems():
    systems = extract_solar_systems(_doc())
    min_x, max_x, min_z, max_z = compute_bounding_box(systems)
    assert min_x < max_x
    assert min_z < max_z


def test_compute_bounding_box_fallback_when_empty():
    bbox = compute_bounding_box([])
    assert bbox == (-200.0, 200.0, -200.0, 200.0)


def test_document_round_trips_perfectly_after_extraction():
    """L'extraction seule (lecture) ne doit jamais modifier le document."""
    path = FIXTURE_PATH
    original = path.read_bytes()
    doc = parse_yaml_file(path)
    extract_solar_systems(doc)
    assert doc.render().encode("utf-8") == original
