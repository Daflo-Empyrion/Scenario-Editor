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

"""Outils de lecture a l'echelle du scenario, A ET B COMPRIS.

Vecu 21/10 : question « ou est reference LightWeaponsSmall ? » -> le modele
ne voyait que le fichier actif, repondait « je n'ai pas de tool pour ouvrir
un fichier » et demandait a l'utilisateur de changer d'onglet. Ces outils
repondent sans changer d'onglet :

  - scenario_list_files   : inventaire (filtrable par motif de chemin) ;
  - scenario_find         : occurrence litterale, insensible a la casse,
                            dans .ecf/.yaml/.csv/.txt (c'est LA question
                            « ou est reference X ») ;
  - file_read             : fenetre de lignes numerotees d'un fichier ;
  - scenario_read_block   : un bloc ECF d'un autre fichier ;
  - catalog_search / yaml_list_entries / yaml_read_entry ;
  - scenario_merge_plan   : plan d'import d'un bloc, fichier ou dossier
                            depuis A/B (statut, dependances, changements
                            prets a recopier).

Chaque outil accepte `scope` : 'working' (defaut), 'a' ou 'b'. Vecu 22/10 :
l'assistant ne pouvait lister QUE la copie de travail et refusait donc de
preparer une fusion de bloc venue de B.

Tout est en LECTURE SEULE, confine a la racine choisie (aucun `..`, aucun
chemin absolu qui en sorte) et borne (taille de fichier, volume scanne,
nombre de resultats) : un outil ne doit jamais pouvoir aspirer un scenario
entier ni lire hors du dossier de travail. L'import lui-meme n'est jamais
un outil : c'est un ChangeSet (kind 'scenario_import') applique apres la
revue humaine.
"""
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ....ecf.parser import parse_ecf_file
from ....merge_dependencies import collect_sector_dependencies, plan_folder_merge
from ....scenario_import import block_plan
from ....yamllite.model import YamlEntry
from ....yamllite.parser import parse_yaml_file
from ..tools import Tool, ToolRegistry
from . import ecf as ecf_surface
from .base import arg

SEARCH_EXTENSIONS = (".ecf", ".yaml", ".yml", ".csv", ".txt", ".json")
MAX_FILES = 300
MAX_MATCHES = 80
MAX_SCAN_BYTES = 30_000_000
MAX_FILE_BYTES = 3_000_000
MAX_LINE_CHARS = 300

INSTRUCTION = (
    "You can read the whole scenario (read-only): scenario_list_files, "
    "scenario_find (literal text across .ecf/.yaml/.csv/.txt), file_read (line "
    "window of any file), scenario_read_block (one ECF block in another file), "
    "catalog_search (item/block technical name, category, market price) and "
    "yaml_list_entries / yaml_read_entry (structured YAML navigation). Paths "
    "are relative to the scenario root. Every tool accepts scope: 'working' "
    "(the working copy, default), 'a' or 'b' (read-only source scenarios).")

