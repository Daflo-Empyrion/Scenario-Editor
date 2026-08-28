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
Pile d'annulation GLOBALE au niveau de l'espace de travail -- couvre toute action qui
touche au systeme de fichiers de la copie de travail : fusion (fichier/dossier/bloc/
ligne/entree), duplication, suppression, traduction, activation d'un bloc en attente.

Complementaire (pas un remplacement) de l'annulation "en session" deja presente dans
chaque editeur ouvert (EcfEditWidget.undo() etc, qui n'agit que sur un fichier en cours
d'edition dans un onglet) : celle-ci agit sur TOUTE action qui ecrit sur le disque,
meme sans avoir ouvert le fichier concerne.

Principe : avant chaque operation qui va modifier un ou plusieurs fichiers de la copie
de travail, on capture leur etat EXACT (contenu binaire, ou absence) ; annuler restaure
cet etat tel quel. Fiable par construction (pas de reconstruction logique fragile),
au prix d'un peu de memoire -- largement acceptable pour des fichiers de configuration
de scenario (texte, quelques Ko a quelques Mo), pile plafonnee pour eviter toute derive.
"""
import shutil
from pathlib import Path
from typing import Optional, Dict, List

from core.constants import UNDO_STACK_MAX_DEPTH


class UndoAction:
    def undo(self) -> None:
        raise NotImplementedError

    def describe(self) -> str:
        raise NotImplementedError


class FileStateUndo(UndoAction):
    """Restaure UN fichier a son etat (contenu, ou absence) d'avant l'operation."""

    def __init__(self, path: Path, prior_bytes: Optional[bytes], label: str):
        self.path = Path(path)
        self.prior_bytes = prior_bytes
        self.label = label

    def undo(self) -> None:
        if self.prior_bytes is None:
            if self.path.exists():
                self.path.unlink()
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_bytes(self.prior_bytes)

    def describe(self) -> str:
        return self.label


class MultiFileStateUndo(UndoAction):
    """Restaure PLUSIEURS fichiers d'un coup (une fusion de dossier ou de bloc peut
    toucher de nombreux fichiers en une seule action utilisateur -- on veut qu'une
    seule 'Annuler' revienne sur tout, pas fichier par fichier)."""

    def __init__(self, entries: List[FileStateUndo], label: str):
        self.entries = entries
        self.label = label

    def undo(self) -> None:
        for entry in self.entries:
            entry.undo()

    def describe(self) -> str:
        return self.label


class FolderStateUndo(UndoAction):
    """Restaure un dossier ENTIER (utilise pour la suppression de dossier -- capture
    tout son contenu avant suppression)."""

    def __init__(self, folder: Path, existed_before: bool, prior_files: Dict[str, bytes], label: str):
        self.folder = Path(folder)
        self.existed_before = existed_before
        self.prior_files = prior_files
        self.label = label

    def undo(self) -> None:
        if self.folder.exists():
            shutil.rmtree(self.folder)
        if self.existed_before:
            for rel, data in self.prior_files.items():
                dest = self.folder / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)

    def describe(self) -> str:
        return self.label


class WorkspaceUndoStack:
    def __init__(self, max_depth: int = UNDO_STACK_MAX_DEPTH):
        self._stack: List[UndoAction] = []
        self.max_depth = max_depth

    def push(self, action: UndoAction) -> None:
        self._stack.append(action)
        if len(self._stack) > self.max_depth:
            self._stack.pop(0)

    def can_undo(self) -> bool:
        return bool(self._stack)

    def peek_label(self) -> str:
        return self._stack[-1].describe() if self._stack else ""

    def all_labels(self) -> list:
        """Description de TOUTES les actions en memoire, de la plus ancienne a la
        plus recente -- utilise notamment par le rapport de bug (voir
        gui/report_issue_dialog.py) pour donner un contexte des dernieres actions
        effectuees avant le probleme signale."""
        return [action.describe() for action in self._stack]

    def undo(self) -> Optional[str]:
        if not self._stack:
            return None
        action = self._stack.pop()
        action.undo()
        return action.describe()

    def clear(self) -> None:
        self._stack.clear()


def capture_file(path: Path) -> Optional[bytes]:
    """Capture le contenu d'un fichier avant modification -- None si le fichier
    n'existe pas encore (l'annulation saura alors qu'il faut le supprimer)."""
    path = Path(path)
    return path.read_bytes() if path.exists() else None


def capture_folder(folder: Path) -> tuple:
    """Capture tout le contenu d'un dossier avant suppression/fusion.
    Retourne (existait_avant: bool, {chemin_relatif: contenu})."""
    folder = Path(folder)
    if not folder.exists():
        return False, {}
    files = {}
    for p in folder.rglob('*'):
        if p.is_file():
            files[str(p.relative_to(folder))] = p.read_bytes()
    return True, files
