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

_ici = Path(__file__).resolve().parent
_candidats = [_ici, _ici / "empyrion_editor", _ici.parent, _ici.parent / "empyrion_editor"]
for _c in _candidats:
    if (_c / "core" / "ecf" / "parser.py").exists():
        sys.path.insert(0, str(_c))
        break
else:
    print("ERREUR : impossible de trouver core/ecf/parser.py")
    sys.exit(1)

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
