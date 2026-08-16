# Tests du module core.property_extractor.
from pathlib import Path

from core.property_extractor import extract_properties, build_property_rows, PROPERTY_EXPORT_HEADER


def _write_ecf(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.replace('\n', '\r\n').encode('utf-8'))


def test_extract_finds_all_properties(tmp_path):
    _write_ecf(tmp_path / 'A.ecf', '{ Block Id: 1, Name: A\n  Mass: 5\n}\n')
    usages = extract_properties(tmp_path)
    names = {u.name for u in usages}
    assert names == {'Id', 'Name', 'Mass'}


def test_extract_counts_occurrences_across_files(tmp_path):
    _write_ecf(tmp_path / 'A.ecf', '{ Block Id: 1, Name: A\n  Mass: 5\n}\n')
    _write_ecf(tmp_path / 'B.ecf', '{ Block Id: 2, Name: B\n  Mass: 10\n}\n')
    usages = extract_properties(tmp_path)
    mass = next(u for u in usages if u.name == 'Mass')
    assert mass.count == 2
    assert mass.files == {'A.ecf', 'B.ecf'}
    assert set(mass.example_values) == {'5', '10'}


def test_numbered_keys_grouped(tmp_path):
    _write_ecf(tmp_path / 'A.ecf',
                '{ Block Id: 1\n  { Child Items\n    Name_0: X, param1: 1\n    Name_1: Y, param1: 2\n  }\n}\n')
    usages = extract_properties(tmp_path)
    names = {u.name for u in usages}
    assert 'Name_N' in names
    assert 'Name_0' not in names
    assert 'Name_1' not in names
    name_n = next(u for u in usages if u.name == 'Name_N')
    assert name_n.count == 2


def test_nested_subblocks_are_walked(tmp_path):
    _write_ecf(tmp_path / 'A.ecf',
                '{ Block Id: 1\n  { Sub\n    { SubSub\n      Deep: value\n    }\n  }\n}\n')
    usages = extract_properties(tmp_path)
    names = {u.name for u in usages}
    assert 'Deep' in names


def test_sorted_by_frequency_descending(tmp_path):
    _write_ecf(tmp_path / 'A.ecf',
                '{ Block Id: 1\n  Rare: 1\n}\n{ Block Id: 2\n  Rare: 1\n  Common: 1\n}\n'
                '{ Block Id: 3\n  Common: 1\n}\n')
    usages = extract_properties(tmp_path)
    counts = [u.count for u in usages]
    assert counts == sorted(counts, reverse=True)


def test_build_property_rows_shape(tmp_path):
    _write_ecf(tmp_path / 'A.ecf', '{ Block Id: 1, Name: A\n  Mass: 5\n}\n')
    usages = extract_properties(tmp_path)
    rows = build_property_rows(usages)
    assert len(PROPERTY_EXPORT_HEADER) == 6
    for row in rows:
        assert len(row) == 6


def test_ambiguous_terms_not_auto_filled(tmp_path):
    _write_ecf(tmp_path / 'A.ecf', '{ Block Id: 1, Name: A\n}\n')
    usages = extract_properties(tmp_path)
    rows = build_property_rows(usages)
    by_name = {r[0]: r[4] for r in rows}
    assert by_name.get('Name', '') == ''
    assert by_name.get('Id', '') == ''


def test_unambiguous_term_gets_description(tmp_path):
    _write_ecf(tmp_path / 'A.ecf', '{ Block Id: 1\n  AllowPlacingAt: MS\n}\n')
    usages = extract_properties(tmp_path)
    rows = build_property_rows(usages)
    by_name = {r[0]: r[4] for r in rows}
    assert by_name.get('AllowPlacingAt', '') != ''


def test_corrupted_file_does_not_crash(tmp_path):
    (tmp_path / 'Bad.ecf').write_bytes(b'{ this is not valid ECF at all {{{ ]')
    _write_ecf(tmp_path / 'Good.ecf', '{ Block Id: 1, Name: A\n}\n')
    usages = extract_properties(tmp_path)
    names = {u.name for u in usages}
    assert 'Name' in names
