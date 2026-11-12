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

"""Extrait du CHANGELOG la note de version, au format note de release.

Depuis la 2.6.0 le CHANGELOG est la SOURCE des notes : le workflow s'en sert
pour remplir le corps du brouillon de release, au lieu d'une recopie manuelle
qui derive. L'extraction tourne AVANT PyInstaller dans le job `build` : sans
entree `## [X.Y.Z]`, le build echoue en quelques secondes, donc jamais de
brouillon sans notes.

    python tools/changelog_excerpt.py 2.6.0                 # corps sur stdout
    python tools/changelog_excerpt.py v2.6.0 -o body.md     # dans un fichier

Le titre descriptif part dans `$GITHUB_OUTPUT` (`title=...`) quand la CI le
fournit ; sur un poste de dev, il est simplement ignore.
"""
import argparse
import os
import re
import sys
from pathlib import Path

HEAD_RE = re.compile(r"^## \[(?P<ver>[^\]]+)\](?:\s*[—-]\s*(?P<date>.*))?$")


def extract(text: str, version: str):
    """(titre, corps) de cette version, ou None si l'entree manque."""
    lines = text.split("\n")
    start = None
    for i, line in enumerate(lines):
        found = HEAD_RE.match(line.strip())
        if found and found.group("ver").strip() == version:
            start = i
            break
    if start is None:
        return None
    rest = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        rest.append(line)
    while rest and not rest[0].strip():
        rest.pop(0)
    sous_titre = ""
    if rest and rest[0].strip().startswith("*") and rest[0].strip().endswith("*"):
        sous_titre = rest.pop(0).strip().strip("*").strip()
    corps = []
    for line in rest:
        if line.startswith("#### "):        # note de release : un niveau de moins
            corps.append("### " + line[5:])
        elif line.startswith("### "):
            corps.append("## " + line[4:])
        else:
            corps.append(line)
    titre = f"v{version} — {sous_titre}" if sous_titre else f"v{version}"
    return titre, f"# {titre}\n" + "\n".join(corps).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("version")
    ap.add_argument("-o", "--out", default="", help="fichier de sortie du corps")
    ap.add_argument("--changelog", default="CHANGELOG.md")
    args = ap.parse_args()
    version = args.version.strip().lstrip("v")
    text = Path(args.changelog).read_text(encoding="utf-8")
    got = extract(text, version)
    if got is None:
        print(f"aucune entree '## [{version}]' dans {args.changelog} : ecrire "
              f"la note de version AVANT de taguer (elle remplit la release)",
              file=sys.stderr)
        return 2
    titre, corps = got
    if args.out:
        Path(args.out).write_text(corps, encoding="utf-8")
        print(f"note de version {version} ecrite dans {args.out} "
              f"({len(corps)} octets)")
    else:
        sys.stdout.write(corps)
    sortie = os.environ.get("GITHUB_OUTPUT")
    if sortie:
        with open(sortie, "a", encoding="utf-8") as fh:
            fh.write(f"title={titre}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
