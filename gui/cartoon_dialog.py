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
"""Look « cartoon » : preset visuel data (terrain.ecf + ciels des
playfields), apercu des couleurs origine vs preset, application +
synchro production, restauration des passes sauvegardees
(core/cartoon_look.py)."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
                             QFileDialog, QGridLayout, QHBoxLayout, QLabel,
                             QLineEdit, QMessageBox, QPlainTextEdit,
                             QPushButton, QScrollArea, QVBoxLayout, QWidget)

from core.cartoon_look import (DEFAULT_PRESET, PRESET_SPECS, list_backups,
                               load_stored_preset, preview_colors,
                               restore_backup, run_preset, save_preset)
from core.i18n import t
from gui.ewa_async import async_call
from gui.module_info import add_info_button
from gui.window_geometry import track

_PREVIEW_MAX = 20
_SWATCH_CSS = ("background-color: rgb({r},{g},{b}); min-width: 56px; "
               "min-height: 14px; max-height: 14px; border: 1px solid #666")

# cle -> (libelle i18n, decimales, pas du spinbox)
_PRESET_UI = {
    "saturation": ("cartoon.f_saturation", 2, 0.1),
    "smoothness_cap": ("cartoon.f_smoothness", 2, 0.05),
    "normal": ("cartoon.f_normal", 2, 0.05),
    "relief": ("cartoon.f_relief", 2, 0.05),
    "rgb_spread": ("cartoon.f_rgb", 2, 0.1),
    "sky_saturation": ("cartoon.f_skysat", 2, 0.1),
    "sky_brightness": ("cartoon.f_skybright", 2, 0.01),
    "fog_intensity": ("cartoon.f_fog", 2, 0.05),
}


def _swatch(text: str) -> QWidget:
    """Nuance de couleur pour une valeur « r, g, b » ou « (r, g, b) » ;
    libelle texte si la valeur n'est pas une couleur affichable."""
    try:
        nums = [float(x) for x in text.strip('()').split(',')]
        if len(nums) != 3:
            raise ValueError
        r, g, b = (max(0.0, min(1.0, v)) for v in nums)
        label = QLabel()
        label.setStyleSheet(_SWATCH_CSS.format(r=int(r * 255),
                                               g=int(g * 255),
                                               b=int(b * 255)))
        label.setToolTip(text)
        return label
    except ValueError:
        return QLabel(text)


