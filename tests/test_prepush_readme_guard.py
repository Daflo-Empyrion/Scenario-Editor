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

"""Garde-fou pre-push (regle 6 d'AGENTS.md) : un push qui touche le code de
l'application doit toucher README.md, sinon la nouveaute n'est documentee dans
aucune des deux langues.

Chaque test fait un VRAI `git push` vers un depot nu temporaire : c'est git
qui invoque le hook, donc rien ne peut diverger du comportement reel.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / ".githooks" / "pre-push"


def _git(repo: Path, *args, check=True):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True,
                          text=True, encoding="utf-8", check=check)


@pytest.fixture
def remote(tmp_path):
    """(depot de travail, depot nu distant) avec le hook du projet actif."""
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(bare)], capture_output=True,
                   check=True)
    repo = tmp_path / "work"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / ".githooks").mkdir()
    shutil.copy2(HOOK, repo / ".githooks" / "pre-push")
    _git(repo, "config", "core.hooksPath", ".githooks")
    _git(repo, "remote", "add", "origin", str(bare))
    _write(repo, "README.md", "# Projet\n")
    _commit(repo, "amorce")
    assert _push(repo).returncode == 0          # le premier push passe
    return repo


def _write(repo: Path, name: str, texte: str) -> None:
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(texte, encoding="utf-8")


def _commit(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)


def _push(repo: Path):
    return subprocess.run(["git", "push", "origin", "main"], cwd=repo,
                          capture_output=True, text=True, encoding="utf-8")


def test_code_without_readme_is_refused(remote):
    _write(remote, "core/nouveau.py", "X = 1\n")
    _commit(remote, "code seul")
    resultat = _push(remote)
    assert resultat.returncode != 0
    assert "PRE-PUSH REFUSE" in resultat.stderr
    assert "core/nouveau.py" in resultat.stderr


def test_code_with_readme_passes(remote):
    _write(remote, "core/nouveau.py", "X = 1\n")
    _write(remote, "README.md", "# Projet\n\n## Français\n\n## English\n")
    _commit(remote, "code + readme")
    assert _push(remote).returncode == 0


def test_internal_changes_do_not_trigger(remote):
    """tests/, docs/, .github/, tools/ ne parlent pas a l'utilisateur."""
    _write(remote, "tests/test_x.py", "def test_x():\n    assert True\n")
    _write(remote, "docs/note.md", "note\n")
    _write(remote, "tools/script.py", "X = 1\n")
    _commit(remote, "interne")
    assert _push(remote).returncode == 0


def test_tags_are_ignored(remote):
    _write(remote, "core/nouveau.py", "X = 1\n")
    _commit(remote, "code seul")
    _git(remote, "tag", "v0.0.1")
    resultat = subprocess.run(["git", "push", "origin", "v0.0.1"], cwd=remote,
                              capture_output=True, text=True, encoding="utf-8")
    assert resultat.returncode == 0
