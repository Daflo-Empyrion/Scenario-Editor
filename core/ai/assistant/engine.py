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

"""Boucle de conversation : un tour d'assistant complet, sans interface.

Enchainement : maillon choisi par le routeur (filtre de capacite) -> appels
d'outils en lecture seule -> reponse finale -> ChangeSet eventuel. Le nombre
de tours d'outils est borne : un modele qui boucle est interrompu avec un
code de probleme, jamais laisse tourner.

Ce module ne touche ni au disque ni a Qt : il prend une Session (historique),
un ToolRegistry (surface active) et une Action (capacite exigee), et rend un
Answer. L'application du ChangeSet reste entierement a l'interface.
"""
import json
from dataclasses import dataclass, field
from typing import List, Optional

from .. import router
from .changeset import ChangeSet, parse_change_set
from .dsml import strip as strip_dsml
from .dsml import tool_calls as dsml_tool_calls
from .session import Session
from .tools import ToolRegistry

MAX_TOOL_ROUNDS = 6

# Le plafond atteint, le modele n'a plus d'outils a disposition : sans cette
# consigne il re-emet son balisage d'appel, qui n'est plus execute (vecu 22/10).
FINAL_NUDGE = ("Tool budget exhausted: do not call any tool now. Answer in "
               "prose from what you have already read, and list what is "
               "missing.")


@dataclass
class Answer:
    text: str = ""
    changeset: Optional[ChangeSet] = None
    problems: List[str] = field(default_factory=list)
    changeset_problems: List[str] = field(default_factory=list)
    link: str = ""
    truncated: bool = False
    rounds: int = 0
    tool_log: List[str] = field(default_factory=list)


def _arguments(raw) -> Optional[dict]:
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw or "{}")
    except (ValueError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def ask(session: Session, action, registry: ToolRegistry, *,
        temperature: float = 0.3,
        max_rounds: int = MAX_TOOL_ROUNDS) -> Answer:
    """Un echange complet. Leve les erreurs du routeur (quota, auth, aucun
    maillon disponible) : c'est l'appelant qui les affiche."""
    answer = Answer()
    tools = registry.schemas(action.surface) if action.needs_tools else None
    if action.needs_tools and not tools:
        answer.problems.append("outils_indisponibles")
        return answer

    history, answer.truncated = session.fit()
    # La consigne de surface voyage dans le message systeme, jamais dans
    # l'historique : elle decrit un contrat de format (cibles, kinds) sans
    # polluer la conversation persistee.
    system = session.system
    if action.instruction:
        system = (f"{system}\n\n{action.instruction}" if system
                  else action.instruction)
    messages = ([{"role": "system", "content": system}] if system else []) \
        + history
    if not messages or messages[-1].get("role") != "user":
        # Rien a repondre : consigne d'action absente de l'historique.
        answer.problems.append("aucune_question")
        return answer

    while answer.rounds < max_rounds:
        answer.rounds += 1
        # shortcut: le plafond de Session s'applique a l'entree, pas au cumul
        # des tours d'outils (4 x max_chars d'outil) -- a revoir si un maillon
        # configure descend sous ~16k de contexte utile.
        result, candidate = router.chat_with_link(
            messages, temperature=temperature, tools=tools,
            min_class=action.min_class, require_tools=action.needs_tools,
            purpose=action.id)
        answer.link = candidate.label
        content = result.get("content") or ""
        calls = result.get("tool_calls") or []
        if not calls:
            content, calls = dsml_tool_calls(content)

        session.add_assistant(content, calls)
        messages.append(session.messages[-1])
        if not calls:
            answer.text = content
            break

        for call in calls:
            function = call.get("function") or {}
            name = str(function.get("name") or "")
            args = _arguments(function.get("arguments"))
            answer.tool_log.append(f"{name}({json.dumps(args or {}, ensure_ascii=False)[:120]})")
            if args is None:
                outcome = {"content": f"Invalid JSON arguments for {name}"}
            else:
                outcome = registry.call(name, args)
            session.add_tool(str(call.get("id") or ""), name,
                             outcome["content"])
            messages.append(session.messages[-1])
    else:
        # Borne atteinte : un DERNIER appel SANS outils, pour forcer une
        # reponse en texte avec ce qui a deja ete lu. Un modele qui boucle ne
        # doit pas laisser l'utilisateur sans rien (vecu 21/10, minimax-flash :
        # quatre tours d'outils pour « explique ce bloc », puis plus rien).
        answer.rounds += 1
        messages.append({"role": "user", "content": FINAL_NUDGE})
        result, candidate = router.chat_with_link(
            messages, temperature=temperature, tools=None,
            min_class=action.min_class, purpose=action.id)
        answer.link = candidate.label
        answer.text = strip_dsml(result.get("content") or "").strip()
        if not answer.text:
            answer.problems.append("boucle_outils_interrompue")

    # Invariant d'affichage : aucun balisage d'appel natif ne sort d'ici, quel
    # que soit le chemin (repli DSML du tour, reponse forcee).
    answer.text = strip_dsml(answer.text).strip()

    if action.produces_changeset and answer.text:
        # Problemes du jeu de changements SEPARES des problemes de la boucle :
        # une reponse en prose sans modification est normale, un ChangeSet
        # invalide ne l'est pas -- l'interface doit pouvoir distinguer les deux.
        answer.changeset, answer.changeset_problems = parse_change_set(
            answer.text)
    return answer