IMPORT_INSTRUCTION = (
    "To import a block, file or folder from A/B into the working copy, call "
    "scenario_merge_plan(source, path, ident?) FIRST: it returns the block "
    "status (added/merged/conflict), the full dependency tree (recipe, "
    "ingredients, Ref, tech tree parents, block groups, icons, localization), "
    "the unresolved references and ready-to-copy suggested_changes. Then "
    "return a change set whose "
    "rows use kind 'scenario_import' and target '<scope>:<relative path>"
    "[#<block Id or Name>]'. Copy the suggested_changes verbatim and do not "
    "invent paths. Copy the plan's unresolved list verbatim into a top-level "
    "\"report\" array (objects with type, reference, from, reason) so the "
    "user can export it as CSV. The tech tree is NOT imported: when the plan "
    "returns a 'techtree' object, always tell the user those parents/tabs "
    "must be added or updated in the working copy to finish the import. The "
    "user reviews every row, and nothing is written before that review.")


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _merge_plan(roots: Dict[str, Path], args: dict) -> dict:
    """Plan d'import A/B -> copie de travail, LECTURE SEULE. Le modele
    presente ce plan a l'utilisateur ; l'ecriture n'a lieu qu'apres la revue
    du ChangeSet (kind 'scenario_import')."""
    src_root, scope, problem = _pick(roots, args)
    if src_root is None:
        return {"error": problem}
    rel = arg(args, "path", "file", "folder").strip().replace("\\", "/")
    if not rel or rel.startswith("/") or ".." in rel.split("/"):
        return {"error": "missing or invalid parameter 'path' "
                         "(relative to the source scenario root)"}
    working = roots["working"]
    src = (src_root / rel).resolve()
    if not src.is_relative_to(src_root):
        return {"error": f"path {rel!r} is outside the source scenario"}
    if not src.exists():
        return {"error": f"not found in scenario {scope!r}: {rel!r}"}
    dest = working / rel
    ident = arg(args, "ident", "id", "name", "block")
    result: dict = {"source": scope, "path": rel, "dest_exists": dest.exists()}
    changes: List[dict] = []

    def change(target: str, new: str, reason: str) -> dict:
        return {"kind": "scenario_import", "target": target,
                "old": "present" if dest.exists() else "absent",
                "new": new, "reason": reason}

    if ident:
        if src.suffix.lower() != ".ecf":
            return {"error": "'ident' needs an .ecf file (got "
                             f"{src.suffix or 'no extension'})"}
        info = block_plan(src, dest, ident)
        if "error" in info:
            return info
        result.update(info)
        result["action"] = "import_block"
        # Resolution RECURSIVE : recette, ingredients, Ref, TechTreeParent,
        # BlockGroups, icones et localisation. Tout ce qui entre et tout ce
        # qui ne peut pas l'etre (report CSV cote revue).
        from ....ecf.dependencies import resolve
        from pathlib import PurePosixPath
        resolution = resolve(src_root, rel, ident, working)
        root_target = f"{rel}#{ident}"
        result["dependencies"] = [
            f"{entry['target']} ({entry['reason']})"
            for entry in resolution.imports
            if entry["target"] != root_target][:MAX_PLAN_FILES]
        result["import_count"] = len(resolution.imports)
        result["already_present_count"] = len(resolution.present)
        result["unresolved"] = [
            {"type": item.kind, "reference": item.ref,
             "from": f"{PurePosixPath(item.from_rel).name}#{item.from_ident}",
             "reason": item.reason}
            for item in resolution.unresolved[:MAX_PLAN_FILES]]
        if resolution.truncated:
            result["truncated"] = True
        parents = sorted({entry["parent"] for entry in resolution.techtree
                          if entry["parent"]})
        tabs = sorted({tab for entry in resolution.techtree
                       for tab in entry["tabs"]})
        if parents or tabs:
            result["techtree"] = {"parents": parents, "tabs": tabs}
        # UNE ligne a recopier : l'apply resout le graphe (+deps), sinon le
        # modele devrait recopier des dizaines de cibles (et se tromper).
        changes = [{
            "kind": "scenario_import",
            "target": f"{scope}:{rel}#{ident}+deps",
            "old": "absent",
            "new": f"block and {len(resolution.imports)} resolved target(s)",
            "reason": "import with dependencies"}]
    elif src.is_dir():
        plan = plan_folder_merge(src, src_root, working)
        result["action"] = "merge_folder"
        result["file_count"] = len(plan.files)
        result["files"] = [{"path": p.rel, "status": p.status,
                            "diff": p.diff_summary}
                           for p in plan.files[:MAX_PLAN_FILES]]
        if len(plan.files) <= MAX_PLAN_FILES:
            for p in plan.files:
                rel_ui = p.rel.replace("\\", "/")
                changes.append(change(f"{scope}:{rel_ui}", p.status,
                                      f"file from folder {rel}"))
        else:
            changes.append(change(f"{scope}:{rel}", "merge_folder",
                                  f"folder {rel} ({len(plan.files)} files)"))
        if plan.dependencies:
            result["dependencies"] = [{
                "source": _rel(src_root, d.source),
                "dest": _rel(working, d.dest),
                "reason": d.reason_i18n, "detail": d.detail}
                for d in plan.dependencies[:MAX_PLAN_FILES]]
            for d in plan.dependencies:
                changes.append(change(
                    f"{scope}:{_rel(src_root, d.source)}", "dependency",
                    f"dependency {d.detail} ({d.reason_i18n})"))
    else:
        suffix = src.suffix.lower()
        result["action"] = "merge_file"
        result["mode"] = ("ecf_merge" if dest.exists() and suffix == ".ecf"
                          else "csv_merge" if dest.exists() and suffix == ".csv"
                          else "copy")
        changes.append(change(f"{scope}:{rel}", result["mode"],
                              f"file from scenario {scope}"))
        if src.name.lower() == "sectors.yaml":
            deps = collect_sector_dependencies(src, src_root, working)
            if deps:
                result["dependencies"] = [{
                    "source": _rel(src_root, d.source),
                    "dest": _rel(working, d.dest),
                    "reason": d.reason_i18n, "detail": d.detail}
                    for d in deps[:MAX_PLAN_FILES]]
                for d in deps:
                    changes.append(change(
                        f"{scope}:{_rel(src_root, d.source)}", "dependency",
                        f"dependency {d.detail} ({d.reason_i18n})"))
    # Les changements EN TETE : si la sortie est coupee, le modele a encore
    # la ligne a recopier (le detail des dependances est indicatif).
    head = {"suggested_changes": changes[:MAX_PLAN_FILES]}
    if len(changes) > MAX_PLAN_FILES:
        head["suggested_truncated"] = len(changes) - MAX_PLAN_FILES
    head.update(result)
    return head


