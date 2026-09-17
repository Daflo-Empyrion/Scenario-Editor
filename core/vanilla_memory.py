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
Memoire de traduction VANILLE : paires EN -> FR officielles extraites des
CSV de localisation du jeu (dossier Content configure dans Options) :
Localization.csv (UI), PDA.csv (textes de mission) et Dialogues.csv
(dialogues de PNJ) -- demande 17/09/2026 : ne plus se limiter a Localization.
Consultee en REPLI par core.translation apres la memoire utilisateur : tout
texte identique a la vanille ressort avec la traduction officielle Eleon,
quel que soit le moteur choisi.

Generee LOCALEMENT depuis l'installation du jeu de l'utilisateur (jamais
redistribuee avec l'application : les textes du jeu appartiennent a Eleon).
Regeneration automatique si un CSV source est plus recent que le fichier
genere, absent, ou si l'index date de l'ancien format mono-fichier.
Consultation en lecture seule : la memoire UTILISATEUR garde toujours la
priorite. En cas de collision entre fichiers, Localization.csv gagne (le
premier de la liste de priorite).
"""
import json
import threading
from pathlib import Path
from typing import Optional

from . import settings
from .csv_handler import parse_csv_text
from .translation import find_language_aliases, _normalize, repair_mojibake

CONFIG_DIR = Path.home() / ".empyrion_editor"
VANILLA_MEMORY_FILE = CONFIG_DIR / "vanilla_memory.json"

_LOCK = threading.Lock()
_cache: Optional[dict] = None  # {'en:fr': {source_normalisee: traduction}}

# Ordre de priorite : le premier fichier qui definit une paire EN->FR gagne.
_SOURCE_CANDIDATES = (
    ("Extras", "Localization.csv"),
    ("Localization.csv",),
    ("Extras", "PDA", "PDA.csv"),
    ("Configuration", "Dialogues.csv"),
)


def _source_files() -> list:
    """CSV de localisation presents dans la vanille configuree, dans l'ordre
    de priorite (liste vide si la vanille n'est pas configuree)."""
    from . import settings
    vanilla = (settings.get_vanilla_content_path() or "").strip()
    if not vanilla:
        return []
    root = Path(vanilla)
    return [root.joinpath(*parts) for parts in _SOURCE_CANDIDATES
            if root.joinpath(*parts).is_file()]


def build_from_vanilla() -> int:
    """Genere (ou regenere) vanilla_memory.json depuis TOUS les CSV de
    localisation de la vanille configuree. Retourne le nombre de paires
    EN->FR importees ; leve une exception si la vanille n'est pas
    disponible."""
    files = _source_files()
    if not files:
        raise RuntimeError("Localisation de la vanille introuvable "
                           "(configure le dossier Content du jeu dans Options).")
    pairs: dict = {}
    sources: dict = {}
    found_cols = False
    for csv_path in files:
        doc = parse_csv_text(csv_path.read_text(encoding="utf-8"))
        header = doc.header or []
        en_col = fr_col = None
        for i, name in enumerate(header):
            norm = _normalize(repair_mojibake(name.strip()))
            if en_col is None and norm in find_language_aliases("en", "Anglais"):
                en_col = i
            elif fr_col is None and norm in find_language_aliases("fr", "Francais"):
                fr_col = i
        if en_col is None or fr_col is None:
            continue  # fichier sans colonnes EN/FR reconnues : ignore
        found_cols = True
        for row in doc.rows:
            if len(row) <= max(en_col, fr_col):
                continue
            src = " ".join(row[en_col].split())
            dst = " ".join(row[fr_col].split())
            if src and dst:
                pairs.setdefault(src, dst)
        sources[str(csv_path)] = int(csv_path.stat().st_mtime)
    if not found_cols:
        raise RuntimeError("Colonnes English/Francais introuvables dans "
                           "la localisation de la vanille.")
    data = {"_sources": sources, "en:fr": pairs}
    with _LOCK:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        VANILLA_MEMORY_FILE.write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8")
        global _cache
        _cache = None  # force le rechargement
    return len(pairs)


def _ensure_built() -> bool:
    """Genere la memoire vanille si la vanille est configuree et que l'index
    est absent, perime (un CSV source plus recent), incomplet (nouveau fichier
    de localisation apparu) ou dans l'ancien format mono-fichier. Jamais
    d'exception remontee (le fallback vanilla est un confort)."""
    files = _source_files()
    if not files:
        return False
    if not VANILLA_MEMORY_FILE.exists():
        try:
            build_from_vanilla()
            return True
        except Exception:
            return False
    try:
        data = json.loads(VANILLA_MEMORY_FILE.read_text(encoding="utf-8"))
        stored = data.get("_sources")
        if not isinstance(stored, dict):
            build_from_vanilla()  # ancien format (<17/09/2026) : regen
        else:
            current = {str(p): int(p.stat().st_mtime) for p in files}
            stored_norm = {k: int(float(v)) for k, v in stored.items()}
            if current != stored_norm:
                build_from_vanilla()
    except Exception:
        try:
            build_from_vanilla()  # index corrompu : tentative de reparation
        except Exception:
            pass  # on garde l'ancien, un re-save le fixera
    return VANILLA_MEMORY_FILE.exists()


def get_vanilla_cached(text: str, target: str) -> Optional[str]:
    """Traduction officielle vanille pour ce texte EN -> langue cible 'fr'
    (seule paire generee), ou None."""
    if not text or not text.strip() or target != "fr":
        return None
    if not _ensure_built():
        return None
    with _LOCK:
        global _cache
        if _cache is None:
            try:
                _cache = json.loads(VANILLA_MEMORY_FILE.read_text(
                    encoding="utf-8"))
            except Exception:
                _cache = {}
        pair = _cache.get("en:fr", {})
        norm = " ".join(text.split())
        return pair.get(norm)
