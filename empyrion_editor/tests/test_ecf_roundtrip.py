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

# Tests de round-trip et de structure pour le parser ECF.
from pathlib import Path

from core.ecf.parser import parse_ecf_file
from core.ecf.model import EcfBlock

FIXTURES = Path(__file__).parent / 'fixtures'


def test_ecf_roundtrip_byte_perfect():
    path = FIXTURES / 'sample.ecf'
    original = path.read_bytes()
    doc = parse_ecf_file(path)
    rendered = doc.render()
    assert rendered.encode('utf-8') == original


def test_ecf_block_count():
    doc = parse_ecf_file(FIXTURES / 'sample.ecf')
    blocks = [n for n in doc.nodes if isinstance(n, EcfBlock)]
    assert len(blocks) == 3


def test_ecf_container_identity():
    doc = parse_ecf_file(FIXTURES / 'sample.ecf')
    container = doc.find_block_by_identity('+Container', '5')
    assert container is not None
    assert container.get_property('Name') == 'TestContainer'
    assert container.get_property('Count') == '"3,4"'


def test_ecf_child_items():
    doc = parse_ecf_file(FIXTURES / 'sample.ecf')
    container = doc.find_block_by_identity('+Container', '5')
    children = container.child_blocks('Child Items')
    assert len(children) == 1


def test_ecf_block_without_id():
    doc = parse_ecf_file(FIXTURES / 'sample.ecf')
    block = doc.find_block_by_identity('Block', 'LegacyForcefield')
    assert block is not None
    assert block.get('Id') is None
