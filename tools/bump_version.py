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

"""Bump de version : UN SEUL geste pour les QUATRE emplacements.

Pourquoi ce script : le tag v2.3.0 a fait echouer la CI parce que
`installer.iss` (MyAppVersion) et les tuples `filevers`/`prodvers` de
`version_info.txt` etaient restes en 2.2.0 — les tests
`test_version_consistency` / `test_installer_version` les comparent a
`core/version.py`. Oublier un seul des quatre rougit la CI ... apres 19 min
de tests et un tag a deplacer.

    python tools/bump_version.py 2.4.0            # ecrit puis relit
    python tools/bump_version.py 2.4.0 --dry-run  # montre sans ecrire

Puis, comme toujours :
    python -m pytest tests/test_version_consistency.py tests/test_installer_version.py -q
    git commit -am "v2.4.0" && git tag v2.4.0 && git push origin main --tags
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

VERSION_PY = Path("core") / "version.py"
VERSION_INFO = Path("version_info.txt")
INSTALLER = Path("installer.iss")

_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def version_tuple(version: str) -> tuple[int, int, int, int]:
    major, minor, patch = (int(part) for part in version.split("."))
    return major, minor, patch, 0


def _replacements(version: str) -> list[tuple[Path, re.Pattern, str]]:
    """(fichier, motif, remplacement) des quatre emplacements, dans l'ordre."""
    quad = version_tuple(version)
    quad_text = ", ".join(str(part) for part in quad)
    return [
        (VERSION_PY,
         re.compile(r'^APP_VERSION = "[^"]*"', re.M),
         f'APP_VERSION = "{version}"'),
        (VERSION_INFO,
         re.compile(r"(StringStruct\(u'FileVersion', u')[^']*('\))"),
         rf"\g<1>{version}.0\g<2>"),
        (VERSION_INFO,
         re.compile(r"(StringStruct\(u'ProductVersion', u')[^']*('\))"),
         rf"\g<1>{version}.0\g<2>"),
        (VERSION_INFO,
         re.compile(r"filevers=\([^)]*\)"),
         f"filevers=({quad_text})"),
        (VERSION_INFO,
         re.compile(r"prodvers=\([^)]*\)"),
         f"prodvers=({quad_text})"),
        (INSTALLER,
         re.compile(r'#define MyAppVersion "[^"]*"'),
         f'#define MyAppVersion "{version}"'),
    ]


def bump(root: Path, version: str, dry_run: bool = False) -> list[Path]:
    """Ecrit la version aux quatre emplacements ; retourne les fichiers
    reellement modifies. Leve ValueError sur une version mal formee ou un
    fichier/motif introuvable (on ne devine jamais)."""
    if not _VERSION_RE.match(version):
        raise ValueError(f"version attendue X.Y.Z, recu {version!r}")
    root = Path(root)
    touched: list[Path] = []
    texts: dict[Path, str] = {}
    for relative, pattern, replacement in _replacements(version):
        path = root / relative
        text = texts.get(path)
        if text is None:
            try:
                text = path.read_text(encoding="utf-8")
            except OSError as exc:
                raise ValueError(f"{relative} illisible : {exc}") from exc
        new_text, count = pattern.subn(replacement, text)
        if count == 0:
            raise ValueError(f"motif introuvable dans {relative} : {pattern.pattern}")
        texts[path] = new_text
        if path not in touched:
            touched.append(path)
    if not dry_run:
        for path, text in texts.items():
            path.write_text(text, encoding="utf-8")
    return touched


def check(root: Path, version: str) -> list[str]:
    """Relit les quatre emplacements et liste ce qui ne correspond pas."""
    root = Path(root)
    quad = version_tuple(version)
    expected = {
        VERSION_PY: [f'APP_VERSION = "{version}"'],
        VERSION_INFO: [f"u'{version}.0'", f"filevers=({', '.join(map(str, quad))})",
                       f"prodvers=({', '.join(map(str, quad))})"],
        INSTALLER: [f'#define MyAppVersion "{version}"'],
    }
    problems = []
    for relative, needles in expected.items():
        try:
            text = (root / relative).read_text(encoding="utf-8")
        except OSError as exc:
            problems.append(f"{relative} illisible : {exc}")
            continue
        for needle in needles:
            if needle not in text:
                problems.append(f"{relative} : {needle} absent")
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version", help="nouvelle version, format X.Y.Z")
    parser.add_argument("--dry-run", action="store_true",
                        help="affiche les fichiers sans rien ecrire")
    args = parser.parse_args(argv)
    try:
        touched = bump(ROOT, args.version, dry_run=args.dry_run)
    except ValueError as exc:
        print(f"ERREUR : {exc}")
        return 2
    for path in touched:
        print(f"{'verifierait' if args.dry_run else 'mis a jour'} : {path.as_posix()}")
    if args.dry_run:
        return 0
    problems = check(ROOT, args.version)
    for problem in problems:
        print(f"INCOHERENT : {problem}")
    if problems:
        return 1
    print(f"version {args.version} coherente aux quatre emplacements")
    print("penser a : pytest tests/test_version_consistency.py "
          "tests/test_installer_version.py -q")
    return 0


if __name__ == "__main__":
    sys.exit(main())
