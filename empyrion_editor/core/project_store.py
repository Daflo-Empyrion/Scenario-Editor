"""
Gestion des "projets recents" : sauvegarde sur disque (petit fichier JSON dans le
dossier utilisateur) la liste des workspaces deja crees, pour pouvoir les reprendre
au demarrage sans avoir a tout re-saisir a chaque fois.
"""
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional

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
    except Exception:
        return []


def save_recent_projects(projects: List[ProjectRecord]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {'projects': [asdict(p) for p in projects]}
    CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


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
