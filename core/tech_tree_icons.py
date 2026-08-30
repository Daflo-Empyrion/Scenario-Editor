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
Resolution des fichiers d'icone pour l'arbre technologique. TROIS sources,
recherchees dans cet ordre (la premiere qui contient l'icone gagne -- la plus
prioritaire est indexee EN DERNIER, voir build_icon_index) :

1. SharedData/Content/Bundles/ItemIcons, relatif a la racine de la copie de
   travail -- dossier propre au SCENARIO (indique par l'utilisateur, session
   du 28/08/2026). Prioritaire : une icone personnalisee/moddee par le
   scenario doit l'emporter sur toute icone vanilla.
2. itemicons/ a la racine du PROJET (pas du scenario, PAS versionne, voir
   .gitignore) -- assets du jeu extraits MANUELLEMENT par l'utilisateur en
   dev (~70+ Mo, dossier complet non filtre). Confort de developpement
   uniquement, jamais distribue avec l'application.
3. data/tech_tree_icons.pak -- archive ZIP FILTREE (seules les icones
   reellement referencees par un vrai BlocksConfig.ecf/ItemsConfig.ecf) et
   ATTRIBUEE (voir NOTICE.txt a l'interieur), generee par
   cli/pack_tech_tree_icons.py et distribuee avec l'application (voir
   empyrion_editor.spec, deja inclus via le dossier data/). C'est la source
   dont beneficient tous les utilisateurs, meme sans dossier itemicons/ local
   ni SharedData/ItemIcons dans leur scenario -- LA PROPRIETE DE CES ICONES
   RESTE A ELEON GAME STUDIOS (Empyrion -- Galactic Survival) : incluses
   UNIQUEMENT pour l'affichage dans cet editeur, jamais modifiees, jamais
   extraites sur disque ni redistribuees en tant qu'assets autonomes (lues en
   memoire directement depuis l'archive, voir load_icon_bytes).

