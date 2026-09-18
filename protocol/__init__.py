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

"""Protocole de test manuel (Aide > Protocole de test).

Donnees pures FR/EN + petits helpers, historiquement logees dans core/
(sous les noms test_protocol.py / test_protocol_en.py) et deplacees ici
(v1.7.1) : ce ne sont ni du moteur, ni des tests pytest, mais le contenu
du protocole embarque dans l'application.
"""

from protocol.cases import (  # noqa: F401
    CATEGORIES,
    CASES,
    case_has_commands,
    cases_by_category,
    category_label,
    localized_case,
    localized_cases,
    protocol_to_markdown,
)
from protocol.cases_en import CATEGORY_LABELS_EN, EN  # noqa: F401
