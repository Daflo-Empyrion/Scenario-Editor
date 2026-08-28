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
Verifie que le handler YAML reproduit fidelement (byte pour byte) un ou plusieurs
fichiers .yaml/.yml reels (playfield_static.yaml, playfield_dynamic.yaml...).

C'est l'equivalent, pour YAML, de verifier_parser_ecf.py -- meme principe : on ne fait
confiance a un format qu'apres l'avoir valide sur de vrais fichiers.

UTILISATION :
    python verifier_parser_yaml.py "C:\\chemin\\vers\\Playfields"
    python verifier_parser_yaml.py fichier.yaml
"""
import sys
from pathlib import Path

# Rend le paquet cli/ (et donc cli._bootstrap) importable meme quand ce script
# est lance DIRECTEMENT (python cli/xxx.py), auquel cas cli/ -- pas la racine du
# projet -- serait sinon le premier dossier sur sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli._bootstrap import ensure_core_importable
ensure_core_importable("core/yaml_handler.py")
try:
    from core.yaml_handler import YamlHandler
except ImportError as e:
    print(f"ERREUR d'import : {e}")
    sys.exit(1)


def check_file(path: Path, handler: YamlHandler) -> bool:
    with open(path, 'rb') as f:
        original = f.read()

    try:
        raw = handler.load(path)
        parsed = handler.parse(raw)
        rendered = handler.serialize(parsed).encode('utf-8')
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
                if shown >= 8:
                    print("    ... (arret apres 8 differences)")
                    break
        if len(orig_lines) != len(rend_lines):
            print(f"    Decalage de longueur de fichier : {len(orig_lines)} vs {len(rend_lines)} lignes")
    except Exception as e:
        print(f"    (impossible d'afficher le detail: {e})")
    return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python verifier_parser_yaml.py <dossier_ou_fichier.yaml>")
        sys.exit(1)

    target = Path(sys.argv[1])
    if target.is_file():
        files = [target]
    else:
        files = sorted(target.rglob("*.yaml")) + sorted(target.rglob("*.yml"))

    if not files:
        print(f"Aucun fichier .yaml/.yml trouve dans {target}")
        return

    handler = YamlHandler()

    print(f"Verification de {len(files)} fichier(s) .yaml/.yml...\n")
    ok_count = 0
    for f in files:
        if check_file(f, handler):
            ok_count += 1

    print(f"\n{'=' * 50}")
    print(f"Resultat : {ok_count}/{len(files)} fichiers reproduits a l'identique")
    if ok_count == len(files):
        print("Tout est bon, le handler YAML est fiable sur ces fichiers.")
    else:
        print("Certains fichiers posent probleme -- envoie-les moi (ou juste le detail affiche "
              "ci-dessus) pour que j'ajuste le handler.")


if __name__ == "__main__":
    main()
