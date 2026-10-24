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

"""Surface PDA : remplissage du formulaire de mission guidee (choix B3).

L'IA ne cree JAMAIS la mission : elle propose des champs `pda_field`, le
wizard les affiche dans ses widgets, l'utilisateur corrige, et la validation
existante (`_TierWidget.validate`) refuse une mission bancale au moment de
Creer. C'est le formulaire qui est la revue -- pas de comparaison `old` ici,
puisqu'on remplit un formulaire, on ne modifie pas une valeur existante.
"""
from typing import Dict, List, Optional

from ..actions import Action
from ..changeset import Change

SURFACE = "pda"
TIERS = 4
TIER_FIELDS = ("TitleEN", "TitleFR", "DescriptionEN", "DescriptionFR",
               "Check", "Names", "Types", "Amount")
ALLOWED = ({"Category", "Repeatable", "NumRepeats", "DelayHours"}
           | {f"Tier{n}.{field}" for n in range(1, TIERS + 1)
              for field in TIER_FIELDS})

INSTRUCTION = (
    "Fill an Empyrion PDA mission form. Return ONE change set with kind "
    "'pda_field' and one change per field: target is 'Category' "
    "(SoloMission, FactionMission, Tutorial, Knowledgebase or FAQ), "
    "'Repeatable' (true/false), 'NumRepeats', 'DelayHours', or "
    "'Tier1..Tier4.TitleEN|TitleFR|DescriptionEN|DescriptionFR|Check|Names|"
    "Types|Amount'. Check is 'SubjectKilled' or 'BlockDestroyed'. Names and "
    "Types are comma-separated technical names. Put the value in 'new'; "
    "'old' may stay empty. Write short English and French texts. Never "
    "invent an item or block name you are not sure exists: leave Names "
    "empty instead.")


def action() -> Action:
    return Action(id="pda_generate", surface=SURFACE, min_class="normal",
                  needs_tools=False, produces_changeset=True,
                  instruction=INSTRUCTION)


def build_question(brief: str, category: str = "") -> str:
    from core.i18n import t
    return t("assistant.pda_question", brief=(brief or "").strip(),
             category=category or "?")


def validate(changes: List[Change]) -> List[str]:
    problems: List[str] = []
    for change in changes:
        if change.kind != "pda_field":
            problems.append("pda_kind_unsupported")
            continue
        if change.target not in ALLOWED:
            problems.append("pda_field_unknown")
    return sorted(set(problems))


def values(changes: List[Change]) -> Dict[str, str]:
    return {change.target: change.new for change in changes
            if change.kind == "pda_field" and change.target in ALLOWED}


def truthy(value: str) -> bool:
    return str(value or "").strip().lower() in ("1", "true", "yes", "oui",
                                                "vrai")


def as_int(value: str) -> Optional[int]:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None
