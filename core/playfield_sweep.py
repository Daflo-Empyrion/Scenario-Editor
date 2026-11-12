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

"""Balayage des playfields : ce que le moteur ne resout qu'a l'instantiation.

Le boot dedie valide les SECTEURS (il annonce les N playfields de
Sectors.yaml) mais n'instancie aucun playfield : le jeu ne les cree qu'a
l'entree d'un joueur, et aucune commande console ne le force (constate en
session les 05 et 12/11/2026, moteur v1.20 build 5229). Un prefab casse ne se
verrait donc qu'apres des heures de jeu, sur une planete encore inexploree.

Ce module rejoue hors jeu la resolution par planete qui manquait au bilan :
les .epb cites (`Prefab:` / `PrefabName:`) et les noms de blocs de leur
table BlockIdMapping embarquee. Les AUTRES familles sont deja rendues par
`run_launch_checks` avec le chemin du playfield (groupes de POI, composes,
zones de spawn, references de prefabs) — on ne les duplique pas ici.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Set

from core.epb_blueprint import read_id_mapping
from core.ecf.parser import parse_ecf_file
from core.launch_check import LaunchIssue

_PREFAB_RE = re.compile(r"(?:^|[,{\s])Prefab(?:Name)?:[ \t]*([^,\r\n#}]+)",
                        re.M)


def _declared_names(conf: Path) -> Set[str]:
    """Blocs et items declares dans la config du scenario (casefold)."""
    noms: Set[str] = set()
    for fname, kinds in (("BlocksConfig.ecf", {"Block", "+Block"}),
                         ("ItemsConfig.ecf", {"Item", "+Item"})):
        chemin = conf / fname
        if not chemin.exists():
            continue
        for bloc in parse_ecf_file(chemin).iter_blocks():
            if bloc.kind in kinds:
                nom = bloc.get("Name")
                if nom:
                    noms.add(nom.strip().strip('"').casefold())
    return noms


def _prefabs_index(root: Path) -> Dict[str, Path]:
    """nom de fichier -> .epb (les playfields citent le nom de fichier)."""
    index: Dict[str, Path] = {}
    prefabs = root / "Prefabs"
    if not prefabs.is_dir():
        return index
    for epb in prefabs.glob("*.epb"):
        index.setdefault(epb.stem.casefold(), epb)
    return index


def sweep_playfields(root: Path, vanilla: str = "") -> List[LaunchIssue]:
    """Un bilan par planete des prefabs qu'elle cite et des blocs manquants
    de leurs tables IdMapping. `vanilla` est accepte pour rester aligne sur
    `run_launch_checks` ; la config vanille n'est PAS fusionnee (un scenario
    RE2 remplace BlocksConfig)."""
    root = Path(root)
    playfields = root / "Playfields"
    if not playfields.is_dir():
        return []
    config = _declared_names(root / "Content" / "Configuration")
    if not config:
        return []
    prefabs = _prefabs_index(root)
    manquants: Dict[Path, Set[str]] = {}
    issues: List[LaunchIssue] = []

    for yaml_file in sorted(playfields.glob("*/playfield_*.yaml")):
        if yaml_file.name.startswith("+"):
            continue                    # fichiers d'auteur desactives
        try:
            texte = yaml_file.read_text(encoding="utf-8-sig",
                                        errors="replace")
        except OSError:
            continue
        cites: Set[Path] = set()
        for m in _PREFAB_RE.finditer(texte):
            nom = m.group(1).strip().strip('"\'')
            epb = prefabs.get(nom.casefold())
            if epb is not None:
                cites.add(epb)
        for epb in sorted(cites):
            if epb not in manquants:
                mapping = read_id_mapping(epb) or {}
                manquants[epb] = {
                    n for n in mapping.values()
                    if n and n.casefold() not in config}
            noms = manquants[epb]
            if not noms:
                continue
            rel = f"{playfields.name}/{yaml_file.parent.name}/{yaml_file.name}"
            issues.append(LaunchIssue(
                check="plane", path=rel, line=0, severity="warning",
                message=f"prefab '{epb.name}' cite par cette planete : "
                        f"{len(noms)} bloc(s) absent(s) de la config, ignores "
                        f"au spawn ({', '.join(sorted(noms)[:6])})"))
    return issues
