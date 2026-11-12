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

Ecriture (demande 12/11/2026) : une traduction VALIDEE par l'utilisateur est
archived dans le corpus perso (`remember_many`). Cle absente = ligne ajoutee ;
cle presente = seules ses cellules vides sont completees. Ce qui est ainsi
appris sur un scenario evite une traduction IA sur tous les suivants.
"""
from __future__ import annotations

import csv
import io
import time
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


def _repair_label(text: str) -> str:
    """En-tete lisible : `FranГ§ais` (UTF-8 relu en CP1251) -> `Français`.
    Les CSV d'origine russe portent le francais double-encode (vecu 12/09)."""
    from core import translation
    return translation.repair_mojibake((text or "").strip())


def _label_key(text: str) -> str:
    """Cle de comparaison d'un en-tete : mojibake repare, casse et accents
    ignores. `FranГ§ais` == `Français` == `FRANCAIS`."""
    from core import translation
    return translation._normalize(_repair_label(text))


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
    labels = [_repair_label(h) for h in header]
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
    root = personal_dir()
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
        by_key = {_label_key(label): value for label, value in values.items()}
        for col in range(1, len(labels)):
            if col < len(row) and row[col].strip():
                continue
            text = by_key.get(_label_key(labels[col]))
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


# ------------------------------------------------- ecriture du corpus perso

DEFAULT_HEADER = ["KEY", "English"]


def personal_dir() -> Path:
    """Dossier perso du corpus : le reglage, sinon `~/.empyrion_editor/corpus`
    (cree a la premiere ecriture seulement). Un dossier configure vide ne
    change rien a la lecture : le corpus embarque reste la base."""
    configured = _settings.get_corpus_trad_dir()
    if configured:
        return Path(configured)
    return Path.home() / ".empyrion_editor" / "corpus"


def personal_path(kind: str) -> Optional[Path]:
    """Fichier du dossier perso pour ce type : le CSV existant (quel que soit
    son sous-dossier), sinon le nom canonique du corpus embarque."""
    if kind not in EMBEDDED_MEMBERS:
        return None
    root = personal_dir()
    if root.is_dir():
        for candidate in sorted(root.rglob("*.csv")):
            if detect_type(candidate) == kind:
                return candidate
    return root / EMBEDDED_MEMBERS[kind]


def _read_table(path: Path, fallback_header=None):
    """(en-tetes, lignes) du CSV ; en-tetes de repli quand il n'existe pas."""
    labels = [_repair_label(h) for h in (fallback_header or DEFAULT_HEADER)]
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return labels, []
    reader = csv.reader(io.StringIO(text))
    rows = [list(r) for r in reader if any(c.strip() for c in r)]
    if not rows:
        return labels, []
    return [_repair_label(h) for h in rows[0]], rows[1:]


BACKUP_EVERY_SECONDS = 3600


def _recent_backup(path: Path) -> bool:
    """Une copie datee de ce fichier existe-t-elle depuis moins d'une heure ?
    Evite de dupliquer un CSV de plusieurs Mo a chaque traduction archivee."""
    folder = Path.home() / ".empyrion_editor" / "backups" / "corpus"
    try:
        return any(time.time() - p.stat().st_mtime < BACKUP_EVERY_SECONDS
                   for p in folder.glob(path.stem + "-*" + path.suffix + ".bak"))
    except OSError:
        return False


def _backup_before_write(path: Path, force: bool = False) -> None:
    """Copie datee avant ecriture, dans ~/.empyrion_editor/backups/corpus --
    jamais un `.bak` a cote du CSV (le dossier perso est relu : un voisin
    s'ajouterait au corpus comme un doublon).

    Un ECRASEMENT est toujours sauvegarde ; un simple ajout, au plus une fois
    par heure (un corpus de reference fait plusieurs Mo)."""
    if not path.is_file():
        return
    if not force and _recent_backup(path):
        return
    from core.fsutil import central_backup
    try:
        central_backup(path, "corpus")
    except OSError:
        pass                    # une sauvegarde ratee ne bloque pas l'ecriture


