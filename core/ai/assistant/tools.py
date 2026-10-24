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

"""Outils exposes au modele : LECTURE SEULE, sortie bornee.

Regle (Q33) : un outil lit ou previsualise en memoire, jamais d'ecriture,
de suppression, de reseau ni de shell -- c'est ce qui laisse une place a la
revue humaine avant application. Chaque surface enregistre son sous-ensemble
et seuls les outils de la surface active sont envoyes (chaque schema coute
des tokens a CHAQUE tour).

La sortie d'un outil est toujours du TEXTE : le handler peut retourner une
structure, elle est serialisee en JSON, puis coupee a `max_chars` avec un
marqueur explicite -- le modele doit savoir que la liste est incomplete.
"""
import json
import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,40}$")

# Jamais enregistrables (verifie par un test) : l'ecriture reste un ChangeSet.
FORBIDDEN_TOOLS = ("write_file", "apply_changes", "delete", "deploy",
                   "shell", "exec", "start_server", "kick", "ban")


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict                      # JSON schema (properties/required)
    handler: Callable[[dict], object]
    surface: str = ""
    max_chars: int = 4000


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def add(self, tool: Tool) -> None:
        if not _NAME_RE.match(tool.name or ""):
            raise ValueError(f"Nom d'outil invalide : {tool.name!r}")
        if tool.name in FORBIDDEN_TOOLS:
            raise ValueError(f"Outil interdit (ecriture/action serveur) : "
                             f"{tool.name}")
        if tool.name in self._tools:
            raise ValueError(f"Outil deja enregistre : {tool.name}")
        self._tools[tool.name] = tool

    def names(self, surface: Optional[str] = None) -> List[str]:
        return sorted(n for n, t in self._tools.items()
                      if surface is None or t.surface == surface)

    def schemas(self, surface: Optional[str] = None) -> List[dict]:
        """Format attendu par l'API (tools=[...]). Pas de schema pour une
        surface vide : on n'envoie pas d'outils inutiles."""
        return [{"type": "function",
                 "function": {"name": t.name,
                              "description": t.description,
                              "parameters": {"type": "object",
                                             **t.parameters}}}
                for t in (self._tools[n] for n in self.names(surface))]

    def call(self, name: str, arguments: dict) -> dict:
        """Execute et retourne {ok, content, truncated}. Une exception du
        handler devient un resultat d'erreur pour le modele : elle ne doit
        jamais remonter dans le thread appelant."""
        tool = self._tools.get(name)
        if tool is None:
            return {"ok": False, "content": f"Outil inconnu : {name}",
                    "truncated": False}
        try:
            value = tool.handler(arguments or {})
        except Exception as e:  # noqa: BLE001 -- remonte au modele, pas a l'UI
            return {"ok": False,
                    "content": f"Erreur outil {name} : {type(e).__name__}: {e}",
                    "truncated": False}
        text = value if isinstance(value, str) else json.dumps(
            value, ensure_ascii=False, default=str)
        if len(text) > tool.max_chars:
            return {"ok": True,
                    "content": text[:tool.max_chars]
                    + "\n[...sortie tronquee...]",
                    "truncated": True}
        return {"ok": True, "content": text, "truncated": False}
