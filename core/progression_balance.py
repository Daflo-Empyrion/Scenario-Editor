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

"""Equilibrage global en LECTURE SEULE : danger des playfields, recompenses
des chapitres PDA, cout des attaques de faction, chacun compare a la MEDIANE
de son groupe de reference.

Perimetre volontairement mesure, sans score composite invente :
- les chapitres PDA n'ont PAS de lien vers un playfield (`VisibleOnStart
  PlayfieldTypes` seulement) et les recompenses observees (RE2) sont XP / UP /
  Reputation — aucun item a valoriser au prix marche. Un ratio
  « danger / valeur de recompense » n'aurait donc aucune base : chaque
  dimension est comparee SEPAREMENT a la mediane de sa categorie.
- danger d'un playfield = somme des groupes d'ondes (POIs aleatoires,
  vaisseaux spatiaux, drones libres, patrouilles) deja calculee par
  core/spawn_waves.py.
- cout d'attaque = prix niveaux 1 et 10 lus par core/faction_warfare.py.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from core.yamllite.model import YamlDocument, YamlEntry
from core.yamllite.parser import parse_yaml_file

OUTLIER_FACTOR = 2.0


@dataclass
class PlayfieldDanger:
    playfield: str
    pf_type: str
    danger_min: int
    danger_max: int
    status: str = "ok"        # ok | outlier


@dataclass
class ChapterProgression:
    title: str
    category: str
    xp: int = 0
    up: int = 0
    reputation: int = 0
    rewards: int = 0
    status: str = "ok"        # ok | below | above | no_reward

    @property
    def total_units(self) -> int:
        return self.xp + self.up + self.reputation


@dataclass
class AttackCost:
    faction: str
    lvl1_min: Optional[float]
    lvl10_max: Optional[float]
    sd_group: str = ""
    status: str = "ok"


@dataclass
class ProgressionReport:
    playfields: List[PlayfieldDanger] = field(default_factory=list)
    chapters: List[ChapterProgression] = field(default_factory=list)
    attacks: List[AttackCost] = field(default_factory=list)
    playfield_medians: Dict[str, float] = field(default_factory=dict)
    chapter_medians: Dict[str, Dict[str, float]] = field(default_factory=dict)
    attack_median: float = 0.0


def _find_pda(root: Path) -> Optional[Path]:
    for candidate in (Path(root) / "Extras" / "PDA" / "PDA.yaml",
                      Path(root) / "Extras" / "PDA" / "Pda.yaml"):
        if candidate.is_file():
            return candidate
    return None


def _int(value) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _read_chapters(doc: YamlDocument) -> List[ChapterProgression]:
    chapters: List[ChapterProgression] = []
    for node in doc.nodes:
        if not (isinstance(node, YamlEntry) and node.key == "Chapters"):
            continue
        for chapter in node.children:
            if not isinstance(chapter, YamlEntry):
                continue
            item = ChapterProgression(
                title=(chapter.value or "?").strip(),
                category=_child_value(chapter, "Category") or "?")
            for rewards in chapter.children:
                if not (isinstance(rewards, YamlEntry) and rewards.key == "Rewards"):
                    continue
                for reward in rewards.children:
                    if not isinstance(reward, YamlEntry):
                        continue
                    # 'Type' est la CLE D'ITEM de la liste Rewards (la valeur
                    # est sur l'item lui-meme), pas une propriete enfant
                    kind = (reward.value or "").strip() if reward.key == "Type"                         else _child_value(reward, "Type")
                    count = _int(_child_value(reward, "Count"))
                    if not kind:
                        continue
                    item.rewards += 1
                    if kind == "XP":
                        item.xp += count
                    elif kind == "UP":
                        item.up += count
                    elif kind in ("Reputation", "ReputationTarget"):
                        item.reputation += count
            chapters.append(item)
    return chapters


def _child_value(entry: YamlEntry, key: str) -> str:
    for child in entry.children:
        if isinstance(child, YamlEntry) and child.key == key:
            return (child.value or "").strip()
    return ""


def _median(values: List[float]) -> float:
    clean = [v for v in values if v is not None]
    return float(statistics.median(clean)) if clean else 0.0


def scan(root: Path) -> ProgressionReport:
    from core.faction_warfare import scan as scan_warfare
    from core.spawn_waves import scan as scan_spawns

    report = ProgressionReport()

    # --- danger par playfield ---
    for summary in scan_spawns(root).summaries:
        if not summary.files:
            continue
        report.playfields.append(PlayfieldDanger(
            playfield=summary.playfield, pf_type=summary.pf_type or "?",
            danger_min=summary.total_min, danger_max=summary.total_max))
    by_type: Dict[str, List[float]] = {}
    for item in report.playfields:
        by_type.setdefault(item.pf_type, []).append(item.danger_max)
    report.playfield_medians = {k: _median(v) for k, v in by_type.items()}
    for item in report.playfields:
        med = report.playfield_medians.get(item.pf_type, 0.0)
        item.status = "outlier" if med > 0 and item.danger_max > med * OUTLIER_FACTOR \
            else "ok"

    # --- recompenses des chapitres ---
    pda = _find_pda(root)
    if pda is not None:
        try:
            report.chapters = _read_chapters(parse_yaml_file(pda))
        except Exception:                      # noqa: BLE001 - PDA illisible
            report.chapters = []
    # medianes calculees sur les chapitres QUI RECOMPENSENT : inclure les
    # chapitres encyclopediques (0 de tout) ecraserait la mediane a zero
    by_cat: Dict[str, List[ChapterProgression]] = {}
    for chapter in report.chapters:
        if chapter.rewards:
            by_cat.setdefault(chapter.category, []).append(chapter)
    for category, items in by_cat.items():
        report.chapter_medians[category] = {
            "xp": _median([c.xp for c in items]),
            "up": _median([c.up for c in items]),
            "reputation": _median([c.reputation for c in items]),
        }
    for chapter in report.chapters:
        med = report.chapter_medians.get(chapter.category, {})
        if chapter.rewards == 0:
            chapter.status = "no_reward"
            continue
        flags = []
        for key in ("xp", "up", "reputation"):
            value = getattr(chapter, key)
            reference = med.get(key, 0.0)
            # une dimension absente d'un cote (0) n'est pas comparable :
            # 35000 XP sans UP ne doit pas devenir 'below' sur le seul UP
            if reference > 0 and value > 0:
                flags.append(1 if value > reference else
                             -1 if value < reference else 0)
        # deux dimensions comparables au minimum, sinon le verdict n'a pas
        # de sens (vecu : un chapitre 35000 XP classe 'below' sur UP seul)
        if len(flags) >= 2 and all(f > 0 for f in flags):
            chapter.status = "above"
        elif len(flags) >= 2 and all(f < 0 for f in flags):
            chapter.status = "below"
        else:
            chapter.status = "ok"

    # --- cout des attaques de faction ---
    for entry in scan_warfare(root).factions:
        sd_group = entry.values.get("sd_group")
        report.attacks.append(AttackCost(
            faction=entry.faction,
            lvl1_min=entry.price(1, "min"),
            lvl10_max=entry.price(10, "max"),
            sd_group=sd_group if isinstance(sd_group, str) else ""))
    report.attack_median = _median([a.lvl10_max for a in report.attacks])
    for attack in report.attacks:
        if attack.lvl10_max is None:
            attack.status = "missing"
        elif report.attack_median > 0 and \
                attack.lvl10_max > report.attack_median * OUTLIER_FACTOR:
            attack.status = "outlier"
        else:
            attack.status = "ok"
    return report


def export_csv(report: ProgressionReport, path: Path) -> Path:
    """Export des trois volets en un seul CSV (separateur ';', UTF-8 BOM)."""
    import csv
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["volet", "nom", "groupe", "min", "max",
                        "xp", "up", "reputation", "statut"])
        for item in report.playfields:
            writer.writerow(["playfield", item.playfield, item.pf_type,
                             item.danger_min, item.danger_max, "", "", "",
                             item.status])
        for chapter in report.chapters:
            writer.writerow(["chapitre", chapter.title, chapter.category,
                             "", "", chapter.xp, chapter.up,
                             chapter.reputation, chapter.status])
        for attack in report.attacks:
            writer.writerow(["attaque", attack.faction, attack.sd_group,
                             attack.lvl1_min if attack.lvl1_min is not None else "",
                             attack.lvl10_max if attack.lvl10_max is not None else "",
                             "", "", "", attack.status])
    return Path(path)
