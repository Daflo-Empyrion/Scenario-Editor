"""
Diagnostic : verifie si mon parser retrouve un bloc precis (par Id) dans un fichier
.ecf, apres une edition manuelle (ex: decommenter un bloc en conflit d'Id).

UTILISATION :
    python diagnostic_bloc.py "chemin\vers\BlocksConfig.ecf" 999999
    (999999 = l'Id que tu as donne au bloc)
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
from core.ecf.model import EcfBlock, EcfComment, block_identity


def main():
    if len(sys.argv) != 3:
        print("Usage: python diagnostic_bloc.py <fichier.ecf> <Id>")
        sys.exit(1)

    path = Path(sys.argv[1])
    target_id = sys.argv[2]

    doc = parse_ecf_file(path)

    print(f"Recherche du bloc avec Id={target_id} dans {path.name}...")
    print()

    found_blocks = []
    for block in doc.iter_blocks():
        if block_identity(block) == target_id:
            found_blocks.append(block)

    print(f"Blocs actifs (structures) trouves avec cet Id : {len(found_blocks)}")
    for b in found_blocks:
        print(f"  - genre={b.kind}, Name={b.get_property('Name')}")

    print()
    print("Recherche de l'Id dans les commentaires bruts (texte non-structure) :")
    count_in_comments = 0
    for node in doc.nodes:
        if isinstance(node, EcfComment) and target_id in node.raw:
            count_in_comments += 1
            print(f"  - {node.raw.rstrip()!r}")
    if count_in_comments == 0:
        print("  (aucun -- l'Id n'apparait dans aucun commentaire, donc pas de residu de commentaire)")

    print()
    print(f"Total de blocs actifs dans tout le fichier : {sum(1 for _ in doc.iter_blocks())}")


if __name__ == "__main__":
    main()
