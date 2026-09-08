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

"""ASSISTANT de creation PDA (nouveau module) -- 3 etapes qui construisent un
chapitre complet : caracteristiques, actions de la premiere tache, textes +
recompenses. A la validation, le chapitre cree est retourné a l'appelant
(self.created_chapter) pour etre selectionne dans l'editeur complet (le
wizard n'ecrit jamais lui-meme : il passe par le meme PdaModel).

Perimetre assume : le wizard pose une BASE SAINe (chapitre + tache + actions
de types courants) ; les structures avancees (multi-taches, activites,
chainage, repetition fine) se font dans l'editeur complet."""
from PyQt6.QtWidgets import (QCheckBox, QDialog, QFormLayout, QHBoxLayout,
                             QLabel, QMessageBox, QPushButton, QSpinBox,
                             QVBoxLayout, QWidget)

from core.i18n import t
from core.pda.model import CHAPTER_REQUIRED_DEFAULTS
from core.pda.schema import ACTIVATABLE, CATEGORIES, VISIBILITY, action_fields
from gui.pda.form import SpecForm
from gui.pda.widgets import RewardsEditor, SearchCombo, TokenTextField

# Types d'actions proposes a l'etape 2 (les plus courants, confirmes sur les
# fichiers de reference) ; le reste reste accessible via l'editeur complet.
_TEMPLATE_CHECKS = ("WaitAction", "NearPoi", "SubjectKilled", "BlockDestroyed",
                    "ItemsPickedUp", "DialogOption", "PlayfieldEntered")


class _ActionEditor(QWidget):
    """Une action de l'etape 2 : type de Check + formulaire de ses champs.
    Seules les valeurs EXPLICITEMENT modifiees (signaux) sont retenues dans
    applied -- a la creation on n'ecrit jamais un champ non touche, pour ne
    pas polluer le fichier avec des valeurs par defaut invisibles."""

    def __init__(self, model, suggestions, on_remove, parent=None):
        super().__init__(parent)
        self.applied = {}
        self.current_check = _TEMPLATE_CHECKS[0]
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel(t("pda.wizard.check")))
        self.check_combo = SearchCombo(_TEMPLATE_CHECKS)
        row.addWidget(self.check_combo, 1)
        btn_del = QPushButton(t("pda.wizard.remove_action"))
        btn_del.clicked.connect(lambda: on_remove(self))
        row.addWidget(btn_del)
        layout.addLayout(row)
        self.form = SpecForm(model, lambda pool: suggestions.pool(pool) if suggestions else [])
        self.form.changed.connect(self._on_changed)
        layout.addWidget(self.form)
        self.check_combo.currentTextChanged.connect(self._on_check_changed)
        self._on_check_changed(self.check_combo.currentText())

    def _on_changed(self, key, value):
        self.applied[key] = value

    def _on_check_changed(self, check):
        # Le lineEdit interne d'un QComboBox editable cache peut renvoyer ''
        # (piege Qt observe en test) : la valeur de reference est MEMORISEE
        # ici, jamais relue depuis le widget au moment de la creation.
        check = (check or "").strip()
        if check:
            self.current_check = check
        fields = action_fields(self.current_check)
        defaults = {}
        for spec in fields:
            if spec.kind in ("names", "types"):
                defaults[spec.key] = []
            else:
                defaults[spec.key] = spec.default
        self.form.build(fields, defaults)


