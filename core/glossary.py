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
Glossaire terminologique de traduction (12/09/2026) : paires
terme source -> traduction imposee, appliquees AVANT l'envoi au moteur
de traduction (quel qu'il soit : Argos, Google, Groq, DeepL, NLLB...) via
des jetons neutres, puis restaurees dans la reponse.

MULTI-LANGUES (v1.10.0) : chaque entree porte la langue CIBLE a laquelle
elle s'applique ("target" : "fr", "de"...). Une entree n'est appliquee
QUE pour les traductions vers sa langue -- avant, la traduction imposee
(francaise) etait reinjectee dans TOUTES les langues cibles. Les entrees
de l'ancien format (sans "target") sont migrees en "fr" au chargement.

Application : chaque terme actif est remplace dans le texte par un jeton
XXGLOS<n>XX (mot entier, insensible a la casse) ; le moteur ne traduit donc
JAMAIS le terme, et la traduction officielle du glossaire est reinjectee a la
place. Les termes les plus longs sont appliques en premier ('Warp Drive'
avant 'Warp').

Alimentation : ajout manuel (dialogue de gestion, menu Options, avec choix
de la langue cible) et auto-alimentation a la VALIDATION d'une cellule
courte (<= _AUTO_FEED_MAX_WORDS mots) dans les revues de traduction -- voir
auto_feed_ok() ; l'entree creee porte la langue cible de la cellule validee.

Stockage : ~/.empyrion_editor/glossary.json, ecrit immediatement (petit
fichier, rarement modifie en rafale).
"""
import json
import re
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple

CONFIG_DIR = Path.home() / ".empyrion_editor"
GLOSSARY_FILE = CONFIG_DIR / "glossary.json"

# Alimentation automatique : une cellule validee avec au plus ce nombre de
# mots alimente le glossaire (au-dela, c'est une phrase, pas une terminologie).
AUTO_FEED_MAX_WORDS = 6

# Langue des entrees de l'ANCIEN format (sans champ "target") : le glossaire
# a toujours ete un outil EN->FR, la migration les range en "fr".
LEGACY_TARGET = "fr"

_LOCK = threading.Lock()
_cache: Optional[List[dict]] = None  # [{"src":..., "dst":..., "target":..., "on": bool}]

# separement : caracteres interdits dans une entree (balises, jetons)
_FORBIDDEN_RE = re.compile(r"[\[\]{}\\]|XXTAG|XXGLOS", re.IGNORECASE)
_TOKEN_RE = re.compile(r"XXGLOS(\d+)XX")
# Un terme source doit contenir au moins UN caractere alphanumerique : un
# src purement ponctuation (ex: '-', '===') matche des fragments de mots
# via \b et injecte du contenu invente dans TOUTES les langues (vecu reel
# 20/09/2026 : src '-' -> dst 'Mourir / Sac a dos / Nager / Faction'
# ajoutee par auto-alimentation sur une cellule-tiret validee).
_WORD_CHAR_RE = re.compile(r"\w", re.UNICODE)


def _src_is_valid(src: str) -> bool:
    return bool(src) and bool(_WORD_CHAR_RE.search(src))


def _normalize_entry(entry: dict) -> dict:
    """Complement d'entree : cible manquante (ancien format) -> fr."""
    out = dict(entry)
    if not out.get("target"):
        out["target"] = LEGACY_TARGET
    return out


def _load_locked() -> List[dict]:
    global _cache
    if _cache is None:
        try:
            data = json.loads(GLOSSARY_FILE.read_text(encoding="utf-8"))
            _cache = [_normalize_entry(e) for e in data] if isinstance(data, list) else []
        except Exception:
            _cache = []
    return _cache


def _save_locked(entries: List[dict]) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        GLOSSARY_FILE.write_text(
            json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


def entries() -> List[dict]:
    with _LOCK:
        return [dict(e) for e in _load_locked()]


def active_entries(target: str = LEGACY_TARGET) -> List[Tuple[str, str]]:
    """[(source, traduction imposee)] des entrees actives pour la langue
    cible `target`, les plus longues d'abord (priorite d'application)."""
    with _LOCK:
        return sorted(
            ((e["src"], e["dst"]) for e in _load_locked()
             if e.get("on", True) and e.get("src") and e.get("dst")
             and e.get("target") == target
             and _src_is_valid(e["src"])),
            key=lambda pair: len(pair[0]), reverse=True)


def add_entry(src: str, dst: str, enabled: bool = True,
              target: str = LEGACY_TARGET) -> bool:
    """Ajoute (ou met a jour la traduction de) une entree pour la langue
    cible `target`. Le meme terme source peut avoir une traduction imposee
    par langue. Retourne False si le terme est vide ou contient des
    caracteres techniques interdits."""
    src = (src or "").strip()
    dst = (dst or "").strip()
    target = (target or LEGACY_TARGET).strip() or LEGACY_TARGET
    if not src or not dst or _FORBIDDEN_RE.search(src) or _FORBIDDEN_RE.search(dst):
        return False
    if not _src_is_valid(src):
        return False  # terme source purement ponctuation : jamais (vecu 20/09)
    with _LOCK:
        entries_list = _load_locked()
        for e in entries_list:
            if (e["src"].lower() == src.lower()
                    and e.get("target") == target):
                e["dst"] = dst
                e["on"] = enabled
                _save_locked(entries_list)
                return True
        entries_list.append({"src": src, "dst": dst, "target": target,
                             "on": enabled})
        _save_locked(entries_list)
        return True


def remove_entry(src: str, target: str = LEGACY_TARGET) -> None:
    global _cache
    with _LOCK:
        entries_list = _load_locked()
        kept = [e for e in entries_list
                if not (e["src"].lower() == src.lower().strip()
                        and e.get("target") == target)]
        if len(kept) != len(entries_list):
            _save_locked(kept)
            # le cache en memoire pointe encore sur l'ANCIENNE liste :
            # sans reassignation, l'entree supprimee restait active
            # jusqu'au redemarrage (bug latent, vecu 19/09/2026).
            _cache = kept


def set_enabled(src: str, enabled: bool,
                target: str = LEGACY_TARGET) -> None:
    with _LOCK:
        entries_list = _load_locked()
        for e in entries_list:
            if (e["src"].lower() == src.lower().strip()
                    and e.get("target") == target):
                e["on"] = enabled
        _save_locked(entries_list)


def auto_feed_ok(source_text: str) -> bool:
    """Vrai si cette cellule validee doit alimenter le glossaire : assez
    courte pour etre une terminologie (<= AUTO_FEED_MAX_WORDS mots) ET
    contenant au moins un caractere alphanumerique (une cellule '-' seule
    validee avait cree l'entree toxique '-' -> liste inventee, vecu
    20/09/2026)."""
    if not _src_is_valid(source_text):
        return False
    return 0 < len(source_text.split()) <= AUTO_FEED_MAX_WORDS


def apply_glossary(text: str, target: str = LEGACY_TARGET
                   ) -> Tuple[str, List[Tuple[str, str]]]:
    """Remplace les termes actifs du glossaire POUR LA LANGUE CIBLE
    `target` par des jetons XXGLOS<n>XX. Retourne (texte_jetonnes,
    [(jeton, traduction_imposee)]). Chaine et liste vides si le glossaire
    est vide ou sans entree pour cette langue (appel sans cout)."""
    active = active_entries(target)
    if not active:
        return text, []
    replacements: List[Tuple[str, str]] = []
    for i, (src, dst) in enumerate(active):
        token = f"XXGLOS{i}XX"
        pattern = re.compile(r"\b" + re.escape(src) + r"\b", re.IGNORECASE)
        if pattern.search(text):
            text = pattern.sub(token, text)
            replacements.append((token, dst))
    return text, replacements


def restore_glossary(translated: str, replacements: List[Tuple[str, str]]) -> str:
    """Reinjecte les traductions imposees a la place des jetons (remplacement
    simple : les espaces autour du jeton sont celles de la phrase traduite et
    doivent rester en place -- consommer les espaces collerait les mots)."""
    for token, dst in replacements:
        translated = translated.replace(token, dst)
    return translated
