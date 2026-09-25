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

"""Analyse de fusion de dossier AVEC DEPENDANCES (demande 25/09/2026) :
la fusion de dossier copiait les YAML en aveugle (Sectors.yaml,
Playfields/, Prefabs/) sans fenetre de revision, et n'embarquait pas les
dependances. Ce module :
  1. planifie chaque fichier (nouveau / remplacement / fusion ecf / csv) ;
  2. si un Sectors.yaml est concerne, collecte les DEPENDANCES : dossiers
     de playfield references (Playfields/<template>/) absents de la copie
     de travail, et POIs (Prefabs/<GroupName>.epb) references par leurs
     playfield_static.yaml et absents de la copie de travail.
L'application reste soumise a la fenetre de revision (validation par
cases a cocher)."""
import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

STATUS_NEW = "new"
STATUS_OVERWRITE = "overwrite"
STATUS_ECF = "ecf"
STATUS_CSV = "csv"

_TEXT_SUFFIXES = {".yaml", ".yml", ".ecf", ".csv", ".txt", ".md", ".json",
                  ".ecf.bak"}


@dataclass
class FilePlan:
    source: Path
    dest: Path
    rel: str
    status: str               # new / overwrite / ecf / csv
    size: int
    diff_summary: str = ""    # "+12 −3" pour les remplacements texte
    diff_text: str = ""       # extrait unifie (tooltip)
    checked: bool = True

    @property
    def status_i18n(self) -> str:
        return {"new": "mergeplan.status_new",
                "overwrite": "mergeplan.status_overwrite",
                "ecf": "mergeplan.status_ecf",
                "csv": "mergeplan.status_csv"}[self.status]


@dataclass
class DependencyFile:
    source: Path
    dest: Path
    reason_i18n: str
    detail: str = ""


@dataclass
class FolderMergePlan:
    files: List[FilePlan] = field(default_factory=list)
    dependencies: List[DependencyFile] = field(default_factory=list)


def plan_folder_merge(source_folder: Path, source_root: Path,
                      working_root: Optional[Path]) -> FolderMergePlan:
    """Planifie la fusion fichier par fichier (meme logique de strategie
    que merge_file_into_working) + dependances si Sectors.yaml concerne.
    working_root=None (aucun projet) : tout est 'nouveau fichier', pas de
    dependances."""
    source_folder, source_root = Path(source_folder), Path(source_root)
    working_root = Path(working_root) if working_root else None
    plan = FolderMergePlan()
    for f in sorted(source_folder.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(source_root)
        dest = (working_root / rel) if working_root else None
        if dest is None or not dest.exists():
            plan.files.append(FilePlan(source=f, dest=dest, rel=str(rel),
                                       status=STATUS_NEW,
                                       size=f.stat().st_size))
        elif dest.suffix.lower() == ".csv":
            plan.files.append(FilePlan(source=f, dest=dest, rel=str(rel),
                                       status=STATUS_CSV,
                                       size=f.stat().st_size))
        elif dest.suffix.lower() == ".ecf":
            plan.files.append(FilePlan(source=f, dest=dest, rel=str(rel),
                                       status=STATUS_ECF,
                                       size=f.stat().st_size))
        else:
            plan.files.append(_overwrite_plan(f, dest, str(rel)))
    # dependances Sectors -> Playfields -> POIs
    sector_yaml = _find_source_sectors_yaml(source_folder)
    if sector_yaml is not None:
        plan.dependencies.extend(
            collect_sector_dependencies(sector_yaml, source_root,
                                        working_root))
    return plan


def _find_source_sectors_yaml(source_folder: Path) -> Optional[Path]:
    candidates = [source_folder / "Sectors.yaml"]
    candidates.extend(source_folder.rglob("Sectors.yaml"))
    for c in candidates:
        if c.is_file():
            return c
    return None


def _overwrite_plan(source: Path, dest: Path, rel: str) -> FilePlan:
    plan = FilePlan(source=source, dest=dest, rel=rel,
                    status=STATUS_OVERWRITE, size=source.stat().st_size,
                    checked=False)          # ecrasement = choix explicite
    if source.suffix.lower() in _TEXT_SUFFIXES:
        try:
            a = dest.read_text(encoding="utf-8", errors="ignore").splitlines()
            b = source.read_text(encoding="utf-8", errors="ignore").splitlines()
            diff = list(difflib.unified_diff(a, b, lineterm="",
                                             fromfile="copie de travail",
                                             tofile="source"))
            adds = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
            dels = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
            plan.diff_summary = f"+{adds} −{dels}"
            plan.diff_text = "\n".join(diff[:200])
        except Exception:                   # noqa: BLE001 - diff informatif
            pass
    else:
        plan.diff_summary = "(binaire)"
    return plan


# ----------------------------------------------------------------- dependances

_GROUP_RE = re.compile(r"GroupName:\s*(.+)")


def _split_flow(value: str) -> List[str]:
    """Eclate une liste flow yaml en champs en respectant les guillemets
    (le champ coordonnees contient lui-meme des virgules)."""
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]          # retire les crochets de la liste flow
    fields, buf, quote = [], "", None
    for c in value:
        if quote:
            buf += c
            if c == quote:
                quote = None
        elif c in "\"'":
            quote = c
            buf += c
        elif c == ",":
            fields.append(buf.strip())
            buf = ""
        else:
            buf += c
    if buf.strip():
        fields.append(buf.strip())
    return [f.strip().strip("'\"") for f in fields]


