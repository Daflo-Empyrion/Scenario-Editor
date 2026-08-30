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
Construit l'archive data/tech_tree_icons.pak distribuee avec l'application
(voir core/tech_tree_icons.py) a partir d'un dossier d'icones EXTRAIT
MANUELLEMENT du jeu par l'utilisateur (session du 28/08/2026 -- ~70+ Mo non
filtres au depart).

DEUX MODES :
- Mode FILTRE (defaut) : n'embarque que les icones reellement referencees
  (CustomIcon ou Name) par les noeuds de l'arbre technologique d'un vrai
  BlocksConfig.ecf/ItemsConfig.ecf -- taille minimale. Limite : tout icone
  referencee par un scenario MAIS absente des fichiers vanilla passes au
  filtre manquera (icone generique dans l'arbre).
- Mode --all : embarque TOUTES les icones supportees du dossier (session du
  30/08/2026 : des scenarios moddes referenceient des icones hors du filtre
  vanilla, affichees en icone generique). Les Blocks/ItemsConfig ne sont pas
  requis dans ce mode. Taille nettement superieure, compensee par la
  compression LZMA (voir ci-dessous).

COMPRESSION : LZMA (zipfile.ZIP_LZMA), le plus compressif disponible dans la
bibliotheque standard -- sur des PNG deja compresses en interne, il gagne
encore ~10-20% sur deflate. Lisible nativement par zipfile (aucun changement
cote lecture, core/tech_tree_icons.py, ni d'extension .pak).

IMPORTANT -- propriete des assets : ces icones appartiennent a Eleon Game
Studios (Empyrion -- Galactic Survival). Ce script les empaquete UNIQUEMENT
pour l'affichage dans cet editeur (jamais modifiees : le contenu des fichiers
est stocke a l'identique, seule la compression du conteneur change), et inclut
un fichier NOTICE.txt d'attribution a l'interieur de l'archive -- voir
_NOTICE_TEXT ci-dessous. L'archive resultante n'est PAS une vraie protection
technique (le format est un simple ZIP renomme, le code source de lecture
est public dans ce depot) -- seulement un signal clair que ces fichiers ne
sont pas prevus pour etre extraits individuellement.

UTILISATION :
    python cli/pack_tech_tree_icons.py <dossier_icones> [--all] [BlocksConfig.ecf ItemsConfig.ecf] [--output CHEMIN]

    <dossier_icones>     : dossier contenant les PNG/JPG extraits du jeu
                            (recherche recursive, structure de sous-dossiers
                            quelconque)
    --all                : embarque TOUTES les icones du dossier, sans filtre
                            (Blocks/ItemsConfig alors facultatifs)
    <BlocksConfig.ecf>/<ItemsConfig.ecf> : (mode filtre) fichiers reels du jeu
                            (ou d'un scenario complet) servant a determiner la
                            liste des icones necessaires -- utiliser idealement
                            les fichiers vanilla complets du jeu pour une
                            couverture maximale, pas seulement un petit
                            scenario.
    --output CHEMIN       : chemin de sortie (defaut : data/tech_tree_icons.pak
                            a la racine du projet)
"""
import argparse
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli._bootstrap import ensure_core_importable
ensure_core_importable("core/tech_tree.py")

from core.tech_tree import load_tech_tree
from core.tech_tree_icons import _SUPPORTED_EXTENSIONS, ICON_PACK_NOTICE_MEMBER, ICON_PACK_FILENAME

_NOTICE_TEXT = """Icones de l'arbre technologique -- ATTRIBUTION

Ces images sont extraites du jeu Empyrion -- Galactic Survival et sont la
propriete d'Eleon Game Studios. Elles sont incluses dans cet editeur
UNIQUEMENT pour l'affichage dans le module Arbre technologique (menu
Fichier > Arbre technologique) -- elles n'ont pas ete modifiees (stockage
a l'identique, seule la compression du conteneur ZIP/LZMA change) et ne sont
pas destinees a etre extraites, redistribuees ou utilisees en dehors de cet
usage d'affichage.

Empyrion Scenario Editor n'est pas affilie a Eleon Game Studios.
"""


def _default_output_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / ICON_PACK_FILENAME


def build_pack(icons_dir: Path, blocks_path: Path, items_path: Path,
               output_path: Path, include_all: bool = False) -> None:
    """Construit l'archive d'icones. include_all=False (defaut) : mode filtre,
    uniquement les icones referencees par l'arbre technologique des fichiers
    Blocks/ItemsConfig fournis. include_all=True : TOUTES les icones supportees
    du dossier (blocks_path/items_path alors ignores)."""
    if not icons_dir.is_dir():
        print(f"ERREUR : dossier d'icones introuvable : {icons_dir}")
        sys.exit(1)

    found_by_key = {}
    if include_all:
        print(f"Indexation de {icons_dir} (mode --all : aucun filtrage)...")
        scanned = 0
        for p in icons_dir.rglob('*'):
            if p.is_file() and p.suffix.lower() in _SUPPORTED_EXTENSIONS:
                scanned += 1
                # Premiere occurrence gagne (comme en mode filtre)
                found_by_key.setdefault(p.stem.lower(), p)
        print(f"  {scanned} fichiers image scannes, {len(found_by_key)} icones distinctes retenues.")
    else:
        if blocks_path is None or items_path is None:
            print("ERREUR : le mode filtre (sans --all) exige BlocksConfig.ecf et ItemsConfig.ecf.")
            sys.exit(1)
        print(f"Lecture de l'arbre technologique ({blocks_path.name}, {items_path.name})...")
        tree = load_tech_tree(blocks_path if blocks_path.exists() else None,
                               items_path if items_path.exists() else None)
        needed_keys = {n.icon_key.lower() for n in tree.nodes if n.icon_key}
        print(f"  {len(needed_keys)} icones referencees par l'arbre technologique.")

        print(f"Indexation de {icons_dir}...")
        scanned = 0
        for p in icons_dir.rglob('*'):
            if p.is_file() and p.suffix.lower() in _SUPPORTED_EXTENSIONS:
                scanned += 1
                stem_lower = p.stem.lower()
                if stem_lower in needed_keys and stem_lower not in found_by_key:
                    found_by_key[stem_lower] = p
        print(f"  {scanned} fichiers image scannes, {len(found_by_key)}/{len(needed_keys)} icones necessaires trouvees.")

        missing = needed_keys - set(found_by_key.keys())
        if missing:
            print(f"  {len(missing)} icones necessaires INTROUVABLES dans {icons_dir} (repli generique restera utilise pour celles-ci).")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    # LZMA : le plus compressif de la stdlib -- sur des PNG (deja compresses en
    # interne) il gagne encore ~10-20% sur deflate max. Lu nativement par
    # zipfile : aucun impact cote application.
    with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_LZMA) as zf:
        zf.writestr(ICON_PACK_NOTICE_MEMBER, _NOTICE_TEXT)
        for key, path in sorted(found_by_key.items()):
            # Nom interne = cle normalisee + extension d'origine -- coherent
            # avec la resolution par nom (voir core.tech_tree_icons).
            member_name = key + path.suffix.lower()
            zf.write(path, arcname=member_name)

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"Archive ecrite : {output_path} ({size_mb:.1f} Mo, {len(found_by_key)} icones + NOTICE.txt)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Construit data/tech_tree_icons.pak a partir d'un dossier d'icones extrait du jeu.")
    parser.add_argument("icons_dir", type=Path, help="Dossier contenant les icones extraites (recherche recursive)")
    parser.add_argument("blocks_config", type=Path, nargs="?", default=None, help="Chemin vers BlocksConfig.ecf (mode filtre uniquement)")
    parser.add_argument("items_config", type=Path, nargs="?", default=None, help="Chemin vers ItemsConfig.ecf (mode filtre uniquement)")
    parser.add_argument("--all", action="store_true",
                        help="Embarque TOUTES les icones du dossier, sans filtrage par l'arbre technologique (Blocks/ItemsConfig alors facultatifs)")
    parser.add_argument("--output", type=Path, default=None, help="Chemin de sortie (defaut : data/tech_tree_icons.pak)")
    args = parser.parse_args()

    output_path = args.output or _default_output_path()
    build_pack(args.icons_dir, args.blocks_config, args.items_config, output_path,
               include_all=args.all)


if __name__ == "__main__":
    main()
