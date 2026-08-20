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

import os
import sys
from pathlib import Path

import pytest

# Ajoute la racine du projet (parent de tests/) au sys.path pour importer core
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Force un affichage virtuel (offscreen) pour les tests touchant a PyQt6 -- evite
# tout echec dans un environnement sans vrai serveur graphique (CI, sandbox...).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    """Instance QApplication partagee pour toute la session de tests -- necessaire
    avant de construire le moindre widget PyQt6. Une seule instance globale (comme
    le voudrait normalement l'appli elle-meme), jamais recreee entre les tests."""
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
