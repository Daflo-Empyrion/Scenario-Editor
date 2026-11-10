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

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (QCheckBox, QDialog, QFileDialog, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QTreeWidget,
                             QTreeWidgetItem, QVBoxLayout)

from core.i18n import t
from core.launch_check import LaunchIssue, run_launch_checks
from core.playfield_sweep import sweep_playfields
from core.settings import get_production_scenario_path, get_vanilla_content_path
from gui.ewa_async import async_call
from gui.module_info import add_info_button
from gui.msgboxes import ask_yes_no, info
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
        # coche par defaut : c'est le SEUL test qui charge vraiment le
        # scenario, et il ne prend qu'une minute (le bilan seul ne prouvait
        # rien du chargement — vecu 05/11 : bloc manquant invisible)
        self.chk_dedi.setChecked(True)
        self.chk_dedi.toggled.connect(self._sync_dedi_box)
        self.path_edit.textChanged.connect(self._sync_dedi_box)
        lay.addWidget(self.chk_dedi)

        self.btn_run = QPushButton(t("launchcheck.run"))
        self.btn_run.clicked.connect(self._run)
        lay.addWidget(self.btn_run)

        # recherche des prefabs inutilises : nettoyage de la distribution,
        # sans rapport avec le chargement — donc un bouton a part, pas une
        # ligne du bilan (le bilan doit rester vide quand tout va bien)
        self.btn_unused = QPushButton(t("launchcheck.unused_btn"))
        self.btn_unused.setToolTip(t("launchcheck.unused_tip"))
        self.btn_unused.clicked.connect(self._scan_unused)
        lay.addWidget(self.btn_unused)

        # nettoyage complet : .bak, caches .yaml.bin orphelins, compagnons de
        # prefabs disparus (SURS) et images non citees (A VERIFIER)
        self.btn_junk = QPushButton(t("launchcheck.junk_btn"))
        self.btn_junk.setToolTip(t("launchcheck.junk_tip"))
        self.btn_junk.clicked.connect(self._scan_junk)
        lay.addWidget(self.btn_junk)

        # corbeille : cocher les lignes a retirer, sauvegarde centralisee
        # avant toute suppression (jamais de *.bak dans Prefabs/ : le jeu le
        # chargerait comme un blueprint)
        self.btn_trash = QPushButton(t("launchcheck.trash_btn"))
        self.btn_trash.setToolTip(t("launchcheck.trash_tip"))
        self.btn_trash.setEnabled(False)
        self.btn_trash.clicked.connect(self._trash_checked)
        lay.addWidget(self.btn_trash)

        buttons = QHBoxLayout()
        self.btn_export = QPushButton(t("launchcheck.export"))
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._export_csv)
        buttons.addWidget(self.btn_export)
        add_info_button(buttons, "launchcheck.info_html")
        buttons.addStretch(1)
        lay.addLayout(buttons)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([t("yamlcheck.col_file"),
                                   t("launchcheck.col_severity"),
                                   t("launchcheck.col_check"),
                                   t("yamlcheck.col_error"),
                                   t("launchcheck.col_fix")])
        self.tree.setColumnWidth(0, 300)
        self.tree.setColumnWidth(1, 90)
        self.tree.setColumnWidth(2, 80)
        self.tree.setColumnWidth(4, 220)
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
        """Le moteur ne charge que Content/Scenarios : la copie de travail
        est installee dans un dossier jetable le temps du boot."""
        from core.dedi_boot_check import dedi_exe
        from core.settings import get_vanilla_content_path
        vanilla = get_vanilla_content_path() or ""
        exe_ok = bool(vanilla) and dedi_exe(Path(vanilla).parent).is_file()
        self.chk_dedi.setEnabled(bool(self.path_edit.text().strip()) and exe_ok)

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
        dedi_root = self.path_edit.text().strip()
        from core.yaml_game_check import ensure_checker, run_yaml_check

        def work():
            issues: list[LaunchIssue] = []
            findings = []
            scanned = 0
            for root in roots:
                issues.extend(run_launch_checks(root, vanilla))
                # balayage par planete (prefabs cites + blocs de leurs tables
                # IdMapping) : ce que le boot dedie ne voit PAS — il ne charge
                # que les secteurs, aucun playfield n'est instancie avant
                # qu'un joueur n'y entre.
                issues.extend(sweep_playfields(Path(root)))
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
                                                            dedi_root),
                   on_fail=self._on_fail,
                   name="launch-check")

    def _on_done_phase1(self, res, dedi_checked: bool, dedi_root: str):
        """Debrief de la phase 1 (structure + moteur), puis phase 2 :
        boot dedie reel si la case est cochee (copie de travail installee
        temporairement sous Content/Scenarios)."""
        self._on_done(res[0], res[1], res[2], res[3])
        if dedi_checked and dedi_root:
            self._running = True
            self.btn_run.setEnabled(False)
            self._start_dedi_phase(dedi_root)

    def _start_dedi_phase(self, source_root: str):
        """Phase 2 : boot REEL du dedi sur la COPIE DE TRAVAIL copiee dans
        un dossier jetable de Content/Scenarios (sauvegarde jetable, ports
        33xxx, config -dedicated jetable, copie supprimee ensuite)."""
        vanilla = get_vanilla_content_path() or ""
        game_root = str(Path(vanilla).parent)
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
                game_root, "", timeout_s=300.0, source_root=source_root,
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
                  "prefabs": t("launchcheck.check_prefabs"),
                  "plane": t("launchcheck.check_plane"),
                  "poi_groups": t("launchcheck.check_poi_groups"),
                  "spawn": t("launchcheck.check_spawn"),
                  "warfare": t("launchcheck.check_warfare"),
                  "pda": t("launchcheck.check_pda"),
                  "scripts": t("launchcheck.check_scripts"),
                  "tokens": t("launchcheck.check_tokens"),
                  "dialogues": t("launchcheck.check_dialogues"),
                  "conflict": t("launchcheck.check_conflict")}
        n_errors = 0
        for issue in issues:
            is_error = issue.severity == "error"
            n_errors += is_error
            item = QTreeWidgetItem([
                f"{issue.path}" + (f":{issue.line}" if issue.line else ""),
                sev_error if is_error else sev_warning,
                checks.get(issue.check, issue.check),
                issue.message,
                issue.fix,
            ])
            item.setToolTip(3, issue.message)
            item.setToolTip(4, issue.fix)
            self.tree.addTopLevelItem(item)
        for f in findings:
            n_errors += 1
            item = QTreeWidgetItem([f.rel_path, sev_error,
                                    t("launchcheck.check_engine"), f.message, ""])
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
                writer.writerow([item.text(c) for c in range(5)])
        self.status_label.setText(t("launchcheck.csv_done", path=out))

    def _on_fail(self, exc: Exception):
        self._running = False
        self.btn_run.setEnabled(True)
        self.status_label.setText(f"{t('yamlcheck.failed')}  ({exc})")

    def _scan_unused(self):
        """Prefabs du scenario cites NULLE PART (ni nom de fichier, ni Name
        interne, ni tag) : candidats au menage avant distribution. Regle
        volontairement conservatrice (un faux positif ferait supprimer un
        prefab utilise) — voir core/prefab_usage.py."""
        root = self.path_edit.text().strip()
        if not root:
            self.status_label.setText(t("yamlcheck.need_scenario"))
            return
        if self._running:
            return
        self._running = True
        self.btn_run.setEnabled(False)
        self.btn_unused.setEnabled(False)
        self.tree.clear()
        self.status_label.setText(t("launchcheck.unused_running"))

        from core.prefab_usage import scan_prefab_usage

        def work():
            return scan_prefab_usage(Path(root))

        async_call(self, work, on_done=self._on_unused_done,
                   on_fail=self._on_fail, name="unused-prefabs")

    def _on_unused_done(self, rapport):
        self._running = False
        self.btn_run.setEnabled(True)
        self.btn_unused.setEnabled(True)
        sev_info = t("launchcheck.sev_info")
        check = t("launchcheck.check_prefabs")
        for chemin, taille in rapport.unused:
            item = QTreeWidgetItem([
                f"Prefabs/{chemin.name}", sev_info, check,
                t("launchcheck.unused_row", ko=f"{taille / 1024:.0f}")])
            # decoche par defaut : la suppression reste un geste explicite
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Unchecked)
            item.setData(0, Qt.ItemDataRole.UserRole, str(chemin))
            item.setToolTip(0, str(chemin))
            self.tree.addTopLevelItem(item)
        self.btn_trash.setEnabled(bool(rapport.unused))
        if rapport.unused:
            self.status_label.setText(t(
                "launchcheck.unused_done", n=len(rapport.unused),
                mo=f"{rapport.unused_bytes / 1e6:.1f}",
                used=rapport.used, total=rapport.scanned))
        else:
            self.status_label.setText(t("launchcheck.unused_none",
                                        total=rapport.scanned))
        self.btn_export.setEnabled(self.tree.topLevelItemCount() > 0)

    def _scan_junk(self):
        """Fichiers inutiles du scenario : `.bak`, caches `*.yaml.bin`
        orphelins, compagnons de prefabs disparus (SURS) et images dont le nom
        n'est cite nulle part (A VERIFIER — le jeu peut les charger par
        convention, l'utilisateur tranche)."""
        root = self.path_edit.text().strip()
        if not root:
            self.status_label.setText(t("yamlcheck.need_scenario"))
            return
        if self._running:
            return
        self._running = True
        self.btn_run.setEnabled(False)
        self.btn_junk.setEnabled(False)
        self.tree.clear()
        self.status_label.setText(t("launchcheck.junk_running"))

        from core.scenario_cleanup import scan_junk

        def work():
            return scan_junk(Path(root))

        async_call(self, work, on_done=self._on_junk_done,
                   on_fail=self._on_fail, name="scenario-junk")

    def _on_junk_done(self, items):
        self._running = False
        self.btn_run.setEnabled(True)
        self.btn_junk.setEnabled(True)
        check = t("launchcheck.check_cleanup")
        for junk in items:
            etat = t("launchcheck.junk_safe") if junk.safe \
                else t("launchcheck.junk_check")
            item = QTreeWidgetItem([
                f"{junk.path.parent.name}/{junk.path.name}"
                if junk.path.parent != Path(self.path_edit.text().strip())
                else junk.path.name,
                etat, check,
                t("launchcheck.junk_row", cat=junk.category,
                  ko=f"{junk.octets / 1024:.0f}")])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            # les SURS sont pre-coches, les autres non : un fichier « a
            # verifier » ne doit jamais partir par une validation distraite
            item.setCheckState(0, Qt.CheckState.Checked if junk.safe
                               else Qt.CheckState.Unchecked)
            item.setData(0, Qt.ItemDataRole.UserRole, str(junk.path))
            item.setToolTip(0, str(junk.path))
            self.tree.addTopLevelItem(item)
        self.btn_trash.setEnabled(bool(items))
        surs = sum(1 for j in items if j.safe)
        self.status_label.setText(t(
            "launchcheck.junk_done", n=len(items), surs=surs,
            mo=f"{sum(j.octets for j in items) / 1e6:.1f}") if items
            else t("launchcheck.junk_none"))
        self.btn_export.setEnabled(self.tree.topLevelItemCount() > 0)

    def _checked_prefabs(self) -> list:
        """Chemins des lignes cochees (les seules concernables par la
        corbeille : un resultat de bilan n'a pas de case)."""
        coches = []
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item.checkState(0) != Qt.CheckState.Checked:
                continue
            chemin = item.data(0, Qt.ItemDataRole.UserRole)
            if chemin:
                coches.append((item, Path(chemin)))
        return coches

    def _trash_checked(self):
        """Sauvegarde centralisee puis suppression des prefabs coches et de
        leurs .decals/.jpg. Confirmation obligatoire, avec le total."""
        from core.scenario_cleanup import trash_files

        coches = self._checked_prefabs()
        if not coches:
            self.status_label.setText(t("launchcheck.trash_none"))
            return
        octets = sum(p.stat().st_size for _i, p in coches if p.exists())
        question = t("launchcheck.trash_confirm", n=len(coches),
                     mo=f"{octets / 1e6:.1f}",
                     dir=str(Path.home() / ".empyrion_editor" / "backups"))
        if not ask_yes_no(self, t("launchcheck.trash_btn"), question):
            return
        racine = Path(self.path_edit.text().strip() or ".")
        faits, echecs = trash_files([p for _i, p in coches],
                                    kind=f"nettoyage-{racine.name}")
        for item, chemin in coches:
            if not chemin.exists():
                idx = self.tree.indexOfTopLevelItem(item)
                if idx >= 0:
                    self.tree.takeTopLevelItem(idx)
        self.btn_trash.setEnabled(bool(self._checked_prefabs()))
        self.status_label.setText(t("launchcheck.trash_done", n=faits,
                                    e=len(echecs)))
        if echecs:
            info(self, t("launchcheck.trash_btn"), "\n".join(echecs[:10]))
