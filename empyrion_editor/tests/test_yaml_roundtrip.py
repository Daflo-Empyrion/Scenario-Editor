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
