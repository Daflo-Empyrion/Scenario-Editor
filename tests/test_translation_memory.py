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
