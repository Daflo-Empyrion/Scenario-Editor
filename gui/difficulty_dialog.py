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

"""Réglage du danger : un palier (coefficients par domaine, éditables),
un aperçu de toutes les valeurs modifiées (rien de précoché, chaque nouvelle
valeur est corrigeable), puis application avec backup et annulation.
Moteur : core/difficulty_tuning.py."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox,
                             QFileDialog, QHBoxLayout, QHeaderView, QLabel,
                             QLineEdit, QPushButton, QSpinBox, QTableWidget,
                             QTableWidgetItem, QVBoxLayout)

from core.difficulty_tuning import (DOMAINS, PRESETS, PRESET_ORDER,
                                    apply_entries, build_plan,
                                    list_undo_snapshots,
                                    restore_undo_snapshot, save_undo_snapshot,
                                    undo_backup_root)
from core.i18n import t
from gui.ewa_async import async_call
from gui.module_info import add_info_button
from gui.msgboxes import ask_yes_no, info
from gui.window_geometry import track

_COLS = 5      # case, domaine, cible, ancienne, nouvelle


class _Ck(QTableWidgetItem):
    def __init__(self, index: int):
        super().__init__()
        self.prop_idx = index
        self.setFlags(Qt.ItemFlag.ItemIsEnabled
                      | Qt.ItemFlag.ItemIsUserCheckable)
        self.setCheckState(Qt.CheckState.Unchecked)


class DifficultyDialog(QDialog):
    def __init__(self, parent, working_root: str = ""):
        super().__init__(parent)
        self.setWindowTitle(t("diff.title"))
        self._running = False
        self._plan = None
        self._undo = []           # [(Path, contenu precedent)]

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

        presets = QHBoxLayout()
        presets.addWidget(QLabel(t("diff.preset")))
        self.cmb_preset = QComboBox()
        for key in PRESET_ORDER:
            self.cmb_preset.addItem(t(f"diff.preset_{key}"), key)
        self.cmb_preset.setCurrentIndex(PRESET_ORDER.index("normal"))
        self.cmb_preset.currentIndexChanged.connect(self._apply_preset)
        presets.addWidget(self.cmb_preset, 1)
        add_info_button(presets, "difficulty.info_html")
        lay.addLayout(presets)

        coeffs = QHBoxLayout()
        self.spins = {}
        for domain in DOMAINS:
            box = QVBoxLayout()
            box.addWidget(QLabel(t(f"diff.domain_{domain}")))
            spin = QSpinBox()
            spin.setRange(10, 300)          # x0.10 a x3.00
            spin.setSingleStep(5)
            spin.setValue(100)
            spin.setSuffix(" %")
            self.spins[domain] = spin
            box.addWidget(spin)
            coeffs.addLayout(box)
        lay.addLayout(coeffs)
        lay.addWidget(QLabel(t("diff.hint")))

        tools = QHBoxLayout()
        self.btn_build = QPushButton(t("diff.build"))
        self.btn_build.clicked.connect(self._build)
        tools.addWidget(self.btn_build)
        self.cmb_filter = QComboBox()
        self.cmb_filter.addItem(t("sw.filter_all"), "__all__")
        for domain in DOMAINS:
            self.cmb_filter.addItem(t(f"diff.domain_{domain}"), domain)
        self.cmb_filter.currentIndexChanged.connect(self._refilter)
        tools.addWidget(self.cmb_filter)
        self.edit_filter = QLineEdit()
        self.edit_filter.setPlaceholderText(t("taudit.filter_name"))
        self.edit_filter.textChanged.connect(self._refilter)
        tools.addWidget(self.edit_filter, 1)
        lay.addLayout(tools)

        self.table = QTableWidget(0, _COLS)
        self.table.setHorizontalHeaderLabels([
            "", t("diff.col_domain"), t("diff.col_target"),
            t("diff.col_old"), t("diff.col_new")])
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 34)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        self.btn_all = QPushButton(t("market.check_all"))
        self.btn_all.clicked.connect(self._check_all)
        self.btn_all.setEnabled(False)
        buttons.addWidget(self.btn_all)
        self.btn_none = QPushButton(t("market.uncheck_all"))
        self.btn_none.clicked.connect(self._uncheck_all)
        self.btn_none.setEnabled(False)
        buttons.addWidget(self.btn_none)
        buttons.addStretch(1)
        self.btn_undo = QPushButton(t("diff.undo"))
        self.btn_undo.setEnabled(False)
        self.btn_undo.clicked.connect(self._undo_apply)
        buttons.addWidget(self.btn_undo)
        self.btn_apply = QPushButton(t("market.apply"))
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self._apply)
        buttons.addWidget(self.btn_apply)
        lay.addLayout(buttons)

        # annulation DURABLE : les applications passees sont archivees sur
        # disque et restables ici meme apres fermeture du dialogue
        backups_row = QHBoxLayout()
        backups_row.addWidget(QLabel(t("diff.backups_label")))
        self.cmb_backups = QComboBox()
        backups_row.addWidget(self.cmb_backups, 1)
        self.btn_restore = QPushButton(t("diff.restore"))
        self.btn_restore.setObjectName("secondaryButton")
        self.btn_restore.clicked.connect(self._restore_snapshot)
        backups_row.addWidget(self.btn_restore)
        lay.addLayout(backups_row)
        self._refresh_backups()

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        lay.addWidget(self.status_label)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        box.rejected.connect(self.reject)
        lay.addWidget(box)
        track(self, "difficulty", (1180, 760))

    # --------------------------------------------------------------- setup

    def _pick_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, t("yamlcheck.scenario"), self.path_edit.text() or ".")
        if path:
            self.path_edit.setText(path)

    def _apply_preset(self):
        preset = PRESETS[self.cmb_preset.currentData()]
        for domain, spin in self.spins.items():
            spin.setValue(int(round(preset.get(domain, 1.0) * 100)))

    def _coefficients(self):
        return {domain: spin.value() / 100.0 for domain, spin in self.spins.items()}

    # ---------------------------------------------------------------- plan

    def _build(self):
        if self._running:
            return
        root = self.path_edit.text().strip()
        if not root:
            self.status_label.setText(t("yamlcheck.need_scenario"))
            return
        self._running = True
        self.btn_build.setEnabled(False)
        self.status_label.setText(t("taudit.running"))
        coeffs = self._coefficients()

        def work():
            return build_plan(Path(root), coeffs)

        async_call(self, work, on_done=self._on_plan,
                   on_fail=self._on_fail, name="difficulty")

    def _on_fail(self, exc: Exception):
        self._running = False
        self.btn_build.setEnabled(True)
        self.status_label.setText(f"{t('yamlcheck.failed')}  ({exc})")

    def _on_plan(self, plan):
        self._running = False
        self.btn_build.setEnabled(True)
        self._plan = plan
        editable = [e for e in plan.entries if e.editable]
        blocked = len(plan.entries) - len(editable)
        if plan.refusals:
            self.status_label.setText(t("diff.refused",
                                        reasons=" ; ".join(plan.refusals)))
            self.btn_apply.setEnabled(False)
        else:
            self.status_label.setText(t(
                "diff.stats", n=len(editable), blocked=blocked))
            self.btn_apply.setEnabled(bool(editable))
        self.btn_all.setEnabled(True)
        self.btn_none.setEnabled(True)
        self._fill()

    def _fill(self):
        entries = self._plan.entries if self._plan else []
        self.table.setRowCount(len(entries))
        for index, entry in enumerate(entries):
            self.table.setItem(index, 0, _Ck(index))
            self._txt(index, 1, t(f"diff.domain_{entry.domain}"))
            self._txt(index, 2, entry.target)
            self._txt(index, 3, entry.label_value(entry.old_value))
            new_item = QTableWidgetItem(entry.label_value(entry.new_value))
            new_item.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                      | Qt.AlignmentFlag.AlignVCenter)
            if entry.blocked:
                new_item.setToolTip(entry.blocked)
                new_item.setForeground(Qt.GlobalColor.darkGray)
            else:
                new_item.setFlags(new_item.flags()
                                  | Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(index, 4, new_item)
        self._refilter()

    def _txt(self, row: int, col: int, text: str):
        item = QTableWidgetItem(text)
        item.setToolTip(text)
        self.table.setItem(row, col, item)

    def _refilter(self):
        if self._plan is None:
            return
        want = self.cmb_filter.currentData()
        needle = self.edit_filter.text().strip().lower()
        for row in range(self.table.rowCount()):
            entry = self._plan.entries[row]
            show = ((want == "__all__" or entry.domain == want)
                    and (not needle or needle in entry.target.lower()))
            self.table.setRowHidden(row, not show)

    # ------------------------------------------------------------- actions

    def _checked(self):
        rows = []
        for row in range(self.table.rowCount()):
            if self.table.isRowHidden(row):
                continue
            item = self.table.item(row, 0)
            if (isinstance(item, _Ck)
                    and item.checkState() == Qt.CheckState.Checked):
                rows.append(row)
        return rows

    def _check_all(self):
        for row in range(self.table.rowCount()):
            if self.table.isRowHidden(row):
                continue
            item = self.table.item(row, 0)
            if isinstance(item, _Ck):
                entry = self._plan.entries[row]
                if not entry.blocked:
                    item.setCheckState(Qt.CheckState.Checked)

    def _uncheck_all(self):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if isinstance(item, _Ck):
                item.setCheckState(Qt.CheckState.Unchecked)

    def _apply(self):
        if self._running or self._plan is None:
            return
        rows = self._checked()
        if not rows:
            info(self, t("diff.title"), t("market.apply_none"))
            return
        planned = []
        for row in rows:
            entry = self._plan.entries[row]
            if entry.blocked:
                continue
            text = self.table.item(row, 4).text().strip().replace(",", ".")
            try:
                value = float(text)
            except ValueError:
                continue
            entry.new_value = value
            if entry.kind in ("minmax", "ecf_param"):
                # la cellule 'nouvelle' est le MAX : le MIN calcule par le
                # plan est conserve (sinon 10-20 x1.5 corrige a 40 donnait
                # 40-40, un min ecrase) ; min <= max garanti
                entry.new_max_raw = int(round(value))
                if entry.new_min_raw > entry.new_max_raw:
                    entry.new_min_raw = entry.new_max_raw
            else:
                entry.new_min_raw = entry.new_max_raw = int(round(value))
            planned.append(entry)
        if not planned:
            info(self, t("diff.title"), t("market.apply_none"))
            return
        if not ask_yes_no(self, t("diff.title"),
                          t("diff.apply_confirm", n=len(planned))):
            return
        self._running = True
        self.btn_apply.setEnabled(False)
        before = {}
        for entry in planned:
            if entry.path not in before:
                before[entry.path] = entry.path.read_text(
                    encoding="utf-8", errors="replace")

        def work():
            applied = apply_entries(planned)
            save_undo_snapshot(before)   # annulation qui survit a la fermeture
            return applied

        def _done(done):
            self._running = False
            self.btn_apply.setEnabled(True)
            self._undo = list(before.items())
            self.btn_undo.setEnabled(True)
            self._refresh_backups()
            info(self, t("diff.title"),
                 t("diff.applied", files=len(done),
                   n=sum(done.values())))

        async_call(self, work, on_done=_done, on_fail=self._on_fail,
                   name="difficulty-apply")

    def _undo_apply(self):
        if not self._undo:
            return
        if not ask_yes_no(self, t("diff.title"), t("diff.undo_confirm")):
            return
        from core.fsutil import atomic_write_text, central_backup
        for path, text in self._undo:
            central_backup(path, "difficulty_undo")
            atomic_write_text(path, text)
        self._undo = []
        self.btn_undo.setEnabled(False)
        info(self, t("diff.title"), t("diff.undone"))

    # ------------------------------------------- restauration d'une passe

    def _refresh_backups(self):
        self.cmb_backups.clear()
        snapshots = list_undo_snapshots()
        self.cmb_backups.addItems([s.name for s in reversed(snapshots)])

    def _restore_snapshot(self):
        """Remonte une application archivee sur disque (survit a la
        fermeture du dialogue, contrairement a Annuler)."""
        if self._running:
            return
        name = self.cmb_backups.currentText()
        if not name:
            return
        if not ask_yes_no(self, t("diff.title"),
                          t("diff.restore_confirm", name=name)):
            return
        self._running = True
        self.btn_restore.setEnabled(False)
        snap = undo_backup_root() / name

        async_call(self, lambda: restore_undo_snapshot(snap),
                   on_done=self._restore_done, on_fail=self._on_fail,
                   name="difficulty-restore")

    def _restore_done(self, result):
        self._running = False
        self.btn_restore.setEnabled(True)
        restored, safety_dir = result
        info(self, t("diff.title"),
             t("diff.restored", n=restored, safety=safety_dir))
        self._refresh_backups()
