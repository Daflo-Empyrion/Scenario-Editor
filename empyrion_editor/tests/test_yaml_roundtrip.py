# Tests de round-trip et de structure pour le parser yamllite.
from pathlib import Path

from core.yamllite.parser import parse_yaml_file

FIXTURES = Path(__file__).parent / 'fixtures'


def test_yaml_roundtrip_byte_perfect():
    path = FIXTURES / 'playfield.yaml'
    original = path.read_bytes()
    doc = parse_yaml_file(path)
    rendered = doc.render()
    assert rendered.encode('utf-8') == original


def test_yaml_get_path():
    doc = parse_yaml_file(FIXTURES / 'playfield.yaml')
    assert doc.get_path('PlayfieldType') == 'Planet'
    assert doc.get_path('PlayfieldName') == 'TestPlanet'
    assert doc.get_path('Atmosphere', 'Enabled') == 'True'
    assert doc.get_path('Atmosphere', 'Color') is not None
