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

"""GARDE-FOU fusion Sectors.yaml : la fusion YAML generique ne connait
PAS l'unicite globale des playfields (vecu 04/10 : « Duplicate playfield
name 'Zeyhines' » — fusion generique de Default Akua-Omicron dans
Vanilla EVO, 5 doublons, systemes importes tels quels). Tout ce qui
fusionne un Sectors.yaml passe donc ICI.

Demande 04/10 (retour utilisateur) : FUSION PLUS FINE — arbre
systeme -> secteur -> ligne de playfield cochenable a chaque niveau,
colonnes « ce qui change », application par sous-ensembles
(core.sectors_merge.apply_fine_selection)."""
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QLabel,
                             QPushButton, QTreeWidget, QTreeWidgetItem,
                             QVBoxLayout)

from core.i18n import t
from core.sectors_merge import (FineRequest, analyze_sectors_merge,
                                apply_fine_selection,
                                collect_playfield_type_deps,
                                copy_playfield_type_deps,
                                drop_duplicate_playfields,
                                find_broken_systems,
                                find_duplicate_playfields)


def is_sectors_yaml(path: Path) -> bool:
    """Le fichier est-il un Sectors.yaml (le nom porte la semantique, la
    fusion de dossier filtre pareil : rel.endswith('Sectors.yaml')) ?"""
    return Path(path).name.lower().endswith("sectors.yaml")


