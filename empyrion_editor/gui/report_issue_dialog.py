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

"""
Dialogue "Signaler un bug / une amelioration" -- ouvre un formulaire GitHub
pre-rempli (titre, description, infos techniques, actions recentes) dans le
navigateur. Ne soumet JAMAIS rien automatiquement : GitHub n'offre aucun moyen
sur, sans jeton d'API embarque dans l'executable (donc extractible et abusable
par n'importe qui), de creer une issue depuis une appli desktop sans intervention
de l'utilisateur -- la personne doit toujours relire et cliquer "Submit" elle-meme
sur la page GitHub, comme n'importe quel lien "Signaler un bug" classique.

La capture d'ecran ne peut pas non plus etre jointe automatiquement (impossible de
joindre un fichier binaire via une simple URL) -- elle est enregistree localement,
et la personne n'a plus qu'a la glisser-deposer dans le champ de texte GitHub
(qui accepte nativement le glisser-deposer d'image).
"""
import platform
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit, QPushButton,
    QComboBox, QMessageBox,
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QPixmap

from core.i18n import t
from core import settings as app_settings
from core.version import APP_VERSION, GITHUB_REPO


def _collect_diagnostic_info() -> str:
    """Bloc d'informations techniques ajoute automatiquement au rapport --
    strictement des faits sur l'environnement d'execution, jamais de contenu
    personnel (aucun chemin de fichier utilisateur, aucun contenu de scenario)."""
    lines = [
        f"- Version de l'application : {APP_VERSION}",
        f"- Mode : {'Executable installe' if getattr(sys, 'frozen', False) else 'Sources Python'}",
        f"- Systeme : {platform.system()} {platform.release()} ({platform.version()})",
        f"- Python : {platform.python_version()}",
        f"- Langue de l'interface : {app_settings.get_language()}",
    ]
    return "\n".join(lines)


def _save_screenshot(screenshot: QPixmap) -> Path:
    folder = Path.home() / ".empyrion_editor" / "bug_reports"
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"rapport_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    path = folder / filename
    screenshot.save(str(path), "PNG")
    return path


class ReportIssueDialog(QDialog):
    def __init__(self, screenshot: QPixmap, recent_actions: list, parent=None):
        super().__init__(parent)
        self.screenshot = screenshot
        self.recent_actions = recent_actions

        self.setWindowTitle(t("report.title"))
        layout = QVBoxLayout(self)

        if not GITHUB_REPO.strip():
            self.setMinimumWidth(420)
            label = QLabel(t("report.not_configured"))
            label.setWordWrap(True)
            layout.addWidget(label)
            btn_close = QPushButton(t("btn.close"))
            btn_close.clicked.connect(self.reject)
            layout.addWidget(btn_close)
            return

        self.setMinimumSize(560, 520)

        layout.addWidget(QLabel(t("report.intro")))

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel(t("report.type_label")))
        self.type_combo = QComboBox()
        self.type_combo.addItem(t("report.type_bug"), "bug")
        self.type_combo.addItem(t("report.type_feature"), "enhancement")
        type_row.addWidget(self.type_combo)
        type_row.addStretch()
        layout.addLayout(type_row)

        layout.addWidget(QLabel(t("report.title_label")))
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText(t("report.title_placeholder"))
        layout.addWidget(self.title_input)

        layout.addWidget(QLabel(t("report.description_label")))
        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText(t("report.description_placeholder"))
        self.description_input.setMinimumHeight(140)
        layout.addWidget(self.description_input)

        # Apercu reduit de la capture d'ecran -- transparence sur ce qui a ete
        # capture au moment du clic, avant meme l'ouverture de ce dialogue (pour
        # refleter fidelement ce que la personne regardait).
        screenshot_row = QHBoxLayout()
        thumb_label = QLabel()
        thumb_label.setPixmap(self.screenshot.scaledToWidth(
            160, Qt.TransformationMode.SmoothTransformation))
        thumb_label.setStyleSheet("border: 1px solid #d0d7e5; border-radius: 4px;")
        screenshot_row.addWidget(thumb_label)
        screenshot_note = QLabel(t("report.screenshot_note"))
        screenshot_note.setWordWrap(True)
        screenshot_row.addWidget(screenshot_note, 1)
        layout.addLayout(screenshot_row)

        # Infos techniques + actions recentes -- affichees en lecture seule pour que
        # la personne sache exactement ce qui sera inclus avant d'envoyer.
        layout.addWidget(QLabel(t("report.auto_included_label")))
        auto_info = QTextEdit()
        auto_info.setReadOnly(True)
        auto_info.setMaximumHeight(110)
        actions_block = ("\n".join(f"  {i+1}. {a}" for i, a in enumerate(recent_actions))
                          if recent_actions else f"  ({t('report.no_recent_actions')})")
        auto_info.setPlainText(
            _collect_diagnostic_info() + "\n\n" + t("report.recent_actions_label") + "\n" + actions_block)
        layout.addWidget(auto_info)

        buttons = QHBoxLayout()
        btn_send = QPushButton(t("report.btn_send"))
        btn_send.setObjectName("primaryButton")
        btn_send.clicked.connect(self._do_send)
        buttons.addWidget(btn_send)
        btn_cancel = QPushButton(t("btn.close"))
        btn_cancel.setObjectName("secondaryButton")
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_cancel)
        layout.addLayout(buttons)

    def _do_send(self):
        title = self.title_input.text().strip()
        description = self.description_input.toPlainText().strip()
        if not title or not description:
            QMessageBox.warning(self, t("report.title"), t("report.error_missing_fields"))
            return

        screenshot_path = _save_screenshot(self.screenshot)

        actions_block = ("\n".join(f"- {a}" for a in self.recent_actions)
                          if self.recent_actions else f"_{t('report.no_recent_actions')}_")
        body = (
            f"{description}\n\n"
            f"---\n\n"
            f"### {t('report.recent_actions_label')}\n{actions_block}\n\n"
            f"### {t('report.tech_info_heading')}\n{_collect_diagnostic_info()}\n\n"
            f"### {t('report.screenshot_heading')}\n{t('report.screenshot_instruction')}"
        )

        label = self.type_combo.currentData()
        params = urllib.parse.urlencode({"title": title, "body": body, "labels": label})
        issue_url = f"https://github.com/{GITHUB_REPO}/issues/new?{params}"

        QDesktopServices.openUrl(QUrl(issue_url))
        QMessageBox.information(
            self, t("report.title"),
            t("report.sent_msg", path=str(screenshot_path)))
        self.accept()
