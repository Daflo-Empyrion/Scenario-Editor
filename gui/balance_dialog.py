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

"""Equilibrage du scenario en un clic (conception : MODULE_EQUILIBRAGE.md,
demande du 24/09/2026) : regles avec politiques (conserve / vanille /
plafond), APERCU MODIFIABLE des changements proposes, application avec
backups, undo espace de travail et rechargement des onglets ouverts."""
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QLabel,
                             QPushButton, QDoubleSpinBox, QTreeWidget,
                             QTreeWidgetItem, QVBoxLayout)

from core.balance_rules import (POLICIES, RULE_CATALOG, BalanceConfig,
                                apply_proposals, load_inventory,
                                propose_changes)
from core.i18n import t
from gui.window_geometry import track


class BalanceDialog(QDialog):
    """Etape 1 : regles + politiques ; Etape 2 : apercu coche des
    changements ; application atomique avec backups et undo."""

    def __init__(self, main_window, parent=None):
        from PyQt6.QtWidgets import QWidget
        qt_parent = parent if isinstance(parent, QWidget) else (
            main_window if isinstance(main_window, QWidget) else None)
        super().__init__(qt_parent)
        self.setWindowTitle(t("balance.title"))
        self.main_window = main_window
        self._inv = None
        self._proposals = []
        track(self, "balance", (900, 620))
        self._build_ui()

    # ------------------------------------------------------------- interface

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(t("balance.intro")))

        row = QHBoxLayout()
        row.addWidget(QLabel(t("balance.preset_label")))
        self.combo_preset = QComboBox()
        self.combo_preset.addItem(t("balance.preset_custom"))
        self.combo_preset.addItem(t("balance.preset_vanille"))
        self.combo_preset.currentIndexChanged.connect(self._apply_preset)
        row.addWidget(self.combo_preset, 1)
        lay.addLayout(row)

        # regles groupees, dans une zone defilante (24 proprietes)
        from PyQt6.QtWidgets import QScrollArea, QWidget
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        form = QVBoxLayout(inner)
        form.setSpacing(2)
        self._rule_policies = {}
        self._rule_values = {}
        current_group = None
        for spec in RULE_CATALOG:
            if spec.group != current_group:
                current_group = spec.group
                gl = QLabel(t(current_group))
                gl.setStyleSheet("font-weight: 700; margin-top: 6px;")
                form.addWidget(gl)
            rrow = QHBoxLayout()
            lbl = QLabel(spec.key)
            lbl.setMinimumWidth(190)
            rrow.addWidget(lbl)
            combo = QComboBox()
            for pol in POLICIES:
                combo.addItem(t(f"balance.policy_{pol}"), pol)
            combo.setCurrentIndex(0)
            rrow.addWidget(combo, 1)
            spin = QDoubleSpinBox()
            spin.setDecimals(2)
            spin.setGroupSeparatorShown(True)
            spin.setMaximum(1_000_000_000)
            spin.setValue(spec.plafond)
            sync = self._make_rule_sync(spec, combo, spin)
            combo.currentIndexChanged.connect(sync)
            sync()
            rrow.addWidget(spin)
            form.addLayout(rrow)
            self._rule_policies[spec.key] = combo
            self._rule_values[spec.key] = spin
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)

        self.btn_analyze = QPushButton(t("epb.analyze"))
        self.btn_analyze.setObjectName("primaryButton")
        self.btn_analyze.clicked.connect(self._analyze)
        lay.addWidget(self.btn_analyze)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([t("balance.col_file"),
                                   t("balance.col_block"),
                                   t("balance.col_prop"),
                                   t("balance.col_old"),
                                   t("balance.col_new")])
        self.tree.setColumnWidth(0, 220)
        self.tree.setColumnWidth(1, 240)
        self.tree.setColumnWidth(2, 160)
        self.tree.setColumnWidth(3, 90)
        lay.addWidget(self.tree, 1)

        self.status_label = QLabel("")
        lay.addWidget(self.status_label)

        bottom = QHBoxLayout()
        self.btn_apply = QPushButton(t("balance.apply"))
        self.btn_apply.setObjectName("primaryButton")
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self._apply)
        bottom.addWidget(self.btn_apply, 1)
        self.btn_close = QPushButton(t("btn.close"))
        self.btn_close.clicked.connect(self.reject)
        bottom.addWidget(self.btn_close)
        lay.addLayout(bottom)

    def _make_rule_sync(self, spec, combo, spin):
        """Le spin sert de PLAFOND ou de POURCENTAGE selon la politique ;
        sa valeur est reinitialisee a un defaut sensible au changement."""
        def sync(*_args):
            pol = combo.currentData()
            spin.setEnabled(pol in ("plafond", "pourcentage"))
            if pol == "plafond":
                spin.setValue(spec.plafond)
            elif pol == "pourcentage":
                spin.setValue(100.0)
        return sync

    def _apply_preset(self, index: int):
        if index == 1:                       # retour aux valeurs vanille
            for combo in self._rule_policies.values():
                combo.setCurrentIndex(combo.findData("vanille"))

    def _current_config(self) -> BalanceConfig:
        cfg = BalanceConfig()
        for rule, combo in self._rule_policies.items():
            cfg.policies[rule] = combo.currentData()
            cfg.plafonds[rule] = self._rule_values[rule].value()
            cfg.pourcentages[rule] = self._rule_values[rule].value()
        return cfg

    # ------------------------------------------------------------- analyse

    def _paths(self):
        from core.settings import get_vanilla_content_path
        ws = self.main_window.workspace if self.main_window else None
        vanilla = get_vanilla_content_path() or ""
        van = str(Path(vanilla) / "Configuration") if vanilla else ""
        scen = str(Path(ws.working_root) / "Content" / "Configuration") \
            if ws else ""
        return van, scen

    def _analyze(self):
        """Inventaire + propositions, hors thread GUI (gerbe plasma > 1 s)."""
        from gui.busy import run_long
        van, scen = self._paths()
        if not scen:
            self.status_label.setText(t("balance.no_project"))
            return
        cfg = self._current_config()
        self.tree.clear()
        self._inv, self._proposals = run_long(
            self, lambda: self._compute(van, scen, cfg))
        for pr in self._proposals:
            item = QTreeWidgetItem([pr.path.name, f"{pr.block} ({pr.block_id})",
                                    pr.prop, pr.old, pr.new])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Checked)
            item.setData(0, Qt.ItemDataRole.UserRole, pr)
            self.tree.addTopLevelItem(item)
        self.btn_apply.setEnabled(bool(self._proposals))
        self.status_label.setText(
            t("balance.found", n=len(self._proposals))
            if self._proposals else t("balance.none"))

    @staticmethod
    def _compute(van, scen, cfg):
        inv = load_inventory([van], [scen])
        return inv, propose_changes(inv, cfg)

    # ------------------------------------------------------------- application

    def _checked(self):
        out = []
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item.checkState(0) == Qt.CheckState.Checked:
                out.append(item.data(0, Qt.ItemDataRole.UserRole))
        return out

    def _apply(self):
        """Capture undo par fichier, ecriture atomique avec .bak, undo
        espace de travail, rechargement des onglets ouverts."""
        from core.workspace_undo import FileStateUndo, capture_file
        from gui.busy import run_long
        from gui.msgboxes import info
        items = self._checked()
        if not items:
            return
        paths = sorted({it.path for it in items})
        priors = {p: capture_file(p) for p in paths}
        done = run_long(self, lambda: apply_proposals(items))
        for path, n in done.items():
            undo = FileStateUndo(
                path, priors[path],
                t("balance.undo_label", file=Path(path).name))
            if self.main_window is not None:
                self.main_window._push_workspace_undo(undo)
                self.main_window._reload_tab_if_open_and_unmodified(path)
        self.btn_apply.setEnabled(False)
        self.status_label.setText(
            t("balance.done", f=len(done),
              n=sum(done.values())) if done else t("balance.none"))
        info(self, t("balance.done_title"),
             t("balance.done_msg", f=len(done), n=sum(done.values())))
