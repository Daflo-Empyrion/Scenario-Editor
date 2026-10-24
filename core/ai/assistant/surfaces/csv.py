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

"""Surface CSV (dialogues, PDA, localisation) : lecture des lignes et
changement `csv_set`. Pur : prend l'en-tete et les lignes, aucun Qt.

Contrat de cible : « [<ligne>] / <Colonne> » ou la ligne est celle affichee
dans le tableau (premiere ligne de donnees = 1) et la colonne son en-tete
exact. `old` doit etre la valeur ACTUELLE : sinon la proposition est refusee.
"""
import re
from typing import List, Optional, Tuple

from ..changeset import Change
from ..context import TabContext, build
from ..tools import Tool, ToolRegistry
from .base import arg

SURFACE = "csv"

INSTRUCTION = (
    "Active file: a CSV table (dialogues, PDA missions, localization...). "
    "The attached context already contains the selected row: call the tools "
    "only when you need more than it. Targets use the form '[<line>] / "
    "<Column>' with the line number shown in the table (first data line = 1) "
    "and the exact column header. Send the exact current cell in 'old'.")

_TARGET_RE = re.compile(
    r"^(?:[^\[\]/]+\.csv\s*)?\[\s*(?P<row>\d+)[^\]]*\]\s*/\s*(?P<col>\S.*)$",
    re.I)



def arg_int(args: dict, names, default: int) -> int:
    for name in names:
        try:
            return int((args or {}).get(name))
        except (TypeError, ValueError):
            continue
    return default


def parse_target(target: str) -> Optional[Tuple[int, str]]:
    match = _TARGET_RE.match((target or "").strip())
    if not match:
        return None
    return int(match.group("row")), match.group("col").strip()


def _cell(rows: List[List[str]], row: int, col: int) -> str:
    if row >= len(rows):
        return ""
    values = rows[row]
    return values[col] if col < len(values) else ""


def _column(header: List[str], name: str) -> Optional[int]:
    for index, title in enumerate(header or []):
        if title == name:
            return index
    return None


def validate(header: List[str], rows: List[List[str]],
             changes: List[Change]) -> List[str]:
    problems: List[str] = []
    for change in changes:
        if change.kind != "csv_set":
            problems.append("csv_kind_unsupported")
            continue
        parsed = parse_target(change.target)
        if parsed is None:
            problems.append("csv_target_invalid")
            continue
        line, column_name = parsed
        if line < 1 or line > len(rows):
            problems.append("csv_row_out")
            continue
        column = _column(header, column_name)
        if column is None:
            problems.append("csv_column_unknown")
            continue
        if _cell(rows, line - 1, column) != (change.old or ""):
            problems.append("csv_value_changed")
    return sorted(set(problems))


def apply(header: List[str], rows: List[List[str]],
          changes: List[Change]) -> int:
    """Applique des changements DEJA valides ; retourne le nombre ecrit."""
    written = 0
    for change in changes:
        if change.kind != "csv_set":
            continue
        parsed = parse_target(change.target)
        if parsed is None:
            continue
        line, column_name = parsed
        column = _column(header, column_name)
        if column is None:
            continue
        row = rows[line - 1]
        while len(row) <= column:
            row.append("")
        row[column] = change.new
        written += 1
    return written


def context(filename: str, header: List[str], rows: List[List[str]],
            row: int, column: int) -> TabContext:
    if row < 0 or column < 0 or row >= len(rows):
        return build(filename, "")
    titles = header or [str(i + 1) for i in range(len(rows[row]))]
    lines = [f"ligne {row + 1} :"]
    for index, title in enumerate(titles):
        if index < len(rows[row]):
            lines.append(f"  {title} = {rows[row][index]}")
    return build(f"{filename} ligne {row + 1} / {titles[column]}",
                 "\n".join(lines))


def registry(header: List[str], rows: List[List[str]]) -> ToolRegistry:
    tools = ToolRegistry()
    tools.add(Tool(
        name="csv_read_rows", surface=SURFACE, max_chars=5000,
        description="Read the header and a window of rows from the active "
                    "CSV table. Lines are numbered as shown in the table.",
        parameters={"properties": {"start": {"type": "integer"},
                                  "count": {"type": "integer"}},
                    "required": []},
        handler=lambda args: _read_rows(
            header, rows,
            arg_int(args, ("start", "offset", "from"), 1),
            arg_int(args, ("count", "limit", "lines"), 40))))
    tools.add(Tool(
        name="csv_find", surface=SURFACE, max_chars=4000,
        description="Find rows whose cells contain the given text, in every "
                    "column or only one.",
        parameters={"properties": {"text": {"type": "string"},
                                  "column": {"type": "string"}},
                    "required": ["text"]},
        handler=lambda args: _find(
            header, rows, arg(args, "text", "query", "q", "search"),
            arg(args, "column", "col", "field"))))
    return tools


def _read_rows(header: List[str], rows: List[List[str]], start: int,
               count: int) -> dict:
    start = max(1, int(start))
    count = max(1, min(200, int(count)))
    window = []
    for line in range(start, min(len(rows), start - 1 + count) + 1):
        window.append({"line": line, "cells": _as_dict(header, rows[line - 1])})
    result = {"columns": list(header or []), "total_lines": len(rows),
              "rows": window}
    if not window:
        result["note"] = (f"no row at line {start}; the table has "
                          f"{len(rows)} line(s)")
    return result


def _find(header: List[str], rows: List[List[str]], text: str,
          column: str) -> List[dict]:
    if not text:
        return [{"error": "missing parameter 'text'"}]
    if column and _column(header, column) is None:
        return [{"error": f"unknown column {column!r}",
                 "columns": list(header or [])}]
    needle = text.lower()
    out = []
    for index, values in enumerate(rows):
        cells = _as_dict(header, values)
        scope = [cells.get(column)] if column else list(cells.values())
        if any(needle in str(value or "").lower() for value in scope):
            out.append({"line": index + 1, "cells": cells})
            if len(out) >= 60:
                break
    return out or [{"note": f"no row contains {text!r}"}]


def _as_dict(header: List[str], values: List[str]) -> dict:
    titles = header or [str(i + 1) for i in range(len(values))]
    return {titles[i]: values[i] for i in range(min(len(titles), len(values)))}
