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
from core.ecf.merge import (ITEM_PROP_RE, merge_documents,
                            normalize_item_list, ordered_items,
                            renumber_item_lines)
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
    display_key: Optional[str] = None   # libelle lisible (ex 'Item1 · Leather')
    identity_paired: bool = False       # liste ItemN appariee PAR IDENTITE


def compute_merge_preview(working_doc, source_doc, source_label: str):
    """Fusion en memoire + extraction des ecarts travail/fusion. Ne modifie
    AUCUN des deux documents d'origine. Retourne (resultat_fusion, lignes)."""
    result = merge_documents(
        [("working", working_doc), ("source", source_doc)],
        mode='properties',
    )
    merged_doc = result.document

    # Cles CONSCIENTES DU PARENT : les blocs enfants sans identite (ex
    # « Child Inputs » de plusieurs templates) partageaient la meme cle et
    # pouvaient etre apparies au mauvais parent (vecu 25/09 : les lignes
    # d'ajout ne disaient pas de quel template elles relevaient).
    def _walk_with_top(doc):
        """(bloc ancetre racine, bloc) pour tous les blocs du document."""
        out = []

        def walk(nodes, top):
            for n in nodes:
                if isinstance(n, EcfBlock):
                    out.append((top, n))
                    walk(n.children, top if top is not None else n)

        walk(doc.nodes, None)
        return out

    def _pair_key(top, block):
        top_key = ((normalized_kind(top.kind), block_identity(top))
                   if top is not None else None)
        return (top_key, normalized_kind(block.kind),
                block_identity(block))
    working_index = {}
    for top, b in _walk_with_top(working_doc):
        working_index.setdefault(_pair_key(top, b), b)
    source_index = {}
    for top, b in _walk_with_top(source_doc):
        source_index.setdefault(_pair_key(top, b), b)

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

    def _label_of(block):
        """Libelle du bloc : kind [identite] + NOM DU BLOC (demande 25/09 :
        valider 'MaxCount 32 -> 6' sans voir TurretBaseCannonOld est
        impossible — l'identite seule est souvent un simple Id)."""
        ident = block_identity(block)
        name = (block.get("Name") or block.get_property("Name") or "")
        name = name.strip().strip('"')
        label = block.kind
        if ident:
            label += f" [{ident}]"
        if name and name != ident:
            label += f" · {name}"
        return label


    rows: List[MergePreviewRow] = []
    for top, b in _walk_with_top(merged_doc):
        key = _pair_key(top, b)
        wblock = working_index.get(key)
        if wblock is None:
            # Bloc ENTIEREMENT nouveau (vient de la source uniquement).
            label = (_label_of(top) + " · " + _label_of(b))                 if top is not None and top is not b else _label_of(b)
            rows.append(MergePreviewRow(
                row_type='added_block', block_key=key, block_label=label,
                prop_key=None, working_value='(absent)', merged_value=b.kind,
                merged_block=b, working_key_present=False))
            continue
        working_props = _props(wblock)
        source_block = source_index.get(key)
        source_props = _props(source_block) if source_block is not None else {}
        label = (_label_of(top) + " · " + _label_of(b))             if top is not None and top is not b else _label_of(b)
        # Listes ItemN (TraderNPCConfig...) : appariement PAR IDENTITE
        # (le nom d'item en debut de valeur), pas par numero — deux
        # scenarios n'ordonnent pas leurs items pareil, et apparier
        # Item1<->Item1 ecrasait des items differents (vecu 25/09).
        w_items = ordered_items(wblock)
        s_items = ordered_items(source_block) if source_block is not None else []
        identity_block = bool(w_items) and bool(s_items)
        final_slots = None
        if identity_block:
            final_slots = normalize_item_list(b, wblock, source_block)
        for k, mv in _props(b).items():
            if identity_block and k and ITEM_PROP_RE.match(str(k)):
                continue              # geres par identite ci-dessous
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
        if identity_block and final_slots:
            working_map = {ident.casefold(): wval
                           for ident, wval in w_items}
            source_map = {ident.casefold(): sval
                          for ident, sval in s_items}
            for i, (ident, mval) in enumerate(final_slots, 1):
                skey = ident.casefold()
                if skey not in source_map:
                    continue          # item uniquement dans la copie de travail
                sval = source_map[skey]
                slot = f"Item{i}"
                display = f"{slot} · {ident}"
                if skey not in working_map:
                    rows.append(MergePreviewRow(
                        row_type='added_property', block_key=key,
                        block_label=label, prop_key=slot,
                        working_value='(absent)', merged_value=sval,
                        merged_block=b, working_key_present=False,
                        display_key=display, identity_paired=True))
                elif sval != mval:
                    rows.append(MergePreviewRow(
                        row_type='changed_property', block_key=key,
                        block_label=label, prop_key=slot,
                        working_value=mval, merged_value=sval,
                        merged_block=b, working_key_present=True,
                        display_key=display, identity_paired=True))
    # Conflits d'Id (meme Id, identite differente) : une ligne par conflit
    # affichant les DEUX noms ET la propriete qui a declenche le conflit —
    # vecu 25/09 : memes Id+Name mais Model/TemplateRoot differents sur des
    # patchs +Block, le conflit semblait absurde sans la raison (le bloc est
    # de toute facon ajoute DESACTIVE en fin de fichier, ligne informative).
    for c in result.id_conflicts:
        diff_txt = " ; ".join(f"{k} : {va} -> {vb}"
                              for k, va, vb in c.differences)
        rows.append(MergePreviewRow(
            row_type='id_conflict',
            block_key=(normalized_kind(c.kind), c.identity),
            block_label=f"{normalized_kind(c.kind)} [{c.identity}]",
            prop_key=(f"Id {c.identity} — {diff_txt}" if diff_txt
                      else str(c.identity)),
            working_value=c.base_name or '(absent)',
            merged_value=c.conflicting_name or '(absent)',
            merged_block=None, working_key_present=True))
    return result, rows


