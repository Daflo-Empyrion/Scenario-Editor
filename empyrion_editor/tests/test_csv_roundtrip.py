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