class SectorsFineDialog(QDialog):
    """Revue FINE de fusion Sectors : arbre systeme -> secteur -> ligne
    de playfield (colonne « Ce qui change »), coches tri-state avec
    propagation parent/enfants. Les entrees deja presentes dans la copie
    de travail sont GRISEES (exclues par le moteur, jamais un doublon).
    OK = retourne (selections(), checked_deps(), fix_dups)."""

    COL_TYPE, COL_NAME, COL_CHANGE, COL_COORDS = range(4)

    def __init__(self, units, deps=(), missing=(), duplicates=None,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("sectorsflow.title"))
        self.setMinimumSize(920, 560)
        self.chk_fix_dups = None
        self._building = True
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(t("fine.hint")))
        if duplicates:
            lay.addWidget(QLabel(t("galaxy.sectors_dups_warn",
                                   n=len(duplicates))))
            for pf, systems in sorted(duplicates.items()):
                it = QLabel(t("galaxy.sectors_dup_item", pf=pf,
                              systems=", ".join(systems)))
                it.setWordWrap(True)
                lay.addWidget(it)
            self.chk_fix_dups = QCheckBox(t("galaxy.sectors_fix_dups"))
            self.chk_fix_dups.setChecked(True)
            lay.addWidget(self.chk_fix_dups)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([t("fine.col_type"), t("fine.col_name"),
                                   t("fine.col_change"),
                                   t("galaxy.sectors_col_coords")])
        self.tree.setColumnWidth(self.COL_TYPE, 120)
        self.tree.setColumnWidth(self.COL_NAME, 240)
        self.tree.setColumnWidth(self.COL_CHANGE, 420)
        self.tree.header().setStretchLastSection(True)
        lay.addWidget(self.tree, 1)
        self._deps_items = []
        self._populate(units, deps, missing)
        for i in range(self.tree.topLevelItemCount()):
            self._init_branch(self.tree.topLevelItem(i))
        self.tree.expandAll()
        self.tree.itemChanged.connect(self._on_item_changed)
        self._building = False
        buttons = QHBoxLayout()
        btn_ok = QPushButton(t("galaxy.sectors_apply"))
        btn_ok.setObjectName("primaryButton")
        btn_ok.clicked.connect(self.accept)
        buttons.addWidget(btn_ok, 1)
        btn_cancel = QPushButton(t("btn.cancel"))
        btn_cancel.setObjectName("secondaryButton")
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_cancel)
        lay.addLayout(buttons)

    # ------------------------------------------------------------- arbre

    def _populate(self, units, deps, missing):
        system_units = {u.system: u for u in units if u.kind == "system"}
        sector_units = [u for u in units if u.kind == "sector"]
        row_units = [u for u in units if u.kind == "playfield"]
        rows_by_sec = {}
        for u in row_units:
            rows_by_sec.setdefault((u.system, u.coordinates), []).append(u)
        secs_by_sys = {}
        for u in sector_units:
            secs_by_sys.setdefault(u.system, []).append(u)
        order = []
        for u in units:
            if u.system not in order:
                order.append(u.system)

        for sname in order:
            sys_unit = system_units.get(sname)
            secs = secs_by_sys.get(sname, [])
            rows = [u for (s, _c), rus in rows_by_sec.items() if s == sname
                    for u in rus]
            if sys_unit is not None:
                detail = t("fine.system_detail", sec=len(secs), pf=len(rows))
                if sys_unit.conflict:
                    detail += " " + t("galaxy.sectors_conflict",
                                      pf=sys_unit.conflict)
                sys_item = QTreeWidgetItem([t("fine.kind_system"), sname,
                                            detail, ""])
                sys_item.setData(0, Qt.ItemDataRole.UserRole, sys_unit)
            else:
                sys_item = QTreeWidgetItem([t("fine.kind_system_group"),
                                            sname,
                                            t("fine.system_detail",
                                              sec=len(secs), pf=len(rows)),
                                            ""])
            sys_item.setFlags(sys_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            sys_item.setCheckState(0, Qt.CheckState.Checked)
            self.tree.addTopLevelItem(sys_item)

            for su in secs:
                kids = rows_by_sec.get((sname, su.coordinates), [])
                if kids:
                    detail = t("fine.sector_kids", n=len(kids))
                else:
                    detail = ", ".join(su.playfields)
                    if su.conflict:
                        detail += " " + t("galaxy.sectors_conflict",
                                          pf=su.conflict)
                sec_item = QTreeWidgetItem([t("fine.kind_sector"), sname,
                                            detail, su.coordinates])
                sec_item.setData(0, Qt.ItemDataRole.UserRole, su)
                sec_item.setFlags(sec_item.flags()
                                  | Qt.ItemFlag.ItemIsUserCheckable)
                sec_item.setCheckState(0, Qt.CheckState.Checked)
                for ru in kids:
                    sec_item.addChild(self._make_row_item(ru))
                sys_item.addChild(sec_item)
            # lignes d'un secteur DEJA present dans le working (pas d'unite
            # secteur proposee) : noeud secteur synthetique
            for (rsys, rcoords), rus in rows_by_sec.items():
                if rsys != sname:
                    continue
                if any(su.coordinates == rcoords for su in secs):
                    continue
                sec_item = QTreeWidgetItem(
                    [t("fine.kind_sector"), sname,
                     t("fine.sector_kids", n=len(rus)), rcoords])
                for ru in rus:
                    sec_item.addChild(self._make_row_item(ru))
                sys_item.addChild(sec_item)

        if deps:
            g = QTreeWidgetItem(["", t("galaxy.group_pf_deps"), "", ""])
            g.setFlags(Qt.ItemFlag.ItemIsEnabled)
            g.setData(0, Qt.ItemDataRole.UserRole, "deps_group")
            self.tree.addTopLevelItem(g)
            for dep in deps:
                item = QTreeWidgetItem(
                    ["", t("galaxy.pf_dep_label", name=dep.name),
                     t("galaxy.pf_dep_detail"), ""])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Checked)
                item.setData(0, Qt.ItemDataRole.UserRole, dep)
                g.addChild(item)
                self._deps_items.append(item)
        if missing:
            g = QTreeWidgetItem(["", t("galaxy.group_pf_missing"), "", ""])
            g.setFlags(Qt.ItemFlag.ItemIsEnabled)
            g.setData(0, Qt.ItemDataRole.UserRole, "missing_group")
            self.tree.addTopLevelItem(g)
            for name in missing:
                it = QTreeWidgetItem(["", name,
                                      t("galaxy.pf_missing_detail"), ""])
                it.setFlags(Qt.ItemFlag.ItemIsEnabled)
                it.setToolTip(self.COL_CHANGE,
                              t("galaxy.pf_missing_tip", name=name))
                g.addChild(it)

    def _make_row_item(self, u):
        if u.conflict:
            detail = t("fine.row_conflict")
            it = QTreeWidgetItem([t("fine.kind_row"), u.name, detail,
                                  u.coordinates])
            it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(0, Qt.CheckState.Unchecked)
            it.setToolTip(self.COL_CHANGE,
                          t("galaxy.sectors_conflict_tip", pf=u.conflict))
        else:
            detail = (t("fine.row_detail", type=u.playfield_types[0])
                      if u.playfield_types else "")
            it = QTreeWidgetItem([t("fine.kind_row"), u.name, detail,
                                  u.coordinates])
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(0, Qt.CheckState.Checked)
        it.setData(0, Qt.ItemDataRole.UserRole, u)
        return it

    def _init_branch(self, item):
        for i in range(item.childCount()):
            self._init_branch(item.child(i))
        if item.childCount():
            self._aggregate(item)

    def _enabled_children(self, item):
        out = []
        for i in range(item.childCount()):
            c = item.child(i)
            if c.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                out.append(c)
        return out

    def _aggregate(self, item):
        """Etat du parent derive de ses enfants activables : tout cochet =
        coche, rien = decoche, melange = partiel ; aucun enfant activable
        (tout conflictueux) = grise. Les noeuds sentinelles (groupes deps/
        missing, data = chaine) ne sont jamais requalifies."""
        if isinstance(item.data(0, Qt.ItemDataRole.UserRole), str):
            return
        kids = self._enabled_children(item)
        if not kids:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Unchecked)
            return
        states = {k.checkState(0) for k in kids}
        if states == {Qt.CheckState.Checked}:
            st = Qt.CheckState.Checked
        elif states == {Qt.CheckState.Unchecked}:
            st = Qt.CheckState.Unchecked
        else:
            st = Qt.CheckState.PartiallyChecked
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(0, st)

    def _on_item_changed(self, item, col):
        if self._building or col != self.COL_TYPE:
            return
        state = item.checkState(0)
        self._building = True
        try:
            if state != Qt.CheckState.PartiallyChecked:
                self._set_children_state(item, state)
            p = item.parent()
            while p is not None:
                self._aggregate(p)
                p = p.parent()
        finally:
            self._building = False

    def _set_children_state(self, item, state):
        for i in range(item.childCount()):
            c = item.child(i)
            if c.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                c.setCheckState(0, state)
                self._set_children_state(c, state)

    # -------------------------------------------------------- selection

    def selections(self):
        """Demandes fines pour apply_fine_selection : [(systeme,
        coordonnees, lignes|None)] — None = secteur entier. L'ordre de
        l'arbre (= ordre du document source) est conserve. Les noeuds
        non-unites (groupes deps marqués par une chaîne sentinelle,
        PlayfieldTypeDep sans .kind) sont ignorés."""
        groups = {}

        def walk(item):
            u = item.data(0, Qt.ItemDataRole.UserRole)
            kind = getattr(u, 'kind', None) if u is not None else None
            if kind == 'playfield':
                g = groups.setdefault((u.system, u.coordinates),
                                      {"enabled": [], "checked": []})
                g["enabled"].append(u.name)
                if item.checkState(0) == Qt.CheckState.Checked:
                    g["checked"].append(u.name)
            elif (kind == 'sector' and item.childCount() == 0):
                conflicted = ({n.strip().casefold()
                               for n in u.conflict.split(",")}
                              if u.conflict else set())
                g = groups.setdefault((u.system, u.coordinates),
                                      {"enabled": [], "checked": []})
                for nm in u.playfields:
                    if nm.casefold() in conflicted:
                        continue
                    g["enabled"].append(nm)
                    if item.checkState(0) == Qt.CheckState.Checked:
                        g["checked"].append(nm)
            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(self.tree.topLevelItemCount()):
            walk(self.tree.topLevelItem(i))
        reqs = []
        for (system, coords), g in groups.items():
            enabled = set(g["enabled"])
            if not enabled:
                continue
            if set(g["checked"]) >= enabled:
                reqs.append(FineRequest(system, coords, None))
            elif g["checked"]:
                reqs.append(FineRequest(system, coords, tuple(g["checked"])))
        return reqs

    def checked_deps(self):
        return [it.data(0, Qt.ItemDataRole.UserRole)
                for it in self._deps_items
                if it.checkState(0) == Qt.CheckState.Checked]


