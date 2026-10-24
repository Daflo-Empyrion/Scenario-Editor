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

"""Contexte joint a une question (Q7) : ce qui part reellement au modele.

Toujours a la demande, toujours borne et toujours SIGNALE : le contexte est
masque (secrets), coupe au plafond, et l'interface affiche ce qui a ete joint,
sa taille, la troncature et le nombre de secrets retires. Jamais de contexte
implicite envoye en douce.
"""
from dataclasses import dataclass

from .guards import redact_secrets

DEFAULT_CONTEXT_CHARS = 8000


@dataclass(frozen=True)
class TabContext:
    label: str
    text: str
    original_chars: int = 0
    truncated: bool = False
    redacted: int = 0

    @property
    def chars(self) -> int:
        return len(self.text)

    def prompt_block(self) -> str:
        """Bloc insere devant la question. Vide si rien n'est joint."""
        if not self.text:
            return ""
        return (f"[Contexte joint : {self.label}]\n{self.text}\n"
                "[/Contexte joint]")


def build(label: str, text: str,
          max_chars: int = DEFAULT_CONTEXT_CHARS) -> TabContext:
    """Prepare le contexte : masquage d'abord (on ne tronque pas une cle au
    milieu puis on en envoie la moitie), puis coupe au plafond."""
    label = (label or "").strip()
    raw = text or ""
    cleaned, hidden = redact_secrets(raw)
    truncated = len(cleaned) > max_chars
    return TabContext(label=label, text=cleaned[:max_chars],
                      original_chars=len(raw), truncated=truncated,
                      redacted=hidden)
