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
