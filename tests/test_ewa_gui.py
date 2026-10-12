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
"""Fenetres EWA : construction COMPLETE (PyQt6.11 : exception en slot =
crash natif -- chaque chemin reel est construit une fois), remplissage
dashboard, filtres chat/joueurs, persistence de la configuration et
async_call (retour thread -> thread GUI via signaux). Tout est MOCKE :
jamais de reseau dans les tests."""

import json
import time

import pytest

from core import settings


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    settings.set_ewa({})


class _FakeDialog:
    """Squelette du EwaServerDialog pour construire les onglets seuls."""

    def __init__(self):
        self.client = None
        self.errors: list = []

    def show_error(self, error):
        self.errors.append(error)

    def telnet_console(self):
        raise AssertionError("pas de telnet dans ce test")

    def drop_telnet(self):
        pass

    def parent(self):
        return None


def _pump(qapp, deadline_s=3.0):
    """Pompe la boucle jusqu'a ce que done() passe (signaux threads)."""
    deadline = time.monotonic() + deadline_s
    while time.monotonic() < deadline:
        qapp.processEvents()
        if _pump.flag:
            return True
        time.sleep(0.01)
    return False


_pump.flag = False


# ------------------------------------------------------------- config dialog

def test_config_dialog_builds(qapp):
    from gui.ewa_config_dialog import EwaConfigDialog
    dlg = EwaConfigDialog()
    dlg.show()
    try:
        assert dlg.url_edit.text() == ""
        assert dlg.ssl_check.isChecked()      # auto-signé accepté par défaut
        assert not dlg.remember_check.isChecked()
    finally:
        dlg.close()
        dlg.deleteLater()


def test_config_dialog_saves_and_normalizes(qapp):
    from gui.ewa_config_dialog import EwaConfigDialog
    from PyQt6.QtWidgets import QDialog
    dlg = EwaConfigDialog()
    try:
        dlg.url_edit.setText("51.254.47.151:5001/")
        dlg.user_edit.setText("bob")
        dlg.password_edit.setText("pwd")
        dlg.remember_check.setChecked(True)
        dlg.sftp_host_edit.setText("51.254.47.151")
        dlg.sftp_port_spin.setValue(2257)
        dlg.tel_port_spin.setValue(30005)
        dlg._save_and_close()
        stored = settings.get_ewa()
        assert stored["url"] == "https://51.254.47.151:5001"
        assert stored["password"] == "pwd"          # remember coche
        assert stored["sftp"]["port"] == 2257
        assert stored["telnet"]["port"] == 30005
    finally:
        dlg.deleteLater()
    # relecture : le dialogue recharge tout
    dlg2 = EwaConfigDialog()
    try:
        assert dlg2.url_edit.text() == "https://51.254.47.151:5001"
    finally:
        dlg2.deleteLater()
    assert QDialog.DialogCode.Accepted is not None


def test_config_dialog_drops_password_when_not_remembered(qapp):
    from gui.ewa_config_dialog import EwaConfigDialog
    dlg = EwaConfigDialog()
    try:
        dlg.url_edit.setText("https://srv:5001")
        dlg.user_edit.setText("bob")
        dlg.password_edit.setText("pwd")
        dlg.remember_check.setChecked(False)
        dlg._save_and_close()
        assert settings.get_ewa()["password"] == ""
        assert EwaConfigDialog().password_edit.text() == ""
    finally:
        dlg.deleteLater()


# ------------------------------------------------------------ install dialog

def test_install_dialog_builds(qapp):
    from gui.ewa_install_dialog import EwaInstallDialog
    dlg = EwaInstallDialog()
    dlg.show()
    try:
        assert "EWA" in dlg._build_html()
    finally:
        dlg.close()
        dlg.deleteLater()


# ------------------------------------------------------------ server dialog

def test_server_dialog_builds_all_tabs(qapp):
    from gui.ewa_dialog import EwaServerDialog
    dlg = EwaServerDialog(parent=None, auto_connect=False)
    dlg.show()
    try:
        assert dlg.tabs.count() == 10
        titles = [dlg.tabs.tabText(i) for i in range(dlg.tabs.count())]
        assert all(titles), "un onglet sans titre"
        assert dlg.client is None
        # tick sans client : aucun plantage
        dlg._tick_visible_tab(force=True)
    finally:
        dlg.close()
        dlg.deleteLater()


