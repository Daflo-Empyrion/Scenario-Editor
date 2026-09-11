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

"""Formulaire generique construit depuis les FieldSpec de core/pda/schema.py
-- un seul moteur pour les actions (par type de Check), les chapitres, les
taches et les activites (ChapterActivation).

Convention d'ecriture LIVE (meme flux que le reste de l'application : le
model mute les documents des onglets, jamais le disque) :
- bool decoche => cle SUPPRIMEE ('' -- une cle vide n'existe pas dans les
  vrais fichiers) ; cochee => 'true' ;
- liste vide => cle supprimee ;
- champ texte vide => cle supprimee (sauf required_defaults, applique par
  l'appelant du signal)."""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QCheckBox, QCompleter, QFormLayout, QLabel,
                             QLineEdit, QVBoxLayout, QWidget)

from core.i18n import t
from core.pda.schema import (KIND_BOOL, KIND_ENUM, KIND_FLOAT, KIND_INT,
                             KIND_NAMES, KIND_TEXT, KIND_TOKEN, KIND_TYPES)
from gui.pda.widgets import IntField, NameListEditor, SearchCombo, TokenTextField


class SpecForm(QWidget):
    """Construit (build) une grille de champs depuis (fields, values) et emet
    changed(key, value) a CHAQUE modification (hors listes, sans signal par
    widget : collect_values() les lit au moment voulu)."""

    changed = pyqtSignal(str, object)

    def __init__(self, model=None, suggestions_provider=None, parent=None):
        super().__init__(parent)
        self._model = model
        self._suggestions = suggestions_provider or (lambda pool: [])
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self._form = QFormLayout()
        lay.addLayout(self._form)
        self._widgets = {}   # key -> (kind, widget)

    def build(self, fields, values):
        """Reconstruit tout le formulaire ; values = {key: str | list[str]}."""
        self._clear()
        for spec in fields:
            value = values.get(spec.key, "")
            widget = self._make_widget(spec, value)
            if widget is None:
                continue
            self._widgets[spec.key] = (spec.kind, widget)
            label = QLabel(t(spec.label_key))
            # Infobulle explicative du champ, basee sur le guide PDA du jeu
            # (doc/EMPYRION_GALACTIC_SURVIVAL/PDA) : convention
            # <label_key>.tooltip dans i18n_strings.json, surcharge possible
            # par spec.tooltip_key. Posee sur le LABEL ET le champ (au
            # survol de l'un ou de l'autre -- demande du 12/09/2026).
            tooltip_key = spec.tooltip_key or (spec.label_key + ".tooltip")
            from core import i18n
            if spec.tooltip_key or i18n.has(tooltip_key):
                tip = t(tooltip_key)
                label.setToolTip(tip)
                widget.setToolTip(tip)
            self._form.addRow(label, widget)

    def _clear(self):
        self._widgets.clear()
        while self._form.rowCount():
            self._form.removeRow(0)

    # ------------------------------------------------------------------
    def _make_widget(self, spec, value):
        if spec.kind == KIND_TOKEN:
            return self._make_token(spec, value)
        if spec.kind == KIND_TEXT:
            return self._make_text(spec, value)
        if spec.kind in (KIND_INT, KIND_FLOAT):
            return self._make_int(spec, value)
        if spec.kind == KIND_BOOL:
            return self._make_bool(spec, value)
        if spec.kind == KIND_ENUM:
            return self._make_enum(spec, value)
        if spec.kind in (KIND_NAMES, KIND_TYPES):
            return self._make_list(spec, value)
        return None

    def _make_token(self, spec, value):
        edit = TokenTextField(self._model)
        edit.set_token(value if isinstance(value, str) else "")

        def on_change():
            self.changed.emit(spec.key, edit.value())
        edit.edit.textEdited.connect(on_change)
        return edit

    def _make_text(self, spec, value):
        edit = QLineEdit()
        suggestions = self._suggestions(spec.pool) if spec.pool else []
        if suggestions:
            completer = QCompleter(suggestions)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            edit.setCompleter(completer)
        edit.setText(value if isinstance(value, str) else "")
        edit.textEdited.connect(lambda text, k=spec.key: self.changed.emit(k, text.strip()))
        return edit

    def _make_int(self, spec, value):
        spin = IntField(value)
        spin.valueChanged.connect(lambda v, k=spec.key: self.changed.emit(k, str(v)))
        return spin

    def _make_bool(self, spec, value):
        check = QCheckBox()
        check.setChecked(str(value).strip().lower() == "true")
        check.toggled.connect(lambda on, k=spec.key: self.changed.emit(k, "true" if on else ""))
        return check

    def _make_enum(self, spec, value):
        combo = SearchCombo(spec.enum_values)
        if isinstance(value, str) and value:
            combo.setCurrentText(value)
        combo.currentTextChanged.connect(lambda text, k=spec.key: self.changed.emit(k, text.strip()))
        return combo

    def _make_list(self, spec, value):
        editor = NameListEditor(self._suggestions(spec.pool))
        editor.set_values(value if isinstance(value, list) else [])
        return editor

    # ------------------------------------------------------------------
    def collect_values(self):
        """Valeurs actuelles de TOUS les champs {key: str|list[str]} -- appelé
        avant chaque changement de selection et a la fermeture pour les
        widgets sans signal par modification (listes)."""
        out = {}
        for key, (kind, widget) in self._widgets.items():
            if kind in (KIND_NAMES, KIND_TYPES):
                out[key] = widget.values()
            elif kind == KIND_TOKEN:
                out[key] = widget.value()
            elif kind == KIND_TEXT:
                out[key] = widget.text().strip()
            elif kind == KIND_ENUM:
                out[key] = widget.value()
        return out
