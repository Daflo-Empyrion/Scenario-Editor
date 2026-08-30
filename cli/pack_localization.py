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
Construit l'archive data/localization_vanilla.pak distribuee avec
l'application (voir core/localization_lookup.py) a partir d'un vrai
Localization.csv VANILLA du jeu (session du 29/08/2026) -- le
Localization.csv d'un SCENARIO ne contient que les cles ajoutees/modifiees
par ce scenario, pas l'integralite du jeu de base ; ce pack vanilla sert de
repli complet pour toute cle absente du scenario.

Contrairement a cli/pack_tech_tree_icons.py, AUCUN FILTRAGE par usage n'est
applique ici : le fichier est embarque en ENTIER (juste compresse) -- les
cles necessaires (noms de blocs/items, labels de proprietes, textes d'aide
'Info:') sont trop nombreuses et trop variees (n'importe quel scenario peut
referencer n'importe quel bloc/item du jeu de base) pour etre pre-filtrees de
maniere fiable sans risquer d'en omettre.

IMPORTANT -- propriete des donnees : ce fichier appartient a Eleon Game
Studios (Empyrion -- Galactic Survival). Empaquete UNIQUEMENT pour l'affichage
dans cet editeur (jamais modifie), avec un fichier NOTICE.txt d'attribution a
l'interieur de l'archive -- voir _NOTICE_TEXT.

UTILISATION :
    python cli/pack_localization.py <Localization.csv> [--output CHEMIN]
"""
import argparse
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli._bootstrap import ensure_core_importable
ensure_core_importable("core/localization_lookup.py")

from core.localization_lookup import LOCALIZATION_PACK_FILENAME, LOCALIZATION_PACK_NOTICE_MEMBER, LOCALIZATION_PACK_CSV_MEMBER

_NOTICE_TEXT = """Localization.csv vanilla -- ATTRIBUTION

Ce fichier est extrait du jeu Empyrion -- Galactic Survival et est la
propriete d'Eleon Game Studios. Il est inclus dans cet editeur UNIQUEMENT
pour l'affichage (noms de blocs/items, labels de proprietes, textes d'aide)
dans les differents modules de l'editeur -- il n'a pas ete modifie et n'est
pas destine a etre extrait, redistribue ou utilise en dehors de cet usage
d'affichage.

Empyrion Scenario Editor n'est pas affilie a Eleon Game Studios.
"""


def _default_output_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / LOCALIZATION_PACK_FILENAME


def build_pack(csv_path: Path, output_path: Path) -> None:
    if not csv_path.is_file():
        print(f"ERREUR : fichier introuvable : {csv_path}")
        sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr(LOCALIZATION_PACK_NOTICE_MEMBER, _NOTICE_TEXT)
        zf.write(csv_path, arcname=LOCALIZATION_PACK_CSV_MEMBER)

    original_mb = csv_path.stat().st_size / (1024 * 1024)
    packed_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"Archive ecrite : {output_path} ({original_mb:.1f} Mo -> {packed_mb:.1f} Mo compresse)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Construit data/localization_vanilla.pak a partir d'un Localization.csv vanilla.")
    parser.add_argument("csv_path", type=Path, help="Chemin vers le Localization.csv vanilla du jeu")
    parser.add_argument("--output", type=Path, default=None, help="Chemin de sortie (defaut : data/localization_vanilla.pak)")
    args = parser.parse_args()

    output_path = args.output or _default_output_path()
    build_pack(args.csv_path, output_path)


if __name__ == "__main__":
    main()
