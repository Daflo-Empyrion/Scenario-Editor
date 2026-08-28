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
Fusionne plusieurs fichiers .ecf selon un ordre de priorite (la premiere source citee
gagne en cas de conflit), et ecrit le resultat dans un nouveau fichier.

UTILISATION :
    python merge_ecf.py sortie.ecf source1.ecf source2.ecf source3.ecf ...
    python merge_ecf.py sortie.ecf source1.ecf source2.ecf --mode properties

    source1.ecf = la plus prioritaire (gagne les conflits)
    source2.ecf, source3.ecf, ... = par ordre de priorite decroissante

MODES :
    block      (par defaut) : en cas de conflit, le bloc ENTIER vient de la source
               la plus prioritaire qui le possede. Le plus sur.
    properties : fusion propriete par propriete -- une propriete manquante dans la
               source prioritaire est completee depuis une source moins prioritaire.
"""
import sys
from pathlib import Path

# Rend le paquet cli/ (et donc cli._bootstrap) importable meme quand ce script
# est lance DIRECTEMENT (python cli/xxx.py), auquel cas cli/ -- pas la racine du
# projet -- serait sinon le premier dossier sur sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli._bootstrap import ensure_core_importable
ensure_core_importable("core/ecf/merge.py")
from core.ecf.parser import parse_ecf_file
from core.ecf.merge import merge_documents, format_report


def main():
    args = sys.argv[1:]
    mode = 'block'
    if '--mode' in args:
        idx = args.index('--mode')
        mode = args[idx + 1]
        del args[idx:idx + 2]

    if len(args) < 3:
        print(__doc__)
        sys.exit(1)

    output_path = Path(args[0])
    source_paths = [Path(p) for p in args[1:]]

    for p in source_paths:
        if not p.exists():
            print(f"ERREUR : fichier introuvable : {p}")
            sys.exit(1)

    print(f"Fusion de {len(source_paths)} source(s), mode='{mode}' :")
    for i, p in enumerate(source_paths):
        rank = "priorite la plus haute" if i == 0 else f"priorite #{i + 1}"
        print(f"  {i + 1}. {p.name}  ({rank})")
    print()

    sources = [(p.name, parse_ecf_file(p)) for p in source_paths]
    result = merge_documents(sources, mode=mode)

    print("=" * 60)
    print("RAPPORT DE FUSION")
    print("=" * 60)
    print(format_report(result))
    print()

    if output_path.exists():
        confirm = input(f"{output_path} existe deja. Ecraser ? (o/N) ")
        if confirm.lower() != 'o':
            print("Annule.")
            return
    else:
        confirm = input(f"Ecrire le resultat dans {output_path} ? (o/N) ")
        if confirm.lower() != 'o':
            print("Annule.")
            return

    rendered = result.document.render()
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        f.write(rendered)

    print(f"Fusion ecrite : {output_path}")


if __name__ == "__main__":
    main()
