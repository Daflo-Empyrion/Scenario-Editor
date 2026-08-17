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
Utilitaire filesystem partage. Sert principalement a garantir qu'aucun fichier/dossier
ecrit par l'application n'herite d'un attribut lecture seule de sa source -- probleme
concret rencontre avec des scenarios installes sous Program Files (souvent marques
lecture seule par Windows) : `shutil.copy2`/`copytree` preservent les metadonnees par
defaut, ce qui rend la copie de travail elle-meme lecture seule (impossible a modifier
ou meme a supprimer -- Windows demande alors "l'autorisation" du proprietaire, meme si
c'est l'utilisateur courant).
"""
import os
import stat
from pathlib import Path


def clear_readonly(path: Path) -> None:
    """Retire l'attribut lecture seule sur `path`. Si c'est un dossier, le fait
    recursivement sur tout son contenu (fichiers ET sous-dossiers). Ignore les erreurs
    individuelles (fichier verrouille par un autre processus, etc.) plutot que de faire
    echouer toute l'operation pour un seul fichier problematique."""
    path = Path(path)
    if not path.exists():
        return

    def _unlock_one(p: Path) -> None:
        try:
            current = os.stat(p).st_mode
            os.chmod(p, current | stat.S_IWRITE | stat.S_IWUSR)
        except OSError:
            pass

    if path.is_dir():
        _unlock_one(path)
        for root, dirs, files in os.walk(path):
            for d in dirs:
                _unlock_one(Path(root) / d)
            for f in files:
                _unlock_one(Path(root) / f)
    else:
        _unlock_one(path)
