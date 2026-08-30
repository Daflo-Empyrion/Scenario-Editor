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
Gestion des "projets recents" : sauvegarde sur disque (petit fichier JSON dans le
dossier utilisateur) la liste des workspaces deja crees, pour pouvoir les reprendre
au demarrage sans avoir a tout re-saisir a chaque fois.
"""
import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".empyrion_editor"
CONFIG_FILE = CONFIG_DIR / "projets_recents.json"


@dataclass
class ProjectRecord:
    source_a: str
    working: str
    source_b: Optional[str] = None
    label: str = ""  # nom d'affichage ; genere automatiquement si vide

    def display_name(self) -> str:
        if self.label:
            return self.label
        name = Path(self.working).name
        mode = "  (fusion)" if self.source_b else ""
        return f"{name}{mode}"


def load_recent_projects() -> List[ProjectRecord]:
    if not CONFIG_FILE.exists():
        return []
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
        return [ProjectRecord(**p) for p in data.get('projects', [])]
    except Exception as e:
        logger.warning('Projets recents illisibles : %s', e)
        return []


def save_recent_projects(projects: List[ProjectRecord]) -> None:
    from .fsutil import atomic_write_text
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {'projects': [asdict(p) for p in projects]}
    atomic_write_text(CONFIG_FILE, json.dumps(data, indent=2, ensure_ascii=False))


def add_recent_project(record: ProjectRecord, max_entries: int = 10) -> List[ProjectRecord]:
    """Ajoute (ou remonte en tete si deja present) un projet a la liste des recents."""
    projects = load_recent_projects()
    projects = [p for p in projects if p.working != record.working]
    projects.insert(0, record)
    projects = projects[:max_entries]
    save_recent_projects(projects)
    return projects


def remove_project(working_path: str) -> List[ProjectRecord]:
    projects = load_recent_projects()
    projects = [p for p in projects if p.working != working_path]
    save_recent_projects(projects)
    return projects
