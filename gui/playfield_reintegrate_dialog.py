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

"""Reintegration de playfields orphelins : liste cochable, lot par systeme,
apercu des lignes YAML, application avec backup + undo, puis bilan.

Le placement calque le corpus (voir core/playfield_reintegrate) : anneau de
30 entre secteurs, lunes et orbites en offset dans le secteur d'une planete,
`SectorMapType` seulement quand le jeu en attend un. Les secteurs ecrits par
l'ancienne version (signature d'etoile) sont proposes a la suppression.

Rappel affiche : le jeu charge la COPIE du Sectors.yaml faite dans la
sauvegarde — ces ajouts ne valent que pour une NOUVELLE partie.
"""
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QLabel,
                             QPlainTextEdit, QPushButton, QSpinBox,
                             QTreeWidget, QTreeWidgetItem, QVBoxLayout)

from core import settings
from core.i18n import t
from core.playfield_reintegrate import (apply_placements,
                                        find_legacy, find_missing_arrivals,
                                        find_orphans, plan_placements,
                                        remove_legacy, render_preview,
                                        sectors_yaml)
from gui.busy import run_long
from gui.ewa_async import async_call
from gui.msgboxes import ask_yes_no, info
from gui.window_geometry import track


class PlayfieldReintegrateDialog(QDialog):
    """Un orphelin = un dossier de Playfields/<Type> que le Sectors.yaml ne
    declare pas. On en coche, on choisit le lot par systeme, on apercoit les
    lignes, on applique (backup central + undo)."""

    def __init__(self, root, parent=None, main_window=None):
        super().__init__(parent)
        self.setWindowTitle(t("reintegrate.title"))
        self.setMinimumSize(760, 620)
        self._root = Path(root)
        self._main = main_window
        self._legacy = []
        self._arrivals = []
        self.applied = 0

        layout = QVBoxLayout(self)

        head = QHBoxLayout()
        head.addWidget(QLabel(t("reintegrate.per_system")))
        self.spin = QSpinBox()
        self.spin.setRange(1, 20)
        self.spin.setValue(2)
        self.spin.setToolTip(t("reintegrate.per_system.tip"))
        head.addWidget(self.spin)
        head.addStretch(1)
        self.legacy_check = QCheckBox("")
        self.legacy_check.setVisible(False)
        self.arrival_check = QCheckBox("")
        self.arrival_check.setVisible(False)
        layout.addLayout(head)
        layout.addWidget(self.legacy_check)
        layout.addWidget(self.arrival_check)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([t("reintegrate.col_type"),
                                   t("reintegrate.col_category"),
                                   t("reintegrate.col_description")])
        self.tree.setColumnWidth(0, 250)
        self.tree.setColumnWidth(1, 110)
        layout.addWidget(self.tree, 1)

        layout.addWidget(QLabel(t("reintegrate.preview")))
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFixedHeight(180)
        layout.addWidget(self.preview)

        buttons = QHBoxLayout()
        self.btn_preview = QPushButton(t("reintegrate.preview_btn"))
        self.btn_apply = QPushButton(t("reintegrate.apply"))
        self.btn_apply.setObjectName("primaryButton")
        self.btn_apply.setEnabled(False)
        btn_close = QPushButton(t("reintegrate.close"))
        buttons.addWidget(self.btn_preview)
        buttons.addWidget(self.btn_apply)
        buttons.addStretch(1)
        buttons.addWidget(btn_close)
        layout.addLayout(buttons)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.btn_preview.clicked.connect(self._preview)
        self.btn_apply.clicked.connect(self._apply)
        self.arrival_check.toggled.connect(self._invalidated)
        btn_close.clicked.connect(self.reject)
        self.tree.itemChanged.connect(self._invalidated)
        self.spin.valueChanged.connect(self._invalidated)
        self.legacy_check.toggled.connect(self._invalidated)

        self._load()
        track(self, "playfield_reintegrate", (840, 660))

    # ------------------------------------------------------------- lecture

    def _load(self) -> None:
        self._legacy = run_long(self, lambda: find_legacy(self._root))
        self.legacy_check.blockSignals(True)
        self.legacy_check.setVisible(bool(self._legacy))
        self.legacy_check.setChecked(bool(self._legacy))
        self.legacy_check.setText(
            t("reintegrate.legacy", n=len(self._legacy)))
        self.legacy_check.blockSignals(False)

        # secteurs de planete sans playfield d'arrivee : la carte n'a aucune
        # cible de warp, « Selectionner » ne fait rien (vecu 22/10)
        self._arrivals = run_long(
            self, lambda: find_missing_arrivals(self._root))
        self.arrival_check.blockSignals(True)
        self.arrival_check.setVisible(bool(self._arrivals))
        self.arrival_check.setChecked(bool(self._arrivals))
        self.arrival_check.setText(
            t("reintegrate.arrivals", n=len(self._arrivals)))
        self.arrival_check.blockSignals(False)

        orphans = run_long(self, lambda: find_orphans(self._root))
        self.tree.blockSignals(True)
        self.tree.clear()
        for family in ("surface", "space"):
            subset = [o for o in orphans if o.family == family]
            if not subset:
                continue
            label = t("reintegrate.group_surface" if family == "surface"
                      else "reintegrate.group_space", n=len(subset))
            parent = QTreeWidgetItem([label, "", ""])
            parent.setFlags(Qt.ItemFlag.ItemIsUserCheckable
                            | Qt.ItemFlag.ItemIsAutoTristate
                            | Qt.ItemFlag.ItemIsEnabled)
            parent.setCheckState(0, Qt.CheckState.Unchecked)
            self.tree.addTopLevelItem(parent)
            for orphan in subset:
                child = QTreeWidgetItem([orphan.type_name,
                                         t(orphan.kind_key),
                                         orphan.description])
                child.setFlags(Qt.ItemFlag.ItemIsUserCheckable
                               | Qt.ItemFlag.ItemIsEnabled
                               | Qt.ItemFlag.ItemIsSelectable)
                child.setCheckState(0, Qt.CheckState.Unchecked)
                child.setData(0, Qt.ItemDataRole.UserRole, orphan.type_name)
                parent.addChild(child)
        self.tree.blockSignals(False)
        self._invalidated()
        if not orphans and not self._legacy:
            self.status.setText(t("reintegrate.none"))

    def _selected(self) -> list:
        picked = []
        for index in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(index)
            for row in range(parent.childCount()):
                child = parent.child(row)
                if child.checkState(0) == Qt.CheckState.Checked:
                    picked.append(child.data(0, Qt.ItemDataRole.UserRole))
        return picked

    def _removals(self) -> list:
        return self._legacy if self.legacy_check.isChecked() else []

    def _routes(self) -> list:
        return self._arrivals if self.arrival_check.isChecked() else []

    def _invalidated(self, *_args) -> None:
        self.btn_apply.setEnabled(False)
        self.preview.clear()

    # ------------------------------------------------------------- actions

    def _preview(self) -> None:
        picks = self._selected()
        plan = plan_placements(self._root, picks, self.spin.value()) \
            if picks else []
        plan += self._routes()
        removals = self._removals()
        if not plan and not removals:
            self.status.setText(t("reintegrate.none_selected"))
            return
        text = render_preview(plan, removals)
        if len(plan) < len(picks):
            text += "\n" + t("reintegrate.skipped", n=len(picks) - len(plan))
        self.preview.setPlainText(text)
        self.btn_apply.setEnabled(True)
        self.status.setText(t("reintegrate.plan_ready", n=len(plan),
                              r=len(removals))
                            + "\n" + t("reintegrate.new_game"))

    def _apply(self) -> None:
        picks = self._selected()
        plan = plan_placements(self._root, picks, self.spin.value()) \
            if picks else []
        plan += self._routes()
        removals = self._removals()
        if not plan and not removals:
            self.status.setText(t("reintegrate.none_selected"))
            return
        if not ask_yes_no(self, t("reintegrate.title"),
                          t("reintegrate.confirm", n=len(plan),
                            r=len(removals))):
            return
        path = sectors_yaml(self._root)
        if path is None:
            self.status.setText(t("reintegrate.no_sectors"))
            return
        from core.fsutil import central_backup
        from core.workspace_undo import FileStateUndo, capture_file
        prior = capture_file(path)
        removed = run_long(self, lambda: remove_legacy(self._root, removals)) \
            if removals else 0
        applied, details = run_long(
            self, lambda: apply_placements(self._root, plan))
        if not applied and not removed:
            self.status.setText("\n".join(details)
                                or t("reintegrate.empty_plan"))
            return
        central_backup(path)
        self.applied += applied
        main = self._main
        if main is not None:
            undo = getattr(main, "_push_workspace_undo", None)
            if undo is not None:
                undo(FileStateUndo(path, prior,
                                   t("reintegrate.undo", n=applied + removed)))
            reload_tab = getattr(main, "_reload_tab_if_open_and_unmodified",
                                 None)
            if reload_tab is not None:
                reload_tab(path)
            ws = getattr(main, "workspace", None)
            if ws is not None:
                ws.rescan_working()
        message = (t("reintegrate.done", n=applied, r=removed) + "\n"
                   + t("reintegrate.new_game"))
        if details:
            message += "\n" + "\n".join(details[:5])
        self.status.setText(message)
        self._load()
        self._run_bilan(message)

    def _run_bilan(self, message: str) -> None:
        vanilla = settings.get_vanilla_content_path() or ""

        def work():
            from core.launch_check import run_launch_checks
            return run_launch_checks(self._root, vanilla)

        def done(issues):
            errors = sum(1 for i in issues if i.severity == "error")
            warnings = len(issues) - errors
            self.status.setText(message + "\n"
                                + t("reintegrate.bilan", e=errors, w=warnings))

        def failed(error):
            self.status.setText(message + "\n"
                                + t("reintegrate.bilan_failed", msg=str(error)))

        async_call(self, work, on_done=done, on_fail=failed,
                   name="reintegrate-bilan")


def open_reintegrate(parent, main_window=None) -> bool:
    ws = getattr(main_window, "workspace", None)
    root = getattr(ws, "working_root", None) if ws is not None else None
    if root is None:
        info(parent, t("reintegrate.title"), t("reintegrate.no_workspace"))
        return False
    dialog = PlayfieldReintegrateDialog(root, parent=parent,
                                       main_window=main_window)
    dialog.exec()
    return dialog.applied > 0
