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
"""Onglets LOCAUX : console TELNET (secours direct au dedié, meme sans EWA)
et DEPLOIEMENT du scenario par SFTP (sync miroir + restart prevenue -- la
boucle editer -> valider -> deployer -> redemarrer)."""
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from core.i18n import t
from gui.theme import icon


class ConsoleTab(QWidget):
    """Console telnet brute du dedié (mot de passe telnet du serverconfig)."""

    def __init__(self, dialog):
        super().__init__()
        self.dialog = dialog
        self._history: list = []
        self._history_index = 0

        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self.status_label = QLabel(t("ewa.console.disconnected"))
        row.addWidget(self.status_label, 1)
        self.connect_btn = QPushButton(icon("fa5s.plug", "#ffffff"),
                                       t("ewa.console.connect"))
        self.connect_btn.setObjectName("secondaryButton")
        self.connect_btn.clicked.connect(self._toggle_connection)
        row.addWidget(self.connect_btn)
        clear_btn = QPushButton(icon("fa5s.eraser", "#ffffff"),
                                t("ewa.console.clear"))
        clear_btn.setObjectName("secondaryButton")
        clear_btn.clicked.connect(lambda: self.output.setPlainText(""))
        row.addWidget(clear_btn)
        layout.addLayout(row)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output, 1)

        send_row = QHBoxLayout()
        self.command_edit = HistoryLineEdit(self)
        self.command_edit.setPlaceholderText(t("ewa.console.placeholder"))
        self.command_edit.returnPressed.connect(self._send)
        send_row.addWidget(self.command_edit, 1)
        self.send_btn = QPushButton(icon("fa5s.terminal", "#ffffff"),
                                    t("ewa.console.send"))
        self.send_btn.clicked.connect(self._send)
        send_row.addWidget(self.send_btn)
        layout.addLayout(send_row)

    # ------------------------------------------------------------ affichage

    def append_output(self, text: str) -> None:
        self.output.setPlainText(self.output.toPlainText() + text)
        scrollbar = self.output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def on_disconnected(self) -> None:
        self.status_label.setText(t("ewa.console.disconnected"))
        self.connect_btn.setText(t("ewa.console.connect"))

    # ---------------------------------------------------------- connexion

    def _toggle_connection(self) -> None:
        telnet = self.dialog.telnet_console()
        if telnet.connected:
            telnet.close()
            self.on_disconnected()
            return
        self.connect_btn.setEnabled(False)
        self.status_label.setText(t("ewa.console.connecting"))
        dialog = self.dialog

        def _work():
            from core.ewa import config as ewa_config
            cfg = ewa_config.load().get("telnet", {})
            telnet.connect(cfg.get("host", ""),
                           int(cfg.get("port", 0) or 0),
                           cfg.get("password", ""))

        def _done(_result):
            self.connect_btn.setEnabled(True)
            self.connect_btn.setText(t("ewa.console.disconnect"))
            self.status_label.setText(t("ewa.console.connected"))
            self.command_edit.setFocus()

        def _fail(error):
            # echec = instance half-open jetee : mutation d'etat du dialog
            # ICI (thread GUI), jamais dans le worker
            dialog.drop_telnet()
            self.connect_btn.setEnabled(True)
            self.status_label.setText(t("ewa.console.connect_fail",
                                        error=error))

        from gui.ewa_async import async_call
        async_call(self, _work, _done, _fail, "ewa-telnet-connect")

    # ---------------------------------------------------------------- envoi

    def _send(self) -> None:
        command = self.command_edit.text().strip()
        if not command:
            return
        telnet = self.dialog.telnet_console()
        if not telnet.connected:
            self.status_label.setText(t("ewa.console.disconnected"))
            return
        try:
            telnet.send_command(command)
        except Exception as error:      # noqa: BLE001 - TelnetError surtout
            self.status_label.setText(t("ewa.console.send_fail", error=error))
            return
        self.command_edit.remember(command)
        self.command_edit.clear()


class HistoryLineEdit(QLineEdit):
    """Ligne de commande avec historique (fleches Haut/Bas)."""

    def __init__(self, owner: QWidget):
        super().__init__()
        self._owner = owner
        self._history: list = []
        self._index = 0

    def remember(self, command: str) -> None:
        self._history.append(command)
        self._index = len(self._history)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Up and self._history:
            self._index = max(0, self._index - 1)
            self.setText(self._history[self._index])
            return
        if event.key() == Qt.Key.Key_Down and self._history:
            self._index = min(len(self._history), self._index + 1)
            if self._index >= len(self._history):
                self.clear()
            else:
                self.setText(self._history[self._index])
            return
        super().keyPressEvent(event)


