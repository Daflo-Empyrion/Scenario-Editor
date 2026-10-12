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

"""Bilan « avant lancement » : les points qui font echouer le chargement du
scenario par le jeu — structure Sectors (doublons, fichiers etrangers,
systemes sans soleil, playfields absents) + prefabs introuvables + moteur
yaml/ecf (tools/yamlcheck). Regroupe les resultats dans un arbre ; détail
des regles dans core/launch_check.py. Scan hors thread GUI."""
from __future__ import annotations

import csv
import datetime
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (QCheckBox, QDialog, QFileDialog, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QTreeWidget,
                             QTreeWidgetItem, QVBoxLayout)

from core.i18n import t
from core.launch_check import LaunchIssue, run_launch_checks
from core.settings import get_production_scenario_path, get_vanilla_content_path
from gui.ewa_async import async_call
from gui.window_geometry import track


class LaunchCheckDialog(QDialog):
    """Scan complet « pre-lancement » d'un scenario (travail + production)."""

    def __init__(self, parent, working_root: str = ""):
        super().__init__(parent)
        self.setWindowTitle(t("launchcheck.title"))
        self._running = False

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

        self.chk_production = QCheckBox(t("yamlcheck.production"))
        self.chk_production.toggled.connect(self._sync_production_path)
        self.path_edit.textChanged.connect(self._sync_production_path)
        lay.addWidget(self.chk_production)

        # test REEL : boot du serveur dedie sur le scenario installe
        # (1-3 min, ports et sauvegarde jetables)
        self.chk_dedi = QCheckBox(t("launchcheck.dedi"))
        self.chk_dedi.setToolTip(t("launchcheck.dedi.tip"))
        self.chk_dedi.toggled.connect(self._sync_dedi_box)
        self.path_edit.textChanged.connect(self._sync_dedi_box)
        lay.addWidget(self.chk_dedi)

        self.btn_run = QPushButton(t("launchcheck.run"))
        self.btn_run.clicked.connect(self._run)
        lay.addWidget(self.btn_run)

        buttons = QHBoxLayout()
        self.btn_export = QPushButton(t("launchcheck.export"))
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._export_csv)
        buttons.addWidget(self.btn_export)
        buttons.addStretch(1)
        lay.addLayout(buttons)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([t("yamlcheck.col_file"),
                                   t("launchcheck.col_severity"),
                                   t("launchcheck.col_check"),
                                   t("yamlcheck.col_error")])
        self.tree.setColumnWidth(0, 300)
        self.tree.setColumnWidth(1, 90)
        self.tree.setColumnWidth(2, 80)
        lay.addWidget(self.tree, 1)

        self.status_label = QLabel("")
        lay.addWidget(self.status_label)
        self._sync_production_path()

        track(self, "launch_check", (820, 480))

    # ------------------------------------------------------------- parcours

    def _production_path(self) -> str:
        root = self.path_edit.text().strip()
        if not root:
            return ""
        return get_production_scenario_path(root) or ""

    def _sync_production_path(self) -> None:
        self.chk_production.setEnabled(bool(self._production_path()))

    def _sync_dedi_box(self) -> None:
        """Le test dédié ne peut viser que le scenario INSTALLE (le moteur
        charge Content/Scenarios) : actif si une production est connue."""
        from core.dedi_boot_check import dedi_exe
        from core.settings import get_vanilla_content_path
        vanilla = get_vanilla_content_path() or ""
        exe_ok = bool(vanilla) and dedi_exe(Path(vanilla).parent).is_file()
        self.chk_dedi.setEnabled(bool(self._production_path()) and exe_ok)

    def _pick_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, t("yamlcheck.scenario"), self.path_edit.text() or ".")
        if path:
            self.path_edit.setText(path)

    # ---------------------------------------------------------------- scan

    def _run(self):
        if self._running:
            return
        if not self.path_edit.text().strip():
            self.status_label.setText(t("yamlcheck.need_scenario"))
            return
        self._running = True
        self.btn_run.setEnabled(False)
        self.tree.clear()
        self.status_label.setText(t("launchcheck.running"))
        # captures AVANT le thread (regle projet : jamais de widget lu dans
        # le worker) ; la vanille sert aux prefabs et templates de playfields
        roots = [self.path_edit.text().strip()]
        if self.chk_production.isChecked():
            prod = self._production_path()
            if prod:
                roots.append(prod)
        vanilla = get_vanilla_content_path() or ""
        dedi_checked = self.chk_dedi.isEnabled() and self.chk_dedi.isChecked()
        prod_path = self._production_path()
        from core.yaml_game_check import ensure_checker, run_yaml_check

        def work():
            issues: list[LaunchIssue] = []
            findings = []
            scanned = 0
            for root in roots:
                issues.extend(run_launch_checks(root, vanilla))
            # moteur du jeu (yaml + ecf) : si l'outil est absent, le bilan
            # structurel reste rendu — le statut dira que le moteur a ete saute
            engine_ok = True
            try:
                checker = ensure_checker()
            except Exception:       # noqa: BLE001 - outil optionnel ici
                engine_ok = False
            if engine_ok:
                for root in roots:
                    for mode in ("yaml", "ecf"):
                        f, n = run_yaml_check(checker, [root], mode=mode)
                        findings.extend(f)
                        scanned += n
            return issues, findings, scanned, engine_ok

        async_call(self, work,
                   # le signal livre UN tuple : le slot direct planquerait
                   # (TypeError avalé par le garde ewa_async, dialogue bloqué
                   # en « en cours » — vecu au premier smoke 11/10)
                   on_done=lambda res: self._on_done_phase1(res, dedi_checked,
                                                            prod_path),
                   on_fail=self._on_fail,
                   name="launch-check")

    def _on_done_phase1(self, res, dedi_checked: bool, prod_path: str):
        """Debrief de la phase 1 (structure + moteur), puis phase 2 :
        boot dedie reel si la case est cochee (le scenario INSTALLE)."""
        self._on_done(res[0], res[1], res[2], res[3])
        if dedi_checked and prod_path:
            self._running = True
            self.btn_run.setEnabled(False)
            self._start_dedi_phase(prod_path)

    def _start_dedi_phase(self, prod_path: str):
        """Phase 2 : boot REEL du dedi sur le scenario installe (sauvegarde
        jetable, ports 33xxx, config -dedicated jetable)."""
        vanilla = get_vanilla_content_path() or ""
        game_root = str(Path(vanilla).parent)
        scenario_name = Path(prod_path).name
        from core.dedi_boot_check import run_dedi_boot_check
        self._dedi_progress = {"line": ""}
        self._dedi_timer = QTimer(self)
        self._dedi_timer.setInterval(700)

        def _tick():
            last = self._dedi_progress.get("line", "")
            if last:
                self.status_label.setText(t("launchcheck.dedi.phase", s=last))

        self._dedi_timer.timeout.connect(_tick)
        self._dedi_timer.start()

        def dedi_work():
            return run_dedi_boot_check(
                game_root, scenario_name, timeout_s=300.0,
                progress=lambda s: self._dedi_progress.__setitem__("line", s))

        async_call(self, dedi_work,
                   on_done=self._on_dedi_done,
                   on_fail=lambda e: (self._stop_dedi_timer(),
                                      self._on_fail(e)),
                   name="dedi-boot")

    def _stop_dedi_timer(self):
        timer = getattr(self, "_dedi_timer", None)
        if timer is not None:
            timer.stop()

    def _on_dedi_done(self, result):
        self._stop_dedi_timer()
        self._running = False
        self.btn_run.setEnabled(True)
        sev_error = t("launchcheck.sev_error")
        sev_warning = t("launchcheck.sev_warning")
        head = QTreeWidgetItem([
            t("launchcheck.dedi.row", s=f"{result.seconds:.0f}",
              n=result.playfields),
            sev_error if not result.ready else sev_warning,
            t("launchcheck.check_engine"),
            "" if result.ready else t("launchcheck.dedi.not_ready"),
        ])
        self.tree.addTopLevelItem(head)
        for line in result.issues:
            item = QTreeWidgetItem([result.log_path, sev_warning,
                                    t("launchcheck.check_engine"), line])
            item.setToolTip(3, line)
            self.tree.addTopLevelItem(item)
        if result.ready:
            self.status_label.setText(t("launchcheck.dedi.ok",
                                        s=f"{result.seconds:.0f}",
                                        n=result.playfields,
                                        l=result.log_path))
        else:
            self.status_label.setText(t("launchcheck.dedi.failed",
                                        l=result.log_path))
        self.btn_export.setEnabled(self.tree.topLevelItemCount() > 0)

    def _on_done(self, issues: list[LaunchIssue], findings, scanned: int,
                 engine_ok: bool):
        self._running = False
        self.btn_run.setEnabled(True)
        sev_error = t("launchcheck.sev_error")
        sev_warning = t("launchcheck.sev_warning")
        checks = {"sectors": t("launchcheck.check_sectors"),
                  "playfields": t("launchcheck.check_playfields"),
                  "prefabs": t("launchcheck.check_prefabs")}
        n_errors = 0
        for issue in issues:
            is_error = issue.severity == "error"
            n_errors += is_error
            item = QTreeWidgetItem([
                f"{issue.path}" + (f":{issue.line}" if issue.line else ""),
                sev_error if is_error else sev_warning,
                checks.get(issue.check, issue.check),
                issue.message,
            ])
            item.setToolTip(3, issue.message)
            self.tree.addTopLevelItem(item)
        for f in findings:
            n_errors += 1
            item = QTreeWidgetItem([f.rel_path, sev_error,
                                    t("launchcheck.check_engine"), f.message])
            item.setToolTip(3, f.message)
            self.tree.addTopLevelItem(item)
        total = len(issues) + len(findings)
        if total:
            self.status_label.setText(t("launchcheck.done", i=total,
                                        e=n_errors, n=scanned))
        else:
            self.status_label.setText(t("launchcheck.all_ok", n=scanned)
                                      if engine_ok else t("launchcheck.all_ok_noengine"))
        self.btn_export.setEnabled(self.tree.topLevelItemCount() > 0)
        if not engine_ok and total:
            self.status_label.setText(self.status_label.text()
                                      + "  " + t("launchcheck.noengine"))

    def _export_csv(self):
        """Export des resultats affiches (arbre complet, les deux phases)
        en CSV point-virgule UTF-8 BOM (ouvrable directement dans Excel)."""
        if not self.tree.topLevelItemCount():
            return
        base_dir = self.path_edit.text().strip() or str(Path.home())
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
        suggested = str(Path(base_dir) / f"bilan_lancement_{stamp}.csv")
        out, _ = QFileDialog.getSaveFileName(self, t("launchcheck.export"),
                                             suggested, "CSV (*.csv)")
        if not out:
            return
        with open(out, "w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh, delimiter=";")
            writer.writerow(t("launchcheck.csv_headers").split(";"))
            for i in range(self.tree.topLevelItemCount()):
                item = self.tree.topLevelItem(i)
                writer.writerow([item.text(c) for c in range(4)])
        self.status_label.setText(t("launchcheck.csv_done", path=out))

    def _on_fail(self, exc: Exception):
        self._running = False
        self.btn_run.setEnabled(True)
        self.status_label.setText(f"{t('yamlcheck.failed')}  ({exc})")
