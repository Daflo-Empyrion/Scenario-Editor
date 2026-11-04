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

"""Dialogue « declarations inactives » -- nettoyage des Item/Block
commentes d'un ECF de la copie de travail, repris de la manipulation
manuelle du 04/11/2026 : reactiver les noms absents (sans Id si l'Id est
pris), supprimer les variantes deja representees. NON MODAL, comme la
bibliotheque de blocs : consultable pendant l'edition."""

from pathlib import Path

from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QMessageBox,
    QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from core.ecf.inactive_declarations import apply_plan, scan_file
from core.i18n import t
from core.workspace_undo import FileStateUndo, capture_file


class InactiveDeclarationsDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent or (main_window if isinstance(main_window, QWidget) else None))
        self.main_window = main_window
        self._plan = None
        self.setWindowTitle(t("inactive.title"))
        self.resize(760, 560)
        from gui.window_geometry import track
        track(self, "inactive_decls")
        self._build_ui()
        self._fill_files()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        intro = QLabel(t("inactive.intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        row = QHBoxLayout()
        row.addWidget(QLabel(t("inactive.file_label")))
        self.combo = QComboBox()
        self.combo.setEditable(False)
        self.combo.currentIndexChanged.connect(self._reset_plan)
        row.addWidget(self.combo, 1)
        layout.addLayout(row)

        self.chk_remove = QCheckBox(t("inactive.remove_dropped"))
        self.chk_remove.setChecked(True)
        layout.addWidget(self.chk_remove)

        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        layout.addWidget(self.report, 1)

        buttons = QHBoxLayout()
        self.btn_analyse = QPushButton(t("inactive.analyse"))
        self.btn_analyse.clicked.connect(self._analyse)
        self.btn_apply = QPushButton(t("inactive.apply"))
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self._apply)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_analyse)
        buttons.addWidget(self.btn_apply)
        layout.addLayout(buttons)

    def _fill_files(self):
        ws = getattr(self.main_window, "workspace", None)
        files = []
        if ws is not None:
            try:
                files = [f.path for f in ws.working.configuration
                         if f.extension == ".ecf"]
            except Exception:
                files = []
        files.sort(key=lambda p: (p.name not in ("BlocksConfig.ecf", "ItemsConfig.ecf"),
                                  p.name.lower()))
        for p in files:
            self.combo.addItem(f"{p.name} — {p.parent}", str(p))
        if not files:
            self.btn_analyse.setEnabled(False)
            self.report.setPlainText(t("inactive.no_ecf"))

    def _reset_plan(self, *_args):
        self._plan = None
        self.btn_apply.setEnabled(False)

    def _current_path(self):
        data = self.combo.currentData()
        return Path(data) if data else None

    def _analyse(self):
        path = self._current_path()
        if path is None:
            self.report.setPlainText(t("inactive.no_ecf"))
            return
        try:
            plan = scan_file(path)
        except Exception as e:
            QMessageBox.critical(self, t("err.title"), str(e))
            return
        self._plan = plan
        self.btn_apply.setEnabled(not plan.nothing_to_do)
        if plan.nothing_to_do:
            self.report.setPlainText(t("inactive.nothing"))
            return
        lines = [t("inactive.report", active=len(plan.active_names),
                   inactive=len(plan.inactive), restore=len(plan.to_restore),
                   drop=len(plan.to_drop), ids=len(plan.id_dropped))]
        if plan.to_restore:
            lines.append(t("inactive.restore_list",
                           names=", ".join(d.name for d in plan.to_restore)))
        if plan.to_drop:
            lines.append(t("inactive.drop_list",
                           names=", ".join(d.name for d in plan.to_drop)))
        if plan.id_dropped:
            lines.append(t("inactive.id_list",
                           names=", ".join(plan.id_dropped)))
        self.report.setPlainText("\n\n".join(lines))

    def _apply(self):
        path = self._current_path()
        if self._plan is None or path is None or Path(self._plan.path) != path:
            QMessageBox.information(self, t("inactive.title"), t("inactive.analyse_first"))
            return
        if QMessageBox.question(
                self, t("inactive.title"),
                t("inactive.confirm", file=path.name,
                  restore=len(self._plan.to_restore),
                  drop=len(self._plan.to_drop) if self.chk_remove.isChecked() else 0)
        ) != QMessageBox.StandardButton.Yes:
            return
        prior = capture_file(path)
        try:
            result = apply_plan(self._plan, remove_dropped=self.chk_remove.isChecked())
        except Exception as e:
            QMessageBox.critical(self, t("err.title"), str(e))
            return
        mw = self.main_window
        if mw is not None and getattr(mw, "workspace", None) is not None:
            mw._push_workspace_undo(FileStateUndo(
                path, prior, t("inactive.undo_label", n=result.restored)))
            mw.workspace.rescan_working()
            mw._reload_tab_if_open_and_unmodified(path)
            mw.statusBar().showMessage(
                t("inactive.done", restore=result.restored, drop=result.dropped,
                  headers=result.headers_removed), 8000)
        self._plan = None
        self.btn_apply.setEnabled(False)
        self._analyse()
