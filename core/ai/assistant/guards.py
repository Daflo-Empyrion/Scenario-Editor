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

"""Garde-fous avant envoi d'un texte a un fournisseur distant.

`redact_secrets` est un filtre DUR sur les formes connues de secrets (cles
API, mots de passe, identifiants dans une URL). C'est une heuristique : elle
retire ce qu'elle reconnait et signale le nombre de retraits pour que
l'interface avertissent -- elle ne pretend pas garantir l'absence de toute
donnee sensible.

`writable` porte la politique Q19 : un document modifie mais non sauvegarde
n'est jamais touche par une proposition (refus avec message), pour qu'un
Ctrl+Z ne melange pas une modification humaine et une application IA.
"""
import re
from typing import Tuple

UNSAVED_KEY = "assistant.refuse_unsaved"

_REDACTIONS = (
    # Cles OpenAI/OpenRouter/DeepSeek (sk-...), Groq (gsk_...).
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{10,}"), "sk-***"),
    (re.compile(r"\bgsk_[A-Za-z0-9]{15,}"), "gsk_***"),
    (re.compile(r"(?i)(\bbearer\s+)[A-Za-z0-9._\-]{12,}"), r"\1***"),
    # champ: valeur (api_key=..., password: ..., token ...).
    (re.compile(r"(?i)((?:api[_-]?key|apikey|token|secret|password|passwd)"
                r"\s*[:=]\s*['\"]?)[^\s'\",;]{6,}"), r"\1***"),
    # Identifiants dans une URL (https://user:pass@host).
    (re.compile(r"(?i)(https?://[^\s/:@]+:)[^\s@]+@"), r"\1***@"),
)


def redact_secrets(text: str) -> Tuple[str, int]:
    """Retourne (texte masque, nombre de secrets retires)."""
    hidden = 0
    for pattern, replacement in _REDACTIONS:
        text, count = pattern.subn(replacement, text or "")
        hidden += count
    return text, hidden


def writable(is_modified: bool) -> Tuple[bool, str]:
    """Peut-on proposer une application sur cet onglet ? (ok, cle i18n)."""
    if is_modified:
        return False, UNSAVED_KEY
    return True, ""
