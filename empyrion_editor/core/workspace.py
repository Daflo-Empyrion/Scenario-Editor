"""
Gestion de l'espace de travail (Workspace) : un scenario source A (lecture seule), un
scenario source B optionnel (lecture seule, pour la fusion), et une COPIE DE TRAVAIL
physique -- un scenario complet, copie sur disque a un nouvel emplacement -- qui est le
seul scenario modifiable. Les sources A et B ne sont jamais touchees.
"""
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .scanner import scan_scenario
from .models import Scenario


@dataclass
class Workspace:
    source_a: Scenario
    source_a_root: Path
    working: Scenario
    working_root: Path
    source_b: Optional[Scenario] = None
    source_b_root: Optional[Path] = None

    @property
    def is_merge_mode(self) -> bool:
        return self.source_b is not None

    def rescan_working(self) -> None:
        """A appeler apres toute modification physique de la copie de travail (ex:
        copie d'un fichier depuis une source) pour rafraichir l'inventaire."""
        self.working = scan_scenario(self.working_root)


def create_working_copy(source_root: Path, dest_root: Path) -> Path:
    """Copie physiquement TOUT le contenu du scenario source vers un nouvel
    emplacement, qui devient la copie de travail modifiable. Le dossier de destination
    ne doit pas deja exister (securite : on ne veut jamais ecraser quoi que ce soit par
    erreur)."""
    if dest_root.exists():
        raise FileExistsError(f"Le dossier de destination existe deja : {dest_root}")
    shutil.copytree(source_root, dest_root, copy_function=shutil.copy2)
    return dest_root


def open_workspace(source_a_root: Path, working_dest: Path,
                    source_b_root: Optional[Path] = None) -> Workspace:
    """Cree la copie de travail a partir de la source A, scanne les scenarios
    concernes, et retourne le Workspace pret a l'emploi."""
    source_a = scan_scenario(source_a_root)
    create_working_copy(source_a_root, working_dest)
    working = scan_scenario(working_dest)
    source_b = scan_scenario(source_b_root) if source_b_root else None
    return Workspace(
        source_a=source_a, source_a_root=source_a_root,
        working=working, working_root=working_dest,
        source_b=source_b, source_b_root=source_b_root,
    )


def copy_file_into_working(workspace: Workspace, source_file: Path, source_root: Path) -> Path:
    """Copie un fichier (mesh, icone, ECF, YAML...) depuis une source (A ou B) vers la
    copie de travail, en preservant son chemin relatif. Cree les dossiers intermediaires
    si besoin. Retourne le chemin de destination."""
    rel = source_file.relative_to(source_root)
    dest = workspace.working_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_file, dest)
    return dest
