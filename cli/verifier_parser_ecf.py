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
Verifie que le parser ECF reproduit fidelement (byte pour byte) un ou plusieurs
fichiers .ecf reels. A lancer sur TES fichiers pour valider le parser au-dela
de l'exemple deja teste (Containers.ecf).

UTILISATION :
    python verifier_parser_ecf.py "C:\chemin\vers\Content\Configuration"

    (ou un chemin vers un seul fichier .ecf)

Passe en revue chaque .ecf trouve et affiche OK / ECHEC pour chacun, avec le detail
des differences en cas d'echec.
"""
import sys
from pathlib import Path

# Rend le paquet cli/ (et donc cli._bootstrap) importable meme quand ce script
# est lance DIRECTEMENT (python cli/xxx.py), auquel cas cli/ -- pas la racine du
# projet -- serait sinon le premier dossier sur sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli._bootstrap import ensure_core_importable
ensure_core_importable("core/ecf/parser.py")
from core.ecf.parser import parse_ecf_file


def check_file(path: Path) -> bool:
    with open(path, 'rb') as f:
        original = f.read()

    try:
        doc = parse_ecf_file(path)
        rendered = doc.render().encode('utf-8')
    except Exception as e:
        print(f"  [ERREUR PARSING] {path.name} : {e}")
        return False

    if original == rendered:
        print(f"  [OK] {path.name} ({len(original)} octets, identique)")
        return True

    print(f"  [ECHEC] {path.name} : difference detectee")
    try:
        orig_lines = original.decode('utf-8', errors='replace').splitlines(keepends=True)
        rend_lines = rendered.decode('utf-8', errors='replace').splitlines(keepends=True)
        print(f"    Lignes original: {len(orig_lines)}, rendu: {len(rend_lines)}")
        shown = 0
        for i, (a, b) in enumerate(zip(orig_lines, rend_lines)):
            if a != b:
                print(f"    Ligne {i+1}: original={a!r}  rendu={b!r}")
                shown += 1
                if shown >= 5:
                    print("    ... (arret apres 5 differences)")
                    break
    except Exception as e:
        print(f"    (impossible d'afficher le detail: {e})")
    return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python verifier_parser_ecf.py <dossier_ou_fichier.ecf>")
        sys.exit(1)

    target = Path(sys.argv[1])
    if target.is_file():
        files = [target]
    else:
        files = sorted(target.rglob("*.ecf"))

    if not files:
        print(f"Aucun fichier .ecf trouve dans {target}")
        return

    print(f"Verification de {len(files)} fichier(s) .ecf...\n")
    ok_count = 0
    for f in files:
        if check_file(f):
            ok_count += 1

    print(f"\n{'=' * 50}")
    print(f"Resultat : {ok_count}/{len(files)} fichiers reproduits a l'identique")
    if ok_count == len(files):
        print("Tout est bon, le parser est fiable sur ces fichiers.")
    else:
        print("Certains fichiers posent probleme -- envoie-les moi pour que je corrige le parser.")


if __name__ == "__main__":
    main()
