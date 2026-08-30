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
import tempfile
from pathlib import Path
from typing import Optional


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


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Ecrit `data` dans `path` de maniere ATOMIQUE : le contenu est d'abord ecrit
    entierement dans un fichier temporaire DANS LE MEME DOSSIER (meme volume --
    os.replace ne sait pas traverser les volumes), synchronise sur le disque, puis
    renomme sur la destination via os.replace, qui est atomique sur Windows comme
    sur POSIX.

    Interet : avec un truncate-then-write classique, un crash ou une coupure
    d'alimentation PENDANT l'ecriture laisse le fichier coupe en deux (donnee de
    scenario ou de configuration irrecuperable). Avec ce helper, au pire l'ancienne
    version intacte est conservee, au mieux la nouvelle est complete -- jamais
    d'etat intermediaire. Le fichier temporaire est supprime en cas d'echec.

    Gere aussi l'attribut lecture seule de la destination (meme probleme que pour
    une ecriture directe -- cf. clear_readonly, que les appelants n'ont donc plus
    besoin d'appeler eux-memes avant d'ecrire).

    Leve OSError en cas d'echec (disque plein, destination verrouillee par un
    autre processus...) -- l'appelant affiche l'erreur comme avant."""
    path = Path(path)
    clear_readonly(path)

    tmp = tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=path.name + '.', suffix='.tmp', delete=False)
    tmp_path = Path(tmp.name)
    try:
        with tmp:
            tmp.write(data)
            tmp.flush()
            os.fsync(tmp.fileno())  # garantit que le contenu est bien sur le disque AVANT le renommage
        os.replace(tmp_path, path)
    except OSError:
        try:
            tmp_path.unlink()
        except OSError:
            pass  # le nettoyage du temporaire ne doit pas masquer l'erreur d'origine
        raise


def atomic_write_text(path: Path, text: str, encoding: str = 'utf-8') -> None:
    """Variante texte de atomic_write_bytes -- meme semantique qu'un
    `open(path, 'w', encoding=..., newline='')` : le texte est encode SANS
    traduction des fins de ligne, donc le contenu au disque est exactement la
    chaine passee (comportement requis pour le round-trip fidele des fichiers
    de scenario, voir core/ecf/model.py)."""
    atomic_write_bytes(path, text.encode(encoding))
