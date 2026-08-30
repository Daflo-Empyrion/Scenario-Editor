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
Widget d'edition pour un fichier .ecf de la COPIE DE TRAVAIL : contrairement a
EcfViewWidget (lecture seule, dans main_window.py), celui-ci permet de modifier une
valeur, ajouter/supprimer une propriete, ajouter/supprimer un bloc -- avec annotation
automatique de tracabilite sur chaque modification.

Contient aussi CompareWidget : une vue cote a cote (copie de travail modifiable a
gauche, source(s) A/B en lecture seule a droite, dans des onglets si les deux sont
disponibles) pour editer en gardant la reference sous les yeux, sans perdre d'espace
d'affichage a switcher entre onglets separes.
"""
from pathlib import Path
from typing import Dict, List, Optional
import re

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem, QTableWidget,
    QTableWidgetItem, QSplitter, QLabel, QLineEdit, QPushButton, QMenu, QMessageBox,
    QInputDialog, QTabWidget, QDialog, QListWidget, QListWidgetItem, QTextEdit, QSizePolicy,
    QApplication, QComboBox, QFormLayout, QDoubleSpinBox, QSpinBox, QCheckBox, QCompleter,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtWidgets import QTreeWidgetItemIterator
from PyQt6.QtGui import QColor, QBrush, QPixmap

from core.ecf.parser import parse_ecf_file, parse_ecf_text
from core.ecf.transform import TransformRule, preview_transform, format_block_label
from core.ecf.model import (
    EcfDocument, EcfBlock, EcfProperty, block_identity, normalized_kind,
    add_property_line, remove_property_line, remove_block, create_block, annotate_property,
    add_repeating_item_row, detect_repeating_items, _ITEM_KEY_RE,
    find_first_inline_comment_for_key, duplicate_block,
)
from core.ecf_header_glossary import find_term_explanation
from core.ecf.pending_conflicts import suggest_free_ids
from core import settings
from core.i18n import t
from gui.theme import icon, icon_size
from gui import theme as _theme
from gui.csv_edit_widget import TranslationResultDialog
from gui.text_tools import add_clipboard_menu_actions, install_clipboard_shortcuts, open_bbcode_tool

COLOR_MODIFIED_ROW = QBrush(QColor(255, 250, 200))  # jaune clair : ligne modifiee dans cette session


class DisabledBlocksDialog(QDialog):
    """Liste les blocs desactives (commentes) manuellement dans le fichier ouvert,
    avec un bouton pour les reactiver un par un -- utile pour tester l'elimination
    de causes probables d'un bug de lancement sans avoir a editer le fichier a la
    main."""

    def __init__(self, doc, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.reactivated = False
        self.setWindowTitle(t("ecf.disabled_blocks_title"))
        self.resize(500, 400)

        layout = QVBoxLayout(self)
        intro = QLabel(t("ecf.disabled_blocks_intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_reactivate = QPushButton(icon("fa5s.undo", "#ffffff"), t("ecf.reactivate_block"))
        self.btn_reactivate.setIconSize(icon_size())
        self.btn_reactivate.clicked.connect(self._reactivate_selected)
        btn_row.addWidget(self.btn_reactivate)
        btn_close = QPushButton(t("btn.close"))
        btn_close.setObjectName("secondaryButton")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

        self._refresh_list()

    def _refresh_list(self):
        from core.ecf.disable_block import find_disabled_blocks
        self.list_widget.clear()
        self.entries = find_disabled_blocks(self.doc)
        if not self.entries:
            item = QListWidgetItem(t("ecf.disabled_blocks_none"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(item)
            self.btn_reactivate.setEnabled(False)
            return
        self.btn_reactivate.setEnabled(True)
        for entry in self.entries:
            self.list_widget.addItem(entry.label)

    def _reactivate_selected(self):
        from core.ecf.disable_block import enable_disabled_block
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.entries):
            return
        entry = self.entries[row]
        if enable_disabled_block(self.doc, entry):
            self.reactivated = True
            self._refresh_list()


class PendingConflictsDialog(QDialog):
    """Fenetre de revue des blocs en attente : liste a gauche, comparaison detaillee
    (bloc actuel vs bloc en attente, via le moteur de diff) a droite, avec suggestion
    d'Id libres pour l'activation."""

    def __init__(self, entries: List[dict], used_ids: set, parent=None):
        """entries : liste de dict {path, conflict, pending_block, base_block}."""
        super().__init__(parent)
        self.setWindowTitle(t("pending.title"))
        self.setMinimumSize(900, 600)
        self.entries = entries
        self.used_ids = used_ids
        self.chosen_new_id: Optional[str] = None
        self.chosen_entry: Optional[dict] = None

        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.list_widget = QListWidget()
        for e in entries:
            ident = block_identity(e['pending_block']) if e['pending_block'] else "?"
            name = e['pending_block'].get_property('Name') if e['pending_block'] else "?"
            self.list_widget.addItem(f"{e['path'].name} -- Id {ident} ({name})")
        self.list_widget.currentRowChanged.connect(self._on_selection_changed)
        splitter.addWidget(self.list_widget)

        right = QWidget()
        right_layout = QVBoxLayout(right)

        right_layout.addWidget(QLabel(t("pending.compare_label")))
        self.diff_view = QTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setFontFamily("Consolas, monospace")
        right_layout.addWidget(self.diff_view)

        id_row = QHBoxLayout()
        id_row.addWidget(QLabel(t("pending.new_id_label")))
        self.id_edit = QLineEdit()
        id_row.addWidget(self.id_edit)
        right_layout.addLayout(id_row)

        self.suggestions_label = QLabel("")
        self.suggestions_label.setWordWrap(True)
        right_layout.addWidget(self.suggestions_label)

        splitter.addWidget(right)
        splitter.setSizes([300, 600])
        layout.addWidget(splitter)

        buttons = QHBoxLayout()
        btn_activate = QPushButton(t("pending.activate"))
        btn_activate.clicked.connect(self._on_activate)
        buttons.addWidget(btn_activate)
        btn_cancel = QPushButton(t("btn.close"))
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_cancel)
        layout.addLayout(buttons)

        if entries:
            self.list_widget.setCurrentRow(0)

    def _on_selection_changed(self, row: int):
        if row < 0 or row >= len(self.entries):
            return
        entry = self.entries[row]
        pending = entry['pending_block']
        base = entry['base_block']

        lines = []
        if base is None:
            lines.append(t("pending.no_base_block"))
            lines.append("")
            lines.append(pending.render() if pending else t("pending.read_error"))
        else:
            from core.ecf.diff import diff_documents, format_diff
            from core.ecf.model import EcfDocument
            doc_a = EcfDocument(nodes=[base])
            doc_b = EcfDocument(nodes=[pending])
            diffs = diff_documents(doc_a, doc_b)
            if diffs:
                lines.append(t("pending.differences_header"))
                lines.append("")
                lines.append(format_diff(diffs))
            else:
                lines.append(t("pending.no_diff"))
            lines.append("")
            lines.append(t("pending.active_block_header"))
            lines.append(base.render())
            lines.append("")
            lines.append(t("pending.pending_block_header"))
            lines.append(pending.render())

        self.diff_view.setPlainText("\n".join(lines))

        suggestions = suggest_free_ids(self.used_ids, 8)
        self.suggestions_label.setText(
            t("pending.suggestions_label", ids=", ".join(str(s) for s in suggestions))
        )
        self.id_edit.setText(str(suggestions[0]))

    def _on_activate(self):
        row = self.list_widget.currentRow()
        if row < 0:
            return
        new_id = self.id_edit.text().strip()
        if not new_id:
            QMessageBox.warning(self, t("pending.id_missing"), t("pending.id_missing_msg"))
            return
        if new_id.isdigit() and int(new_id) in self.used_ids:
            confirm = QMessageBox.question(
                self, t("pending.id_already_used"),
                t("pending.id_already_used_confirm", id=new_id)
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        self.chosen_entry = self.entries[row]
        self.chosen_new_id = new_id
        self.accept()


def _block_own_keys(block: EcfBlock) -> set:
    """Cles de proprietes DIRECTES d'un bloc (en-tete + lignes enfants directes, sans
    descendre dans les sous-blocs comme 'Child Items')."""
    keys = set()
    for k, v in block.pairs:
        if k:
            keys.add(k)
    for child in block.children:
        if isinstance(child, EcfProperty):
            for k, v in child.pairs:
                if k:
                    keys.add(k)
    return keys


class PropertyFilterDialog(QDialog):
    """Liste toutes les proprietes existantes dans un fichier (blocs de premier niveau)
    a cocher ; le filtre s'applique EN DIRECT sur l'arbre principal du fichier ouvert
    (masque les blocs qui n'ont pas toutes les proprietes cochees), via le callback
    `on_filter_changed`. Reste actif meme apres fermeture de cette fenetre."""

    def __init__(self, doc: EcfDocument, on_filter_changed, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("propfilter.title"))
        self.setMinimumSize(400, 500)
        self.on_filter_changed = on_filter_changed

        top_blocks = [n for n in doc.nodes if isinstance(n, EcfBlock)]
        key_counts: Dict[str, int] = {}
        for b in top_blocks:
            for k in _block_own_keys(b):
                key_counts[k] = key_counts.get(k, 0) + 1

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(t("propfilter.instructions")))

        self.prop_list = QListWidget()
        for key in sorted(key_counts.keys()):
            item = QListWidgetItem(f"{key}  ({key_counts[key]})")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.prop_list.addItem(item)
        self.prop_list.itemChanged.connect(self._on_checkbox_changed)
        layout.addWidget(self.prop_list)

        buttons = QHBoxLayout()
        btn_clear = QPushButton(t("propfilter.clear_all"))
        btn_clear.clicked.connect(self._clear_all)
        buttons.addWidget(btn_clear)
        btn_close = QPushButton(t("btn.close"))
        btn_close.setObjectName("secondaryButton")
        btn_close.clicked.connect(self.accept)
        buttons.addWidget(btn_close)
        layout.addLayout(buttons)

    def _checked_keys(self) -> List[str]:
        keys = []
        for i in range(self.prop_list.count()):
            item = self.prop_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                keys.append(item.data(Qt.ItemDataRole.UserRole))
        return keys

    def _on_checkbox_changed(self, _item):
        self.on_filter_changed(self._checked_keys())

    def _clear_all(self):
        self.prop_list.blockSignals(True)
        for i in range(self.prop_list.count()):
            self.prop_list.item(i).setCheckState(Qt.CheckState.Unchecked)
        self.prop_list.blockSignals(False)
        self.on_filter_changed([])


def _all_property_keys_recursive(doc: EcfDocument) -> dict:
    """Toutes les cles de propriete PRESENTES DANS LE CORPS des blocs (jamais sur
    leur ligne d'ouverture, ex: Id/Name -- coherent avec _find_matching_pairs()
    dans core/ecf/transform.py, qui exclut deliberement ces cles d'identite pour ne
    jamais les toucher par erreur), y compris a l'interieur des sous-blocs comme
    'Child Items' -- avec leur nombre d'occurrences. Contrairement a
    _block_own_keys() (utilisee par le filtre de proprietes classique), qui reste
    volontairement limitee aux proprietes directes d'un bloc, la transformation en
    masse cible tres souvent des cles imbriquees (ex: param1 dans les listes
    d'items), d'ou cette version recursive dediee."""
    counts: dict = {}

    def _walk(nodes):
        for node in nodes:
            if isinstance(node, EcfBlock):
                _walk(node.children)
            elif isinstance(node, EcfProperty):
                for k, v in node.pairs:
                    if k:
                        counts[k] = counts.get(k, 0) + 1

    _walk(doc.nodes)
    return counts


class TransformDialog(QDialog):
    """Transformation numerique en masse sur une cle de propriete (multiplier,
    ajouter, fixer, plafonner, arrondir), avec apercu obligatoire avant application
    -- reprend exactement le moteur de transform_ecf.py (core/ecf/transform.py),
    deja utilise et teste par l'outil en ligne de commande equivalent."""

    def __init__(self, doc: EcfDocument, on_before_apply, on_after_apply, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.on_before_apply = on_before_apply
        self.on_after_apply = on_after_apply
        self._preview_changes = []

        self.setWindowTitle(t("transform.title"))
        self.setMinimumSize(700, 560)
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText(t("transform.key_placeholder"))
        form.addRow(t("transform.key_label"), self.key_input)

        layout.addLayout(form)

        # Liste des cles reellement presentes dans le fichier (avec nombre
        # d'occurrences), cochables -- alternative au clavier pour choisir une cle
        # sans risque de faute de frappe. Cocher une entree remplit automatiquement
        # le champ ci-dessus et decoche les autres (une seule cle active a la fois,
        # comme le reste du dialogue). Le champ texte reste utilisable directement
        # en tapant, avec autocompletion (QCompleter, voir plus bas) sur ces memes
        # cles -- pratique si la cle voulue n'est pas visible sans defiler.
        layout.addWidget(QLabel(t("transform.available_keys_label")))
        self._all_keys = _all_property_keys_recursive(doc)
        self.keys_list = QListWidget()
        self.keys_list.setMaximumHeight(110)
        for key in sorted(self._all_keys.keys()):
            item = QListWidgetItem(f"{key}  ({self._all_keys[key]})")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.keys_list.addItem(item)
        self.keys_list.itemChanged.connect(self._on_key_checkbox_changed)
        layout.addWidget(self.keys_list)

        completer = QCompleter(sorted(self._all_keys.keys()), self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.key_input.setCompleter(completer)
        self.key_input.textEdited.connect(self._on_key_typed_manually)

        form = QFormLayout()
        self.op_combo = QComboBox()
        self.op_combo.addItem(t("transform.op_multiply"), "multiply")
        self.op_combo.addItem(t("transform.op_add"), "add")
        self.op_combo.addItem(t("transform.op_set"), "set")
        self.op_combo.addItem(t("transform.op_clamp"), "clamp")
        self.op_combo.addItem(t("transform.op_round"), "round")
        self.op_combo.currentIndexChanged.connect(self._update_field_visibility)
        form.addRow(t("transform.op_label"), self.op_combo)

        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(-1_000_000, 1_000_000)
        self.amount_spin.setDecimals(4)
        self.amount_spin.setValue(1.0)
        self.amount_row_label = QLabel(t("transform.amount_label"))
        form.addRow(self.amount_row_label, self.amount_spin)

        self.min_check = QCheckBox(t("transform.enable_min"))
        self.min_spin = QDoubleSpinBox()
        self.min_spin.setRange(-1_000_000, 1_000_000)
        self.min_spin.setDecimals(4)
        self.min_spin.setEnabled(False)
        self.min_check.toggled.connect(self.min_spin.setEnabled)
        min_row = QHBoxLayout()
        min_row.addWidget(self.min_check)
        min_row.addWidget(self.min_spin)
        self.min_row_label = QLabel(t("transform.min_label"))
        form.addRow(self.min_row_label, min_row)

        self.max_check = QCheckBox(t("transform.enable_max"))
        self.max_spin = QDoubleSpinBox()
        self.max_spin.setRange(-1_000_000, 1_000_000)
        self.max_spin.setDecimals(4)
        self.max_spin.setEnabled(False)
        self.max_check.toggled.connect(self.max_spin.setEnabled)
        max_row = QHBoxLayout()
        max_row.addWidget(self.max_check)
        max_row.addWidget(self.max_spin)
        self.max_row_label = QLabel(t("transform.max_label"))
        form.addRow(self.max_row_label, max_row)

        self.ndigits_spin = QSpinBox()
        self.ndigits_spin.setRange(0, 10)
        self.ndigits_spin.setValue(2)
        self.ndigits_row_label = QLabel(t("transform.ndigits_label"))
        form.addRow(self.ndigits_row_label, self.ndigits_spin)

        self.kind_combo = QComboBox()
        self.kind_combo.setEditable(True)
        self.kind_combo.addItem(t("transform.all_kinds"), None)
        known_kinds = sorted({b.kind for b in doc.nodes if isinstance(b, EcfBlock) and b.kind})
        for kind in known_kinds:
            self.kind_combo.addItem(kind, kind)
        form.addRow(t("transform.kind_label"), self.kind_combo)

        self.ids_input = QLineEdit()
        self.ids_input.setPlaceholderText(t("transform.ids_placeholder"))
        form.addRow(t("transform.ids_label"), self.ids_input)

        self.recursive_check = QCheckBox(t("transform.recursive_label"))
        self.recursive_check.setChecked(True)
        form.addRow("", self.recursive_check)

        layout.addLayout(form)

        layout.addWidget(QLabel(t("transform.report_label")))
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels([
            "", t("transform.col_block"), t("transform.col_key"),
            t("transform.col_old"), t("transform.col_new"),
        ])
        self.results_table.setColumnWidth(0, 30)
        self.results_table.setColumnWidth(1, 140)
        self.results_table.setColumnWidth(2, 100)
        self.results_table.setColumnWidth(3, 90)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setMinimumHeight(220)
        self.results_table.itemChanged.connect(self._update_apply_count)
        layout.addWidget(self.results_table)

        self.skipped_label = QLabel("")
        self.skipped_label.setWordWrap(True)
        layout.addWidget(self.skipped_label)

        check_row = QHBoxLayout()
        btn_check_all = QPushButton(t("trans.check_all"))
        btn_check_all.setObjectName("secondaryButton")
        btn_check_all.clicked.connect(lambda: self._set_all_checked(True))
        check_row.addWidget(btn_check_all)
        btn_uncheck_all = QPushButton(t("trans.uncheck_all"))
        btn_uncheck_all.setObjectName("secondaryButton")
        btn_uncheck_all.clicked.connect(lambda: self._set_all_checked(False))
        check_row.addWidget(btn_uncheck_all)
        check_row.addStretch()
        layout.addLayout(check_row)

        buttons = QHBoxLayout()
        self.btn_preview = QPushButton(t("transform.btn_preview"))
        self.btn_preview.clicked.connect(self._do_preview)
        buttons.addWidget(self.btn_preview)
        self.btn_apply = QPushButton(t("transform.btn_apply"))
        self.btn_apply.setObjectName("primaryButton")
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self._do_apply)
        buttons.addWidget(self.btn_apply)
        btn_close = QPushButton(t("btn.close"))
        btn_close.setObjectName("secondaryButton")
        btn_close.clicked.connect(self.accept)
        buttons.addWidget(btn_close)
        layout.addLayout(buttons)

        self._update_field_visibility()

    def _on_key_checkbox_changed(self, changed_item):
        """Cocher une entree de la liste des cles disponibles : decoche toutes les
        autres (une seule cle active a la fois) et remplit le champ texte -- comme
        cocher une case de type radio, mais via une liste plus lisible qu'un
        QComboBox pour un grand nombre de cles avec leur nombre d'occurrences."""
        if changed_item.checkState() != Qt.CheckState.Checked:
            return
        self.keys_list.blockSignals(True)
        for i in range(self.keys_list.count()):
            item = self.keys_list.item(i)
            if item is not changed_item:
                item.setCheckState(Qt.CheckState.Unchecked)
        self.keys_list.blockSignals(False)
        self.key_input.setText(changed_item.data(Qt.ItemDataRole.UserRole))
        self._update_field_visibility()

    def _on_key_typed_manually(self, _text):
        """Taper directement dans le champ decoche toute selection faite dans la
        liste -- evite un etat incoherent ou la liste montrerait une cle cochee
        differente de celle effectivement tapee."""
        self.keys_list.blockSignals(True)
        for i in range(self.keys_list.count()):
            self.keys_list.item(i).setCheckState(Qt.CheckState.Unchecked)
        self.keys_list.blockSignals(False)

    def _update_field_visibility(self):
        op = self.op_combo.currentData()
        needs_amount = op in ("multiply", "add", "set")
        needs_clamp = op == "clamp"
        needs_ndigits = op == "round"
        for w in (self.amount_row_label, self.amount_spin):
            w.setVisible(needs_amount)
        for w in (self.min_row_label, self.min_check, self.min_spin):
            w.setVisible(needs_clamp)
        for w in (self.max_row_label, self.max_check, self.max_spin):
            w.setVisible(needs_clamp)
        for w in (self.ndigits_row_label, self.ndigits_spin):
            w.setVisible(needs_ndigits)
        # Toute modification des reglages invalide l'apercu precedent -- il faut
        # revoir le tableau avant de pouvoir appliquer, pour ne jamais appliquer une
        # combinaison jamais previsualisee.
        self.results_table.setRowCount(0)
        self._preview_changes = []
        self.skipped_label.setText("")
        self.btn_apply.setEnabled(False)

    def _build_rule(self):
        key = self.key_input.text().strip()
        if not key:
            QMessageBox.warning(self, t("transform.title"), t("transform.error_no_key"))
            return None
        op = self.op_combo.currentData()

        amount = self.amount_spin.value() if op in ("multiply", "add", "set") else None
        min_value = self.min_spin.value() if (op == "clamp" and self.min_check.isChecked()) else None
        max_value = self.max_spin.value() if (op == "clamp" and self.max_check.isChecked()) else None
        if op == "clamp" and min_value is None and max_value is None:
            QMessageBox.warning(self, t("transform.title"), t("transform.error_no_clamp_bound"))
            return None

        kind_text = self.kind_combo.currentText().strip()
        all_kinds_label = t("transform.all_kinds")
        # currentData() n'est pas fiable sur un QComboBox editable une fois du texte
        # affiche (renvoie souvent None meme index inchange, ou l'inverse selon la
        # plateforme Qt) -- comparaison textuelle explicite plus robuste ici : le
        # libelle "(tous les genres)" ou un champ vide signifient tous deux "aucun
        # filtre", tout autre texte est un genre de bloc tape ou choisi.
        kind = None if kind_text in ("", all_kinds_label) else kind_text

        ids_text = self.ids_input.text().strip()
        block_ids = [s.strip() for s in ids_text.split(",") if s.strip()] if ids_text else None

        return TransformRule(
            property_key=key,
            operation=op,
            amount=amount,
            min_value=min_value,
            max_value=max_value,
            ndigits=self.ndigits_spin.value(),
            block_kind=kind,
            block_ids=block_ids,
            recursive=self.recursive_check.isChecked(),
        )

    def _set_all_checked(self, checked: bool):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self.results_table.rowCount()):
            self.results_table.item(i, 0).setCheckState(state)

    def _update_apply_count(self, item):
        if item is not None and item.column() != 0:
            return  # seule la case a cocher change le compte -- une edition de
            # valeur ne doit pas re-décompter, juste rester prise en compte a
            # l'application
        count = sum(1 for i in range(self.results_table.rowCount())
                    if self.results_table.item(i, 0).checkState() == Qt.CheckState.Checked)
        self.btn_apply.setText(t("transform.btn_apply_count", count=count))
        self.btn_apply.setEnabled(count > 0)

    def _do_preview(self):
        rule = self._build_rule()
        if rule is None:
            return
        # Calcule directement sur le VRAI document (preview_transform ne mute jamais
        # rien -- voir core/ecf/transform.py) : les references (prop_node,
        # pair_index) capturees restent valides pour une application ulterieure
        # exacte, y compris apres edition manuelle d'une valeur dans le tableau.
        report = preview_transform(self.doc, rule)
        self._preview_changes = report.changes

        self.results_table.blockSignals(True)
        self.results_table.setRowCount(len(report.changes))
        for i, change in enumerate(report.changes):
            check_item = QTableWidgetItem()
            check_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            check_item.setCheckState(Qt.CheckState.Checked)
            self.results_table.setItem(i, 0, check_item)

            label = format_block_label(change)
            block_item = QTableWidgetItem(label)
            block_item.setFlags(block_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.results_table.setItem(i, 1, block_item)

            key_item = QTableWidgetItem(change.property_key)
            key_item.setFlags(key_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.results_table.setItem(i, 2, key_item)

            old_item = QTableWidgetItem(change.old_value)
            old_item.setFlags(old_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.results_table.setItem(i, 3, old_item)

            # Colonne EDITABLE -- pre-remplie avec la valeur calculee automatiquement,
            # mais ajustable a la main avant application (ex: forcer MaxCount a 1 sur
            # un bloc precis a cause d'une limite du moteur du jeu, malgre la regle
            # generale appliquee au reste du fichier).
            new_item = QTableWidgetItem(change.new_value)
            self.results_table.setItem(i, 4, new_item)
        self.results_table.resizeRowsToContents()
        self.results_table.blockSignals(False)

        if report.skipped_non_numeric:
            self.skipped_label.setText(t("transform.skipped_non_numeric", count=report.skipped_non_numeric))
        else:
            self.skipped_label.setText("")

        self._update_apply_count(None)
        if not report.changes:
            QMessageBox.information(self, t("transform.title"), t("transform.no_changes"))

    def _do_apply(self):
        applied_count = 0
        for i, change in enumerate(self._preview_changes):
            check_item = self.results_table.item(i, 0)
            if check_item.checkState() != Qt.CheckState.Checked:
                continue
            final_value = self.results_table.item(i, 4).text()
            if applied_count == 0:
                self.on_before_apply()  # snapshot undo une seule fois, avant la 1ere ecriture reelle
            change.prop_node.pairs[change.pair_index] = (change.property_key, final_value)
            change.prop_node.dirty = True
            applied_count += 1

        if applied_count == 0:
            return

        self.on_after_apply()
        QMessageBox.information(self, t("transform.title"),
                                 t("transform.applied_msg", count=applied_count))
        self.results_table.setRowCount(0)
        self._preview_changes = []
        self.btn_apply.setEnabled(False)
        self.btn_apply.setText(t("transform.btn_apply"))


class EcfHeaderExplanationPanel(QWidget):
    """Panneau retractable (replie par defaut) affichant une explication claire des
    commentaires techniques d'en-tete d'un fichier ECF -- place entre le nom du fichier
    et la barre de recherche. Pour les fichiers ayant un glossaire dedie (voir
    core/ecf_header_glossary.py -- GLOSSARY_BY_FILE), affiche une explication francaise
    clarifiee faite main ; pour les autres, montre le texte original brut avec un
    bouton de traduction automatique a la demande (reutilise le meme moteur de
    traduction que l'onglet CSV)."""

    def __init__(self, doc: EcfDocument, filename: str, parent=None):
        super().__init__(parent)
        from core.ecf_header_glossary import GLOSSARY_BY_FILE
        self._header_text = doc.extract_header_comment()
        self._glossary = GLOSSARY_BY_FILE.get(filename)
        self._has_glossary = self._glossary is not None
        self._showing_raw = False
        self._translated_cache: Optional[str] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        if not self._header_text:
            self.setVisible(False)
            return

        self.toggle_btn = QPushButton(icon("fa5s.info-circle", "#4a7dfc"), t("ecf.header_toggle_show"))
        self.toggle_btn.setObjectName("secondaryButton")
        self.toggle_btn.clicked.connect(self._toggle)
        layout.addWidget(self.toggle_btn)

        self.content = QTextEdit()
        self.content.setReadOnly(True)
        self.content.setVisible(False)
        self.content.setMaximumHeight(220)
        layout.addWidget(self.content)

        btn_row = QHBoxLayout()
        self.btn_raw_toggle = QPushButton(t("ecf.header_raw_toggle"))
        self.btn_raw_toggle.setObjectName("secondaryButton")
        self.btn_raw_toggle.setVisible(False)
        self.btn_raw_toggle.clicked.connect(self._toggle_raw)
        btn_row.addWidget(self.btn_raw_toggle)

        self.btn_translate = QPushButton(icon("fa5s.language", "#4a7dfc"), t("ecf.header_translate_btn"))
        self.btn_translate.setObjectName("secondaryButton")
        self.btn_translate.setVisible(False)
        self.btn_translate.clicked.connect(self._translate)
        btn_row.addWidget(self.btn_translate)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _toggle(self):
        expanded = not self.content.isVisible()
        self.content.setVisible(expanded)
        self.toggle_btn.setText(t("ecf.header_toggle_hide") if expanded else t("ecf.header_toggle_show"))
        self.btn_raw_toggle.setVisible(expanded and self._has_glossary)
        self.btn_translate.setVisible(expanded and not self._has_glossary)
        if expanded:
            self._render_content()

    def _render_content(self):
        if self._has_glossary and not self._showing_raw:
            self._render_glossary()
        elif self._translated_cache:
            self.content.setPlainText(self._translated_cache)
        else:
            self.content.setPlainText(self._header_text)

    def _render_glossary(self):
        parts = [f"<p><i>{t('ecf.header_glossary_intro')}</i></p>"]
        for section_title, entries in self._glossary:
            parts.append(f"<p style='margin-top:8px'><b>{section_title}</b></p><ul style='margin-top:0'>")
            for term, explanation in entries:
                parts.append(f"<li><b>{term}</b> : {explanation}</li>")
            parts.append("</ul>")
        self.content.setHtml("".join(parts))

    def _toggle_raw(self):
        self._showing_raw = not self._showing_raw
        self.btn_raw_toggle.setText(
            t("ecf.header_toggle_show") if self._showing_raw else t("ecf.header_raw_toggle"))
        self._render_content()

    def _translate(self):
        from core import translation
        if not translation.is_available():
            QMessageBox.warning(self, t("err.title"), "deep-translator n'est pas installe.")
            return
        self.content.setPlainText(t("ecf.header_translating"))
        QApplication.processEvents()
        try:
            self._translated_cache = translation.translate_text(self._header_text, target="fr")
        except Exception as e:
            QMessageBox.warning(self, t("err.title"), t("ecf.header_translate_error", error=str(e)))
            self.content.setPlainText(self._header_text)
            return
        self.content.setPlainText(self._translated_cache)


class AddTableRowDialog(QDialog):
    """Formulaire d'ajout d'une ligne au mode tableau (Child Items, Child Inputs, mais
    aussi Item_x dans LootGroups.ecf, DamageMultiplier_N dans DamageMultiplierConfig.ecf,
    et toute autre structure suivant la meme convention 'Prefixe_N') : un champ par
    colonne detectee, plus le choix du prefixe (Type) -- la numerotation (Name_6,
    Item_3, DamageMultiplier_7...) est calculee automatiquement par l'appli, jamais
    saisie a la main."""

    def __init__(self, param_columns: List[str], prefixes: List[str], parent=None,
                 value_suggestions: Optional[List[str]] = None,
                 value_suggestions_players_only: Optional[List[str]] = None):
        """value_suggestions : si fourni (ex: noms reels d'ItemsConfig.ecf/
        BlocksConfig.ecf pour LootGroups.ecf), le champ Valeur devient un menu
        deroulant EDITABLE peuple de ces noms plutot qu'un champ de texte libre --
        reste modifiable si aucune suggestion ne convient, comme partout ailleurs
        dans l'application ou ce motif est deja utilise (creation de bloc,
        ingredients de Template).

        value_suggestions_players_only : meme liste, filtree aux seuls blocs
        posables par un joueur (voir core.ecf.block_creation.list_craftable_names,
        players_only=True) -- si fourni, une case a cocher permet de basculer
        entre les deux listes sans fermer le dialogue."""
        super().__init__(parent)
        self.setWindowTitle(t("ecf.add_row_title"))
        self.param_columns = param_columns
        self._value_suggestions_all = value_suggestions or []
        self._value_suggestions_players_only = value_suggestions_players_only or []

        layout = QFormLayout(self)
        self.type_combo = QComboBox()
        self.type_combo.addItems(prefixes if prefixes else ["Name", "Group"])
        self.type_combo.setEditable(True)  # au cas ou l'utilisateur veut un NOUVEAU
                                            # prefixe absent du bloc jusqu'ici
        layout.addRow(t("ecf.add_row_type_label"), self.type_combo)

        if value_suggestions:
            self.value_edit = QComboBox()
            self.value_edit.setEditable(True)
            self.value_edit.addItems(value_suggestions)
            self.value_edit.setCurrentText("")
        else:
            self.value_edit = QLineEdit()
        layout.addRow(t("ecf.add_row_value_label"), self.value_edit)

        if value_suggestions and value_suggestions_players_only is not None:
            self.players_only_check = QCheckBox(t("ecf.players_only_checkbox"))
            self.players_only_check.setToolTip(t("ecf.tooltip_players_only"))
            self.players_only_check.toggled.connect(self._on_players_only_toggled)
            layout.addRow("", self.players_only_check)
        else:
            self.players_only_check = None

        self.param_edits: Dict[str, QLineEdit] = {}
        for col in param_columns:
            edit = QLineEdit()
            self.param_edits[col] = edit
            layout.addRow(f"{col} :", edit)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton(t("ecf.add_row_title"))
        btn_ok.clicked.connect(self._on_accept)
        btn_row.addWidget(btn_ok)
        btn_cancel = QPushButton(t("btn.cancel"))
        btn_cancel.setObjectName("secondaryButton")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        layout.addRow(btn_row)

        self.result_type = None
        self.result_value = None
        self.result_extra_pairs: List[tuple] = []

    def _on_players_only_toggled(self, checked: bool):
        """Rebascule le contenu du menu deroulant Valeur entre la liste complete
        et la liste filtree aux blocs posables par un joueur, en conservant le
        texte deja saisi (le champ reste editable dans tous les cas)."""
        if not isinstance(self.value_edit, QComboBox):
            return
        current_text = self.value_edit.currentText()
        self.value_edit.clear()
        source = self._value_suggestions_players_only if checked else self._value_suggestions_all
        self.value_edit.addItems(source)
        self.value_edit.setCurrentText(current_text)

    def _get_value_text(self) -> str:
        """Lit le texte du champ Valeur, qu'il s'agisse d'un QLineEdit (cas
        general) ou d'un QComboBox editable (cas LootGroups.ecf, voir
        __init__)."""
        if isinstance(self.value_edit, QComboBox):
            return self.value_edit.currentText().strip()
        return self.value_edit.text().strip()

    def _on_accept(self):
        if not self._get_value_text():
            QMessageBox.warning(self, t("err.missing_field"), t("ecf.add_row_value_required"))
            return
        self.result_type = self.type_combo.currentText()
        self.result_value = self._get_value_text()
        self.result_extra_pairs = [
            (col, edit.text().strip()) for col, edit in self.param_edits.items() if edit.text().strip()
        ]
        self.accept()


class EcfEditWidget(QWidget):
    """Editeur d'un fichier .ecf de la copie de travail. Emet `modified_changed(bool)`
    quand l'etat 'modifications non enregistrees' change, pour que le conteneur (onglet)
    puisse afficher un indicateur."""

    modified_changed = pyqtSignal(bool)
    saved = pyqtSignal()

    def __init__(self, path: Path, sibling_ecf_files: Optional[List[Path]] = None,
                 working_root: Optional[Path] = None):
        super().__init__()
        self.path = path
        self.doc: EcfDocument = parse_ecf_file(path)
        self._modified = False
        self._current_block: Optional[EcfBlock] = None
        self._table_mode = False
        self._edited_prop_nodes = set()  # ids Python des EcfProperty touches cette session
        # Chemins des autres fichiers .ecf du meme scenario (Content/Configuration) --
        # utilise par le dialogue de creation guidee pour localiser Templates.ecf/
        # ItemsConfig.ecf/BlocksConfig.ecf lors de la proposition de creation du
        # Template associe. None si ce widget n'a pas ete ouvert depuis un scenario
        # complet (ex: fichier isole) -- le dialogue gere ce cas en desactivant
        # simplement la proposition de Template.
        self.sibling_ecf_files = sibling_ecf_files
        # Racine de la copie de travail -- utilise UNIQUEMENT pour resoudre les
        # icones reelles lors de la previsualisation dans l'arbre technologique
        # (voir gui/tech_tree_preview_dialog.py). None si absent (memes cas que
        # sibling_ecf_files ci-dessus) -- la previsualisation retombe alors sur
        # l'icone generique pour tous les noeuds.
        self.working_root = working_root
        # Fiche d'information flottante (voir gui/block_info_card_widget.py,
        # core/block_info_card.py) -- caches lazy pour la localisation/les
        # icones (statiques le temps d'une session) ; Templates.ecf N'EST
        # JAMAIS mis en cache ici (voir _get_info_card_templates_doc -- doit
        # toujours refleter l'etat le plus a jour, y compris un Template
        # tout juste cree par duplication et encore non enregistre).
        self._info_card = None
        self._info_card_localization_index = None
        self._info_card_icon_index = None
        self._undo_stack: list = []  # textes serialises (fidelite deja prouvee par le parser)
        self._undo_max = 20

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)
        filename_label = QLabel(f"{path.name}  ({t('status.editable')})")
        filename_label.setStyleSheet("font-size: 11px; color: gray; padding: 0px;")
        filename_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(filename_label, 0)

        self.header_panel = EcfHeaderExplanationPanel(self.doc, path.name)
        layout.addWidget(self.header_panel, 0)

        search_row = QHBoxLayout()
        search_row.setSpacing(4)
        search_row.addWidget(QLabel(t("label.search")))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Id / Name / CustomIcon...")
        self.search_box.addAction(icon("fa5s.search", color="#7c859c"), QLineEdit.ActionPosition.LeadingPosition)
        self.search_box.returnPressed.connect(self._search_next)
        search_row.addWidget(self.search_box)
        self.search_status = QLabel("")
        search_row.addWidget(self.search_status)
        layout.addLayout(search_row, 0)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)
        btn_add_block = QPushButton(icon("fa5s.plus", "#ffffff"), t("btn.add_block"))
        btn_add_block.setIconSize(icon_size())
        btn_add_block.clicked.connect(self._add_block_dialog)
        toolbar.addWidget(btn_add_block)
        self.btn_add_prop = QPushButton(icon("fa5s.plus", "#ffffff"), t("btn.add_property"))
        self.btn_add_prop.setIconSize(icon_size())
        self.btn_add_prop.clicked.connect(self._add_property_dialog)
        toolbar.addWidget(self.btn_add_prop)
        self.btn_add_row = QPushButton(icon("fa5s.plus", "#ffffff"), t("btn.add_row_table"))
        self.btn_add_row.setIconSize(icon_size())
        self.btn_add_row.clicked.connect(self._add_table_row_dialog)
        self.btn_add_row.setVisible(False)
        toolbar.addWidget(self.btn_add_row)
        btn_filter = QPushButton(icon("fa5s.filter", "#4a7dfc"), t("btn.filter_by_property"))
        btn_filter.setIconSize(icon_size())
        btn_filter.setObjectName("secondaryButton")
        btn_filter.clicked.connect(self._open_property_filter)
        toolbar.addWidget(btn_filter)
        btn_disabled_blocks = QPushButton(icon("fa5s.ban", "#4a7dfc"), t("ecf.disabled_blocks_menu"))
        btn_disabled_blocks.setIconSize(icon_size())
        btn_disabled_blocks.setObjectName("secondaryButton")
        btn_disabled_blocks.clicked.connect(self._open_disabled_blocks_dialog)
        toolbar.addWidget(btn_disabled_blocks)
        btn_transform = QPushButton(icon("fa5s.calculator", "#4a7dfc"), t("btn.transform"))
        btn_transform.setIconSize(icon_size())
        btn_transform.setObjectName("secondaryButton")
        btn_transform.clicked.connect(self._open_transform_dialog)
        toolbar.addWidget(btn_transform)
        self.btn_undo = QPushButton(icon("fa5s.undo", "#7c859c"), t("btn.undo"))
        self.btn_undo.setIconSize(icon_size())
        self.btn_undo.setObjectName("secondaryButton")
        self.btn_undo.clicked.connect(self.undo)
        self.btn_undo.setEnabled(False)
        toolbar.addWidget(self.btn_undo)
        btn_save = QPushButton(icon("fa5s.save", "#ffffff"), t("btn.save"))
        btn_save.setIconSize(icon_size())
        btn_save.clicked.connect(self.save)
        toolbar.addWidget(btn_save)
        toolbar.addStretch()
        layout.addLayout(toolbar, 0)

        from PyQt6.QtGui import QKeySequence, QShortcut
        QShortcut(QKeySequence.StandardKey.Undo, self, activated=self.undo)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Bloc"])
        self._populate_tree()
        self.tree.itemClicked.connect(self._on_block_selected)
        self.tree.itemClicked.connect(self._on_tree_item_clicked_for_info_card)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_tree_context_menu)
        splitter.addWidget(self.tree)

        self.props_table = QTableWidget(0, 2)
        self.props_table.setHorizontalHeaderLabels(["Propriete", "Valeur"])
        self.props_table.horizontalHeader().setStretchLastSection(True)
        self.props_table.itemChanged.connect(self._on_cell_changed)
        self.props_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.props_table.customContextMenuRequested.connect(self._show_table_context_menu)
        install_clipboard_shortcuts(self.props_table, allow_new_rows=False)
        splitter.addWidget(self.props_table)

        splitter.setSizes([400, 500])
        layout.addWidget(splitter, 1)

        self._search_matches: list = []
        self._search_index = -1
        self._search_last_query = ""

    # ------------------------------------------------------------------
    # Etat modifie / enregistrement
    # ------------------------------------------------------------------

    def _set_modified(self, value: bool):
        if value != self._modified:
            self._modified = value
            self.modified_changed.emit(value)

    def is_modified(self) -> bool:
        return self._modified

    def save(self):
        try:
            from core.fsutil import atomic_write_text
            atomic_write_text(self.path, self.doc.render())
        except OSError as e:
            QMessageBox.critical(self, t("save.error_title"),
                                  t("save.error_msg", name=self.path.name, error=str(e)))
            return
        self._set_modified(False)
        self.saved.emit()

    def _get_content_for_autosave(self) -> str:
        """Contenu actuel (non enregistre) pour un instantane de recuperation
        -- voir core/autosave.py. Duplique volontairement la logique de
        preparation du contenu de save() ci-dessus plutot que de la
        reutiliser directement, pour ne jamais risquer de perturber le
        chemin critique d'enregistrement reel."""
        return self.doc.render()

    def _snapshot_undo(self):
        """A appeler AVANT toute modification -- sauvegarde l'etat actuel du document
        (texte serialise ; fidelite deja prouvee par le parser) pour pouvoir l'annuler."""
        self._undo_stack.append(self.doc.render())
        if len(self._undo_stack) > self._undo_max:
            self._undo_stack.pop(0)
        self.btn_undo.setEnabled(True)

    def undo(self):
        if not self._undo_stack:
            return
        previous_text = self._undo_stack.pop()
        self.doc = parse_ecf_text(previous_text)
        self._current_block = None
        self.props_table.setRowCount(0)
        self._populate_tree()
        self._set_modified(True)
        if not self._undo_stack:
            self.btn_undo.setEnabled(False)

    # ------------------------------------------------------------------
    # Arbre des blocs
    # ------------------------------------------------------------------

    def _populate_tree(self):
        self.tree.clear()
        group_before, label_by_block_id = self.doc.scan_section_groups_and_labels()
        self._label_by_block_id = label_by_block_id
        for index, node in enumerate(self.doc.nodes):
            if index in group_before:
                self.tree.addTopLevelItem(self._make_group_header_item(group_before[index]))
            if isinstance(node, EcfBlock):
                self.tree.addTopLevelItem(self._make_block_item(node))

    def _make_group_header_item(self, title: str) -> QTreeWidgetItem:
        """Ligne de section non selectionnable (juste un repere visuel), pour les
        groupes de blocs annonces par un commentaire '# === Titre ===' dans le fichier
        source -- aide a s'y retrouver dans les tres longs fichiers (ex: Containers.ecf
        classe ses centaines de blocs en categories comme 'Gigas', 'Dinosaurs',
        'Zirax'...)."""
        item = QTreeWidgetItem([f"\u25a0 {title}"])
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setForeground(0, QBrush(QColor(_theme.PRIMARY_DARK)))
        font = item.font(0)
        font.setBold(True)
        item.setFont(0, font)
        return item

    def _make_block_item(self, block: EcfBlock) -> QTreeWidgetItem:
        ident = block_identity(block)
        label = f"{block.kind} [{ident}]" if ident else block.kind
        name = block.get_property('Name')
        if name and name != ident:
            label += f"  - {name}"
        friendly = self._label_by_block_id.get(id(block)) if hasattr(self, '_label_by_block_id') else None
        if friendly:
            label += f"   ({friendly})"
        item = QTreeWidgetItem([label])
        item.setData(0, Qt.ItemDataRole.UserRole, block)
        for child in block.children:
            if isinstance(child, EcfBlock):
                item.addChild(self._make_block_item(child))
        return item

    def _search_next(self):
        query = self.search_box.text().strip().lower()
        if not query:
            return
        if not self._search_matches or self._search_last_query != query:
            self._search_matches = []
            it = QTreeWidgetItemIterator(self.tree)
            while it.value():
                item = it.value()
                block = item.data(0, Qt.ItemDataRole.UserRole)
                searchable = item.text(0).lower()
                if isinstance(block, EcfBlock):
                    for key in ('Name', 'CustomIcon', 'TemplateRoot', 'IndexName'):
                        val = block.get_property(key)
                        if val:
                            searchable += " " + val.lower()
                if query in searchable:
                    self._search_matches.append(item)
                it += 1
            self._search_index = -1
            self._search_last_query = query

        if not self._search_matches:
            self.search_status.setText("Aucun resultat")
            return
        self._search_index = (self._search_index + 1) % len(self._search_matches)
        item = self._search_matches[self._search_index]
        self.tree.setCurrentItem(item)
        self.tree.scrollToItem(item)
        self._on_block_selected(item, 0)
        self.search_status.setText(f"{self._search_index + 1} / {len(self._search_matches)}")

    def select_block_by_identity(self, identity: str, prop_key: Optional[str] = None,
                                  prop_value: Optional[str] = None) -> bool:
        """Trouve et selectionne (dans l'arbre, avec defilement) le bloc RACINE dont
        l'identite (Id ou Name) correspond EXACTEMENT a `identity` -- contrairement a
        _search_next() qui fait une recherche floue par sous-chaine, celle-ci sert a
        naviguer directement depuis un resultat deja identifie avec precision (ex:
        double-clic sur un resultat du dialogue "References croisees") sans repasser
        par la recherche manuelle.

        Si prop_key/prop_value sont fournis, cherche en plus le sous-bloc EXACT qui
        contient cette paire directement (ex: le sous-bloc "Child Items" imbrique
        dans un +Container, pas le +Container racine lui-meme) et selectionne CE
        sous-bloc precis plutot que la racine -- necessaire pour que la ligne
        recherchee soit effectivement visible dans le tableau de proprietes affiche
        ensuite, puisque les valeurs d'un sous-bloc n'apparaissent jamais dans le
        tableau de son parent. Retourne True si le bloc racine a ete trouve (que la
        propriete precise ait pu etre localisee ou non)."""
        it = QTreeWidgetItemIterator(self.tree)
        root_item = None
        while it.value():
            item = it.value()
            block = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(block, EcfBlock) and block_identity(block) == identity:
                root_item = item
                break
            it += 1
        if root_item is None:
            return False

        target_item = root_item
        if prop_key and prop_value:
            found = self._find_tree_item_with_property(root_item, prop_key, prop_value)
            if found is not None:
                target_item = found

        self.tree.setCurrentItem(target_item)
        self.tree.scrollToItem(target_item)
        self._on_block_selected(target_item, 0)
        if prop_key and prop_value:
            self._select_property_row(prop_key, prop_value)
        return True

    def reload_from_disk(self) -> None:
        """Recharge le contenu DEPUIS LE DISQUE (ex: apres une ecriture
        externe faite par l'arbre technologique) -- demande explicite de
        l'utilisateur (session du 29/08/2026) : pouvoir observer EN DIRECT,
        dans cet onglet deja ouvert, les valeurs changer pendant qu'il glisse
        une icone dans l'arbre technologique.

        NE DOIT JAMAIS etre appele si is_modified() est vrai -- voir
        l'appelant, MainWindow._reload_tab_if_open_and_unmodified, qui
        garantit cette condition : ecraserait sinon un travail en cours sans
        aucun avertissement.

        Re-selectionne automatiquement le meme bloc qu'avant (par identite
        Id/Name, voir select_block_by_identity) s'il existe toujours, pour
        que le panneau de proprietes affiche la nouvelle valeur
        immediatement, sans action de l'utilisateur."""
        previous_identity = block_identity(self._current_block) if self._current_block else None

        self.doc = parse_ecf_file(self.path)
        self._current_block = None
        self._edited_prop_nodes = set()
        self._undo_stack = []
        self._populate_tree()

        if previous_identity is not None:
            self.select_block_by_identity(previous_identity)
        else:
            self._refresh_props_table()
        self._set_modified(False)

    def _find_tree_item_with_property(self, item: QTreeWidgetItem, key: str, value: str):
        """Cherche, dans le sous-arbre de `item` (lui-meme inclus), le premier noeud
        dont le bloc associe contient DIRECTEMENT (sans redescendre plus loin) une
        EcfProperty avec la paire (key, value) -- utilise par
        select_block_by_identity() pour localiser le bon sous-bloc (ex: 'Child
        Items') plutot que de rester sur le bloc racine ou cette valeur n'est pas
        visible."""
        block = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(block, EcfBlock):
            for child in block.children:
                if isinstance(child, EcfProperty):
                    for k, v in child.pairs:
                        if k == key and v == value:
                            return item
        for i in range(item.childCount()):
            found = self._find_tree_item_with_property(item.child(i), key, value)
            if found is not None:
                return found
        return None

    def _select_property_row(self, key: str, value: str) -> bool:
        """Selectionne, dans le tableau de proprietes actuellement affiche, la
        premiere ligne dont une cellule correspond a `value` -- cherche dans toutes
        les colonnes (le mode tableau des structures repetitives a plusieurs colonnes
        par ligne, la cle exacte n'y est pas toujours une colonne visible)."""
        for row in range(self.props_table.rowCount()):
            for col in range(self.props_table.columnCount()):
                cell = self.props_table.item(row, col)
                if cell is not None and cell.text() == value:
                    self.props_table.setCurrentCell(row, col)
                    self.props_table.scrollToItem(cell)
                    return True
        return False

    # ------------------------------------------------------------------
    # Table des proprietes (editable)
    # ------------------------------------------------------------------

    def _on_block_selected(self, item: QTreeWidgetItem, column: int):
        block = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(block, EcfBlock):
            return
        self._current_block = block
        self._refresh_props_table()

    def _on_tree_item_clicked_for_info_card(self, item: QTreeWidgetItem, column: int) -> None:
        """Distinct de _on_block_selected : celui-ci n'est branche QUE sur un
        vrai clic utilisateur (QTreeWidget.itemClicked), jamais sur une
        reselection PROGRAMMATIQUE (recherche, select_block_by_identity,
        reload_from_disk) -- demande explicite de l'utilisateur, la fiche ne
        doit s'ouvrir que sur un clic reel, jamais se rouvrir toute seule
        apres un rechargement externe."""
        block = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(block, EcfBlock):
            self._show_info_card_for(block)

    def _get_info_card_localization_index(self):
        if self._info_card_localization_index is None:
            from core.localization_lookup import build_localization_index
            self._info_card_localization_index = build_localization_index(self.working_root)
        return self._info_card_localization_index

    def _get_info_card_templates_doc(self):
        """Cherche TOUJOURS l'etat le PLUS A JOUR de Templates.ecf -- bug
        reel signale par l'utilisateur (29/08/2026) : un Template juste cree
        par duplication n'apparaissait jamais dans la fiche d'information,
        car l'ancienne version METTAIT EN CACHE une lecture disque UNIQUE au
        premier clic, jamais rafraichie ensuite -- et un Template cree par
        duplication vit d'abord en MEMOIRE dans l'onglet Templates.ecf tant
        qu'il n'est pas enregistre, invisible a une relecture disque.
        Cherche donc D'ABORD un onglet Templates.ecf DEJA OUVERT (forcement
        a jour), et ne relit le disque qu'en dernier recours (aucun onglet
        ouvert pour ce fichier)."""
        if not self.sibling_ecf_files:
            return None
        from core.ecf.block_creation import find_file_by_name
        templates_path = find_file_by_name(self.sibling_ecf_files, 'Templates.ecf')
        if templates_path is None:
            return None
        main_window = self.window()
        if hasattr(main_window, 'tabs'):
            for i in range(main_window.tabs.count()):
                if main_window.tabs.tabToolTip(i) == str(templates_path):
                    tab_widget = main_window.tabs.widget(i)
                    edit_widget = getattr(tab_widget, 'edit_widget', tab_widget)
                    if hasattr(edit_widget, 'doc'):
                        return edit_widget.doc
        try:
            return parse_ecf_file(templates_path)
        except Exception:
            return None

    def _get_info_card_icon_index(self):
        if self._info_card_icon_index is None:
            if self.working_root is not None:
                from core.tech_tree_icons import build_icon_index
                self._info_card_icon_index = build_icon_index(self.working_root)
            else:
                self._info_card_icon_index = {}
        return self._info_card_icon_index

    def _show_info_card_for(self, block: EcfBlock) -> None:
        """Construit et affiche la fiche d'information du bloc selectionne --
        voir gui/block_info_card_widget.py. S'ouvre UNIQUEMENT depuis un clic
        (seul appelant : _on_block_selected, lui-meme branche sur
        QTreeWidget.itemClicked), jamais au survol ni automatiquement."""
        name = block.get('Name') or block.get_property('Name')
        if not name:
            return
        from core.i18n import get_language
        from core.block_info_card import build_block_info_card
        loc = self._get_info_card_localization_index()
        templates_doc = self._get_info_card_templates_doc()
        card_data = build_block_info_card(block, loc, get_language(), templates_doc)

        pixmap = None
        if card_data.icon_key:
            from core.tech_tree_icons import resolve_icon_path, load_icon_bytes
            icon_index = self._get_info_card_icon_index()
            ref = resolve_icon_path(icon_index, card_data.icon_key)
            if ref is not None:
                data = load_icon_bytes(ref)
                if data:
                    candidate = QPixmap()
                    if candidate.loadFromData(data) and not candidate.isNull():
                        pixmap = candidate

        if self._info_card is None:
            from gui.block_info_card_widget import BlockInfoCardWidget
            self._info_card = BlockInfoCardWidget(self)
            self._info_card.field_clicked.connect(self._on_info_card_field_clicked)
        # Ne repositionne QUE lors d'une VRAIE ouverture (fiche fermee, ou
        # affichant deja un AUTRE bloc) -- un simple rafraichissement (meme
        # bloc, ex: apres edition d'une propriete) ne doit jamais annuler un
        # deplacement manuel de l'utilisateur (fiche deplacable a la souris,
        # demande explicite du 29/08/2026).
        was_showing_this_block = self._info_card.is_showing(name)
        self._info_card.show_card(name, card_data, pixmap)
        if not was_showing_this_block:
            self._position_info_card()

    def _position_info_card(self) -> None:
        """Position INITIALE seulement (voir _show_info_card_for, jamais
        appelee lors d'un simple rafraichissement) -- la fiche etant
        desormais une fenetre independante (voir BlockInfoCardWidget), sa
        position se fixe en coordonnees ECRAN (mapToGlobal), pas relatives a
        ce widget."""
        if self._info_card is None:
            return
        local_x = max(0, self.width() - self._info_card.width() - 14)
        global_pos = self.mapToGlobal(QPoint(local_x, 30))
        self._info_card.move(global_pos)

    def _on_info_card_field_clicked(self, root_identity: str, prop_key: str, prop_value: str) -> None:
        """Clic sur une valeur de la fiche d'information -- navigue
        directement vers la ligne correspondante dans le tableau de
        proprietes pour modification rapide (demande explicite de
        l'utilisateur, session du 29/08/2026). Reutilise select_block_by_
        identity(), deja capable de retrouver le sous-bloc EXACT (ex:
        '{ Child 0 ... }' d'une arme) contenant cette paire cle/valeur, pas
        seulement le bloc racine."""
        self.select_block_by_identity(root_identity, prop_key=prop_key, prop_value=prop_value)

    def _refresh_info_card_if_showing(self, block: EcfBlock) -> None:
        """Rafraichissement EN DIRECT (demande explicite de l'utilisateur,
        session du 29/08/2026) -- appele apres toute modification de
        propriete (voir _on_cell_changed) ; ne fait rien si la fiche n'est
        pas ouverte ou affiche un AUTRE bloc que celui modifie."""
        if self._info_card is None:
            return
        name = block.get('Name') or block.get_property('Name')
        if name and self._info_card.is_showing(name):
            self._show_info_card_for(block)

    def _detect_repeating_items(self, block: EcfBlock):
        """Delegue a core.ecf.model.detect_repeating_items -- extrait pour
        garder une source unique de verite (evite toute divergence future
        si cette logique est reutilisee ailleurs)."""
        return detect_repeating_items(block)

    def _field_tooltip(self, key: str) -> str:
        """Construit le texte d'infobulle pour une cle de propriete/colonne
        (ex: 'AllowPlacingAt', 'param1') -- TOUJOURS coherent avec le
        fichier reellement ouvert :
        1. Glossaire manuel dedie a ce fichier (core/ecf_header_glossary.py)
           si une entree correspond exactement a cette cle -- explication
           claire et verifiee.
        2. Sinon, premier commentaire de fin de ligne trouve dans LE
           FICHIER LUI-MEME pour cette cle (jamais invente).
        3. Sinon, chaine vide (Qt n'affiche alors aucune infobulle) --
           mieux vaut rien qu'une explication inventee."""
        if not key:
            return ""
        explanation = find_term_explanation(self.path.name, key)
        if explanation:
            return f"<b>{key}</b><br>{explanation}"
        inline = find_first_inline_comment_for_key(self.doc, key)
        if inline:
            return f"<b>{key}</b><br>{inline}"
        return ""

    def _refresh_props_table(self):
        if not self._current_block:
            return
        block = self._current_block
        self.props_table.blockSignals(True)
        self.props_table.setSortingEnabled(False)

        detected = self._detect_repeating_items(block)
        self._table_mode = detected is not None
        self.btn_add_row.setVisible(self._table_mode)
        self.btn_add_prop.setVisible(not self._table_mode)

        if self._table_mode:
            param_columns, prefixes = detected
            self._refresh_props_table_grid(block, param_columns)
        else:
            self._refresh_props_table_flat(block)

        self.props_table.blockSignals(False)

    def _refresh_props_table_flat(self, block: EcfBlock):
        """Affichage classique : une ligne par paire cle/valeur (utilise pour la
        grande majorite des blocs, qui n'ont pas de structure repetitive)."""
        self.props_table.setColumnCount(2)
        self.props_table.setHorizontalHeaderLabels([t("ecf.col_property"), t("ecf.col_value")])
        rows = []
        for k, v in block.pairs:
            if k:
                rows.append((k, v, block))
        for child in block.children:
            if isinstance(child, EcfProperty):
                for k, v in child.pairs:
                    if k:
                        rows.append((k, v, child))
        self.props_table.setRowCount(len(rows))
        for i, (k, v, prop_node) in enumerate(rows):
            item_k = QTableWidgetItem(k)
            item_k.setFlags(item_k.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item_k.setData(Qt.ItemDataRole.UserRole, (prop_node, k))
            item_v = QTableWidgetItem(v)
            item_v.setData(Qt.ItemDataRole.UserRole, (prop_node, k))
            # Infobulle specifique a CETTE cle (glossaire du fichier ou
            # commentaire reel trouve dans le fichier), avec une note
            # structurelle en plus si la propriete est sur la ligne
            # d'ouverture du bloc (ex: Id, Name).
            tooltip = self._field_tooltip(k)
            if prop_node is block:
                header_note = t("ecf.header_property_tooltip")
                tooltip = f"{tooltip}<br><br><i>{header_note}</i>" if tooltip else header_note
            if tooltip:
                item_k.setToolTip(tooltip)
            if id(prop_node) in self._edited_prop_nodes:
                item_k.setBackground(COLOR_MODIFIED_ROW)
                item_v.setBackground(COLOR_MODIFIED_ROW)
            self.props_table.setItem(i, 0, item_k)
            self.props_table.setItem(i, 1, item_v)

    def _refresh_props_table_grid(self, block: EcfBlock, param_columns: List[str]):
        """Affichage en tableau pour les structures repetitives (Child Items, Child
        Inputs...) : une LIGNE par entree (Name_X/Group_X), une COLONNE par parametre
        -- bien plus lisible qu'une longue liste plate ou les param1/param2 de
        chaque entree se retrouvaient meles a la suite les uns des autres."""
        columns = [t("ecf.col_type"), t("ecf.col_item_value")] + param_columns
        self.props_table.setColumnCount(len(columns))
        self.props_table.setHorizontalHeaderLabels(columns)

        # Infobulles d'en-tete de colonne (apparition apres une courte pause du
        # curseur, comportement standard Qt) -- toujours coherentes avec le VRAI
        # fichier ouvert : glossaire dedie si disponible, sinon commentaire reel
        # trouve dans le fichier pour cette cle precise, sinon aucune infobulle.
        header_type = self.props_table.horizontalHeaderItem(0)
        if header_type:
            header_type.setToolTip(t("ecf.col_type_tooltip"))
        header_value = self.props_table.horizontalHeaderItem(1)
        if header_value:
            header_value.setToolTip(t("ecf.col_item_value_tooltip"))
        for col_idx, param_key in enumerate(param_columns):
            header_item = self.props_table.horizontalHeaderItem(2 + col_idx)
            if header_item:
                header_item.setToolTip(self._field_tooltip(param_key))

        prop_children = [c for c in block.children if isinstance(c, EcfProperty)]
        self.props_table.setRowCount(len(prop_children))
        for row, prop in enumerate(prop_children):
            if not prop.pairs:
                continue
            first_key, first_value = prop.pairs[0]
            m = _ITEM_KEY_RE.match(first_key) if first_key else None
            item_type = QTableWidgetItem(m.group(1) if m else (first_key or ""))
            item_type.setData(Qt.ItemDataRole.UserRole, (prop, "__TYPE__"))
            item_value = QTableWidgetItem(first_value)
            item_value.setData(Qt.ItemDataRole.UserRole, (prop, first_key))
            modified = id(prop) in self._edited_prop_nodes
            if modified:
                item_type.setBackground(COLOR_MODIFIED_ROW)
                item_value.setBackground(COLOR_MODIFIED_ROW)
            self.props_table.setItem(row, 0, item_type)
            self.props_table.setItem(row, 1, item_value)

            pairs_by_key = {k: v for k, v in prop.pairs[1:] if k}
            for col_idx, param_key in enumerate(param_columns):
                cell = QTableWidgetItem(pairs_by_key.get(param_key, ""))
                cell.setData(Qt.ItemDataRole.UserRole, (prop, param_key))
                if modified:
                    cell.setBackground(COLOR_MODIFIED_ROW)
                self.props_table.setItem(row, 2 + col_idx, cell)

    def _on_cell_changed(self, item: QTableWidgetItem):
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        prop_node, pair_key = data
        new_value = item.text()

        if isinstance(prop_node, EcfBlock):
            old_value = prop_node.get(pair_key)
            if old_value == new_value:
                return
            self._snapshot_undo()
            prop_node.set(pair_key, new_value)
            annotate_target = None
            key_for_annotation = pair_key
        elif pair_key == "__TYPE__":
            # Colonne 'Type' en mode tableau : bascule Name_N <-> Group_N en gardant le
            # meme N et la meme valeur -- reconstruit juste la cle de la 1ere paire.
            if not isinstance(prop_node, EcfProperty) or not prop_node.pairs:
                return
            old_first_key, first_value = prop_node.pairs[0]
            m = _ITEM_KEY_RE.match(old_first_key) if old_first_key else None
            suffix = m.group(2) if m else "0"
            new_type = new_value.strip()
            if not new_type or not re.match(r'^[A-Za-z]+$', new_type):
                # Valeur non reconnue (vide ou contient des caracteres invalides pour
                # une cle ECF) : remet l'affichage precedent plutot que de laisser une
                # cle invalide silencieusement
                self._refresh_props_table()
                return
            new_first_key = f"{new_type}_{suffix}"
            if new_first_key == old_first_key:
                return
            self._snapshot_undo()
            prop_node.pairs[0] = (new_first_key, first_value)
            prop_node.dirty = True
            annotate_target = prop_node
            old_value = old_first_key
            key_for_annotation = "Type"
        else:
            if not isinstance(prop_node, EcfProperty):
                return
            old_value = None
            idx = None
            for i, (k, v) in enumerate(prop_node.pairs):
                if k == pair_key:
                    old_value = v
                    idx = i
                    break
            if idx is None:
                if new_value.strip() == "":
                    return
                # Nouvelle colonne param pour cette ligne precise (ex: on tape une
                # valeur dans param2 pour une ligne qui n'avait que param1 jusque la)
                self._snapshot_undo()
                prop_node.pairs.append((pair_key, new_value))
                prop_node.dirty = True
                annotate_target = prop_node
                old_value = "(absent)"
            else:
                if old_value == new_value:
                    return
                self._snapshot_undo()
                prop_node.pairs[idx] = (pair_key, new_value)
                prop_node.dirty = True
                annotate_target = prop_node
            key_for_annotation = pair_key

        if settings.get_annotations_enabled() and annotate_target is not None:
            author = settings.get_author()
            annotate_property(annotate_target, f"# original {key_for_annotation}: {old_value} -- Mod par {author}")

        self._edited_prop_nodes.add(id(prop_node))
        self._set_modified(True)
        self.props_table.blockSignals(True)
        item.setBackground(COLOR_MODIFIED_ROW)
        self.props_table.blockSignals(False)
        if self._current_block is not None:
            self._refresh_info_card_if_showing(self._current_block)

    def _show_table_context_menu(self, pos):
        item = self.props_table.itemAt(pos)
        if not item or not self._current_block:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        prop_node, pair_key = data
        value_item = item  # la cellule cliquee elle-meme porte le texte pertinent
        # traduire/bbcode agissent sur n'importe quelle cellule cliquee ; supprimer agit
        # sur toute la LIGNE (le prop_node entier), peu importe la colonne cliquee

        is_header_prop = isinstance(prop_node, EcfBlock)
        global_pos = self.props_table.viewport().mapToGlobal(pos)

        menu = QMenu(self)
        add_clipboard_menu_actions(menu, self.props_table, allow_new_rows=False)
        menu.addSeparator()

        from core import translation
        translate_menu = menu.addMenu(t("ctx.translate_to"))
        lang_actions = {}
        for label, code in translation.COMMON_LANGUAGES:
            a = translate_menu.addAction(label)
            lang_actions[a] = code

        action_bbcode = menu.addAction(t("ctx.bbcode"))

        action_duplicate_row = None
        if self._table_mode and isinstance(prop_node, EcfProperty):
            action_duplicate_row = menu.addAction(t("dup.row_title"))

        action_del = None
        if not is_header_prop:
            action_del = menu.addAction(t("ecf.delete_property_action"))

        chosen = menu.exec(global_pos)

        if chosen == action_bbcode:
            new_text = open_bbcode_tool(self, value_item.text())
            if new_text is not None:
                value_item.setText(new_text)
        elif chosen in lang_actions:
            self._translate_cell(value_item, None, prop_node, lang_actions[chosen])
        elif chosen == action_duplicate_row and isinstance(prop_node, EcfProperty):
            self._duplicate_row_action(prop_node)
        elif chosen == action_del and isinstance(prop_node, EcfProperty):
            self._snapshot_undo()
            remove_property_line(self._current_block, prop_node)
            self._set_modified(True)
            self._refresh_props_table()

    def _duplicate_row_action(self, prop: EcfProperty):
        """Duplique une ligne de structure repetitive (mode tableau) --
        soit une copie unique avec un nouveau nom, soit plusieurs
        variantes nommees {Nom}T1..TN avec variation en pourcentage sur
        des champs numeriques choisis (voir core/ecf/variants.py). Les
        lignes de ce type n'ont pas d'Id (identite = valeur du premier
        couple cle/valeur, ex: 'IronOre' dans 'Item: IronOre, ...')."""
        from core.ecf.variants import (
            detect_numeric_fields_row, generate_row_variants, compute_single_variant_value,
        )
        from gui.duplicate_variants_dialog import DuplicateVariantsDialog

        if not prop.pairs or not self._current_block:
            return
        current_name = prop.pairs[0][1]
        numeric_fields = detect_numeric_fields_row(prop)

        dialog = DuplicateVariantsDialog(None, current_name, [], numeric_fields,
                                          parent=self, show_id_field=False)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        siblings = [c for c in self._current_block.children if isinstance(c, EcfProperty)]
        try:
            idx = self._current_block.children.index(prop)
        except ValueError:
            return
        existing_names = {p.pairs[0][1] for p in siblings if p.pairs}

        if dialog.result_multi:
            m = dialog.result_multi
            new_rows = generate_row_variants(
                prop, m['num_variants'], m['varying_fields'], m['total_percent'], m['first_is_original'])
            colliding = [r for r in new_rows if r.pairs and r.pairs[0][1] in existing_names]
            if colliding:
                QMessageBox.warning(self, t("dup.already_used_title"),
                                     t("dup.already_used_msg", file=self.path.name))
                return
            self._snapshot_undo()
            for offset, new_row in enumerate(new_rows):
                self._current_block.children.insert(idx + 1 + offset, new_row)
            self._set_modified(True)
            self._refresh_props_table()
            names = ', '.join(r.pairs[0][1] for r in new_rows)
            QMessageBox.information(self, t("dup.row_title"),
                                     t("dup.variants_created", count=len(new_rows), names=names))
        else:
            import copy as _copy
            new_name = dialog.result_new_name
            if new_name in existing_names:
                QMessageBox.warning(self, t("dup.already_used_title"),
                                     t("dup.already_used_msg", file=self.path.name))
                return
            new_row = _copy.deepcopy(prop)
            new_row.dirty = True
            first_key = new_row.pairs[0][0]
            new_row.set(first_key, new_name)
            if dialog.result_simple_percent is not None and dialog.result_simple_fields:
                for field_key in dialog.result_simple_fields:
                    original_value = prop.get(field_key)
                    if original_value is None:
                        continue
                    new_row.set(field_key, compute_single_variant_value(original_value, dialog.result_simple_percent))
            self._snapshot_undo()
            self._current_block.children.insert(idx + 1, new_row)
            self._set_modified(True)
            self._refresh_props_table()

    def _translate_cell(self, value_item, key_item, prop_node, target_lang: str):
        from core import translation
        text = value_item.text()
        if not translation.is_available():
            QMessageBox.warning(self, t("trans.unavailable_title"), t("trans.unavailable_msg", error=translation.get_import_error()))
            return
        try:
            translated = translation.translate_text(text, target=target_lang)
        except Exception as e:
            QMessageBox.critical(self, t("trans.error_title"), t("trans.error_msg", error=e))
            return

        dialog = TranslationResultDialog(text, translated, self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.accepted_replace:
            return
        new_value = dialog.result_text()

        # Applique via le meme chemin qu'une edition manuelle -- annotation de
        # tracabilite comprise (comportement coherent avec toute autre modification).
        value_item.setText(new_value)  # declenche _on_cell_changed, qui gere tout le reste

    def _add_property_dialog(self):
        if not self._current_block:
            QMessageBox.information(self, t("ecf.no_block_title"), t("ecf.no_block_msg"))
            return
        key, ok = QInputDialog.getText(self, t("ecf.add_property_title"), t("ecf.property_name_label"))
        if not ok or not key.strip():
            return
        value, ok = QInputDialog.getText(self, t("ecf.add_property_title"),
                                          t("ecf.property_value_label", key=key))
        if not ok:
            return
        self._snapshot_undo()

        # Permet de taper directement plusieurs paires a la suite, EXACTEMENT comme
        # dans le fichier (ex: valeur = 'AlienParts04, param1: 0.6, param2: "1,3"') --
        # sinon chaque propriete ajoutee une par une finissait sur SA PROPRE ligne au
        # lieu d'etre regroupee comme ses voisines (Name_X, param1, param2...), ce qui
        # cassait le format attendu par le jeu pour ce genre de structure repetitive.
        # Les valeurs contenant une virgule doivent etre entre guillemets, comme
        # partout ailleurs dans le fichier (ex: "1,3") -- une virgule NON protegee y
        # serait sinon interpretee a tort comme separant une propriete supplementaire.
        from core.ecf.parser import _parse_pairs
        extra = _parse_pairs(value.strip())
        if len(extra) > 1 and extra[0][0] is None:
            pairs = [(key.strip(), extra[0][1])] + extra[1:]
        else:
            pairs = [(key.strip(), value.strip())]

        new_prop = add_property_line(self._current_block, pairs)
        if settings.get_annotations_enabled():
            author = settings.get_author()
            annotate_property(new_prop, f"# Ajoute par {author}")
        self._set_modified(True)
        self._refresh_props_table()

    def _add_table_row_dialog(self):
        """Ajoute une ligne au mode tableau (Child Items...) -- la numerotation
        (Name_N/Group_N) et la position (a la suite des entrees du meme type) sont
        entierement automatiques, jamais laissees a la saisie manuelle : c'est
        precisement ce qui posait probleme avec le dialogue generique '+ Propriete'
        (cle non numerotee, ligne ajoutee en toute fin de bloc plutot qu'au bon
        endroit)."""
        if not self._current_block or not self._table_mode:
            QMessageBox.information(self, t("ecf.no_block_title"), t("ecf.no_block_msg"))
            return
        detected = self._detect_repeating_items(self._current_block)
        param_columns, prefixes = detected if detected else ([], ["Name", "Group"])

        # Menu deroulant des vrais items/blocs du scenario (ItemsConfig.ecf/
        # BlocksConfig.ecf) pour le champ Valeur -- disponible sur TOUS les
        # fichiers en mode tableau (pas seulement LootGroups.ecf), a la
        # demande de l'utilisateur : le champ reste de toute facon editable
        # (QComboBox editable), donc aucun risque a proposer ces suggestions
        # meme sur un fichier ou 'Valeur' ne represente pas un nom d'item/bloc
        # -- au pire l'utilisateur les ignore et tape sa propre valeur.
        value_suggestions = None
        value_suggestions_players_only = None
        if self.sibling_ecf_files:
            from core.ecf.block_creation import find_file_by_name, list_craftable_names
            items_path = find_file_by_name(self.sibling_ecf_files, "ItemsConfig.ecf")
            blocks_path = find_file_by_name(self.sibling_ecf_files, "BlocksConfig.ecf")
            if items_path or blocks_path:
                value_suggestions = list_craftable_names(items_path, blocks_path)
                value_suggestions_players_only = list_craftable_names(
                    items_path, blocks_path, players_only=True)

        dialog = AddTableRowDialog(param_columns, prefixes, self, value_suggestions=value_suggestions,
                                    value_suggestions_players_only=value_suggestions_players_only)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self._snapshot_undo()
        new_prop = add_repeating_item_row(
            self._current_block, dialog.result_type, dialog.result_value, dialog.result_extra_pairs)
        if settings.get_annotations_enabled():
            author = settings.get_author()
            annotate_property(new_prop, f"# Ajoute par {author}")
        self._set_modified(True)
        self._refresh_props_table()

    # ------------------------------------------------------------------
    # Blocs : ajout / suppression
    # ------------------------------------------------------------------

    def _show_tree_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        block = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(block, EcfBlock):
            return
        menu = QMenu(self)
        action_duplicate = menu.addAction(t("dup.duplicate"))
        menu.addSeparator()
        action_disable = menu.addAction(t("ecf.disable_block_action"))
        action_del = menu.addAction(t("ecf.delete_block_action"))
        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen == action_duplicate:
            self._duplicate_block_action(block)
        elif chosen == action_disable:
            confirm = QMessageBox.question(self, t("merge.confirm_title"),
                                            t("ecf.confirm_disable_block", name=item.text(0)))
            if confirm == QMessageBox.StandardButton.Yes:
                self._snapshot_undo()
                from core.ecf.disable_block import disable_block
                disable_block(self.doc, block, settings.get_author())
                self._set_modified(True)
                if self._current_block is block:
                    self._current_block = None
                    self.props_table.setRowCount(0)
                self._populate_tree()
        elif chosen == action_del:
            confirm = QMessageBox.question(self, t("merge.confirm_title"),
                                            t("ecf.confirm_delete_block", name=item.text(0)))
            if confirm == QMessageBox.StandardButton.Yes:
                self._snapshot_undo()
                remove_block(self.doc.nodes, block)
                self._set_modified(True)
                if self._current_block is block:
                    self._current_block = None
                    self.props_table.setRowCount(0)
                self._populate_tree()

    def _find_container_list(self, target_block: EcfBlock) -> Optional[list]:
        """Cherche la VRAIE liste (self.doc.nodes au niveau racine, ou
        children d'un bloc parent si le bloc est imbrique) qui contient
        actuellement ce bloc -- necessaire pour inserer un duplicata juste
        apres, peu importe sa profondeur d'imbrication."""
        def search(nodes):
            if target_block in nodes:
                return nodes
            for node in nodes:
                if isinstance(node, EcfBlock):
                    found = search(node.children)
                    if found is not None:
                        return found
            return None
        return search(self.doc.nodes)

    def _duplicate_block_action(self, block: EcfBlock):
        """Duplique un bloc DANS LE MEME FICHIER en cours d'edition -- soit
        une copie unique (Id/Name, comme le dialogue historique de
        duplication depuis Scenario A/B), soit plusieurs variantes
        nommees {Name}T1..TN avec variation en pourcentage sur des champs
        numeriques choisis (voir core/ecf/variants.py). Inseree juste
        apres le bloc source, au meme niveau d'imbrication."""
        from core.ecf.pending_conflicts import find_used_ids, suggest_free_ids
        from core.ecf.variants import (
            detect_numeric_fields_block, generate_block_variants,
            get_block_field, set_block_field, compute_single_variant_value,
        )
        from gui.duplicate_variants_dialog import DuplicateVariantsDialog

        current_id = block.get('Id')
        current_name = block.get_property('Name')
        used_ids = find_used_ids([self.path])
        suggestions = suggest_free_ids(used_ids, 5)
        numeric_fields = detect_numeric_fields_block(block)

        dialog = DuplicateVariantsDialog(current_id, current_name, suggestions, numeric_fields,
                                          parent=self, show_id_field=True, source_block=block)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        container = self._find_container_list(block)
        if container is None:
            return
        idx = container.index(block)
        existing_identities = {block_identity(b) for b in self.doc.iter_blocks()}

        if dialog.result_multi:
            m = dialog.result_multi
            new_blocks = generate_block_variants(
                block, current_name or "Bloc", m['num_variants'], m['varying_fields'],
                m['total_percent'], m['first_is_original'], variant_names=m.get('variant_names'))
            colliding = [b for b in new_blocks if block_identity(b) in existing_identities]
            if colliding:
                QMessageBox.warning(self, t("dup.already_used_title"),
                                     t("dup.already_used_msg", file=self.path.name))
                return
            # Controle avant insertion (Id/Name uniques, casse...) -- voir
            # _check_before_insert : refuse la duplication si erreur bloquante.
            if not self._check_before_insert(new_blocks):
                return
            self._snapshot_undo()
            for offset, new_block in enumerate(new_blocks):
                new_block.indent = block.indent
                # Proprietes ajustees dans l'apercu du dialogue -- appliquees
                # a TOUTES les variantes, en plus de la variation en
                # pourcentage deja calculee par generate_block_variants (voir
                # docstring de DuplicateVariantsDialog, demande explicite de
                # l'utilisateur du 29/08/2026).
                for field_key, field_value in dialog.result_field_overrides.items():
                    set_block_field(new_block, field_key, field_value)
                container.insert(idx + 1 + offset, new_block)
            self._set_modified(True)
            self._populate_tree()
            names = ', '.join(b.get_property('Name') for b in new_blocks)
            QMessageBox.information(self, t("dup.title"),
                                     t("dup.variants_created", count=len(new_blocks), names=names))
            new_names = [b.get_property('Name') for b in new_blocks if b.get_property('Name')]
            # Nom affiche (Localization.csv) -- demande explicite de
            # l'utilisateur (29/08/2026) : un duplicata n'a par definition
            # jamais de traduction, sans quoi il s'affiche en jeu avec sa
            # cle technique brute.
            self._offer_localization_adjustment(current_name, new_names)
            # Propose la creation des Templates associes a chaque variante --
            # retour utilisateur clarifie (29/08/2026) : la demande initiale
            # concernait bien CE flux (duplication au sein de la copie de
            # travail), pas seulement Scenario A/B -> copie de travail.
            self._maybe_propose_templates_for_variants(current_name, new_names)
        else:
            overrides = {}
            if dialog.result_new_id:
                overrides['Id'] = dialog.result_new_id
            if dialog.result_new_name:
                overrides['Name'] = dialog.result_new_name
            remove_keys = ['Id'] if dialog.result_remove_id else []
            new_block = duplicate_block(block, overrides=overrides, remove_keys=remove_keys)
            if dialog.result_simple_percent is not None and dialog.result_simple_fields:
                for field_key in dialog.result_simple_fields:
                    original_value = get_block_field(block, field_key)
                    if original_value is None:
                        continue
                    new_value = compute_single_variant_value(original_value, dialog.result_simple_percent)
                    set_block_field(new_block, field_key, new_value)
            # Proprietes ajustees dans l'apercu du dialogue -- demande
            # explicite de l'utilisateur (29/08/2026), voir docstring de
            # DuplicateVariantsDialog. Applique APRES la variation en
            # pourcentage eventuelle, pour que l'ajustement manuel ait
            # toujours le dernier mot si les deux touchent le meme champ.
            for field_key, field_value in dialog.result_field_overrides.items():
                set_block_field(new_block, field_key, field_value)
            if block_identity(new_block) in existing_identities:
                QMessageBox.warning(self, t("dup.already_used_title"),
                                     t("dup.already_used_msg", file=self.path.name))
                return
            # Controle avant insertion (Id/Name uniques, casse...) -- voir
            # _check_before_insert : refuse la duplication si erreur bloquante.
            if not self._check_before_insert([new_block]):
                return
            new_block.indent = block.indent
            self._snapshot_undo()
            container.insert(idx + 1, new_block)
            self._set_modified(True)
            self._populate_tree()
            # Nom affiche (Localization.csv) puis proposition de Template --
            # meme logique que le mode multi-variantes ci-dessus, pour cette
            # copie unique.
            new_name = new_block.get_property('Name')
            if new_name:
                self._offer_localization_adjustment(current_name, [new_name])
                self._maybe_propose_templates_for_variants(current_name, [new_name])


    def _offer_localization_adjustment(self, source_name: Optional[str], new_names: List[str]) -> None:
        """Propose d'ajouter/ajuster le nom AFFICHE (Extras/Localization.csv
        du scenario) pour chaque bloc/item nouvellement cree ou duplique --
        demande explicite de l'utilisateur (session du 29/08/2026), etendu a la
        CREATION le 30/08/2026 (obligation no 3 : sans entree a sa cle, l'entree
        s'affiche en jeu avec son nom technique brut). `source_name` peut etre
        None (creation) : le pre-remplissage retombe sur le nom technique lui-
        meme. Les noms DEJA localises (scenario ou vanilla) sont filtres -- on
        ne propose que ce qui en a reellement besoin. Voir
        gui/localization_adjust_dialog.py. Sans contexte de scenario
        (working_root), la proposition est silencieusement sautee."""
        if not new_names or self.working_root is None:
            return
        from core.localization_lookup import build_localization_index, write_scenario_localization_entries
        from core.ecf.creation_check import names_needing_localization
        from gui.localization_adjust_dialog import LocalizationAdjustDialog

        names_to_fill = names_needing_localization(self.working_root, new_names)
        if not names_to_fill:
            return

        loc = build_localization_index(self.working_root)
        if source_name:
            source_fr = loc.get(source_name, 'fr') or source_name
            source_en = loc.get(source_name, 'en') or source_name
        else:
            source_fr = names_to_fill[0]
            source_en = names_to_fill[0]

        dialog = LocalizationAdjustDialog(names_to_fill, (source_fr, source_en), parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        entries = dialog.get_entries()
        if entries:
            write_scenario_localization_entries(self.working_root, entries)

    def _maybe_propose_templates_for_variants(self, source_name: Optional[str],
                                               variant_names: List[str]):
        """Après la création de plusieurs variantes d'un bloc (ou d'une copie
        simple), propose de créer les Templates (recettes de craft) associés
        à chaque variante. Deux cas, depuis la demande du 30/08/2026 :
        - le bloc SOURCE avait un Template : il est dupliqué pour chaque
          variante (même structure, seuls les noms changent) ;
        - le bloc source n'en avait PAS : proposition QUAND MEME d'un
          Template par variante, pré-rempli avec les valeurs LES PLUS
          COURANTES du scénario (voir core/ecf/block_creation.py::
          scan_template_defaults) -- plus jamais de bloc impossible à
          fabriquer sous prétexte que sa source n'avait pas de recette.
        """
        if self.path.name.lower() == 'templates.ecf':
            return
        if not self.sibling_ecf_files:
            return
        if not source_name:
            return
        from core.ecf.block_creation import find_file_by_name
        from core.ecf.parser import parse_ecf_file
        templates_path = find_file_by_name(self.sibling_ecf_files, 'Templates.ecf')
        if templates_path is None:
            return

        # Le Template source existe-t-il ? (determine le message ET le mode
        # de creation : copie du source OU valeurs les plus courantes)
        source_exists = False
        try:
            templates_doc = parse_ecf_file(templates_path)
            source_exists = any(b.get_property('Name') == source_name
                                for b in templates_doc.iter_blocks())
        except Exception:
            return

        if source_exists:
            prompt = t("dup.variants_create_templates_prompt",
                       count=len(variant_names),
                       names=', '.join(variant_names[:3]) + ('...' if len(variant_names) > 3 else ''))
        else:
            prompt = t("dup.no_source_offer_msg", name=source_name,
                       count=len(variant_names))
        reply = QMessageBox.question(
            self, t("addblock.ask_template_title"), prompt,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._create_templates_for_variants(templates_path, source_name, variant_names)

    def _create_templates_for_variants(self, templates_path: Path,
                                        source_template_name: str,
                                        variant_names: List[str]):
        """Cree un Template par variante via le moteur partage
        (gui/template_tools.create_templates) : copie du Template source
        s'il existe, sinon valeurs les plus courantes du fichier. Ouvre (ou
        active) Templates.ecf comme un VRAI onglet de la copie de travail."""
        from core.ecf.block_creation import find_file_by_name, list_craftable_names
        from gui.template_tools import create_templates

        main_window = self.window()
        if not hasattr(main_window, "open_working_file_tab"):
            return
        items_path = find_file_by_name(self.sibling_ecf_files, 'ItemsConfig.ecf')
        blocks_path = find_file_by_name(self.sibling_ecf_files, 'BlocksConfig.ecf')
        craftable_names = list_craftable_names(items_path, blocks_path)
        create_templates(
            self, main_window, templates_path, variant_names,
            source_template_name=source_template_name,
            author=settings.get_author() if settings.get_annotations_enabled() else "",
            craftable_names=craftable_names)

    def _open_disabled_blocks_dialog(self):
        from core.ecf.disable_block import find_disabled_blocks, enable_disabled_block
        dialog = DisabledBlocksDialog(self.doc, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.reactivated:
            self._set_modified(True)
            self._populate_tree()

    def _open_property_filter(self):
        dialog = PropertyFilterDialog(self.doc, on_filter_changed=self._apply_property_filter, parent=self)
        dialog.exec()

    def _open_transform_dialog(self):
        def _on_before_apply():
            self._snapshot_undo()

        def _on_after_apply():
            self._current_block = None
            self.props_table.setRowCount(0)
            self._populate_tree()
            self._set_modified(True)

        dialog = TransformDialog(self.doc, on_before_apply=_on_before_apply,
                                  on_after_apply=_on_after_apply, parent=self)
        dialog.exec()

    def _apply_property_filter(self, keys: List[str]):
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            block = item.data(0, Qt.ItemDataRole.UserRole)
            if not keys or not isinstance(block, EcfBlock):
                item.setHidden(False)
                continue
            item.setHidden(not all(k in _block_own_keys(block) for k in keys))

    def _tech_tree_source_for_current_file(self) -> Optional[str]:
        """'block' si ce widget edite BlocksConfig.ecf, 'item' si
        ItemsConfig.ecf, None sinon (ex: LootGroups.ecf, Templates.ecf --
        pas de concept d'arbre technologique) -- determine si le bouton de
        previsualisation de l'arbre technologique doit apparaitre dans
        PropertyTableDialog (voir gui/tech_tree_preview_dialog.py)."""
        name_lower = self.path.name.lower()
        if name_lower == "blocksconfig.ecf":
            return "block"
        if name_lower == "itemsconfig.ecf":
            return "item"
        return None

    def _add_block_dialog(self):
        """Creation guidee d'un nouveau bloc/item -- tableau de proprietes issu
        du fichier de travail, puis proposition de creer le Template associe
        (voir gui/add_block_dialog.py et core/ecf/block_creation.py pour le
        detail). Remplace l'ancienne version a 3 QInputDialog successifs."""
        from gui.add_block_dialog import IdentityModeDialog, PropertyTableDialog
        from core.ecf.block_creation import scan_kind_frequency, create_new_block

        mode_dialog = IdentityModeDialog(parent=self)
        if mode_dialog.exec() != QDialog.DialogCode.Accepted:
            return
        id_mode = mode_dialog.chosen_mode

        existing_ids = {b.get('Id') for b in self.doc.iter_blocks() if b.get('Id')}
        kind_counts = scan_kind_frequency(self.doc)
        default_kind = kind_counts.most_common(1)[0][0] if kind_counts else ""

        table_dialog = PropertyTableDialog(
            self.doc, id_mode, existing_ids, default_kind=default_kind,
            window_title_key="addblock.table_title", parent=self,
            tech_tree_source=self._tech_tree_source_for_current_file(),
            working_root=self.working_root,
            sibling_ecf_files=self.sibling_ecf_files)
        if table_dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self._snapshot_undo()
        new_block = create_new_block(table_dialog.result_kind, table_dialog.result_id,
                                      table_dialog.result_name, table_dialog.result_properties)
        if settings.get_annotations_enabled():
            new_block.comment = f"# Ajoute par {settings.get_author()}"
        self.doc.nodes.append(new_block)
        self._set_modified(True)
        self._populate_tree()

        created_name = table_dialog.result_name or table_dialog.result_id or "?"
        self._maybe_propose_template(created_name)
        # Obligation no 3 (localisation) : un bloc/item cree sans entree a sa
        # cle s'affiche en jeu avec son nom technique brut -- propose l'ajout
        # FR/EN tout de suite, comme la duplication le fait deja.
        self._offer_localization_adjustment(None, [table_dialog.result_name]
                                            if table_dialog.result_name else [])

    def _check_before_insert(self, new_blocks: list) -> bool:
        """Controle pre-insertion des duplications (meme moteur que la creation
        guidee, voir core/ecf/creation_check.py) : Id/Name uniques, piege de
        casse, collision Templates. Retourne False (et affiche les erreurs) si
        au moins une erreur bloquante -- l'insertion ne doit PAS se faire."""
        from core.ecf.creation_check import (
            CreationContext, check_creation, has_blocking, format_blocking)
        context = CreationContext(self.sibling_ecf_files, self.working_root)
        all_issues = []
        for new_block in new_blocks:
            all_issues.extend(check_creation(
                self.doc, context, new_block.kind,
                new_block.get('Id'), new_block.get_property('Name'),
                check_template_collision=False,  # les Templates sont proposes APRES, pas encore crees
                check_techtree_hint=False))
        if has_blocking(all_issues):
            QMessageBox.warning(self, t("createcheck.blocked_title"),
                                t("createcheck.blocked_msg",
                                  issues=format_blocking(all_issues)))
            return False
        return True

    def _maybe_propose_template(self, created_name: str):
        """Propose de creer le Template (recette de craft) associe au bloc/item
        qui vient d'etre cree -- seulement si ce fichier n'est pas deja
        Templates.ecf lui-meme, et si ce fichier a bien ete localise parmi les
        fichiers voisins du scenario (voir sibling_ecf_files)."""
        if self.path.name.lower() == 'templates.ecf':
            return
        if not self.sibling_ecf_files:
            return

        from core.ecf.block_creation import find_file_by_name
        templates_path = find_file_by_name(self.sibling_ecf_files, 'Templates.ecf')
        if templates_path is None:
            return

        reply = QMessageBox.question(
            self, t("addblock.ask_template_title"),
            t("addblock.ask_template_msg", name=created_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._create_associated_template(templates_path, created_name)

    def _create_associated_template(self, templates_path: Path, prefill_name: str):
        """Ouvre (ou active) Templates.ecf comme un VRAI onglet de la copie de
        travail (via main_window.open_working_file_tab -- jamais une ecriture
        directe sur disque, pour rester coherent avec le reste de l'appli ou
        rien ne s'enregistre sans validation explicite, et pour eviter tout
        conflit si Templates.ecf etait deja ouvert ailleurs), puis ajoute le
        nouveau Template dedans avec le meme mecanisme de tableau, Name
        pre-rempli pour correspondre exactement au bloc/item cree juste
        avant, et une section Ingredients (Child Inputs) en plus."""
        from gui.add_block_dialog import IdentityModeDialog, PropertyTableDialog
        from core.ecf.block_creation import (
            scan_kind_frequency, create_new_block, add_child_inputs,
            find_file_by_name, list_craftable_names,
        )

        main_window = self.window()
        if not hasattr(main_window, "open_working_file_tab"):
            return
        templates_widget = main_window.open_working_file_tab(templates_path)
        if templates_widget is None:
            return
        templates_edit = getattr(templates_widget, "edit_widget", templates_widget)
        if not hasattr(templates_edit, "doc"):
            return
        templates_doc = templates_edit.doc

        existing_ids = {b.get('Id') for b in templates_doc.iter_blocks() if b.get('Id')}
        items_path = find_file_by_name(self.sibling_ecf_files, 'ItemsConfig.ecf')
        blocks_path = find_file_by_name(self.sibling_ecf_files, 'BlocksConfig.ecf')
        craftable_names = list_craftable_names(items_path, blocks_path)
        craftable_names_players_only = list_craftable_names(items_path, blocks_path, players_only=True)

        kind_counts = scan_kind_frequency(templates_doc)
        default_kind = kind_counts.most_common(1)[0][0] if kind_counts else "+Template"

        # Pre-remplissage avec les valeurs les plus courantes du fichier
        # (CraftTime/Target coches, ingredients les plus utilises) -- demande
        # explicite de l'utilisateur du 30/08/2026. Aucune imposition : tout
        # reste decochable/modifiable.
        from core.ecf.block_creation import scan_template_defaults
        defaults = scan_template_defaults(templates_doc) or {}

        template_dialog = PropertyTableDialog(
            templates_doc, IdentityModeDialog.MODE_NAME_ONLY, existing_ids,
            default_kind=default_kind, name_prefill=prefill_name, name_readonly=True,
            enable_ingredients=True, craftable_names=craftable_names,
            craftable_names_players_only=craftable_names_players_only,
            window_title_key="addblock.template_table_title", parent=self,
            prechecked_properties=defaults.get("scalars"),
            prefill_ingredients=defaults.get("ingredients"))
        if template_dialog.exec() != QDialog.DialogCode.Accepted:
            return

        if hasattr(templates_edit, "_snapshot_undo"):
            templates_edit._snapshot_undo()
        new_template = create_new_block(template_dialog.result_kind, None,
                                         template_dialog.result_name, template_dialog.result_properties)
        if template_dialog.result_ingredients:
            add_child_inputs(new_template, template_dialog.result_ingredients)
        if settings.get_annotations_enabled():
            new_template.comment = f"# Ajoute par {settings.get_author()}"
        templates_doc.nodes.append(new_template)

        if hasattr(templates_edit, "_set_modified"):
            templates_edit._set_modified(True)
        if hasattr(templates_edit, "_populate_tree"):
            templates_edit._populate_tree()


class CompareWidget(QWidget):
    """Vue cote a cote : copie de travail (editable) a gauche, source(s) A/B en
    lecture seule a droite (dans des onglets si plusieurs sont disponibles).
    Le clic droit "copier ce bloc" fonctionne aussi depuis les panneaux source ici."""

    def __init__(self, working_path: Path, compare_sources: Dict[str, tuple], view_widget_factory,
                 copy_block_callback=None, duplicate_block_callback=None,
                 sibling_ecf_files: Optional[List[Path]] = None, working_root: Optional[Path] = None):
        """
        compare_sources : {label: (chemin_source, racine_source)}
        view_widget_factory(path, on_copy_block=None, on_duplicate_block=None) doit
        retourner un widget de lecture seule (typiquement EcfViewWidget de
        main_window.py) -- injecte pour eviter un import circulaire entre ce module et
        main_window.py.
        copy_block_callback(block, source_path, source_root, source_label) : appele
        quand l'utilisateur choisit "copier ce bloc" depuis un panneau source.
        duplicate_block_callback(block, parent_chain, source_path, source_root,
        source_label) : appele quand l'utilisateur choisit "dupliquer avec un nouvel
        Id" depuis un panneau source.
        sibling_ecf_files : voir EcfEditWidget, transmis tel quel.
        working_root : voir EcfEditWidget, transmis tel quel (previsualisation
        arbre technologique).
        """
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.edit_widget = EcfEditWidget(working_path, sibling_ecf_files=sibling_ecf_files,
                                          working_root=working_root)
        splitter.addWidget(self.edit_widget)

        if compare_sources:
            right_side = QTabWidget()
            for label, (src_path, src_root) in compare_sources.items():
                on_copy = None
                if copy_block_callback:
                    on_copy = (lambda block, p=src_path, r=src_root, l=label:
                               copy_block_callback(block, p, r, l))
                on_dup = None
                if duplicate_block_callback:
                    on_dup = (lambda block, parent_chain, p=src_path, r=src_root, l=label:
                              duplicate_block_callback(block, parent_chain, p, r, l))
                right_side.addTab(
                    view_widget_factory(src_path, on_copy_block=on_copy, copy_label=label,
                                         on_duplicate_block=on_dup),
                    label)
            splitter.addWidget(right_side)
            splitter.setSizes([600, 500])
        else:
            splitter.setSizes([1])

        layout.addWidget(splitter)

        self.modified_changed = self.edit_widget.modified_changed
        self.saved = self.edit_widget.saved

    def is_modified(self) -> bool:
        return self.edit_widget.is_modified()

    def reload_from_disk(self) -> None:
        self.edit_widget.reload_from_disk()

    def save(self):
        self.edit_widget.save()

    def _get_content_for_autosave(self) -> str:
        return self.edit_widget._get_content_for_autosave()
