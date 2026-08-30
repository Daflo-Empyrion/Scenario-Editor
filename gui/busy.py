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
Garde de chargement pour les operations longues (retour utilisateur du
30/08/2026 : "on a l'impression que rien ne se passe et que le logiciel est
bloque" pendant l'ouverture d'un scenario ou les verifications).

Un context manager (with busy_guard(parent): ...) qui :
1. pose un curseur d'attente application-wide ;
2. affiche IMMEDIATEMENT une boite de progression INDETERMINEE modale a la
   fenetre (l'utilisateur ne peut plus cliquer ailleurs -> ni impression de
   blocage, ni double-declenchement), repeinte une fois via processEvents()
   AVANT que le travail synchrone ne bloque la boucle d'evenements ;
3. ferme tout proprement, meme si le travail leve une exception (le curseur
   d'attente oublie est le classique "appli figee" apres une erreur).

Le travail reste SYNCHRONE (pas de thread) : ces gardes entourent des
operations deja testees, et l'objectif est le retour visuel immediate, pas
le parallelisme.
"""
from contextlib import contextmanager


@contextmanager
def busy_guard(parent=None, message_key: str = "busy.please_wait"):
    """Curseur d'attente + boite de progression indeterminee pendant le
    bloc `with`. Le rendu de la boite est forcé par un processEvents() avant
    d'entrer dans le bloc (le travail synchrone bloque ensuite la boucle)."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication, QProgressDialog

    from core.i18n import t

    app = QApplication.instance()
    if app is not None:
        app.setOverrideCursor(Qt.CursorShape.WaitCursor)
    progress = None
    if app is not None:
        progress = QProgressDialog(t(message_key), None, 0, 0, parent)
        progress.setWindowTitle(t("busy.title"))
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.setMinimumWidth(320)
        progress.show()
        # Peint la boite MAINTENANT : ensuite le travail synchrone bloque la
        # boucle d'evenements, plus aucun repaint ne serait fait.
        app.processEvents()
    try:
        yield progress
    finally:
        if progress is not None:
            progress.close()
        if app is not None:
            app.restoreOverrideCursor()
