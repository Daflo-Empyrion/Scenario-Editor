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
vanille). La liste des fichiers est une DIFFERENCE AVEC LE DOSSIER DE
PRODUCTION passe en argument (le dialogue passe le dossier de production,
PAS la source A -- docstring erronee corrigee le 26/09/2026 apres vecu :
un sync vs source A n'aurait jamais liste les fichiers identiques a A
mais absents ou anciens dans la production)."""
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


def list_extra_files(working_root, prod_root) -> List[Path]:
    """Fichiers presents en PRODUCTION SEULEMENT — a supprimer pour que la
    production reste le miroir fidele de la copie de travail (vecu 05/10 :
    l'ancien etat du scenario y laissait des fichiers que le jeu servait
    encore). Exclus : *.yaml.bin (caches compiles du jeu, regeneres a la
    volee) et *.bak (sauvegardes, inertes)."""
    working_root, prod_root = Path(working_root), Path(prod_root)
    extra: List[Path] = []
    for path in sorted(prod_root.rglob('*')):
        if not path.is_file():
            continue
        if path.name.lower().endswith('.yaml.bin') \
                or path.suffix.lower() == '.bak':
            continue
        rel = path.relative_to(prod_root)
        if not (working_root / rel).exists():
            extra.append(path)
    return extra


def sync_to_production(files: Sequence[Tuple], working_root, prod_root,
                       backup_dir=None,
                       delete_files: Sequence = ()) -> Tuple[
        int, int, int, Optional[Path]]:
    """Copie (remplace) `files` — [(chemin_source, etat), ...] produits par
    list_changed_files — vers prod_root en conservant l'arborescence, puis
    supprime `delete_files` (chemins production, produits par
    list_extra_files). Chaque fichier ecrase OU supprime est sauvegarde au
    prealable sous backup_dir (meme arborescence relative). Retourne
    (copies, supprimes, bins_invalides, racine_sauvegarde).
    Les *.yaml.bin ne sont JAMAIS copies (caches compiles du jeu) et le
    cache d'un yaml Playfields copie est INVALIDE : copy2 conserve le
    vieux mtime du yaml, le jeu jugeait son .bin « plus frais » et
    servait un playfield PERIME (vecu 05/10 : missions cassees jusqu'a la
    suppression manuelle complete du dossier de production). Les caches
    orphelins sous Playfields (yaml supprime/renomme) sont supprimes.
    Une erreur OSError est re-levee AVEC le fichier fautif (vecu 26/09 :
    l'utilisateur ne voyait PAS quel fichier faisait echouer la copie)."""
    working_root, prod_root = Path(working_root), Path(prod_root)
    copied = deleted = bins = 0
    saved_root: Optional[Path] = None

    def _backup(dest: Path, rel: Path) -> None:
        nonlocal saved_root
        if backup_dir is None or not dest.exists():
            return
        backup_path = Path(backup_dir) / rel
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dest, backup_path)
        saved_root = Path(backup_dir)

    for src, _state in files:
        src = Path(src)
        if src.name.lower().endswith('.yaml.bin'):
            continue          # cache compile du jeu : jamais synchronise
        rel = src.relative_to(working_root)
        dest = prod_root / rel
        try:
            _backup(dest, rel)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            if rel.as_posix().lower().startswith('playfields/') \
                    and src.name.lower().endswith('.yaml'):
                cache = dest.with_name(dest.name + '.bin')
                if cache.exists():
                    cache.unlink()
                    bins += 1
        except OSError as e:
            raise OSError(f"{src} -> {dest} : {e}") from e
        copied += 1
    for path in delete_files:
        path = Path(path)
        try:
            _backup(path, path.relative_to(prod_root))
            path.unlink()
        except OSError as e:
            raise OSError(f"{path} : {e}") from e
        deleted += 1
    playfields = prod_root / "Playfields"
    if playfields.is_dir():
        for cache in sorted(playfields.rglob('*.yaml.bin')):
            if not cache.with_name(cache.name[:-4]).exists():
                try:
                    _backup(cache, cache.relative_to(prod_root))
                    cache.unlink()
                except OSError as e:
                    raise OSError(f"{cache} : {e}") from e
                bins += 1
    return copied, deleted, bins, saved_root
