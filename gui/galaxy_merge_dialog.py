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
        self.btn_sectors = QPushButton(t("galaxy.sectors_action"))
        self.btn_sectors.clicked.connect(self._merge_sectors)
        bottom.addWidget(self.btn_sectors)
        self.btn_close = QPushButton(t("btn.close"))
        self.btn_close.clicked.connect(self.reject)
        bottom.addWidget(self.btn_close)
        lay.addLayout(bottom)

        if self.working_path is None:
            self.btn_analyze.setEnabled(False)
            self.status_label.setText(t("galaxy.need_project"))
        self._update_sectors_button()

    def _sectors_pair(self):
        """(working Sectors.yaml, source Sectors.yaml) si les deux
        existent, sinon (None, None)."""
        ws = getattr(self.main_window, "workspace", None) if \
            self.main_window else None
        if ws is None or not getattr(ws, "working_root", None):
            return None, None
        w = Path(ws.working_root) / "Sectors" / "Sectors.yaml"
        s = self._source_root() / "Sectors" / "Sectors.yaml"
        if w.exists() and s.exists():
            return w, s
        return None, None

    def _update_sectors_button(self):
        w, s = self._sectors_pair()
        self.btn_sectors.setEnabled(w is not None)

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

    # ------------------------------------------------- fusion Sectors.yaml

    def _merge_sectors(self):
        """Fusion STRUCTURELLE du Sectors.yaml de la source (moteur
        core/sectors_merge.py deja existant) : systemes entiers, secteurs
        par coordonnees, lignes de playfield — proposes cochables, inserts
        dans le Sectors.yaml du working, JAMAIS d'ecrasement. Plus les
        dossiers Playfields/<Type> references par les unites importees."""
        from core.sectors_merge import (analyze_sectors_merge,
                                        collect_playfield_type_deps,
                                        drop_duplicate_playfields,
                                        find_duplicate_playfields)
        from gui.busy import run_long
        from gui.msgboxes import info
        working_sectors, source_sectors = self._sectors_pair()
        if working_sectors is None:
            return
        ws = self.main_window.workspace
        units = run_long(self, lambda: analyze_sectors_merge(
            working_sectors, source_sectors))
        duplicates = run_long(self, lambda: find_duplicate_playfields(
            working_sectors))
        deps, missing = ([], [])
        identical = []
        if units:
            deps, missing, identical = run_long(
                self, lambda: collect_playfield_type_deps(
                    working_sectors, source_sectors, units,
                    working_root=ws.working_root,
                    source_root=self._source_root()))
        if not units and not deps and not duplicates:
            info(self, t("galaxy.sectors_title"), t("galaxy.sectors_none"))
            return
        dlg = SectorsUnitsDialog(units, deps, missing, duplicates,
                                 parent=self)
        if not dlg.exec():
            return
        checked = dlg.checked_units()
        checked_deps = dlg.checked_deps()
        fix_dups = (dlg.chk_fix_dups is not None
                    and dlg.chk_fix_dups.isChecked())
        if not checked and not checked_deps and not fix_dups:
            return
        from core.sectors_merge import (apply_structural_units,
                                        copy_playfield_type_deps)
        from core.workspace_undo import FileStateUndo, capture_file
        prior = capture_file(working_sectors)
        applied = run_long(self, lambda: apply_structural_units(
            working_sectors, checked, source_sectors))
        copied = run_long(self, lambda: copy_playfield_type_deps(
            checked_deps, ws.working_root))
        dups_fixed, dups_details = (run_long(
            self, lambda: drop_duplicate_playfields(working_sectors))
            if fix_dups and duplicates else (0, []))
        if applied:
            # backup CENTRAL : jamais de .bak a cote du fichier, le jeu
            # charge tous les .yaml du dossier Sectors/ (vecu 02/10)
            from core.fsutil import central_backup
            central_backup(working_sectors)
            if self.main_window is not None:
                self.main_window._push_workspace_undo(FileStateUndo(
                    working_sectors, prior,
                    t("galaxy.sectors_undo", n=applied)))
                reload_tab = getattr(
                    self.main_window,
                    "_reload_tab_if_open_and_unmodified", None)
                if reload_tab:
                    reload_tab(working_sectors)
        msg = t("galaxy.done_sectors", n=applied)
        if copied:
            msg += " " + t("galaxy.done_pf", n=copied)
        if dups_fixed:
            msg += " " + t("galaxy.done_dups", n=dups_fixed)
        info(self, t("galaxy.sectors_title"), msg)


def _all_indexed_keys(indexed_add) -> set:
    """Toutes les cles indexees d'un plan DEJA filtre par cochage."""
    return {f"{family}|{ib.index}"
            for family, lst in indexed_add.items() for ib in lst}


