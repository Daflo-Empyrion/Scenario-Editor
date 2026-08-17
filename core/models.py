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
Modèle de données central pour représenter un scénario Empyrion scanné.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict  # noqa: F401 (Dict utilisé plus bas)

# Extensions considérées comme "éditables" par l'outil (texte structuré qu'on pourra parser/éditer)
EDITABLE_EXTENSIONS = {'.ecf', '.yaml', '.yml', '.csv'}


@dataclass
class FileEntry:
    """Un fichier détecté dans le scénario, avec sa catégorie et si l'outil sait (potentiellement) l'éditer."""
    path: Path
    category: str
    editable: bool = False

    @property
    def extension(self) -> str:
        return self.path.suffix.lower()

    @property
    def name(self) -> str:
        return self.path.name

    def __repr__(self):
        return f"FileEntry({self.name}, category={self.category}, editable={self.editable})"


@dataclass
class Playfield:
    """
    Un dossier de playfield (planète, orbite, secteur spatial...).

    Empyrion utilise plusieurs conventions de nommage selon le type de playfield :
      - Surface (planète)         : playfield_dynamic.yaml + playfield_static.yaml + terrain.ecf
      - Spatial (orbite/secteur)  : space_dynamic.yaml (+ souvent pas de terrain.ecf, pas de sol)
      - Système/soleil            : sun_static.yaml
      - Ancien format combiné     : playfield.yaml
      - Sauvegardes de l'éditeur  : fichiers préfixés "+" (ex: +backup_terrain.ecf) -> ignorés du
                                     rôle principal, gardés à part pour ne pas les confondre avec l'actif.
    On stocke donc les fichiers "rôle" détectés dans un dict plutôt que des champs fixes.
    """
    name: str
    role_files: Dict[str, Path] = field(default_factory=dict)   # rôle ('dynamic','static','terrain','combined') -> chemin
    backups: List[FileEntry] = field(default_factory=list)      # fichiers +backup*
    other_files: List[FileEntry] = field(default_factory=list)  # tout le reste (non reconnu)

    @property
    def dynamic_yaml(self) -> Optional[Path]:
        return self.role_files.get('dynamic')

    @property
    def static_yaml(self) -> Optional[Path]:
        return self.role_files.get('static')

    @property
    def terrain_ecf(self) -> Optional[Path]:
        return self.role_files.get('terrain')

    @property
    def combined_yaml(self) -> Optional[Path]:
        return self.role_files.get('combined')

    def is_complete(self) -> bool:
        """Un playfield est considéré 'reconnu' s'il a au moins un fichier de rôle principal détecté."""
        return bool(self.role_files)

    def file_count(self) -> int:
        return len(self.role_files) + len(self.backups) + len(self.other_files)


@dataclass
class Scenario:
    """Représentation complète d'un scénario Empyrion, une fois scanné."""
    root_path: Path
    name: str = ""

    configuration: List[FileEntry] = field(default_factory=list)   # Content/Configuration/*
    playfields: Dict[str, Playfield] = field(default_factory=dict)  # Playfields/<nom>/
    sectors: List[FileEntry] = field(default_factory=list)          # Sectors/*
    random_presets: List[FileEntry] = field(default_factory=list)   # RandomPresets/*
    extras: List[FileEntry] = field(default_factory=list)           # Extras/* (Localization.csv, PDA...)
    shared_data: Optional["Scenario"] = None                        # SharedData/ (structure annexe, même forme)
    other_files: List[FileEntry] = field(default_factory=list)      # Prefabs, Logos, racine, non catégorisé

    def total_file_count(self, include_shared: bool = False) -> int:
        count = (
            len(self.configuration)
            + len(self.sectors)
            + len(self.random_presets)
            + len(self.extras)
            + len(self.other_files)
        )
        for pf in self.playfields.values():
            count += pf.file_count()
        if include_shared and self.shared_data:
            count += self.shared_data.total_file_count()
        return count

    def configuration_extensions_summary(self) -> str:
        ext_counts = {}
        for f in self.configuration:
            ext_counts[f.extension] = ext_counts.get(f.extension, 0) + 1
        return ", ".join(f"{ext}: {n}" for ext, n in sorted(ext_counts.items()))

    def ecf_files(self) -> List[FileEntry]:
        """Raccourci pratique : uniquement les .ecf de Configuration."""
        return [f for f in self.configuration if f.extension == '.ecf']

    def summary(self) -> str:
        lines = []
        lines.append(f"Scénario : {self.name or self.root_path.name}")
        lines.append(f"  Configuration : {len(self.configuration)} fichiers détectés")
        ext_str = self.configuration_extensions_summary()
        if ext_str:
            lines.append(f"      ({ext_str})")

        lines.append(f"  Playfields    : {len(self.playfields)} dossiers détectés")
        incomplete = [p for p in self.playfields.values() if not p.is_complete()]
        if incomplete:
            lines.append(f"      ({len(incomplete)} sans fichier standard reconnu)")

        lines.append(f"  Sectors       : {len(self.sectors)} fichier(s)")
        lines.append(f"  RandomPresets : {len(self.random_presets)} fichier(s)")

        extras_names = ", ".join(sorted(f.name for f in self.extras)) or "-"
        lines.append(f"  Extras        : {len(self.extras)} fichier(s) [{extras_names}]")

        if self.shared_data:
            total_shared = self.shared_data.total_file_count()
            lines.append(f"  SharedData    : (structure annexe, {total_shared} fichiers)")

        lines.append(f"  Autres/non éditables : {len(self.other_files)} fichiers")
        return "\n".join(lines)
