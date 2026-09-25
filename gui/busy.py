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

"""Gardes de chargement pour les operations longues (retour utilisateur du
30/08/2026 : "on a l'impression que rien ne se passe" ; evolué le 23/09/2026 :
gerbe plasma animee au-dela d'une seconde, voir gui/plasma_overlay.py).

- run_long(parent, fn, ...) : fn (calcul pur / reseau — JAMAIS de QWidget)
  tourne dans un thread demon ; le thread GUI pompe une QEventLoop, donc
  l'overlay plasma reste ANIME. L'overlay est present (et bloque l'entree,
  modalite application) des l'entree mais INVISIBLE pendant la premiere
  seconde ; la gerbe n'apparait que si fn dure plus (delay_ms). L'exception
  de fn est relancee sur le thread appelant.
- busy_guard(parent, ...) : context manager pour les blocs qui touchent aux
  widgets (construction de dialogues, onglets...) — travail synchrone donc
  l'image fige apres quelques frames pompees : la gerbe sert d'ecran d'attente
  immediat. La boucle d'evenements n'etant pas pompee pendant le bloc, aucune
  interaction n'est possible (comportement identique a l'ancienne boite).
"""
import threading
from contextlib import contextmanager


def run_long(parent, fn, message_key: str = "busy.please_wait",
             delay_ms: int = 1000):
    """Execute fn hors du thread GUI avec la gerbe plasma au-dela de
    `delay_ms`. Retourne le resultat de fn ; relance son exception.
    CONTRAINTE : fn ne doit PAS creer/toucher de QWidget (hors thread GUI).
    NOTE : on pompe processEvents() tant que le worker vit (pas de
    QEventLoop.exec + invokeMethod : ce chemin s'est fige en test — le
    quit enqueued depuis le thread n'y est jamais delivre)."""
    import time as _time

    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication

    from core.i18n import t
    from gui.plasma_overlay import PlasmaWindow

    app = QApplication.instance()
    outcome: dict = {}

    def _work():
        try:
            outcome["result"] = fn()
        except BaseException as e:  # noqa: BLE001 - relance cote appelant
            outcome["error"] = e
        outcome["done"] = True

    if app is not None:
        app.setOverrideCursor(Qt.CursorShape.WaitCursor)
        overlay = PlasmaWindow(parent, message=t(message_key))
        overlay.start(delay_ms)
        worker = threading.Thread(target=_work, daemon=True,
                                  name="run-long-work")
        worker.start()
        try:
            # Pompe : l'animation vit, l'entree est bloquee par l'overlay
            # modal ; la granularite 10 ms ne coute rien.
            while worker.is_alive():
                app.processEvents()
                if worker.is_alive():
                    _time.sleep(0.01)
        finally:
            worker.join()
            overlay.finish()
            app.restoreOverrideCursor()
    else:                       # sans QApplication (tests purs) : synchrone
        _work()
    error = outcome.get("error")
    if error is not None:
        raise error
    return outcome.get("result")


@contextmanager
def busy_guard(parent=None, message_key: str = "busy.please_wait"):
    """Gerbe plasma immediate + curseur d'attente pendant le bloc `with`
    (blocs synchrones qui touchent aux widgets). Quelques frames sont
    pompees pour peindre l'ecran d'attente AVANT que le travail ne bloque
    la boucle d'evenements."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication

    from core.i18n import t
    from gui.plasma_overlay import PlasmaWindow

    app = QApplication.instance()
    if app is not None:
        app.setOverrideCursor(Qt.CursorShape.WaitCursor)
    overlay = None
    if app is not None:
        overlay = PlasmaWindow(parent, message=t(message_key))
        overlay.start(0)
        # Peint la gerbe MAINTENANT (quelques frames) : ensuite le travail
        # synchrone bloque la boucle, plus aucun repaint ne serait fait.
        for _ in range(8):
            overlay.repaint()
            app.processEvents()
    try:
        yield overlay
    finally:
        if overlay is not None:
            overlay.finish()
        if app is not None:
            app.restoreOverrideCursor()