def test_each_tab_builds_against_stub(qapp):
    from gui.ewa_tabs_admin import ServerTab, UsersTab
    from gui.ewa_tabs_local import ConsoleTab, DeployTab
    from gui.ewa_tabs_players import ChatTab, PlayersTab
    from gui.ewa_tabs_world import RestoreTab, StructuresTab, TimetableTab
    from gui.ewa_dialog import DashboardTab

    stub = _FakeDialog()
    for tab_class in (DashboardTab, ChatTab, PlayersTab, StructuresTab,
                      RestoreTab, TimetableTab, ServerTab, UsersTab,
                      ConsoleTab, DeployTab):
        tab = tab_class(stub)
        try:
            tab.show()
            qapp.processEvents()
        finally:
            tab.deleteLater()


def test_dashboard_fill_handles_casing(qapp):
    from gui.ewa_dialog import DashboardTab
    tab = DashboardTab(_FakeDialog())
    try:
        tab._fill({
            "serverName": "Serveur-MP",
            "online": "o",
            "versionESG": "1.20",
            "versionESGBuild": "3863",
            "activePlayers": 3,
            "activePlayfields": 5,
            "totalPlayfieldserver": 12,
            "cpuTotalLoad": 42,
            "ramTotalMB": 32768,
            "ramAvailableMB": 16384,
            "diskUsedSpace": 1024 ** 4,
            "diskFreeSpace": 1024 ** 4,
            "ewaMemorySize": 512,
        })
        assert tab.values["server"].text() == "Serveur-MP"
        assert tab.values["players"].text() == "3"
        assert "16.0 GB" in tab.values["ram"].text()
        assert "42 %" in tab.values["cpu"].text()
    finally:
        tab.deleteLater()


def test_chat_render_filters(qapp):
    from gui.ewa_tabs_players import ChatTab
    tab = ChatTab(_FakeDialog())
    try:
        tab._messages = [
            {"Timestamp": "2026-10-06T21:44:11.5", "FactionName": "SERV",
             "PlayerName": "Server", "Message": "redemarrage"},
            {"Timestamp": "2026-10-06T21:45:12.9", "FactionName": "INV",
             "PlayerName": "Bob", "Message": "salut"},
            {"Timestamp": "2026-10-06T21:45:40.0", "FactionName": "INV",
             "PlayerName": "Bob", "Message": "/login test"},
        ]
        tab._render()
        assert tab.list_widget.count() == 1        # SERV et / masques
        assert "Bob" in tab.list_widget.item(0).text()
        assert tab.list_widget.item(0).text().startswith("21:45")
        tab.hide_serv_check.setChecked(False)
        assert tab.list_widget.count() == 2        # le SAY serveur revient
    finally:
        tab.deleteLater()


def test_players_table_render_and_filter(qapp):
    from gui.ewa_tabs_players import PlayersTab
    tab = PlayersTab(_FakeDialog())
    try:
        tab._players = [
            {"PlayerName": "Bob", "Online": True, "Playfield": "Akua",
             "Ping": 30, "FactionId": 2, "Credits": 500, "SteamId": "7654"},
            {"PlayerName": "Alice", "Online": False, "Playfield": "Omicron",
             "Ping": 0, "FactionId": 1, "Credits": 0, "SteamId": "7655"},
        ]
        tab._render_table()
        assert tab.table.rowCount() == 2
        tab.filter_edit.setText("bob")
        assert tab.table.rowCount() == 1
        assert tab.table.item(0, 0).text() == "Bob"
        tab.table.selectRow(0)
        assert tab._selected_player()["PlayerName"] == "Bob"
    finally:
        tab.deleteLater()


def test_async_call_delivers_in_gui_thread(qapp):
    from PyQt6.QtCore import QObject
    from gui.ewa_async import async_call

    owner = QObject()
    results: list = []
    errors: list = []
    _pump.flag = False

    def done(value):
        results.append(value)
        _pump.flag = True

    def fail(error):
        errors.append(error)
        _pump.flag = True

    async_call(owner, lambda: 42, done, fail)
    assert _pump(qapp)
    assert results == [42] and errors == []

    def boom():
        raise RuntimeError("kaput")

    _pump.flag = False
    async_call(owner, boom, done, fail)
    assert _pump(qapp)
    assert len(errors) == 1 and str(errors[0]) == "kaput"
    owner.deleteLater()


# ------------------------------------------------- chemins connectes (v1.16)

