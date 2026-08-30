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

"""Tests du garde de chargement (gui/busy.py), ajoute apres le retour
utilisateur du 30/08/2026 : pendant les operations longues (ouverture de
scenario, verifications), l'application semblait bloquee -- le garde pose un
curseur d'attente et affiche une boite de progression indeterminee modale a
la fenetre, puis restaure TOUT, meme si le travail leve une exception."""
from PyQt6.QtWidgets import QApplication, QProgressDialog

from gui.busy import busy_guard


def test_busy_guard_shows_and_closes_progress(qapp):
    assert QApplication.instance() is not None
    seen = []
    with busy_guard(None) as progress:
        seen.append(progress)
        assert isinstance(progress, QProgressDialog)
        assert progress.isVisible() is True
        assert progress.maximum() == 0  # indeterminee (0..0)
    assert progress.isVisible() is False
    assert seen == [progress]


def test_busy_guard_restores_cursor_even_on_exception(qapp):
    """Un travail qui echoue ne doit JAMAIS laisser le curseur d'attente
    pose (le classique 'appli figee' apres une erreur)."""
    for _ in range(2):
        try:
            with busy_guard(None):
                raise RuntimeError("echec metier quelconque")
        except RuntimeError:
            pass
    # restoreOverrideCursor a ete appele autant de fois que setOverrideCursor
    # : aucun curseur residuel (sinon ce serait le dernier emit qui gagnerait
    # et l'appli resterait en sablier). Verifie par le compteur interne de Qt.
    assert QApplication.instance().overrideCursor() is None