def _safe_path(root: Path, relative: str) -> Tuple[Optional[Path], str]:
    relative = (relative or "").strip().replace("\\", "/")
    if not relative:
        return None, "missing parameter 'path' (relative to the scenario root)"
    try:
        candidate = (root / relative).resolve()
        inside = candidate.is_relative_to(root.resolve())
    except (OSError, ValueError):
        return None, f"invalid path {relative!r}"
    if not inside:
        return None, f"path {relative!r} is outside the scenario"
    if not candidate.is_file():
        return None, f"file not found: {relative!r}"
    return candidate, ""


def _walk_files(root: Path) -> List[Path]:
    files: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for name in sorted(filenames):
            files.append(Path(dirpath) / name)
    return files


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _list_files(root: Path, pattern: str, limit: int = MAX_FILES) -> dict:
    files = _walk_files(root)
    if pattern:
        needle = pattern.lower()
        files = [p for p in files if needle in _rel(root, p).lower()]
    rows = [{"path": _rel(root, p), "size": _size(p)} for p in files[:limit]]
    result = {"count": len(files), "files": rows,
              "truncated": len(files) > limit}
    if not rows:
        result["note"] = (f"no file matching {pattern!r}" if pattern
                          else "empty scenario folder")
    return result


def _find(root: Path, text: str, extension: str) -> dict:
    if not (text or "").strip():
        return {"error": "missing parameter 'text'"}
    needle = text.lower()
    suffixes = SEARCH_EXTENSIONS
    if extension:
        suffix = extension.strip().lower()
        suffixes = (suffix if suffix.startswith(".") else "." + suffix,)
    matches: List[dict] = []
    scanned = 0
    files = 0
    truncated = False
    for path in _walk_files(root):
        if path.suffix.lower() not in suffixes:
            continue
        size = _size(path)
        if size > MAX_FILE_BYTES:
            continue
        if scanned + size > MAX_SCAN_BYTES:
            truncated = True
            break
        scanned += size
        files += 1
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                for number, line in enumerate(handle, 1):
                    if needle in line.lower():
                        matches.append({
                            "path": _rel(root, path), "line": number,
                            "text": line.strip()[:MAX_LINE_CHARS]})
                        if len(matches) >= MAX_MATCHES:
                            truncated = True
                            break
        except OSError:
            continue
        if truncated:
            break
    result = {"matches": matches, "files_searched": files}
    if truncated:
        result["note"] = "results truncated"
    if not matches:
        result["note"] = f"no occurrence of {text!r}"
    return result


