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
"""Onglets SERVEUR (SystemConfig : message de bienvenue, StartCMD, start /
stop / restart temporisés) et UTILISATEURS EWA (comptes du web EWA)."""
from PyQt6.QtWidgets import (
    QFormLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from core.ewa.client import pick
from core.i18n import t
from gui.ewa_dialog import EwaTab
from gui.theme import icon

EWA_ROLES = ["ewa.users.role.none", "ewa.users.role.player",
             "ewa.users.role.vip", "ewa.users.role.gm",
             "ewa.users.role.modo", "ewa.users.role.igadmin",
             "ewa.users.role.serveradmin"]


def _s(value) -> str:
    return "" if value is None else str(value)


class ServerTab(EwaTab):
    """Reglages serveur (Systeminfo/SystemConfig) + start/stop/restart."""

    def __init__(self, dialog):
        super().__init__(dialog)
        self._config: dict = {}
        self._busy = False

        layout = QVBoxLayout(self)

        group_start = QGroupBox(t("ewa.server.group_power"))
        power_layout = QHBoxLayout(group_start)
        power_layout.addWidget(QLabel(t("ewa.server.delay")))
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(0, 60)
        self.delay_spin.setValue(5)
        self.delay_spin.setSuffix(t("ewa.server.delay_suffix"))
        power_layout.addWidget(self.delay_spin)
        start_btn = QPushButton(icon("fa5s.play", "#ffffff"),
                                t("ewa.server.start"))
        start_btn.setObjectName("secondaryButton")
        start_btn.clicked.connect(self._start)
        power_layout.addWidget(start_btn)
        stop_btn = QPushButton(icon("fa5s.stop", "#ffffff"),
                               t("ewa.server.stop"))
        stop_btn.setObjectName("secondaryButton")
        stop_btn.clicked.connect(self._stop)
        power_layout.addWidget(stop_btn)
        restart_btn = QPushButton(icon("fa5s.sync", "#ffffff"),
                                  t("ewa.server.restart"))
        restart_btn.setObjectName("secondaryButton")
        restart_btn.clicked.connect(self._restart)
        power_layout.addWidget(restart_btn)
        power_layout.addStretch()
        layout.addWidget(group_start)

        group_cfg = QGroupBox(t("ewa.server.group_config"))
        cfg_layout = QFormLayout(group_cfg)
        self.version_label = QLabel("")
        cfg_layout.addRow(QLabel(t("ewa.server.version")), self.version_label)
        self.build_label = QLabel("")
        cfg_layout.addRow(QLabel(t("ewa.server.build")), self.build_label)
        self.startcmd_edit = QLineEdit()
        cfg_layout.addRow(QLabel(t("ewa.server.startcmd")), self.startcmd_edit)
        self.welcome_edit = QPlainTextEdit()
        self.welcome_edit.setMaximumHeight(100)
        cfg_layout.addRow(QLabel(t("ewa.server.welcome")), self.welcome_edit)
        save_cfg_btn = QPushButton(icon("fa5s.upload", "#ffffff"),
                                   t("ewa.server.save_cfg"))
        save_cfg_btn.setObjectName("secondaryButton")
        save_cfg_btn.clicked.connect(self._save_config)
        cfg_layout.addRow(save_cfg_btn)
        layout.addWidget(group_cfg)
        layout.addStretch()

    def on_connected(self) -> None:
        self._load_config()

    def _load_config(self) -> None:
        if self._busy or self.client is None:
            return
        self._busy = True

        def _work():
            return (self.client.get_system_config(),
                    self.client.get_systeminfo())

        def _done(payload):
            self._busy = False
            config, info = payload
            self._config = config or {}
            self.startcmd_edit.setText(
                _s(pick(self._config, "StartCMD")))
            self.welcome_edit.setPlainText(
                _s(pick(self._config, "WelcomeMessage")))
            self.version_label.setText(_s(pick(info, "versionESG")))
            self.build_label.setText(_s(pick(info, "GameBuildId")))

        def _fail(error):
            self._busy = False
            self.dialog.show_error(error)

        from gui.ewa_async import async_call
        async_call(self, _work, _done, _fail, "ewa-server-cfg")

    def _save_config(self) -> None:
        if self.client is None or not self._config:
            return
        config = dict(self._config)
        config["StartCMD"] = self.startcmd_edit.text()
        config["WelcomeMessage"] = self.welcome_edit.toPlainText()

        def _work():
            self.client.set_system_config(config)

        def _done(_result):
            QMessageBox.information(self, t("ewa.server.saved_title"),
                                    t("ewa.server.saved"))

        from gui.ewa_async import async_call
        async_call(self, _work, _done,
                   lambda error: self.dialog.show_error(error),
                   "ewa-server-save")

    def _confirm_power(self, message_key: str) -> bool:
        from gui.msgboxes import ask_yes_no
        return ask_yes_no(self, t("ewa.server.confirm_title"),
                          t(message_key, minutes=self.delay_spin.value()))

    def _start(self) -> None:
        if self.client is None:
            return

        def _work():
            self.client.egs_start()

        from gui.ewa_async import async_call
        async_call(self, _work, lambda _r: None,
                   lambda error: self.dialog.show_error(error), "ewa-start")

    def _stop(self) -> None:
        if self.client is None or not self._confirm_power("ewa.server.stop_q"):
            return
        minutes = self.delay_spin.value()

        def _work():
            self.client.egs_stop(minutes)

        from gui.ewa_async import async_call
        async_call(self, _work, lambda _r: None,
                   lambda error: self.dialog.show_error(error), "ewa-stop")

    def _restart(self) -> None:
        if self.client is None or not self._confirm_power(
                "ewa.server.restart_q"):
            return
        minutes = self.delay_spin.value()

        def _work():
            self.client.egs_restart(minutes)

        from gui.ewa_async import async_call
        async_call(self, _work, lambda _r: None,
                   lambda error: self.dialog.show_error(error), "ewa-restart")


class UsersTab(EwaTab):
    """Comptes de l'interface web EWA (Users + rôles)."""

    def __init__(self, dialog):
        super().__init__(dialog)
        self._busy = False

        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels([
            t("ewa.users.col.id"), t("ewa.users.col.name"),
            t("ewa.users.col.role")])
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, 1)

        row = QHBoxLayout()
        reload_btn = QPushButton(icon("fa5s.refresh", "#ffffff"),
                                 t("ewa.users.reload"))
        reload_btn.setObjectName("secondaryButton")
        reload_btn.clicked.connect(self.reload)
        row.addWidget(reload_btn)
        add_btn = QPushButton(icon("fa5s.user-plus", "#ffffff"),
                              t("ewa.users.add"))
        add_btn.setObjectName("secondaryButton")
        add_btn.clicked.connect(self._add_user)
        row.addWidget(add_btn)
        delete_btn = QPushButton(icon("fa5s.user-minus", "#ffffff"),
                                 t("ewa.users.delete"))
        delete_btn.setObjectName("secondaryButton")
        delete_btn.clicked.connect(self._delete_user)
        row.addWidget(delete_btn)
        password_btn = QPushButton(icon("fa5s.key", "#ffffff"),
                                   t("ewa.users.password"))
        password_btn.setObjectName("secondaryButton")
        password_btn.clicked.connect(self._change_password)
        row.addWidget(password_btn)
        row.addStretch()
        layout.addLayout(row)

    def on_connected(self) -> None:
        self.reload()

    def reload(self) -> None:
        if self._busy or self.client is None:
            return
        self._busy = True

        def _work():
            return self.client.get_users()

        def _done(users):
            self._busy = False
            self.table.setRowCount(len(users))
            for row_index, user in enumerate(users):
                role = int(pick(user, "Role", default=0) or 0)
                role_label = t(EWA_ROLES[role]) if 0 <= role < len(EWA_ROLES) \
                    else _s(role)
                for column, value in enumerate([
                        _s(pick(user, "Id")), _s(pick(user, "Username")),
                        role_label]):
                    self.table.setItem(row_index, column,
                                       QTableWidgetItem(value))

        def _fail(error):
            self._busy = False
            self.dialog.show_error(error)

        from gui.ewa_async import async_call
        async_call(self, _work, _done, _fail, "ewa-users")

    def _selected_user(self):
        row = self.table.currentRow()
        if row < 0:
            return None, ""
        return (self.table.item(row, 0).text(),
                self.table.item(row, 1).text())

    def _add_user(self) -> None:
        if self.client is None:
            return
        username, ok = QInputDialog.getText(
            self, t("ewa.users.add_title"), t("ewa.users.add_name"))
        if not ok or not username.strip():
            return
        password, ok = QInputDialog.getText(
            self, t("ewa.users.add_title"), t("ewa.users.add_password"),
            text="")
        if not ok or not password:
            return
        role, ok = QInputDialog.getItem(
            self, t("ewa.users.add_title"), t("ewa.users.add_role"),
            [t(key) for key in EWA_ROLES], 1, False)
        if not ok:
            return
        role_index = [t(key) for key in EWA_ROLES].index(role)

        def _work():
            self.client.register_user(username.strip(), password, role_index)

        from gui.ewa_async import async_call
        async_call(self, _work, lambda _r: self.reload(),
                   lambda error: self.dialog.show_error(error), "ewa-user-add")

    def _delete_user(self) -> None:
        if self.client is None:
            return
        user_id, username = self._selected_user()
        if not user_id:
            return
        from gui.msgboxes import ask_yes_no
        if not ask_yes_no(self, t("ewa.users.delete_title"),
                          t("ewa.users.delete_confirm", name=username)):
            return

        def _work():
            self.client.delete_user(int(user_id))

        from gui.ewa_async import async_call
        async_call(self, _work, lambda _r: self.reload(),
                   lambda error: self.dialog.show_error(error),
                   "ewa-user-del")

    def _change_password(self) -> None:
        if self.client is None:
            return
        user_id, username = self._selected_user()
        if not user_id:
            return
        password, ok = QInputDialog.getText(
            self, t("ewa.users.password_title"),
            t("ewa.users.password_ask", name=username), text="")
        if not ok or not password:
            return

        def _work():
            self.client.update_user(int(user_id), username, password)

        from gui.ewa_async import async_call
        async_call(self, _work, lambda _r: self.reload(),
                   lambda error: self.dialog.show_error(error),
                   "ewa-user-pass")