class MergePreviewDialog(QDialog):
    """Tableau coche + avant + apres EDITABLE (meme esprit que l'apercu de la
    transformation en masse). N'ECRIT RIEN : `apply_selected()` mute le
    document fusionne en memoire ; l'appelant le serialise apres accept()."""

    COL_CHECK, COL_TYPE, COL_BLOCK, COL_KEY, COL_BEFORE, COL_AFTER = range(6)

    def __init__(self, working_doc, source_doc, source_label: str, parent=None,
                 precomputed=None):
        super().__init__(parent)
        self.setWindowTitle(t("mergepreview.title"))
        self.setMinimumSize(860, 560)
        from gui.window_geometry import track
        track(self, "merge_preview")

        # precomputed = resultat de compute_merge_preview deja calcule hors
        # du thread GUI (run_long, gerbe plasma) ; calcule ici sinon.
        if precomputed is not None:
            result, rows = precomputed
        else:
            result, rows = compute_merge_preview(working_doc, source_doc,
                                                 source_label)
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
            'id_conflict': t("mergepreview.type_id_conflict"),
        }
        for r, row in enumerate(rows):
            check = QTableWidgetItem()
            if row.row_type != 'id_conflict':
                check.setFlags(check.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            else:
                # les flags PAR DEFAUT incluent UserCheckable : retire
                # explicitement pour les lignes informatives (conflit d'Id)
                check.setFlags(check.flags()
                               & ~Qt.ItemFlag.ItemIsUserCheckable)
            # Blocs et proprietes AJOUTES : coches par defaut (la fusion les
            # apporte). Proprietes DIFFERENTES : decochees (la copie de
            # travail reste prioritaire tant que l'utilisateur ne choisit pas
            # explicitement la valeur source). Conflits d'Id : PAS de case
            # (informationnels — le bloc est ajoute desactive en fin de
            # fichier, avec son nom visible dans les colonnes Avant/Apres).
            check.setCheckState(Qt.CheckState.Checked if row.row_type == 'added_block'
                                or row.row_type == 'added_property'
                                else Qt.CheckState.Unchecked)
            self.table.setItem(r, self.COL_CHECK, check)

            item = QTableWidgetItem(type_labels[row.row_type])
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, self.COL_TYPE, item)

            item = QTableWidgetItem(row.block_label)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, self.COL_BLOCK, item)

            item = QTableWidgetItem(row.display_key or row.prop_key or "")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, self.COL_KEY, item)

            item = QTableWidgetItem(row.working_value)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, self.COL_BEFORE, item)

            after = row.merged_value if row.row_type != 'added_block' else ""
            item_after = QTableWidgetItem(after)
            if row.row_type in ('added_block', 'id_conflict'):
                item_after.setFlags(item_after.flags()
                                    & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, self.COL_AFTER, item_after)
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
            item = self.table.item(r, self.COL_CHECK)
            if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(cs)

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
        identity_blocks = {}
        for r, row in enumerate(self.rows):
            if row.row_type == 'id_conflict':
                continue            # informatif : rien a appliquer
            checked = self.table.item(r, self.COL_CHECK).checkState() == Qt.CheckState.Checked
            after = self.table.item(r, self.COL_AFTER).text()
            if row.row_type == 'added_block':
                if not checked and row.merged_block is not None:
                    blocks_to_remove.append(row.merged_block)
                continue
            if row.merged_block is None or not row.prop_key:
                continue
            if row.identity_paired and row.merged_block is not None:
                identity_blocks[id(row.merged_block)] = row.merged_block
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
        # listes ItemN appariees par identite : renumerote sans trou apres
        # les retraits d'ajouts decoches (Item1..N contigu pour le jeu)
        for block in identity_blocks.values():
            renumber_item_lines(block)

    def rejected_summary(self) -> int:
        """Nombre de lignes laissees decochees (pour le message de statut)."""
        count = 0
        for r in range(self.table.rowCount()):
            item = self.table.item(r, self.COL_CHECK)
            if (item.flags() & Qt.ItemFlag.ItemIsUserCheckable
                    and item.checkState() != Qt.CheckState.Checked):
                count += 1
        return count
