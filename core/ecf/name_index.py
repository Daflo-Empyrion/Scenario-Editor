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

"""Index en memoire (SQLite) des noms craftables -- demande du 31/10.

SYMPTOME : list_craftable_names reparse ItemsConfig.ecf + BlocksConfig.ecf a
CHAQUE ouverture d'une combo (fiche, AddTableRowDialog...) ; sur un scenario
qui grossit, ca devient lent.

PRINCIPE :
  - un cache par (items, blocks, players_only), cle de fraicheur =
    (mtime_ns, taille) des deux fichiers : index FRAIS = reponse instantanee
    depuis une base SQLite en memoire ;
  - index PERIME : la liste precedente est servie IMMEDIATEMENT et une
    reconstruction est lancee en thread daemon (l'utilisateur demande a ne
    JAMAIS attendre : la prochaine ouverture aura la liste a jour) ;
  - PREMIER appel : construction bloquante (aucune donnee a servir) ;
  - mise a jour EN ARRIERE-PLAN A LA SAUVEGARDE : un accroche sur
    core.fsutil.atomic_write_bytes (toutes les ecritures ECF du projet y
    passent) marque l'index perime et relance la reconstruction des qu'un
    fichier suivi est ecrit -- la combo ouverte quelques secondes plus tard
    est deja fraiche.

Thread-safety : un seul rebuild a la fois par cle ; threads joignables via
wait_rebuilds() pour des tests deterministes.
"""
import sqlite3
import threading
from pathlib import Path
from typing import List, Optional, Tuple

_lock = threading.Lock()
_rebuild_threads: List[threading.Thread] = []


class _Entry:
    __slots__ = ("stamp", "db", "rebuilding")

    def __init__(self, stamp, names):
        self.stamp = stamp
        self.db = _new_db(names)
        self.rebuilding = False


def _new_db(names: List[str]) -> sqlite3.Connection:
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.execute("CREATE TABLE names (name TEXT PRIMARY KEY)")
    db.executemany("INSERT OR IGNORE INTO names VALUES (?)",
                   [(n,) for n in names])
    db.commit()
    return db


def _read(entry: _Entry) -> List[str]:
    return [r[0] for r in entry.db.execute(
        "SELECT name FROM names ORDER BY name")]


def _stamp(pairs) -> Tuple:
    out = []
    for p in pairs:
        if p is None:
            out.append(None)
            continue
        try:
            st = Path(p).stat()
            out.append((st.st_mtime_ns, st.st_size))
        except OSError:
            out.append(None)
    return tuple(out)


def _compute(items_path, blocks_path, players_only: bool) -> List[str]:
    from .block_creation import list_craftable_names_uncached
    return list_craftable_names_uncached(items_path, blocks_path, players_only)


def _rebuild(key, items_path, blocks_path, players_only: bool) -> None:
    try:
        try:
            names = _compute(items_path, blocks_path, players_only)
        except Exception:
            names = None          # fichier en cours d'ecriture, illisible...
        with _lock:
            entry = _entries.get(key)
            if entry is None:
                return            # reset entre-temps
            if names is not None:
                entry.stamp = _stamp((items_path, blocks_path))
                entry.db = _new_db(names)
            entry.rebuilding = False
    finally:
        with _lock:
            try:
                _rebuild_threads.remove(threading.current_thread())
            except ValueError:
                pass


def _kick(key, items_path, blocks_path, players_only: bool) -> None:
    """Lance la reconstruction en arriere-plan (marquee rebuilding)."""
    entry = _entries.get(key)
    if entry is None or entry.rebuilding:
        return
    entry.rebuilding = True
    t = threading.Thread(target=_rebuild,
                         args=(key, items_path, blocks_path, players_only),
                         daemon=True)
    _rebuild_threads.append(t)
    t.start()


_entries = {}


def get_names(items_path, blocks_path,
              players_only: bool = False) -> List[str]:
    """Liste triee des noms craftables, servie par l'index (voir docstring
    du module). Remplace list_craftable_names pour tous les appelants."""
    key = (str(items_path), str(blocks_path), players_only)
    stamp = _stamp((items_path, blocks_path))
    with _lock:
        entry = _entries.get(key)
        if entry is not None:
            if entry.stamp == stamp:
                return _read(entry)
            # perime : on sert tout de suite la liste precedente et on
            # reconstruit en arriere-plan (jamais d'attente pour une combo)
            _kick(key, items_path, blocks_path, players_only)
            return _read(entry)
    # premier appel pour cette cle : construction bloquante, donnee requise
    names = _compute(items_path, blocks_path, players_only)
    with _lock:
        _entries[key] = _Entry(stamp, names)
    return names


def refresh(items_path, blocks_path, players_only: bool = False) -> List[str]:
    """Reconstruction SYNCHRONE (tests et cas ou la fraicheur est requise
    immediatement)."""
    key = (str(items_path), str(blocks_path), players_only)
    names = _compute(items_path, blocks_path, players_only)
    with _lock:
        _entries[key] = _Entry(_stamp((items_path, blocks_path)), names)
    return names


def on_file_written(path) -> None:
    """Accroche de core.fsutil.atomic_write_bytes : un fichier de
    configuration suivi vient d'etre ecrit -> index perime + reconstruction
    en arriere-plan immediate (mise a jour a la sauvegarde, demande du
    31/10). Jamais d'exception : une ecriture ne doit jamais echouer a cause
    de l'index."""
    try:
        path = str(Path(path))
        with _lock:
            for key in list(_entries):
                items, blocks, players_only = key
                if path in (items, blocks):
                    _entries[key].stamp = None
                    _kick(key, items, blocks, players_only)
    except Exception:
        pass


def wait_rebuilds(timeout: float = 10.0) -> None:
    """Joint les reconstructions en cours (tests)."""
    with _lock:
        threads = list(_rebuild_threads)
    for t in threads:
        t.join(timeout)


def reset() -> None:
    """Vide l'index (tests)."""
    with _lock:
        _entries.clear()


# Accroche a TOUTES les ecritures atomiques du projet (fsutil ne connait pas
# ce module : enregistrement ici, a l'import, sans cycle -- name_index n'est
# charge qu'a la premiere utilisation de list_craftable_names).
from ..fsutil import register_write_hook  # noqa: E402
register_write_hook(on_file_written)
