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
Creation guidee d'une mission PDA -- voir core/pda_mission.py pour la
structure reelle (confirmee sur un vrai PDA.yaml, 530 chapitres) et les
limites assumees (les noms de cibles precis type 'XenuMainRG' restent en
saisie libre avec des suggestions issues du meme PDA.yaml, jamais extraits
de fichiers de blueprint, decision prise avec l'utilisateur).

Un seul palier (par defaut) -> un seul Chapter, avec repetition simple
optionnelle (RepeatConditions). Plusieurs paliers ("+ Ajouter un palier") ->
une CHAINE de Chapters distincts (voir core.pda_mission.create_tier_chain),
mecanisme reel different confirme sur une vraie chaine du jeu (RewardedChapters
+ Activatable: WhenRewarded) -- jamais RepeatConditions, qui ne fait que
repeter IDENTIQUEMENT le meme chapitre. La section Repetition est donc
desactivee des qu'un second palier est ajoute, pour rester coherent avec ce
qui est reellement observe."""
from typing import List, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit, QComboBox,
    QSpinBox, QCheckBox, QPushButton, QGroupBox, QListWidget, QListWidgetItem, QMessageBox,
    QWidget, QScrollArea,
)

from core.i18n import t
from core.pda_mission import (
    collect_used_names, collect_used_block_types, collect_all_tokens, generate_token,
    ObjectiveSpec, RewardSpec, RepeatSpec, TierSpec, create_chapter, create_tier_chain,
    add_pda_text_entries,
)
from gui.translate_context_menu import install_translate_context_menu

_CATEGORIES = ["SoloMission", "FactionMission", "Tutorial", "Knowledgebase", "FAQ"]
_REWARD_KINDS = ["XP", "UP", "Reputation", "Item"]


def _prioritize_credits_item(item_names: List[str]) -> List[str]:
    """Replace 'MoneyCard' (voir core.pda_mission.credits_reward_item_name)
    en tete de la liste de suggestions d'une recompense Item, quand ce nom
    existe reellement dans ItemsConfig.ecf -- c'est le vrai item du jeu qui
    represente les credits (chaque carte vaut 1 credit, confirme sur un vrai
    fichier : '## Please do not rename - referenced in code'), donc l'option
    la plus probable pour une recompense en argent. Ne fabrique JAMAIS ce nom
    s'il est absent des suggestions -- reste fidele au contenu reel du
    scenario."""
    from core.pda_mission import credits_reward_item_name
    credits_name = credits_reward_item_name()
    if credits_name not in item_names:
        return item_names
    return [credits_name] + [n for n in item_names if n != credits_name]


class _NameListEditor(QGroupBox):
    """Petite liste ajout/suppression avec suggestions -- meme principe que le
    choix d'ingredients pour un Template (gui/add_block_dialog.py), reutilise
    ici pour les listes Names/Types des objectifs PDA."""

    def __init__(self, title: str, suggestions: List[str], parent=None):
        super().__init__(title, parent)
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        row = QHBoxLayout()
        self.combo = QComboBox()
        self.combo.setEditable(True)
        self.combo.addItems(suggestions)
        self.combo.setCurrentText("")
        row.addWidget(self.combo, 1)
        btn_add = QPushButton(t("pda_mission.btn_add_value"))
        btn_add.clicked.connect(self._on_add)
        row.addWidget(btn_add)
        btn_remove = QPushButton(t("pda_mission.btn_remove_value"))
        btn_remove.clicked.connect(self._on_remove)
        row.addWidget(btn_remove)
        layout.addLayout(row)

    def _on_add(self):
        value = self.combo.currentText().strip()
        if value:
            self.list_widget.addItem(QListWidgetItem(value))
            self.combo.setCurrentText("")

    def _on_remove(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.list_widget.takeItem(row)

    def values(self) -> List[str]:
        return [self.list_widget.item(i).text() for i in range(self.list_widget.count())]

    def set_suggestions(self, suggestions: List[str]):
        """Remplace le contenu du menu deroulant de suggestions -- utilise
        pour basculer les suggestions du champ 'Noms des cibles' selon le
        type d'objectif choisi (SubjectKilled vs BlockDestroyed, voir
        _TierWidget._on_check_changed). Conserve le texte deja saisi si
        editable."""
        current_text = self.combo.currentText()
        self.combo.clear()
        self.combo.addItems(suggestions)
        self.combo.setCurrentText(current_text)


class _RewardRow(QWidget):
    def __init__(self, item_suggestions: List[str], on_remove, parent=None,
                 item_suggestions_players_only: Optional[List[str]] = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.kind_combo = QComboBox()
        self.kind_combo.addItems(_REWARD_KINDS)
        self.kind_combo.setToolTip(t("pda_mission.tooltip_reward_kind"))
        self.kind_combo.currentTextChanged.connect(self._on_kind_changed)
        layout.addWidget(self.kind_combo)

        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 999999)
        self.count_spin.setValue(100)
        self.count_spin.setToolTip(t("pda_mission.tooltip_reward_count"))
        layout.addWidget(self.count_spin)

        self.extra_combo = QComboBox()
        self.extra_combo.setEditable(True)
        self.extra_combo.setToolTip(t("pda_mission.tooltip_reward_extra"))
        self._item_suggestions = item_suggestions
        self._item_suggestions_players_only = item_suggestions_players_only or []
        layout.addWidget(self.extra_combo, 1)

        self.players_only_check = QCheckBox(t("ecf.players_only_checkbox"))
        self.players_only_check.setToolTip(t("ecf.tooltip_players_only"))
        self.players_only_check.toggled.connect(lambda _checked: self._on_kind_changed(self.kind_combo.currentText()))
        layout.addWidget(self.players_only_check)

        btn_remove = QPushButton(t("pda_mission.btn_remove_reward"))
        btn_remove.setToolTip(t("pda_mission.tooltip_remove_reward"))
        btn_remove.clicked.connect(lambda: on_remove(self))
        layout.addWidget(btn_remove)

        self._on_kind_changed(self.kind_combo.currentText())

    def _on_kind_changed(self, kind: str):
        self.extra_combo.clear()
        if kind == "Item":
            use_players_only = self.players_only_check.isChecked()
            source = self._item_suggestions_players_only if use_players_only else self._item_suggestions
            self.extra_combo.addItems(_prioritize_credits_item(source))
            self.extra_combo.setVisible(True)
            self.players_only_check.setVisible(True)
        elif kind == "Reputation":
            self.extra_combo.addItems(["Zirax", "Talon", "Polaris", "Colonists", "Trader"])
            self.extra_combo.setVisible(True)
            self.players_only_check.setVisible(False)
        else:
            self.extra_combo.setVisible(False)
            self.players_only_check.setVisible(False)

    def to_spec(self) -> RewardSpec:
        kind = self.kind_combo.currentText()
        if kind == "Item":
            return RewardSpec(kind="Item", item_name=self.extra_combo.currentText().strip(),
                               count=self.count_spin.value())
        if kind == "Reputation":
            return RewardSpec(kind="Reputation", faction=self.extra_combo.currentText().strip(),
                               count=self.count_spin.value())
        return RewardSpec(kind=kind, count=self.count_spin.value())


class _TierWidget(QGroupBox):
    """Un palier complet : titre/description propres, objectif propre,
    recompenses propres -- voir core.pda_mission.TierSpec, dont cette classe
    est le pendant GUI direct."""

    def __init__(self, doc, item_suggestions: List[str], tier_number: int, parent=None,
                 item_suggestions_players_only: Optional[List[str]] = None,
                 mining_name_suggestions: Optional[List[str]] = None):
        super().__init__(t("pda_mission.tier_group_title", n=tier_number), parent)
        self._item_suggestions = item_suggestions
        self._item_suggestions_players_only = item_suggestions_players_only or []
        self.reward_rows: List[_RewardRow] = []

        # Suggestions du champ "Noms des cibles" -- DEPENDENT du type
        # d'objectif choisi (bug corrige : c'etait fige sur SubjectKilled
        # quel que soit le choix). BlockDestroyed melange les noms deja
        # utilises pour ce type d'action ET les vrais noms de ressources
        # minables (voir core.pda_mission.list_mining_target_name_suggestions).
        self._subject_killed_name_suggestions = collect_used_names(doc, "SubjectKilled")
        self._block_destroyed_name_suggestions = sorted(
            set(collect_used_names(doc, "BlockDestroyed")) | set(mining_name_suggestions or []))
        layout = QVBoxLayout(self)

        text_layout = QFormLayout()
        self.title_en_edit = QLineEdit()
        self.title_en_edit.setToolTip(t("pda_mission.tooltip_title_en"))
        install_translate_context_menu(self.title_en_edit)
        text_layout.addRow(t("pda_mission.title_en"), self.title_en_edit)
        self.title_fr_edit = QLineEdit()
        self.title_fr_edit.setToolTip(t("pda_mission.tooltip_title_fr"))
        install_translate_context_menu(self.title_fr_edit)
        text_layout.addRow(t("pda_mission.title_fr"), self.title_fr_edit)
        self.desc_en_edit = QLineEdit()
        self.desc_en_edit.setToolTip(t("pda_mission.tooltip_desc_en"))
        install_translate_context_menu(self.desc_en_edit)
        text_layout.addRow(t("pda_mission.desc_en"), self.desc_en_edit)
        self.desc_fr_edit = QLineEdit()
        self.desc_fr_edit.setToolTip(t("pda_mission.tooltip_desc_fr"))
        install_translate_context_menu(self.desc_fr_edit)
        text_layout.addRow(t("pda_mission.desc_fr"), self.desc_fr_edit)
        layout.addLayout(text_layout)

        obj_box = QGroupBox(t("pda_mission.section_objective"))
        obj_layout = QVBoxLayout(obj_box)
        self.check_combo = QComboBox()
        self.check_combo.addItem(t("pda_mission.check_kill"), "SubjectKilled")
        self.check_combo.addItem(t("pda_mission.check_destroy_or_mine"), "BlockDestroyed")
        self.check_combo.setToolTip(t("pda_mission.tooltip_check"))
        self.check_combo.currentIndexChanged.connect(self._on_check_changed)
        obj_layout.addWidget(self.check_combo)

        self.names_editor = _NameListEditor(t("pda_mission.names_label"),
                                             self._subject_killed_name_suggestions)
        obj_layout.addWidget(self.names_editor)

        self.types_editor = _NameListEditor(t("pda_mission.types_label"),
                                             collect_used_block_types(doc))
        self.types_editor.setToolTip(t("pda_mission.tooltip_types"))
        obj_layout.addWidget(self.types_editor)

        amount_row = QHBoxLayout()
        amount_label = QLabel(t("pda_mission.amount"))
        amount_label.setToolTip(t("pda_mission.tooltip_amount"))
        amount_row.addWidget(amount_label)
        self.amount_spin = QSpinBox()
        self.amount_spin.setRange(1, 999999)
        self.amount_spin.setValue(10)
        self.amount_spin.setToolTip(t("pda_mission.tooltip_amount"))
        amount_row.addWidget(self.amount_spin)
        amount_row.addStretch()
        obj_layout.addLayout(amount_row)
        layout.addWidget(obj_box)

        rewards_box = QGroupBox(t("pda_mission.section_rewards"))
        rewards_box.setToolTip(t("pda_mission.tooltip_rewards"))
        self.rewards_layout = QVBoxLayout(rewards_box)
        btn_add_reward = QPushButton(t("pda_mission.btn_add_reward"))
        btn_add_reward.clicked.connect(self._add_reward_row)
        self.rewards_layout.addWidget(btn_add_reward)
        layout.addWidget(rewards_box)
        self._add_reward_row()

        self._on_check_changed(0)

    def _on_check_changed(self, index: int):
        check_type = self.check_combo.currentData()
        self.types_editor.setVisible(check_type == "BlockDestroyed")
        if check_type == "SubjectKilled":
            self.names_editor.setToolTip(t("pda_mission.tooltip_names_kill"))
            self.names_editor.set_suggestions(self._subject_killed_name_suggestions)
        else:
            self.names_editor.setToolTip(t("pda_mission.tooltip_names_destroy_or_mine"))
            self.names_editor.set_suggestions(self._block_destroyed_name_suggestions)

    def _add_reward_row(self):
        row = _RewardRow(self._item_suggestions, self._remove_reward_row,
                          item_suggestions_players_only=self._item_suggestions_players_only)
        self.reward_rows.append(row)
        self.rewards_layout.insertWidget(self.rewards_layout.count() - 1, row)

    def _remove_reward_row(self, row):
        if row in self.reward_rows:
            self.reward_rows.remove(row)
            self.rewards_layout.removeWidget(row)
            row.setParent(None)
            row.deleteLater()

    def set_tier_number(self, n: int):
        self.setTitle(t("pda_mission.tier_group_title", n=n))

    def validate(self) -> Optional[str]:
        """Retourne un message d'erreur (cle deja traduite) si ce palier est
        incomplet, sinon None."""
        if not self.title_en_edit.text().strip():
            return t("pda_mission.err_title_required")
        if not self.names_editor.values():
            return t("pda_mission.err_names_required")
        return None

    def to_tier_spec(self) -> TierSpec:
        check_type = self.check_combo.currentData()
        types_values = self.types_editor.values() if check_type == "BlockDestroyed" else None
        objective = ObjectiveSpec(check_type=check_type, names=self.names_editor.values(),
                                   amount=self.amount_spin.value(), types=types_values)
        rewards = [row.to_spec() for row in self.reward_rows]
        title_en = self.title_en_edit.text().strip()
        desc_en = self.desc_en_edit.text().strip()
        return TierSpec(title_text=title_en, description_text=desc_en,
                         objective=objective, rewards=rewards)


class PdaMissionDialog(QDialog):
    def __init__(self, doc, csv_doc, sibling_ecf_files: Optional[list] = None, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.csv_doc = csv_doc
        self.setWindowTitle(t("pda_mission.title"))
        self.setMinimumSize(720, 800)
        self.tier_widgets: List[_TierWidget] = []

        self._item_suggestions = []
        self._item_suggestions_players_only = []
        self._mining_name_suggestions = []
        if sibling_ecf_files:
            from core.ecf.block_creation import find_file_by_name, list_craftable_names
            from core.pda_mission import list_mining_target_name_suggestions
            items_path = find_file_by_name(sibling_ecf_files, "ItemsConfig.ecf")
            blocks_path = find_file_by_name(sibling_ecf_files, "BlocksConfig.ecf")
            self._item_suggestions = list_craftable_names(items_path, blocks_path)
            self._item_suggestions_players_only = list_craftable_names(
                items_path, blocks_path, players_only=True)
            if blocks_path:
                self._mining_name_suggestions = list_mining_target_name_suggestions([blocks_path])

        outer_layout = QVBoxLayout(self)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel(t("pda_mission.category")))
        self.category_combo = QComboBox()
        self.category_combo.addItems(_CATEGORIES)
        self.category_combo.setToolTip(t("pda_mission.tooltip_category"))
        top_row.addWidget(self.category_combo)
        top_row.addStretch()
        outer_layout.addLayout(top_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._tiers_container = QWidget()
        self.tiers_layout = QVBoxLayout(self._tiers_container)
        scroll.setWidget(self._tiers_container)
        outer_layout.addWidget(scroll, 1)

        btn_add_tier = QPushButton(t("pda_mission.btn_add_tier"))
        btn_add_tier.setToolTip(t("pda_mission.tooltip_add_tier"))
        btn_add_tier.clicked.connect(self._add_tier)
        outer_layout.addWidget(btn_add_tier)

        self.repeat_box = QGroupBox(t("pda_mission.section_repeat"))
        repeat_layout = QFormLayout(self.repeat_box)
        self.repeatable_check = QCheckBox(t("pda_mission.repeatable_checkbox"))
        self.repeatable_check.setToolTip(t("pda_mission.tooltip_repeatable"))
        self.repeatable_check.toggled.connect(self._on_repeatable_toggled)
        repeat_layout.addRow(self.repeatable_check)
        self.num_repeats_spin = QSpinBox()
        self.num_repeats_spin.setRange(1, 999)
        self.num_repeats_spin.setValue(5)
        self.num_repeats_spin.setEnabled(False)
        self.num_repeats_spin.setToolTip(t("pda_mission.tooltip_num_repeats"))
        repeat_layout.addRow(t("pda_mission.num_repeats"), self.num_repeats_spin)
        self.delay_hours_spin = QSpinBox()
        self.delay_hours_spin.setRange(0, 999)
        self.delay_hours_spin.setValue(1)
        self.delay_hours_spin.setEnabled(False)
        self.delay_hours_spin.setToolTip(t("pda_mission.tooltip_delay_hours"))
        repeat_layout.addRow(t("pda_mission.delay_hours"), self.delay_hours_spin)
        outer_layout.addWidget(self.repeat_box)

        self._add_tier()

        buttons = QHBoxLayout()
        buttons.addStretch()
        btn_cancel = QPushButton(t("btn.cancel"))
        btn_cancel.setObjectName("secondaryButton")
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_cancel)
        btn_create = QPushButton(t("pda_mission.btn_create"))
        btn_create.setObjectName("primaryButton")
        btn_create.clicked.connect(self._on_create)
        buttons.addWidget(btn_create)
        outer_layout.addLayout(buttons)

    def _add_tier(self):
        tier = _TierWidget(self.doc, self._item_suggestions, len(self.tier_widgets) + 1,
                            item_suggestions_players_only=self._item_suggestions_players_only,
                            mining_name_suggestions=self._mining_name_suggestions)
        self.tier_widgets.append(tier)
        self.tiers_layout.addWidget(tier)
        self._update_repeat_availability()

    def _update_repeat_availability(self):
        """La repetition simple (RepeatConditions) ne s'applique qu'a une
        mission a un seul palier -- voir docstring de tete de module. Des
        qu'un second palier existe, on utilise l'enchainement de chapitres a
        la place, jamais les deux mecanismes combines."""
        single_tier = len(self.tier_widgets) == 1
        self.repeat_box.setEnabled(single_tier)
        if not single_tier:
            self.repeatable_check.setChecked(False)

    def _on_repeatable_toggled(self, checked: bool):
        self.num_repeats_spin.setEnabled(checked)
        self.delay_hours_spin.setEnabled(checked)

    def _on_create(self):
        for tier in self.tier_widgets:
            error = tier.validate()
            if error:
                QMessageBox.warning(self, t("pda_mission.title"), error)
                return

        category = self.category_combo.currentText()

        if len(self.tier_widgets) == 1:
            tier_widget = self.tier_widgets[0]
            objective = tier_widget.to_tier_spec().objective
            rewards = [row.to_spec() for row in tier_widget.reward_rows]
            repeat = RepeatSpec(
                num_repeats=self.num_repeats_spin.value() if self.repeatable_check.isChecked() else 0,
                delay_seconds=self.delay_hours_spin.value() * 3600,
            )
            tokens_used = collect_all_tokens(self.doc)

            def new_tok():
                token = generate_token(tokens_used)
                tokens_used.add(token)
                return token

            title_token, desc_token = new_tok(), new_tok()
            task_token, action_title_token, action_desc_token = new_tok(), new_tok(), new_tok()

            chapter = create_chapter(
                self.doc, title_token, desc_token, category,
                [objective], rewards, repeat, task_token, [(action_title_token, action_desc_token)],
            )
            if chapter is None:
                QMessageBox.critical(self, t("pda_mission.title"), t("pda_mission.err_no_chapters_key"))
                return

            title_en = tier_widget.title_en_edit.text().strip()
            title_fr = tier_widget.title_fr_edit.text().strip() or title_en
            desc_en = tier_widget.desc_en_edit.text().strip()
            desc_fr = tier_widget.desc_fr_edit.text().strip() or desc_en
            add_pda_text_entries(self.csv_doc, [
                (title_token, title_en, title_fr),
                (desc_token, desc_en, desc_fr),
                (task_token, title_en, title_fr),
                (action_title_token, title_en, title_fr),
                (action_desc_token, desc_en, desc_fr),
            ])
        else:
            tiers = [tw.to_tier_spec() for tw in self.tier_widgets]
            chapters = create_tier_chain(self.doc, self.csv_doc, tiers, category)
            if not chapters:
                QMessageBox.critical(self, t("pda_mission.title"), t("pda_mission.err_no_chapters_key"))
                return

        self.accept()
