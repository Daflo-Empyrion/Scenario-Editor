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
Taille/position PERSISTEES des fenetres (v1.10.0, demande utilisateur :
ne plus avoir a agrandir les fenetres a la main a chaque ouverture).

track(dialog, "cle") : ajoute les boutons Agrandir/Reduire a la barre de
titre (les QDialog n'ont par defaut qu'une croix), restaure la geometrie
sauvegardee pour cette cle (resize + deplacement, si l'ecran d'origine
existe encore, + etat maximise), puis sauvegarde automatiquement a la
fermeture/masquage (filtre d'evenements -- aucune surcharge de
closeEvent requise). La geometrie part dans settings.json LOCAL.
"""
from PyQt6.QtCore import QEvent, QObject, QPoint, Qt
from PyQt6.QtGui import QGuiApplication

from core import settings


def enable_maximize(dialog) -> None:
    """Boutons Reduire/Agrandir-Restaurer dans la barre de titre. Les
    QDialog n'ont par defaut qu'une croix ; les hints Min/Max + menu
    systeme les affichent SANS changer le type de fenetre (pas d'entree
    en plus dans la barre des taches)."""
    dialog.setWindowFlags(dialog.windowFlags()
                          | Qt.WindowType.WindowMinMaxButtonsHint
                          | Qt.WindowType.WindowMinimizeButtonHint
                          | Qt.WindowType.WindowSystemMenuHint)


def _save(dialog, key: str) -> None:
    maximized = bool(dialog.windowState() & Qt.WindowState.WindowMaximized)
    # fenetre maximisee : sauver la geometrie NORMALE (sinon la
    # de-maximiser offrirait une fenetre plein ecran "figee")
    g = (dialog.normalGeometry() if maximized and dialog.isVisible()
         and dialog.normalGeometry().isValid() else dialog.geometry())
    settings.set_window_geometry(
        key, [int(g.x()), int(g.y()), int(g.width()), int(g.height()),
              1 if maximized else 0])


class _SaveOnClose(QObject):
    """Filtre d'evenements : sauvegarde la geometrie quand la fenetre
    devient invisible. Close couvre la fenetre principale et close() ;
    Hide couvre QDialog.accept()/reject() (done() cache la boite SANS
    evenement Close) -- sauvegarde idempotente, la derniere gagne."""

    def __init__(self, dialog, key: str):
        super().__init__(dialog)
        self._dialog = dialog
        self._key = key

    def eventFilter(self, obj, event):
        if obj is self._dialog and event.type() in (
                QEvent.Type.Close, QEvent.Type.Hide):
            _save(self._dialog, self._key)
        return False


def track(dialog, key: str, default_size: tuple = None) -> None:
    """Boutons Reduire/Agrandir + restauration de la geometrie persistee
    de la fenetre `key` (ou application de `default_size` si rien n'est
    encore sauvegarde), etat maximise compris, et sauvegarde a la
    fermeture/masquage. A appeler EN FIN de __init__."""
    enable_maximize(dialog)
    if default_size:
        dialog.resize(*default_size)
    geo = settings.get_window_geometry(key)
    if geo and len(geo) >= 4:
        try:
            x, y, w, h = (int(v) for v in geo[:4])
        except (TypeError, ValueError):
            x = y = w = h = 0
        if w > 0 and h > 0:
            dialog.resize(w, h)
            # Ne deplacer que si l'ecran d'origine existe toujours
            # (debranchement d'un second ecran, changement de layout).
            if QGuiApplication.screenAt(QPoint(x, y)) is not None:
                dialog.move(x, y)
        if len(geo) >= 5 and geo[4]:
            # etat maximise persiste : applique a l'affichage
            dialog.setWindowState(
                dialog.windowState() | Qt.WindowState.WindowMaximized)
    dialog.installEventFilter(_SaveOnClose(dialog, key))