def _read(root: Path, relative: str, start: int, count: int) -> dict:
    path, problem = _safe_path(root, relative)
    if path is None:
        return {"error": problem}
    start = max(1, int(start))
    count = max(1, min(400, int(count)))
    lines: List[dict] = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for number, line in enumerate(handle, 1):
                if number < start:
                    continue
                if number >= start + count:
                    break
                lines.append({"n": number,
                              "text": line.rstrip("\r\n")[:MAX_LINE_CHARS]})
    except OSError as e:
        return {"error": f"cannot read {relative!r}: {e}"}
    result = {"path": relative, "start": start, "lines": lines}
    if not lines:
        result["note"] = f"no line {start} in this file"
    return result


def _read_block(root: Path, relative: str, ident: str,
                cache: Dict[Path, object]) -> object:
    path, problem = _safe_path(root, relative)
    if path is None:
        return {"error": problem}
    if path.suffix.lower() != ".ecf":
        return {"error": f"{relative!r} is not an ECF file"}
    if not ident:
        return {"error": "missing parameter 'ident' (block Id or Name)"}
    doc = cache.get(path)
    if doc is None:
        try:
            doc = parse_ecf_file(path)
        except Exception as e:  # noqa: BLE001 -- fichier illisible = reponse
            return {"error": f"cannot parse {relative!r}: {e}"}
        cache[path] = doc
    block, _code = ecf_surface.find_block(doc, ident)
    if block is None:
        return {"error": f"no block with ident {ident!r} in {relative!r}"}
    return block.render()


MAX_PLAN_FILES = 20


def _roots(root, extra_roots) -> Dict[str, Path]:
    """Racines lisibles par les outils : 'working' toujours, plus 'a' et 'b'
    quand le projet est ouvert en mode fusion."""
    roots = {"working": Path(root).resolve()}
    for name, path in (extra_roots or {}).items():
        if path:
            roots[str(name).lower()] = Path(path).resolve()
    return roots


def _scopes(roots: Dict[str, Path]) -> list:
    return sorted(roots)


def _pick(roots: Dict[str, Path], args: dict):
    """(root, scope, probleme). Defaut = copie de travail : une question sans
    scope ne doit jamais basculer silencieusement sur un scenario source."""
    scope = arg(args, "scope", "source", "scenario").strip().lower()
    if not scope:
        scope = "working"
    found = roots.get(scope)
    if found is None:
        return None, scope, (f"unknown scope {scope!r} "
                             f"(available: {', '.join(_scopes(roots))})")
    return found, scope, ""


def _with_scope(pick, args, handler):
    root, _scope, problem = pick(args)
    if root is None:
        return {"error": problem}
    return handler(root)


