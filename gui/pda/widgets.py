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

"""Widgets partages du NOUVEAU module PDA.

Principes respectes (regles projet) :
- COMBOS EDITABLES avec saisie libre TOUJOURS permise (QCompleter pour la
  recherche -- jamais de blocage a une liste) ;
- textes localises via TokenTextField : l'utilisateur tape du TEXTE, le YAML
  ne stocke qu'un jeton pda_XXXXXXX resolu dans PDA.csv ; anti-doublon : si
  le texte existe deja (hors balises de mise en forme), le jeton existant est
  REUTILISE (comportement confirme utile, repris de l'exemple eWPDA) ;
- traduction : le menu contextuel existant (gui/translate_context_menu.py)
  est installe sur chaque champ texte -- rien de nouveau a inventer."""
import re

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                             QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                             QListWidget, QListWidgetItem, QPushButton,
                             QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from core.i18n import t


_TAG_RE = re.compile(r"\[/?.{1,32}?\]")

TAG_COLORS = ("#00ffff", "#0088ff", "#ff0000", "#ffffff", "#00ff00", "#ffee00")


def normalize_text(text: str) -> str:
    """Normalise un texte PDA pour l'anti-doublon : retire les balises de
    mise en forme Empyrion ([c][ffffff], [b], [-]...) et casefold."""
    cleaned = _TAG_RE.sub("", text or "")
    return " ".join(cleaned.split()).casefold()


def _reference_column() -> str:
    """Colonne CSV correspondant a la langue de l'application (fr -> Français,
    en -> English) -- les autres langues passent par l'editeur multilingue."""
    try:
        from core.settings import get_language
        return "Français" if get_language().lower().startswith("fr") else "English"
    except Exception:
        return "English"


class SearchCombo(QComboBox):
    """Combo editable + completer (recherche insensible a la casse, saisie
    libre). Les suggestions viennent des pools PdaSuggestions."""

    def __init__(self, suggestions=(), parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.set_suggestions(suggestions)

    def set_suggestions(self, suggestions):
        current = self.currentText()
        self.clear()
        self.addItems(sorted(suggestions))
        self.setCurrentText(current)

    def value(self) -> str:
        return self.currentText().strip()


class TokenTextField(QWidget):
    """Edition d'un texte localise : affiche le texte resolu (colonne de
    reference selon la langue de l'appli), stocke un jeton pda_XXXXXXX.
    value() retourne la VALEUR A ECRIRE DANS LE YAML ('' si champ vide) :
    'prefix|token' quand la valeur d'origine portait un prefixe de format
    ('mbox;20|pda_KaOsQr' -- style;duree, confirme sur les vrais fichiers),
    le jeton seul sinon.
    Le menu contextuel de traduction existant est installe sur le champ."""

    def __init__(self, model, allow_empty=True, multiline_hint=False, parent=None):
        super().__init__(parent)
        self.model = model
        self.token = ""
        self.prefix = ""       # prefixe de format ('mbox;20') ou ''
        self.raw_text = ""     # valeur d'origine NON jeton (texte brut YAML)
        self._loading = False
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(t("pda.token_field.placeholder"))
        self.edit.textEdited.connect(self._on_text_edited)
        layout.addWidget(self.edit, 1)
        self.btn_langs = QPushButton()
        self.btn_langs.setFixedWidth(34)
        self.btn_langs.setToolTip(t("pda.token_field.all_langs"))
        # Icône qtawesome fa5s.globe de l'application : le glyphe emoji "🌐"
        # ne se rend PAS sous Windows/Qt (carre bleu, retour utilisateur du
        # 31/08/2026) -- theme.icon() degrade proprement si qtawesome absent.
        from gui.theme import icon as theme_icon
        self.btn_langs.setIcon(theme_icon("fa5s.globe"))
        self.btn_langs.clicked.connect(self._open_multilang)
        layout.addWidget(self.btn_langs)
        self.state_label = QLabel("")
        self.state_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.state_label)
        from gui.translate_context_menu import install_translate_context_menu
        install_translate_context_menu(self.edit)

    def set_token(self, value: str):
        """Charge une valeur YAML brute : 'prefix|token', jeton pur, texte
        brut (affiche tel quel, converti en jeton a la premiere edition) ou
        vide."""
        self._loading = True
        from core.pda.model import _TOKEN_RE, split_token_value
        self.prefix, candidate = split_token_value(value or "")
        self.raw_text = ""
        text = ""
        if _TOKEN_RE.match(candidate):
            self.token = candidate
            text = self.model.csv_text(self.token, _reference_column())
            if not text:
                text = self.model.csv_text(self.token, "English")
            if not text:
                # Repli : affiche le jeton brut (comme l'arbre) pour qu'un
                # titre sans traduction reste VISIBLE et modifiable.
                text = f"{self.prefix}|{self.token}" if self.prefix else self.token
        elif value:
            # Texte brut non localise : affiche tel quel, PRESERVE tant que
            # l'utilisateur ne touche pas au champ (value() le rejoue).
            self.token = ""
            self.raw_text = value
            text = value
        else:
            self.token = ""
        self.edit.setText(text)
        self._update_state()
        self._loading = False

    def value(self) -> str:
        """Valeur a ecrire dans le YAML ('' si le champ est vide)."""
        if self.token:
            return f"{self.prefix}|{self.token}" if self.prefix else self.token
        return self.raw_text

    def _on_text_edited(self, text: str):
        if self._loading:
            return
        text = text.strip()
        self.raw_text = ""
        if not text:
            # Le prefixe de format ('mbox;20') est une propriete de
            # l'emplacement, pas du texte : il est CONSERVE pour la prochaine
            # saisie (value() retourne '' tant que le champ est vide).
            self.token = ""
            self._update_state()
            return
        # Anti-doublon : reutilise le jeton existant si le texte (hors balises)
        # est deja present dans le CSV.
        existing = self._find_existing_token(text)
        if existing and existing != self.token:
            self.token = existing
        elif not self.token:
            self.token = self.model.new_token(self.model.collect_all_tokens())
        self.model.set_csv_text(self.token, text, _reference_column())
        self._update_state()

    def _find_existing_token(self, text: str):
        wanted = normalize_text(text)
        if not wanted:
            return None
        column = _reference_column()
        idx = self.model.csv_column_index(column)
        fallback = self.model.csv_column_index("English")
        for row in self.model.csv_doc.rows:
            if not row or not (row[0].startswith("pda_") or "_pda_" in row[0]):
                continue
            for i in (idx, fallback):
                if i is not None and i < len(row) and normalize_text(row[i]) == wanted:
                    return row[0]
        return None

    def _update_state(self):
        if not self.token:
            self.state_label.setText("")
            return
        translated = self.model.csv_text(self.token, "English")
        mark = "✔" if translated else "⚠"
        shown = f"{self.prefix}|{self.token}" if self.prefix else self.token
        self.state_label.setText(f"{mark} {shown}")
        self.state_label.setToolTip(t("pda.token_field.token_tooltip", token=shown))

    def _open_multilang(self):
        if not self.token:
            text = self.edit.text().strip()
            if text:
                self._on_text_edited(text)
            if not self.token:
                self.token = self.model.new_token(self.model.collect_all_tokens())
        dlg = MultiLanguageEditor(self.model, self.token, self)
        dlg.exec()


