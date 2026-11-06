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

"""Chrome style webapp (gui/chrome.py, 31/10) : fenetre sans cadre, barre
de titre maison au-dessus des menus, reversible par reglage.

ATTENTION (vecu 31/10) : _make_window(fresh=False) renvoie une fenetre
CACHEE PARTAGEE (_WINDOW_CACHE) reutilisee par test_theme_verriere ensuite
-- ne JAMAIS la fermer (la fermeture + collecte tuait ses QMenu en suite
complete). Seules les fenetres fresh=True sont fermees."""
import json
import sys

import pytest
from PyQt6.QtCore import Qt

from test_theme_verriere_and_reorg import _make_window


def _fresh_with_chrome(qapp, monkeypatch):
    """Chrome DESACTIVE par defaut depuis le 02/11 (abort natif frameless) :
    les tests qui verifient son FONCTIONNEMENT doivent l'activer, les autres
    (test_disabled_setting_keeps_native_bar) verifient justement le defaut."""
    from core import settings
    monkeypatch.setattr(settings, "get_titlebar_custom_enabled", lambda: True)
    return _make_window(qapp, monkeypatch, None, fresh=True)


def _all_actions(menu):
    out = []
    for a in menu.actions():
        out.append(a)
        if a.menu() is not None:
            out.extend(_all_actions(a.menu()))
    return out


@pytest.mark.skipif(sys.platform != "win32",
                    reason="chrome frameless specifique Windows")
class TestChrome:

    def test_installed_when_enabled(self, qapp, monkeypatch):
        from gui import chrome
        win = _fresh_with_chrome(qapp, monkeypatch)
        try:
            assert chrome.is_available()
            assert win._chrome_installed is True
            assert win.windowFlags() & Qt.WindowType.FramelessWindowHint
            assert win._chrome_state.title_bar is not None
        finally:
            win.close()

    def test_menus_still_native(self, qapp, monkeypatch):
        """La QMenuBar reste le menu widget natif (jamais remplacee — vecu
        31/10 : setMenuWidget faisait deleteLater sur l'ancienne barre, qui
        tuait les QMenu des que une boucle d'evenements pompait)."""
        win = _fresh_with_chrome(qapp, monkeypatch)
        try:
            assert win.action_tech_tree in _all_actions(win.menu_tools)
            # la marge haute reserve la place de la barre custom
            assert win.contentsMargins().top() >= 42
        finally:
            win.close()

    def test_breadcrumb_follows_project(self, qapp, monkeypatch):
        from gui import chrome
        win = _fresh_with_chrome(qapp, monkeypatch)
        try:
            bar = win._chrome_state.title_bar
            chrome.set_project(win, "RE2-ATL-PRO")
            assert any(lab.text() == "RE2-ATL-PRO"
                       for lab in bar.findChildren(type(bar._project_label)))
            chrome.set_project(win, "")
            assert all(not lab.isVisible()
                       for lab in bar.findChildren(type(bar._project_label)))
        finally:
            win.close()

    def test_disabled_setting_keeps_native_bar(self, qapp, monkeypatch):
        from core import settings
        monkeypatch.setattr(settings, "get_titlebar_custom_enabled",
                            lambda: False)
        win = _make_window(qapp, monkeypatch, None, fresh=True)
        try:
            assert settings.get_titlebar_custom_enabled() is False
            # install() a refuse : pas de state pose, barre native conservee
            assert getattr(win, "_chrome_state", None) is None
            assert win._chrome_installed is False
        finally:
            win.close()

    def test_unavailable_dependency_falls_back(self, qapp, monkeypatch):
        from gui import chrome
        monkeypatch.setattr(chrome, "is_available", lambda: False)
        win = _make_window(qapp, monkeypatch, None, fresh=True)
        try:
            assert win._chrome_installed is False
            assert not (win.windowFlags() & Qt.WindowType.FramelessWindowHint)
        finally:
            win.close()


def test_nav_rail_wraps_central_and_launches(qapp, monkeypatch):
    """Le rail enveloppe le central widget, 8 lanceurs, et un clic appelle
    bien la methode MainWindow correspondante."""
    win = _fresh_with_chrome(qapp, monkeypatch)
    try:
        rail = win._chrome_state.nav_rail
        assert rail is not None and len(rail._buttons) == 8
        # le central d'origine est embarque dans un conteneur avec le rail
        central = win.centralWidget()
        assert rail.parent() is central or rail in central.findChildren(type(rail))
        # le clic est connecte a la methode REELLE (liee a la construction) :
        # sans workspace, elle affiche un message — on verifie ce chemin
        # (QMessageBox.information neutralise, sinon boucle modale sans
        # clicseur — vecu 01/11 : le test hangait).
        from PyQt6.QtWidgets import QMessageBox
        msgs = []
        monkeypatch.setattr(QMessageBox, "information",
                            lambda *a, **k: msgs.append(1))
        rail._buttons[0][0].click()
        assert msgs == [1]
    finally:
        win.close()

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

