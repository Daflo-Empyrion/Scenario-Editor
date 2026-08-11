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
from typing import List, Optional

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
