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

"""Persistance taille/position des fenetres (v1.10.0, gui/window_geometry.py)
-- demande utilisateur : ne plus avoir a agrandir a la main a chaque
ouverture. Sauvegarde au Hide (couvre QDialog.accept()) ET au Close,
restauration avec garde multi-ecran. Settings isoles."""

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog

from core import settings
from gui.window_geometry import track


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")


def test_track_adds_maximize_buttons(qapp):
    """Demande utilisateur : les QDialog n'ont qu'une croix par defaut --
    track doit poser les hints Reduire/Agrandir-Restaurer."""
    dlg = QDialog()
    assert not (dlg.windowFlags() & Qt.WindowType.WindowMinMaxButtonsHint)
    track(dlg, "test_flags", default_size=(600, 400))
    assert dlg.windowFlags() & Qt.WindowType.WindowMinMaxButtonsHint
    assert dlg.windowFlags() & Qt.WindowType.WindowMinimizeButtonHint
    dlg.deleteLater()


def test_default_size_when_nothing_saved(qapp):
    dlg = QDialog()
    track(dlg, "test_win", default_size=(700, 500))
    assert dlg.size().width() == 700 and dlg.size().height() == 500
    dlg.deleteLater()


def test_geometry_saved_on_accept_and_restored(qapp):
    dlg = QDialog()
    track(dlg, "test_win", default_size=(700, 500))
    dlg.show()  # accept() sur un dialogue JAMAIS visible ne delivre aucun
    # evenement Hide (rien ne se cache) -- dans l'app il est toujours montre
    dlg.resize(980, 640)
    dlg.accept()  # QDialog.done() : Hide SANS evenement Close -- doit sauver
    saved = settings.get_window_geometry("test_win")
    assert len(saved) >= 4 and saved[2] == 980 and saved[3] == 640
    assert saved[4] == 0  # non maximisee

    dlg2 = QDialog()
    track(dlg2, "test_win")
    # restauree a l'identique SAUF si l'ecran de test est plus petit
    # (bornage a l'ecran d'accueil, retour utilisateur 07/11)
    from PyQt6.QtGui import QGuiApplication
    avail = QGuiApplication.primaryScreen().availableGeometry()
    assert dlg2.size().width() == min(980, avail.width())
    assert dlg2.size().height() == min(640, avail.height())
    dlg2.deleteLater()


def test_maximized_state_saved_and_restored(qapp):
    """Fenetre maximisee : on sauve la geometrie NORMALE + le flag (pas le
    plein ecran), et la restauration remaximise."""
    dlg = QDialog()
    track(dlg, "test_max", default_size=(600, 400))
    dlg.show()
    dlg.showMaximized()
    dlg.accept()
    saved = settings.get_window_geometry("test_max")
    assert saved[4] == 1
    assert saved[2] == 600 and saved[3] == 400  # geometrie normale, pas l'ecran

    dlg2 = QDialog()
    track(dlg2, "test_max")
    assert dlg2.windowState() & Qt.WindowState.WindowMaximized
    dlg2.deleteLater()


def test_geometry_saved_on_close(qapp):
    dlg = QDialog()
    track(dlg, "test_close", default_size=(400, 300))
    dlg.resize(520, 460)
    dlg.close()  # QEvent.Close -- chemin de la fenetre principale
    saved = settings.get_window_geometry("test_close")
    assert saved[2] == 520 and saved[3] == 460


def test_bogus_saved_geometry_ignored(qapp):
    settings.set_window_geometry("test_bad", [10, 10, 0, 0])  # taille nulle
    dlg = QDialog()
    track(dlg, "test_bad", default_size=(600, 400))
    assert dlg.size().width() == 600
    settings.set_window_geometry("test_bad2", "corrompu")
    dlg2 = QDialog()
    track(dlg2, "test_bad2", default_size=(600, 400))
    assert dlg2.size().width() == 600
    dlg.deleteLater()
    dlg2.deleteLater()


def test_offscreen_position_not_restored_outside_screens(qapp):
    # position sur un ecran inexistant : la TAILLE est restauree, pas la
    # position (fenetre introuvable sinon -- second ecran debranche).
    from PyQt6.QtCore import QPoint
    from PyQt6.QtGui import QGuiApplication
    screen = QGuiApplication.primaryScreen().geometry()
    far_x = screen.x() + screen.width() + 20000
    settings.set_window_geometry("test_offscreen", [far_x, 10, 800, 600])
    dlg = QDialog()
    track(dlg, "test_offscreen")
    assert dlg.size().width() == 800
    assert not dlg.geometry().contains(QPoint(far_x, 10))
    dlg.deleteLater()


def test_restored_size_clamped_to_screen(qapp):
    """Retour utilisateur 07/11 : geometrie sauvegardee sur un ecran de
    2560 px, restoree sur un ecran de 1920 -> QWindowsWindow::setGeometry
    alerte et la fenetre arrive tronquee. La restauration doit borner la
    taille a l'ecran d'accueil."""
    from PyQt6.QtGui import QGuiApplication
    screen = QGuiApplication.primaryScreen()
    avail = screen.availableGeometry()
    dlg = QDialog()
    track(dlg, "test_clamp", default_size=(600, 400))
    # simule une geometrie sauvegardee plus large que l'ecran
    settings.set_window_geometry(
        "test_clamp", [avail.left() + 10, avail.top() + 10,
                       avail.width() + 800, avail.height() + 400, 0])
    dlg2 = QDialog()
    track(dlg2, "test_clamp", default_size=(600, 400))
    assert dlg2.width() <= avail.width()
    assert dlg2.height() <= avail.height()
    # fenetre encore atteignable : pas envoyee hors ecran
    assert dlg2.x() >= avail.left()
    dlg2.deleteLater()