def add_tools(tools: ToolRegistry, root, surface: str,
              extra_roots: Optional[Dict[str, Path]] = None) -> None:
    """Enregistre les outils de lecture sous le nom de la surface active
    (seuls ceux de la surface courante sont envoyes au modele). `extra_roots`
    ajoute les scenarios A/B : sans eux, le modele ne voit que la copie de
    travail (vecu 22/10 : impossible de lister les dependances d'un bloc de
    B avant de le fusionner)."""
    roots = _roots(root, extra_roots)
    scope_prop = {"type": "string", "enum": _scopes(roots)}
    cache: Dict[Path, object] = {}

    def pick(args):
        return _pick(roots, args)

    tools.add(Tool(
        name="scenario_list_files", surface=surface, max_chars=6000,
        description="List the files of a scenario (read-only), optionally "
                    "filtered by a substring of their path. scope='working' "
                    "(default), 'a' or 'b'.",
        parameters={"properties": {"pattern": {"type": "string"},
                                  "scope": scope_prop},
                    "required": []},
        handler=lambda args: _with_scope(
            pick, args, lambda r: _list_files(r, arg(args, "pattern", "filter",
                                                     "glob")))))
    tools.add(Tool(
        name="scenario_find", surface=surface, max_chars=6000,
        description="Find a literal text (case-insensitive) in every .ecf, "
                    ".yaml, .csv and .txt of a scenario. Returns file, line "
                    "number and the line. Use it for 'where is X referenced'. "
                    "scope='working' (default), 'a' or 'b'.",
        parameters={"properties": {"text": {"type": "string"},
                                  "extension": {"type": "string"},
                                  "scope": scope_prop},
                    "required": ["text"]},
        handler=lambda args: _with_scope(
            pick, args, lambda r: _find(r, arg(args, "text", "query", "q"),
                                        arg(args, "extension", "ext", "type")))))
    tools.add(Tool(
        name="file_read", surface=surface, max_chars=6000,
        description="Read a window of numbered lines from any file of a "
                    "scenario (path relative to the scenario root; "
                    "scope='working', 'a' or 'b').",
        parameters={"properties": {"path": {"type": "string"},
                                  "start": {"type": "integer"},
                                  "count": {"type": "integer"},
                                  "scope": scope_prop},
                    "required": ["path"]},
        handler=lambda args: _with_scope(
            pick, args, lambda r: _read(
                r, arg(args, "path", "file"),
                _int(args, ("start", "offset", "from"), 1),
                _int(args, ("count", "limit", "lines"), 120)))))
    tools.add(Tool(
        name="scenario_read_block", surface=surface, max_chars=6000,
        description="Read one ECF block (by Id or Name) from an ECF file of a "
                    "scenario, without opening it (scope='working', 'a' or "
                    "'b').",
        parameters={"properties": {"path": {"type": "string"},
                                  "ident": {"type": "string"},
                                  "scope": scope_prop},
                    "required": ["path", "ident"]},
        handler=lambda args: _with_scope(
            pick, args, lambda r: _read_block(
                r, arg(args, "path", "file"),
                arg(args, "ident", "id", "name", "block"), cache))))
    tools.add(Tool(
        name="catalog_search", surface=surface, max_chars=5000,
        description="Search the item/block catalog (ItemsConfig.ecf and "
                    "BlocksConfig.ecf of a scenario) by technical name or "
                    "category. Returns name, source (item/block), category "
                    "and market price. scope='working' (default), 'a' or 'b'.",
        parameters={"properties": {"text": {"type": "string"},
                                  "limit": {"type": "integer"},
                                  "scope": scope_prop},
                    "required": []},
        handler=lambda args: _with_scope(
            pick, args, lambda r: _catalog(
                r, arg(args, "text", "query", "q", "name"),
                _int(args, ("limit", "count", "max"), 30)))))
    tools.add(Tool(
        name="yaml_list_entries", surface=surface, max_chars=6000,
        description="List the mapping entries of a YAML file of a scenario "
                    "with their dotted path ('Sectors.HomeSystem.Name'). "
                    "Sequence items are shown as '[]'. scope='working', 'a' "
                    "or 'b'.",
        parameters={"properties": {"path": {"type": "string"},
                                  "limit": {"type": "integer"},
                                  "scope": scope_prop},
                    "required": ["path"]},
        handler=lambda args: _with_scope(
            pick, args, lambda r: _yaml_entries(
                r, arg(args, "path", "file"),
                _int(args, ("limit", "count", "max"), 200)))))
    tools.add(Tool(
        name="yaml_read_entry", surface=surface, max_chars=5000,
        description="Read one YAML entry by its dotted key path (e.g. "
                    "'Playfield.Name'); returns its value and direct "
                    "children when it is a mapping. scope='working', 'a' or "
                    "'b'.",
        parameters={"properties": {"path": {"type": "string"},
                                  "keys": {"type": "string"},
                                  "scope": scope_prop},
                    "required": ["path", "keys"]},
        handler=lambda args: _with_scope(
            pick, args, lambda r: _yaml_read(
                r, arg(args, "path", "file"),
                arg(args, "keys", "key", "entry", "path_keys")))))
    sources = [s for s in _scopes(roots) if s != "working"]
    if sources:
        tools.add(Tool(
            name="scenario_merge_plan", surface=surface, max_chars=9000,
            description="Plan an import from a source scenario into the "
                        "working copy, read-only. source='a' or 'b'; path is "
                        "relative to that source. With ident (a block Id or "
                        "Name in an .ecf file) it reports the block status "
                        "(added/merged/conflict), the source files that "
                        "reference it and the suggested_changes to copy into "
                        "the change set. Without ident it plans a whole file "
                        "or folder, including the editor's own dependencies "
                        "(playfields, POIs).",
            parameters={"properties": {"source": {"type": "string",
                                                 "enum": sources},
                                      "path": {"type": "string"},
                                      "ident": {"type": "string"}},
                        "required": ["source", "path"]},
            handler=lambda args: _merge_plan(roots, args)))


