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
Gestion des fichiers de recuperation (sauvegarde automatique periodique des
onglets modifies mais pas encore enregistres) -- volontairement SEPARE de la
copie de travail reelle : jamais ecrit dans les vrais fichiers du scenario
tant que l'utilisateur ne clique pas explicitement sur Enregistrer. Le but
unique est de pouvoir restaurer du travail non enregistre apres un plantage
ou une fermeture inattendue.

Un dossier de recuperation distinct par scenario (racine de la copie de
travail), identifie par un hash court plutot que par le chemin complet
(portable, evite les soucis de caracteres speciaux/longueur de chemin sous
Windows). Un fichier metadata.json a la racine de chaque dossier garde le
vrai chemin, pour pouvoir l'afficher lisiblement a l'utilisateur.

IMPORTANT -- l'appelant est responsable d'appeler clear_recovery_file() des
qu'un onglet est enregistre avec succes : c'est ce qui garantit qu'un
fichier de recuperation encore present au demarrage represente forcement du
contenu JAMAIS ecrit dans la copie de travail (donc toujours legitime a
restaurer, jamais un risque d'ecraser une version plus recente)."""
import hashlib
import json
import time
from pathlib import Path
from typing import List, Optional

RECOVERY_ROOT = Path.home() / ".empyrion_editor" / "recovery"


def _scenario_recovery_dir(working_root: Path) -> Path:
    digest = hashlib.sha1(str(working_root.resolve()).encode("utf-8")).hexdigest()[:16]
    return RECOVERY_ROOT / digest


def _relative_safe_name(working_root: Path, file_path: Path) -> str:
    """Chemin relatif a la copie de travail, encode en un seul nom de fichier
    plat (remplace les separateurs) -- evite de recreer toute l'arborescence
    de sous-dossiers dans le dossier de recuperation."""
    try:
        rel = file_path.resolve().relative_to(working_root.resolve())
    except ValueError:
        rel = Path(file_path.name)
    return str(rel).replace("/", "__").replace("\\", "__")


def write_recovery_snapshot(working_root: Path, file_path: Path, content: str) -> None:
    """Enregistre l'etat actuel (non enregistre) d'un fichier -- ecrase le
    precedent instantane de ce meme fichier s'il existait deja."""
    scenario_dir = _scenario_recovery_dir(working_root)
    scenario_dir.mkdir(parents=True, exist_ok=True)

    meta_path = scenario_dir / "metadata.json"
    from .fsutil import atomic_write_text
    atomic_write_text(meta_path, json.dumps({
        "working_root": str(working_root.resolve()),
        "last_snapshot": time.time(),
    }))

    snapshot_path = scenario_dir / _relative_safe_name(working_root, file_path)
    atomic_write_text(snapshot_path, content)


def clear_recovery_file(working_root: Path, file_path: Path) -> None:
    """A appeler des qu'un fichier est enregistre avec succes dans la vraie
    copie de travail -- son instantane de recuperation n'a alors plus de
    raison d'etre (voir avertissement de tete de module)."""
    scenario_dir = _scenario_recovery_dir(working_root)
    snapshot_path = scenario_dir / _relative_safe_name(working_root, file_path)
    snapshot_path.unlink(missing_ok=True)
    _cleanup_if_empty(scenario_dir)


def clear_recovery_for_scenario(working_root: Path) -> None:
    """Supprime tout le dossier de recuperation d'un scenario -- apres une
    restauration traitee, ou un refus explicite de l'utilisateur."""
    import shutil
    scenario_dir = _scenario_recovery_dir(working_root)
    if scenario_dir.exists():
        shutil.rmtree(scenario_dir, ignore_errors=True)


def _cleanup_if_empty(scenario_dir: Path) -> None:
    if not scenario_dir.exists():
        return
    remaining = [p for p in scenario_dir.iterdir() if p.name != "metadata.json"]
    if not remaining:
        import shutil
        shutil.rmtree(scenario_dir, ignore_errors=True)


def list_recoverable_scenarios() -> List[dict]:
    """Parcourt le dossier racine de recuperation, retourne une entree par
    scenario ayant au moins un fichier recuperable (le metadata seul, sans
    fichier associe, ne compte pas -- peut arriver si clear_recovery_file()
    a nettoye le dernier fichier sans que _cleanup_if_empty() ait pu
    supprimer un metadata.json cree juste apres par une autre ecriture
    concurrente, cas limite rare mais gere par prudence)."""
    if not RECOVERY_ROOT.exists():
        return []
    results = []
    for scenario_dir in RECOVERY_ROOT.iterdir():
        if not scenario_dir.is_dir():
            continue
        meta_path = scenario_dir / "metadata.json"
        if not meta_path.exists():
            continue
        files = [p for p in scenario_dir.iterdir() if p.name != "metadata.json"]
        if not files:
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        results.append({
            "working_root": Path(meta["working_root"]),
            "last_snapshot": meta.get("last_snapshot"),
            "file_count": len(files),
        })
    return results


def list_recovery_files(working_root: Path) -> List[str]:
    """Noms encodes (voir _relative_safe_name) des fichiers recuperables
    d'un scenario -- pour affichage/restauration."""
    scenario_dir = _scenario_recovery_dir(working_root)
    if not scenario_dir.exists():
        return []
    return sorted(p.name for p in scenario_dir.iterdir() if p.name != "metadata.json")


def decode_relative_name(encoded_name: str) -> Path:
    """Inverse de _relative_safe_name -- reconstruit le chemin relatif reel a
    partir du nom de fichier plat stocke dans le dossier de recuperation."""
    return Path(encoded_name.replace("__", "/"))


def read_recovery_content(working_root: Path, encoded_name: str) -> Optional[str]:
    scenario_dir = _scenario_recovery_dir(working_root)
    snapshot_path = scenario_dir / encoded_name
    if not snapshot_path.exists():
        return None
    return snapshot_path.read_text(encoding="utf-8")
