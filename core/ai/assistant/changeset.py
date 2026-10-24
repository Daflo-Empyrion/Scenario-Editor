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

"""Jeu de changements propose par l'assistant, a revoir avant application.

L'assistant n'ecrit jamais : il rend un ChangeSet, l'interface le montre
ligne par ligne (cocher / editer la valeur finale, comme TransformDialog) et
n'applique que ce qui reste coche, via les validateurs existants de chaque
format. Un ChangeSet invalide n'est JAMAIS applique : on affiche les
problemes et on laisse la reponse en texte.

Les codes de validation sont des identifiants stables (pas de phrase) : la
traduction vit dans l'interface. `kind` est volontairement une liste FERMEE,
chaque valeur correspondra a un adaptateur de surface.
"""
import json
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

CHANGE_KINDS = ("ecf_set", "ecf_create_block", "yaml_set", "csv_set",
                "pda_field", "playfield_place", "scenario_import")
MAX_CHANGES = 200

_FENCED = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.S)


@dataclass
class Change:
    kind: str
    target: str                  # ex: 'Blocks.ecf [399] / Count'
    old: str = ""
    new: str = ""
    reason: str = ""


@dataclass
class ChangeSet:
    changes: List[Change] = field(default_factory=list)
    summary: str = ""
    report: List[dict] = field(default_factory=list)   # non importables

    def validate(self) -> List[str]:
        """Problemes bloquants (codes), liste vide = applicable."""
        problems: List[str] = []
        if not self.changes:
            problems.append("changeset_vide")
        if len(self.changes) > MAX_CHANGES:
            problems.append("changeset_trop_long")
        for change in self.changes:
            if change.kind not in CHANGE_KINDS:
                problems.append("kind_inconnu")
            if not (change.target or "").strip():
                problems.append("cible_vide")
            if change.new == change.old:
                problems.append("changement_sans_effet")
        return sorted(set(problems))

    def write_report_csv(self, path) -> int:
        """Ecrit les dependances non resolues (export demandee 22/10) et
        retourne le nombre de lignes. BOM pour qu'Excel lise le francais."""
        import csv
        from pathlib import Path

        rows = [row for row in self.report if isinstance(row, dict)]
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["type", "reference", "from", "reason"])
            for row in rows:
                writer.writerow([row.get("type", ""),
                                 row.get("reference", ""),
                                 row.get("from", ""),
                                 row.get("reason", "")])
        return len(rows)


def _payloads(text: str):
    """Blocs JSON candidats, du plus recent au plus ancien : le modele met
    parfois le jeu de changements apres une explication."""
    found = [m.group(1) for m in _FENCED.finditer(text or "")]
    if not found and (text or "").strip().startswith("{"):
        found = [text.strip()]
    return list(reversed(found))


def parse_change_set(text: str) -> Tuple[Optional[ChangeSet], List[str]]:
    """Extrait et valide le ChangeSet d'une reponse. Retourne (jeu, problemes).
    Aucun bloc exploitable -> (None, ['changeset_absent'])."""
    for block in _payloads(text):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        if not isinstance(data, dict) or "changes" not in data:
            continue
        changes = []
        for item in data.get("changes") or []:
            if not isinstance(item, dict):
                continue
            changes.append(Change(
                kind=str(item.get("kind") or ""),
                target=str(item.get("target") or ""),
                old=str(item.get("old") if item.get("old") is not None else ""),
                new=str(item.get("new") if item.get("new") is not None else ""),
                reason=str(item.get("reason") or ""),
            ))
        result = ChangeSet(
            changes=changes,
            summary=str(data.get("summary") or ""),
            report=[row for row in (data.get("report") or [])
                    if isinstance(row, dict)])
        return result, result.validate()
    return None, ["changeset_absent"]
