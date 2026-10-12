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

"""Verification « avant lancement » : parse les *.yaml d'un scenario avec le
MOTEUR DU JEU (tools/yamlcheck, YamlDotNet embarque d'Empyrion) et liste les
fichiers qui feraient planter le chargement — vecu 11/10 : descriptions
playfield avec guillemets non echappes, planetes de depart disparues en jeu
sans autre message que « did not find expected key » dans le log client.
Scan hors du thread GUI via gui.ewa_async.async_call."""
from __future__ import annotations

from PyQt6.QtWidgets import (QCheckBox, QDialog, QFileDialog, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QTreeWidget,
                             QTreeWidgetItem, QVBoxLayout)

from core.i18n import t
from core.settings import get_production_scenario_path
from core.yaml_game_check import (YamlCheckError, YamlFinding, ensure_checker,
                                  run_yaml_check)
from gui.ewa_async import async_call
from gui.window_geometry import track


class YamlCheckDialog(QDialog):
    """Scan « moteur de jeu » d'un scenario : copie de travail (+ production
    en option) -> fichiers en erreur avec ligne/colonne et message exact."""

    def __init__(self, parent, working_root: str = ""):
        super().__init__(parent)
        self.setWindowTitle(t("yamlcheck.title"))
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

        # production : ressuscitee depuis les settings a chaque edition du
        # chemin (la cle est indexee par working_root)
        self.chk_production = QCheckBox(t("yamlcheck.production"))
        self.chk_production.toggled.connect(self._sync_production_path)
        self.path_edit.textChanged.connect(self._sync_production_path)
        lay.addWidget(self.chk_production)

        self.btn_run = QPushButton(t("yamlcheck.run"))
        self.btn_run.clicked.connect(self._run)
        lay.addWidget(self.btn_run)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([t("yamlcheck.col_file"),
                                   t("yamlcheck.col_line"),
                                   t("yamlcheck.col_col"),
                                   t("yamlcheck.col_error")])
        self.tree.setColumnWidth(0, 340)
        self.tree.setColumnWidth(1, 70)
        self.tree.setColumnWidth(2, 50)
        lay.addWidget(self.tree, 1)

        self.status_label = QLabel("")
        lay.addWidget(self.status_label)
        self._sync_production_path()

        track(self, "yaml_check", (780, 480))

    # ------------------------------------------------------------- parcours

    def _production_path(self) -> str:
        root = self.path_edit.text().strip()
        if not root:
            return ""
        return get_production_scenario_path(root) or ""

    def _sync_production_path(self) -> None:
        self.chk_production.setEnabled(bool(self._production_path()))

    def _pick_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, t("yamlcheck.scenario"), self.path_edit.text() or ".")
        if path:
            self.path_edit.setText(path)

    # ---------------------------------------------------------------- scan

    def _scan_dirs(self) -> list[str]:
        dirs = [self.path_edit.text().strip()]
        if self.chk_production.isChecked():
            prod = self._production_path()
            if prod:
                dirs.append(prod)
        return [d for d in dirs if d]

    def _run(self):
        if self._running:
            return
        if not self.path_edit.text().strip():
            self.status_label.setText(t("yamlcheck.need_scenario"))
            return
        self._running = True
        self.btn_run.setEnabled(False)
        self.tree.clear()
        self.status_label.setText(t("yamlcheck.running"))
        # captures AVANT le thread (regle projet : jamais de widget lu dans
        # le worker) ; le build eventuel de l'outil (dotnet) y passe aussi
        scan_dirs = self._scan_dirs()

        def work():
            try:
                checker = ensure_checker()
            except YamlCheckError as exc:
                raise RuntimeError(str(exc)) from exc
            findings: list[YamlFinding] = []
            scanned = 0
            # les DEUX familles en un clic : *.yaml au moteur du jeu,
            # *.ecf a la validation structurelle calibree corpus
            for mode in ("yaml", "ecf"):
                f, n = run_yaml_check(checker, scan_dirs, mode=mode)
                findings.extend(f)
                scanned += n
            return findings, scanned

        async_call(self, work,
                   on_done=lambda res: self._on_done(res[0], res[1]),
                   on_fail=self._on_fail, name="yaml-game-check")

    def _on_done(self, findings: list[YamlFinding], scanned: int):
        self._running = False
        self.btn_run.setEnabled(True)
        for f in findings:
            item = QTreeWidgetItem([f.rel_path, str(f.line), str(f.col),
                                    f.message])
            item.setToolTip(3, f.message)
            self.tree.addTopLevelItem(item)
        if findings:
            self.status_label.setText(t("yamlcheck.done", n=scanned,
                                        e=len(findings)))
        else:
            self.status_label.setText(t("yamlcheck.all_ok", n=scanned))

    def _on_fail(self, exc: Exception):
        self._running = False
        self.btn_run.setEnabled(True)
        self.status_label.setText(f"{t('yamlcheck.failed')}  ({exc})")
