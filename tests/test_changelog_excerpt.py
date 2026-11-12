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

"""Note de version tiree du CHANGELOG (tools/changelog_excerpt.py) : le
workflow la pose en corps du brouillon de release, donc plus de recopie
manuelle qui derive."""
import sys
from pathlib import Path

CHANGELOG = """# CHANGELOG

## [1.3.0] — 2026-12-01

*Troisieme version, sous-titre descriptif*

### Ajoute
- une chose
- une autre

### Corrige
- un bug

## [1.2.0] — 2026-11-01

*Deuxieme version*

### Ajoute
- rien
"""


def _module():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import changelog_excerpt
    return changelog_excerpt


def test_extracts_title_and_body_for_one_version():
    titre, corps = _module().extract(CHANGELOG, "1.3.0")
    assert titre == "v1.3.0 — Troisieme version, sous-titre descriptif"
    assert corps.startswith("# v1.3.0 — Troisieme version")
    assert "## Ajoute" in corps                 # ### demote en ##
    assert "## Corrige" in corps
    assert "1.2.0" not in corps                # s'arrete a l'entree suivante
    assert "- un bug" in corps


def test_unknown_version_returns_none():
    assert _module().extract(CHANGELOG, "9.9.9") is None


def test_cli_writes_the_body_and_fails_without_entry(tmp_path):
    module = _module()
    body = tmp_path / "body.md"
    argv = sys.argv
    try:
        sys.argv = ["changelog_excerpt", "1.2.0", "-o", str(body),
                    "--changelog", str(_write(tmp_path))]
        assert module.main() == 0
        assert body.read_text(encoding="utf-8").startswith("# v1.2.0")
        assert chr(13).encode() not in body.read_bytes()  # corps OS-independant
        sys.argv = ["changelog_excerpt", "9.9.9", "--changelog",
                    str(_write(tmp_path))]
        assert module.main() == 2               # le build CI doit echouer
    finally:
        sys.argv = argv


def test_current_version_has_a_changelog_entry():
    """Garde-fou : APP_VERSION doit avoir son entree, sinon le job `build`
    echoue en CI (meme controle, plus tot)."""
    from core.version import APP_VERSION
    racine = Path(__file__).resolve().parents[1]
    titre, corps = _module().extract(
        (racine / "CHANGELOG.md").read_text(encoding="utf-8"), APP_VERSION)
    assert titre.startswith(f"v{APP_VERSION} — "), titre
    assert corps.count("## ") >= 2, "note de version trop pauvre"


def _write(tmp_path: Path) -> Path:
    p = tmp_path / "CHANGELOG.md"
    p.write_text(CHANGELOG, encoding="utf-8")
    return p