Le format exact des fichiers (extension) n'a pas ete verifie sur un vrai
dossier ItemIcons -- la recherche est donc VOLONTAIREMENT tolerante : elle
scanne le contenu reel (recursivement pour les dossiers, la structure exacte
d'une extraction d'assets n'etant pas garantie) plutot que de supposer une
extension fixe (.png/.dds/...), et compare les noms en case-insensitive.
"""
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

ICON_SUBPATH = ("SharedData", "Content", "Bundles", "ItemIcons")
BUNDLED_ICON_DIRNAME = "itemicons"
ICON_PACK_FILENAME = "tech_tree_icons.pak"
ICON_PACK_NOTICE_MEMBER = "NOTICE.txt"

# Extensions que QPixmap sait charger nativement -- une icone dans un format
# non supporte (ex: .dds brut, non convertie) sera silencieusement ignoree au
# profit du repli generique plutot que de planter l'ouverture de l'arbre.
_SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif"}


@dataclass(frozen=True)
class IconRef:
    """Reference vers une icone, sans en charger le contenu -- soit un
    fichier reel sur disque (kind='file'), soit un membre d'une archive .pak
    (kind='archive', voir load_icon_bytes ci-dessous pour la lecture en
    memoire, sans jamais extraire l'archive)."""
    kind: str  # 'file' ou 'archive'
    path: Path  # chemin du fichier, ou de l'archive .pak
    member: Optional[str] = None  # nom interne dans l'archive (kind='archive' uniquement)


def load_icon_bytes(ref: IconRef) -> Optional[bytes]:
    """Lit le contenu binaire d'une icone -- directement EN MEMOIRE pour les
    icones d'archive (jamais extraites sur disque, voir docstring du module).
    Retourne None si la lecture echoue (fichier/archive deplace, corrompu...)
    -- l'appelant doit alors utiliser l'icone generique de repli."""
    try:
        if ref.kind == 'file':
            return ref.path.read_bytes()
        with zipfile.ZipFile(ref.path) as zf:
            return zf.read(ref.member)
    except (OSError, KeyError, zipfile.BadZipFile):
        return None


def icon_directory(working_root: Path) -> Optional[Path]:
    """Chemin du dossier d'icones propre au scenario, s'il existe reellement
    dans la copie de travail, sinon None."""
    candidate = working_root.joinpath(*ICON_SUBPATH)
    return candidate if candidate.is_dir() else None


def bundled_icon_directory() -> Optional[Path]:
    """Chemin du dossier itemicons/ (dev uniquement, non distribue) a la
    racine du projet, s'il existe reellement, sinon None."""
    if getattr(sys, 'frozen', False):
        return None  # dossier dev uniquement -- jamais present dans un build
    candidate = Path(__file__).resolve().parent.parent / BUNDLED_ICON_DIRNAME
    return candidate if candidate.is_dir() else None


def icon_pack_path() -> Optional[Path]:
    """Chemin de l'archive distribuee data/tech_tree_icons.pak, s'il existe
    reellement, sinon None -- meme logique dev/frozen que
    core.resource_loading.resolve_data_path."""
    if getattr(sys, 'frozen', False):
        candidate = Path(sys._MEIPASS) / "data" / ICON_PACK_FILENAME
        return candidate if candidate.is_file() else None
    candidate = Path(__file__).resolve().parent.parent / "data" / ICON_PACK_FILENAME
    return candidate if candidate.is_file() else None


def _scan_directory(directory: Path) -> Dict[str, IconRef]:
    """Index {nom_sans_extension.lower(): IconRef} pour tout le contenu d'un
    dossier, recursivement (voir docstring du module)."""
    index: Dict[str, IconRef] = {}
    try:
        for p in directory.rglob('*'):
            if p.is_file() and p.suffix.lower() in _SUPPORTED_EXTENSIONS:
                index.setdefault(p.stem.lower(), IconRef(kind='file', path=p))
    except OSError:
        return {}
    return index


def _scan_archive(archive_path: Path) -> Dict[str, IconRef]:
    """Index {nom_sans_extension.lower(): IconRef} pour le contenu d'une
    archive .pak -- ignore NOTICE.txt et toute entree hors extensions
    supportees."""
    index: Dict[str, IconRef] = {}
    try:
        with zipfile.ZipFile(archive_path) as zf:
            for member in zf.namelist():
                if member == ICON_PACK_NOTICE_MEMBER:
                    continue
                suffix = Path(member).suffix.lower()
                if suffix in _SUPPORTED_EXTENSIONS:
                    stem = Path(member).stem.lower()
                    index.setdefault(stem, IconRef(kind='archive', path=archive_path, member=member))
    except (OSError, zipfile.BadZipFile):
        return {}
    return index


def build_icon_index(working_root: Path) -> Dict[str, IconRef]:
    """Construit UNE FOIS un index fusionne des trois sources (voir docstring
    du module) -- evite de relister/rouvrir les sources a chaque noeud de
    l'arbre. Indexe de la MOINS prioritaire a la PLUS prioritaire (chaque
    etape ecrase les collisions de la precedente) : archive distribuee ->
    dossier dev itemicons/ -> dossier propre au scenario. Retourne un dict
    vide si aucune des trois sources n'existe."""
    index: Dict[str, IconRef] = {}

    pack = icon_pack_path()
    if pack is not None:
        index.update(_scan_archive(pack))

    bundled = bundled_icon_directory()
    if bundled is not None:
        index.update(_scan_directory(bundled))

    scenario_dir = icon_directory(working_root)
    if scenario_dir is not None:
        index.update(_scan_directory(scenario_dir))

    return index


def resolve_icon_path(icon_index: Dict[str, IconRef], icon_key: str) -> Optional[IconRef]:
    """Cherche icon_key (CustomIcon ou Name, voir core.tech_tree) dans l'index
    construit par build_icon_index(). Retourne None si absent -- l'appelant
    doit alors utiliser une icone generique de repli (voir
    gui/tech_tree_widget.py), jamais planter ni laisser une case vide."""
    return icon_index.get(icon_key.lower())
