# Tests du module core.translation_memory.
from core import translation_memory as tm


def test_cache_miss_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(tm, 'CONFIG_DIR', tmp_path)
    monkeypatch.setattr(tm, 'MEMORY_FILE', tmp_path / 'translation_memory.json')
    assert tm.get_cached('Hello', 'auto', 'fr') is None


def test_store_and_get_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(tm, 'CONFIG_DIR', tmp_path)
    monkeypatch.setattr(tm, 'MEMORY_FILE', tmp_path / 'translation_memory.json')
    tm.store('Hello', 'auto', 'fr', 'Bonjour')
    assert tm.get_cached('Hello', 'auto', 'fr') == 'Bonjour'


def test_extra_whitespace_normalized(tmp_path, monkeypatch):
    monkeypatch.setattr(tm, 'CONFIG_DIR', tmp_path)
    monkeypatch.setattr(tm, 'MEMORY_FILE', tmp_path / 'translation_memory.json')
    tm.store('Hello', 'auto', 'fr', 'Bonjour')
    assert tm.get_cached('  Hello  ', 'auto', 'fr') == 'Bonjour'


def test_different_language_pair_is_separate(tmp_path, monkeypatch):
    monkeypatch.setattr(tm, 'CONFIG_DIR', tmp_path)
    monkeypatch.setattr(tm, 'MEMORY_FILE', tmp_path / 'translation_memory.json')
    tm.store('Hello', 'auto', 'fr', 'Bonjour')
    assert tm.get_cached('Hello', 'auto', 'de') is None


def test_entry_count(tmp_path, monkeypatch):
    monkeypatch.setattr(tm, 'CONFIG_DIR', tmp_path)
    monkeypatch.setattr(tm, 'MEMORY_FILE', tmp_path / 'translation_memory.json')
    assert tm.entry_count() == 0
    tm.store('Hello', 'auto', 'fr', 'Bonjour')
    tm.store('World', 'auto', 'fr', 'Monde')
    assert tm.entry_count() == 2


def test_clear(tmp_path, monkeypatch):
    monkeypatch.setattr(tm, 'CONFIG_DIR', tmp_path)
    monkeypatch.setattr(tm, 'MEMORY_FILE', tmp_path / 'translation_memory.json')
    tm.store('Hello', 'auto', 'fr', 'Bonjour')
    tm.clear()
    assert tm.entry_count() == 0
