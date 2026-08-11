"""
Handler CSV, pour l'edition des fichiers de traduction Empyrion (Localization.csv,
PDA.csv, Dialogues.csv...).

IMPORTANT -- contrairement au parser ECF (valide sur 240+ fichiers reels) et au parser
YAML (valide sur 561 fichiers reels), ce handler n'a pas encore ete teste sur un vrai
fichier CSV Empyrion. Il utilise le module 'csv' standard de Python, avec detection
automatique du delimiteur (virgule, point-virgule...) et du style de fin de ligne
(CRLF/LF). A VALIDER avec verifier_parser_csv.py sur tes vrais fichiers avant de lui
faire confiance pour de l'edition reelle -- meme demarche que pour l'ECF et le YAML.
"""
import csv
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from .file_handlers import FileHandler


@dataclass
class CsvDocument:
    header: Optional[List[str]]
    rows: List[List[str]]
    delimiter: str = ","
    quotechar: str = '"'
    lineterminator: str = "\r\n"
    quoting: int = csv.QUOTE_MINIMAL


def _detect_lineterminator(raw_text: str) -> str:
    return "\r\n" if "\r\n" in raw_text else "\n"


def _detect_dialect(raw_text: str) -> csv.Dialect:
    sample = raw_text[:4096]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        class _Default(csv.Dialect):
            delimiter = ','
            quotechar = '"'
            doublequote = True
            skipinitialspace = False
            lineterminator = '\r\n'
            quoting = csv.QUOTE_MINIMAL
        return _Default


def _detect_has_header(raw_text: str, dialect: csv.Dialect) -> bool:
    """Les fichiers CSV Empyrion (Localization.csv, PDA.csv, Dialogues.csv...) ont
    quasiment toujours une ligne d'en-tete (Key/EN/FR/DE...). L'heuristique de
    csv.Sniffer().has_header() s'est averee peu fiable sur de petits fichiers reels
    (rate des cas evidents) -- on suppose donc un en-tete present par defaut, ce qui
    correspond a la convention de ces fichiers."""
    return True


def parse_csv_text(raw_text: str) -> CsvDocument:
    lineterminator = _detect_lineterminator(raw_text)
    dialect = _detect_dialect(raw_text)
    has_header = _detect_has_header(raw_text, dialect)

    reader = csv.reader(io.StringIO(raw_text), dialect)
    all_rows = list(reader)
    if all_rows and all_rows[-1] == []:
        all_rows.pop()

    header = all_rows[0] if (has_header and all_rows) else None
    rows = all_rows[1:] if header is not None else all_rows

    return CsvDocument(
        header=header, rows=rows,
        delimiter=dialect.delimiter, quotechar=dialect.quotechar,
        lineterminator=lineterminator, quoting=dialect.quoting,
    )


def render_csv(doc: CsvDocument) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=doc.delimiter, quotechar=doc.quotechar,
                         lineterminator=doc.lineterminator, quoting=doc.quoting)
    if doc.header is not None:
        writer.writerow(doc.header)
    writer.writerows(doc.rows)
    return buf.getvalue()


class CsvHandler(FileHandler):
    extensions = ('.csv',)

    def load(self, path: Path) -> str:
        with open(path, 'rb') as f:
            raw = f.read()
        return raw.decode('utf-8-sig')

    def parse(self, raw: str) -> CsvDocument:
        return parse_csv_text(raw)

    def serialize(self, ast: CsvDocument) -> str:
        return render_csv(ast)


def merge_csv_documents(working_doc: CsvDocument, incoming_doc: CsvDocument) -> "Tuple[CsvDocument, List[str]]":
    """
    Fusionne deux documents CSV par cle (1ere colonne) : la copie de travail est
    TOUJOURS prioritaire -- une ligne dont la cle existe deja n'est jamais ecrasee,
    seules les CELLULES VIDES sont completees depuis la source (meme philosophie que
    la fusion ECF en mode 'properties'). Les lignes dont la cle est absente de la copie
    de travail sont ajoutees telles quelles.

    Retourne (document_fusionne, rapport_des_changements -- une ligne de texte par
    ligne ajoutee ou completee).
    """
    report: List[str] = []
    merged_rows = [list(row) for row in working_doc.rows]
    key_to_index = {row[0]: i for i, row in enumerate(merged_rows) if row}

    for inc_row in incoming_doc.rows:
        if not inc_row:
            continue
        key = inc_row[0]
        if key not in key_to_index:
            merged_rows.append(list(inc_row))
            key_to_index[key] = len(merged_rows) - 1
            report.append(f"+ {key} (nouvelle ligne)")
        else:
            idx = key_to_index[key]
            existing_row = merged_rows[idx]
            new_row = list(existing_row)
            changed_cols = []
            for c in range(max(len(existing_row), len(inc_row))):
                existing_val = existing_row[c] if c < len(existing_row) else ""
                inc_val = inc_row[c] if c < len(inc_row) else ""
                if not existing_val.strip() and inc_val.strip():
                    while len(new_row) <= c:
                        new_row.append("")
                    new_row[c] = inc_val
                    changed_cols.append(c)
            if changed_cols:
                merged_rows[idx] = new_row
                col_names = [working_doc.header[c] if working_doc.header and c < len(working_doc.header) else str(c)
                             for c in changed_cols]
                report.append(f"~ {key} (complete : {', '.join(col_names)})")

    merged_doc = CsvDocument(
        header=working_doc.header, rows=merged_rows,
        delimiter=working_doc.delimiter, quotechar=working_doc.quotechar,
        lineterminator=working_doc.lineterminator, quoting=working_doc.quoting,
    )
    return merged_doc, report


def merge_single_csv_row(working_doc: CsvDocument, row: List[str]) -> "Tuple[CsvDocument, str]":
    """Fusionne UNE SEULE ligne (par cle) dans un document CSV deja charge -- meme
    logique que merge_csv_documents (complete les cellules vides, jamais d'ecrasement).
    Retourne (document_modifie, statut) ou statut vaut 'added', 'merged', ou 'unchanged'."""
    if not row:
        return working_doc, 'unchanged'
    key = row[0]
    for i, existing_row in enumerate(working_doc.rows):
        if existing_row and existing_row[0] == key:
            new_row = list(existing_row)
            changed = False
            for c in range(max(len(existing_row), len(row))):
                existing_val = existing_row[c] if c < len(existing_row) else ""
                inc_val = row[c] if c < len(row) else ""
                if not existing_val.strip() and inc_val.strip():
                    while len(new_row) <= c:
                        new_row.append("")
                    new_row[c] = inc_val
                    changed = True
            if changed:
                working_doc.rows[i] = new_row
                return working_doc, 'merged'
            return working_doc, 'unchanged'
    working_doc.rows.append(list(row))
    return working_doc, 'added'
