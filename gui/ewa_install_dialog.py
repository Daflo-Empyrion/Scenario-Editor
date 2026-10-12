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
"""Guide d'installation du mod EWA sur le serveur dedie (pas-a-pas SFTP) +
diagnostic a distance : une fois l'API EWA configuree, « Diagnostiquer »
eprouve la joignabilite, le JWT et la presence du mod loader
(Mod/ModLoaderInstalled) pour dire OU bloque l'installation."""
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QTextBrowser, QVBoxLayout,
)

from core.i18n import t
from gui.theme import icon
from gui.window_geometry import track


class EwaInstallDialog(QDialog):
    """Pas-a-pas d'installation d'EmpyrionWebAccess sur un dédié + diag."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("ewa.install.title"))
        self.setMinimumSize(720, 560)
        track(self, "ewa_install")

        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(self._build_html())
        layout.addWidget(browser, 1)

        row = QHBoxLayout()
        self.diag_btn = QPushButton(icon("fa5s.stethoscope", "#ffffff"),
                                    t("ewa.install.diag_btn"))
        self.diag_btn.setObjectName("secondaryButton")
        self.diag_btn.clicked.connect(self._diagnose)
        row.addWidget(self.diag_btn)
        row.addStretch()
        close_btn = QPushButton(t("btn.close"))
        close_btn.setObjectName("secondaryButton")
        close_btn.clicked.connect(self.close)
        row.addWidget(close_btn)
        layout.addLayout(row)

        self.diag_label = QLabel("")
        self.diag_label.setWordWrap(True)
        layout.addWidget(self.diag_label)

    # ------------------------------------------------------------------ html

    @staticmethod
    def _build_html() -> str:
        steps = [t(f"ewa.install.step{i}") for i in range(1, 9)]
        html = f"<p>{t('ewa.install.intro')}</p><ol>"
        html += "".join(f"<li>{step}</li>" for step in steps)
        html += f"</ol><p>{t('ewa.install.bootstrap')}</p>"
        html += f"<p>{t('ewa.install.diag_hint')}</p>"
        return html

    # ------------------------------------------------------------- diagnostic

    def _diagnose(self) -> None:
        """Diagnostic REEL via l'API EWA configuree (hors thread GUI)."""
        from core.ewa import client as ewa_client
        from core.ewa import config as ewa_config
        cfg = ewa_config.load()
        if not ewa_client.normalize_url(cfg.get("url", "")):
            self.diag_label.setText(t("ewa.install.diag_no_config"))
            return
        self.diag_btn.setEnabled(False)
        self.diag_label.setText(t("ewa.install.diag_running"))

        def _work():
            probe = ewa_client.EwaClient(
                ewa_client.normalize_url(cfg.get("url", "")),
                verify_ssl=bool(cfg.get("verify_ssl")),
                timeout=int(cfg.get("timeout", 20)))
            username = cfg.get("username", "")
            password = cfg.get("password", "")
            if username and password:
                probe.authenticate(username, password)
            return probe.diagnose()

        def _done(result):
            self.diag_btn.setEnabled(True)
            lines = []
            key = "ewa.install.diag_ok" if result.get("reachable") \
                else "ewa.install.diag_unreachable"
            lines.append(t(key))
            if result.get("error"):
                lines.append(t("ewa.install.diag_error", error=result["error"]))
            if result.get("auth"):
                lines.append(t("ewa.install.diag_auth"))
            if result.get("server_name"):
                lines.append(t("ewa.install.diag_server",
                               name=result["server_name"]))
            loader = result.get("mod_loader")
            if loader is True:
                lines.append(t("ewa.install.diag_loader_ok"))
            elif loader is False:
                lines.append(t("ewa.install.diag_loader_missing"))
            if not result.get("auth") and result.get("reachable"):
                lines.append(t("ewa.install.diag_no_auth"))
            self.diag_label.setText("<br>".join(lines))

        def _fail(error):
            self.diag_btn.setEnabled(True)
            self.diag_label.setText(t("ewa.install.diag_error", error=error))

        from gui.ewa_async import async_call
        async_call(self, _work, _done, _fail, "ewa-install-diag")
