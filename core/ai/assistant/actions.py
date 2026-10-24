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

"""Contrat d'une action d'assistant (catalogue rempli par les surfaces).

Une action declare ce qu'elle exige du modele, pas l'inverse (Q34/C3) :
  - `min_class` : light (question simple) / normal (analyse) / strong
    (generation longue) -- le routeur ecarte les maillons qui ne suivent pas ;
  - `needs_tools` : l'action lit le document via des outils (lecture seule) ;
    sans maillon a outils, elle est indisponible avec une raison claire ;
  - `produces_changeset` : la reponse doit contenir un ChangeSet a revoir ;
  - `instruction` : consigne utilisateur envoyee avec le contexte de surface.

Les libelles visibles (nom de l'action) resteront cote interface : ce module
ne contient aucune chaine affichee.
"""
from dataclasses import dataclass

from ..router import CLASS_RANK


@dataclass(frozen=True)
class Action:
    id: str
    surface: str
    min_class: str = "normal"
    needs_tools: bool = False
    produces_changeset: bool = False
    instruction: str = ""

    def __post_init__(self):
        if self.min_class not in CLASS_RANK:
            raise ValueError(f"Niveau inconnu : {self.min_class!r}")
        if not (self.id or "").strip() or not (self.surface or "").strip():
            raise ValueError("Une action exige un id et une surface")
