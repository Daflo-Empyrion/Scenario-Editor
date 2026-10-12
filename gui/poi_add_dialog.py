# Empyrion Scenario Editor
# Copyright (C) 2026  Daflo
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
"""Assistant « Ajouter un POI » dans un playfield_static (demande 09/10).

Deux onglets, une seule sortie : `plan` vaut ('new', section, bloc_texte)
ou ('import', unites YamlUnit) ; l'appelant applique (add_poi_block /
apply_yaml_units) avec capture/undo espace de travail, comme pour une
fusion. Le dialogue ne touche jamais au disque en ecriture.

- Nouveau : prefab choisi dans le scan des .epb (scenario + vanille),
  Faction/Type/Mode en combos editables alimentees par l'existant du
  playfield, aperçu du bloc genere en direct. Bloc Fixed ordonne Name
  d'abord : l'identite du moteur est la PREMIERE cle de l'item ('- Type:'
  rendrait deux POIs de meme Type incompatibles entre eux).
- Importer : POIs d'un autre playfield_static du workspace absents du
  dest (poi_units), cochables.
"""
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox, QCompleter, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QPlainTextEdit, QPushButton, QRadioButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QTabWidget, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from core.i18n import t
from core.poi_add import (field_pool, list_pois, poi_units,
                          scan_playfield_statics, scan_prefab_names,
                          remove_pois)
from core.settings import get_vanilla_content_path
from gui.window_geometry import track

_FACTIONS = ["Zirax", "TheLegacy", "Swarm", "Wastewater", "Pirates", "Alien"]
_FIXED_TYPES = ["BA", "BA_Alien", "CV", "CV_Alien", "SV", "HV"]
_FIXED_MODES = ["Survival", "Debug"]


def _mono() -> QFont:
    f = QFont("Consolas")
    f.setStyleHint(QFont.StyleHint.Monospace)
    return f


