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
Sauvegarde/restauration generique de dossiers complets -- utilise pour deux besoins :

  - 'scenario' : garder une copie de la version vanille d'un scenario juste avant une
    mise a jour (le Workshop Steam ecrase le dossier original en place a la mise a
    jour), pour pouvoir ensuite comparer l'ancienne et la nouvelle version avec la
    fonction de comparaison de scenarios.
  - 'savegame' : garder des copies de la progression de partie, avec restauration
    possible si une mise a jour de scenario casse la sauvegarde en cours.

Chaque sauvegarde est un dossier horodate contenant une copie integrale de la source,
plus un petit fichier _backup_info.json avec les metadonnees (source d'origine, date,
nom donne par l'utilisateur, type).
"""
import json
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .fsutil import clear_readonly

logger = logging.getLogger(__name__)

INFO_FILENAME = "_backup_info.json"


@dataclass
class BackupRecord:
    backup_path: Path
    label: str
    source_path: str
    created_at: str  # ISO 8601
    kind: str  # 'scenario' | 'savegame'

    def content_path(self) -> Path:
        """Le contenu copie vit dans un sous-dossier 'content' -- evite toute ambiguite
        avec le fichier _backup_info.json lui-meme lors d'une restauration."""
        return self.backup_path / "content"

    def display_name(self) -> str:
        dt = self.created_at.replace("T", " ")[:19]
        return f"{self.label}  --  {dt}"


def _sanitize_label(label: str) -> str:
    safe = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in label)
    return safe.strip().replace(' ', '_')[:60] or "sauvegarde"


def create_backup(source: Path, backup_root: Path, label: Optional[str], kind: str) -> BackupRecord:
    """Copie integralement `source` dans un nouveau sous-dossier horodate de
    `backup_root`. Leve une exception si `source` n'existe pas."""
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(f"La source n'existe pas : {source}")

    backup_root = Path(backup_root)
    backup_root.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now()
    ts_str = timestamp.strftime("%Y-%m-%d_%Hh%M")
    label = label.strip() if label and label.strip() else source.name
    folder_name = f"{ts_str}__{_sanitize_label(label)}"

    backup_path = backup_root / folder_name
    n = 1
    while backup_path.exists():
        n += 1
        backup_path = backup_root / f"{folder_name}_{n}"

    content_path = backup_path / "content"
    shutil.copytree(source, content_path)
    clear_readonly(content_path)

    record = BackupRecord(
        backup_path=backup_path,
        label=label,
        source_path=str(source),
        created_at=timestamp.isoformat(),
        kind=kind,
    )
    info = {
        'label': record.label,
        'source_path': record.source_path,
        'created_at': record.created_at,
        'kind': record.kind,
    }
    from .fsutil import atomic_write_text
    atomic_write_text(backup_path / INFO_FILENAME,
                      json.dumps(info, ensure_ascii=False, indent=2))

    return record


def list_backups(backup_root: Path, kind: Optional[str] = None) -> List[BackupRecord]:
    """Liste les sauvegardes presentes dans `backup_root`, triees de la plus recente a
    la plus ancienne. Ignore silencieusement les sous-dossiers qui ne sont pas des
    sauvegardes valides (pas de _backup_info.json lisible)."""
    backup_root = Path(backup_root)
    if not backup_root.exists():
        return []

    records = []
    for entry in backup_root.iterdir():
        if not entry.is_dir():
            continue
        info_file = entry / INFO_FILENAME
        if not info_file.exists():
            continue
        try:
            info = json.loads(info_file.read_text(encoding='utf-8'))
            record = BackupRecord(
                backup_path=entry,
                label=info.get('label', entry.name),
                source_path=info.get('source_path', ''),
                created_at=info.get('created_at', ''),
                kind=info.get('kind', 'scenario'),
            )
            if kind is None or record.kind == kind:
                records.append(record)
        except Exception as e:
            logger.debug('Backup invalide ignore : %s', e)
            continue

    records.sort(key=lambda r: r.created_at, reverse=True)
    return records


def restore_backup(record: BackupRecord, destination: Path,
                    safety_backup_root: Optional[Path] = None) -> Optional[BackupRecord]:
    """Restaure une sauvegarde vers `destination`, en REMPLACANT completement son
    contenu actuel (pas une fusion -- un vrai retour en arriere).

    Si `safety_backup_root` est fourni et que `destination` existe deja avec du
    contenu, une sauvegarde automatique de securite de l'etat ACTUEL est d'abord
    creee (label "avant restauration") avant tout ecrasement -- pour qu'une
    restauration accidentelle ne fasse jamais perdre de donnees de facon
    irreversible. Retourne cette sauvegarde de securite si elle a ete creee, sinon
    None.

    Cette fonction ne demande AUCUNE confirmation elle-meme -- c'est la responsabilite
    de l'appelant (interface graphique) de confirmer avec l'utilisateur avant d'appeler
    cette fonction, vu son caractere destructif.
    """
    destination = Path(destination)
    safety_record = None

    if destination.exists() and any(destination.iterdir()) and safety_backup_root:
        safety_record = create_backup(
            destination, Path(safety_backup_root),
            label=f"avant_restauration_{record.label}", kind=record.kind
        )

    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(record.content_path(), destination)
    clear_readonly(destination)

    return safety_record


def delete_backup(record: BackupRecord) -> None:
    if record.backup_path.exists():
        clear_readonly(record.backup_path)  # au cas ou une sauvegarde anterieure a ce correctif soit verrouillee
        shutil.rmtree(record.backup_path)


def backup_size_bytes(record: BackupRecord) -> int:
    total = 0
    for p in record.content_path().rglob('*'):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError as e:
                logger.debug('Fichier inaccessible ignore : %s', e)
    return total


def format_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ('o', 'Ko', 'Mo', 'Go'):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} To"
