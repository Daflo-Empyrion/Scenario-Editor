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

"""Corpus de traduction partage : les cles deja traduites dans les trois CSV
d'un scenario de reference (Localization, Dialogues, PDA), embarquees avec
l'application et completables par un dossier perso.

But (demande 03/11/2026) : quand un utilisateur traduit une de ces trois
familles de fichiers, une cle deja traduite dans le corpus est reprise
TELLE QUELLE (toutes les langues de la ligne) au lieu de payer une
traduction IA. L'appariement par CLE est plus fiable que celui par texte
deja utilise par la memoire vanilla (core/vanilla_memory.py) ; les deux se
completent, la cle n'existant pas toujours dans le corpus.

Ordre de priorite d'une valeur : la cellule deja remplie du fichier courant
n'est JAMAIS ecrasee -- on ne comble que les vides.
"""
from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core import settings as _settings

# Fichiers embarques dans data/corpus_traduction.zip (noms fixes).
EMBEDDED_ZIP = Path(__file__).resolve().parent.parent / "data" / "corpus_traduction.zip"
EMBEDDED_MEMBERS = {
    "localization": "Localization.csv",
    "dialogues": "Dialogues.csv",
    "pda": "PDA.csv",
}

# (motif de nom de fichier, type de corpus), du plus specifique au plus large.
_NAME_HINTS = (
    ("dialogues.csv", "dialogues"),
    ("pda.csv", "pda"),
    ("localization.csv", "localization"),
)

_cache: Dict[str, Dict[str, Dict[str, str]]] = {}


def detect_type(path) -> Optional[str]:
    """Type de corpus d'un fichier CSV, d'apres son nom ; None si inconnu
    (un CSV quelconque n'a pas de corpus)."""
    name = Path(path).name.casefold()
    for hint, kind in _NAME_HINTS:
        if name == hint:
            return kind
    return None


def _rows_index(header: List[str], rows: List[List[str]]) -> Dict[str, Dict[str, str]]:
    index: Dict[str, Dict[str, str]] = {}
    if not header:
        return index
    labels = [h.strip() for h in header]
    for row in rows:
        if not row or not row[0].strip():
            continue
        key = row[0].strip()
        if key in index:
            # premiere occurrence gagnante : les CSV du jeu peuvent contenir
            # des cles en double, on ne les fusionne pas
            continue
        index[key] = {labels[i]: (row[i] if i < len(row) else "")
                      for i in range(1, len(labels))}
    return index


def _parse_csv_text(text: str) -> Dict[str, Dict[str, str]]:
    reader = csv.reader(io.StringIO(text))
    all_rows = [r for r in reader if any(c.strip() for c in r)]
    if not all_rows:
        return {}
    return _rows_index(all_rows[0], all_rows[1:])


def _read_member(zf: zipfile.ZipFile, member: str) -> Optional[str]:
    try:
        return zf.read(member).decode("utf-8-sig", errors="replace")
    except KeyError:
        return None


def _load_embedded(kind: str) -> Dict[str, Dict[str, str]]:
    if not EMBEDDED_ZIP.is_file():
        return {}
    try:
        with zipfile.ZipFile(EMBEDDED_ZIP) as zf:
            text = _read_member(zf, EMBEDDED_MEMBERS[kind])
    except (OSError, zipfile.BadZipFile):
        return {}
    return _parse_csv_text(text) if text else {}


def _load_folder(kind: str) -> Dict[str, Dict[str, str]]:
    """Fichiers du dossier perso : tout CSV dont le nom correspond au type
    (Localization.csv / Dialogues.csv / PDA.csv). Le premier trouve gagne."""
    folder = _settings.get_corpus_trad_dir()
    if not folder:
        return {}
    root = Path(folder)
    if not root.is_dir():
        return {}
    for candidate in sorted(root.rglob("*.csv")):
        if detect_type(candidate) != kind:
            continue
        try:
            text = candidate.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        return _parse_csv_text(text)
    return {}


def corpus_index(kind: str) -> Dict[str, Dict[str, str]]:
    """Index cle -> {nom de colonne: valeur} pour ce type de corpus ; dossier
    perso d'abord (prioritaire), embarque en complement. Cache memoire."""
    index = _cache.get(kind)
    if index is None:
        index = _load_folder(kind)
        for key, values in _load_embedded(kind).items():
            index.setdefault(key, values)
        _cache[kind] = index
    return index


def lookup(kind: Optional[str], key: str) -> Optional[Dict[str, str]]:
    """Ligne du corpus pour cette cle (nom de colonne -> texte), ou None."""
    if not kind or not key:
        return None
    return corpus_index(kind).get(key.strip())


def fill_document(doc, kind: Optional[str]) -> List[Tuple[int, int]]:
    """Complete les cellules VIDES de `doc` (CsvDocument) depuis le corpus,
    par cle puis par NOM de colonne (les fichiers peuvent ne pas avoir les
    memes langues). Retourne les positions (ligne, colonne) remplies -- la
    table de l'editeur est reconstruite ensuite et doit re-marquer ces
    cellules.

    Mutateur : la table de l'editeur doit etre resynchronisee par l'appelant
    (rendre le document, cf. CsvEditWidget)."""
    if not kind or not doc.header:
        return []
    labels = [h.strip() for h in doc.header]
    filled: List[Tuple[int, int]] = []
    for r, row in enumerate(doc.rows):
        if not row or not row[0].strip():
            continue
        values = lookup(kind, row[0])
        if not values:
            continue
        for col in range(1, len(labels)):
            if col < len(row) and row[col].strip():
                continue
            text = values.get(labels[col])
            if not text:
                continue
            while len(row) <= col:
                row.append("")
            row[col] = text
            filled.append((r, col))
    return filled


def available(kind: Optional[str] = None) -> Dict[str, int]:
    """Nombre de cles disponibles par type (pour l'affichage du bouton)."""
    kinds = [kind] if kind else list(EMBEDDED_MEMBERS)
    return {k: len(corpus_index(k)) for k in kinds if k}


def clear_cache() -> None:
    """Vide le cache (tests, ou apres changement du dossier perso)."""
    _cache.clear()
