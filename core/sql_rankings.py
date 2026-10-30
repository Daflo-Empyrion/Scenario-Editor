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

"""Classements du PDA (SqlQueries.txt) : boites de classement, requetes SQL
associees et etat (actifs / desactives).

Format confirme sur la vanilla et sur RE2 : fichier INI-like
    - RankingBox<X>,<Y> = <NomDeBoite>
    - <Boite>.Name = <titre affiche>
    - <Boite>.PlayersTop10.Query = <SQL sur plusieurs lignes indentees>
    - <Boite>.CacheTime = 120
Les lignes INDENTEES prolongent la valeur precedente (les requetes vanilla
font une dizaine de lignes).

Etat : RE2 ne desactive pas les boites une par une — son fichier definit des
boites au nom 'RankingsDisabled' dont TOUTES les requetes sont vides (le jeu
ne peut rien afficher). Le 'vrai' retour aux classements vanilla se fait en
supprimant le fichier du scenario (le jeu reprend la config de base) —
d'ou les deux actions explicites de ce module."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from core.ecf.validation import ValidationIssue

SQL_FILE = "SqlQueries.txt"
QUERY_KINDS = ("PlayersTop10", "LocalPlayer", "FactionTop10",
               "AllFactionsTop10")

_BOX_RE = re.compile(r"^RankingBox\s*(\d+)\s*,\s*(\d+)$", re.IGNORECASE)


@dataclass
class RankingBox:
    name: str
    positions: List[str] = field(default_factory=list)   # 'RankingBox1,1'
    title: str = ""
    cache_time: str = ""
    queries: Dict[str, str] = field(default_factory=dict)

    @property
    def has_query(self) -> bool:
        return any(q.strip() for q in self.queries.values())


@dataclass
class RankingScan:
    path: Optional[Path] = None
    boxes: List[RankingBox] = field(default_factory=list)
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def active(self) -> bool:
        """Au moins une boite a une requete non vide -> le jeu peut afficher."""
        return any(b.has_query for b in self.boxes)


def find_sql_file(root: Path) -> Optional[Path]:
    for candidate in (Path(root) / "Content" / "Configuration" / SQL_FILE,
                      Path(root) / "Configuration" / SQL_FILE):
        if candidate.is_file():
            return candidate
    return None


def _join(parts: List[str]) -> str:
    return "\n".join(parts).strip()


def _parse_property_key(key: str):
    """'Boite.Name' / 'Boite.CacheTime' / 'Boite.<Kind>.Query' ->
    (boite, kind, sous-cle). Decoupage par la DROITE : les kinds contiennent
    des chiffres ('PlayersTop10'), un regex [A-Za-z]+ les tronquait."""
    parts = key.split(".")
    if len(parts) >= 3 and parts[-1] in ("Query", "CacheTime") \
            and parts[-2] in QUERY_KINDS:
        return ".".join(parts[:-2]), parts[-2], parts[-1]
    if len(parts) >= 2 and parts[-1] in ("Name", "CacheTime"):
        return ".".join(parts[:-1]), parts[-1], None
    return None


def scan(root: Path) -> RankingScan:
    path = find_sql_file(root)
    result = RankingScan(path=path)
    if path is None:
        return result
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        result.issues.append(ValidationIssue(
            code="E340", level="error",
            message=f"SqlQueries.txt illisible : {exc}", file_path=path))
        return result

    boxes: Dict[str, RankingBox] = {}
    values: Dict[str, List[str]] = {}       # cle brute -> lignes de valeur
    current: Optional[str] = None
    for raw in lines:
        if not raw.strip():
            current = None
            continue
        if raw.lstrip().startswith("#"):
            continue
        if raw.startswith("-"):
            body = raw[1:].strip()
            if "=" not in body:
                current = None
                continue
            key, value = body.split("=", 1)
            current = key.strip()
            values[current] = [value.strip()]
            continue
        if current is not None:            # continuation indentee (SQL)
            values[current].append(raw.strip())

    unresolved: List[str] = []
    for key, parts in values.items():
        value = _join(parts)
        box_match = _BOX_RE.match(key)
        if box_match:
            positions = f"RankingBox{box_match.group(1)},{box_match.group(2)}"
            box = boxes.setdefault(value or positions,
                                   RankingBox(name=value or positions))
            box.positions.append(positions)
            continue
        prop = _parse_property_key(key)
        if prop is None:
            unresolved.append(key)
            continue
        box_name, kind, sub = prop
        box = boxes.setdefault(box_name, RankingBox(name=box_name))
        if kind == "Name" and sub is None:
            box.title = value
        elif kind == "CacheTime" and sub is None:
            box.cache_time = value
        elif kind in QUERY_KINDS and sub == "Query":
            box.queries[kind] = value
        elif kind in QUERY_KINDS and sub == "CacheTime":
            continue                        # cache par requete : non expose
        else:
            unresolved.append(key)

    result.boxes = sorted(boxes.values(), key=lambda b: b.name.lower())
    _run_checks(path, result, bool(unresolved))
    return result


def _run_checks(path: Path, result: RankingScan, has_unresolved: bool) -> None:
    for box in result.boxes:
        if not box.has_query:
            continue                        # boite volontairement vide
        # SEULE la liste principale est obligatoire : la vanilla elle-meme
        # laisse FactionTop10/AllFactionsTop10 vides sur la plupart des boites
        if not box.queries.get("PlayersTop10", "").strip():
            result.issues.append(ValidationIssue(
                code="W341", level="warning",
                message=f"classement '{box.name}' : requete PlayersTop10 "
                        f"vide alors que d'autres sont remplies -- la boite "
                        f"n'affichera pas son classement principal",
                file_path=path))
    if has_unresolved:
        result.issues.append(ValidationIssue(
            code="W342", level="warning",
            message="ligne(s) non reconnue(s) dans SqlQueries.txt "
                    "(verifier la syntaxe '- Cle = valeur')",
            file_path=path))


def summary(result: RankingScan) -> str:
    named = [b for b in result.boxes if b.has_query]
    return f"{len(result.boxes)}|{len(named)}"


# ============================================================================
# Actions : desactiver (fichier RE2-like) ou revenir aux classements vanilla
# ============================================================================

_DISABLED_BOX = "RankingsDisabled"

_DISABLED_TEMPLATE = """# Classements desactives par l'editeur de scenario.
# Le jeu n'affiche aucune boite : toutes les requetes sont vides.
# Pour revenir aux classements par defaut du jeu, supprimer ce fichier.
- RankingBox1,1 = {box}
- {box}.Name = [c][ffff00]RANKINGS DISABLED[-][/c]
- {box}.PlayersTop10.Query = 
- {box}.LocalPlayer.Query = 
- {box}.FactionTop10.Query = 
- {box}.AllFactionsTop10.Query = 
"""


def disable_rankings(root: Path) -> Path:
    """Ecrit un SqlQueries.txt de desactivation (backup central avant)."""
    from core.fsutil import atomic_write_text, central_backup
    path = find_sql_file(root) or (Path(root) / "Content" / "Configuration"
                                   / SQL_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        central_backup(path, "sql_rankings")
    atomic_write_text(path, _DISABLED_TEMPLATE.format(box=_DISABLED_BOX))
    return path


def restore_default_rankings(root: Path) -> Optional[Path]:
    """Supprime le fichier du scenario : le jeu reprend la config de base
    (c'est la procedure documentee par le fichier lui-meme). Retourne le
    chemin sauvegarde, ou None si le fichier etait absent."""
    from core.fsutil import central_backup
    path = find_sql_file(root)
    if path is None:
        return None
    backup = central_backup(path, "sql_rankings")
    path.unlink()
    return backup


def set_box_title(result: RankingScan, box: RankingBox, title: str) -> bool:
    """Remplace UNIQUEMENT la ligne '- <Boite>.Name = ...' : commentaires,
    requetes et mise en forme du fichier restent intacts (pas de reecriture
    globale — le fichier contient de la doc et du SQL multi-lignes)."""
    from core.fsutil import atomic_write_text, central_backup
    if result.path is None:
        return False
    lines = result.path.read_text(encoding="utf-8",
                                  errors="replace").splitlines()
    needle = f"- {box.name}.Name ="
    for index, raw in enumerate(lines):
        if raw.strip().startswith(needle):
            lines[index] = f"{needle} {title}"
            central_backup(result.path, "sql_rankings")
            atomic_write_text(result.path, "\n".join(lines) + "\n")
            box.title = title
            return True
    return False
