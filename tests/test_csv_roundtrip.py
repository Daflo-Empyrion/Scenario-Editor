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

# Tests de round-trip et de structure pour le handler CSV.
from pathlib import Path

from core.csv_handler import CsvHandler

FIXTURES = Path(__file__).parent / 'fixtures'


def test_csv_roundtrip_byte_perfect():
    path = FIXTURES / 'localization.csv'
    handler = CsvHandler()
    original = path.read_bytes()
    doc = handler.parse(handler.load(path))
    rendered = handler.serialize(doc)
    assert rendered.encode('utf-8') == original


def test_csv_header_and_rows():
    handler = CsvHandler()
    doc = handler.parse(handler.load(FIXTURES / 'localization.csv'))
    assert doc.header is not None
    assert doc.header[0] == 'Key'
    assert len(doc.rows) == 3


def test_csv_delimiter_detected():
    handler = CsvHandler()
    doc = handler.parse(handler.load(FIXTURES / 'localization.csv'))
    assert doc.delimiter == ','