class SectorsUnitsDialog(QDialog):
    """Revue cochable des unites STRUCTURELLES du Sectors.yaml source
    (systemes entiers, secteurs par coordonnees, lignes de playfield) +
    dossiers Playfields/<Type> a copier — moteur core/sectors_merge.py,
    meme principe que la fenetre de fusion de dossier. OK = retourne les
    unites et deps cochees."""

    def __init__(self, units, deps=(), missing=(), duplicates=None,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("galaxy.sectors_title"))
        self.setMinimumSize(760, 480)
        self.chk_fix_dups = None
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(t("galaxy.sectors_hint", n=len(units))))
        if duplicates:
            lay.addWidget(QLabel(t("galaxy.sectors_dups_warn",
                                   n=len(duplicates))))
            for pf, systems in sorted(duplicates.items()):
                it = QLabel(t("galaxy.sectors_dup_item", pf=pf,
                              systems=", ".join(systems)))
                it.setWordWrap(True)
                lay.addWidget(it)
            from PyQt6.QtWidgets import QCheckBox
            self.chk_fix_dups = QCheckBox(t("galaxy.sectors_fix_dups"))
            self.chk_fix_dups.setChecked(True)
            lay.addWidget(self.chk_fix_dups)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([t("galaxy.sectors_col_kind"),
                                   t("galaxy.sectors_col_unit"),
                                   t("galaxy.sectors_col_coords")])
        self.tree.setColumnWidth(0, 140)
        self.tree.setColumnWidth(1, 420)
        # vecu 04/10 : l'arbre n'etait JAMAIS ajoute au layout — la fenetre
        # s'affichait vide (le contenu existait, invisible pour l'usage)
        lay.addWidget(self.tree, 1)
        for unit in units:
            kind_label = t("mergeplan.struct_system") \
                if unit.kind == "system" \
                else (t("mergeplan.struct_sector")
                      if unit.kind == "sector"
                      else t("mergeplan.struct_playfield"))
            coords = unit.coordinates
            if unit.conflict:
                # playfield(s) deja presents dans le working : DECOCHEE
                # par defaut ; l'application exclura les secteurs en
                # doublon de toute facon (double securite)
                coords = (t("galaxy.sectors_conflict", pf=unit.conflict)
                          + ("\n" + coords if coords else ""))
            item = QTreeWidgetItem([kind_label,
                                    f"{unit.name}  ·  {unit.system}",
                                    coords])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Unchecked if unit.conflict
                               else Qt.CheckState.Checked)
            if unit.conflict:
                item.setToolTip(2, t("galaxy.sectors_conflict_tip",
                                     pf=unit.conflict))
            item.setData(0, Qt.ItemDataRole.UserRole, unit)
            self.tree.addTopLevelItem(item)
        self._deps_items = []
        if deps:
            g = QTreeWidgetItem(["", t("galaxy.group_pf_deps"), ""])
            g.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.tree.addTopLevelItem(g)
            for dep in deps:
                item = QTreeWidgetItem(
                    ["", t("galaxy.pf_dep_label", name=dep.name),
                     t("galaxy.pf_dep_detail")])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Checked)
                item.setData(0, Qt.ItemDataRole.UserRole, dep)
                g.addChild(item)
                self._deps_items.append(item)
        if missing:
            g = QTreeWidgetItem(["", t("galaxy.group_pf_missing"), ""])
            g.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.tree.addTopLevelItem(g)
            for name in missing:
                it = QTreeWidgetItem(
                    ["", name, t("galaxy.pf_missing_detail")])
                it.setFlags(Qt.ItemFlag.ItemIsEnabled)
                it.setToolTip(2, t("galaxy.pf_missing_tip", name=name))
                g.addChild(it)
        self.tree.expandAll()
        buttons = QHBoxLayout()
        btn_ok = QPushButton(t("galaxy.sectors_apply"))
        btn_ok.setObjectName("primaryButton")
        btn_ok.clicked.connect(self.accept)
        buttons.addWidget(btn_ok, 1)
        btn_cancel = QPushButton(t("btn.cancel"))
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_cancel)
        lay.addLayout(buttons)

    def checked_units(self):
        out = []
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            if (it.flags() & Qt.ItemFlag.ItemIsUserCheckable
                    and it.checkState(0) == Qt.CheckState.Checked):
                data = it.data(0, Qt.ItemDataRole.UserRole)
                if data is not None and not isinstance(data, str):
                    out.append(data)
        return out

    def checked_deps(self):
        return [it.data(0, Qt.ItemDataRole.UserRole)
                for it in self._deps_items
                if it.checkState(0) == Qt.CheckState.Checked]
