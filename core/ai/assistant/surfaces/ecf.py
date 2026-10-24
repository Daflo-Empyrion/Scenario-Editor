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

"""Surface ECF : outils de lecture, contexte, changements `ecf_set` et
`ecf_create_block`. Pur (aucun Qt, aucun disque) : le widget fournit le
document, applique apres validation et garde son propre undo.

Contrat de cible, rappele dans l'instruction et dans la sortie des outils :
« [<Id ou Name>] / <Propriete> », par exemple « [399] / Count ». La valeur
`old` doit etre EXACTEMENT celle du document : sinon la proposition est
refusee (le fichier a bouge depuis la lecture du modele).
"""
import re
from pathlib import Path
from typing import List, Optional, Tuple

from ....ecf.model import EcfBlock, EcfDocument, EcfProperty, block_identity
from ....ecf.parser import parse_ecf_text
from ..changeset import Change
from ..context import TabContext, build
from ..tools import Tool, ToolRegistry
from .base import arg

SURFACE = "ecf"

INSTRUCTION = (
    "Active file: an ECF file. The attached context already contains the "
    "selected block: call the tools only when you need more than it. Targets "
    "use the form '[<Id or Name>] / <Property>' (e.g. '[399] / Count'); copy "
    "the identifier exactly as the tools print it. To create a block, use "
    "kind 'ecf_create_block' with target = the opening line after '{' (kind "
    "and identity, e.g. 'Block Id: 500, Name: MyBlock') and new = the "
    "remaining 'Key: value' lines. Always send the exact current value in "
    "'old'. Identity properties (Id, Name, Ref) are read-only: never target "
    "them.")


_TARGET_RE = re.compile(
    r"^(?:[^\[\]/]+\.ecf\s*)?\[\s*(?P<ident>[^\]\s]+)[^\]]*\]\s*/\s*"
    r"(?P<key>\S.*)$", re.I)


def parse_target(target: str) -> Optional[Tuple[str, str]]:
    match = _TARGET_RE.match((target or "").strip())
    if not match:
        return None
    return match.group("ident").strip(), match.group("key").strip()


def _pairs_for(block: EcfBlock, key: str) -> List[Tuple[EcfProperty, int]]:
    out: List[Tuple[EcfProperty, int]] = []
    for child in block.children:
        if isinstance(child, EcfProperty):
            for index, (name, _value) in enumerate(child.pairs):
                if name == key:
                    out.append((child, index))
        elif isinstance(child, EcfBlock):
            out.extend(_pairs_for(child, key))
    return out


def find_block(doc: EcfDocument, ident: str):
    """(bloc, code) : un seul bloc portant cette identite, sinon code d'erreur."""
    wanted = (ident or "").strip()
    matches = [b for b in doc.iter_blocks()
               if wanted in {block_identity(b), b.get("Id"), b.get("Name"),
                             b.get("Ref")}]
    if not matches:
        return None, "ecf_block_not_found"
    if len(matches) > 1:
        return None, "ecf_block_ambiguous"
    return matches[0], ""


def _doc_eol(doc: EcfDocument) -> str:
    for node in doc.nodes:
        eol = getattr(node, "eol", None)
        if eol:
            return eol
    return "\n"


def _block_text(change: Change, eol: str) -> str:
    """Ligne d'ouverture = la cible telle quelle : c'est la que doivent se
    trouver le genre et l'identite (Id/Name), comme dans un ECF reel. Le
    bloc herite du separateur de ligne du document (pas de fichier mixte)."""
    header = (change.target or "").strip()
    body = eol.join((change.new or "").strip("\n").splitlines())
    return f"{{ {header}{eol}{body}{eol}}}{eol}"


def _build_block(doc: EcfDocument, change: Change) -> Optional[EcfBlock]:
    header = (change.target or "").strip()
    if not header or any(char in header for char in "{}\n"):
        return None
    if not (change.new or "").strip():
        return None
    try:
        parsed = parse_ecf_text(_block_text(change, _doc_eol(doc)))
    except Exception:  # noqa: BLE001 -- tout parse rate = bloc invalide
        return None
    blocks = [node for node in parsed.nodes if isinstance(node, EcfBlock)]
    if len(blocks) != 1:
        return None
    return blocks[0]


def validate(doc: EcfDocument, changes: List[Change]) -> List[str]:
    """Codes bloquants, liste vide = applicable. Tout ou rien."""
    problems: List[str] = []
    for change in changes:
        if change.kind == "ecf_set":
            problems.extend(_validate_set(doc, change))
        elif change.kind == "ecf_create_block":
            problems.extend(_validate_create(doc, change))
        else:
            problems.append("ecf_kind_unsupported")
    return sorted(set(problems))


def _validate_set(doc: EcfDocument, change: Change) -> List[str]:
    parsed = parse_target(change.target)
    if parsed is None:
        return ["ecf_target_invalid"]
    block, code = find_block(doc, parsed[0])
    if block is None:
        return [code]
    pairs = _pairs_for(block, parsed[1])
    if not pairs:
        return ["ecf_key_missing"]
    if len(pairs) > 1:
        return ["ecf_key_ambiguous"]
    prop, index = pairs[0]
    if (prop.pairs[index][1] or "") != (change.old or ""):
        return ["ecf_value_changed"]
    return []


def _validate_create(doc: EcfDocument, change: Change) -> List[str]:
    block = _build_block(doc, change)
    if block is None:
        return ["ecf_block_invalid"]
    ident = block_identity(block)
    if ident is None:
        return ["ecf_identity_missing"]
    for existing in doc.iter_blocks():
        if block_identity(existing) == ident:
            return ["ecf_duplicate_identity"]
    return []