def collect_sector_dependencies(sector_yaml: Path, source_root: Path,
                                working_root: Path) -> List[DependencyFile]:
    """Playfields references par le Sectors.yaml source et absents de la
    copie de travail (dossier Playfields/<template>/ complet), puis POIs
    (Prefabs/<GroupName>.epb) references par ces playfields et absents de
    la copie de travail.

    PAS de PyYAML ici (absent des requirements et donc de l'installeur,
    vecu CI v1.12.0 : import silencieux avale -> dependances vides) : les
    lignes playfield sont des listes flow UNE-LIGNE
    (convention Empyrion : - ['x,y,z', Nom, Template, ...])."""
    deps: List[DependencyFile] = []
    source_root, working_root = Path(source_root), Path(working_root)
    try:
        text = sector_yaml.read_text(encoding="utf-8")
    except OSError:
        return deps
    templates: set = set()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- ["):
            continue
        fields = _split_flow(stripped[2:].strip())
        if len(fields) > 2 and fields[2]:
            templates.add(fields[2])
    for template in sorted(templates):
        src_dir = source_root / "Playfields" / template
        dest_dir = working_root / "Playfields" / template
        if not src_dir.is_dir() or dest_dir.is_dir():
            continue
        files = [f for f in sorted(src_dir.rglob("*")) if f.is_file()]
        for f in files:
            deps.append(DependencyFile(
                source=f, dest=working_root / "Playfields" / template
                / f.relative_to(src_dir),
                reason_i18n="mergeplan.dep_playfield",
                detail=template))
        # POIs references par les playfield_static de CE template
        names: set = set()
        for f in files:
            if "playfield_static" not in f.name or f.suffix.lower() != ".yaml":
                continue
            names |= _poi_groups(f)
        for name in sorted(names):
            for suffix in (".epb", ".yaml"):
                src_poi = source_root / "Prefabs" / f"{name}{suffix}"
                dst_poi = working_root / "Prefabs" / f"{name}{suffix}"
                if src_poi.is_file() and not dst_poi.exists():
                    deps.append(DependencyFile(
                        source=src_poi, dest=dst_poi,
                        reason_i18n="mergeplan.dep_poi", detail=name))
                    break
    return deps


def _poi_groups(playfield_static: Path) -> set:
    """Tous les GroupName references par un playfield_static.yaml
    (lecture LIGNE par ligne : le fichier est du yaml partiellement
    commente, on ne cherche que les tokens de reference)."""
    names: set = set()
    try:
        text = playfield_static.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return names
    for m in _GROUP_RE.finditer(text):
        raw = m.group(1).strip()
        for token in re.split(r"[\[\],]", raw):
            token = token.strip().strip("'\"").strip()
            if token and not token.startswith("#") and token not in (
                    "True", "False"):
                names.add(token)
    return names
