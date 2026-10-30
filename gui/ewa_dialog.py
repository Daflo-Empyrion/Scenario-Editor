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
"""Fenetre ADMIN SERVEUR (module EWA) : cliente de l'API du mod
EmpyrionWebAccess installe sur le serveur dedie. Fenetre NON MODALE a
onglets -- tableau de bord, chat, joueurs, structures, restauration,
planificateur, reglages serveur, utilisateurs EWA, console telnet,
deploiement SFTP.

Cycle de vie : _initial_connect() authentifie (JWT) hors thread GUI ;
chaque onglet recoit self.dialog (client + config + telnet partage) et
rafrachit quand il devient visible (polling rest, jamais de reseau dans le
thread GUI -- voir gui/ewa_async.py)."""
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QVBoxLayout, QWidget,
)

from core.i18n import t
from gui.module_info import add_info_button
from gui.theme import icon
from gui.window_geometry import track


class EwaTab(QWidget):
    """Onglet de base : acces au client EWA + hooks de visibilite."""

    def __init__(self, dialog):
        super().__init__()
        self.dialog = dialog

    @property
    def client(self):
        return self.dialog.client

    def on_visible(self) -> None:
        """Appele quand l'onglet devient courant (raffraichissement)."""

    def on_connected(self) -> None:
        """Appele apres une authentification reussie."""


class DashboardTab(EwaTab):
    """Etat du serveur : CPU / RAM / disque / version / joueurs / playfields."""

    POLL_SECONDS = 15

    ROWS = [
        ("server", "ewa.dash.server", None),
        ("online", "ewa.dash.online", None),
        ("version", "ewa.dash.version", None),
        ("players", "ewa.dash.players", None),
        ("playfields", "ewa.dash.playfields", None),
        ("cpu", "ewa.dash.cpu", None),
        ("ram", "ewa.dash.ram", None),
        ("disk", "ewa.dash.disk", None),
        ("ewa_mem", "ewa.dash.ewa_mem", None),
    ]

    def __init__(self, dialog):
        super().__init__(dialog)
        layout = QVBoxLayout(self)
        self.form = QFormLayout()
        self.values: dict = {}
        for key, label_key, _ in self.ROWS:
            value_label = QLabel(t("ewa.dash.na"))
            value_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse)
            self.values[key] = value_label
            self.form.addRow(QLabel(t(label_key)), value_label)
        layout.addLayout(self.form)
        row = QHBoxLayout()
        self.refresh_btn = QPushButton(icon("fa5s.refresh", "#ffffff"),
                                       t("ewa.dash.refresh"))
        self.refresh_btn.setObjectName("secondaryButton")
        self.refresh_btn.clicked.connect(self.refresh)
        row.addWidget(self.refresh_btn)
        row.addStretch()
        layout.addLayout(row)
        layout.addStretch()
        self._busy = False

    @staticmethod
    def _fmt_mb(megabytes) -> str:
        try:
            value = float(megabytes)
        except (TypeError, ValueError):
            return "?"
        if value >= 1024:
            return f"{value / 1024:.1f} GB"
        return f"{value:.0f} MB"

    def refresh(self) -> None:
        if self._busy or self.client is None:
            return
        self._busy = True

        def _work():
            return self.client.get_systeminfo()

        def _done(info):
            self._busy = False
            self._fill(info)

        def _fail(error):
            self._busy = False
            self.values["server"].setText(t("ewa.dash.na"))
            self.dialog.show_error(error)

        from gui.ewa_async import async_call
        async_call(self, _work, _done, _fail, "ewa-dashboard")

    def _fill(self, info) -> None:
        from core.ewa.client import pick
        self.values["server"].setText(
            str(pick(info, "serverName", default="?") or "?"))
        self.values["online"].setText(
            str(pick(info, "online", default="?") or "?"))
        version = str(pick(info, "versionESG", default="") or "")
        build = str(pick(info, "versionESGBuild", default="") or "")
        self.values["version"].setText(f"{version} ({build})".strip())
        active = pick(info, "activePlayers", default="?")
        self.values["players"].setText(str(active))
        active_pf = pick(info, "activePlayfields", default="?")
        total_pf = pick(info, "totalPlayfieldserver", default="?")
        self.values["playfields"].setText(f"{active_pf} / {total_pf}")
        self.values["cpu"].setText(f"{pick(info, 'cpuTotalLoad', default='?')} %")
        ram_total = pick(info, "ramTotalMB", default=0)
        ram_avail = pick(info, "ramAvailableMB", default=0)
        try:
            ram_used = float(ram_total) - float(ram_avail)
            self.values["ram"].setText(
                f"{self._fmt_mb(ram_used)} / {self._fmt_mb(ram_total)}")
        except (TypeError, ValueError):
            self.values["ram"].setText("?")
        disk_used = pick(info, "diskUsedSpace", default=0)
        disk_free = pick(info, "diskFreeSpace", default=0)
        try:
            self.values["disk"].setText(
                f"{self._fmt_gb(float(disk_used))} / "
                f"{self._fmt_gb(float(disk_used) + float(disk_free))}")
        except (TypeError, ValueError):
            self.values["disk"].setText("?")
        ewa_mem = pick(info, "ewaMemorySize", default=0)
        self.values["ewa_mem"].setText(self._fmt_mb(ewa_mem))

    @staticmethod
    def _fmt_gb(bytes_value: float) -> str:
        return f"{bytes_value / (1024 ** 3):.1f} GB"

    def on_connected(self) -> None:
        self.refresh()

    def on_visible_tick(self) -> None:
        self.refresh()


