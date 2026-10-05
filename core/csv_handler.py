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
Handler CSV, pour l'edition des fichiers de traduction Empyrion (Localization.csv,
PDA.csv, Dialogues.csv...).

Valide contre de vrais fichiers Empyrion (PDA.csv, 9267 lignes ; Dialogues.csv) --
round-trip parfait confirme. Un vrai bug trouve et corrige lors de cette
verification : voir _detect_dialect() ci-dessous pour le detail (doublequote mal
detecte par le Sniffer standard sur certains fichiers reels).
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
    """Detecte delimiteur/guillemets automatiquement -- MAIS force toujours
    doublequote=True quel que soit le resultat du Sniffer, meme quand celui-ci
    reussit sans lever d'erreur : confirme sur un vrai PDA.yaml/PDA.csv que le
    Sniffer peut detecter a tort doublequote=False sur un fichier qui utilise
    pourtant bel et bien l'echappement standard "" pour les guillemets
    imbriques (ex: une citation entre guillemets a l'interieur d'un texte de
    mission) -- sans ce correctif, un aller-retour casse silencieusement ces
    valeurs (guillemets dupliques a chaque sauvegarde). Meme categorie de
    defaillance deja connue et deja contournee pour has_header() ci-dessous."""
    sample = raw_text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = None
    # Le Sniffer choisit parfois quotechar=' sur les CSV Empyrion (a cause
    # des '' d'echappement des textes) — et tout le pipeline parse+render
    # derive alors dans ce dialecte : guillemets litteraux dans les
    # cellules, fichier re-ecrit illisible pour le jeu, cles brutes
    # partout dans le PDA (vecu 04-05/10, Vanilla EVO + Serveur-MP). Les
    # fichiers officiels (MP, Random EXP, base) sont tous en quoting
    # standard " : on FORCE donc quotechar/doublequote, seul le
    # delimiteur reste sniffe.
    if dialect is None:
        class _Default(csv.Dialect):
            delimiter = ','
            quotechar = '"'
            doublequote = True
            skipinitialspace = False
            lineterminator = '\r\n'
            quoting = csv.QUOTE_MINIMAL
        return _Default
    dialect.quotechar = '"'
    dialect.doublequote = True
    return dialect


def _detect_has_header(raw_text: str, dialect: csv.Dialect) -> bool:
    """Les fichiers CSV Empyrion (Localization.csv, PDA.csv, Dialogues.csv...) ont
    quasiment toujours une ligne d'en-tete (Key/EN/FR/DE...). L'heuristique de
    csv.Sniffer().has_header() s'est averee peu fiable sur de petits fichiers reels
    (rate des cas evidents) -- on suppose donc un en-tete present par defaut, ce qui
    correspond a la convention de ces fichiers."""
    return True


class _PdaDialect(csv.Dialect):
    """Dialecte VERIFIE des PDA.csv officiels (MP, Random EXP) : quoting
    standard. A FORCER sur ce fichier : le Sniffer y choisit quotechar=' '
    (a cause des '' d'echappement) et tout le pipeline parse+render derape
    alors (guillemets litteraux dans les cellules, fichier illisible pour
    le jeu, cles brutes partout dans le PDA — vecu 04-05/10)."""
    delimiter = ','
    quotechar = '"'
    doublequote = True
    skipinitialspace = False
    lineterminator = '\r\n'
    quoting = csv.QUOTE_MINIMAL


def parse_pda_csv_text(raw_text: str) -> CsvDocument:
    """Parse un PDA.csv avec le dialecte standard force (voir _PdaDialect)."""
    return parse_csv_text(raw_text, dialect=_PdaDialect())


def parse_csv_text(raw_text: str, dialect: Optional[csv.Dialect] = None) -> CsvDocument:
    lineterminator = _detect_lineterminator(raw_text)
    dialect = dialect if dialect is not None else _detect_dialect(raw_text)
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