class CreateWizard(QDialog):
    def __init__(self, model, suggestions, parent=None):
        super().__init__(parent)
        self.model = model
        self.suggestions = suggestions
        self.created_chapter = None
        self.setWindowTitle(t("pda.wizard.title"))
        self.setMinimumSize(860, 680)

        layout = QVBoxLayout(self)
        self.step_label = QLabel("")
        self.step_label.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(self.step_label)

        # ---------- etape 1 : caracteristiques
        self.page1 = QWidget()
        form1 = QFormLayout(self.page1)
        self.category_combo = SearchCombo(CATEGORIES)
        self.category_combo.setCurrentText("SoloMission")
        form1.addRow(t("pda.chapter.category"), self.category_combo)
        self.level_spin = QSpinBox()
        self.level_spin.setRange(1, 50)
        self.level_spin.setValue(1)
        form1.addRow(t("pda.chapter.player_level"), self.level_spin)
        self.activatable_combo = SearchCombo(ACTIVATABLE)
        form1.addRow(t("pda.chapter.activatable"), self.activatable_combo)
        self.visibility_combo = SearchCombo(VISIBILITY)
        form1.addRow(t("pda.chapter.visibility"), self.visibility_combo)
        self.noskip_check = QCheckBox(t("pda.chapter.noskip"))
        self.noskip_check.setChecked(True)
        form1.addRow(self.noskip_check)
        layout.addWidget(self.page1)

        # ---------- etape 2 : actions de la premiere tache
        self.page2 = QWidget()
        lay2 = QVBoxLayout(self.page2)
        lay2.addWidget(QLabel(t("pda.wizard.actions_hint")))
        self.actions_area = QVBoxLayout()
        lay2.addLayout(self.actions_area)
        btn_add_action = QPushButton(t("pda.wizard.add_action"))
        btn_add_action.clicked.connect(self._add_action_editor)
        lay2.addWidget(btn_add_action)
        lay2.addStretch()
        layout.addWidget(self.page2)

        # ---------- etape 3 : textes + recompenses
        self.page3 = QWidget()
        lay3 = QVBoxLayout(self.page3)
        form3 = QFormLayout()
        self.title_field = TokenTextField(self.model)
        form3.addRow(t("pda.wizard.chapter_title"), self.title_field)
        self.desc_field = TokenTextField(self.model)
        form3.addRow(t("pda.chapter.description"), self.desc_field)
        self.task_title_field = TokenTextField(self.model)
        form3.addRow(t("pda.wizard.task_title"), self.task_title_field)
        lay3.addLayout(form3)
        lay3.addWidget(QLabel(f"<b>{t('pda.chapter.rewards')}</b>"))
        self.rewards = RewardsEditor(
            suggestions.pool("item") if suggestions else [],
            suggestions.pool("faction") if suggestions else [])
        lay3.addWidget(self.rewards)
        layout.addWidget(self.page3)

        # ---------- navigation
        nav = QHBoxLayout()
        self.btn_back = QPushButton(t("pda.wizard.back"))
        self.btn_back.clicked.connect(lambda: self._go(-1))
        nav.addWidget(self.btn_back)
        nav.addStretch()
        self.btn_next = QPushButton(t("pda.wizard.next"))
        self.btn_next.setObjectName("primaryButton")
        self.btn_next.clicked.connect(lambda: self._go(1))
        nav.addWidget(self.btn_next)
        self.btn_create = QPushButton(t("pda.wizard.create"))
        self.btn_create.setObjectName("primaryButton")
        self.btn_create.clicked.connect(self._on_create)
        nav.addWidget(self.btn_create)
        btn_cancel = QPushButton(t("btn.cancel"))
        btn_cancel.setObjectName("secondaryButton")
        btn_cancel.clicked.connect(self.reject)
        nav.addWidget(btn_cancel)
        layout.addLayout(nav)

        self._step = 0
        self._action_editors = []
        self._page1_snapshot = None
        self._go(0)

    # ------------------------------------------------------------------
    def _go(self, delta):
        if delta > 0 and self._step == 0:
            # Snapshot des choix de la page 1 AVANT qu'elle ne soit cachee :
            # le lineEdit interne d'un QComboBox editable cache peut renvoyer
            # '' (piege Qt observe en test -- voir _ActionEditor).
            self._page1_snapshot = (
                self.category_combo.value() or "SoloMission",
                str(self.level_spin.value()),
                self.activatable_combo.value() or "Always",
                self.visibility_combo.value() or "Always",
                self.noskip_check.isChecked(),
            )
        self._step = max(0, min(2, self._step + delta))
        titles = (t("pda.wizard.step1"), t("pda.wizard.step2"), t("pda.wizard.step3"))
        self.step_label.setText(titles[self._step])
        self.page1.setVisible(self._step == 0)
        self.page2.setVisible(self._step == 1)
        self.page3.setVisible(self._step == 2)
        self.btn_back.setEnabled(self._step > 0)
        self.btn_next.setVisible(self._step < 2)
        self.btn_create.setVisible(self._step == 2)

    def _add_action_editor(self):
        editor = _ActionEditor(self.model, self.suggestions, self._remove_action_editor)
        self._action_editors.append(editor)
        self.actions_area.addWidget(editor)

    def _remove_action_editor(self, editor):
        if editor in self._action_editors:
            self._action_editors.remove(editor)
        editor.deleteLater()

    # ------------------------------------------------------------------
    def _on_create(self):
        title_token = self.title_field.value()
        if not title_token:
            QMessageBox.warning(self, t("pda.wizard.title"), t("pda.wizard.err_title"))
            return
        # Snapshot + journal via le dialogue editeur parent (s'il existe)
        from gui.pda.editor_dialog import PdaEditorDialog
        dlg = self.parent()
        dlg = dlg if isinstance(dlg, PdaEditorDialog) else None
        if dlg is not None:
            dlg.push_undo()
        desc_token = self.desc_field.value() or title_token
        task_token = self.task_title_field.value() or title_token
        if self._page1_snapshot is None:
            self._go(1)  # restore le snapshot si l'utilisateur a saute la page
        category, level, activatable, visibility, noskip = self._page1_snapshot

        chapter = self.model.create_chapter()
        # LE TITRE : create_chapter pose un jeton aleatoire sur la ligne
        # '- ChapterTitle:' -- le remplacer par le jeton du champ titre (bug
        # retour utilisateur : le titre saisi n'etait jamais applique, le
        # chapitre gardait un jeton brut sans texte).
        chapter.set_own_value(title_token)
        for key, value in (
                ("Category", category),
                ("PlayerLevel", level),
                ("Activatable", activatable),
                ("Visibility", visibility),
                ("NoSkip", "true" if noskip else ""),
                ("Description", desc_token),
        ):
            self.model.set_scalar(chapter, key, value, CHAPTER_REQUIRED_DEFAULTS)

        task = self.model.create_task(chapter)
        # create_task a deja pose un jeton TaskTitle sur la LIGNE '- TaskTitle:'
        # -- le remplacer se fait sur l'entree elle-meme (set_own_value),
        # JAMAIS via set_scalar qui creerait un enfant homonyme (doublon au
        # re-parse).
        if task_token:
            task.set_own_value(task_token)

        for editor in self._action_editors:
            check = editor.current_check
            action = self.model.create_action(task, check)
            for key, value in editor.applied.items():
                if isinstance(value, list):
                    self.model.set_list(action, key, value)
                else:
                    self.model.set_scalar(action, key, value)

        self.model.set_rewards(chapter, self.rewards.values())
        if dlg is not None:
            dlg._log_operation(t("pda.log.wizard",
                                 target=self.title_field.edit.text().strip() or title_token))
        self.created_chapter = chapter
        self.accept()
