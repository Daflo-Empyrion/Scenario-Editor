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
    """Dernier dossier de sauvegardes utilise pour ce type ('scenario' ou 'savegame'),
    ou chaine vide si jamais defini."""
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
            return data.get(f'backup_root_{kind}', '')
        except Exception:
            pass
    return ''


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
