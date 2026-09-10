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

"""Sauvegardes versionnees automatiques de la copie de travail (demande du
10/09/2026) : a chaque enregistrement reussi, le fichier ecrit est copie
dans ~/.empyrion_editor/backups/<scenario>/<horodatage>/<chemin encode>.
Rotation : seuls les N horodatages les plus recents sont conserves (reglage
versioned_backup_keep, defaut 15) -- les plus anciens sont supprimes a
chaque nouveau snapshot. Dossier SEPARE de la recuperation autosave (qui
elle, n'a qu'une generation) et des backups manuels de l'utilisateur."""

import shutil
import time
from pathlib import Path
from typing import List

from core.settings import CONFIG_DIR

BACKUPS_ROOT = Path(CONFIG_DIR) / "backups"
DEFAULT_KEEP = 15


def _safe_relative(working_root: Path, file_path: Path) -> str:
    """Chemin relatif encode (meme principe que core.autosave : les separateurs
    et caracteres risques deviennent un nom de fichier unique sur une seule
    profondeur)."""
    try:
        rel = Path(file_path).resolve().relative_to(Path(working_root).resolve())
    except ValueError:
        rel = Path(Path(file_path).name)
    return "__".join(rel.parts).replace(":", "_")


def snapshot_file(working_root: Path, file_path: Path, keep: int = DEFAULT_KEEP) -> Path:
    """Copie l'etat ACTUEL (post-enregistrement) de file_path dans un dossier
    horodatage du scenario, puis applique la rotation. Retourne le chemin de
    la copie ; no-op silencieux si la source n'existe pas."""
    working_root = Path(working_root)
    file_path = Path(file_path)
    if not file_path.exists():
        return None
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest_dir = BACKUPS_ROOT / working_root.name / stamp
    dest = dest_dir / _safe_relative(working_root, file_path)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(file_path, dest)
    rotate(working_root.name, keep)
    return dest


def restore_latest(working_root: Path, file_path: Path) -> Path:
    """Restaure la plus recente sauvegarde de file_path par-dessus le fichier
    courant (apres que l'appelant ait fait sa propre capture d'undo).
    Retourne le chemin de la source restauree, ou None si aucune."""
    working_root = Path(working_root)
    rel = _safe_relative(working_root, file_path)
    scenario_dir = BACKUPS_ROOT / working_root.name
    if not scenario_dir.exists():
        return None
    for stamp_dir in sorted(scenario_dir.iterdir(), reverse=True):
        candidate = stamp_dir / rel
        if candidate.exists():
            shutil.copy2(candidate, file_path)
            return candidate
    return None


def rotate(scenario_name: str, keep: int = DEFAULT_KEEP) -> List[Path]:
    """Ne garde que les `keep` horodatages les plus recents du scenario.
    Retourne la liste des dossiers supprimes."""
    scenario_dir = BACKUPS_ROOT / scenario_name
    if not scenario_dir.exists():
        return []
    stamp_dirs = sorted((d for d in scenario_dir.iterdir() if d.is_dir()),
                        reverse=True)
    removed = []
    for old in stamp_dirs[keep:]:
        shutil.rmtree(old, ignore_errors=True)
        removed.append(old)
    return removed
