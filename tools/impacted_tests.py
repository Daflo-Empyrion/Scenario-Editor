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

"""Selection des TESTS IMPACTES par les fichiers modifies du working tree.

Pourquoi : la suite complete fait ~19 min ; pendant un chantier on veut
valider vite, la suite complete reste OBLIGATOIRE avant commit (regle
projet). Cet outil est un filet INTERMEDIAIRE, pas un remplacement.

Comment (zero dependance, tout statique) :
  1. graphe d'imports du projet par AST (core/, gui/, tools/), Y COMPRIS les
     imports paresseux au fond des fonctions (pattern maison des dialogues) ;
  2. fichiers modifies = git status --porcelain (M/A/R/??), ou passes en
     argument ; les non-suivis _*.py (scripts de chantier) sont ignores ;
  3. fermeture TRANSITIVE des importeurs : toucher core/ecf/model.py
     remonte jusqu'aux tests qui importent gui/ecf/parser.py ;
  4. sortie = fichiers de tests + commande pytest prete a coller.

Limites affichees honnetement (regle du 11/10 : jamais de « 0 » muet) : un
.py modifie hors graphe ou une donnee non-py (json, docs, fixtures) ne peut
pas etre tracee statiquement -> l'outil le DIT et recommande la suite
complete plutot que de mentir.

Usage :
  python tools/impacted_tests.py                     # depuis git status
  python tools/impacted_tests.py core/market_balance.py gui/main_window.py
  python tools/impacted_tests.py --run [...]         # execute la selection
"""
from __future__ import annotations

import ast
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG_ROOTS = ("core", "gui", "tools")
SRC_DIRS = ("core", "gui", "tools", "tests")


# ------------------------------------------------------------- graphe

def _try_file(cand: Path, out: set) -> None:
    for target in (cand.with_suffix(".py"), cand / "__init__.py"):
        if target.is_file():
            out.add(target)
            return


def project_imports(path: Path, root: Path = None) -> set:
    """Chemins .py du projet importes par `path` (top-level ET fonctions —
    les dialogues importent souvent paresseusement dans leurs slots)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, OSError):
        return set()
    root = root or ROOT
    out: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = tuple(alias.name.split("."))
                if parts[0] in PKG_ROOTS:
                    _try_file(root.joinpath(*parts), out)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # import relatif : from . import x  /  from ..pkg import y
                base = path.parents[node.level - 1]
                try:
                    prefix = base.relative_to(root).parts
                except ValueError:
                    continue               # remonte hors du projet
                parts = prefix + tuple((node.module or "").split(".")) \
                    if node.module else prefix
                _try_file(root.joinpath(*parts), out)
                sub_base = root.joinpath(*parts)
            else:
                mod = tuple((node.module or "").split("."))
                if not mod or mod[0] not in PKG_ROOTS:
                    continue
                _try_file(root.joinpath(*mod), out)
                sub_base = root.joinpath(*mod)
            # from core import fsutil  /  from . import model
            for alias in node.names:
                sub = sub_base / f"{alias.name}.py"
                if sub.is_file():
                    out.add(sub)
    return out


def build_graph(root: Path = None) -> dict:
    """{fichier: ensemble de fichiers importes} sur tout le projet."""
    root = root or ROOT
    graph = {}
    for d in SRC_DIRS:
        base = root / d
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            graph[path] = project_imports(path, root)
    return graph


def importers_closure(graph: dict, changed: set) -> set:
    """Fermeture transitive des IMPORTEURS : tout fichier qui depend
    (directement ou via une chaine) d'un fichier change."""
    reverse: dict = {}
    for src, deps in graph.items():
        for dep in deps:
            reverse.setdefault(dep, set()).add(src)
    seen = set(changed)
    stack = list(changed)
    while stack:
        for imp in reverse.get(stack.pop(), ()):
            if imp not in seen:
                seen.add(imp)
                stack.append(imp)
    return seen


# --------------------------------------------------------- changement

def git_changed(root: Path = ROOT) -> tuple:
    """(py_modifies, non_py_modifies, autres) depuis git status --porcelain.
    non_py = donnees sous core/gui/tools/tests/data (fixtures, json) ->
    non tracables statiquement, signalees. autres = README/docs/... (comptes,
    sans impact test connu). Non-suivis _*.py (chantier) ignores."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return (), (), ()
    py, non_py, other = [], [], []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        # format porcelain : XY<espace>chemin — X/Y peuvent etre des ESPACES
        # (fichier suivi modifie non stague = " M") : le chemin commence
        # TOUJOURS au caractere 3, jamais de partition naive
        code = line[:2].strip()
        pathpart = line[3:].strip().strip('"')
        if "->" in pathpart:      # renommage : seul le nouveau chemin compte
            pathpart = pathpart.split("->")[-1].strip()
        rel = pathpart.replace("\\", "/")
        if code.strip() == "??" and Path(rel).name.startswith("_"):
            continue              # script de chantier non-suivi
        if Path(rel).suffix == ".py" and rel.split("/")[0] in SRC_DIRS:
            py.append(root / rel)
        elif rel.split("/")[0] in ("core", "gui", "tools", "tests", "data"):
            non_py.append(root / rel)
        else:
            other.append(root / rel)
    return py, non_py, other


# ------------------------------------------------------------- choix

def impacted_tests(graph: dict, changed_py: set) -> set:
    """Fichiers de tests touches : dans la fermeture des importeurs, ou
    eux-memes modifies."""
    closure = importers_closure(graph, {p for p in changed_py if p in graph})
    tests = {p for p in closure if p.parent.name == "tests"}
    tests |= {p for p in changed_py if p.parent.name == "tests"}
    return tests


def main(argv: list) -> int:
    run = bool(argv) and argv[0] == "--run"
    if run:
        argv = argv[1:]
    t0 = time.perf_counter()
    graph = build_graph()
    if argv:
        changed_py = {ROOT / a for a in argv}
        non_py, other = [], []
    else:
        changed_py, non_py, other = git_changed()
        changed_py = set(changed_py)
    tests = sorted(impacted_tests(graph, changed_py))
    dt = time.perf_counter() - t0

    n_src = sum(1 for p in graph if p.parent.name != "tests")
    print(f"Graphe: {n_src} modules + {len(graph) - n_src} tests, "
          f"fermeture en {dt:.1f}s ; modifies: {len(changed_py)} .py"
          + (f" (+{len(non_py)} donnees non-py)" if non_py else ""))
    for p in sorted(changed_py):
        if p.suffix == ".py" and p not in graph:
            print(f"  ATTENTION hors graphe: {p.relative_to(ROOT)}")
    if non_py:
        print("  ATTENTION donnees non-py modifiees sous core/gui/tools/"
              "tests/data : selection statique impossible -> ces tests "
              "concernes (ou la suite complete) restent conseilles :")
        for p in sorted(non_py):
            print(f"    {p.relative_to(ROOT)}")
    if other:
        print(f"  hors perimetre tests (README/docs/build) : {len(other)} "
              "fichier(s) ignore(s).")
    if not tests:
        print("Aucun test impacte.")
        return 0
    rel = [str(t.relative_to(ROOT)).replace("\\", "/") for t in tests]
    print(f"Tests impactes ({len(rel)}) :")
    for r in rel:
        print(f"  {r}")
    cmd = ["python", "-m", "pytest", *rel, "-q", "-p", "no:cacheprovider"]
    print("Commande :")
    print("  rtk test " + " ".join(cmd))
    if run:
        return subprocess.call(cmd)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
