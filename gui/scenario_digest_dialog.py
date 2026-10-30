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
"""Fiche du scenario : apercu Markdown (FR + EN) et export .md pour une
note de version Workshop/Discord (core/scenario_digest.py)."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel,
                             QLineEdit, QPlainTextEdit, QPushButton,
                             QVBoxLayout)

from core.i18n import t
from core.scenario_digest import collect_digest, render_markdown
from gui.module_info import add_info_button
from core.settings import get_vanilla_content_path
from gui.ewa_async import async_call
from gui.window_geometry import track


class ScenarioDigestDialog(QDialog):
    """Apercu + export de la fiche du scenario."""
    def __init__(self, parent, working_root: str = ""):
        super().__init__(parent)
        self.setWindowTitle(t("digest.title"))
        self._running = False
        self._text = ""

        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel(t("yamlcheck.scenario")))
        self.path_edit = QLineEdit(working_root)
        self.path_edit.setPlaceholderText(t("yamlcheck.scenario_hint"))
        row.addWidget(self.path_edit, 1)
        self.btn_browse = QPushButton(t("yamlcheck.browse"))
        self.btn_browse.clicked.connect(self._pick_folder)
        row.addWidget(self.btn_browse)
        lay.addLayout(row)

        buttons = QHBoxLayout()
        self.btn_run = QPushButton(t("digest.run"))
        self.btn_run.clicked.connect(self._run)
        buttons.addWidget(self.btn_run)
        self.btn_export = QPushButton(t("digest.export"))
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._export)
        buttons.addWidget(self.btn_export)
        add_info_button(buttons, "digest.info_html")
        buttons.addStretch(1)
        lay.addLayout(buttons)

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        lay.addWidget(self.preview, 1)

        self.status_label = QLabel("")
        lay.addWidget(self.status_label)

        track(self, "scenario_digest", (900, 650))

    def _pick_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, t("yamlcheck.scenario"), self.path_edit.text() or ".")
        if path:
            self.path_edit.setText(path)

    def _run(self) -> None:
        if self._running:
            return
        root = self.path_edit.text().strip()
        if not root:
            self.status_label.setText(t("digest.need_scenario"))
            return
        self._running = True
        self.btn_run.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.status_label.setText(t("digest.running"))
        vanilla = get_vanilla_content_path() or ""

        def work() -> str:
            return render_markdown(collect_digest(Path(root), vanilla))

        async_call(self, work, on_done=self._done, on_fail=self._fail,
                   name="scenario-digest")

    def _done(self, text: str) -> None:
        self._running = False
        self.btn_run.setEnabled(True)
        self._text = text
        self.preview.setPlainText(text)
        self.btn_export.setEnabled(True)
        self.status_label.setText(t("digest.done"))

    def _fail(self, exc: BaseException) -> None:
        self._running = False
        self.btn_run.setEnabled(True)
        self.status_label.setText(t("digest.error", msg=str(exc)))

    def _export(self) -> None:
        if not self._text:
            return
        root = Path(self.path_edit.text().strip() or ".")
        default = root / f"{root.name}_fiche.md"
        path, _filter = QFileDialog.getSaveFileName(
            self, t("digest.save_title"), str(default), "Markdown (*.md)")
        if not path:
            return
        try:
            Path(path).write_text(self._text, encoding="utf-8")
        except OSError as exc:
            self.status_label.setText(t("digest.error", msg=str(exc)))
            return
        self.status_label.setText(t("digest.exported", path=path))
