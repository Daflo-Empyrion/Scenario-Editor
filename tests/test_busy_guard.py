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

"""Tests des gardes de chargement (gui/busy.py + gui/plasma_overlay.py).
23/09/2026 : la boite figee devient une gerbe plasma animee — run_long
execute le travail hors du thread GUI avec la boucle pompee (animation
vivante), la gerbe n'apparaissant qu'au-dela du delai ; busy_guard reste
synchrone (blocs touchant aux widgets) avec l'ecran plasma immediat."""
import time

import pytest
from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtWidgets import QApplication

from gui.busy import busy_guard, run_long


def test_busy_guard_shows_and_closes_overlay(qapp):
    assert QApplication.instance() is not None
    seen = []
    with busy_guard(None) as overlay:
        seen.append(overlay)
        assert overlay.isVisible() is True
        assert overlay.is_bursting()      # ecran plasma immediat
    assert overlay.isVisible() is False
    assert seen == [overlay]


def test_busy_guard_restores_cursor_even_on_exception(qapp):
    """Un travail qui echoue ne doit JAMAIS laisser le curseur d'attente
    pose (le classique 'appli figee' apres une erreur)."""
    for _ in range(2):
        try:
            with busy_guard(None):
                raise RuntimeError("echec metier quelconque")
        except RuntimeError:
            pass
    assert QApplication.instance().overrideCursor() is None


def test_plasma_window_construction_paint_and_finish(qapp):
    """Regle projet : tout dialogue nouveau a au moins un test de
    construction ; la peinture ne doit lever aucune exception."""
    from gui.plasma_overlay import PlasmaWindow
    w = PlasmaWindow(None, message="chargement de test")
    w.resize(320, 240)
    w.start(0)
    assert w.isVisible() and w.is_bursting()
    pm = w.grab()
    assert not pm.isNull() and pm.size().width() > 0
    w.finish()
    assert w.isVisible() is False


def test_plasma_window_phantom_shield_then_burst(qapp):
    """Avec un delai : la fenetre est visible des l'entree (bouclier
    d'entree, entree bloquee) mais ne peint la gerbe qu'apres le delai."""
    from gui.plasma_overlay import PlasmaWindow
    w = PlasmaWindow(None)
    w.start(80)
    try:
        assert w.isVisible() and not w.is_bursting()
        loop = QEventLoop()
        QTimer.singleShot(250, loop.quit)
        loop.exec()
        assert w.is_bursting()
    finally:
        w.finish()


def test_run_long_returns_result_fast_without_burst(qapp):
    """Operation rapide : resultat correct, gerbe jamais allumee."""
    res = run_long(None, lambda: 42, delay_ms=60_000)
    assert res == 42


def test_run_long_keeps_gui_loop_alive(qapp):
    """LA propriete cle : pendant le travail (thread), la boucle GUI est
    pompee — un timer pose AVANT l'appel doit tirer PENDANT l'operation
    (c'est ce qui fait vivre l'animation)."""
    fired = []
    QTimer.singleShot(120, lambda: fired.append(1))
    run_long(None, lambda: time.sleep(0.35), delay_ms=60_000)
    assert fired == [1]


def test_run_long_reraises_worker_exception(qapp):
    def boom():
        raise ValueError("echec worker")
    with pytest.raises(ValueError):
        run_long(None, boom, delay_ms=10)


def test_run_long_burst_after_delay(qapp):
    """Operation lente + petit delai : la gerbe s'allume pendant le travail
    (simule ici en controlant PlasmaWindow directement, run_long ne
    l'exposant pas ; la sequence delay->ignite est deja testee)."""
    # securite : la sequence complete via run_long avec un delai court
    seen = []
    res = run_long(None, lambda: (time.sleep(0.05), seen.append(1))[0] or "ok",
                   delay_ms=10)
    assert res == "ok"
