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
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".empyrion_editor"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
DEFAULT_AUTHOR = "utilisateur"

# Protege les sequences lecture-modification-ecriture ci-dessous contre une
# corruption si deux threads du MEME processus ecrivent en meme temps (ex:
# un toggle utilisateur dans l'UI pendant qu'un autosave en arriere-plan lit
# les reglages) -- ne protege pas contre deux PROCESSUS distincts (hors de
# portee : l'appli ne gere qu'une seule instance de settings.json a la fois
# en usage normal).
_LOCK = threading.Lock()

# Cache memoire du settings.json (v1.10.0, lenteur generale vecue) : le
# fichier etait RELU ET PARSE a CHAQUE getter -- or des chemins chauds le
# consultent par ligne/par cellule (memoire vanille, chaine de secours,
# reglages moteur...). Invalidation par mtime : une edition manuelle du
# fichier (ou un autre processus) reste prise en compte.
_CACHE_DATA: Optional[dict] = None
_CACHE_MTIME: float = -1.0


def _read_settings() -> dict:
    with _LOCK:
        return _read_settings_locked()


def _read_settings_locked() -> dict:
    """Version sans verrou de _read_settings(), a utiliser UNIQUEMENT depuis
    une section deja protegee par _LOCK (evite un deadlock si appelee depuis
    _set()/set_annotations_enabled(), qui tiennent deja le verrou)."""
    global _CACHE_DATA, _CACHE_MTIME
    try:
        mtime = SETTINGS_FILE.stat().st_mtime
    except OSError:
        _CACHE_DATA = None
        _CACHE_MTIME = -1.0
        return {}
    if _CACHE_DATA is not None and mtime == _CACHE_MTIME:
        return _CACHE_DATA
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                _CACHE_DATA = data
                _CACHE_MTIME = mtime
                return data
        except Exception as e:
            logger.warning("Impossible de lire %s : %s", SETTINGS_FILE, e)
    return {}


def _write_settings(data: dict) -> None:
    with _LOCK:
        _write_settings_locked(data)


def _write_settings_locked(data: dict) -> None:
    """Version sans verrou de _write_settings() -- meme raison que
    _read_settings_locked()."""
    global _CACHE_DATA, _CACHE_MTIME
    from .fsutil import atomic_write_text
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # Ecriture ATOMIQUE : settings.json contient la langue, l'etat des options,
    # la liste des annotations... sa corruption par un crash pendant l'ecriture
    # reinitialiserait d'un coup toute la configuration de l'utilisateur.
    atomic_write_text(SETTINGS_FILE, json.dumps(data, ensure_ascii=False))
    # le cache sert la nouvelle valeur immédiatement (et evite une relecture)
    _CACHE_DATA = data
    try:
        _CACHE_MTIME = SETTINGS_FILE.stat().st_mtime
    except OSError:
        _CACHE_MTIME = -1.0


def _get(key: str, default):
    return _read_settings().get(key, default)


def _set(key: str, value) -> None:
    with _LOCK:
        data = _read_settings_locked()
        data[key] = value
        _write_settings_locked(data)


def get_author() -> str:
    return _get('author', DEFAULT_AUTHOR)


def set_author(name: str) -> None:
    _set('author', name)


def get_annotations_enabled() -> bool:
    return _get('annotations_enabled', True)


def set_annotations_enabled(enabled: bool) -> None:
    with _LOCK:
        data = _read_settings_locked()
        data['annotations_enabled'] = enabled
        data['author'] = data.get('author', DEFAULT_AUTHOR)
        _write_settings_locked(data)


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


def get_theme() -> str:
    """Id du theme visuel choisi (voir core/themes.py) -- 'classic' par
    defaut pour ne rien changer visuellement tant que l'utilisateur n'a pas
    choisi explicitement un autre theme dans Options > Theme."""
    from core.themes import DEFAULT_THEME_ID
    return _get('theme', DEFAULT_THEME_ID)


def set_theme(theme_id: str) -> None:
    _set('theme', theme_id)


