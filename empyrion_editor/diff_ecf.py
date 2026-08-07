"""
Compare deux fichiers .ecf et affiche les differences (blocs ajoutes/supprimes/modifies).

UTILISATION :
    python diff_ecf.py fichierA.ecf fichierB.ecf

Exemple concret : comparer la meme config entre deux versions d'un scenario, ou entre
deux scenarios differents (ex: Config_RE.ecf de Atlantis Next vs RE2).
"""
import sys
from pathlib import Path

_ici = Path(__file__).resolve().parent
_candidats = [_ici, _ici / "empyrion_editor", _ici.parent, _ici.parent / "empyrion_editor"]
for _c in _candidats:
    if (_c / "core" / "ecf" / "diff.py").exists():
        sys.path.insert(0, str(_c))
        break
else:
    print("ERREUR : impossible de trouver core/ecf/diff.py")
    sys.exit(1)

from core.ecf.parser import parse_ecf_file
from core.ecf.diff import diff_documents, format_diff, summarize_diff


def main():
    if len(sys.argv) != 3:
        print("Usage: python diff_ecf.py fichierA.ecf fichierB.ecf")
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
