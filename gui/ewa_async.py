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
"""Appels asynchrones reseau pour le module EWA : fn (pur / reseau, JAMAIS
de QWidget) en thread demon, resultat de retour dans le thread GUI via un
signal Qt (file d'attente) -- jamais de widget touche hors du thread GUI.

PIEGE PyQt6 6.11 / Py3.14 : une exception qui s'echappe d'un slot = crash
NATIF -- les callbacks sont donc executes sous try/except (log), et le
worker lui-meme capte tout (jamais de relance implicite)."""
import logging
import threading

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class _Bridge(QObject):
    done = pyqtSignal(object)
    fail = pyqtSignal(object)           # Exception passee en object (slots sur)


def async_call(owner: QObject, fn, on_done=None, on_fail=None,
               name: str = "ewa-async"):
    """Execute fn hors du thread GUI ; on_done(resultat) / on_fail(exception)
    sont appeles DANS le thread GUI (connexion queued). owner possede le
    pont : si la fenetre meurt, la reponse pendante est ignoree."""
    bridge = _Bridge()
    bridge.setParent(owner)

    def _dispatch(callback):
        if callback is None:
            return lambda _value: None

        def slot(value):
            try:
                callback(value)
            except Exception:           # noqa: BLE001 - crash natif sinon
                logger.exception("callback EWA")

        return slot

    bridge.done.connect(_dispatch(on_done))
    bridge.fail.connect(_dispatch(on_fail))
    # le polling cree un bridge par appel : libere apres livraison, sinon
    # les QObject morts s'accumulent sur le propriétaire (24/7 = milliers)
    bridge.done.connect(bridge.deleteLater)
    bridge.fail.connect(bridge.deleteLater)

    def _work():
        try:
            result = fn()
        except BaseException as e:      # noqa: BLE001 - relance via signal
            bridge.fail.emit(e)
        else:
            bridge.done.emit(result)

    threading.Thread(target=_work, daemon=True, name=name).start()
