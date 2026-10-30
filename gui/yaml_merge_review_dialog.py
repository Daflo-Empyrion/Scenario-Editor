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

"""Fenetre de REVISION d'une fusion YAML (demande 26/09/2026 : un
PDA.yaml existant etait ecrase en aveugle par la fusion de fichier).
Liste les unites structurelles proposees (cles racines et elements de
listes de blocs absents de la copie de travail, cf. core/yaml_merge.py),
cocheables une a une ; bouton explicite 'Remplacer tout le fichier' pour
l'ecrasement complet (choix explicite, copie de travail prioritaire)."""
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton,
                             QTreeWidget, QTreeWidgetItem, QVBoxLayout)

from core.i18n import t
from gui.module_info import add_info_button
from core.yaml_merge import YamlUnit, analyze_yaml_merge, yaml_files_identical
from gui.window_geometry import track


class YamlMergeReviewDialog(QDialog):
    """Unites de fusion YAML cochees. N'applique RIEN : l'appelant lit
    `selected_units()` (ou `replace_all`) et gere ecriture + undo."""

    COL_CHECK, COL_KIND, COL_NAME, COL_INFO = range(4)

    def __init__(self, working_yaml: Path, source_yaml: Path,
                 source_label: str, parent=None, working_root=None):
        super().__init__(parent)
        self.working_yaml = Path(working_yaml)
        self.source_yaml = Path(source_yaml)
        self.source_label = source_label
        self.replace_all = False
        self.working_root = working_root
        self.setWindowTitle(t("yamlmerge.title", file=source_yaml.name))
        track(self, "yaml_merge_review", (760, 520))

        layout = QVBoxLayout(self)
        self.intro_label = QLabel()
        layout.addWidget(self.intro_label)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([t("mergeplan.col_apply"),
                                   t("yamlmerge.col_kind"),
                                   t("yamlmerge.col_name"),
                                   t("mergeplan.col_info")])
        self.tree.setColumnWidth(0, 70)
        self.tree.setColumnWidth(1, 160)
        self.tree.setColumnWidth(2, 300)
        layout.addWidget(self.tree, 1)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        buttons = QHBoxLayout()
        self.btn_all = QPushButton(t("trans.check_all"))
        self.btn_all.clicked.connect(lambda: self._set_all_checks(True))
        buttons.addWidget(self.btn_all)
        self.btn_none = QPushButton(t("trans.uncheck_all"))
        self.btn_none.clicked.connect(lambda: self._set_all_checks(False))
        buttons.addWidget(self.btn_none)
        add_info_button(buttons, "yamlmerge.info_html")
        buttons.addStretch()
        self.btn_poi = None
        if (self.working_yaml.name.lower() == "playfield_static.yaml"
                and self.working_root):
            # demande 09/10 : ajouter un POI au playfield en revision
            self.btn_poi = QPushButton(t("poi.add_action"))
            self.btn_poi.clicked.connect(self._open_poi_add)
            buttons.addWidget(self.btn_poi)
        self.btn_replace = QPushButton(t("yamlmerge.btn_replace"))
        self.btn_replace.clicked.connect(self._do_replace_all)
        buttons.addWidget(self.btn_replace)
        self.btn_apply = QPushButton(t("mergepreview.btn_apply"))
        self.btn_apply.setObjectName("primaryButton")
        self.btn_apply.clicked.connect(self._do_apply)
        buttons.addWidget(self.btn_apply)
        self.btn_cancel = QPushButton(t("btn.cancel"))
        self.btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(self.btn_cancel)
        layout.addLayout(buttons)

        # analyse (lecture des deux fichiers) en worker + gerbe plasma
        from gui.busy import run_long
        self.identical, self.units = run_long(self, self._analyze)
        self._fill()

    def _open_poi_add(self):
        """Assistant POI sur le playfield en revision ; l'application avec
        undo espace de travail passe par la MainWindow parente (le bouton
        n'existe que si working_root a ete fourni par elle)."""
        from gui.busy import run_long
        from gui.poi_add_dialog import PoiAddDialog
        dlg = PoiAddDialog(self, self.working_yaml,
                           working_root=self.working_root)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        apply_plan = getattr(self.parent(), "_apply_poi_plan", None)
        if apply_plan is not None:
            apply_plan(self.working_yaml, dlg.plan)
            # le fichier vient de changer : les unites appliquees ne
            # doivent plus etre proposees (moteur idempotent)
            self.identical, self.units = run_long(self, self._analyze)
            self._fill()

    def _analyze(self):
        if yaml_files_identical(self.working_yaml, self.source_yaml):
            return True, []
        return False, analyze_yaml_merge(self.working_yaml, self.source_yaml)

    def _fill(self):
        if self.identical:
            self.intro_label.setText(t("yamlmerge.intro", source=self.source_label))
            self.status_label.setText(t("yamlmerge.identical_file",
                                        name=self.source_yaml.name))
            self.btn_apply.setEnabled(False)
            self.btn_replace.setEnabled(False)
            self.btn_all.setEnabled(False)
            self.btn_none.setEnabled(False)
            return
        self.intro_label.setText(t("yamlmerge.intro", source=self.source_label))
        _KINDS = {"key": t("yamlmerge.kind_key"),
                  "item": t("yamlmerge.kind_item"),
                  "subkey": t("yamlmerge.kind_subkey"),
                  "modified": t("yamlmerge.kind_modified")}
        for unit in self.units:
            kind = _KINDS.get(unit.kind, unit.kind)
            label = unit.name if unit.kind == "key" \
                else f"{unit.name}  ·  {unit.root}"
            detail = unit.detail
            if unit.kind == "modified":
                detail = f"{unit.detail}  ·  {t('yamlmerge.modified_hint')}"
            item = QTreeWidgetItem(["", kind, label, detail])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            # unite 'modified' : la coche par defaut reflete ses lignes
            # (copie de travail prioritaire -> generalement DECOCHÉE),
            # le detail ligne a ligne est ouverte au double-clic
            checked = any(r.checked for r in unit.rows) \
                if unit.kind == "modified" else True
            item.setCheckState(
                0, Qt.CheckState.Checked if checked
                else Qt.CheckState.Unchecked)
            if unit.kind == "modified":
                item.setToolTip(self.COL_KIND, t("yamlmerge.modified_tip"))
            item.setData(0, Qt.ItemDataRole.UserRole, unit)
            item.setToolTip(self.COL_INFO, unit.detail)
            self.tree.addTopLevelItem(item)
        self.tree.itemChanged.connect(self._on_unit_check_changed)
        self.tree.itemDoubleClicked.connect(self._open_line_detail)
        self.status_label.setText(
            t("yamlmerge.summary", n=len(self.units),
              name=self.source_yaml.name))
        self.btn_apply.setEnabled(bool(self.units))
        self._refresh_buttons()

    def _on_unit_check_changed(self, item, _column) -> None:
        """Cocher une unite 'modified' coche TOUTES ses lignes
        actionables (ajouts, modifications ET suppressions miroir --
        la confirmation avant application reste l'ultime garde-fou)."""
        unit = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(unit, YamlUnit) or unit.kind != "modified":
            return
        state = item.checkState(0) == Qt.CheckState.Checked
        for row in unit.rows:
            if row.state != "same":
                row.checked = state
        self._refresh_buttons()

    def _open_line_detail(self, item, _column) -> None:
        """Double-clic sur une unite 'modified' : diff fin ligne a ligne
        (avant/apres, coches par ligne) -- met a jour les lignes de
        l'unite et l'etat de sa coche."""
        unit = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(unit, YamlUnit) or unit.kind != "modified":
            return
        from gui.yaml_line_merge_dialog import YamlLineMergeDialog
        dialog = YamlLineMergeDialog(unit, self.working_yaml,
                                     self.source_yaml, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            checked = any(r.checked for r in unit.rows)
            item.setCheckState(
                0, Qt.CheckState.Checked if checked
                else Qt.CheckState.Unchecked)
        self._refresh_buttons()

    def _refresh_buttons(self):
        self.btn_apply.setText(t("yamlmerge.btn_apply_n",
                                 n=len(self.selected_units())))

    def _set_all_checks(self, state: bool):
        cs = Qt.CheckState.Checked if state else Qt.CheckState.Unchecked
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            item.setCheckState(0, cs)
            unit = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(unit, YamlUnit) and unit.kind == "modified":
                for row in unit.rows:
                    if row.state != "same":
                        row.checked = state
        self._refresh_buttons()

    def _do_replace_all(self):
        self.replace_all = True
        self.accept()

    def _do_apply(self):
        """Application : une confirmation explicite des que la fusion
        cochee SUPPRIME des lignes du working (miroir -- jamais implicite)."""
        removals = self.pending_removals()
        if removals:
            from gui.msgboxes import ask_yes_no
            if not ask_yes_no(self, t("yamlmerge.remove_title"),
                              t("yamlmerge.remove_confirm", n=removals)):
                return
        self.accept()

    def selected_units(self):
        out = []
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            unit = item.data(0, Qt.ItemDataRole.UserRole)
            if not isinstance(unit, YamlUnit):
                continue
            if item.checkState(0) != Qt.CheckState.Checked:
                continue
            if unit.kind == "modified" \
                    and not any(r.checked for r in unit.rows):
                continue            # cochee mais aucune ligne choisie
            out.append(unit)
        return out

    def pending_removals(self) -> int:
        """Lignes 'remove' (miroir) cochees des unites selectionnees :
        l'appelant (ou le bouton Appliquer) peut exiger une confirmation
        avant d'effacer du working."""
        total = 0
        for unit in self.selected_units():
            if unit.kind == "modified":
                total += sum(1 for r in unit.rows
                             if r.checked and r.state == "remove")
        return total