class MultiLanguageEditor(QDialog):
    """Edition d'un jeton dans TOUTES les langues du PDA.csv (les autres
    langues restent vides si non saisies, comme dans les vrais fichiers)."""

    def __init__(self, model, token, parent=None):
        super().__init__(parent)
        self.model = model
        self.token = token
        self.setWindowTitle(t("pda.multilang.title", token=token))
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.editors = {}
        for lang in model.csv_languages():
            edit = QLineEdit(model.csv_text(token, lang))
            install_translate(edit)
            form.addRow(lang, edit)
            self.editors[lang] = edit
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        for lang, edit in self.editors.items():
            self.model.set_csv_text(self.token, edit.text().strip(), lang)
        super().accept()


def install_translate(edit):
    from gui.translate_context_menu import install_translate_context_menu
    install_translate_context_menu(edit)


class NameListEditor(QWidget):
    """Edition d'une liste Names/Types : QListWidget + combo editable avec
    suggestions (pool) + ajout/suppression + montee/descente. Saisie libre
    toujours permise (regle projet)."""

    def __init__(self, suggestions=(), parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.list_widget = QListWidget()
        self.list_widget.setMinimumHeight(60)
        layout.addWidget(self.list_widget)
        row = QHBoxLayout()
        self.combo = SearchCombo(suggestions)
        self.combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.combo.setMinimumContentsLength(12)
        row.addWidget(self.combo, 1)
        btn_add = QPushButton(t("pda.list.add"))
        btn_add.clicked.connect(self._on_add)
        row.addWidget(btn_add)
        btn_del = QPushButton(t("pda.list.remove"))
        btn_del.clicked.connect(self._on_remove)
        row.addWidget(btn_del)
        btn_up = QPushButton("▲")
        btn_up.setFixedWidth(30)
        btn_up.setToolTip(t("pda.list.up"))
        btn_up.clicked.connect(lambda: self._move(-1))
        row.addWidget(btn_up)
        btn_down = QPushButton("▼")
        btn_down.setFixedWidth(30)
        btn_down.setToolTip(t("pda.list.down"))
        btn_down.clicked.connect(lambda: self._move(1))
        row.addWidget(btn_down)
        layout.addLayout(row)

    def _on_add(self):
        value = self.combo.value()
        if value:
            self.list_widget.addItem(QListWidgetItem(value))
            self.combo.setCurrentText("")

    def _on_remove(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.list_widget.takeItem(row)

    def _move(self, delta):
        row = self.list_widget.currentRow()
        if row < 0:
            return
        new_row = row + delta
        if new_row < 0 or new_row >= self.list_widget.count():
            return
        item = self.list_widget.takeItem(row)
        self.list_widget.insertItem(new_row, item)
        self.list_widget.setCurrentRow(new_row)

    def values(self):
        return [self.list_widget.item(i).text().strip()
                for i in range(self.list_widget.count())
                if self.list_widget.item(i).text().strip()]

    def set_values(self, values):
        self.list_widget.clear()
        for v in values:
            self.list_widget.addItem(QListWidgetItem(v))


class RewardsEditor(QWidget):
    """Edition des recompenses (chapitre OU tache) : formes confirmees
    Item+Count[+Meta] / Type+Count[+Faction][+Meta] -- voir schema."""

    def __init__(self, item_suggestions=(), faction_suggestions=(), parent=None):
        super().__init__(parent)
        self.item_suggestions = item_suggestions
        self.faction_suggestions = faction_suggestions
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout = QVBoxLayout()
        layout.addLayout(self.rows_layout)
        btn_add = QPushButton(t("pda.rewards.add"))
        btn_add.clicked.connect(self.add_row)
        layout.addWidget(btn_add)

    def add_row(self, reward=None):
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        kind_w = SearchCombo(["Item", "XP", "UP", "Reputation",
                              "ReputationTarget", "LevelTarget", "LevelIncrease"])
        name_w = SearchCombo(self.item_suggestions)
        count_w = QSpinBox()
        # Pas de plafond "999" : la taille de pile depend des items du
        # SCENARIO (MaxCount, souvent bien superieur a 999) et le jeu
        # DECOMPOSE automatiquement les recompenses en plusieurs piles
        # (retour utilisateur du 12/09/2026 : MoneyCard pile 50000,
        # recompense 100000 -> deux piles de 50000).
        count_w.setRange(1, 999999)
        count_w.setValue(1)
        faction_w = SearchCombo(self.faction_suggestions)
        meta_w = QLineEdit()
        meta_w.setPlaceholderText(t("pda.rewards.meta"))
        meta_w.setMaximumWidth(70)
        btn_del = QPushButton(t("pda.list.remove"))
        lay.addWidget(QLabel(t("pda.rewards.kind")))
        lay.addWidget(kind_w)
        lay.addWidget(name_w, 1)
        lay.addWidget(QLabel(t("pda.rewards.count")))
        lay.addWidget(count_w)
        lay.addWidget(QLabel(t("pda.rewards.faction")))
        lay.addWidget(faction_w)
        lay.addWidget(meta_w)
        lay.addWidget(btn_del)
        faction_w.setVisible(False)
        row._fields = (kind_w, name_w, count_w, faction_w, meta_w)

        def on_kind(text):
            is_item = text == "Item"
            name_w.set_suggestions(self.item_suggestions if is_item else [])
            name_w.setCurrentText(reward.name if reward else "")
            faction_w.setVisible(text in ("Reputation", "ReputationTarget"))

        kind_w.currentTextChanged.connect(on_kind)
        if reward:
            kind_w.setCurrentText("Item" if reward.kind == "Item" else reward.name
                                  if reward.kind == "Type" else reward.kind)
            # pour Type: le combo kind porte le type lui-meme (XP/UP/...)
            if reward.kind == "Type":
                kind_w.setCurrentText(reward.name)
                name_w.setCurrentText("")
            count_w.setValue(reward.count)
            faction_w.setCurrentText(reward.faction)
            meta_w.setText(reward.meta)
        btn_del.clicked.connect(lambda: self._remove_row(row))
        self.rows_layout.addWidget(row)
        on_kind(kind_w.currentText())

    def _remove_row(self, row):
        self.rows_layout.removeWidget(row)
        row.deleteLater()

    def values(self):
        from core.pda.model import RewardEntry
        out = []
        for i in range(self.rows_layout.count()):
            row = self.rows_layout.itemAt(i).widget()
            if row is None or not hasattr(row, "_fields"):
                continue
            kind_w, name_w, count_w, faction_w, meta_w = row._fields
            kind_text = kind_w.currentText()
            if kind_text == "Item":
                out.append(RewardEntry(kind="Item", name=name_w.value(),
                                       count=count_w.value(), faction="",
                                       meta=meta_w.text().strip()))
            else:
                out.append(RewardEntry(kind="Type", name=kind_text,
                                       count=count_w.value(),
                                       faction=faction_w.value() if faction_w.isVisible() else "",
                                       meta=meta_w.text().strip()))
        return out

    def set_values(self, rewards):
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for r in rewards:
            self.add_row(r)


class IntField(QSpinBox):
    """Spin generique sans borne abusive (valeurs PDA parfois grandes)."""

    def __init__(self, value="", parent=None):
        super().__init__(parent)
        self.setRange(-999999, 999999)
        try:
            self.setValue(int(str(value).strip()))
        except (TypeError, ValueError):
            self.setValue(0)
