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

"""Fenetre de fusion ECF PAR NOM (v1.14.0, demande du 01/10/2026) :
pour les fichiers a blocs identifies par leur Name sans Id
(EGroupsConfig = créatures/groupes, EClassConfig = entites/classes...)
que la fusion generique refuse des que la copie de travail contient des
noms dupliques. Apercu cochable des blocs a ajouter, conflits signalés,
application avec .bak + undo + idempotence (core/name_merge.py)."""
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton,
                             QTreeWidget, QTreeWidgetItem, QVBoxLayout)

from core.i18n import t
from gui.window_geometry import track


class NameMergeDialog(QDialog):
    """Clic droit sur un fichier ECF a blocs Nom (EGroupsConfig,
    EClassConfig...)."""

    def __init__(self, main_window, source_path: Path):
        from PyQt6.QtWidgets import QWidget
        qt_parent = (main_window
                     if isinstance(main_window, QWidget) else None)
        super().__init__(qt_parent)
        self.setWindowTitle(t("namemerge.title"))
        self.main_window = main_window
        self.source_path = Path(source_path)
        self.working_path = None
        self._plan = None
        ws = getattr(main_window, "workspace", None) if main_window else None
        if ws is not None and getattr(ws, "working_root", None):
            cfg = Path(ws.working_root) / "Content/Configuration"
            if not cfg.is_dir():
                cfg = Path(ws.working_root) / "Configuration"
            self.working_path = cfg / self.source_path.name
        track(self, "name_merge", (860, 620))
        self._build_ui()

    # ------------------------------------------------------------- interface

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(t("namemerge.intro")))
        lay.addWidget(QLabel(t("namemerge.working") + " "
                             + str(self.working_path or "-")))
        lay.addWidget(QLabel(t("namemerge.source") + " "
                             + str(self.source_path)))

        self.btn_analyze = QPushButton(t("galaxy.analyze"))
        self.btn_analyze.setObjectName("primaryButton")
        self.btn_analyze.clicked.connect(self._analyze)
        lay.addWidget(self.btn_analyze)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([t("namemerge.col_name"),
                                   t("namemerge.col_kind")])
        self.tree.setColumnWidth(0, 380)
        self.tree.setColumnWidth(1, 200)
        lay.addWidget(self.tree, 1)

        self.status_label = QLabel("")
        lay.addWidget(self.status_label)

        bottom = QHBoxLayout()
        self.btn_apply = QPushButton(t("namemerge.apply"))
        self.btn_apply.setObjectName("primaryButton")
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self._apply)
        bottom.addWidget(self.btn_apply, 1)
        self.btn_close = QPushButton(t("btn.close"))
        self.btn_close.clicked.connect(self.reject)
        bottom.addWidget(self.btn_close)
        lay.addLayout(bottom)

        if self.working_path is None:
            self.btn_analyze.setEnabled(False)
            self.status_label.setText(t("galaxy.need_project"))

    # ------------------------------------------------------------- analyse

    def _compute(self):
        from core.name_merge import analyze_name_merge
        return analyze_name_merge(self.working_path, self.source_path)

    def _analyze(self):
        if self.working_path is None:
            return
        from gui.busy import run_long
        self.tree.clear()
        self.btn_apply.setEnabled(False)
        plan = run_long(self, self._compute)
        self._plan = plan
        if not plan.ok:
            self.status_label.setText("; ".join(plan.errors))
            return

        def _group(title):
            it = QTreeWidgetItem([title, ""])
            it.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.tree.addTopLevelItem(it)
            return it

        if plan.blocks_add:
            g = _group(t("namemerge.group_add"))
            for b in plan.blocks_add:
                item = QTreeWidgetItem([b.name, b.kind])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Checked)
                item.setData(0, Qt.ItemDataRole.UserRole, b.name)
                g.addChild(item)
        if plan.blocks_same:
            g = _group(t("namemerge.group_same"))
            for nm in plan.blocks_same:
                it = QTreeWidgetItem([nm, t("namemerge.same_detail")])
                it.setFlags(Qt.ItemFlag.ItemIsEnabled)
                g.addChild(it)
        if plan.working_dupes:
            g = _group(t("namemerge.group_working_dupes"))
            for nm, extra in plan.working_dupes:
                it = QTreeWidgetItem(
                    [nm, t("namemerge.dupe_detail", n=extra + 1)])
                it.setFlags(Qt.ItemFlag.ItemIsEnabled)
                g.addChild(it)
        self.tree.expandAll()

        self.status_label.setText(
            t("namemerge.none") if not plan.blocks_add else
            t("namemerge.found", n=len(plan.blocks_add),
              same=len(plan.blocks_same)))
        self.btn_apply.setEnabled(bool(plan.blocks_add))

    # ------------------------------------------------------------- application

    def _apply(self):
        from gui.busy import run_long
        from gui.msgboxes import info
        names = []
        for i in range(self.tree.topLevelItemCount()):
            g = self.tree.topLevelItem(i)
            for j in range(g.childCount()):
                it = g.child(j)
                data = it.data(0, Qt.ItemDataRole.UserRole)
                if data is None:
                    continue
                if it.checkState(0) == Qt.CheckState.Checked:
                    names.append(data)
        if not names or self._plan is None:
            return
        stats = run_long(self, lambda: self._do_apply(names))
        if self.main_window is not None:
            from core.workspace_undo import FileStateUndo, capture_file
            self.main_window._push_workspace_undo(FileStateUndo(
                self.working_path, capture_file(self.working_path),
                t("namemerge.undo", file=Path(self.working_path).name)))
            reload_tab = getattr(self.main_window,
                                 "_reload_tab_if_open_and_unmodified", None)
            if reload_tab:
                reload_tab(self.working_path)
        self.status_label.setText(t("namemerge.done", n=stats["blocks"]))
        info(self, t("namemerge.done_title"),
             t("namemerge.done", n=stats["blocks"]))
        self._analyze()

    def _do_apply(self, names):
        from core.name_merge import apply_name_merge
        return apply_name_merge(self._plan, self.working_path, names=names)
