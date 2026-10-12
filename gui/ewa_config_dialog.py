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
"""Fenetre de CONFIGURATION de la connexion au serveur dedie (module EWA) :
l'editeur est client d'un serveur DISTANT -- URL de l'API EWA, identifiants,
certificat auto-signé, acces SFTP (deploiement) et telnet (console). Le test
de connexion fait un appel REEL (Users/authenticate + Systeminfo) hors du
thread GUI."""
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout,
)

from core.ewa import client as ewa_client
from core.i18n import t
from gui.theme import icon
from gui.window_geometry import track


def _password_row(layout_form, label_key, edit):
    layout_form.addRow(QLabel(t(label_key)), edit)


class EwaConfigDialog(QDialog):
    """URL + identifiants EWA, certificat auto-signé, SFTP, telnet."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from core.ewa import config as ewa_config
        self._cfg = ewa_config.load()
        self.setWindowTitle(t("ewa.cfg.title"))
        self.setMinimumWidth(620)
        track(self, "ewa_config")

        layout = QVBoxLayout(self)

        # ------------------------------------------------- groupe API EWA
        group_ewa = QGroupBox(t("ewa.cfg.group_ewa"))
        form_ewa = QFormLayout(group_ewa)
        self.url_edit = QLineEdit(self._cfg.get("url", ""))
        self.url_edit.setPlaceholderText(t("ewa.cfg.url_placeholder"))
        form_ewa.addRow(QLabel(t("ewa.cfg.url")), self.url_edit)
        self.user_edit = QLineEdit(self._cfg.get("username", ""))
        form_ewa.addRow(QLabel(t("ewa.cfg.user")), self.user_edit)
        self.password_edit = QLineEdit(self._cfg.get("password", ""))
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        _password_row(form_ewa, "ewa.cfg.password", self.password_edit)
        self.remember_check = QCheckBox(t("ewa.cfg.remember"))
        self.remember_check.setChecked(bool(self._cfg.get("remember_password")))
        form_ewa.addRow(self.remember_check)
        self.ssl_check = QCheckBox(t("ewa.cfg.selfsigned"))
        self.ssl_check.setChecked(not bool(self._cfg.get("verify_ssl")))
        self.ssl_check.setToolTip(t("ewa.cfg.selfsigned_tip"))
        form_ewa.addRow(self.ssl_check)
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 120)
        self.timeout_spin.setValue(int(self._cfg.get("timeout", 20)))
        self.timeout_spin.setSuffix(" s")
        form_ewa.addRow(QLabel(t("ewa.cfg.timeout")), self.timeout_spin)
        test_row = QHBoxLayout()
        self.test_btn = QPushButton(icon("fa5s.plug", "#ffffff"),
                                    t("ewa.cfg.test_btn"))
        self.test_btn.setObjectName("secondaryButton")
        self.test_btn.clicked.connect(self._test_connection)
        test_row.addWidget(self.test_btn)
        test_row.addStretch()
        form_ewa.addRow(test_row)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        form_ewa.addRow(self.status_label)
        layout.addWidget(group_ewa)

        # ------------------------------------------------- groupe SFTP
        group_sftp = QGroupBox(t("ewa.cfg.group_sftp"))
        form_sftp = QFormLayout(group_sftp)
        sftp = self._cfg.get("sftp", {})
        self.sftp_host_edit = QLineEdit(sftp.get("host", ""))
        form_sftp.addRow(QLabel(t("ewa.cfg.sftp_host")), self.sftp_host_edit)
        port_row = QHBoxLayout()
        self.sftp_port_spin = QSpinBox()
        self.sftp_port_spin.setRange(1, 65535)
        self.sftp_port_spin.setValue(int(sftp.get("port", 22)))
        port_row.addWidget(self.sftp_port_spin)
        port_row.addStretch()
        form_sftp.addRow(QLabel(t("ewa.cfg.sftp_port")), port_row)
        self.sftp_user_edit = QLineEdit(sftp.get("username", ""))
        form_sftp.addRow(QLabel(t("ewa.cfg.sftp_user")), self.sftp_user_edit)
        self.sftp_password_edit = QLineEdit(sftp.get("password", ""))
        self.sftp_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form_sftp.addRow(QLabel(t("ewa.cfg.sftp_password")),
                         self.sftp_password_edit)
        self.sftp_path_edit = QLineEdit(sftp.get("remote_scenario", ""))
        self.sftp_path_edit.setPlaceholderText(
            t("ewa.cfg.sftp_path_placeholder"))
        form_sftp.addRow(QLabel(t("ewa.cfg.sftp_path")), self.sftp_path_edit)
        layout.addWidget(group_sftp)

        # ------------------------------------------------- groupe Telnet
        group_tel = QGroupBox(t("ewa.cfg.group_telnet"))
        form_tel = QFormLayout(group_tel)
        telnet = self._cfg.get("telnet", {})
        self.tel_host_edit = QLineEdit(telnet.get("host", ""))
        form_tel.addRow(QLabel(t("ewa.cfg.tel_host")), self.tel_host_edit)
        self.tel_port_spin = QSpinBox()
        self.tel_port_spin.setRange(1, 65535)
        self.tel_port_spin.setValue(int(telnet.get("port", 30004)))
        port_tel_row = QHBoxLayout()
        port_tel_row.addWidget(self.tel_port_spin)
        port_tel_row.addStretch()
        form_tel.addRow(QLabel(t("ewa.cfg.tel_port")), port_tel_row)
        self.tel_password_edit = QLineEdit(telnet.get("password", ""))
        self.tel_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form_tel.addRow(QLabel(t("ewa.cfg.tel_password")),
                        self.tel_password_edit)
        layout.addWidget(group_tel)

        # ------------------------------------------------- boutons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save_and_close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------ test

    def _test_connection(self) -> None:
        """Test REEL : auth + systeminfo, hors thread GUI."""
        url = ewa_client.normalize_url(self.url_edit.text())
        username = self.user_edit.text().strip()
        password = self.password_edit.text()
        if not url or not username or not password:
            self.status_label.setText(t("ewa.cfg.test_need_fields"))
            return
        verify = not self.ssl_check.isChecked()
        timeout = self.timeout_spin.value()
        self.status_label.setText(t("ewa.cfg.testing"))
        self.test_btn.setEnabled(False)

        def _work():
            probe = ewa_client.EwaClient(url, verify_ssl=verify,
                                         timeout=timeout)
            probe.authenticate(username, password)
            info = probe.get_systeminfo()
            return ewa_client.pick(info, "serverName", default="") or "?"

        def _done(server_name):
            self.test_btn.setEnabled(True)
            self.status_label.setText(t("ewa.cfg.test_ok", name=server_name))

        def _fail(error):
            self.test_btn.setEnabled(True)
            self.status_label.setText(t("ewa.cfg.test_fail", error=error))

        from gui.ewa_async import async_call
        async_call(self, _work, _done, _fail, "ewa-config-test")

    # ----------------------------------------------------------------- save

    def _save_and_close(self) -> None:
        from core.ewa import config as ewa_config
        self._cfg.update({
            "url": ewa_client.normalize_url(self.url_edit.text()),
            "username": self.user_edit.text().strip(),
            "password": self.password_edit.text(),
            "remember_password": self.remember_check.isChecked(),
            "verify_ssl": not self.ssl_check.isChecked(),
            "timeout": self.timeout_spin.value(),
            "sftp": {
                "host": self.sftp_host_edit.text().strip(),
                "port": self.sftp_port_spin.value(),
                "username": self.sftp_user_edit.text().strip(),
                "password": self.sftp_password_edit.text(),
                "remote_scenario": self.sftp_path_edit.text().strip(),
            },
            "telnet": {
                "host": self.tel_host_edit.text().strip(),
                "port": self.tel_port_spin.value(),
                "password": self.tel_password_edit.text(),
            },
        })
        ewa_config.save(self._cfg)
        self.accept()
