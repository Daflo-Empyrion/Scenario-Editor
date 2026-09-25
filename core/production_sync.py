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

"""Synchronisation de la copie de travail vers le scenario EN PRODUCTION
(demande utilisateur 24/09/2026 : eviter de copier a la main, a chaque
fermeture, les fichiers modifies vers le repertoire Scenarios de la
vanille). La liste des fichiers vient de list_changed_files (diff vs
source A, meme semantique que le dialogue « Fichiers modifies »)."""
import shutil
from pathlib import Path
from typing import List, Optional, Sequence, Tuple


def find_default_production_root(vanilla_content: str,
                                 working_root) -> Optional[Path]:
    """Scenario de production deduit du nom : <vanille>/Content/Scenarios/
    <nom de la copie de travail> (insensible a la casse). None sinon —
    l'utilisateur choisira le dossier a la main (persiste ensuite)."""
    if not vanilla_content or not working_root:
        return None
    scenarios = Path(vanilla_content) / "Scenarios"
    if not scenarios.is_dir():
        return None
    name = Path(working_root).name.lower()
    for entry in sorted(scenarios.iterdir()):
        if entry.is_dir() and entry.name.lower() == name:
            return entry
    return None


def sync_to_production(files: Sequence[Tuple], working_root, prod_root,
                       backup_dir=None) -> Tuple[int, Optional[Path]]:
    """Copie (remplace) `files` — [(chemin_source, etat), ...] produits par
    list_changed_files — vers prod_root en conservant l'arborescence.
    Chaque fichier ecrase est sauvegarde au prealable sous backup_dir
    (meme arborescence relative). Retourne (copies, racine_sauvegarde)."""
    working_root, prod_root = Path(working_root), Path(prod_root)
    copied = 0
    saved_root: Optional[Path] = None
    for src, _state in files:
        src = Path(src)
        rel = src.relative_to(working_root)
        dest = prod_root / rel
        if backup_dir is not None and dest.exists():
            backup_path = Path(backup_dir) / rel
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dest, backup_path)
            saved_root = Path(backup_dir)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied += 1
    return copied, saved_root
