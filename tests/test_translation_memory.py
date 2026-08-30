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


# ---------------------------------------------------------------------------
# Nouveaux comportements : cache en RAM, ecriture diffee/debordee, thread-safety
# ---------------------------------------------------------------------------

def _reset_flush_state():
    """Remet a zero l'etat interne de debordement entre deux tests (les variables
    module sont volontairement touchees ici : c'est l'objet meme du test)."""
    tm._dirty_entries = 0
    tm._last_save_monotonic = 0.0


def test_first_store_persists_immediately(tmp_path, monkeypatch):
    monkeypatch.setattr(tm, 'MEMORY_FILE', tmp_path / 'translation_memory.json')
    _reset_flush_state()
    tm.store('Hello', 'auto', 'fr', 'Bonjour')
    assert (tmp_path / 'translation_memory.json').exists()


def test_store_within_interval_defers_disk_write(tmp_path, monkeypatch):
    """Apres une premiere ecriture, une entree isolee dans l'intervalle de
    debordement reste en RAM (pas de reecriture disque a chaque store -- le
    defaut O(n^2) corrige ici) ; flush() la persiste."""
    import time
    monkeypatch.setattr(tm, 'MEMORY_FILE', tmp_path / 'translation_memory.json')
    _reset_flush_state()
    tm.store('Hello', 'auto', 'fr', 'Bonjour')  # premiere ecriture -> disque
    memory_file = tmp_path / 'translation_memory.json'
    before = memory_file.stat().st_mtime_ns
    tm._last_save_monotonic = time.monotonic()  # simule une ecriture tout juste faite

    tm.store('World', 'auto', 'fr', 'Monde')
    assert memory_file.stat().st_mtime_ns == before  # rien ecrit
    assert tm.get_cached('World', 'auto', 'fr') == 'Monde'  # mais visible en RAM

    tm.flush()
    assert memory_file.stat().st_mtime_ns != before  # persiste au flush
    # Et une NOUVELLE instance de cache (changement de chemin force la relecture)
    # retrouve bien l'entree depuis le disque :
    monkeypatch.setattr(tm, 'MEMORY_FILE', tmp_path / 'other.json')
    assert tm.get_cached('World', 'auto', 'fr') is None  # autre fichier -> autre memoire
    monkeypatch.setattr(tm, 'MEMORY_FILE', memory_file)
    assert tm.get_cached('World', 'auto', 'fr') == 'Monde'


def test_cache_invalidated_when_memory_file_path_changes(tmp_path, monkeypatch):
    """Le cache s'invalide si le chemin change (isolations de tests, config
    future) -- sinon un test contaminerait le suivant."""
    first = tmp_path / 'a.json'
    monkeypatch.setattr(tm, 'MEMORY_FILE', first)
    _reset_flush_state()  # sinon _last_save_monotonic du test precedent difere l'ecriture
    tm.store('Hello', 'auto', 'fr', 'Bonjour')
    monkeypatch.setattr(tm, 'MEMORY_FILE', tmp_path / 'b.json')
    assert tm.get_cached('Hello', 'auto', 'fr') is None
    monkeypatch.setattr(tm, 'MEMORY_FILE', first)
    assert tm.get_cached('Hello', 'auto', 'fr') == 'Bonjour'


def test_corrupt_file_falls_back_to_empty_and_recovers(tmp_path, monkeypatch):
    memory_file = tmp_path / 'translation_memory.json'
    memory_file.write_text('{json corrompu', encoding='utf-8')
    monkeypatch.setattr(tm, 'MEMORY_FILE', memory_file)
    _reset_flush_state()
    assert tm.get_cached('Hello', 'auto', 'fr') is None
    tm.store('Hello', 'auto', 'fr', 'Bonjour')  # reconstruit le fichier (atomique)
    assert tm.get_cached('Hello', 'auto', 'fr') == 'Bonjour'


def test_concurrent_stores_all_persisted(tmp_path, monkeypatch):
    """Les appels peuvent venir de threads differents (worker de traduction +
    interface) : aucune entree ne doit etre perdue ni corrompue."""
    monkeypatch.setattr(tm, 'MEMORY_FILE', tmp_path / 'translation_memory.json')
    _reset_flush_state()
    import threading
    def _worker(worker_id):
        for i in range(25):
            tm.store(f'texte {worker_id}-{i}', 'auto', 'fr', f'traduit {worker_id}-{i}')
    threads = [threading.Thread(target=_worker, args=(w,)) for w in range(8)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    tm.flush()
    assert tm.entry_count() == 200
