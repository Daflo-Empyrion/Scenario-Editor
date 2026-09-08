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

"""
Apercu MODIFIABLE d'une fusion ECF avant ecriture (ECF-030 + FUS-010, v1.6.1).

Avant : la fusion de fichier etait ecrite DIRECTEMENT sur disque, l'utilisateur
ne voyait le rapport qu'APRES coup (colorations) et n'avait AUCUN controle sur
ce qui passait. Desormais :
  1. la fusion est CALCULEE EN MEMOIRE (meme moteur, core/ecf/merge.py,
     mode 'properties', copie de travail prioritaire) ;
  2. les differences proposees sont listees ligne par ligne (bloc ajoute /
     propriete ajoutee / propriete DIFFERENTE) avec AVANT et APRES ;
  3. chaque ligne est cochable (appliquer ou pas) et la colonne "Apres" est
     editable librement (comme l'apercu de la transformation en masse) ;
  4. a la validation, SEULES les lignes cochees sont appliquees au document
     fusionne -- l'ecriture disque reste l'affaire de l'appelant (main_window),
     qui pousse l'undo et ouvre l'onglet sur le premier bloc fusionne.

Contrairement au rapport CSV, le moteur 'properties' ne modifie JAMAIS une
propriete deja presente avec une valeur : la colonne "differentes" liste ces
ecarts pour information, decoches par defaut -- cocher la case applique la
valeur du scenario source (l'inverse de la priorite par defaut, choix explicite).
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QMessageBox, QAbstractItemView,
)

from core.i18n import t
from core.ecf.merge import merge_documents
from core.ecf.model import EcfBlock, EcfProperty, block_identity, normalized_kind


@dataclass
class MergePreviewRow:
    """Une ligne d'ecart propose par la fusion (voir docstring module)."""
    row_type: str           # 'added_block' | 'added_property' | 'changed_property'
    block_key: Tuple[str, Optional[str]]   # (kind normalise, identite)
    block_label: str
    prop_key: Optional[str]      # None pour un bloc entier
    working_value: str           # '(absent)' si la cle n'existe pas
    merged_value: str            # valeur proposee par la fusion (source)
    merged_block: Optional[EcfBlock] = None   # reference DANS le document fusionne
    working_key_present: bool = True


def compute_merge_preview(working_doc, source_doc, source_label: str):
    """Fusion en memoire + extraction des ecarts travail/fusion. Ne modifie
    AUCUN des deux documents d'origine. Retourne (resultat_fusion, lignes)."""
    result = merge_documents(
        [("working", working_doc), ("source", source_doc)],
        mode='properties',
    )
    merged_doc = result.document

    working_index = {}
    for b in working_doc.iter_blocks():
        working_index.setdefault((normalized_kind(b.kind), block_identity(b)), b)
    source_index = {}
    for b in source_doc.iter_blocks():
        source_index.setdefault((normalized_kind(b.kind), block_identity(b)), b)

    def _props(block):
        props = {}
        for k, v in block.pairs:
            if k:
                props.setdefault(k, v)
        for child in block.children:
            if isinstance(child, EcfProperty):
                for k, v in child.pairs:
                    if k:
                        props.setdefault(k, v)
        return props

    rows: List[MergePreviewRow] = []
    for b in merged_doc.iter_blocks():
        key = (normalized_kind(b.kind), block_identity(b))
        wblock = working_index.get(key)
        if wblock is None:
            # Bloc ENTIEREMENT nouveau (vient de la source uniquement).
            label = b.kind + (f" [{block_identity(b)}]" if block_identity(b) else "")
            rows.append(MergePreviewRow(
                row_type='added_block', block_key=key, block_label=label,
                prop_key=None, working_value='(absent)', merged_value=b.kind,
                merged_block=b, working_key_present=False))
            continue
        working_props = _props(wblock)
        source_block = source_index.get(key)
        source_props = _props(source_block) if source_block is not None else {}
        label = b.kind + (f" [{block_identity(b)}]" if block_identity(b) else "")
        for k, mv in _props(b).items():
            if k not in working_props:
                rows.append(MergePreviewRow(
                    row_type='added_property', block_key=key, block_label=label,
                    prop_key=k, working_value='(absent)', merged_value=mv,
                    merged_block=b, working_key_present=False))
            elif k in source_props and source_props[k] != working_props[k]:
                # Propriete presente des deux cotes avec des VALEURS
                # DIFFERENTES : la fusion conserve la copie de travail, mais
                # on liste l'ecart pour permettre un choix explicite (cocher =
                # prendre la valeur source, ou saisir une autre valeur).
                rows.append(MergePreviewRow(
                    row_type='changed_property', block_key=key, block_label=label,
                    prop_key=k, working_value=working_props[k],
                    merged_value=source_props[k],
                    merged_block=b, working_key_present=True))
    return result, rows


