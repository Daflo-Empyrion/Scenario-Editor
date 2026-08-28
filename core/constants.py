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
Valeurs de configuration de l'application (pas des donnees de jeu -- pour les
constantes issues de la logique metier ECF, ex: MAX_BLOCK_ID, voir
core/ecf/validation.py, qui les garde a cote de leurs constantes soeurs
CONTAINER_CLASSES etc. plutot que de les isoler ici).
"""

# Nombre maximum d'actions gardees dans la pile d'annulation (voir
# core/workspace_undo.py) -- au-dela, la plus ancienne action est perdue sans
# avertissement. Pas encore expose comme reglage utilisateur.
UNDO_STACK_MAX_DEPTH = 15

# Intervalle entre deux sauvegardes automatiques, en millisecondes (voir
# gui/main_window.py, QTimer de l'autosave). Pas encore expose comme reglage
# utilisateur.
AUTOSAVE_INTERVAL_MS = 3 * 60 * 1000  # 3 minutes