def open_sectors_merge(parent, main_window, working_yaml: Path,
                       source_yaml: Path, source_root=None) -> bool:
    """Fusion STRUCTURELLE FINE d'un Sectors.yaml source dans la copie de
    travail : arbre cochenable (systemes/secteurs/lignes), deps
    Playfields/<Type>, correction optionnelle des doublons preexistants,
    backup CENTRAL (jamais de .bak dans <scenario>/Sectors/), undo, scan
    post-application. Retourne True si quelque chose a ete modifie."""
    from gui.busy import run_long
    from gui.msgboxes import info

    ws = getattr(main_window, "workspace", None)
    working_root = (Path(ws.working_root)
                    if ws is not None and getattr(ws, "working_root", None)
                    else None)
    units = run_long(parent, lambda: analyze_sectors_merge(
        working_yaml, source_yaml, detailed=True))
    duplicates = run_long(parent, lambda: find_duplicate_playfields(
        working_yaml))
    broken = run_long(parent, lambda: find_broken_systems(working_yaml))
    deps, missing = [], []
    if units:
        deps, missing, _identical = run_long(
            parent, lambda: collect_playfield_type_deps(
                working_yaml, source_yaml, units,
                working_root=working_root, source_root=source_root))
    if not units and not deps and not duplicates:
        if broken:
            info(parent, t("sectorsflow.title"),
                 t("sectorsflow.broken_only", systems=", ".join(broken)))
        else:
            info(parent, t("sectorsflow.title"), t("sectorsflow.none"))
        return False
    dlg = SectorsFineDialog(units, deps, missing, duplicates, parent=parent)
    if not dlg.exec():
        return False
    reqs = dlg.selections()
    checked_deps = dlg.checked_deps()
    fix_dups = (dlg.chk_fix_dups is not None
                and dlg.chk_fix_dups.isChecked())
    if not reqs and not checked_deps and not fix_dups:
        return False
    from core.fsutil import central_backup
    from core.workspace_undo import FileStateUndo, capture_file
    prior = capture_file(working_yaml)
    applied, _apply_details = run_long(parent, lambda: apply_fine_selection(
        working_yaml, reqs, source_yaml))
    copied = 0
    if checked_deps and working_root is not None:
        copied = run_long(parent, lambda: copy_playfield_type_deps(
            checked_deps, working_root))
    dups_fixed = 0
    if fix_dups and duplicates:
        dups_fixed, _details = run_long(
            parent, lambda: drop_duplicate_playfields(working_yaml))
    if not (applied or copied or dups_fixed):
        return False
    central_backup(working_yaml)
    if main_window is not None:
        main_window._push_workspace_undo(FileStateUndo(
            working_yaml, prior, t("sectorsflow.undo", n=applied)))
        reload_tab = getattr(main_window,
                             "_reload_tab_if_open_and_unmodified", None)
        if reload_tab is not None:
            reload_tab(working_yaml)
        if ws is not None:
            ws.rescan_working()
    # filet post-application : ne doit JAMAIS sonner en regime normal
    # (le moteur exclut deja les conflits et les systemes sans soleil) ;
    # si ca sonne, on l'affiche plutot que de jouer avec un fichier casse.
    dups_left = run_long(parent, lambda: find_duplicate_playfields(
        working_yaml))
    broken_left = run_long(parent, lambda: find_broken_systems(working_yaml))
    msg = t("sectorsflow.done", n=applied)
    if copied:
        msg += " " + t("sectorsflow.done_pf", n=copied)
    if dups_fixed:
        msg += " " + t("sectorsflow.done_dups", n=dups_fixed)
    if dups_left or broken_left:
        msg += "\n" + t("sectorsflow.post_warn", dups=len(dups_left),
                        broken=", ".join(broken_left) or "-")
    info(parent, t("sectorsflow.title"), msg)
    return True