def _catalog(root: Path, text: str, limit: int) -> dict:
    # build_catalog et non load_catalog : ce dernier ecrit un cache disque
    # (~/.empyrion_editor), or un outil de lecture ne doit rien ecrire.
    from ....item_catalog import build_catalog

    paths = [p for p in _walk_files(root)
             if p.name in ("ItemsConfig.ecf", "BlocksConfig.ecf")]
    if not paths:
        return {"note": "ItemsConfig.ecf / BlocksConfig.ecf not found in this "
                        "scenario"}
    needle = (text or "").strip().lower()
    limit = max(1, min(100, limit))
    matches = [{"name": entry.name, "source": entry.source,
                "category": entry.category,
                "market_price": entry.market_price}
               for entry in build_catalog(paths)
               if not needle or needle in entry.name.lower()
               or needle in (entry.category or "").lower()]
    if not matches:
        return {"note": f"no catalog entry matching {text!r}"}
    return {"entries": matches[:limit], "count": len(matches),
            "truncated": len(matches) > limit}


def _yaml_doc(root: Path, relative: str) -> Tuple[Optional[object], str]:
    path, problem = _safe_path(root, relative)
    if path is None:
        return None, problem
    try:
        return parse_yaml_file(path), ""
    except Exception as e:  # noqa: BLE001 -- YAML illisible = reponse
        return None, f"cannot parse {relative!r}: {e}"


def _yaml_entries(root: Path, relative: str, limit: int) -> dict:
    doc, problem = _yaml_doc(root, relative)
    if doc is None:
        return {"error": problem}
    limit = max(1, min(500, limit))
    rows: List[dict] = []

    def walk(nodes, stack):
        for node in nodes:
            if not isinstance(node, YamlEntry):
                continue
            if node.key is not None:
                path = ".".join(stack + [node.key])
                rows.append({"path": path, "value": node.value})
                walk(node.children, stack + [node.key])
            else:
                rows.append({"path": ".".join(stack + ["[]"]),
                             "value": node.value})
                walk(node.children, stack + ["[]"])

    walk(doc.nodes, [])
    if not rows:
        return {"entries": [], "note": "no entry in this YAML file"}
    return {"entries": rows[:limit], "count": len(rows),
            "truncated": len(rows) > limit}


def _yaml_read(root: Path, relative: str, keys: str) -> dict:
    doc, problem = _yaml_doc(root, relative)
    if doc is None:
        return {"error": problem}
    parts = [part.strip() for part in re.split(r"[./]", keys or "")
             if part.strip()]
    if not parts:
        return {"error": "missing parameter 'keys' (e.g. Playfield.Name)"}
    nodes = doc.nodes
    entry = None
    for depth, key in enumerate(parts):
        entry = next((node for node in nodes
                      if isinstance(node, YamlEntry) and node.key == key),
                     None)
        if entry is None:
            return {"error": f"key {key!r} not found "
                             f"(resolved: {'.'.join(parts[:depth]) or '<root>'})"}
        nodes = entry.children
    children = [{"key": child.key, "value": child.value}
                for child in entry.children if isinstance(child, YamlEntry)]
    result = {"path": ".".join(parts), "value": entry.value}
    if children:
        result["children"] = children[:100]
    return result


def _int(args: dict, names, default: int) -> int:
    for name in names:
        try:
            return int((args or {}).get(name))
        except (TypeError, ValueError):
            continue
    return default