class EwaServerDialog(QDialog):
    """Fenetre d'administration du serveur dedie (non modale)."""

    def __init__(self, parent=None, auto_connect: bool = True):
        super().__init__(parent)
        self.setWindowTitle(t("ewa.main.title"))
        self.setMinimumSize(880, 640)
        track(self, "ewa_server")

        self.client = None            # core.ewa.client.EwaClient | None
        self._telnet = None           # TelnetConsole partage (console + chat)

        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        self.status_label = QLabel(t("ewa.main.disconnected"))
        self.status_label.setWordWrap(True)
        header.addWidget(self.status_label, 1)
        self.connect_btn = QPushButton(icon("fa5s.plug", "#ffffff"),
                                       t("ewa.main.connect"))
        self.connect_btn.setObjectName("secondaryButton")
        self.connect_btn.clicked.connect(self._reconnect_clicked)
        header.addWidget(self.connect_btn)
        config_btn = QPushButton(icon("fa5s.cog", "#ffffff"),
                                 t("ewa.main.config"))
        config_btn.setObjectName("secondaryButton")
        config_btn.clicked.connect(self._open_config_modal)
        header.addWidget(config_btn)
        layout.addLayout(header)

        self.tabs = QTabWidget()
        from gui.ewa_tabs_admin import ServerTab, UsersTab
        from gui.ewa_tabs_local import ConsoleTab, DeployTab
        from gui.ewa_tabs_players import ChatTab, PlayersTab
        from gui.ewa_tabs_world import RestoreTab, StructuresTab, TimetableTab
        self._chat_tab = ChatTab(self)
        self._console_tab = ConsoleTab(self)
        self._tabs = [
            DashboardTab(self),
            self._chat_tab,
            PlayersTab(self),
            StructuresTab(self),
            RestoreTab(self),
            TimetableTab(self),
            ServerTab(self),
            UsersTab(self),
            self._console_tab,
            DeployTab(self),
        ]
        titles = ["ewa.tab.dashboard", "ewa.tab.chat", "ewa.tab.players",
                  "ewa.tab.structures", "ewa.tab.restore", "ewa.tab.timetable",
                  "ewa.tab.server", "ewa.tab.users", "ewa.tab.console",
                  "ewa.tab.deploy"]
        for tab, title_key in zip(self._tabs, titles):
            self.tabs.addTab(tab, t(title_key))
        self.tabs.currentChanged.connect(self._tab_changed)
        add_info_button(layout, "ewa.info_html")
        layout.addWidget(self.tabs, 1)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(1000)
        self._poll_timer.timeout.connect(self._tick_visible_tab)
        self._last_poll: dict = {}      # id(onglet) -> monotonic du dernier tick
        self._poll_timer.start()

        if auto_connect:
            QTimer.singleShot(0, self._initial_connect)

    # ------------------------------------------------------------ connexion

    def _initial_connect(self) -> None:
        from core.ewa import config as ewa_config
        cfg = ewa_config.load()
        if not ewa_config.ewa_ready(cfg) or not cfg.get("password"):
            if not self._open_config_modal():
                return
            cfg = ewa_config.load()
        self._authenticate(cfg)

    def _reconnect_clicked(self) -> None:
        from core.ewa import config as ewa_config
        cfg = ewa_config.load()
        if not cfg.get("password"):
            if not self._open_config_modal():
                return
            cfg = ewa_config.load()
        self._authenticate(cfg)

    def _open_config_modal(self) -> bool:
        from PyQt6.QtWidgets import QDialog as _QDialog
        from gui.ewa_config_dialog import EwaConfigDialog
        dialog = EwaConfigDialog(self)
        return dialog.exec() == _QDialog.DialogCode.Accepted

    def _authenticate(self, cfg: dict) -> None:
        from core.ewa import client as ewa_client
        self._set_status(t("ewa.main.connecting"))
        self.client = None

        def _work():
            probe = ewa_client.EwaClient(
                cfg.get("url", ""), verify_ssl=bool(cfg.get("verify_ssl")),
                timeout=int(cfg.get("timeout", 20)))
            probe.authenticate(cfg.get("username", ""),
                               cfg.get("password", ""))
            return probe

        def _done(probe):
            self.client = probe
            name = ewa_client.pick(probe.user, "Username", default="")
            self._set_status(t("ewa.main.connected_as", user=name))
            self._broadcast_connected()

        def _fail(error):
            message = str(error)
            if "Username or password" in message:
                message = t("ewa.main.bad_credentials")
            self._set_status(t("ewa.main.connect_fail", error=message))
            self.show_error(error)

        from gui.ewa_async import async_call
        async_call(self, _work, _done, _fail, "ewa-auth")

    def _broadcast_connected(self) -> None:
        for tab in self._tabs:
            try:
                tab.on_connected()
            except Exception:           # noqa: BLE001 - crash natif sinon
                import logging
                logging.getLogger(__name__).exception("on_connected")

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def show_error(self, error) -> None:
        """Erreur reseau non bloquante (barre de statut + log)."""
        import logging
        logging.getLogger(__name__).warning("EWA : %s", error)
        self.status_label.setText(t("ewa.main.error", error=error))

    # ------------------------------------------------------------- telnet

    def telnet_console(self):
        """TelnetConsole partage (console + envoi chat SAY) -- cree a la
        volee ; les lignes recues vont a l'onglet console."""
        from core.ewa.telnet import TelnetConsole
        if self._telnet is None:
            self._telnet = TelnetConsole(
                on_line=self._on_telnet_line,
                on_closed=self._on_telnet_closed)
        return self._telnet

    def _on_telnet_line(self, text: str) -> None:
        console_tab = self._console_tab
        if console_tab is not None:
            console_tab.append_output(text)

    def _on_telnet_closed(self) -> None:
        console_tab = self._console_tab
        if console_tab is not None:
            console_tab.on_disconnected()

    def drop_telnet(self) -> None:
        self._telnet = None

    # ------------------------------------------------------------ onglets

    def _tab_changed(self, _index: int) -> None:
        self._tick_visible_tab(force=True)

    def _tick_visible_tab(self, force: bool = False) -> None:
        """Polling par onglet : l'onglet visible declare POLL_SECONDS et
        on_visible_tick() ; jamais deux appels plus rapides que l'intervalle."""
        tab = self.tabs.currentWidget()
        if tab is None or self.client is None:
            return
        interval = int(getattr(tab, "POLL_SECONDS", 0) or 0)
        if interval <= 0:
            return
        import time
        now = time.monotonic()
        if not force and now - self._last_poll.get(id(tab), 0.0) < interval:
            return
        self._last_poll[id(tab)] = now
        try:
            tab.on_visible_tick()
        except Exception:               # noqa: BLE001 - crash natif sinon
            import logging
            logging.getLogger(__name__).exception("on_visible_tick")

    def closeEvent(self, event) -> None:
        if self._telnet is not None:
            self._telnet.close()
        super().closeEvent(event)
