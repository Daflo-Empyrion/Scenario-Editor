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
Recherche a travers TOUS les fichiers de la copie de travail d'un scenario
(pas un seul fichier ouvert) -- ECF, YAML, CSV. Reutilise les mecanismes de
navigation precise deja construits pour les fenetres de verification :
select_block_by_identity() pour ECF, select_entry_by_key_value() pour YAML
(voir gui/cross_reference_dialog.py, meme principe). Pour le CSV, aucun
mecanisme de selection de ligne n'existe actuellement dans l'application --
un resultat CSV ouvre simplement le fichier, sans naviguer jusqu'a la ligne
exacte (limitation connue, documentee plutot que masquee).
"""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .ecf.parser import parse_ecf_file
from .ecf.model import block_identity
from .ecf.cross_reference_check import _all_property_pairs
from .yamllite.parser import parse_yaml_file
from .csv_handler import parse_csv_text


@dataclass
class SearchResult:
    file_path: Path
    file_kind: str          # 'ecf', 'yaml', 'csv'
    match_context: str      # texte lisible pour la liste de resultats

    # ECF -- pour select_block_by_identity()
    identity: Optional[str] = None
    prop_key: Optional[str] = None
    prop_value: Optional[str] = None

    # YAML -- pour select_entry_by_key_value()
    entry_key: Optional[str] = None
    entry_value: Optional[str] = None


def _make_matcher(query: str, case_sensitive: bool = False, use_regex: bool = False):
    """Retourne une fonction de test (haystack -> bool) compilee UNE fois par
    recherche (pas une compilation ni une mise en minuscules par ligne testee).
    En mode regex, leve re.error si le motif est invalide -- l'appelant GUI
    intercepte pour afficher l'erreur a l'utilisateur ; les chercheurs directs
    (outils CLI, tests) peuvent laisser filer."""
    if use_regex:
        flags = 0 if case_sensitive else re.IGNORECASE
        pattern = re.compile(query, flags)
        return lambda haystack: bool(haystack) and pattern.search(haystack) is not None
    if case_sensitive:
        needle = query
        return lambda haystack: bool(haystack) and needle in haystack
    needle = query.lower()
    return lambda haystack: bool(haystack) and needle in haystack.lower()


def _truncate_context(text: str, max_len: int = 100) -> str:
    """Aplati les retours a la ligne et tronque -- une description de
    playfield peut faire plusieurs centaines de caracteres sur plusieurs
    lignes (confirme sur un vrai fichier), illisible telle quelle dans une
    liste de resultats."""
    flat = " ".join(text.split())
    if len(flat) > max_len:
        return flat[:max_len] + "..."
    return flat


def search_ecf_files(ecf_files: List[Path], query: str, case_sensitive: bool = False,
                     use_regex: bool = False) -> List[SearchResult]:
    """Cherche dans le genre, l'Id/Name et toutes les proprietes (y compris
    imbriquees, ex: Child Items) de chaque bloc -- _all_property_pairs()
    couvre deja les paires d'en-tete du bloc lui-meme (Id, Name, Kind), pas
    seulement les proprietes enfants, confirme contre de vraies donnees
    (recherche 'IronOre' -> trouve bien via la paire Name: IronOre de l'en-tete,
    pas seulement les Meshfile imbriques). Un seul resultat par bloc (la
    premiere correspondance trouvee) -- eviter d'inonder la liste si un meme
    terme apparait plusieurs fois dans un gros bloc."""
    results: List[SearchResult] = []
    match = _make_matcher(query, case_sensitive, use_regex)
    for path in ecf_files:
        try:
            doc = parse_ecf_file(path)
        except Exception:
            continue
        seen_blocks = set()
        for top_block, prop_node, key, value in _all_property_pairs(doc):
            block_id_python = id(top_block)
            if block_id_python in seen_blocks:
                continue
            haystack = f"{key or ''} {value or ''}"
            if match(haystack):
                identity = block_identity(top_block)
                results.append(SearchResult(
                    file_path=path, file_kind="ecf",
                    match_context=_truncate_context(f"{top_block.kind} {identity or '?'} -- {key}: {value}"),
                    identity=identity, prop_key=key, prop_value=value,
                ))
                seen_blocks.add(block_id_python)
    return results


def search_yaml_files(yaml_files: List[Path], query: str, case_sensitive: bool = False,
                      use_regex: bool = False) -> List[SearchResult]:
    results: List[SearchResult] = []
    match = _make_matcher(query, case_sensitive, use_regex)
    for path in yaml_files:
        try:
            doc = parse_yaml_file(path)
        except Exception:
            continue
        for entry in doc.iter_entries():
            haystack = f"{entry.key or ''} {entry.value or ''}"
            if match(haystack):
                results.append(SearchResult(
                    file_path=path, file_kind="yaml",
                    match_context=_truncate_context(f"{entry.key}: {entry.value}"),
                    entry_key=entry.key, entry_value=(entry.value or "").strip().strip('"').strip("'"),
                ))
    return results


def search_csv_files(csv_files: List[Path], query: str, case_sensitive: bool = False,
                     use_regex: bool = False) -> List[SearchResult]:
    """Aucune navigation precise vers la ligne exacte -- voir docstring de
    tete de module. Un resultat par ligne correspondante."""
    results: List[SearchResult] = []
    match = _make_matcher(query, case_sensitive, use_regex)
    for path in csv_files:
        try:
            raw = path.read_text(encoding="utf-8")
            doc = parse_csv_text(raw)
        except Exception:
            continue
        for row in doc.rows:
            row_text = " ".join(row)
            if match(row_text):
                snippet = row[0] if row else ""
                results.append(SearchResult(
                    file_path=path, file_kind="csv",
                    match_context=_truncate_context(f"{snippet} -- {row_text}"),
                ))
    return results


def search_scenario(ecf_files: List[Path], yaml_files: List[Path], csv_files: List[Path],
                     query: str, case_sensitive: bool = False,
                     use_regex: bool = False) -> List[SearchResult]:
    """Point d'entree unique -- combine les 3 recherches par type de fichier.
    use_regex=True interprete la requete comme une expression reguliere
    Python (leve re.error si invalide)."""
    if not query.strip():
        return []
    results = []
    results.extend(search_ecf_files(ecf_files, query, case_sensitive, use_regex))
    results.extend(search_yaml_files(yaml_files, query, case_sensitive, use_regex))
    results.extend(search_csv_files(csv_files, query, case_sensitive, use_regex))
    return results
