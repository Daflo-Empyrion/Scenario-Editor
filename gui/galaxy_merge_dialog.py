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

"""Fenetre de fusion SPECIALISEE GalaxyConfig (demande du 01/10/2026) :
apercu cochable des systemes a ajouter (apparies par Name + StarClass)
et des dependances a copier, General du working prioritaire avec diff
informatif, avertissements Sectors/playfields. Application via
core/galaxy_merge.py (idempotent, .bak)."""
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton,
                             QTreeWidget, QTreeWidgetItem, QVBoxLayout)

from core.i18n import t
from gui.window_geometry import track

_ROLE_BLOCK = "block"
_ROLE_DEP = "dep"
_ROLE_INDEXED = "indexed"
_ROLE_GENERAL = "general"
_ROLE_FACTION = "faction"
_ROLE_EGROUP = "egroup"


class GalaxyMergeDialog(QDialog):
    """Clic droit sur un GalaxyConfig.ecf source (scenario A ou B)."""

    def __init__(self, main_window, source_path: Path):
        from PyQt6.QtWidgets import QWidget
        qt_parent = (main_window
                     if isinstance(main_window, QWidget) else None)
        super().__init__(qt_parent)
        self.setWindowTitle(t("galaxy.title"))
        self.main_window = main_window
        self.source_path = Path(source_path)
        self.working_path = None
        self._plan = None
        ws = getattr(main_window, "workspace", None) if main_window else None
        if ws is not None and getattr(ws, "working_root", None):
            self.working_path = (Path(ws.working_root)
                                 / "Content/Configuration/GalaxyConfig.ecf")
        track(self, "galaxy_merge", (860, 620))
        self._build_ui()

    # ------------------------------------------------------------- interface

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(t("galaxy.intro")))
        lay.addWidget(QLabel(t("galaxy.working") + " "
                             + str(self.working_path or "-")))
        lay.addWidget(QLabel(t("galaxy.source") + " "
                             + str(self.source_path)))

        self.btn_analyze = QPushButton(t("galaxy.analyze"))
        self.btn_analyze.setObjectName("primaryButton")
        self.btn_analyze.clicked.connect(self._analyze)
        lay.addWidget(self.btn_analyze)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([t("galaxy.col_item"),
                                   t("galaxy.col_detail")])
        self.tree.setColumnWidth(0, 380)
        lay.addWidget(self.tree, 1)

        self.status_label = QLabel("")
        lay.addWidget(self.status_label)

        bottom = QHBoxLayout()
        self.btn_apply = QPushButton(t("galaxy.apply"))
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
        from core.galaxy_merge import build_plan
        src_root = self._source_root()
        return build_plan(self.working_path, self.source_path,
                          working_root=self.main_window.workspace.working_root,
                          source_root=src_root)

    def _source_root(self) -> Path:
        """Racine du scenario SOURCE (celle qui contient RandomPresets et
        Playfields) : .../Content/Configuration/ -> parent.parent.parent,
        avec repli Configuration/ a la racine."""
        cfg = self.source_path.parent
        for root in (cfg.parent.parent, cfg.parent):
            if (root / "RandomPresets").is_dir() or (root / "Playfields") \
                    .is_dir():
                return root
        return cfg.parent.parent

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
            g = _group(t("galaxy.group_add"))
            for b in plan.blocks_add:
                detail = (f"StarClass: {b.star_class}" if b.star_class
                          else "sans StarClass")
                if b.solar_suffix:
                    detail += f"  |  preset: {b.solar_suffix}"
                item = QTreeWidgetItem([b.name, detail])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Checked)
                item.setData(0, Qt.ItemDataRole.UserRole,
                             (_ROLE_BLOCK, b.key))
                g.addChild(item)
            self.tree.expandAll()
        if plan.indexed_add:
            g = _group(t("galaxy.group_indexed"))
            for family, lst in plan.indexed_add.items():
                for ib in lst:
                    item = QTreeWidgetItem(
                        [f"Child {family}_{ib.index}",
                         t("galaxy.indexed_detail")])
                    item.setFlags(item.flags()
                                  | Qt.ItemFlag.ItemIsUserCheckable)
                    item.setCheckState(0, Qt.CheckState.Checked)
                    item.setData(0, Qt.ItemDataRole.UserRole,
                                 (_ROLE_INDEXED, f"{family}|{ib.index}"))
                    g.addChild(item)
        if plan.factions_to_import:
            g = _group(t("galaxy.group_factions"))
            for f in plan.factions_to_import:
                item = QTreeWidgetItem([f.name, t("galaxy.faction_detail")])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Checked)
                item.setData(0, Qt.ItemDataRole.UserRole,
                             (_ROLE_FACTION, f.name))
                g.addChild(item)
        if plan.egroups_to_import:
            g = _group(t("galaxy.group_egroups"))
            for e in plan.egroups_to_import:
                item = QTreeWidgetItem([e.name, t("galaxy.egroup_detail")])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Checked)
                item.setData(0, Qt.ItemDataRole.UserRole,
                             (_ROLE_EGROUP, e.name))
                g.addChild(item)
        if plan.blocks_same:
            g = _group(t("galaxy.group_same"))
            for key in plan.blocks_same:
                it = QTreeWidgetItem([key.split("|")[0], key.split("|")[1]])
                it.setFlags(Qt.ItemFlag.ItemIsEnabled)
                g.addChild(it)
        if plan.deps:
            g = _group(t("galaxy.group_deps"))
            for d in plan.deps:
                item = QTreeWidgetItem([d.relative, d.reason])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Checked)
                item.setData(0, Qt.ItemDataRole.UserRole,
                             (_ROLE_DEP, d.relative))
                g.addChild(item)
        if plan.general_diff:
            g = _group(t("galaxy.group_general"))
            for prop, wv, sv in plan.general_diff:
                item = QTreeWidgetItem([prop, f"{wv}   <-   {sv}"])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Unchecked)  # working gagne
                item.setData(0, Qt.ItemDataRole.UserRole,
                             (_ROLE_GENERAL, prop))
                g.addChild(item)
        warns = ([t("galaxy.warn_sector", name=n)
                  for n in plan.sector_warnings]
                 + [t("galaxy.warn_playfield", name=n)
                    for n in plan.playfields_absent]
                 + [t("galaxy.warn_warfare", name=n)
                    for n in plan.warfare_warnings]
                 + [t("galaxy.warn_unknown_faction", name=n)
                    for n in plan.factions_unknown]
                 + [t("galaxy.warn_limit", lim=l) for l in plan.indexed_limits])
        if warns:
            g = _group(t("galaxy.group_warn"))
            for wtext in warns:
                it = QTreeWidgetItem([wtext, ""])
                it.setFlags(Qt.ItemFlag.ItemIsEnabled)
                g.addChild(it)
        self.tree.expandAll()

        n_add = (len(plan.blocks_add) + len(plan.deps)
                 + sum(len(v) for v in plan.indexed_add.values())
                 + len(plan.factions_to_import)
                 + len(plan.egroups_to_import))
        self.status_label.setText(
            t("galaxy.none") if n_add == 0 else
            t("galaxy.done", b=len(plan.blocks_add), d=len(plan.deps)))
        self.btn_apply.setEnabled(n_add > 0)

    # ------------------------------------------------------------- application

    def _checked(self):
        """Sets coches par role : (blocks, deps, indexed, general,
        factions, egroups). General DECOCHE par defaut : le working
        gagne."""
        out = {role: set() for role in
               (_ROLE_BLOCK, _ROLE_DEP, _ROLE_INDEXED, _ROLE_GENERAL,
                _ROLE_FACTION, _ROLE_EGROUP)}
        for i in range(self.tree.topLevelItemCount()):
            g = self.tree.topLevelItem(i)
            for j in range(g.childCount()):
                it = g.child(j)
                data = it.data(0, Qt.ItemDataRole.UserRole)
                if not data or it.checkState(0) != Qt.CheckState.Checked:
                    continue
                role, key = data
                if role in out:
                    out[role].add(key)
        return out

    def _apply(self):
        import copy as _copy
        from gui.busy import run_long
        from gui.msgboxes import info
        checked = self._checked()
        plan = self._plan
        if plan is None:
            return
        # FILTRAGE par cochage : deps, blocs indexes, factions (copie
        # superficielle du plan ; General passe par general_props)
        plan_apply = _copy.copy(plan)
        plan_apply.deps = [d for d in plan.deps
                           if d.relative in checked[_ROLE_DEP]]
        plan_apply.indexed_add = {
            family: [ib for ib in lst
                     if f"{family}|{ib.index}" in checked[_ROLE_INDEXED]]
            for family, lst in plan.indexed_add.items()}
        plan_apply.factions_to_import = [
            f for f in plan.factions_to_import
            if f.name in checked[_ROLE_FACTION]]
        plan_apply.egroups_to_import = [
            e for e in plan.egroups_to_import
            if e.name in checked[_ROLE_EGROUP]]
        stats = run_long(
            self, lambda: self._do_apply(checked[_ROLE_BLOCK],
                                         checked[_ROLE_GENERAL],
                                         plan_apply))
        if self.main_window is not None:
            self.main_window._push_workspace_undo(self._make_undo())
            reload_tab = getattr(self.main_window,
                                 "_reload_tab_if_open_and_unmodified", None)
            if reload_tab:
                reload_tab(self.working_path)
        self.status_label.setText(
            t("galaxy.done", b=stats["blocks"], d=stats["deps"]))
        info(self, t("galaxy.done_title"),
             t("galaxy.done", b=stats["blocks"], d=stats["deps"])
             + "\n\n" + t("galaxy.savegame_note"))
        self._analyze()

    def _do_apply(self, blocks, general_props, plan_apply):
        from core.galaxy_merge import apply_plan
        # blocks est un set : VIDE = tout decoche -> rien a ecrire
        # (jamais `blocks or None`, qui re-cocherait tout)
        return apply_plan(plan_apply, self.working_path,
                          working_root=self.main_window.workspace.working_root,
                          block_keys=blocks,
                          copy_deps=bool(plan_apply.deps),
                          indexed_keys=_all_indexed_keys(
                              plan_apply.indexed_add),
                          general_props=general_props or None)

    def _make_undo(self):
        from core.workspace_undo import FileStateUndo, capture_file
        return FileStateUndo(
            self.working_path, capture_file(self.working_path),
            t("balance.undo_label",
              file=Path(self.working_path).name))


def _all_indexed_keys(indexed_add) -> set:
    """Toutes les cles indexees d'un plan DEJA filtre par cochage."""
    return {f"{family}|{ib.index}"
            for family, lst in indexed_add.items() for ib in lst}
