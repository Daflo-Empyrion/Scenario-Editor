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

"""Session d'assistant : conversation, plafond de contexte, persistance.

Historique par SCENARIO (Q12) : un fichier JSON dans le dossier du projet,
purge manuelle. Aucune I/O ici hors de save()/load() explicites.

Plafond en CARACTERES, pas en tokens : aucune tokenizer n'est embarquee, et
une approximation pessimiste (~3,5 caracteres par token de francais) suffit
pour decider quoi jeter. On jette les TOURS LES PLUS ANCIENS (un tour = un
message 'user' et tout ce qui le suit, donc les paires assistant/tool
restent intactes : l'API refuse un role 'tool' orphelin), jamais le message
systeme, et la troncature est SIGNALEE (jamais de coupe silencieuse).
"""
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from ... import settings
from ...fsutil import atomic_write_text
from .dsml import strip as strip_dsml

DEFAULT_MAX_CHARS = 24_000


def history_path(scenario_root) -> Path:
    """Fichier d'historique propre a un scenario, HORS de son arbre : un fichier
    depose dans la copie de travail serait vu par la synchronisation de
    production et pourrait etre deploye sur le serveur (vecu : un fichier
    parasite dans un scenario est fatal au chargement du jeu). Nom lisible +
    empreinte du chemin absolu pour distinguer deux scenarios homonymes."""
    root = Path(scenario_root)
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", root.name) or "scenario"
    digest = hashlib.sha1(
        str(root.resolve()).lower().encode("utf-8")).hexdigest()[:10]
    return settings.CONFIG_DIR / "assistant" / f"{slug}-{digest}.json"


def _size(message: dict) -> int:
    """Cout approximatif d'un message : contenu + marge de role + arguments
    d'appels d'outils (souvent longs, contenu vide)."""
    size = len(str(message.get("content") or "")) + 40
    calls = message.get("tool_calls")
    if calls:
        size += len(json.dumps(calls, ensure_ascii=False))
    return size


@dataclass
class Session:
    scenario: str = ""
    system: str = ""
    messages: List[dict] = field(default_factory=list)
    max_chars: int = DEFAULT_MAX_CHARS

    def add_user(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})

    def add_assistant(self, text: str, tool_calls: Optional[list] = None) -> None:
        message = {"role": "assistant", "content": text}
        if tool_calls:
            message["tool_calls"] = tool_calls
        self.messages.append(message)

    def add_tool(self, tool_call_id: str, name: str, content: str) -> None:
        self.messages.append({"role": "tool", "tool_call_id": tool_call_id,
                              "name": name, "content": content})

    def clear(self) -> None:
        self.messages.clear()

    def fit(self) -> Tuple[List[dict], bool]:
        """Messages a envoyer, du plus ancien au plus recent, bornes au
        plafond. Retourne (messages, troncature). Ne mute rien."""
        used = 0
        kept: List[dict] = []
        truncated = False
        for message in reversed(self.messages):
            cost = _size(message)
            if used + cost > self.max_chars and kept:
                truncated = True
                break
            kept.append(message)
            used += cost
        kept.reverse()
        # Un role 'tool' ne peut pas ouvrir la conversation (l'API exige le
        # tool_calls correspondant juste avant).
        while kept and kept[0].get("role") == "tool":
            kept.pop(0)
        return kept, truncated

    def to_dict(self) -> dict:
        return {"scenario": self.scenario, "system": self.system,
                "max_chars": self.max_chars,
                "messages": [dict(m) for m in self.messages]}

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        messages = [m for m in (data.get("messages") or [])
                    if isinstance(m, dict) and m.get("role")]
        # Un historique ecrit avant le repli DSML garde le balisage en clair :
        # le renvoyer apprendrait au modele a en reecrire (vecu 22/10).
        for message in messages:
            if message.get("role") == "assistant":
                message["content"] = strip_dsml(message.get("content"))
        return cls(scenario=str(data.get("scenario") or ""),
                   system=str(data.get("system") or ""),
                   messages=messages,
                   max_chars=int(data.get("max_chars") or DEFAULT_MAX_CHARS))

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(self.to_dict(), ensure_ascii=False,
                                           indent=1))

    @classmethod
    def load(cls, path: Path) -> "Session":
        """Chargement tolerant : historique illisible = session vide, jamais
        un plantage qui empecherait d'ouvrir le scenario."""
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        return cls.from_dict(data) if isinstance(data, dict) else cls()