def get_fluent_pilot_enabled() -> bool:
    """Pilote PyQt-Fluent-Widgets sur la fenetre principale (decision du
    09/09/2026) : True par defaut pour que le pilote soit visible des la
    premiere relance ; reactivable/desactivable dans Options."""
    return _get('fluent_pilot_enabled', True)


def set_fluent_pilot_enabled(enabled: bool) -> None:
    _set('fluent_pilot_enabled', enabled)


def get_production_scenario_path(working_root: str = "") -> str:
    """Repertoire du scenario EN PRODUCTION (celui que le jeu charge, ex :
    <vanille>/Content/Scenarios/RE2 ATL) — destination de la synchronisation
    de fin de session. MEMORISE PAR PROJET (vecu 24/09 : un reglage global
    faisait proposer le scenario RE2 ATL pour N'IMPORTE QUEL projet — y
    compris dans les tests, ou l'exec modal se figeait)."""
    paths = _get('production_scenario_paths', {}) or {}
    if working_root:
        return paths.get(_prod_key(working_root), '')
    return ''


def set_production_scenario_path(working_root: str, path: str) -> None:
    paths = _get('production_scenario_paths', {}) or {}
    paths[_prod_key(working_root)] = path
    _set('production_scenario_paths', paths)


def _prod_key(working_root: str) -> str:
    import os as _os
    return _os.path.normcase(_os.path.abspath(str(working_root)))


def get_propose_sync_on_close() -> bool:
    """Proposer la synchronisation vers la production a la fermeture de
    l'application (demande 24/09/2026). La case « ne plus me proposer » du
    dialogue passe a False."""
    return _get('propose_sync_on_close', True)


def set_propose_sync_on_close(enabled: bool) -> None:
    _set('propose_sync_on_close', enabled)


def get_press_anim_enabled() -> bool:
    """Animation de pression des boutons (enfoncement subtil, look Relief
    phase 2 du 12/09/2026) : True par defaut (activee), desactivable dans
    Options > Interface. N'a d'effet QUE sur un theme Relief."""
    return _get('press_anim_enabled', True)


def set_press_anim_enabled(enabled: bool) -> None:
    _set('press_anim_enabled', enabled)


def get_nllb_variant() -> str:
    """Variante du modele NLLB installee/utilisee ('600M' par defaut,
    '1.3B' pour la qualite maximale)."""
    return _get('nllb_variant', '600M')


def set_nllb_variant(variant: str) -> None:
    _set('nllb_variant', variant)


def get_nllb_beam_size() -> int:
    """Taille du faisceau (beam search) du decodeur NLLB : 2 = rapide,
    4 = equilibre (defaut), 8 = qualite maximale au prix de la vitesse.
    Determ : meme entree -> meme traduction (pas de sampling)."""
    try:
        return int(_get('nllb_beam_size', 4))
    except (TypeError, ValueError):
        return 4


def set_nllb_beam_size(size: int) -> None:
    if isinstance(size, int) and 1 <= size <= 10:
        _set('nllb_beam_size', size)


def get_groq_api_key() -> str:
    """Cle API Groq (console.groq.com) pour le moteur 'groq' -- LLM en
    ligne compatible OpenAI. STOCKEE EN LOCAL dans settings.json uniquement
    (jamais dans le depot)."""
    return _get('groq_api_key', '')


def set_groq_api_key(key: str) -> None:
    _set('groq_api_key', (key or '').strip())


def get_groq_model() -> str:
    """Modele Groq utilise pour la traduction (defaut : qwen3.8-27b, sans
    raisonnement -- le meilleur rapport qualite/vitesse/tokens teste)."""
    return _get('groq_model', 'qwen/qwen3.8-27b')


def set_groq_model(model: str) -> None:
    _set('groq_model', (model or '').strip())


def get_deepl_api_key() -> str:
    """Cle API DeepL (plan DeepL API FREE : 500 000 caracteres/mois,
    sans carte bancaire -- la cle free se termine par ':fx'). Stockee en
    LOCAL dans settings.json uniquement (jamais dans le depot). Le texte
    a traduire part chez DeepL SE : soumis a la case 'Traduction en
    ligne' comme les autres moteurs en ligne."""
    return _get('deepl_api_key', '')


