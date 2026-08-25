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
Reglages persistants simples de l'application.
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".empyrion_editor"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
DEFAULT_AUTHOR = "utilisateur"


def _read_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
        except Exception as e:
            logger.warning("Impossible de lire %s : %s", SETTINGS_FILE, e)
    return {}


def _write_settings(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


def _get(key: str, default):
    return _read_settings().get(key, default)


def _set(key: str, value) -> None:
    data = _read_settings()
    data[key] = value
    _write_settings(data)


def get_author() -> str:
    return _get('author', DEFAULT_AUTHOR)


def set_author(name: str) -> None:
    _set('author', name)


def get_annotations_enabled() -> bool:
    return _get('annotations_enabled', True)


def set_annotations_enabled(enabled: bool) -> None:
    data = _read_settings()
    data['annotations_enabled'] = enabled
    data['author'] = data.get('author', DEFAULT_AUTHOR)
    _write_settings(data)


def get_language() -> str:
    return _get('language', 'fr')


def set_language(lang: str) -> None:
    _set('language', lang)


def get_merge_enabled() -> bool:
    return _get('merge_enabled', False)


def set_merge_enabled(enabled: bool) -> None:
    _set('merge_enabled', enabled)


def get_online_translation_enabled() -> bool:
    """True (par defaut) tant que l'utilisateur n'a pas explicitement desactive
    la traduction en ligne (Google Translate, via deep-translator) --
    fonctionnalite qui envoie le texte a traduire aux serveurs Google. Voir
    core/translation.py:translate_text() qui refuse de fonctionner si False,
    et PRIVACY.md pour la politique de confidentialite complete. Ajoutee pour
    respecter les exigences SignPath Foundation sur les fonctions transferant
    des donnees utilisateur (offrir une option de desactivation explicite)."""
    return _get('online_translation_enabled', True)


def get_autosave_enabled() -> bool:
    """True (par defaut) -- sauvegarde automatique periodique des onglets
    modifies vers un dossier de recuperation SEPARE de la vraie copie de
    travail (voir core/autosave.py), jamais dans les vrais fichiers du
    scenario. Uniquement utile pour recuperer du travail non enregistre apres
    un plantage ou une fermeture inattendue."""
    return _get('autosave_enabled', True)


def set_autosave_enabled(enabled: bool) -> None:
    _set('autosave_enabled', enabled)


def set_online_translation_enabled(enabled: bool) -> None:
    _set('online_translation_enabled', enabled)


def get_backup_root(kind: str) -> str:
    return _get(f'backup_root_{kind}', '')


def set_backup_root(kind: str, path: str) -> None:
    _set(f'backup_root_{kind}', path)


def get_language_chosen() -> bool:
    return _get('language_chosen', False)


def set_language_chosen(chosen: bool = True) -> None:
    _set('language_chosen', chosen)


def get_auto_open_tutorial() -> bool:
    return _get('auto_open_tutorial', True)


def set_auto_open_tutorial(auto_open: bool) -> None:
    _set('auto_open_tutorial', auto_open)


def get_default_translation_language() -> tuple:
    saved = _get('default_translation_language', None)
    if saved and len(saved) == 2:
        return tuple(saved)
    return ('fr', 'Francais')


def set_default_translation_language(code: str, label: str) -> None:
    _set('default_translation_language', [code, label])
