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

r"""
Diagnostic : verifie si mon parser retrouve un bloc precis (par Id) dans un fichier
.ecf, apres une edition manuelle (ex: decommenter un bloc en conflit d'Id).

UTILISATION :
    python cli/diagnostic_bloc.py "chemin\vers\BlocksConfig.ecf" 999999
    (999999 = l'Id que tu as donne au bloc)
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
from core.ecf.model import EcfBlock, EcfComment, block_identity


def main():
    if len(sys.argv) != 3:
        print("Usage: python cli/diagnostic_bloc.py <fichier.ecf> <Id>")
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
