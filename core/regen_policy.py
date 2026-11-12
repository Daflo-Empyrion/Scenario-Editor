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

"""Politique de regeneration des POI : ressources en tension (C + mines).

`RegenAfter: 0` = la structure ne revient JAMAIS (verifie en v1.19.6, non
revérifié en v1.20) ; les
gisements de terrain n'ont deja aucun regen, donc tout le renouvellement de
ressources passe par les POI. La politique retenue :

- **vaisseaux** (SV/CV/HV/OPV, epaves) : intacts — la tension de patrouille
  repose sur eux ;
- **ancres** (`GroupName` reference par un `SpawnPOINear`, union galaxie) :
  intactes — 3 811 dependances de placement reposent sur 163 ancres ;
- **marchands** (`Trader`) : intacts — un service detruit ne revient pas ;
- **mines** : ramenees a 72 h de jeu (4 320 min) — l'exploration reste
  obligatoire mais une mine epuisee finit par revenir (pas de blocage) ;
- **tout le reste** : `0`, recupere une seule fois.

Le fichier n'est jamais re-serialise : on ne reecrit que la ligne `Value:`
qui suit `- Key: RegenAfter`, pour garder le format et les commentaires.
"""
import re
from pathlib import Path

VESSEL = re.compile(r"(SV|CV|HV|OPV)_|Ship|Vessel|Wreck", re.I)
MINE = re.compile(r"Mine", re.I)
KEEP = ("Trader",)
MINE_CYCLE = 4320          # 72 h de temps de jeu

GROUP_RE = re.compile(r"^(?P<ind>\s*)- GroupName:\s*(?P<name>\S+)\s*$")
NEAR_RE = re.compile(r"SpawnPOINear:\s*\[([^\]]*)\]")
KEY_RE = re.compile(r"^\s*- Key:\s*RegenAfter\s*$")
VALUE_RE = re.compile(r"^(?P<ind>\s*)Value:\s*(?P<val>-?\d+)\s*$")


def playfield_files(scenario):
    """Les `playfield_static.yaml` du scenario, chemins tries."""
    root = Path(scenario) / "Playfields"
    return sorted(root.glob("*/playfield_static.yaml")) if root.is_dir() else []


def read(path: Path) -> str:
    return path.read_bytes().decode("utf-8", errors="replace").replace("\r\n", "\n")


def anchors(texts) -> set:
    """Union galaxie des groupes cites comme ancre de placement."""
    out = set()
    for text in texts:
        for m in NEAR_RE.finditer(text):
            out.update(a.strip().strip("'\"") for a in m.group(1).split(","))
    return {a for a in out if a}


def decision(name: str, anchor_set: set, current):
    """Valeur voulue, ou None quand il ne faut pas toucher (deja conforme)."""
    if current is None:
        return None
    if VESSEL.search(name) or name in anchor_set or any(k in name for k in KEEP):
        return None
    if MINE.search(name):
        return MINE_CYCLE if current != MINE_CYCLE else None
    return 0 if current not in (0, "0") else None


def plan_text(text: str, anchor_set: set):
    """[(ligne Value (1-based), nom du POI, valeur actuelle, valeur voulue)]."""
    out, name = [], ""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        m = GROUP_RE.match(line)
        if m:
            name = m.group("name")
            continue
        if not KEY_RE.match(line) or i + 1 >= len(lines):
            continue
        v = VALUE_RE.match(lines[i + 1])
        if v is None:                       # forme inattendue : on ne touche pas
            continue
        want = decision(name, anchor_set, int(v.group("val")))
        if want is not None:
            out.append((i + 2, name, int(v.group("val")), want))
    return out


def plan(scenario):
    """[{path, text, changes}] pour tout le scenario (lecture seule)."""
    paths = playfield_files(scenario)
    texts = [read(p) for p in paths]
    anchor_set = anchors(texts)
    rows = []
    for path, text in zip(paths, texts):
        changes = plan_text(text, anchor_set)
        if changes:
            rows.append({"path": path, "text": text, "changes": changes})
    return rows, anchor_set


def rewrite(text: str, changes) -> str:
    lines = text.split("\n")
    for line_no, _name, _old, want in changes:
        v = VALUE_RE.match(lines[line_no - 1])
        lines[line_no - 1] = v.group("ind") + "Value: " + str(want)
    return "\n".join(lines)


def scan(scenario) -> list:
    """[(playfield, ligne, POI, valeur, voulue)] : ce qui echappe a la politique.
    Un regen laisse a 720 sur un POI de combat = ressources infinies rendues."""
    try:
        rows, _ = plan(scenario)
    except OSError:
        return []
    out = []
    for row in rows:
        for line_no, name, old, want in row["changes"]:
            out.append((row["path"].parent.name, line_no, name, old, want))
    return out
