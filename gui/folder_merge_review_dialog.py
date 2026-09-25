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

"""Fenetre de REVISION d'une fusion de dossier (demande 25/09/2026) : les
fichiers non-ECF (Sectors.yaml, Playfields/, Prefabs/) etaient copies en
aveugle. Desormais : plan fichier par fichier (nouveau / remplacement avec
diff / fusion ECF / fusion CSV) + DEPENDANCES detectees (dossiers de
playfield et POIs references par un Sectors.yaml source et absents de la
copie de travail), cochables avant validation."""
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton,
                             QTreeWidget, QTreeWidgetItem, QVBoxLayout)

from core.i18n import t
from core.merge_dependencies import (DependencyFile, STATUS_CSV, STATUS_ECF,
                                     STATUS_NEW, STATUS_OVERWRITE, FilePlan,
                                     plan_folder_merge)
from core.sectors_merge import SectorUnit
from gui.window_geometry import track


class FolderMergeReviewDialog(QDialog):
    """Plan de fusion cocheable + dependances proposees. N'applique RIEN :
    l'appelant lit `selected_merge_files()` et `selected_dependencies()`."""

    COL_CHECK, COL_STATUS, COL_PATH, COL_INFO = range(4)

    def __init__(self, main_window, source_folder: Path, source_root: Path,
                 source_label: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("mergeplan.title"))
        self.main_window = main_window
        self.source_folder = Path(source_folder)
        self.source_root = Path(source_root)
        self.source_label = source_label
        track(self, "folder_merge_review", (880, 600))

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(t("mergeplan.intro",
                                  folder=self.source_folder.name)))

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([t("mergeplan.col_apply"),
                                   t("mergeplan.col_status"),
                                   t("mergeplan.col_path"),
                                   t("mergeplan.col_info")])
        self.tree.setColumnWidth(0, 70)
        self.tree.setColumnWidth(1, 170)
        self.tree.setColumnWidth(2, 380)
        layout.addWidget(self.tree, 1)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        buttons = QHBoxLayout()
        btn_all = QPushButton(t("trans.check_all"))
        btn_all.clicked.connect(lambda: self._set_all_checks(True))
        buttons.addWidget(btn_all)
        btn_none = QPushButton(t("trans.uncheck_all"))
        btn_none.clicked.connect(lambda: self._set_all_checks(False))
        buttons.addWidget(btn_none)
        buttons.addStretch()
        self.btn_apply = QPushButton(t("mergeplan.btn_apply"))
        self.btn_apply.setObjectName("primaryButton")
        self.btn_apply.clicked.connect(self.accept)
        buttons.addWidget(self.btn_apply)
        self.btn_cancel = QPushButton(t("btn.cancel"))
        self.btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(self.btn_cancel)
        layout.addLayout(buttons)

        from gui.busy import run_long
        ws_obj = getattr(self.main_window, "workspace", None)
        working_root = (Path(ws_obj.working_root)
                        if ws_obj is not None else None)
        self.plan = run_long(
            self, lambda: plan_folder_merge(self.source_folder,
                                            self.source_root, working_root))
        # fusion structurelle du Sectors.yaml (tranche 2) : unites absentes
        # de la copie de travail, inserees un a un sans ecraser le fichier
        self.structural_units = []
        self.sectors_plan = next((p for p in self.plan.files
                                  if p.rel.endswith("Sectors.yaml")
                                  and p.status == STATUS_OVERWRITE), None)
        if self.sectors_plan is not None and working_root is not None:
            from core.sectors_merge import analyze_sectors_merge
            self.structural_units = run_long(
                self, lambda: analyze_sectors_merge(
                    working_root / self.sectors_plan.rel,
                    self.sectors_plan.source))
        self._fill()

    # ------------------------------------------------------------- contenu

    def _fill(self):
        status_i18n = {STATUS_NEW: t("mergeplan.status_new"),
                       STATUS_OVERWRITE: t("mergeplan.status_overwrite"),
                       STATUS_ECF: t("mergeplan.status_ecf"),
                       STATUS_CSV: t("mergeplan.status_csv")}
        if self.structural_units:
            header = QTreeWidgetItem(
                ["", t("mergeplan.struct_header"),
                 f"Sectors.yaml ({len(self.structural_units)})",
                 t("mergeplan.struct_hint")])
            header.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.tree.addTopLevelItem(header)
            for unit in self.structural_units:
                kind_label = t("mergeplan.struct_system") \
                    if unit.kind == "system" \
                    else (t("mergeplan.struct_sector")
                          if unit.kind == "sector"
                          else t("mergeplan.struct_playfield"))
                item = QTreeWidgetItem(["", kind_label,
                                        f"{unit.name}  ·  {unit.system}",
                                        unit.coordinates])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Checked)
                item.setData(0, Qt.ItemDataRole.UserRole, unit)
                self.tree.addTopLevelItem(item)
        for plan in self.plan.files:
            item = QTreeWidgetItem(["", status_i18n[plan.status],
                                    plan.rel, plan.diff_summary])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Checked if plan.checked
                               else Qt.CheckState.Unchecked)
            if plan.diff_text:
                item.setToolTip(self.COL_INFO, plan.diff_text)
            item.setData(0, Qt.ItemDataRole.UserRole, plan)
            self.tree.addTopLevelItem(item)
        if self.plan.dependencies:
            header = QTreeWidgetItem(["", t("mergeplan.dep_header"), "", ""])
            header.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.tree.addTopLevelItem(header)
            for dep in self.plan.dependencies:
                item = QTreeWidgetItem([
                    "", t(dep.reason_i18n),
                    str(dep.dest.relative_to(self.source_root.parent)),
                    dep.detail])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Checked)
                item.setData(0, Qt.ItemDataRole.UserRole, dep)
                self.tree.addTopLevelItem(item)
        n_files = len(self.plan.files)
        n_deps = len(self.plan.dependencies)
        self.status_label.setText(t("mergeplan.summary",
                                    f=n_files, d=n_deps))
        self._refresh_buttons()

    def _refresh_buttons(self):
        n = (len(self.selected_merge_files())
             + len(self.selected_dependencies())
             + len(self.selected_structural_units()))
        self.btn_apply.setText(t("mergeplan.btn_apply_n", n=n))

    def _set_all_checks(self, state: bool):
        cs = Qt.CheckState.Checked if state else Qt.CheckState.Unchecked
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(0, cs)
        self._refresh_buttons()

    # ------------------------------------------------------------- resultats

    def selected_merge_files(self):
        """Fichiers du dossier fusionne coches (chemins absolus source)."""
        out = []
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            plan = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(plan, FilePlan) \
                    and item.checkState(0) == Qt.CheckState.Checked:
                out.append(plan.source)
        return out

    def selected_structural_units(self):
        """Unites de fusion structurelle du Sectors.yaml cochees."""
        out = []
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            unit = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(unit, SectorUnit) \
                    and item.checkState(0) == Qt.CheckState.Checked:
                out.append(unit)
        return out

    def selected_dependencies(self):
        """Dependances cochees (DependencyFile)."""
        out = []
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            dep = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(dep, DependencyFile) \
                    and item.checkState(0) == Qt.CheckState.Checked:
                out.append(dep)
        return out