"""Chrome style webapp (gui/chrome.py, 31/10) : fenetre sans cadre, barre
de titre maison au-dessus des menus, reversible par reglage.

ATTENTION (vecu 31/10) : _make_window(fresh=False) renvoie une fenetre
CACHEE PARTAGEE (_WINDOW_CACHE) reutilisee par test_theme_verriere ensuite
-- ne JAMAIS la fermer (la fermeture + collecte tuait ses QMenu en suite
complete). Seules les fenetres fresh=True sont fermees."""
import json
import sys

import pytest
from PyQt6.QtCore import Qt

from test_theme_verriere_and_reorg import _make_window


def _fresh_with_chrome(qapp, monkeypatch):
    """Chrome DESACTIVE par defaut depuis le 02/11 (abort natif frameless) :
    les tests qui verifient son FONCTIONNEMENT doivent l'activer, les autres
    (test_disabled_setting_keeps_native_bar) verifient justement le defaut."""
    from core import settings
    monkeypatch.setattr(settings, "get_titlebar_custom_enabled", lambda: True)
    return _make_window(qapp, monkeypatch, None, fresh=True)


def _all_actions(menu):
    out = []
    for a in menu.actions():
        out.append(a)
        if a.menu() is not None:
            out.extend(_all_actions(a.menu()))
    return out


@pytest.mark.skipif(sys.platform != "win32",
                    reason="chrome frameless specifique Windows")
class TestChrome:

    def test_installed_when_enabled(self, qapp, monkeypatch):
        from gui import chrome
        win = _fresh_with_chrome(qapp, monkeypatch)
        try:
            assert chrome.is_available()
            assert win._chrome_installed is True
            assert win.windowFlags() & Qt.WindowType.FramelessWindowHint
            assert win._chrome_state.title_bar is not None
        finally:
            win.close()

    def test_menus_still_native(self, qapp, monkeypatch):
        """La QMenuBar reste le menu widget natif (jamais remplacee — vecu
        31/10 : setMenuWidget faisait deleteLater sur l'ancienne barre, qui
        tuait les QMenu des que une boucle d'evenements pompait)."""
        win = _fresh_with_chrome(qapp, monkeypatch)
        try:
            assert win.action_tech_tree in _all_actions(win.menu_tools)
            # la marge haute reserve la place de la barre custom
            assert win.contentsMargins().top() >= 42
        finally:
            win.close()

    def test_breadcrumb_follows_project(self, qapp, monkeypatch):
        from gui import chrome
        win = _fresh_with_chrome(qapp, monkeypatch)
        try:
            bar = win._chrome_state.title_bar
            chrome.set_project(win, "RE2-ATL-PRO")
            assert any(lab.text() == "RE2-ATL-PRO"
                       for lab in bar.findChildren(type(bar._project_label)))
            chrome.set_project(win, "")
            assert all(not lab.isVisible()
                       for lab in bar.findChildren(type(bar._project_label)))
        finally:
            win.close()

    def test_disabled_setting_keeps_native_bar(self, qapp, monkeypatch):
        from core import settings
        monkeypatch.setattr(settings, "get_titlebar_custom_enabled",
                            lambda: False)
        win = _make_window(qapp, monkeypatch, None, fresh=True)
        try:
            assert settings.get_titlebar_custom_enabled() is False
            # install() a refuse : pas de state pose, barre native conservee
            assert getattr(win, "_chrome_state", None) is None
            assert win._chrome_installed is False
        finally:
            win.close()

    def test_unavailable_dependency_falls_back(self, qapp, monkeypatch):
        from gui import chrome
        monkeypatch.setattr(chrome, "is_available", lambda: False)
        win = _make_window(qapp, monkeypatch, None, fresh=True)
        try:
            assert win._chrome_installed is False
            assert not (win.windowFlags() & Qt.WindowType.FramelessWindowHint)
        finally:
            win.close()


def test_nav_rail_wraps_central_and_launches(qapp, monkeypatch):
    """Le rail enveloppe le central widget, 8 lanceurs, et un clic appelle
    bien la methode MainWindow correspondante."""
    win = _fresh_with_chrome(qapp, monkeypatch)
    try:
        rail = win._chrome_state.nav_rail
        assert rail is not None and len(rail._buttons) == 8
        # le central d'origine est embarque dans un conteneur avec le rail
        central = win.centralWidget()
        assert rail.parent() is central or rail in central.findChildren(type(rail))
        # le clic est connecte a la methode REELLE (liee a la construction) :
        # sans workspace, elle affiche un message — on verifie ce chemin
        # (QMessageBox.information neutralise, sinon boucle modale sans
        # clicseur — vecu 01/11 : le test hangait).
        from PyQt6.QtWidgets import QMessageBox
        msgs = []
        monkeypatch.setattr(QMessageBox, "information",
                            lambda *a, **k: msgs.append(1))
        rail._buttons[0][0].click()
        assert msgs == [1]
    finally:
        win.close()