class PoiAddDialog(QDialog):
    COL_CHECK, COL_IDENT, COL_SECTION, COL_DETAIL = range(4)

    def __init__(self, parent, dest_yaml, working_root=None):
        super().__init__(parent)
        self.dest_yaml = Path(dest_yaml)
        self.plan = None   # ('new', section, bloc) | ('import', [YamlUnit])
        self.setWindowTitle(t("poi.title", name=self.dest_yaml.name))
        self.resize(880, 660)
        track(self, "poi_add")

        lay = QVBoxLayout(self)
        hint = QLabel(t("poi.dest_label", name=self.dest_yaml.name))
        hint.setWordWrap(True)
        lay.addWidget(hint)

        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)
        self.tabs.addTab(self._tab_new(working_root), t("poi.tab_new"))
        self.tabs.addTab(self._tab_import(working_root), t("poi.tab_import"))
        self.tabs.addTab(self._tab_remove(), t("poi.tab_remove"))
        self.tabs.currentChanged.connect(self._on_tab_changed)

        row = QHBoxLayout()
        row.addStretch(1)
        self.btn_add = QPushButton(t("poi.add_button"))
        self.btn_add.clicked.connect(self._accept_plan)
        row.addWidget(self.btn_add)
        self.btn_cancel = QPushButton(t("btn.cancel"))
        self.btn_cancel.clicked.connect(self.reject)
        row.addWidget(self.btn_cancel)
        lay.addLayout(row)

    def _on_tab_changed(self, index: int):
        self.btn_add.setText(t("poi.remove_button")
                             if index == 2 else t("poi.add_button"))

    # ------------------------------------------------- onglet 1 : nouveau
    def _tab_new(self, working_root) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        form = QFormLayout()

        sec_row = QHBoxLayout()
        self.rb_random = QRadioButton(t("poi.section_random"))
        self.rb_fixed = QRadioButton(t("poi.section_fixed"))
        self.rb_random.setChecked(True)
        sec_row.addWidget(self.rb_random)
        sec_row.addWidget(self.rb_fixed)
        sec_row.addStretch(1)
        form.addRow(t("poi.section"), sec_row)

        # prefab : ligne editable + completer « contient » sur le scan
        self.cb_prefab = QLineEdit()
        roots = []
        if working_root:
            roots.append(Path(working_root) / "Prefabs")
        vanilla = get_vanilla_content_path()
        if vanilla:
            roots.append(Path(vanilla) / "Prefabs")
        completer = QCompleter(scan_prefab_names(*roots), self.cb_prefab)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.cb_prefab.setCompleter(completer)
        form.addRow(t("poi.prefab"), self.cb_prefab)

        self.cb_group = QLineEdit()
        form.addRow(t("poi.group_name"), self.cb_group)
        self.cb_faction = self._pool_combo(_FACTIONS, "Faction")
        form.addRow(t("poi.faction"), self.cb_faction)

        self.cb_ftype = self._pool_combo(_FIXED_TYPES, "Type")
        self.cb_ftype.setCurrentIndex(0)   # requis par le jeu : defaut BA
        self.lbl_ftype = QLabel(t("poi.type"))
        form.addRow(self.lbl_ftype, self.cb_ftype)
        self.cb_name = QLineEdit()
        self.lbl_name = QLabel(t("poi.name"))
        form.addRow(self.lbl_name, self.cb_name)
        self.cb_mode = self._pool_combo(_FIXED_MODES, "Mode")
        self.cb_mode.setCurrentIndex(0)    # requis par le jeu : Survival
        self.lbl_mode = QLabel(t("poi.mode"))
        form.addRow(self.lbl_mode, self.cb_mode)
        self.sp_x, self.sp_y, self.sp_z = QSpinBox(), QSpinBox(), QSpinBox()
        pos_row = self._spin_row(self.sp_x, self.sp_y, self.sp_z)
        self.lbl_pos = QLabel(t("poi.pos"))
        form.addRow(self.lbl_pos, pos_row)
        self.sp_roty = QSpinBox()
        self.sp_roty.setRange(0, 359)
        self.lbl_roty = QLabel(t("poi.roty"))
        form.addRow(self.lbl_roty, self.sp_roty)

        self.sp_cmin, self.sp_cmax = QSpinBox(), QSpinBox()
        cnt_row = self._spin_row(self.sp_cmin, self.sp_cmax)
        self.sp_cmin.setRange(0, 99)
        self.sp_cmax.setRange(0, 99)
        self.sp_cmin.setValue(1)
        self.sp_cmax.setValue(1)
        self.lbl_count = QLabel(t("poi.count_minmax"))
        form.addRow(self.lbl_count, cnt_row)
        self.sp_prob = QSpinBox()
        self.sp_prob.setRange(0, 100)
        self.sp_prob.setValue(100)
        self.lbl_prob = QLabel(t("poi.drone_prob"))
        form.addRow(self.lbl_prob, self.sp_prob)
        self.sp_dmin, self.sp_dmax = QSpinBox(), QSpinBox()
        dr_row = self._spin_row(self.sp_dmin, self.sp_dmax)
        self.sp_dmin.setRange(0, 99)
        self.sp_dmax.setRange(0, 99)
        self.sp_dmin.setValue(2)
        self.sp_dmax.setValue(3)
        self.lbl_drones = QLabel(t("poi.drones_minmax"))
        form.addRow(self.lbl_drones, dr_row)
        self.sp_reserve = QSpinBox()
        self.sp_reserve.setRange(0, 99)
        self.sp_reserve.setValue(5)
        self.lbl_reserve = QLabel(t("poi.reserve"))
        form.addRow(self.lbl_reserve, self.sp_reserve)
        lay.addLayout(form)

        self.props = QTableWidget(0, 2)
        self.props.setHorizontalHeaderLabels([t("poi.prop_key"),
                                              t("poi.prop_value")])
        self.props.horizontalHeader().setStretchLastSection(True)
        self.props.setMaximumHeight(120)
        lay.addWidget(self.props, 1)
        pr_row = QHBoxLayout()
        btn_add_prop = QPushButton(t("poi.prop_add"))
        btn_add_prop.clicked.connect(self._add_prop_row)
        pr_row.addWidget(btn_add_prop)
        btn_del_prop = QPushButton(t("poi.prop_del"))
        btn_del_prop.clicked.connect(self._del_prop_row)
        pr_row.addWidget(btn_del_prop)
        pr_row.addStretch(1)
        lay.addLayout(pr_row)

        lay.addWidget(QLabel(t("poi.preview")))
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFont(_mono())
        lay.addWidget(self.preview, 2)

        for sp in (self.sp_x, self.sp_y, self.sp_z, self.sp_roty,
                   self.sp_cmin, self.sp_cmax, self.sp_prob,
                   self.sp_dmin, self.sp_dmax, self.sp_reserve):
            sp.valueChanged.connect(self._refresh_preview)
        self.cb_prefab.textChanged.connect(self._on_prefab)
        self.cb_group.textChanged.connect(self._refresh_preview)
        self.cb_faction.editTextChanged.connect(self._refresh_preview)
        self.cb_ftype.editTextChanged.connect(self._refresh_preview)
        self.cb_name.textChanged.connect(self._refresh_preview)
        self.cb_mode.editTextChanged.connect(self._refresh_preview)
        self.props.cellChanged.connect(self._refresh_preview)
        self.rb_random.toggled.connect(self._on_section)
        self._on_section()
        return w

    def _pool_combo(self, pool, key: str) -> QComboBox:
        """Combo editable : pool standard + valeurs deja dans le dest."""
        combo = QComboBox()
        combo.setEditable(True)
        seen = set()
        for v in list(pool) + field_pool(self.dest_yaml, key):
            if v.lower() not in seen:
                seen.add(v.lower())
                combo.addItem(v)
        combo.setCurrentIndex(-1)
        return combo

    def _spin_row(self, *spins) -> QHBoxLayout:
        for sp in spins:
            sp.setRange(-100000, 100000)
        row = QHBoxLayout()
        for sp in spins:
            row.addWidget(sp)
        row.addStretch(1)
        return row

    def _on_prefab(self, txt):
        if not self.cb_group.text().strip():
            self.cb_group.setText(txt.strip())

    def _on_section(self):
        fixed = self.rb_fixed.isChecked()
        for lbl, wdgs in ((self.lbl_ftype, (self.cb_ftype,)),
                          (self.lbl_name, (self.cb_name,)),
                          (self.lbl_mode, (self.cb_mode,)),
                          (self.lbl_pos, (self.sp_x, self.sp_y, self.sp_z)),
                          (self.lbl_roty, (self.sp_roty,))):
            for wdg in (lbl,) + wdgs:
                wdg.setVisible(fixed)
        for lbl, wdgs in ((self.lbl_count, (self.sp_cmin, self.sp_cmax)),
                          (self.lbl_prob, (self.sp_prob,)),
                          (self.lbl_drones, (self.sp_dmin, self.sp_dmax)),
                          (self.lbl_reserve, (self.sp_reserve,))):
            for wdg in (lbl,) + wdgs:
                wdg.setVisible(not fixed)
        self._refresh_preview()

    def _add_prop_row(self):
        r = self.props.rowCount()
        self.props.insertRow(r)
        self.props.setItem(r, 0, QTableWidgetItem(t("poi.prop_key_default")))
        self.props.setItem(r, 1, QTableWidgetItem(t("poi.prop_value_default")))

    def _del_prop_row(self):
        r = self.props.currentRow()
        if r >= 0:
            self.props.removeRow(r)

    def _prop_pairs(self):
        out = []
        for r in range(self.props.rowCount()):
            k_it = self.props.item(r, 0)
            v_it = self.props.item(r, 1)
            if k_it is None or v_it is None:
                continue
            k, v = k_it.text().strip(), v_it.text().strip()
            if k and v:
                out.append((k, v))
        return out

    def _build_block(self) -> str:
        """Bloc RELATIF au niveau de l'item ('- ' colonne 0, champs +2) :
        add_poi_block ajoute l'indentation du playfield de destination."""
        prefab = self.cb_prefab.text().strip()
        faction = self.cb_faction.currentText().strip()
        ind = " " * 2
        ind2 = " " * 4
        if self.rb_fixed.isChecked():
            lines = ["- Name: " + (self.cb_name.text().strip() or prefab),
                     ind + "Type: " + self.cb_ftype.currentText().strip(),
                     ind + "Prefab: " + prefab]
            if faction:
                lines.append(ind + "Faction: " + faction)
            lines.append(ind + "Mode: " + self.cb_mode.currentText().strip())
            lines.append(ind + f"Pos: [ {self.sp_x.value()}, "
                         f"{self.sp_y.value()}, {self.sp_z.value()} ]")
            if self.sp_roty.value():
                lines.append(ind + f"RotY: {self.sp_roty.value()}")
        else:
            group = self.cb_group.text().strip() or prefab
            lines = ["- GroupName: " + group]
            if faction:
                lines.append(ind + "Faction: " + faction)
            lines.append(ind + f"CountMinMax: [ {self.sp_cmin.value()}, "
                         f"{self.sp_cmax.value()} ]")
            lines.append(ind + f"DroneProb: {self.sp_prob.value() / 100.0:g}")
            lines.append(ind + f"DronesMinMax: [ {self.sp_dmin.value()}, "
                         f"{self.sp_dmax.value()} ]")
            lines.append(ind + f"ReserveCount: {self.sp_reserve.value()}")
        pairs = self._prop_pairs()
        if pairs:
            lines.append(ind + "Properties:")
            for k, v in pairs:
                lines.append(ind2 + "- Key: " + k)
                lines.append(ind2 + "  Value: " + v)
        return "\n".join(lines)

    def _refresh_preview(self):
        self.preview.setPlainText(self._build_block())

    # ------------------------------------------------- onglet 2 : import
    def _tab_import(self, working_root) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        row = QHBoxLayout()
        row.addWidget(QLabel(t("poi.source_playfield")))
        self.cb_source = QComboBox()
        self.cb_source.currentIndexChanged.connect(self._load_source)
        row.addWidget(self.cb_source, 1)
        lay.addLayout(row)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([t("mergeplan.col_apply"),
                                   t("epb.col_id"), t("poi.col_section"),
                                   t("epb.col_name")])
        self.tree.setColumnWidth(self.COL_CHECK, 60)
        self.tree.setColumnWidth(self.COL_IDENT, 260)
        self.tree.setColumnWidth(self.COL_SECTION, 150)
        lay.addWidget(self.tree, 1)

        row2 = QHBoxLayout()
        btn_all = QPushButton(t("trans.check_all"))
        btn_all.clicked.connect(lambda: self._check_all(True))
        row2.addWidget(btn_all)
        btn_none = QPushButton(t("trans.uncheck_all"))
        btn_none.clicked.connect(lambda: self._check_all(False))
        row2.addWidget(btn_none)
        row2.addStretch(1)
        self.lbl_status = QLabel("")
        row2.addWidget(self.lbl_status, 1)
        lay.addLayout(row2)

        self._import_units = []
        if working_root:
            for p in scan_playfield_statics(working_root):
                if p != self.dest_yaml:
                    self.cb_source.addItem(p.parent.name, str(p))
        return w

    def _load_source(self):
        self.tree.clear()
        self._import_units = []
        path = self.cb_source.currentData()
        if not path:
            return
        units = poi_units(self.dest_yaml, Path(path))
        for u in units:
            it = QTreeWidgetItem(["", u.name,
                                  u.root or u.name, u.detail])
            it.setCheckState(self.COL_CHECK, Qt.CheckState.Checked)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            self.tree.addTopLevelItem(it)
            self._import_units.append((it, u))
        self.lbl_status.setText(t("poi.import_count", n=len(units)))

    def _check_all(self, state: bool):
        for i in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(i).setCheckState(
                self.COL_CHECK,
                Qt.CheckState.Checked if state else Qt.CheckState.Unchecked)

    def _selected_units(self):
        return [u for it, u in self._import_units
                if it.checkState(self.COL_CHECK) == Qt.CheckState.Checked]

    # ---------------------------------------------- onglet 3 : supprimer
    def _tab_remove(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lbl = QLabel(t("poi.remove_hint"))
        lbl.setWordWrap(True)
        lay.addWidget(lbl)

        self.tree_remove = QTreeWidget()
        self.tree_remove.setHeaderLabels([t("mergeplan.col_apply"),
                                          t("poi.col_section"),
                                          t("epb.col_id"),
                                          t("mergeplan.col_info")])
        self.tree_remove.setColumnWidth(self.COL_CHECK, 60)
        self.tree_remove.setColumnWidth(self.COL_SECTION, 150)
        self.tree_remove.setColumnWidth(self.COL_IDENT, 280)
        lay.addWidget(self.tree_remove, 1)

        row2 = QHBoxLayout()
        btn_all = QPushButton(t("trans.check_all"))
        btn_all.clicked.connect(lambda: self._check_all_remove(True))
        row2.addWidget(btn_all)
        btn_none = QPushButton(t("trans.uncheck_all"))
        btn_none.clicked.connect(lambda: self._check_all_remove(False))
        row2.addWidget(btn_none)
        row2.addStretch(1)
        self.lbl_remove = QLabel("")
        row2.addWidget(self.lbl_remove, 1)
        lay.addLayout(row2)

        # suppression jamais implicite : TOUT est decoche par defaut
        self._remove_items = []
        for section, ident, detail in list_pois(self.dest_yaml):
            it = QTreeWidgetItem(["", section, f"{ident[0]}: {ident[1]}",
                                  detail])
            it.setCheckState(self.COL_CHECK, Qt.CheckState.Unchecked)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            self.tree_remove.addTopLevelItem(it)
            self._remove_items.append((it, section, ident))
        self.lbl_remove.setText(
            t("poi.remove_count", n=len(self._remove_items)))
        return w

    def _check_all_remove(self, state: bool):
        for i in range(self.tree_remove.topLevelItemCount()):
            self.tree_remove.topLevelItem(i).setCheckState(
                self.COL_CHECK,
                Qt.CheckState.Checked if state else Qt.CheckState.Unchecked)

    def _selected_remove(self):
        return [(section, ident) for it, section, ident in self._remove_items
                if it.checkState(self.COL_CHECK) == Qt.CheckState.Checked]

    # ------------------------------------------------------------- sortie
    def _accept_plan(self):
        from gui.msgboxes import info
        title = t("poi.title", name=self.dest_yaml.name)
        if self.tabs.currentIndex() == 0:
            if not self.cb_prefab.text().strip():
                info(self, title, t("poi.need_prefab"))
                return
            self.plan = ("new", "Fixed" if self.rb_fixed.isChecked()
                         else "Random", self._build_block())
        elif self.tabs.currentIndex() == 2:
            # suppression jamais implicite : rien de coche = rien a faire
            targets = self._selected_remove()
            if not targets:
                info(self, title, t("mergeplan.nothing_selected"))
                return
            self.plan = ("remove", targets)
        else:
            units = self._selected_units()
            if not units:
                info(self, title, t("mergeplan.nothing_selected"))
                return
            self.plan = ("import", self.cb_source.currentData(), units)
        self.accept()