class DeployTab(QWidget):
    """Deploiement SFTP du scenario local (working) vers le dedié (miroir).

    Progression : le worker SFTP emit log_signal(str) -- connexion QUEUED,
    le GUI n'est jamais touche hors du thread GUI."""

    log_signal = pyqtSignal(str)

    def __init__(self, dialog):
        super().__init__()
        self.dialog = dialog
        self._plan: dict | None = None
        self._busy = False
        self.log_signal.connect(self._append_log)

        layout = QVBoxLayout(self)

        self.warn_label = QLabel(t("ewa.deploy.warn"))
        self.warn_label.setWordWrap(True)
        layout.addWidget(self.warn_label)

        row = QHBoxLayout()
        row.addWidget(QLabel(t("ewa.deploy.local")))
        self.local_edit = QLineEdit()
        self.local_edit.setText(self._default_local_dir())
        row.addWidget(self.local_edit, 1)
        browse_btn = QPushButton(icon("fa5s.folder-open", "#ffffff"),
                                 t("ewa.deploy.browse"))
        browse_btn.setObjectName("secondaryButton")
        browse_btn.clicked.connect(self._browse)
        row.addWidget(browse_btn)
        layout.addLayout(row)

        self.mirror_check = QCheckBox(t("ewa.deploy.mirror"))
        self.mirror_check.setChecked(True)
        self.mirror_check.setToolTip(t("ewa.deploy.mirror_tip"))
        layout.addWidget(self.mirror_check)

        buttons = QHBoxLayout()
        self.analyze_btn = QPushButton(icon("fa5s.search", "#ffffff"),
                                       t("ewa.deploy.analyze"))
        self.analyze_btn.setObjectName("secondaryButton")
        self.analyze_btn.clicked.connect(self._analyze)
        buttons.addWidget(self.analyze_btn)
        self.deploy_btn = QPushButton(icon("fa5s.upload", "#ffffff"),
                                      t("ewa.deploy.deploy"))
        self.deploy_btn.setEnabled(False)
        self.deploy_btn.clicked.connect(self._deploy)
        buttons.addWidget(self.deploy_btn)
        self.restart_btn = QPushButton(icon("fa5s.sync", "#ffffff"),
                                       t("ewa.deploy.restart"))
        self.restart_btn.setObjectName("secondaryButton")
        self.restart_btn.clicked.connect(self._ask_restart)
        buttons.addWidget(self.restart_btn)
        buttons.addStretch()
        layout.addLayout(buttons)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log, 1)

    # ------------------------------------------------------------- helpers

    def _default_local_dir(self) -> str:
        try:
            from core.ewa import config as ewa_config
            saved = ewa_config.load().get("deploy_local_dir", "")
        except Exception:               # noqa: BLE001 - settings absents
            saved = ""
        if saved:
            return saved
        workspace = getattr(self.dialog.parent(), "workspace", None)
        root = getattr(workspace, "working_root", None)
        return str(root) if root is not None else ""

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, t("ewa.deploy.browse"), self.local_edit.text() or "")
        if not chosen:
            return
        self.local_edit.setText(chosen)
        try:
            from core.ewa import config as ewa_config
            cfg = ewa_config.load()
            cfg["deploy_local_dir"] = chosen
            ewa_config.save(cfg)
        except Exception:               # noqa: BLE001
            pass

    def _append_log(self, text: str) -> None:
        self.log.setPlainText(self.log.toPlainText() + text + "\n")
        scrollbar = self.log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _sftp_ready(self) -> bool:
        from core.ewa import config as ewa_config
        from core.ewa.sftp_deploy import availability_message, is_available
        if not is_available():
            QMessageBox.warning(self, t("ewa.deploy.sftp_title"),
                                availability_message())
            return False
        sftp_cfg = ewa_config.load().get("sftp", {})
        if not sftp_cfg.get("host") or not sftp_cfg.get("username") \
                or not (sftp_cfg.get("remote_scenario") or "").strip():
            QMessageBox.warning(self, t("ewa.deploy.sftp_title"),
                                t("ewa.deploy.no_sftp"))
            return False
        return True

    # ------------------------------------------------------------- analyse

    def _analyze(self) -> None:
        """Liste le dossier distant et calcule le plan (hors thread GUI)."""
        local_dir = Path(self.local_edit.text().strip())
        if not local_dir.is_dir():
            QMessageBox.warning(self, t("ewa.deploy.bad_local_title"),
                                t("ewa.deploy.bad_local"))
            return
        if not self._sftp_ready():
            return
        self._busy = True
        self.analyze_btn.setEnabled(False)
        self._append_log(t("ewa.deploy.analyzing"))

        def _work():
            from core.ewa import config as ewa_config
            from core.ewa.sftp_deploy import SftpSession, plan_sync
            cfg = ewa_config.load()
            sftp_cfg = cfg.get("sftp", {})
            session = SftpSession(sftp_cfg.get("host", ""),
                                  int(sftp_cfg.get("port", 22) or 22),
                                  sftp_cfg.get("username", ""),
                                  sftp_cfg.get("password", ""))
            try:
                remote_files = session.list_remote(
                    (sftp_cfg.get("remote_scenario") or "").strip())
            finally:
                session.close()
            return plan_sync(local_dir, remote_files)

        def _done(plan):
            self._busy = False
            self.analyze_btn.setEnabled(True)
            if not self.mirror_check.isChecked():
                plan = dict(plan, delete=[], orphans=[])
            self._plan = plan
            self._append_log(t("ewa.deploy.plan",
                               up=len(plan["upload"]),
                               deleted=len(plan["delete"]),
                               bins=len(plan["invalidate"])
                               + len(plan["orphans"]),
                               unchanged=plan["unchanged"]))
            for rel in plan["upload"][:50]:
                self._append_log(f"  + {rel}")
            for rel in plan["delete"][:50]:
                self._append_log(f"  - {rel} [{t('ewa.deploy.mark_delete')}]")
            self.deploy_btn.setEnabled(bool(
                plan["upload"] or plan["delete"] or plan["invalidate"]
                or plan["orphans"]))

        def _fail(error):
            self._busy = False
            self.analyze_btn.setEnabled(True)
            self._append_log(str(error))

        from gui.ewa_async import async_call
        async_call(self, _work, _done, _fail, "ewa-deploy-analyze")

    # ---------------------------------------------------------- deploiement

    def _deploy(self) -> None:
        if self._plan is None or self._busy:
            return
        plan = self._plan
        if (plan["delete"] or plan["orphans"]):
            answer = QMessageBox.question(
                self, t("ewa.deploy.confirm_title"),
                t("ewa.deploy.confirm", deleted=len(plan["delete"]),
                  bins=len(plan["orphans"])))
            if answer != QMessageBox.StandardButton.Yes:
                return
        local_dir = Path(self.local_edit.text().strip())
        mirror = self.mirror_check.isChecked()   # capture thread GUI
        self._busy = True
        self.deploy_btn.setEnabled(False)
        self.analyze_btn.setEnabled(False)
        self.log_signal.emit(t("ewa.deploy.starting"))

        def _work():
            from core.ewa import config as ewa_config
            from core.ewa.sftp_deploy import (
                SftpSession, apply_sync, plan_sync, sync_summary)
            cfg = ewa_config.load()
            sftp_cfg = cfg.get("sftp", {})
            remote_root = (sftp_cfg.get("remote_scenario") or "").strip()
            session = SftpSession(sftp_cfg.get("host", ""),
                                  int(sftp_cfg.get("port", 22) or 22),
                                  sftp_cfg.get("username", ""),
                                  sftp_cfg.get("password", ""))
            try:
                remote_files = session.list_remote(remote_root)
                live_plan = plan_sync(local_dir, remote_files)
                if not mirror:
                    live_plan = dict(live_plan, delete=[], orphans=[])
                done = apply_sync(
                    session, local_dir, remote_root, live_plan,
                    _backup_root(),
                    progress=lambda text: self.log_signal.emit(text))
                return sync_summary(done)
            finally:
                session.close()

        def _done(summary):
            self._busy = False
            self.deploy_btn.setEnabled(True)
            self.analyze_btn.setEnabled(True)
            self._append_log(summary)
            self._plan = None

        def _fail(error):
            self._busy = False
            self.deploy_btn.setEnabled(True)
            self.analyze_btn.setEnabled(True)
            self._append_log(str(error))

        from gui.ewa_async import async_call
        async_call(self, _work, _done, _fail, "ewa-deploy-apply")

    def _ask_restart(self) -> None:
        """Restart PREVENU : EGSRestart/{minutes} via l'API EWA."""
        if self.dialog.client is None:
            self.dialog.show_error(t("ewa.main.not_connected"))
            return
        minutes, ok = QInputDialog.getInt(
            self, t("ewa.deploy.restart_title"), t("ewa.deploy.restart_delay"),
            5, 0, 60)
        if not ok:
            return
        from gui.msgboxes import ask_yes_no
        if not ask_yes_no(self, t("ewa.deploy.restart_title"),
                          t("ewa.deploy.restart_q", minutes=minutes)):
            return
        client = self.dialog.client

        def _work():
            client.egs_restart(int(minutes))

        from gui.ewa_async import async_call
        async_call(self, _work,
                   lambda _r: self._append_log(t(
                       "ewa.deploy.restart_scheduled", minutes=minutes)),
                   lambda error: self.dialog.show_error(error),
                   "ewa-deploy-restart")


def _backup_root() -> Path:
    """Racine locale des sauvegardes pre-suppression (miroir SFTP)."""
    import time
    return (Path.home() / ".empyrion_editor" / "backups" / "sftp_remote"
            / time.strftime("%Y%m%d-%H%M%S"))
