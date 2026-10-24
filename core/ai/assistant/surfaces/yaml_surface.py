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

"""Surface YAML (playfields, Sectors, presets) : contexte de l'entree
selectionnee, lecture du document VIVANT, changement `yaml_set`. Pur : prend
un YamlDocument, aucun Qt, aucun disque.

Contrat de cible : chemin pointe des cles de mapping, ex. `Playfield.Name`.
`old` doit etre la valeur actuelle exacte ; les items de sequence (sans cle)
ne sont pas adressables -- on le dit plutot que de deviner.
"""
import re
from typing import List, Optional, Tuple

from ....yamllite.model import YamlDocument, YamlEntry
from ..changeset import Change
from ..context import TabContext, build
from ..tools import Tool, ToolRegistry

SURFACE = "yaml"

INSTRUCTION = (
    "Active file: a YAML file. Targets are dotted key paths (e.g. "
    "'Playfield.Name'); send the exact current value in 'old'. Sequence "
    "items have no key and cannot be targeted. Use yaml_active_entries to "
    "see the live document (unsaved edits included).")


def parse_target(target: str) -> Optional[List[str]]:
    parts = [part.strip() for part in re.split(r"[./]", target or "")
             if part.strip()]
    return parts or None


def _child_entries(entry: YamlEntry) -> List[YamlEntry]:
    return [child for child in entry.children
            if isinstance(child, YamlEntry)]


def resolve(doc: YamlDocument, keys: List[str]) -> Tuple[Optional[YamlEntry],
                                                         str]:
    nodes = doc.nodes
    entry = None
    for key in keys:
        entry = next((node for node in nodes
                      if isinstance(node, YamlEntry) and node.key == key),
                     None)
        if entry is None:
            return None, "yaml_key_not_found"
        nodes = entry.children
    return entry, ""


def entry_path(doc: YamlDocument, target: YamlEntry) -> str:
    """Chemin pointe de cette entree (premiere occurrence par identite)."""
    def walk(nodes, stack):
        for node in nodes:
            if not isinstance(node, YamlEntry):
                continue
            path = stack + ([node.key] if node.key is not None else [])
            if node is target:
                return ".".join(path)
            found = walk(node.children, path)
            if found is not None:
                return found
        return None

    return walk(doc.nodes, []) or ""


def context(doc: YamlDocument, entry: Optional[YamlEntry],
            filename: str) -> TabContext:
    if entry is None:
        return build(filename, "")
    path = entry_path(doc, entry) or (entry.key or "?")
    children = _child_entries(entry)
    if not children:
        return build(f"{filename} {path}", entry.value)
    lines = [f"{path}: {entry.value}".rstrip()]
    lines.extend(f"  {child.key}: {child.value}" for child in children[:80])
    return build(f"{filename} {path}", "\n".join(lines))


def validate(doc: YamlDocument, changes: List[Change]) -> List[str]:
    problems: List[str] = []
    for change in changes:
        if change.kind != "yaml_set":
            problems.append("yaml_kind_unsupported")
            continue
        keys = parse_target(change.target)
        if keys is None:
            problems.append("yaml_target_invalid")
            continue
        entry, code = resolve(doc, keys)
        if entry is None:
            problems.append(code)
            continue
        if (entry.value or "") != (change.old or ""):
            problems.append("yaml_value_changed")
    return sorted(set(problems))


def apply(doc: YamlDocument, changes: List[Change]) -> int:
    written = 0
    for change in changes:
        if change.kind != "yaml_set":
            continue
        keys = parse_target(change.target)
        if keys is None:
            continue
        entry, _code = resolve(doc, keys)
        if entry is None:
            continue
        entry.set_own_value(change.new)
        written += 1
    return written


def registry(doc: YamlDocument) -> ToolRegistry:
    tools = ToolRegistry()
    tools.add(Tool(
        name="yaml_active_entries", surface=SURFACE, max_chars=6000,
        description="List the mapping entries of the ACTIVE YAML document "
                    "(unsaved edits included) with their dotted path.",
        parameters={"properties": {"limit": {"type": "integer"}},
                    "required": []},
        handler=lambda args: _active_entries(doc, args)))
    return tools


def _active_entries(doc: YamlDocument, args: dict) -> dict:
    try:
        limit = int((args or {}).get("limit") or 200)
    except (TypeError, ValueError):
        limit = 200
    limit = max(1, min(500, limit))
    rows: List[dict] = []

    def walk(nodes, stack):
        for node in nodes:
            if not isinstance(node, YamlEntry):
                continue
            path = stack + ([node.key] if node.key is not None else [])
            rows.append({"path": ".".join(path), "value": node.value})
            walk(node.children, path)

    walk(doc.nodes, [])
    if not rows:
        return {"entries": [], "note": "no entry in this YAML file"}
    return {"entries": rows[:limit], "count": len(rows),
            "truncated": len(rows) > limit}
