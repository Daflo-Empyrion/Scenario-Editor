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

"""Tableau de bord du scenario (demande du 10/09/2026) : vue d'ensemble en
LECTURE SEULE de la copie de travail -- decompte des fichiers par type,
modifications en attente, marchands, volume de blocs ECF et bilan des
regles metiers (validation ECF + TraderZone). Tout est recalcule a
l'ouverture (busy guard) ; rien n'est ecrit."""

from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QLabel, QFrame, QPushButton,
)

from core.i18n import t


class DashboardDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self.main_window = main_window
        self.setWindowTitle(t("dash.title"))
        self.resize(560, 420)
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(24)
        self.grid.setVerticalSpacing(10)
        layout.addLayout(self.grid)
        btn = QPushButton(t("dash.refresh"))
        btn.clicked.connect(self._refresh)
        layout.addWidget(btn)
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

    def _add_stat(self, row, col, value, label):
        frame = QFrame()
        v = QVBoxLayout(frame)
        val = QLabel(str(value))
        val.setStyleSheet("font-size: 22px; font-weight: 700;")
        lab = QLabel(label)
        lab.setStyleSheet("color: gray;")
        lab.setWordWrap(True)
        v.addWidget(val)
        v.addWidget(lab)
        self.grid.addWidget(frame, row, col)

    def _refresh(self):
        ws = self.main_window.workspace
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not ws:
            self.summary.setText(t("status.no_project"))
            return
        from gui.busy import busy_guard
        try:
            with busy_guard(self):
                self._compute(ws)
        except Exception as e:
            self.summary.setText(f"{t('err.title')} : {e}")

    def _compute(self, ws):
        working = ws.working
        n_ecf = sum(1 for f in working.configuration if f.extension == '.ecf')
        n_csv = sum(1 for f in working.configuration if f.extension == '.csv')
        n_yaml = (sum(1 for pf in working.playfields.values()
                      for p in pf.role_files.values() if p.suffix.lower() in ('.yaml', '.yml'))
                  + sum(1 for f in working.sectors if f.path.suffix.lower() in ('.yaml', '.yml'))
                  + sum(1 for f in working.random_presets
                        if f.path.suffix.lower() in ('.yaml', '.yml')))
        n_blocks = self._count_ecf_blocks(working.root_path)
        n_traders = self._count_traders(working.root_path)
        errors, warnings = self._validation_summary(working.root_path)
        modified = len(self.main_window._modified_tab_widgets())

        cells = [
            (n_ecf, "dash.stat_ecf"),
            (n_blocks, "dash.stat_blocks"),
            (n_yaml, "dash.stat_yaml"),
            (n_csv, "dash.stat_csv"),
            (n_traders, "dash.stat_traders"),
            (modified, "dash.stat_modified"),
        ]
        for i, (value, key) in enumerate(cells):
            self._add_stat(i // 3, i % 3, value, t(key))
        self.summary.setText(t("dash.validation_summary",
                               errors=errors, warnings=warnings))

    def _count_ecf_blocks(self, root: Path) -> int:
        from core.ecf.parser import parse_ecf_file
        from core.ecf.model import EcfBlock
        total = 0
        for f in self.main_window.workspace.working.configuration:
            if f.extension != '.ecf':
                continue
            try:
                doc = parse_ecf_file(f.path)
            except Exception:
                continue
            stack = list(doc.nodes)
            while stack:
                node = stack.pop()
                if isinstance(node, EcfBlock):
                    total += 1
                    stack.extend(node.children)
        return total

    def _count_traders(self, root: Path) -> int:
        from core.economy.trader_config import load_trader_names
        try:
            return len(load_trader_names(root / "Content" / "Configuration"
                                         / "TraderNPCConfig.ecf"))
        except Exception:
            return 0

    def _validation_summary(self, root: Path) -> "tuple[int, int]":
        from core.ecf.validation import validate_scenario
        from core.trader_zone_check import check_trader_zone_references
        errors = warnings = 0
        try:
            issues_by_file = validate_scenario(root)
            for issues in issues_by_file.values():
                errors += sum(1 for i in issues if i.level == 'error')
                warnings += sum(1 for i in issues if i.level == 'warning')
            for i in check_trader_zone_references(root):
                if i.level == 'error':
                    errors += 1
                else:
                    warnings += 1
        except Exception:
            pass
        return errors, warnings
