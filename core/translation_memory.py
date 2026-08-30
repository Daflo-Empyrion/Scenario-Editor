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

"""
Memoire de traduction : reutilise une traduction deja obtenue pour le meme texte
source (meme langue source -> meme langue cible) plutot que de rappeler l'API a
chaque fois -- plus rapide, evite de gaspiller des requetes, et surtout garantit que
le meme texte se traduit toujours de la meme facon partout dans le fichier (probleme
frequent avec un traducteur automatique : la meme phrase source peut ressortir
legerement differente d'un appel a l'autre).

Stockage : un simple fichier JSON sous le dossier de configuration de l'appli
(~/.empyrion_editor/translation_memory.json), commun a tous les projets -- la memoire
s'enrichit au fil du temps, quel que soit le fichier/scenario en cours d'edition.

FIL DE CACHE EN MEMOIRE : le JSON n'est lu UNE SEULE FOIS puis garde en RAM -- une
traduction en lot de quelques milliers de cellules ne doit ni relire ni reecrire le
fichier a chaque cellule (l'ancienne implementation, lecture+reecriture complete par
operation, devenait O(n^2) en I/O sur un lot). Les ecritures sont DIFFEREES et
DEBORDEES (au plus une par _FLUSH_INTERVAL_S ou _FLUSH_EVERY_N entrees) ; flush()
force la persistance (registre via atexit pour une sortie normale de l'application).
En cas de crash, on perd au pire les dernieres secondes d'entrees -- la memoire est
un confort, pas une donnee critique (l'ancienne implementation perdait pareillement
la totalite du fichier en cas d'ecriture coupee, faute d'atomicite).

THREAD-SAFETY : toutes les operations passent par un verrou -- les appels peuvent
venir de threads differents (worker de traduction, interface). Le cache s'invalide
automatiquement si le chemin du fichier change (tests, configuration future).
"""
import atexit
import json
import threading
import time
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".empyrion_editor"
MEMORY_FILE = CONFIG_DIR / "translation_memory.json"

# Persistance debordee : inutile d'ecriver le fichier a chaque store() -- un lot
# de traduction genere des dizaines d'entrees a la seconde. Ces seuils garantissent
# qu'au pire on perd _FLUSH_INTERVAL_S de traductions en cas de crash brutal.
_FLUSH_INTERVAL_S = 5.0
_FLUSH_EVERY_N = 50

_LOCK = threading.Lock()
_cache: Optional[dict] = None          # charge a la premiere utilisation (lazy)
_cache_for_path: Optional[Path] = None # chemin dont provient _cache (invalidation si MEMORY_FILE change)
_dirty_entries = 0                     # entrees non persistees depuis la derniere ecriture
_last_save_monotonic = 0.0


def _normalize_key(text: str) -> str:
    """Normalise le texte source pour la clef de cache : espaces superflus retires,
    mais la casse et les accents sont conserves (le sens peut en dependre)."""
    return " ".join(text.split())


def _load_from(path: Path) -> dict:
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                return data
        except Exception:
            # Fichier corrompu (crash ancien, edition manuelle...) : on repart
            # d'un dictionnaire vide -- la memoire est un confort, jamais une
            # donnee critique, et la prochaine ecriture (atomique) la reconstruit.
            pass
    return {}


def _get_cache_locked() -> dict:
    global _cache, _cache_for_path
    if _cache is None or _cache_for_path != MEMORY_FILE:
        _cache = _load_from(MEMORY_FILE)
        _cache_for_path = MEMORY_FILE
    return _cache


def _save_locked(data: dict) -> None:
    global _dirty_entries, _last_save_monotonic
    from .fsutil import atomic_write_text
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        atomic_write_text(MEMORY_FILE, json.dumps(data, ensure_ascii=False, indent=0))
        _dirty_entries = 0
        _last_save_monotonic = time.monotonic()
    except OSError:
        pass  # la memoire est un confort, pas une donnee critique -- on n'interrompt jamais pour ca


def _should_flush_locked() -> bool:
    if _last_save_monotonic == 0.0:
        return True  # jamais sauvegarde pendant cette session : la premiere entree part au disque
    return (_dirty_entries >= _FLUSH_EVERY_N
            or (time.monotonic() - _last_save_monotonic) >= _FLUSH_INTERVAL_S)


def get_cached(text: str, source: str, target: str) -> Optional[str]:
    """Retourne la traduction memorisee pour ce texte/cette paire de langues, ou None
    si jamais rencontree."""
    if not text or not text.strip():
        return None
    with _LOCK:
        data = _get_cache_locked()
        pair_key = f"{source}:{target}"
        return data.get(pair_key, {}).get(_normalize_key(text))


def store(text: str, source: str, target: str, translated: str) -> None:
    """Enregistre une traduction pour reutilisation future. N'ecrase jamais une
    entree existante avec le meme texte source par une traduction differente sans
    raison -- mais une nouvelle traduction (ex: l'utilisateur a corrige le resultat
    a la main) remplace bien l'ancienne, c'est le comportement voulu.

    L'ecriture disque est debordee (voir en-tete de module) ; appeler flush()
    pour forcer la persistance immedia."""
    global _dirty_entries
    if not text or not text.strip() or not translated:
        return
    with _LOCK:
        data = _get_cache_locked()
        pair_key = f"{source}:{target}"
        data.setdefault(pair_key, {})[_normalize_key(text)] = translated
        _dirty_entries += 1
        if _should_flush_locked():
            _save_locked(data)


def flush() -> None:
    """Persiste immediatement les entrees non encore ecrites (sans effet si tout
    est deja sur disque). Appeler avant de quitter l'application ; aussi enregistre
    via atexit pour couvrir toute sortie normale de l'interpreteur."""
    with _LOCK:
        if _dirty_entries > 0:
            _save_locked(_get_cache_locked())


def entry_count() -> int:
    """Nombre total d'entrees memorisees, toutes paires de langues confondues --
    utile pour un petit indicateur dans l'interface."""
    with _LOCK:
        data = _get_cache_locked()
        return sum(len(v) for v in data.values())


def clear() -> None:
    """Vide entierement la memoire (bouton 'Reinitialiser' dans les options)."""
    global _cache
    with _LOCK:
        _cache = {}
        _save_locked(_cache)


atexit.register(flush)