class CartoonDialog(QDialog):
    """Preset visuel cartoon : couleurs origine vs preset, application +
    synchro, restauration des passes."""
    def __init__(self, parent, working_root: str = ""):
        super().__init__(parent)
        self.setWindowTitle(t("cartoon.title"))
        self._running = False
        self._backup_paths: dict = {}

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

        self.force_box = QCheckBox(t("cartoon.force"))
        lay.addWidget(self.force_box)

        lay.addWidget(QLabel(t("cartoon.preset")))
        preset_grid = QGridLayout()
        self.preset_spins: dict = {}
        for idx, (key, (label_key, dec, step)) in enumerate(
                _PRESET_UI.items()):
            dflt, lo, hi = PRESET_SPECS[key]
            spin = QDoubleSpinBox()
            spin.setRange(lo, hi)
            spin.setSingleStep(step)
            spin.setDecimals(dec)
            spin.setValue(dflt)
            spin.setToolTip(t(label_key + ".tip"))
            self.preset_spins[key] = spin
            preset_grid.addWidget(QLabel(t(label_key)), idx // 2, (idx % 2) * 2)
            preset_grid.addWidget(spin, idx // 2, (idx % 2) * 2 + 1)
        lay.addLayout(preset_grid)

        buttons = QHBoxLayout()
        self.btn_preview = QPushButton(t("cartoon.preview"))
        self.btn_preview.clicked.connect(self._preview)
        buttons.addWidget(self.btn_preview)
        self.btn_apply = QPushButton(t("cartoon.apply"))
        self.btn_apply.clicked.connect(self._apply)
        buttons.addWidget(self.btn_apply)
        self.btn_defaults = QPushButton(t("cartoon.preset_defaults"))
        self.btn_defaults.clicked.connect(
            lambda: self._set_preset(DEFAULT_PRESET))
        buttons.addWidget(self.btn_defaults)
        buttons.addStretch(1)
        add_info_button(buttons, "cartoon.info_html")
        lay.addLayout(buttons)

        self.status_label = QLabel("")
        lay.addWidget(self.status_label)

        lay.addWidget(QLabel(t("cartoon.colors")))
        self.pf_combo = QComboBox()
        self.pf_combo.currentIndexChanged.connect(self._refresh_colors)
        lay.addWidget(self.pf_combo)
        grid = QGridLayout()
        for col, key in enumerate(("cartoon.col_property", "cartoon.col_origin",
                                   "cartoon.col_new")):
            grid.addWidget(QLabel(t(key)), 0, col)
        lay.addLayout(grid)
        self.colors_area = QScrollArea()
        self.colors_area.setWidgetResizable(True)
        colors_box = QWidget()
        self.colors_grid = QGridLayout(colors_box)
        self.colors_grid.setContentsMargins(4, 2, 4, 2)
        self.colors_area.setWidget(colors_box)
        lay.addWidget(self.colors_area, 1)

        restore_row = QHBoxLayout()
        restore_row.addWidget(QLabel(t("cartoon.backups")))
        self.backup_combo = QComboBox()
        restore_row.addWidget(self.backup_combo, 1)
        self.btn_restore = QPushButton(t("cartoon.restore"))
        self.btn_restore.clicked.connect(self._restore)
        restore_row.addWidget(self.btn_restore)
        lay.addLayout(restore_row)

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        lay.addWidget(self.preview, 1)

        track(self, "cartoon_look", (820, 640))
        if working_root:
            self._refresh_meta()

    # -- preset (facteurs editables) ---------------------------------------

    def _capture_preset(self) -> dict:
        return {key: spin.value() for key, spin in self.preset_spins.items()}

    def _set_preset(self, preset: dict) -> None:
        for key, value in preset.items():
            spin = self.preset_spins.get(key)
            if spin is not None:
                spin.setValue(value)

    # -- meta (liste playfields + passes sauvegardees) --------------------

    def _refresh_meta(self) -> None:
        if self._running:
            return
        scenario = self.path_edit.text().strip()

        def _load():
            names = []
            pfs = Path(scenario) / "Playfields"
            if pfs.is_dir():
                from core.cartoon_look import TARGET_NAMES
                for pf in sorted(p for p in pfs.iterdir()
                                 if p.is_dir() and not p.name.startswith('+')):
                    if any((pf / n).is_file() for n in TARGET_NAMES):
                        names.append(pf.name)
            backups = {b.name: str(b) for b in list_backups()}
            return names, backups, load_stored_preset()

        async_call(self, _load, on_done=self._meta_done, name="cartoon-meta")

    def _meta_done(self, result) -> None:
        names, backups, preset = result
        self.pf_combo.blockSignals(True)
        self.pf_combo.clear()
        self.pf_combo.addItems(names)
        self.pf_combo.blockSignals(False)
        self._backup_paths = backups
        self.backup_combo.clear()
        self.backup_combo.addItems(sorted(backups))
        self._set_preset(preset)
        if names:
            self._refresh_colors()

    # -- apercu des couleurs ----------------------------------------------

    def _refresh_colors(self) -> None:
        scenario = self.path_edit.text().strip()
        pf = self.pf_combo.currentText()
        if not scenario or not pf:
            return
        preset = self._capture_preset()
        async_call(self, lambda: preview_colors(scenario, pf, preset),
                   on_done=self._colors_done, name="cartoon-colors")

    def _colors_done(self, rows: dict) -> None:
        while self.colors_grid.count():
            item = self.colors_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        entries = [("ciel", rows.get("ciel", [])),
                   ("terrain", rows.get("terrain", []))]
        grid_row = 0
        for section, items in entries:
            if not items:
                continue
            self.colors_grid.addWidget(
                QLabel(t("cartoon.section_" + section)), grid_row, 0)
            grid_row += 1
            for label, old, new in items[:_PREVIEW_MAX]:
                self.colors_grid.addWidget(QLabel(label), grid_row, 0)
                self.colors_grid.addWidget(_swatch(old), grid_row, 1)
                self.colors_grid.addWidget(_swatch(new), grid_row, 2)
                grid_row += 1
            if len(items) > _PREVIEW_MAX:
                self.colors_grid.addWidget(
                    QLabel(t("cartoon.more").format(n=len(items)
                                                    - _PREVIEW_MAX)),
                    grid_row, 0)
                grid_row += 1
        if grid_row == 0:
            self.colors_grid.addWidget(QLabel(t("cartoon.colors_none")), 0, 0)

    # -- preset : previsualisation et application --------------------------

    def _pick_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, t("yamlcheck.scenario"), self.path_edit.text() or ".")
        if path:
            self.path_edit.setText(path)
            self._refresh_meta()

    def _launch(self, dry_run: bool) -> None:
        if self._running:
            return
        if not self.path_edit.text().strip():
            self.status_label.setText(t("digest.need_scenario"))
            return
        self._running = True
        self.btn_preview.setEnabled(False)
        self.btn_apply.setEnabled(False)
        self.btn_restore.setEnabled(False)
        self.status_label.setText(t("cartoon.running"))
        scenario = self.path_edit.text().strip()
        force = self.force_box.isChecked() and not dry_run
        preset = self._capture_preset()

        def _worker():
            if not dry_run:
                save_preset(preset)     # reglage persiste a l'application
            return run_preset(scenario, dry_run=dry_run, force=force,
                              preset=preset)

        async_call(self, _worker,
                   on_done=self._done, on_fail=self._fail,
                   name="cartoon-look")

    def _preview(self) -> None:
        self._launch(dry_run=True)

    def _apply(self) -> None:
        self._launch(dry_run=False)

    def _restore(self) -> None:
        name = self.backup_combo.currentText()
        if self._running or not name:
            return
        backup_dir = self._backup_paths.get(name, "")
        if not backup_dir:
            return
        answer = QMessageBox.question(
            self, t("cartoon.restore"),
            t("cartoon.confirm_restore").format(name=name))
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._running = True
        self.btn_preview.setEnabled(False)
        self.btn_apply.setEnabled(False)
        self.btn_restore.setEnabled(False)
        self.status_label.setText(t("cartoon.running"))
        scenario = self.path_edit.text().strip()
        async_call(self, lambda: restore_backup(scenario, backup_dir),
                   on_done=self._restore_done, on_fail=self._fail,
                   name="cartoon-restore")

    def _finish_turn(self) -> None:
        self._running = False
        self.btn_preview.setEnabled(True)
        self.btn_apply.setEnabled(True)
        self.btn_restore.setEnabled(True)

    def _done(self, rep: dict) -> None:
        self._finish_turn()
        if rep.get("error"):
            self.status_label.setText(t("cartoon.missing"))
            return
        if rep.get("marker_blocked"):
            self.status_label.setText(t("cartoon.blocked"))
            return
        touched = rep["touched"]
        lines = [f"+ {rel}  ({n})" for rel, n in touched[:_PREVIEW_MAX]]
        rest = len(touched) - len(lines)
        if rest > 0:
            lines.append(f"+ … ({rest})")
        for line in rep["invalid"][:_PREVIEW_MAX]:
            lines.append(f"! {line}")
        self.preview.setPlainText("\n".join(lines))
        if rep.get("dry_run"):
            self.status_label.setText(
                t("cartoon.dry").format(n=len(touched), total=rep["total"]))
            return
        status = t("cartoon.done").format(n=len(touched), total=rep["total"],
                                          backup=rep["backup_dir"])
        if rep.get("invalid"):
            status += " " + t("cartoon.invalid").format(n=len(rep["invalid"]))
        if rep.get("prod"):
            status += " " + t("cartoon.synced").format(
                copied=rep["copied"], bins=rep["bins"])
        else:
            status += " " + t("cartoon.noprod")
        self.status_label.setText(status)
        self._refresh_meta()

    def _restore_done(self, rep: dict) -> None:
        self._finish_turn()
        if rep.get("error"):
            self.status_label.setText(t("cartoon.backup_missing"))
            return
        status = t("cartoon.restored").format(n=rep["copied"])
        if rep.get("prod"):
            status += " " + t("cartoon.synced").format(
                copied=rep["copied"], bins=rep["bins"])
        else:
            status += " " + t("cartoon.noprod")
        status += " " + t("cartoon.marker_removed")
        self.status_label.setText(status)
        self._refresh_meta()
        self._refresh_colors()

    def _fail(self, exc: Exception) -> None:
        self._finish_turn()
        self.status_label.setText(f"{type(exc).__name__}: {exc}")
