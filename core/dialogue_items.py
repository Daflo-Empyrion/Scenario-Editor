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

"""
Autocompletion des ITEMS dans les scripts de dialogue (v1.9.0, backlog
"Dialogues.ecf : autocompletion des items give/take") : les dialogues du
jeu manipulent les objets via AddItem('Id', n), RemoveItem('Id', n) et
HasItem('Id', n) -- formes relevees sur le vrai Dialogues.ecf vanille
(Execute, OptionIf, OptionExecute, NextIf). L'Id est un nom d'item du
catalogue (ItemsConfig/BlocksConfig) : l'editeur propose les noms du
catalogue scenario+vanille pendant la saisie, entre les apostrophes.
"""
import re
from typing import Optional

# Commandes du jeu dont le PREMIER argument est un Id d'item entre
# apostrophes (releve sur le Dialogues.ecf vanille 21/09/2026).
ITEM_COMMANDS = ("AddItem", "RemoveItem", "HasItem")

# Cles de propriete de dialogue dont la valeur est du script (avec suffixe
# numerique eventuel : Execute_1, OptionIf_2...).
SCRIPT_VALUE_KEYS = frozenset({"Execute", "OptionExecute", "OptionIf",
                               "NextIf", "If"})

# Apostrophe ouvrante d'un Id d'item, token partiel jusqu'au bout de la
# chaine recue (le CURSEUR doit donc etre coupe avant l'appel) : le groupe
# capture echoue des qu'une apostrophe fermante apparait -- on ne propose
# rien une fois l'Id ferme (les arguments suivant sont des nombres).
_ITEM_TOKEN_RE = re.compile(
    r"\b(" + "|".join(ITEM_COMMANDS) + r")\s*\(\s*'([^']*)\Z")


def script_value_key(key: str) -> bool:
    """Vrai si la cle de propriete porte du script de dialogue (Execute_1,
    OptionIf_2... -- suffixe numerique tolere)."""
    base = (key or "").split("_", 1)[0]
    return base in SCRIPT_VALUE_KEYS


def quoted_item_token(text: str, cursor: int) -> Optional[str]:
    """Partie DEJA SAISIE de l'Id d'item sous le curseur, si le curseur est
    entre l'apostrophe ouvrante d'une commande item et sa fermeture --
    None sinon (pas une commande item, ou Id deja ferme : les arguments
    suivants sont des nombres, rien a completer)."""
    if not text or cursor < 0:
        return None
    head = text[:min(cursor, len(text))]
    m = _ITEM_TOKEN_RE.search(head)
    if not m:
        return None
    return m.group(2)
