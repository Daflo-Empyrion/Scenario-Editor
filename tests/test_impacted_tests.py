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

"""Selection des tests impactes (tools/impacted_tests.py) : graphe d'imports
AST (top-level, en fonctions, from-pkg-import, relatifs), parsing porcelain
(le piege « XY<espace>chemin » : un fichier suivi modifie commence par
«  M », partition naive casse), fermeture transitive, signalement honnete
des donnees non-py."""

from pathlib import Path
from types import SimpleNamespace

from tools.impacted_tests import (build_graph, git_changed,
                                     impacted_tests, project_imports)


def _mini(root: Path):
    (root / "core").mkdir()
    (root / "core" / "__init__.py").write_text("", encoding="utf-8")
    (root / "core" / "model.py").write_text("", encoding="utf-8")
    (root / "core" / "fsutil.py").write_text("", encoding="utf-8")
    (root / "core" / "sub").mkdir()
    (root / "core" / "sub" / "__init__.py").write_text("", encoding="utf-8")
    (root / "core" / "sub" / "deep.py").write_text("", encoding="utf-8")
    (root / "tests").mkdir()
    return root


def test_imports_toplevel_function_and_from_pkg(tmp_path):
    root = _mini(tmp_path)
    src = root / "tests" / "test_x.py"
    src.write_text(
        "from core.model import A\n"
        "def f():\n"
        "    from core import fsutil      # import paresseux en fonction\n"
        "    return fsutil\n"
        "import core.sub.deep\n", encoding="utf-8")
    got = {p.name for p in project_imports(src, root)}
    # __init__.py du package est aussi ajoute (from core import x charge
    # core/__init__.py : le modifier doit impacter les importeurs)
    assert {"model.py", "fsutil.py", "deep.py", "__init__.py"} <= got


def test_imports_relative(tmp_path):
    root = _mini(tmp_path)
    src = root / "core" / "sub" / "mod.py"
    src.write_text(
        "from . import deep\n"
        "from ..model import A\n", encoding="utf-8")
    got = {str(p.relative_to(root)) for p in project_imports(src, root)}
    got = {g.replace("\\", "/") for g in got}
    assert "core/sub/deep.py" in got
    assert "core/model.py" in got


def test_closure_and_impacted_tests(tmp_path):
    root = _mini(tmp_path)
    (root / "core" / "parser.py").write_text(
        "from core.model import A\n", encoding="utf-8")
    (root / "tests" / "test_parser.py").write_text(
        "from core.parser import parse\n", encoding="utf-8")
    (root / "tests" / "test_autre.py").write_text(
        "from core.fsutil import x\n", encoding="utf-8")
    graph = build_graph(root)
    got = {p.name for p in impacted_tests(
        graph, {root / "core" / "model.py"})}
    # model -> parser -> test_parser (transitif) ; test_autre non concerne
    assert got == {"test_parser.py"}


def test_git_changed_parses_porcelain_correctly(tmp_path, monkeypatch):
    """Piege vecu : «  M chemin » (suivi modifie) — un partition(' ')
    collerait le M au chemin et IGNORERAIT silencieusement le fichier."""
    monkeypatch.setattr("tools.impacted_tests.subprocess.run", lambda *a, **k: (
        SimpleNamespace(stdout=(
            " M core/tutorials.py\n"
            "M  core/staged.py\n"
            "?? core/new_module.py\n"
            "?? _chantier_ignore.py\n"
            "R  ancien.py -> core/renomme.py\n"
            " M data/i18n_strings.json\n"
            " M README.md\n"), check=True)))
    py, non_py, other = git_changed(tmp_path)
    py_names = {p.name for p in py}
    assert py_names == {"tutorials.py", "staged.py", "new_module.py",
                        "renomme.py"}
    assert "_chantier_ignore.py" not in py_names
    assert [p.name for p in non_py] == ["i18n_strings.json"]
    assert [p.name for p in other] == ["README.md"]


def test_graph_on_real_repo_sees_new_modules():
    """Ancrage reel : le graphe du repo voit le module market_balance et sa
    chaine complete jusqu'aux tests (hub main_window inclus)."""
    from tools.impacted_tests import ROOT
    graph = build_graph(ROOT)
    got = {p.name for p in impacted_tests(graph, {ROOT / "core" / "market_balance.py"})}
    assert "test_market_balance.py" in got
    assert "test_market_price_dialog.py" in got
    # la fermeture remonte jusqu'au hub main_window -> un large panel de
    # tests GUI : comportement VOLONTAIRE (rappel maximal, zero faux negatif)
    assert len(got) >= 10
