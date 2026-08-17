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
Verifie que le handler CSV reproduit fidelement (byte pour byte) un ou plusieurs
fichiers .csv reels (Localization.csv, PDA.csv, Dialogues.csv...).

Meme demarche que verifier_parser_ecf.py et verifier_parser_yaml.py -- on ne fait
confiance a un format qu'apres l'avoir valide sur de vrais fichiers.

UTILISATION :
    python verifier_parser_csv.py "C:\\chemin\\vers\\Extras"
    python verifier_parser_csv.py fichier.csv
"""
import sys
from pathlib import Path

if getattr(sys, 'frozen', False):
    # Construit par PyInstaller (voir empyrion_editor.spec, executable
    # 'EmpyrionEditorCLI') : 'core' est deja compile et importable directement,
    # aucune recherche de dossier necessaire.
    pass
else:
    _ici = Path(__file__).resolve().parent
    _candidats = [_ici, _ici / "empyrion_editor", _ici.parent, _ici.parent / "empyrion_editor"]
    for _c in _candidats:
        if (_c / "core" / "csv_handler.py").exists():
            sys.path.insert(0, str(_c))
            break
    else:
        print("ERREUR : impossible de trouver core/csv_handler.py")
        sys.exit(1)
from core.csv_handler import CsvHandler


def check_file(path: Path, handler: CsvHandler) -> bool:
    with open(path, 'rb') as f:
        original = f.read()

    try:
        raw = handler.load(path)
        doc = handler.parse(raw)
        rendered = handler.serialize(doc)
        original_text = original.decode('utf-8-sig')
        rendered_bytes = rendered.encode('utf-8')
        original_compare_bytes = original_text.encode('utf-8')
    except Exception as e:
        print(f"  [ERREUR PARSING] {path.name} : {e}")
        return False

    if original_compare_bytes == rendered_bytes:
        print(f"  [OK] {path.name} ({len(original)} octets, identique)")
        return True

    print(f"  [ECHEC] {path.name} : difference detectee")
    try:
        orig_lines = original_text.splitlines(keepends=True)
        rend_lines = rendered.splitlines(keepends=True)
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
            print(f"    Decalage de longueur : {len(orig_lines)} vs {len(rend_lines)} lignes")
    except Exception as e:
        print(f"    (impossible d'afficher le detail: {e})")
    return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python verifier_parser_csv.py <dossier_ou_fichier.csv>")
        sys.exit(1)

    target = Path(sys.argv[1])
    if target.is_file():
        files = [target]
    else:
        files = sorted(target.rglob("*.csv"))

    if not files:
        print(f"Aucun fichier .csv trouve dans {target}")
        return

    handler = CsvHandler()
    print(f"Verification de {len(files)} fichier(s) .csv...\n")
    ok_count = 0
    for f in files:
        if check_file(f, handler):
            ok_count += 1

    print(f"\n{'=' * 50}")
    print(f"Resultat : {ok_count}/{len(files)} fichiers reproduits a l'identique")
    if ok_count == len(files):
        print("Tout est bon, le handler CSV est fiable sur ces fichiers.")
    else:
        print("Certains fichiers posent probleme -- envoie-les moi (ou le detail ci-dessus) "
              "pour que j'ajuste le handler.")


if __name__ == "__main__":
    main()
