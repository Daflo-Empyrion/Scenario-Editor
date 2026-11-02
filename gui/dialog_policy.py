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

"""Politique commune des fenetres (demande du 31/10/2026) :

  - bouton Agrandir/Reduire sur TOUTES les fenetres, y compris celles qui
    n'appellent pas gui.window_geometry.track() (25 dialogues sur 85) ;
  - `exec()` ne verrouille plus le reste de l'application : le code qui
    appelle exec() attend toujours la fermeture et recoit le meme code de
    retour (aucun appelant a modifier), mais l'utilisateur peut continuer a
    travailler dans les autres fenetres pendant qu'un rapport est ouvert
    (cas vecu : bilan F5, controles, inspections).

Mise en place : `install()` une seule fois au demarrage (gui.main_window.main).
Les boites de confirmation QMessageBox restent modales : une question
« enregistrer ? » ne doit pas laisser l'utilisateur modifier l'objet de la
question pendant qu'elle est ouverte.

Un seul exemplaire par type de fenetre : demander une seconde fois la meme
fenetre ramene celle deja ouverte au premier plan au lieu d'en empiler une
autre (l'appelant recoit Rejected et ne reapplique rien). Un dialogue qui a
vraiment besoin de plusieurs exemplaires declare `allow_multiple = True`.

Limite connue : une action de fond peut modifier les donnees affichees dans
un rapport deja ouvert (relancer le rapport pour rafraichir).
"""
from PyQt6 import sip
from PyQt6.QtCore import QEventLoop, Qt
from PyQt6.QtWidgets import QDialog, QMessageBox

from gui.window_geometry import enable_maximize

_original_init = QDialog.__init__
_original_exec = QDialog.exec
_installed = False
# fenetre ouverte par type (cle = classe exacte)
_open_dialogs: dict = {}


def _raise_existing(dialog) -> bool:
    """Si une fenetre du meme type est deja ouverte, la ramene au premier
    plan et retourne True (le nouvel exemplaire n'est pas affiche)."""
    if getattr(dialog, "allow_multiple", False):
        return False
    existing = _open_dialogs.get(type(dialog))
    if existing is None or existing is dialog or sip.isdeleted(existing):
        return False
    if existing.isMinimized():
        existing.showNormal()
    existing.raise_()
    existing.activateWindow()
    return True


def exec_without_locking(dialog):
    """Comme QDialog.exec(), avec le meme resultat, mais sans desactiver les
    autres fenetres : boucle d'evenements imbriquee non modale. Si la meme
    fenetre est deja ouverte, elle est ramenee au premier plan et cet
    exemplaire repond Rejected sans s'afficher."""
    if _raise_existing(dialog):
        # pas de deleteLater : l'appelant peut encore lire l'objet apres
        # exec() ; il n'est jamais affiche et disparait avec son parent
        return int(QDialog.DialogCode.Rejected)
    enable_maximize(dialog)
    dialog.setWindowModality(Qt.WindowModality.NonModal)
    dialog.setModal(False)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    loop = QEventLoop()

    def _stop(*_args):
        loop.quit()

    dialog.finished.connect(_stop)
    _open_dialogs[type(dialog)] = dialog
    try:
        loop.exec()
    finally:
        if _open_dialogs.get(type(dialog)) is dialog:
            _open_dialogs.pop(type(dialog), None)
        try:
            dialog.finished.disconnect(_stop)
        except (TypeError, RuntimeError):
            pass              # dialogue detruit par le systeme entre-temps
    return dialog.result()


def _policy_init(self, *args, **kwargs):
    _original_init(self, *args, **kwargs)
    if not isinstance(self, QMessageBox):
        enable_maximize(self)


def _policy_exec(self):
    if isinstance(self, QMessageBox):
        return _original_exec(self)      # une question doit bloquer
    return exec_without_locking(self)


def install() -> None:
    global _installed
    if _installed:
        return
    QDialog.__init__ = _policy_init
    QDialog.exec = _policy_exec
    _installed = True


def uninstall() -> None:
    """Restaure le comportement Qt d'origine (utilise par les tests)."""
    global _installed
    _open_dialogs.clear()
    QDialog.__init__ = _original_init
    QDialog.exec = _original_exec
    _installed = False
