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

"""Dialogue « Audit IA » : état de l'IA des PNJ du scénario (vaisseaux sans
.blueprint, pools BAI, pression drone, re-pops) et application guidée des
passes de réalisme (core/ai_realism.py) — dry-run affiché, application
confirmée, backups automatiques (BackupStore), re-audit après coup."""
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QTextEdit, QLabel,
)

from core.ai_realism import ALL_PASSES, run_audit, run_passes
from core.i18n import t
from gui.msgboxes import ask_yes_no
from gui.theme import icon

_SEV_COLORS = {
    "critical": QColor(220, 60, 60),
    "warn": QColor(200, 140, 20),
    "info": QColor(110, 110, 110),
}


class AiAuditDialog(QDialog):
    def __init__(self, parent, scenario_root: Path):
        super().__init__(parent)
        self.scenario = Path(scenario_root)
        self.setWindowTitle(t("aiaudit.title"))
        self.setModal(True)
        self.resize(760, 560)

        layout = QVBoxLayout(self)
        info = QLabel(t("aiaudit.info"))
        info.setWordWrap(True)
        layout.addWidget(info)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([t("aiaudit.col_id"), t("aiaudit.col_severity"),
                                   t("aiaudit.col_count"), t("aiaudit.col_message")])
        self.tree.header().setStretchLastSection(True)
        self.tree.setRootIsDecorated(False)
        layout.addWidget(self.tree, 1)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(140)
        self.log.setPlaceholderText(t("aiaudit.log_placeholder"))
        layout.addWidget(self.log, 0)

        buttons = QHBoxLayout()
        self.btn_audit = QPushButton(icon("fa5s.search", "#4a7dfc"), t("aiaudit.btn_audit"))
        self.btn_audit.clicked.connect(self._do_audit)
        buttons.addWidget(self.btn_audit)
        self.btn_dry = QPushButton(t("aiaudit.btn_dry"))
        self.btn_dry.setObjectName("secondaryButton")
        self.btn_dry.clicked.connect(self._do_dry)
        buttons.addWidget(self.btn_dry)
        self.btn_apply = QPushButton(icon("fa5s.magic", "#ffffff"), t("aiaudit.btn_apply"))
        self.btn_apply.clicked.connect(self._do_apply)
        buttons.addWidget(self.btn_apply)
        buttons.addStretch()
        btn_close = QPushButton(t("btn.close"))
        btn_close.setObjectName("secondaryButton")
        btn_close.clicked.connect(self.accept)
        buttons.addWidget(btn_close)
        layout.addLayout(buttons)

        self._do_audit()

    # ------------------------------------------------------------- audit
    def _do_audit(self):
        from gui.busy import run_long
        findings = run_long(self, lambda: run_audit(self.scenario),
                            message_key="ai.running_audit")
        self.tree.clear()
        for f in findings:
            item = QTreeWidgetItem(
                [f["id"], t(f"ai.sev_{f['severity']}"), str(f["count"]),
                 f["message"]])
            color = _SEV_COLORS.get(f["severity"])
            if color:
                item.setForeground(1, color)
            item.setData(0, Qt.ItemDataRole.UserRole, f)
            self.tree.addTopLevelItem(item)
        if not findings:
            item = QTreeWidgetItem(["", "", "", t("aiaudit.no_findings")])
            self.tree.addTopLevelItem(item)
        self._log(t("aiaudit.log_audited", n=len(findings)))

    # ----------------------------------------------------------- dry-run
    def _do_dry(self):
        from gui.busy import run_long
        reports = run_long(self, lambda: run_passes(
            self.scenario, list(ALL_PASSES), apply=False),
            message_key="ai.running_dry")
        self._show_reports(reports, applied=False)

    # ------------------------------------------------------------- apply
    def _do_apply(self):
        if not ask_yes_no(self, t("aiaudit.confirm_title"), t("aiaudit.confirm_text")):
            return
        from gui.busy import run_long
        try:
            reports = run_long(self, lambda: run_passes(
                self.scenario, list(ALL_PASSES), apply=True),
                message_key="ai.running_apply")
        except Exception as e:  # noqa: BLE001 - affiché dans le journal
            self._log(t("aiaudit.apply_error", error=str(e)))
            return
        self._show_reports(reports, applied=True)
        self._do_audit()

    # ------------------------------------------------------------ journal
    def _show_reports(self, reports, applied: bool):
        total = sum(r["edits"] for r in reports)
        lines = [t("aiaudit.log_header_dry" if not applied else "ai.log_header_apply")]
        for r in reports:
            if r["edits"] or r["files"]:
                lines.append(f"  {r['pass']}: {r['edits']} ({r['files']} fichiers)")
        lines.append(t("aiaudit.log_total", n=total))
        self._log("\n".join(lines))

    def _log(self, text: str):
        self.log.append(text)