class MergePreviewDialog(QDialog):
    """Tableau coche + avant + apres EDITABLE (meme esprit que l'apercu de la
    transformation en masse). N'ECRIT RIEN : `apply_selected()` mute le
    document fusionne en memoire ; l'appelant le serialise apres accept()."""

    COL_CHECK, COL_TYPE, COL_BLOCK, COL_KEY, COL_BEFORE, COL_AFTER = range(6)

    def __init__(self, working_doc, source_doc, source_label: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("mergepreview.title"))
        self.setMinimumSize(860, 560)

        result, rows = compute_merge_preview(working_doc, source_doc, source_label)
        self.result = result
        self.rows = rows

        layout = QVBoxLayout(self)
        intro = QLabel(t("mergepreview.intro", n=len(rows), source=source_label))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.table = QTableWidget(len(rows), 6)
        self.table.setHorizontalHeaderLabels([
            "", t("mergepreview.col_type"), t("mergepreview.col_block"),
            t("mergepreview.col_key"), t("mergepreview.col_before"),
            t("mergepreview.col_after"),
        ])
        self.table.horizontalHeader().setSectionResizeMode(self.COL_BLOCK, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(self.COL_KEY, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(self.COL_BEFORE, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(self.COL_AFTER, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.table.verticalHeader().setVisible(False)

        type_labels = {
            'added_block': t("mergepreview.type_added_block"),
            'added_property': t("mergepreview.type_added_property"),
            'changed_property': t("mergepreview.type_changed_property"),
        }
        for r, row in enumerate(rows):
            check = QTableWidgetItem()
            check.setFlags(check.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            # Blocs et proprietes AJOUTES : coches par defaut (la fusion les
            # apporte). Proprietes DIFFERENTES : decochees (la copie de
            # travail reste prioritaire tant que l'utilisateur ne choisit pas
            # explicitement la valeur source).
            check.setCheckState(Qt.CheckState.Checked if row.row_type != 'changed_property'
                                else Qt.CheckState.Unchecked)
            self.table.setItem(r, self.COL_CHECK, check)

            item = QTableWidgetItem(type_labels[row.row_type])
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, self.COL_TYPE, item)

            item = QTableWidgetItem(row.block_label)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, self.COL_BLOCK, item)

            item = QTableWidgetItem(row.prop_key or "")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, self.COL_KEY, item)

            item = QTableWidgetItem(row.working_value)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, self.COL_BEFORE, item)

            after = row.merged_value if row.row_type != 'added_block' else ""
            self.table.setItem(r, self.COL_AFTER, QTableWidgetItem(after))
        layout.addWidget(self.table, 1)

        note = QLabel(t("mergepreview.note"))
        note.setWordWrap(True)
        layout.addWidget(note)

        if result.id_conflicts:
            conflicts_label = QLabel(t("mergepreview.id_conflicts", n=len(result.id_conflicts)))
            conflicts_label.setWordWrap(True)
            conflicts_label.setStyleSheet("color: #c62828;")
            layout.addWidget(conflicts_label)

        buttons = QHBoxLayout()
        btn_all = QPushButton(t("trans.check_all"))
        btn_all.clicked.connect(lambda: self._set_all_checks(True))
        buttons.addWidget(btn_all)
        btn_none = QPushButton(t("trans.uncheck_all"))
        btn_none.clicked.connect(lambda: self._set_all_checks(False))
        buttons.addWidget(btn_none)
        buttons.addStretch()
        btn_ok = QPushButton(t("mergepreview.btn_apply"))
        btn_ok.setObjectName("primaryButton")
        btn_ok.clicked.connect(self._on_accept)
        buttons.addWidget(btn_ok)
        btn_cancel = QPushButton(t("btn.cancel"))
        btn_cancel.setObjectName("secondaryButton")
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_cancel)
        layout.addLayout(buttons)

    def _set_all_checks(self, state: bool) -> None:
        cs = Qt.CheckState.Checked if state else Qt.CheckState.Unchecked
        for r in range(self.table.rowCount()):
            self.table.item(r, self.COL_CHECK).setCheckState(cs)

    def _on_accept(self) -> None:
        self.apply_selected()
        self.accept()

    def apply_selected(self) -> None:
        """Applique les lignes cochees au document fusionne EN MEMOIRE :
        - ligne decochee d'un bloc ajoute -> le bloc est RETIRE du document ;
        - ligne decochee d'une propriete -> la valeur copie de travail est
          restauree (ajout : la propriete retrouve sa valeur d'origine) ;
        - ligne cochee -> la valeur "Apres" (eventuellement editee) est ecrite.
        Les blocs ajoutes decoches retirent aussi leurs proprietes (deja
        couverts : le bloc entier part)."""
        blocks_to_remove = []
        for r, row in enumerate(self.rows):
            checked = self.table.item(r, self.COL_CHECK).checkState() == Qt.CheckState.Checked
            after = self.table.item(r, self.COL_AFTER).text()
            if row.row_type == 'added_block':
                if not checked and row.merged_block is not None:
                    blocks_to_remove.append(row.merged_block)
                continue
            if row.merged_block is None or not row.prop_key:
                continue
            if checked:
                row.merged_block.set_property(row.prop_key, after)
            else:
                if row.working_key_present:
                    row.merged_block.set_property(row.prop_key, row.working_value)
                else:
                    # Retire la propriete ajoutee non voulue : vide les paires
                    # porteuses puis supprime les noeuds vidés (directs ou
                    # enfants) pour ne laisser AUCUNE ligne residuelle.
                    row.merged_block.pairs = [
                        (k, v) for (k, v) in row.merged_block.pairs if k != row.prop_key]
                    for child in list(row.merged_block.children):
                        if isinstance(child, EcfProperty):
                            child.pairs = [
                                (k, v) for (k, v) in child.pairs if k != row.prop_key]
                            if not child.pairs:
                                row.merged_block.children.remove(child)
        for block in blocks_to_remove:
            try:
                self.result.document.nodes.remove(block)
            except ValueError:
                pass  # deja retire (ligne bloquee en double dans le rapport)

    def rejected_summary(self) -> int:
        """Nombre de lignes laissees decochees (pour le message de statut)."""
        return sum(1 for r in range(self.table.rowCount())
                   if self.table.item(r, self.COL_CHECK).checkState() != Qt.CheckState.Checked)
