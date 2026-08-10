"""
Detecte les blocs ECF qui contiennent anormalement d'autres blocs "Block"/"+Block"
imbriques a l'interieur -- signe caracteristique du bug ou une ligne de fermeture '}'
est restee commentee ('#}') apres une edition manuelle, ce qui fait que tout le reste
du fichier se retrouve avale comme "enfant" du bloc mal ferme.

Normalement, dans BlocksConfig.ecf, un bloc 'Block'/'+Block' ne contient PAS d'autres
blocs 'Block'/'+Block' imbriques -- si on en trouve, c'est le signe du probleme.

UTILISATION :
    python detecter_imbrication_anormale.py "chemin\vers\BlocksConfig.ecf"
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
from core.ecf.model import EcfBlock, normalized_kind, block_identity


def main():
    if len(sys.argv) != 2:
        print("Usage: python detecter_imbrication_anormale.py <fichier.ecf>")
        sys.exit(1)

    path = Path(sys.argv[1])
    doc = parse_ecf_file(path)

    print(f"Analyse de {path.name}...")
    print()

    suspects = []
    for node in doc.nodes:
        if not isinstance(node, EcfBlock):
            continue
        nested_blocks = [c for c in node.children if isinstance(c, EcfBlock)
                          and normalized_kind(c.kind) == normalized_kind(node.kind)]
        if nested_blocks:
            suspects.append((node, nested_blocks))

    if not suspects:
        print("Aucune imbrication anormale detectee -- la structure du fichier semble saine.")
        return

    print(f"{len(suspects)} bloc(s) contiennent anormalement d'autres blocs du meme genre imbriques :")
    print()
    for node, nested in suspects:
        ident = block_identity(node)
        print(f"  {node.kind} [{ident}]  contient {len(nested)} bloc(s) imbrique(s) a tort :")
        for n in nested[:10]:
            print(f"      -> {n.kind} [{block_identity(n)}]")
        if len(nested) > 10:
            print(f"      ... et {len(nested) - 10} autre(s)")
        print()

    print("Cause probable : une ligne de fermeture '}' est restee commentee ('#}') lors d'une")
    print("edition manuelle. Le bloc liste ci-dessus n'a jamais ete correctement referme, donc")
    print("tout ce qui suit dans le fichier (jusqu'a la prochaine '}' non commentee) a ete")
    print("englouti comme si ca faisait partie de son contenu.")


if __name__ == "__main__":
    main()
