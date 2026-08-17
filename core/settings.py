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
Reglages persistants simples de l'application (pour l'instant : le nom utilise dans
les annotations de tracabilite lors des modifications, ex: '# original: X -- Mod par
<nom>'). Stocke dans le meme dossier que les projets recents.
"""
import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".empyrion_editor"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
DEFAULT_AUTHOR = "utilisateur"


def get_author() -> str:
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
            return data.get('author', DEFAULT_AUTHOR)
        except Exception:
            pass
    return DEFAULT_AUTHOR


def set_author(name: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {}
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    data['author'] = name
    SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


def get_annotations_enabled() -> bool:
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
            return data.get('annotations_enabled', True)
        except Exception:
            pass
    return True


def set_annotations_enabled(enabled: bool) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {}
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    data['annotations_enabled'] = enabled
    data['author'] = data.get('author', DEFAULT_AUTHOR)
    SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


def get_language() -> str:
    """Code langue de l'interface : 'fr' ou 'en'."""
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
            return data.get('language', 'fr')
        except Exception:
            pass
    return 'fr'


def set_language(lang: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {}
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    data['language'] = lang
    SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


def get_merge_enabled() -> bool:
    """La fusion (copier/fusionner fichier, dossier, bloc, ligne) est DESACTIVEE par
    defaut : trop de cas particuliers pour etre fiable a 100%, source de scenarios
    casses. La duplication (creation d'une entree nouvelle et independante) reste
    toujours disponible, elle. Peut etre reactivee via Options si besoin."""
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
            return data.get('merge_enabled', False)
        except Exception:
            pass
    return False


def set_merge_enabled(enabled: bool) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {}
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    data['merge_enabled'] = enabled
    SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


def get_backup_root(kind: str) -> str:
    """Dernier dossier de sauvegardes utilise pour ce type ('scenario' ou 'savegame'),
    ou chaine vide si jamais defini."""
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
            return data.get(f'backup_root_{kind}', '')
        except Exception:
            pass
    return ''


def get_language_chosen() -> bool:
    """True si l'utilisateur a deja explicitement choisi une langue au moins une
    fois (via le selecteur de tout premier lancement) -- permet de distinguer
    'jamais choisi' de 'a choisi francais', puisque get_language() renvoie 'fr' par
    defaut dans les deux cas."""
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
            return bool(data.get('language_chosen', False))
        except Exception:
            pass
    return False


def set_language_chosen(chosen: bool = True) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {}
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    data['language_chosen'] = chosen
    SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


def get_auto_open_tutorial() -> bool:
    """True (par defaut) tant que l'utilisateur n'a pas explicitement decoche
    'Ne plus afficher automatiquement au demarrage' dans le tutoriel."""
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
            return bool(data.get('auto_open_tutorial', True))
        except Exception:
            pass
    return True


def set_auto_open_tutorial(auto_open: bool) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {}
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    data['auto_open_tutorial'] = auto_open
    SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


def get_default_translation_language() -> tuple:
    """Langue utilisee par le bouton de traduction rapide (une seule cellule ou une
    selection, sans passer par le sous-menu de choix de langue). Retourne
    (code_iso, libelle) -- Francais par defaut."""
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
            saved = data.get('default_translation_language')
            if saved and len(saved) == 2:
                return tuple(saved)
        except Exception:
            pass
    return ('fr', 'Francais')


def set_default_translation_language(code: str, label: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {}
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    data['default_translation_language'] = [code, label]
    SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


def set_backup_root(kind: str, path: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {}
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    data[f'backup_root_{kind}'] = path
    SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
