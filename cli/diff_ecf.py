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

"""
Compare deux fichiers .ecf et affiche les differences (blocs ajoutes/supprimes/modifies).

UTILISATION :
    python cli/diff_ecf.py fichierA.ecf fichierB.ecf

Exemple concret : comparer la meme config entre deux versions d'un scenario, ou entre
deux scenarios differents (ex: Config_RE.ecf de Atlantis Next vs RE2).
"""
import sys
from pathlib import Path

# Rend le paquet cli/ (et donc cli._bootstrap) importable meme quand ce script
# est lance DIRECTEMENT (python cli/xxx.py), auquel cas cli/ -- pas la racine du
# projet -- serait sinon le premier dossier sur sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli._bootstrap import ensure_core_importable
ensure_core_importable("core/ecf/diff.py")
from core.ecf.parser import parse_ecf_file
from core.ecf.diff import diff_documents, format_diff, summarize_diff


def main():
    if len(sys.argv) != 3:
        print("Usage: python cli/diff_ecf.py fichierA.ecf fichierB.ecf")
        sys.exit(1)

    path_a = Path(sys.argv[1])
    path_b = Path(sys.argv[2])

    for p in (path_a, path_b):
        if not p.exists():
            print(f"ERREUR : fichier introuvable : {p}")
            sys.exit(1)

    print(f"Comparaison :")
    print(f"  A = {path_a}")
    print(f"  B = {path_b}")
    print()

    doc_a = parse_ecf_file(path_a)
    doc_b = parse_ecf_file(path_b)

    diffs = diff_documents(doc_a, doc_b)
    resume = summarize_diff(diffs)

    print("=" * 60)
    print("RESUME")
    print("=" * 60)
    print(f"  Blocs ajoutes   (dans B, absents de A) : {resume['added']}")
    print(f"  Blocs supprimes (dans A, absents de B) : {resume['removed']}")
    print(f"  Blocs modifies                         : {resume['modified']}")
    total = resume['added'] + resume['removed'] + resume['modified']
    print()

    if total == 0:
        print("Aucune difference detectee -- les deux fichiers sont equivalents.")
        return

    print("=" * 60)
    print("DETAIL")
    print("=" * 60)
    print(format_diff(diffs))


if __name__ == "__main__":
    main()