def apply(doc: EcfDocument, changes: List[Change]) -> int:
    """Applique des changements DEJA valides ; retourne le nombre ecrit."""
    written = 0
    for change in changes:
        if change.kind == "ecf_set":
            parsed = parse_target(change.target)
            if parsed is None:
                continue
            block, _code = find_block(doc, parsed[0])
            if block is None:
                continue
            pairs = _pairs_for(block, parsed[1])
            if not pairs:
                continue
            prop, index = pairs[0]
            prop.pairs[index] = (prop.pairs[index][0], change.new)
            prop.dirty = True
            written += 1
        elif change.kind == "ecf_create_block":
            block = _build_block(doc, change)
            if block is not None:
                doc.nodes.append(block)
                written += 1
    return written


# ---------------------------------------------------------------------------
# Contexte et outils de lecture
# ---------------------------------------------------------------------------

def context(doc: EcfDocument, block: Optional[EcfBlock],
            filename: str) -> TabContext:
    if block is None:
        return build(filename, "")
    ident = block_identity(block) or "?"
    return build(f"{filename} [{ident}] {block.kind}", block.render())


def registry(doc: EcfDocument, path=None) -> ToolRegistry:
    tools = ToolRegistry()
    tools.add(Tool(
        name="ecf_list_blocks", surface=SURFACE, max_chars=3000,
        description="List the blocks of the active ECF file, optionally "
                    "filtered by kind. Returns kind, identifier and Name.",
        parameters={"properties": {"kind": {"type": "string"}},
                    "required": []},
        handler=lambda args: _list_blocks(
            doc, arg(args, "kind", "type", "genre"))))
    tools.add(Tool(
        name="ecf_read_block", surface=SURFACE, max_chars=6000,
        description="Read one block of the active ECF file by its Id or "
                    "Name, exactly as listed by ecf_list_blocks.",
        parameters={"properties": {"ident": {"type": "string"}},
                    "required": ["ident"]},
        handler=lambda args: _read_block(
            doc, arg(args, "ident", "id", "name", "block"))))
    tools.add(Tool(
        name="ecf_find_property", surface=SURFACE, max_chars=4000,
        description="Find every block that has a given property key, with "
                    "its current value. Identity properties on the opening "
                    "line (Id, Name, Ref) are listed with editable=false and "
                    "cannot be changed.",
        parameters={"properties": {"key": {"type": "string"},
                                  "kind": {"type": "string"}},
                    "required": ["key"]},
        handler=lambda args: _find_property(
            doc, arg(args, "key", "property", "prop", "name"),
            arg(args, "kind", "type"))))
    tools.add(Tool(
        name="ecf_validate", surface=SURFACE, max_chars=4000,
        description="Run the editor's own ECF validation on the active file "
                    "(same rules as the F5 check) and return its issues: "
                    "code, level, block, property, message.",
        parameters={"properties": {}, "required": []},
        handler=lambda args: _validate(doc, path)))
    return tools


def _validate(doc: EcfDocument, path) -> dict:
    from ....ecf.validation import validate_document

    try:
        issues = validate_document(doc, Path(path) if path else None)
    except Exception as e:  # noqa: BLE001 -- une regle fautive ne casse pas l'outil
        return {"error": f"validation failed: {type(e).__name__}: {e}"}
    rows = [{"code": issue.code, "level": issue.level,
             "block": issue.block.get("Id") or issue.block.get("Name")
             if issue.block is not None else None,
             "property": issue.property_key, "message": issue.message}
            for issue in issues[:60]]
    if not rows:
        return {"issues": [], "note": "no issue found by the built-in validation"}
    return {"issues": rows, "count": len(issues)}


def _list_blocks(doc: EcfDocument, kind: str) -> List[dict]:
    out = []
    for block in doc.iter_blocks(kind or None):
        out.append({"kind": block.kind, "ident": block_identity(block),
                    "name": block.get("Name")})
        if len(out) >= 150:
            out.append({"note": "list truncated to 150 blocks"})
            break
    if not out:
        return [{"note": f"no block of kind {kind!r}"
                         if kind else "no block in this file"}]
    return out


def _read_block(doc: EcfDocument, ident: str) -> str:
    if not ident:
        return ("missing parameter 'ident' (block Id or Name). "
                "Use ecf_list_blocks to get one.")
    block, code = find_block(doc, ident)
    if block is None:
        if code == "ecf_block_ambiguous":
            return (f"several blocks share the ident {ident!r}; "
                    "use a more precise Id.")
        return (f"no block with ident {ident!r}. Use the Id or the Name "
                "printed by ecf_list_blocks.")
    return block.render()


def _find_property(doc: EcfDocument, key: str, kind: str) -> List[dict]:
    """Cherche AUSSI sur la ligne d'ouverture (Id, Name, Ref...) : c'est la
    que vivent les identites, et un modele qui ne les voit pas conclut a tort
    « aucun bloc ne possede cette cle » (vecu 21/10). Ces proprietes sont
    signalees non modifiables : la cible d'un changement reste une propriete
    de corps, jamais une identite."""
    if not key:
        return [{"error":
                 "missing parameter 'key' (property name, e.g. Count)"}]
    out = []
    for block in doc.iter_blocks(kind or None):
        ident = block_identity(block)
        for name, value in block.pairs:
            if name == key:
                out.append({"kind": block.kind, "ident": ident,
                            "name": block.get("Name"), "key": key,
                            "value": value, "editable": False,
                            "where": "opening line"})
        for prop, index in _pairs_for(block, key):
            out.append({"kind": block.kind, "ident": ident,
                        "name": block.get("Name"), "key": key,
                        "value": prop.pairs[index][1], "editable": True})
        if len(out) >= 200:
            return out[:200]
    return out or [{"note": f"no block has the property {key!r}"}]
