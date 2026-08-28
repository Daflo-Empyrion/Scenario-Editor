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


def test_yaml_roundtrip_real_file_with_zero_indent_comments():
    """Regression pour le piege des commentaires a indentation zero au milieu
    d'une liste imbriquee (voir core/yamllite/parser.py) -- playfield_static_real.yaml
    est un vrai fichier de jeu (playfield_static.yaml) contenant ce motif reel sous
    'POIs > Random' (commentaires a colonne 0 entre des entrees '- GroupName:'
    indentees a 8 espaces). Round-trip byte-perfect ET vraie descente d'arbre
    (sans passer par les fonctions par plage d'indices de core/playfield_editor.py)
    doivent tous deux retrouver les 41 POI reels."""
    path = FIXTURES / 'playfield_static_real.yaml'
    original = path.read_bytes()
    doc = parse_yaml_file(path)
    assert doc.render().encode('utf-8') == original

    from core.yamllite.model import YamlEntry
    from core.playfield_editor import find_top_level_key

    def descend_count(nodes, key):
        n = 0
        for node in nodes:
            if isinstance(node, YamlEntry):
                if node.key == key and node.is_sequence_item:
                    n += 1
                n += descend_count(node.children, key)
        return n

    section = find_top_level_key(doc, 'POIs')
    assert section is not None
    assert descend_count(section.children, 'GroupName') == 41
