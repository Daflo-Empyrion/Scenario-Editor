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

"""Dialogue « reparations automatiques » : deux corrections mecaniques du
bilan F5, sans choix de contenu --

- reordonner les declarations ECF pour que chaque `Ref:` pointe une cible
  declaree AVANT (chargeur sequentiel du jeu) ;
- relever les UnlockLevel non croissants de l'arbre technologique (paliers
  reels du jeu, point fixe sur les enfants).

NON MODAL, analyse avant application, undo par fichier.
"""
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QPushButton,
    QVBoxLayout, QWidget,
)

from core.ecf.ref_order import apply_ref_order, plan_ref_order
from core.i18n import t
from core.tech_tree_levels import (apply_unlock_progression,
                                   plan_unlock_progression)
from core.workspace_undo import FileStateUndo, capture_file


class AutoRepairDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent or (main_window if isinstance(main_window, QWidget) else None))
        self.main_window = main_window
        self._ref_plans = []
        self._level_plan = None
        self.setWindowTitle(t("repair.title"))
        self.resize(720, 480)
        from gui.window_geometry import track
        track(self, "auto_repair")
        self._build_ui()
        self._analyse()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        intro = QLabel(t("repair.intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        layout.addWidget(self.report, 1)
        buttons = QHBoxLayout()
        self.btn_analyse = QPushButton(t("repair.analyse"))
        self.btn_analyse.clicked.connect(self._analyse)
        self.btn_apply = QPushButton(t("repair.apply"))
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self._apply)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_analyse)
        buttons.addWidget(self.btn_apply)
        layout.addLayout(buttons)

    def _paths(self):
        ws = getattr(self.main_window, "workspace", None)
        if ws is None:
            return None, None
        try:
            conf = ws.working.configuration
        except Exception:
            return None, None
        blocks = next((f.path for f in conf if f.path.name == "BlocksConfig.ecf"), None)
        items = next((f.path for f in conf if f.path.name == "ItemsConfig.ecf"), None)
        return blocks, items

    def _analyse(self):
        blocks, items = self._paths()
        if blocks is None and items is None:
            self.report.setPlainText(t("repair.no_ecf"))
            self.btn_apply.setEnabled(False)
            return
        self._ref_plans = [p for p in (plan_ref_order(f) for f in (blocks, items) if f)]
        try:
            self._level_plan = plan_unlock_progression(blocks, items)
        except Exception as e:
            self._level_plan = None
            self.report.setPlainText(str(e))
            self.btn_apply.setEnabled(False)
            return
        moves = sum(len(p.fixes) for p in self._ref_plans)
        cycles = sum(len(p.cycles) for p in self._ref_plans)
        levels = len(self._level_plan.fixes)
        self._market_plan = None
        try:
            from core.market_repair import plan_market_repair
            from core.settings import get_vanilla_content_path
            ws = getattr(self.main_window, "workspace", None)
            if ws is not None:
                self._market_plan = plan_market_repair(
                    ws.working_root, get_vanilla_content_path())
        except Exception:
            self._market_plan = None
        templates = len(self._market_plan.bad_templates) if self._market_plan else 0
        prices = len(self._market_plan.price_fixes) if self._market_plan else 0
        unresolved = len(self._market_plan.unresolved) if self._market_plan else 0
        lines = [t("repair.report", moves=moves, levels=levels)]
        if cycles:
            lines.append(t("repair.cycles", n=cycles))
        if self._market_plan is not None:
            lines.append(t("repair.market", templates=templates, prices=prices,
                           unresolved=unresolved))
        if not moves and not levels and not templates and not prices:
            lines.append(t("repair.nothing"))
        self.report.setPlainText("\n\n".join(lines))
        self.btn_apply.setEnabled(bool(moves or levels or templates or prices))

    def _apply(self):
        if self._level_plan is None:
            return
        moves = sum(len(p.fixes) for p in self._ref_plans)
        levels = len(self._level_plan.fixes)
        templates = len(self._market_plan.bad_templates) if self._market_plan else 0
        prices = len(self._market_plan.price_fixes) if self._market_plan else 0
        if QMessageBox.question(
                self, t("repair.title"),
                t("repair.confirm", moves=moves, levels=levels,
                  templates=templates, prices=prices)
        ) != QMessageBox.StandardButton.Yes:
            return
        touched = {}
        for plan in self._ref_plans:
            if plan.nothing_to_do:
                continue
            touched[Path(plan.path)] = capture_file(Path(plan.path))
        for fix in self._level_plan.fixes:
            touched.setdefault(Path(fix.path), capture_file(Path(fix.path)))
        if self._market_plan is not None and not self._market_plan.nothing_to_do:
            touched.setdefault(Path(self._market_plan.templates_path),
                               capture_file(Path(self._market_plan.templates_path)))
            if self._market_plan.price_fixes:
                from core.market_balance import load_index
                idx, _ = load_index(self._market_plan.root)
                for fix in self._market_plan.price_fixes:
                    od = idx.objs.get(fix.name)
                    if od is not None:
                        touched.setdefault(Path(od.final_path),
                                           capture_file(Path(od.final_path)))
        try:
            if self._market_plan is not None:
                from core.market_repair import apply_market_repair
                apply_market_repair(self._market_plan)
            for plan in self._ref_plans:
                apply_ref_order(plan)
            apply_unlock_progression(self._level_plan)
        except Exception as e:
            QMessageBox.critical(self, t("err.title"), str(e))
            return
        mw = self.main_window
        if mw is not None and getattr(mw, "workspace", None) is not None:
            for path, prior in touched.items():
                mw._push_workspace_undo(FileStateUndo(
                    path, prior, t("repair.undo_label", file=path.name)))
            mw.workspace.rescan_working()
            for path in touched:
                mw._reload_tab_if_open_and_unmodified(path)
            mw.statusBar().showMessage(
                t("repair.done", moves=moves, levels=levels,
                  templates=templates, prices=prices), 8000)
        self._analyse()