def _write_table(path: Path, labels: List[str], rows: List[List[str]]) -> None:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(labels)
    for row in rows:
        writer.writerow((list(row) + [""] * len(labels))[:len(labels)])
    from core.fsutil import atomic_write_text
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, out.getvalue())


def remember_many(kind: Optional[str], entries: Dict[str, Dict[str, str]],
                  header=None, overwrite: bool = False) -> Optional[Path]:
    """Archive des traductions VALIDEES dans le corpus perso, en un seul
    aller-retour disque.

    - cle absente : la ligne est **ajoutee** -- c'est la demande du 12/11 :
      une cle traduite une fois ne repart jamais vers l'IA sur un autre
      scenario ;
    - cle presente : seules les cellules **vides** sont completees, jamais
      d'ecrasement (meme contrat que `fill_document`) ;
    - une colonne de langue absente du fichier est ajoutee.

    `header` = en-tetes du fichier en cours d'edition, pour que le corpus
    naisse avec les memes colonnes. Retourne le fichier ecrit, ou None.
    """
    merged = {str(k).strip(): {_repair_label(c): v
                               for c, v in (vals or {}).items() if c and v}
              for k, vals in (entries or {}).items() if str(k).strip()}
    merged = {k: v for k, v in merged.items() if v}
    path = personal_path(kind) if kind else None
    if not merged or path is None:
        return None
    labels, rows = _read_table(path, header)
    changed = False
    for key, values in merged.items():
        for label in values:
            if label not in labels:
                labels.append(label)
                for row in rows:
                    row.extend([""] * (len(labels) - len(row)))
                changed = True
        row = next((r for r in rows if r and r[0].strip() == key), None)
        if row is None:
            row = [key] + [""] * (len(labels) - 1)
            rows.append(row)
            changed = True
        for label, text in values.items():
            col = labels.index(label)
            while len(row) <= col:
                row.append("")
            if overwrite or not row[col].strip():
                if row[col] != text:
                    row[col] = text
                    changed = True
    if not changed:
        return None
    _backup_before_write(path, force=overwrite)
    _write_table(path, labels, rows)
    clear_cache()
    return path


def harvest(kind: Optional[str], header, rows) -> Tuple[dict, dict]:
    """(entrees, bilan) des cellules remplies d'un fichier, SANS ecrire.

    Sert a l'action « Mettre a jour le corpus » : l'utilisateur voit combien
    de cles sont nouvelles, combien de cellules seront ajoutees et combien de
    valeurs **remplacees** (une correction manuelle ecrase la reference) avant
    de decider.
    """
    labels = [_repair_label(h) for h in (header or [])]
    entries: Dict[str, Dict[str, str]] = {}
    for row in rows or []:
        if not row or not str(row[0]).strip():
            continue
        values = {}
        for col in range(1, len(labels)):
            text = str(row[col]) if col < len(row) else ""
            if text.strip() and labels[col]:
                values[labels[col]] = text
        if values:
            entries[str(row[0]).strip()] = values
    known_index = corpus_index(kind) if kind else {}
    report = {"new_keys": 0, "added": 0, "changed": 0}
    for key, values in entries.items():
        known = known_index.get(key)
        if known is None:
            report["new_keys"] += 1
        known_by_label = {_label_key(label): value
                          for label, value in (known or {}).items()}
        for label, text in values.items():
            current = known_by_label.get(_label_key(label))
            if current is None:
                report["added"] += 1
            elif current != text:
                report["changed"] += 1
    return entries, report


def remember(kind: Optional[str], key: str, values: Dict[str, str],
             header=None) -> Optional[Path]:
    """Variante une cle de `remember_many`."""
    return remember_many(kind, {key: values}, header)


def clear_cache() -> None:
    """Vide le cache (tests, ou apres changement du dossier perso)."""
    _cache.clear()
