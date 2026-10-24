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

"""Assistant IA de l'editeur (socle, sans interface).

Invariants decides le 21/10/2026 (voir CONTEXTE_REPRISE / questionnaire) :
  - l'assistant ne MUTE jamais un document : il propose un ChangeSet, l'appli
    l'applique apres revue (undo + sauvegarde centrale) ;
  - les outils exposes au modele sont en LECTURE SEULE et bornes ;
  - chaque action declare sa capacite (min_class, needs_tools) : le routeur
    filtre la chaine des maillons, aucune degradation silencieuse ;
  - la traduction reste le circuit existant ; la reecriture libre est une
    action distincte.
"""
from . import (actions, changeset, context, engine, guards, prompts, session,
               tools)  # noqa: F401