def set_deepl_api_key(key: str) -> None:
    _set('deepl_api_key', (key or '').strip())


def get_engine_fallback_enabled() -> bool:
    """Bascule automatique entre moteurs (v1.10.0, inspiree du failover
    de freellmapi) : quand le moteur principal (radio du sous-menu
    Moteur) atteint son quota ou tombe en panne, la chaine de secours
    enchaine les autres moteurs disponibles -- Groq -> DeepL -> Google
    -> NLLB -> Argos, l'ordre reel partant du moteur principal. True par
    defaut, desactivable dans Options > Traduction."""
    return _get('engine_fallback_enabled', True)


def set_engine_fallback_enabled(enabled: bool) -> None:
    _set('engine_fallback_enabled', enabled)


def get_window_geometry(key: str) -> list:
    """Geometrie persistee d'une fenetre ([x, y, w, h] ou [x, y, w, h,
    maximise]) ou liste vide -- voir gui/window_geometry.py (v1.10.0 :
    ne plus avoir a agrandir les fenetres a la main a chaque ouverture)."""
    geo = _get(f'win_geo_{key}', [])
    return geo if isinstance(geo, list) else []


def set_window_geometry(key: str, geo: list) -> None:
    if (isinstance(geo, list) and len(geo) in (4, 5)
            and all(isinstance(v, (int, float)) for v in geo)):
        _set(f'win_geo_{key}', geo)


def get_groq_batch_enabled() -> bool:
    """Mode LOTS du moteur Groq (v1.8.0) : plusieurs cellules traduites par
    requete au lieu d'une par appel (tier gratuit plafonne en debit :
    ~30 req/min) -- True par defaut, desactivable dans Options >
    Traduction. Le squelette de jetons de CHAQUE cellule reste verifie :
    une cellule deviante repasse en mode cellule entiere."""
    return _get('groq_batch_enabled', True)


def set_groq_batch_enabled(enabled: bool) -> None:
    _set('groq_batch_enabled', enabled)


def get_groq_style() -> str:
    """Conseigne de style/ton libre (registre, tutoiement, terminologie...)
    injectee dans la consigne systeme envoyee au modele Groq (demande du
    backlog 18/09/2026). Vide = consigne par defaut (localisateur de jeu
    sobre)."""
    return _get('groq_style', '')


def set_groq_style(style: str) -> None:
    _set('groq_style', (style or '').strip()[:500])


def get_extra_icons_dir() -> str:
    """Dossier d'icones supplementaires (icônes de MODS, ex RE2) fusionne en
    PRIORITE HAUTE dans l'index d'icones (apres les sources vanille/scenario,
    voir core.tech_tree_icons.build_icon_index). Vide = desactive."""
    return _get('extra_icons_dir', "")


def set_extra_icons_dir(path: str) -> None:
    _set('extra_icons_dir', path)


def get_translation_engine() -> str:
    """Moteur de traduction prefere : 'google' (en ligne, defaut) ou 'argos'
    (hors ligne, voir core/argos_provider.py -- requiert le moteur + une
    paire de langues installes)."""
    return _get('translation_engine', 'google')


def set_translation_engine(engine: str) -> None:
    if engine in ('google', 'argos', 'nllb', 'groq', 'deepl'):
        _set('translation_engine', engine)


def get_vanilla_content_path() -> str:
    """Dossier Content de l'installation Steam du jeu (ex:
    C:/Program Files (x86)/Steam/steamapps/common/Empyrion - Galactic
    Survival/Content) -- utilise par le module PDA pour completer les
    suggestions contextuelles (POI, playfields, creatures...) avec les
    valeurs vanille, sur le modele du repli localization_vanilla.pak. Vide =
    non renseigne (suggestions scenario seules)."""
    return _get('vanilla_content_path', '')


def set_vanilla_content_path(path: str) -> None:
    _set('vanilla_content_path', path)