def _game_safe_cell(cell: str) -> str:
    """Empyrion lit ses CSV ligne par ligne : un vrai retour a la ligne dans
    une cellule produit une cellule multi-lignes que le parseur du jeu ne
    resout plus (les cles concernees s'affichent brutes en jeu, vecu 21/09
    sur le PDA.csv de RE2 ATL). Convention du jeu et du vanille : le
    litteral \n dans la cellule, jamais de vrai retour."""
    return cell.replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n")


def unwrap_game_style_cell(cell: str) -> str:
    """Defait le dialecte « game-style » d'un cellule CSV Empyrion : texte
    enveloppe dans '...' avec apostrophes doublees ('') — tel que livre par
    certains fichiers de scenario (Random EXP, vecu 05/10). Ingere
    litteralement par le parseur standard, ce dialecte re-rendu tel quel
    rendait le fichier illisible pour le jeu (cles brutes partout dans le
    PDA). Signature non ambigue : commence ET finit par ', contient ''."""
    if len(cell) >= 3 and cell.startswith("'") and cell.endswith("'")             and "''" in cell:
        return cell[1:-1].replace("''", "'")
    return cell


def sanitize_pda_game_dialect(doc: CsvDocument) -> CsvDocument:
    """PDA.csv uniquement (le jeu attend le quoting standard — les fichiers
    officiels MP/Random EXP le prouvent) : defeait le dialecte game-style
    sur toutes les cellules. Retourne le doc pour chainer."""
    for row in doc.rows:
        for c, cell in enumerate(row):
            row[c] = unwrap_game_style_cell(cell)
    return doc


def render_csv(doc: CsvDocument) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=doc.delimiter, quotechar=doc.quotechar,
                         lineterminator=doc.lineterminator, quoting=doc.quoting)
    if doc.header is not None:
        writer.writerow([_game_safe_cell(c) for c in doc.header])
    writer.writerows([_game_safe_cell(c) for c in row] for row in doc.rows)
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


@dataclass
class CsvMergeChange:
    """Un changement propose par une fusion CSV (revision ligne par ligne,
    demande 26/09/2026 : la fusion CSV etait aveugle)."""
    key: str
    action: str          # 'added' | 'completed'
    detail: str          # colonnes completees ('' pour une ligne ajoutee)
    row: List[str]       # ligne source (rejouee a l'application)


def plan_csv_merge(working_doc: "CsvDocument",
                   incoming_doc: "CsvDocument") -> List[CsvMergeChange]:
    """Les changements que merge_csv_documents apporterait, SANS ecrire :
    une ligne de changement par ligne ajoutee ou completee (meme logique,
    meme priorite copie de travail)."""
    changes: List[CsvMergeChange] = []
    keys = {row[0] for row in working_doc.rows if row}
    for inc_row in incoming_doc.rows:
        if not inc_row:
            continue
        key = inc_row[0]
        if key not in keys:
            changes.append(CsvMergeChange(key=key, action="added",
                                          detail="", row=list(inc_row)))
            continue
        existing = next(r for r in working_doc.rows if r and r[0] == key)
        changed_cols = [c for c in range(max(len(existing), len(inc_row)))
                        if not (existing[c] if c < len(existing) else "").strip()
                        and (inc_row[c] if c < len(inc_row) else "").strip()]
        if changed_cols:
            cols = ", ".join(
                working_doc.header[c] if working_doc.header and c < len(working_doc.header)
                else str(c) for c in changed_cols)
            changes.append(CsvMergeChange(key=key, action="completed",
                                          detail=cols, row=list(inc_row)))
    return changes


def apply_csv_changes(working_doc: "CsvDocument",
                      changes: List[CsvMergeChange]) -> int:
    """Applique les changements COCHES au document (en memoire) via la
    meme logique que merge_single_csv_row ; retourne le nombre reellement
    applique ('added' ou 'merged', pas 'unchanged')."""
    applied = 0
    for change in changes:
        _, status = merge_single_csv_row(working_doc, change.row)
        if status != 'unchanged':
            applied += 1
    return applied