class _FakeClient:
    """Client EWA factice : reponses statiques, appels enregistres."""

    def __init__(self, players=None, chats=None, timetable=None):
        self.players = players or []
        self.chats = chats or []
        self.timetable = timetable or []
        self.run_all: list = []
        self.run_sub: list = []

    def get_players(self):
        return self.players

    def get_chats(self, top=200):
        return self.chats[:top]

    def get_timetable(self):
        return self.timetable

    def run_timetable(self, subs):
        self.run_all.append(subs)

    def run_timetable_sub(self, sub):
        self.run_sub.append(sub)


def _wait(qapp, condition, deadline_s=3.0):
    deadline = time.monotonic() + deadline_s
    while time.monotonic() < deadline:
        qapp.processEvents()
        if condition():
            return True
        time.sleep(0.01)
    return False


def test_players_refresh_connected_no_crash_and_selection_follows(qapp):
    """Le bug du 09/10 : self.client n'existait pas sur 7 onglets ->
    AttributeError en slot = crash natif. Et le polling ne doit pas
    decaler la selection (kick du mauvais joueur)."""
    from gui.ewa_tabs_players import PlayersTab
    bob = {"PlayerName": "Bob", "SteamId": "1", "Online": True}
    alice = {"PlayerName": "Alice", "SteamId": "2", "Online": False}
    tab = PlayersTab(_FakeDialog())
    try:
        tab.dialog.client = _FakeClient(players=[bob, alice])
        tab.refresh()
        assert _wait(qapp, lambda: tab.table.rowCount() == 2)
        assert tab.dialog.errors == []
        tab.table.selectRow(0)                  # Bob
        # le serveur renvoie Alice d'abord : la selection suit BOB
        tab.dialog.client = _FakeClient(players=[alice, bob])
        tab.refresh()
        assert _wait(qapp, lambda: tab.table.item(0, 0).text() == "Alice")
        qapp.processEvents()
        assert tab._selected_player()["PlayerName"] == "Bob"
    finally:
        tab.deleteLater()


def test_chat_poll_dedupes_repeated_odata_pages(qapp):
    from gui.ewa_tabs_players import ChatTab
    chat = {"Timestamp": "2026-10-09T21:45:12.9", "FactionName": "INV",
            "PlayerName": "Bob", "Message": "salut"}
    tab = ChatTab(_FakeDialog())
    try:
        tab.dialog.client = _FakeClient(chats=[chat])
        tab._poll()
        assert _wait(qapp, lambda: len(tab._messages) == 1)
        tab._poll()                             # meme page : aucun doublon
        qapp.processEvents()
        time.sleep(0.05)
        qapp.processEvents()
        assert len(tab._messages) == 1
    finally:
        tab.deleteLater()


def test_timetable_run_resolves_selection_in_gui_thread(qapp):
    """Le worker ne doit NI toucher au tree NI relire json_edit : la
    subAction est resolue dans le thread GUI avant async_call."""
    from gui.ewa_tabs_world import TimetableTab
    sub = {"active": True, "actionType": "SAY", "data": "bonjour"}
    actions = [{"repeat": "daily", "subAction": [sub]}]
    tab = TimetableTab(_FakeDialog())
    try:
        client = _FakeClient(timetable=actions)
        tab.dialog.client = client
        tab._fill_tree(actions)
        tab.json_edit.setPlainText(json.dumps(actions))
        item = tab.tree.topLevelItem(0).child(0)
        tab.tree.setCurrentItem(item)
        tab._run_selected()
        assert _wait(qapp, lambda: client.run_sub == [sub])
        assert client.run_all == []
    finally:
        tab.deleteLater()


def test_config_save_gates_sftp_and_telnet_passwords(qapp):
    """Sans « Se souvenir », AUCUN mot de passe ne doit rester sur disque
    (avant : SFTP et telnet passaient toujours, en clair)."""
    from gui.ewa_config_dialog import EwaConfigDialog
    dlg = EwaConfigDialog()
    try:
        dlg.password_edit.setText("pwd")
        dlg.sftp_password_edit.setText("sftp-pwd")
        dlg.tel_password_edit.setText("tel-pwd")
        dlg.remember_check.setChecked(False)
        dlg._save_and_close()
        stored = settings.get_ewa()
        assert stored["password"] == ""
        assert stored["sftp"]["password"] == ""
        assert stored["telnet"]["password"] == ""
    finally:
        dlg.deleteLater()
