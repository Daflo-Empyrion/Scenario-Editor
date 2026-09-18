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
Progression de traduction d'un scenario (v1.8.0, demande du backlog) :
comptage cellules traduites / a traduire par CSV, pour le tableau de bord.
Lecture seule, tolerant aux fichiers corrompus (ignores) ; les CSV sans
colonnes de langue reconnues sont tout simplement exclus du bilan.
"""
from pathlib import Path
from typing import List, Optional, Tuple

from .csv_handler import CsvHandler, parse_csv_text
from .translation import COMMON_LANGUAGES, find_language_aliases

_LABELS = {code: label for label, code in COMMON_LANGUAGES}


def csv_translation_progress(csv_path: Path, target: str = "fr",
                             source: str = "en") -> Optional[Tuple[int, int]]:
    """(cellules_traduites, cellules_a_traduire) pour source -> target sur un
    CSV de langue, ou None si le fichier n'a pas les deux colonnes, si la
    lecture echoue ou si rien n'est a traduire. Une cellule est traduite
    des que la colonne cible est non vide ; une cellule est a traduire des
    que la colonne source est non vide."""
    try:
        raw = CsvHandler().load(Path(csv_path))
        doc = parse_csv_text(raw)
    except Exception:
        return None
    if not doc.header:
        return None
    norm_header = [h for h in doc.header]

    def _col(code: str) -> Optional[int]:
        aliases = find_language_aliases(code, _LABELS.get(code, code))
        for i, h in enumerate(norm_header):
            if h.strip() and h.strip() in aliases:
                return i
        return None

    src_col = _col(source)
    tgt_col = _col(target)
    if src_col is None or tgt_col is None or src_col == tgt_col:
        return None
    total = done = 0
    for row in doc.rows:
        src = row[src_col] if src_col < len(row) else ""
        tgt = row[tgt_col] if tgt_col < len(row) else ""
        if src.strip():
            total += 1
            if tgt.strip():
                done += 1
    if not total:
        return None
    return done, total


def scenario_translation_progress(csv_paths: List[Path], target: str = "fr",
                                  source: str = "en") -> List[Tuple[str, int, int]]:
    """Bilan par fichier pour le tableau de bord : [(chemin, traduites,
    a_traduire)] dans l'ordre des chemins fournis, fichiers sans colonnes
    de langue (ou illisibles) exclus."""
    out: List[Tuple[str, int, int]] = []
    for path in csv_paths:
        res = csv_translation_progress(path, target=target, source=source)
        if res is not None:
            out.append((str(path), res[0], res[1]))
    return out
