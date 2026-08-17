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
"""
import json
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".empyrion_editor"
MEMORY_FILE = CONFIG_DIR / "translation_memory.json"


def _normalize_key(text: str) -> str:
    """Normalise le texte source pour la clef de cache : espaces superflus retires,
    mais la casse et les accents sont conserves (le sens peut en dependre)."""
    return " ".join(text.split())


def _load() -> dict:
    if MEMORY_FILE.exists():
        try:
            return json.loads(MEMORY_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {}


def _save(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        MEMORY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding='utf-8')
    except OSError:
        pass  # la memoire est un confort, pas une donnee critique -- on n'interrompt jamais pour ca


def get_cached(text: str, source: str, target: str) -> Optional[str]:
    """Retourne la traduction memorisee pour ce texte/cette paire de langues, ou None
    si jamais rencontree."""
    if not text or not text.strip():
        return None
    data = _load()
    pair_key = f"{source}:{target}"
    return data.get(pair_key, {}).get(_normalize_key(text))


def store(text: str, source: str, target: str, translated: str) -> None:
    """Enregistre une traduction pour reutilisation future. N'ecrase jamais une
    entree existante avec le meme texte source par une traduction differente sans
    raison -- mais une nouvelle traduction (ex: l'utilisateur a corrige le resultat
    a la main) remplace bien l'ancienne, c'est le comportement voulu."""
    if not text or not text.strip() or not translated:
        return
    data = _load()
    pair_key = f"{source}:{target}"
    data.setdefault(pair_key, {})[_normalize_key(text)] = translated
    _save(data)


def entry_count() -> int:
    """Nombre total d'entrees memorisees, toutes paires de langues confondues --
    utile pour un petit indicateur dans l'interface."""
    data = _load()
    return sum(len(v) for v in data.values())


def clear() -> None:
    """Vide entierement la memoire (bouton 'Reinitialiser' dans les options)."""
    _save({})
