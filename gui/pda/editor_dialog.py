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

"""EDITEUR COMPLET du PDA (nouveau module, remplace a terme l'ancienne
creation guidee -- voir core/pda/model.py pour le contrat d'ecriture).

Arbre Chapters > Tasks > Actions a gauche, panneau d'edition contextuel a
droite (chapitre : proprietes + recompenses + repetition + activites ;
tache : proprietes + recompenses ; action : formulaire dynamique par type de
Check, depuis core/pda/schema.py).

Flux d'ecriture : TOUTE modification mute le PdaModel (documents des onglets
ouverts, jamais le disque) des qu'elle est faite (signaux) ou au pire au
CHANGEMENT DE SELECTION / A LA FERMETURE (listes et recompenses, widgets sans
signal par modification). main_window marque ensuite les onglets modifies --
meme flux que l'ancien module."""
import re

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QLabel,
                             QListWidget, QListWidgetItem, QMessageBox,
                             QPushButton, QScrollArea, QSplitter,
                             QStackedWidget, QTreeWidget, QVBoxLayout,
                             QWidget, QTreeWidgetItem)

from core.i18n import t
from core.pda import schema
from core.pda.model import (CHAPTER_REQUIRED_DEFAULTS, PdaModel)
from core.yamllite.model import YamlEntry
from core.pda.schema import (ACTIVATION_FIELDS, ACTION_COMMON_FIELDS,
                             CHAPTER_FIELDS, CHAPTER_STRUCTURE_KEYS,
                             TASK_FIELDS, TASK_STRUCTURE_KEYS, action_fields,
                             check_spec)
from core.pda.validation import (TITLE_LIMITS, validate_action,
                                 validate_model, visible_len)
from gui.msgboxes import ask_yes_no
from gui.pda.form import SpecForm
from gui.pda.widgets import NameListEditor, RewardsEditor, SearchCombo

_K_CHAPTER, _K_TASK, _K_ACTION = "chapter", "task", "action"
_TAG_STRIP_RE = re.compile(r"\[/?.{1,32}?\]")


def _clean_title(text: str) -> str:
    """Retire les balises BBCode Empyrion ([c][ffffff], [b], [-]...) d'un titre
    destine au journal de session -- lisible brut dans le bandeau de reprise.
    Garde l'original si le nettoyage ne laisse rien."""
    cleaned = " ".join(_TAG_STRIP_RE.sub("", text or "").split())
    return cleaned or (text or "")


def _reference_title(model, token):
    """Titre affiche dans l'arbre : texte resolu (colonne de reference puis
    English), repli sur le jeton brut. La valeur YAML peut porter un prefixe
    de format ('mbox;20|pda_KaOsQr') : seul la partie apres '|' est la cle
    CSV -- et un texte brut non localise est affiche tel quel."""
    if not token:
        return t("pda.tree.untitled")
    try:
        from core.pda.model import _TOKEN_RE, split_token_value
        from gui.pda.widgets import _reference_column
        prefix, real_token = split_token_value(token)
        if not _TOKEN_RE.match(real_token):
            return token  # texte brut non localise
        text = model.csv_text(real_token, _reference_column())
        if not text:
            text = model.csv_text(real_token, "English")
    except Exception:
        text = ""
    return text or token


class _NodeData:
    def __init__(self, kind, entry):
        self.kind = kind
        self.entry = entry


class PdaEditorDialog(QDialog):
    def __init__(self, model: PdaModel, suggestions, parent=None, scenario_key: str = ""):
        super().__init__(parent)
        self.model = model
        self.suggestions = suggestions
        self.scenario_key = scenario_key
        self.setWindowTitle(t("pda.editor.title"))
        self.setMinimumSize(1080, 720)
        self._loading = False
        self._current_item = None
        self._internal_reload = False
        # ---- Annuler : snapshots compacts (texte YAML serialise + copies de
        # lignes CSV), coalesces par (entree, champ) pour que les frappes
        # clavier d'un meme champ ne creent pas une entree de pile chacune.
        self._undo_stack: list = []
        self._undo_max = 12
        self._last_undo_tag = None
        self._last_undo_time = 0.0
        # ---- Journal de session (rappel a la reprise, core/pda/history.py)
        self._session_log: list = []            # libelles operationnels, ordre chronologique
        self._touched_fields: dict = {}         # id(entry) -> {"kind","title","keys"}
        self._field_order: list = []            # id(entry), ordre de premier toucher

        root_layout = QVBoxLayout(self)

        # ---- Bandeau de reprise : rappel des dernieres modifications
        resume_html = self._build_resume_banner()
        if resume_html:
            banner = QLabel(resume_html)
            banner.setWordWrap(True)
            banner.setTextFormat(Qt.TextFormat.RichText)
            banner.setStyleSheet("color: gray; font-size: 11px;")
            root_layout.addWidget(banner)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(splitter, 1)

        # ----- gauche : arbre + boutons de structure
        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel(t("pda.tree.header"))
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self.tree, 1)
        btn_row = QHBoxLayout()
        for text, handler, tooltip_key in (
                (t("pda.tree.add_chapter"), self._add_chapter, "pda.tree.add_chapter"),
                (t("pda.tree.add_task"), self._add_task, "pda.tree.add_task"),
                (t("pda.tree.add_action"), self._add_action, "pda.tree.add_action"),
        ):
            btn = QPushButton(text)
            btn.setToolTip(t(tooltip_key))
            btn.clicked.connect(handler)
            btn_row.addWidget(btn)
        left_layout.addLayout(btn_row)
        btn_row2 = QHBoxLayout()
        self.btn_undo = QPushButton(t("pda.editor.undo"))
        self.btn_undo.setToolTip(t("pda.editor.undo.tooltip"))
        self.btn_undo.setEnabled(False)
        self.btn_undo.clicked.connect(self._undo)
        btn_row2.addWidget(self.btn_undo)
        for text, handler, key in (
                (t("pda.tree.duplicate"), self._duplicate, "pda.tree.duplicate"),
                (t("pda.tree.delete"), self._delete, "pda.tree.delete"),
                ("▲", lambda: self._move(-1), "pda.tree.up"),
                ("▼", lambda: self._move(1), "pda.tree.down"),
        ):
            btn = QPushButton(text)
            btn.clicked.connect(handler)
            if key:
                btn.setToolTip(t(key))
            btn_row2.addWidget(btn)
        left_layout.addLayout(btn_row2)
        splitter.addWidget(left)

        # ----- droite : panneaux
        self.stack = QStackedWidget()
        self.welcome = QLabel(t("pda.editor.welcome"))
        self.welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stack.addWidget(self.welcome)
        self.chapter_panel = _ChapterPanel(self.model, self.suggestions, self)
        self.task_panel = _TaskPanel(self.model, self.suggestions, self)
        self.action_panel = _ActionPanel(self.model, self.suggestions, self)
        self.stack.addWidget(self.chapter_panel)
        self.stack.addWidget(self.task_panel)
        self.stack.addWidget(self.action_panel)
        splitter.addWidget(self.stack)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        # ----- bas : assistant + fermeture
        close_row = QHBoxLayout()
        btn_wizard = QPushButton(t("pda.editor.btn_wizard"))
        btn_wizard.setToolTip(t("pda.editor.btn_wizard.tooltip"))
        btn_wizard.clicked.connect(self._open_wizard)
        close_row.addWidget(btn_wizard)
        # A1-A7 (12/09/2026) : passe de validation complete du PDA
        # (core/pda/validation.py), resultats navigables par double-clic.
        btn_verify = QPushButton(t("pda.validation.button"))
        btn_verify.setObjectName("secondaryButton")
        btn_verify.setToolTip(t("pda.validation.button.tooltip"))
        btn_verify.clicked.connect(self._run_validation)
        close_row.addWidget(btn_verify)
        close_row.addStretch()
        btn_close = QPushButton(t("btn.close"))
        btn_close.setObjectName("primaryButton")
        btn_close.clicked.connect(self._on_close)
        close_row.addWidget(btn_close)
        root_layout.addLayout(close_row)

        self._reload_tree()

    def _open_wizard(self):
        """Lance l'assistant de creation ; le chapitre cree est selectionne
        dans l'arbre a la fermeture."""
        from gui.pda.create_wizard import CreateWizard
        self._save_current_panel()
        wizard = CreateWizard(self.model, self.suggestions, self)
        if wizard.exec() == QDialog.DialogCode.Accepted and wizard.created_chapter is not None:
            self._reload_tree()
            self._select_entry(wizard.created_chapter)

    def _run_validation(self):
        """A1-A7 : passe de validation complete (core/pda/validation.py).
        Resultats dans une fenetre ; double-clic = navigation vers l'element
        concerne dans l'arbre."""
        self._save_current_panel()
        issues = validate_model(self.model)
        if not issues:
            QMessageBox.information(self, t("pda.validation.title"),
                                    t("pda.validation.none"))
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(t("pda.validation.title"))
        dlg.resize(780, 520)
        lay = QVBoxLayout(dlg)
        count_label = QLabel(t("pda.validation.n_issues", n=len(issues)))
        count_label.setObjectName("mutedLabel")
        lay.addWidget(count_label)
        lst = QListWidget()
        for issue in issues:
            item = QListWidgetItem(
                f"[{issue.code}] {issue.path} — {issue.message}")
            item.setData(Qt.ItemDataRole.UserRole, issue.entry)
            item.setForeground(QColor("#E8555A" if issue.severity == "error"
                                      else "#F5A623"))
            lst.addItem(item)
        def _goto(item):
            entry = item.data(Qt.ItemDataRole.UserRole)
            if entry is not None:
                dlg.accept()
                self._select_entry(entry)
        lst.itemDoubleClicked.connect(_goto)
        lst.setToolTip(t("pda.validation.hint"))
        lay.addWidget(lst, 1)
        hint = QLabel(t("pda.validation.hint"))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        lay.addWidget(hint)
        row = QHBoxLayout()
        row.addStretch()
        btn_close = QPushButton(t("btn.close"))
        btn_close.clicked.connect(dlg.reject)
        row.addWidget(btn_close)
        lay.addLayout(row)
        dlg.exec()

    # ------------------------------------------------------------------
    # Arbre
    # ------------------------------------------------------------------
    def _reload_tree(self, keep_current: bool = True):
        # L'entree a resselectionner est capturee AVANT tree.clear() : les
        # QTreeWidgetItem C++ sont detruits par le clear, seuls les objets du
        # model restent valides.
        target_entry = None
        if keep_current and self._current_item is not None:
            try:
                data = self._current_item.data(0, Qt.ItemDataRole.UserRole)
                target_entry = data.entry if data is not None else None
            except RuntimeError:
                target_entry = None
        self._loading = True
        self.tree.clear()
        self._current_item = None

        def add_node(kind, entry):
            node = QTreeWidgetItem()
            node.setData(0, Qt.ItemDataRole.UserRole, _NodeData(kind, entry))
            node.setText(0, self._item_text(_NodeData(kind, entry)))
            return node

        for chapter in self.model.chapters():
            ch_node = add_node(_K_CHAPTER, chapter)
            self.tree.addTopLevelItem(ch_node)
            for task in self.model.tasks(chapter):
                task_node = add_node(_K_TASK, task)
                ch_node.addChild(task_node)
                for action in self.model.actions(task):
                    task_node.addChild(add_node(_K_ACTION, action))
                task_node.setExpanded(True)
            ch_node.setExpanded(True)
        self._loading = False
        if target_entry is not None:
            item = self._find_item_by_entry(target_entry)
            if item is not None:
                self._internal_reload = True
                try:
                    self.tree.setCurrentItem(item)
                finally:
                    self._internal_reload = False
                self._current_item = item
                self._load_current_panel()

    def _iter_tree_items(self):
        def walk(item):
            yield item
            for i in range(item.childCount()):
                yield from walk(item.child(i))
        for i in range(self.tree.topLevelItemCount()):
            yield from walk(self.tree.topLevelItem(i))

    def _item_text(self, data) -> str:
        """Texte d'un noeud d'arbre : titre resolu selon le kind (facteur
        commun entre _reload_tree et refresh_tree_item_text)."""
        entry = data.entry
        if data.kind == _K_CHAPTER:
            return _reference_title(self.model, self.model.chapter_title_token(entry))
        if data.kind == _K_TASK:
            return "☑ " + _reference_title(self.model, entry.value or "")
        spec = check_spec(self.model.action_check(entry))
        return f"• [{t(spec.label_key)}] " + \
            _reference_title(self.model, self.model.scalar(entry, "Description"))

    def refresh_tree_item_text(self, entry):
        """Met a jour le TEXTE du noeud d'arbre d'une entree SANS reconstruire
        l'arbre ni recharger le panneau -- une frappe clavier dans un champ de
        titre/description ne doit jamais perdre le focus."""
        item = self._find_item_by_entry(entry)
        if item is None:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data is None:
            return
        item.setText(0, self._item_text(data))

    def _find_item_by_entry(self, entry):
        for item in self._iter_tree_items():
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data is not None and data.entry is entry:
                return item
        return None

    def _current_data(self):
        items = self.tree.selectedItems()
        if not items:
            return None
        return items[0].data(0, Qt.ItemDataRole.UserRole)

    # ------------------------------------------------------------------
    # Annuler : snapshots coalesces + restauration
    # ------------------------------------------------------------------
    def push_undo(self, tag=None):
        """Capture l'etat ACTUEL des documents AVANT une mutation. `tag`
        (id(entree), champ) coalesque les frappes successives d'un meme champ
        (2 s) et les save() repetes d'un meme panneau -- sinon chaque
        caractere tape creerait une entree de pile."""
        import time
        now = time.monotonic()
        if tag is not None and tag == self._last_undo_tag and (now - self._last_undo_time) < 2.0:
            self._last_undo_time = now
            return
        self._undo_stack.append(self.model.snapshot())
        if len(self._undo_stack) > self._undo_max:
            self._undo_stack.pop(0)
        self._last_undo_tag = tag
        self._last_undo_time = now
        self.btn_undo.setEnabled(True)

    def _undo(self):
        if not self._undo_stack:
            return
        cur = self._current_data()
        marker = (cur.kind, self._entry_title_token(cur)) if cur is not None else None
        self.model.restore_snapshot(self._undo_stack.pop())
        self._last_undo_tag = None
        self._session_log.append(t("pda.log.undo"))
        # keep_current=False + protection interne : les widgets du panneau
        # contiennent encore l'etat ANNEULE -- aucun save() ne doit s'exécuter
        # pendant la reconstruction (sinon il reécrirait ce qu'on vient
        # d'annuler), c'est _load_current_panel final qui recharge.
        self._current_item = None
        self._internal_reload = True
        try:
            self._reload_tree(keep_current=False)
            if marker is not None:
                self._select_by_title_token(*marker)
        finally:
            self._internal_reload = False
        self.btn_undo.setEnabled(bool(self._undo_stack))
        self._load_current_panel()

    def _select_by_title_token(self, kind, token):
        for item in self._iter_tree_items():
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data is not None and data.kind == kind and \
                    self._entry_title_token(data) == token:
                self.tree.setCurrentItem(item)
                self._current_item = item
                return

    @staticmethod
    def _entry_title_token(data):
        """Jeton identifiant une entree dans le temps (survit a un
        restore_snapshot : les objets YamlEntry changent, les jetons non)."""
        entry = data.entry
        if data.kind == _K_CHAPTER:
            return entry.value or ""
        return entry.value or ""  # TaskTitle / ActionTitle sont la valeur meme

    # ------------------------------------------------------------------
    # Journal de session (rappel a la reprise -- core/pda/history.py)
    # ------------------------------------------------------------------
    def _build_resume_banner(self) -> str:
        if not self.scenario_key:
            return ""
        try:
            from core.pda.history import read_history
            entries = read_history(self.scenario_key, limit=6)
        except Exception:
            entries = []
        if not entries:
            return ""
        lines = [t("pda.history.banner")]
        for e in entries[:3]:
            lines.append(f"&bull; [{e.get('ts', '')}] {e.get('label', '')}")
        more = len(entries) - 3
        if more > 0:
            lines.append(t("pda.history.more", n=more))
        return "<br>".join(lines)

    def _log_operation(self, label: str):
        self._session_log.append(label)

    def _log_field(self, kind: str, entry, key: str):
        """Champ touche : coalesce par entree (un seul libelle a la fermeture)."""
        if entry is None:
            return
        ident = id(entry)
        if ident not in self._touched_fields:
            prefix = ""
            if kind == _K_ACTION:
                spec = check_spec(self.model.action_check(entry))
                prefix = f"[{t(spec.label_key)}] "
            self._touched_fields[ident] = {
                "kind": kind,
                "title": _clean_title(_reference_title(self.model, entry.value or "")),
                "check": prefix,
                "keys": set(),
            }
            self._field_order.append(ident)
        self._touched_fields[ident]["keys"].add(key)

    def _flush_history(self):
        """Ecrit le journal de session (operations + champs coalesces) dans
        l'historique persistant -- appele une seule fois a la fermeture."""
        labels = list(self._session_log)
        for ident in self._field_order:
            info = self._touched_fields.get(ident)
            if info and info["keys"]:
                labels.append(t("pda.log.modified",
                                target=f"{info['check']}{info['title']}",
                                fields=", ".join(sorted(info["keys"]))))
        if not labels:
            return
        try:
            from core.pda.history import append_history
            append_history(self.scenario_key, labels)
        except Exception:
            pass

    def done(self, result):
        """accept()/reject()/croix passent tous par done() : le journal est
        flush exactement une fois, quelle que soit la maniere de fermer."""
        self._flush_history()
        super().done(result)

    # ------------------------------------------------------------------
    # Selection : sauvegarde du panneau courant puis chargement
    # ------------------------------------------------------------------
    def _on_selection_changed(self):
        if self._loading:
            return
        # Pendant un rechargement interne (declenche par une mutation deja
        # appliquee au model, ex: changement de titre), la sauvegarde du
        # panneau REECRIRAIT les donnees avec des valeurs de widgets
        # obsoletes -- on saute la sauvegarde, le chargement se fait.
        if not self._internal_reload:
            self._save_current_panel()
        self._current_item = self.tree.selectedItems()[0] if self.tree.selectedItems() else None
        self._load_current_panel()

    def _save_current_panel(self):
        panel = self.stack.currentWidget()
        if panel in (self.chapter_panel, self.task_panel, self.action_panel):
            panel.save()

    def _load_current_panel(self):
        data = self._current_data()
        if data is None:
            self.stack.setCurrentWidget(self.welcome)
            return
        if data.kind == _K_CHAPTER:
            self.chapter_panel.load(data.entry)
            self.stack.setCurrentWidget(self.chapter_panel)
        elif data.kind == _K_TASK:
            self.task_panel.load(data.entry)
            self.stack.setCurrentWidget(self.task_panel)
        else:
            self.action_panel.load(data.entry)
            self.stack.setCurrentWidget(self.action_panel)

    # ------------------------------------------------------------------
    # CRUD structure
    # ------------------------------------------------------------------
    def _add_chapter(self):
        self._save_current_panel()
        self.push_undo()
        self._log_operation(t("pda.log.added_chapter"))
        chapter = self.model.create_chapter()
        self._reload_tree()
        self._select_entry(chapter)

    def _add_task(self):
        data = self._current_data()
        if data is None:
            return
        chapter = data.entry if data.kind == _K_CHAPTER else \
            self._parent_entry_of(data, _K_CHAPTER)
        if chapter is None:
            return
        self.push_undo()
        self._log_operation(t("pda.log.added_task",
                              target=_reference_title(self.model, self.model.chapter_title_token(chapter))))
        task = self.model.create_task(chapter)
        self._reload_tree()
        self._select_entry(task)

    def _add_action(self):
        data = self._current_data()
        if data is None:
            return
        task = data.entry if data.kind == _K_TASK else \
            self._parent_entry_of(data, _K_TASK)
        if task is None:
            return
        self.push_undo()
        self._log_operation(t("pda.log.added_action",
                              target=_reference_title(self.model, task.value or "")))
        action = self.model.create_action(task, "WaitAction")
        self._reload_tree()
        self._select_entry(action)

    def _parent_entry_of(self, data, kind):
        """Remonte dans l'arbre jusqu'au premier ancetre du kind demande."""
        item = self._find_item_by_entry(data.entry)
        while item is not None:
            d = item.data(0, Qt.ItemDataRole.UserRole)
            if d is not None and d.kind == kind:
                return d.entry
            item = item.parent()
        return None

    def _duplicate(self):
        data = self._current_data()
        if data is None or data.kind != _K_CHAPTER:
            return
        self.push_undo()
        self._log_operation(t("pda.log.duplicated",
                              target=_reference_title(self.model, self.model.chapter_title_token(data.entry))))
        clone = self.model.duplicate_chapter(data.entry)
        if clone is not None:
            self._reload_tree()
            self._select_entry(clone)

    def _delete(self):
        data = self._current_data()
        if data is None:
            return
        labels = {_K_CHAPTER: t("pda.tree.confirm_delete_chapter"),
                  _K_TASK: t("pda.tree.confirm_delete_task"),
                  _K_ACTION: t("pda.tree.confirm_delete_action")}
        if not ask_yes_no(self, t("pda.editor.title"), labels[data.kind]):
            return
        self.push_undo()
        self._log_operation(t("pda.log.deleted",
                              target=_reference_title(self.model, self._entry_title_token(data))))
        self.model.delete_entry(data.entry)
        self._current_item = None
        self._reload_tree()
        self.stack.setCurrentWidget(self.welcome)

    def _move(self, delta):
        data = self._current_data()
        if data is None:
            return
        self.push_undo()
        if self.model.move_entry(data.entry, delta):
            self._log_operation(t("pda.log.moved",
                                  target=_reference_title(self.model, self._entry_title_token(data))))
            self._reload_tree()
            self._select_entry(data.entry)
        else:
            self._undo_stack.pop()  # rien deplace : snapshot inutile
            self.btn_undo.setEnabled(bool(self._undo_stack))

    def _select_entry(self, entry):
        item = self._find_item_by_entry(entry)
        if item is None:
            return
        self.tree.setCurrentItem(item)
        self._current_item = item

    # ------------------------------------------------------------------
    def _on_close(self):
        self._save_current_panel()
        self.accept()


class _BasePanel(QScrollArea):
    """Panneau de droite : scroll + sections. save() applique les widgets sans
    signal (listes, recompenses) sur le model -- UNIQUEMENT si la valeur a
    reellement change (pas d'ecriture parasite, journal fidele).

    Chaque panneau possede un champ TITRE en tete : ChapterTitle/TaskTitle/
    ActionTitle sont la VALEUR de la ligne ('- ChapterTitle: pda_x'), pas des
    champs enfants -- ils sont donc edites via set_own_value, jamais par le
    formulaire SpecForm (retour utilisateur du 31/08/2026 : le titre n'etait
    jamais proposé)."""

    title_key = "Title"          # nom de cle pour le journal (ChapterTitle...)
    title_limit = None           # A1 : limite HUD de caracteres (26/24)

    def __init__(self, model, suggestions, parent=None):
        super().__init__(parent)
        self.model = model
        self.suggestions = suggestions
        self.entry = None
        self.kind = ""
        self._loading = False
        self.setWidgetResizable(True)
        self._container = QWidget()
        self.setWidget(self._container)

    def _build_title_row(self, layout, label_key: str):
        layout.addWidget(QLabel(f"<b>{t(label_key)}</b>"))
        from gui.pda.widgets import TokenTextField
        self.title_field = TokenTextField(self.model)
        self.title_field.edit.textEdited.connect(self._on_title_edited)
        layout.addWidget(self.title_field)
        # A1 (12/09/2026) : compteur de caracteres VISIBLES (BBCode retires)
        # contre la limite HUD du jeu (TaskTitle 26, ActionTitle 24).
        self.title_counter = QLabel("")
        self.title_counter.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.title_counter)
        self._update_title_counter()

    def _update_title_counter(self):
        if self.title_limit is None:
            return
        n = visible_len(self.title_field.edit.text())
        over = n > self.title_limit
        self.title_counter.setText(t("pda.val.counter", n=n, max=self.title_limit))
        self.title_counter.setStyleSheet(
            f"color: {'#E8555A' if over else 'gray'}; font-size: 11px;"
            + (" font-weight: bold;" if over else ""))
        self.title_counter.setToolTip(t("pda.val.counter.tip"))

    def _load_title(self, entry):
        self._loading = True
        self.title_field.set_token(entry.value or "")
        self._loading = False
        self._update_title_counter()

    def _on_title_edited(self):
        if self._loading or self.entry is None:
            return
        dlg = self._dlg()
        if dlg is not None:
            dlg.push_undo((id(self.entry), "__title__"))
            dlg._log_field(self.kind, self.entry, self.title_key)
        new_value = self.title_field.value()
        if new_value:
            self.entry.set_own_value(new_value)
        # Rafraichit le TEXTE de l'item d'arbre sans reconstruire ni recharger
        # le panneau : la frappe clavier ne doit jamais perdre le focus.
        if dlg is not None:
            dlg.refresh_tree_item_text(self.entry)
        self._update_title_counter()

    def _build_advanced(self, layout):
        self.advanced_title = QLabel(f"<b>{t('pda.advanced.readonly')}</b>")
        self.advanced_title.setToolTip(t("pda.advanced.readonly.tooltip"))
        self.advanced_label = QLabel("")
        self.advanced_label.setWordWrap(True)
        self.advanced_label.setTextFormat(Qt.TextFormat.RichText)
        self.advanced_label.setStyleSheet("color: gray; font-size: 11px;")
        self.advanced_title.hide()
        self.advanced_label.hide()
        layout.addWidget(self.advanced_title)
        layout.addWidget(self.advanced_label)

    def _update_advanced(self, entry, covered_keys):
        """Affiche TOUTE cle presente du fichier non couverte par le
        formulaire (structures dedies comprises) -- rien n'est jamais
        invisible sans le savoir (retour utilisateur du 31/08/2026)."""
        lines = []
        for child in entry.children:
            if not isinstance(child, YamlEntry) or not child.key:
                continue
            if child.key in covered_keys:
                continue
            if child.children:
                n = sum(1 for c in child.children if isinstance(c, YamlEntry))
                lines.append(f"&bull; {child.key} ({n} {t('pda.advanced.subentries')})")
            else:
                v = (child.value or "")
                if len(v) > 60:
                    v = v[:57] + "..."
                lines.append(f"&bull; {child.key} = {v}")
        self.advanced_label.setText("<br>".join(lines))
        visible = bool(lines)
        self.advanced_title.setVisible(visible)
        self.advanced_label.setVisible(visible)

    def load(self, entry):
        self.entry = entry

    def save(self):
        pass

    def _suggestions_provider(self):
        return lambda pool: self.suggestions.pool(pool)

    def _dlg(self):
        window = self.window()
        return window if isinstance(window, PdaEditorDialog) else None

    def _track(self, key):
        """Snapshot + journal AVANT une mutation de champ (frappe clavier)."""
        dlg = self._dlg()
        if dlg is not None and self.entry is not None:
            dlg.push_undo((id(self.entry), key))
            dlg._log_field(self.kind, self.entry, key)
        return dlg


class _ChapterPanel(_BasePanel):
    title_key = "ChapterTitle"

    def __init__(self, model, suggestions, parent=None):
        super().__init__(model, suggestions, parent)
        self.kind = _K_CHAPTER
        self._layout = QVBoxLayout(self._container)
        self._build_title_row(self._layout, "pda.chapter.title")
        self.form = SpecForm(self.model, self._suggestions_provider())
        self.form.changed.connect(self._on_field_changed)
        self._layout.addWidget(QLabel(f"<b>{t('pda.chapter.properties')}</b>"))
        self._layout.addWidget(self.form)

        self._layout.addWidget(QLabel(f"<b>{t('pda.chapter.rewards')}</b>"))
        self.rewards = RewardsEditor()
        self._layout.addWidget(self.rewards)

        self._layout.addWidget(QLabel(f"<b>{t('pda.chapter.repeat')}</b>"))
        self.repeat_form = SpecForm(self.model, lambda pool: [])
        self.repeat_form.changed.connect(self._on_repeat_changed)
        self._layout.addWidget(self.repeat_form)

        self._layout.addWidget(QLabel(f"<b>{t('pda.chapter.rewards_chain')}</b>"))
        self.rewarded_chapters = NameListEditor(
            self.suggestions.pool(schema.POOL_CHAPTER) if suggestions else [])
        self._layout.addWidget(self.rewarded_chapters)

        act_row = QHBoxLayout()
        self.act_combo = QComboBox()
        self.act_combo.currentIndexChanged.connect(self._on_activation_selected)
        act_row.addWidget(QLabel(t("pda.activation.label")), 1)
        btn_add_act = QPushButton(t("pda.activation.add"))
        btn_add_act.clicked.connect(self._add_activation)
        act_row.addWidget(btn_add_act)
        btn_del_act = QPushButton(t("pda.activation.remove"))
        btn_del_act.clicked.connect(self._remove_activation)
        act_row.addWidget(btn_del_act)
        self._layout.addLayout(act_row)
        self.act_form = SpecForm(self.model, self._suggestions_provider())
        self.act_form.changed.connect(self._on_activation_changed)
        self._layout.addWidget(self.act_form)
        self._build_advanced(self._layout)
        self._layout.addStretch()
        self._activation = None

    # ----- chargement
    def load(self, entry):
        self.entry = entry
        self._loading = True
        self._load_title(entry)
        values = {}
        for spec in CHAPTER_FIELDS:
            # les LISTES (Playfields, VisibleOnStart...) passent par get_list :
            # un scalar() donnerait '' -> widget vide -> save() effacerait la
            # valeur du fichier a chaque ouverture (bug detecte par le test
            # d'idempotence save/save).
            if spec.kind in (schema.KIND_NAMES, schema.KIND_TYPES):
                values[spec.key] = self.model.get_list(entry, spec.key)
            else:
                values[spec.key] = self.model.scalar(entry, spec.key)
        self.form.build(CHAPTER_FIELDS, values)
        self.rewards.set_values(self.model.rewards(entry))
        repeat = self.model.repeat_fields(entry)
        self.repeat_form.build(schema.REPEAT_FIELDS,
                               {s.key: repeat.get(s.key, "") for s in schema.REPEAT_FIELDS})
        self.rewarded_chapters.set_values(self.model.get_list(entry, "RewardedChapters"))
        self._activation = None
        self.act_form.build([], {})
        self._refresh_act_combo()
        self._loading = False
        covered = {spec.key for spec in CHAPTER_FIELDS} | set(CHAPTER_STRUCTURE_KEYS) | {"ChapterTitle"}
        self._update_advanced(entry, covered)

    def _refresh_act_combo(self):
        self.act_combo.blockSignals(True)
        self.act_combo.clear()
        activations = self.model.activations(self.entry) if self.entry else []
        for i, act in enumerate(activations):
            label = act.key or "?"
            value = act.value or ""
            names = self.model.activation_names(act)
            summary = value or (", ".join(names[:2]) if names else "")
            self.act_combo.addItem(f"#{i + 1} [{label}] {summary}"[:60])
        self.act_combo.setCurrentIndex(-1 if not activations else 0)
        self.act_combo.blockSignals(False)
        self._load_activation(0 if activations else None)

    def _load_activation(self, index):
        self._loading = True
        activations = self.model.activations(self.entry) if self.entry else []
        if index is None or index < 0 or index >= len(activations):
            self._activation = None
        else:
            self._activation = activations[index]
        if self._activation is None:
            self.act_form.build([], {})
        else:
            values = {}
            for spec in ACTIVATION_FIELDS:
                if spec.key == "Names":
                    values[spec.key] = self.model.activation_names(self._activation)
                else:
                    values[spec.key] = self.model.activation_field(self._activation, spec.key)
            self.act_form.build(ACTIVATION_FIELDS, values)
        self._loading = False

    # ----- application
    def _on_field_changed(self, key, value):
        if self._loading or self.entry is None:
            return
        self._track(key)
        if isinstance(value, list):
            self.model.set_list(self.entry, key, value)
        else:
            self.model.set_scalar(self.entry, key, value, CHAPTER_REQUIRED_DEFAULTS)
        if key == "Description":
            self._notify_title_change()

    def _on_repeat_changed(self, key, value):
        if self._loading or self.entry is None:
            return
        self._track(f"RepeatConditions.{key}")
        self.model.set_repeat_field(self.entry, key, value)

    def _on_activation_changed(self, key, value):
        if self._loading or self._activation is None:
            return
        self._track(f"ChapterActivation.{key}")
        if key == "Check":
            value = (value or "").strip()
            self.model.set_activation_primary_key(self._activation, "Check" if value else "Names")
            if value:
                self.model.set_activation_field(self._activation, "Check", value)
            return
        if isinstance(value, list):
            self.model.set_activation_names(self._activation, value)
        else:
            self.model.set_activation_field(self._activation, key, value)
        self._refresh_act_combo()

    def _add_activation(self):
        if self.entry is None:
            return
        dlg = self._dlg()
        if dlg is not None:
            dlg.push_undo()
            dlg._log_operation(t("pda.log.added_activation"))
        self.model.create_activation(self.entry)
        self._refresh_act_combo()
        self._load_activation(len(self.model.activations(self.entry)) - 1)

    def _remove_activation(self):
        if self._activation is None:
            return
        dlg = self._dlg()
        if dlg is not None:
            dlg.push_undo()
            dlg._log_operation(t("pda.log.removed_activation"))
        self.model.delete_entry(self._activation)
        self._activation = None
        self._refresh_act_combo()

    def _on_activation_selected(self, index):
        if self._loading:
            return
        self._load_activation(index)

    def _notify_title_change(self):
        # Rafraichit seulement le TEXTE du noeud d'arbre : un reload complet
        # pendant la frappe perdreait le focus du champ en cours d'edition.
        dlg = self._dlg()
        if dlg is not None:
            dlg.refresh_tree_item_text(self.entry)

    def save(self):
        """Applique les widgets sans signal (listes, recompenses) UNIQUEMENT
        si la valeur differe du model -- pas d'ecriture parasite, journal
        fidele. Les autres champs sont deja appliques au signal."""
        if self.entry is None:
            return
        dlg = self._dlg()
        if dlg is not None:
            dlg.push_undo((id(self.entry), "__save__"))
        for key, value in self.form.collect_values().items():
            old = self.model.get_list(self.entry, key) if isinstance(value, list) \
                else self.model.scalar(self.entry, key)
            if old == value:
                continue
            if isinstance(value, list):
                self.model.set_list(self.entry, key, value)
            else:
                self.model.set_scalar(self.entry, key, value, CHAPTER_REQUIRED_DEFAULTS)
            if dlg is not None:
                dlg._log_field(self.kind, self.entry, key)
        old_rewards = self.model.rewards(self.entry)
        new_rewards = self.rewards.values()
        if old_rewards != new_rewards:
            self.model.set_rewards(self.entry, new_rewards)
            if dlg is not None:
                dlg._log_field(self.kind, self.entry, "Rewards")
        old_chain = self.model.get_list(self.entry, "RewardedChapters")
        new_chain = self.rewarded_chapters.values()
        if old_chain != new_chain:
            self.model.set_list(self.entry, "RewardedChapters", new_chain)
            if dlg is not None:
                dlg._log_field(self.kind, self.entry, "RewardedChapters")
        # activation en cours : listes sans signal par modification
        if self._activation is not None:
            for key, value in self.act_form.collect_values().items():
                if key == "Check":
                    continue  # applique au signal (bascule de premiere cle)
                old = self.model.activation_names(self._activation) if isinstance(value, list) \
                    else self.model.activation_field(self._activation, key)
                if old == value:
                    continue
                if isinstance(value, list):
                    self.model.set_activation_names(self._activation, value)
                else:
                    self.model.set_activation_field(self._activation, key, value)
                if dlg is not None:
                    dlg._log_field(self.kind, self._activation, f"ChapterActivation.{key}")


class _TaskPanel(_BasePanel):
    title_key = "TaskTitle"
    title_limit = TITLE_LIMITS["TaskTitle"]     # 26 : limite HUD du jeu

    def __init__(self, model, suggestions, parent=None):
        super().__init__(model, suggestions, parent)
        self.kind = _K_TASK
        self._layout = QVBoxLayout(self._container)
        self._build_title_row(self._layout, "pda.task.title")
        self.form = SpecForm(self.model, self._suggestions_provider())
        self.form.changed.connect(self._on_field_changed)
        self._layout.addWidget(QLabel(f"<b>{t('pda.task.properties')}</b>"))
        self._layout.addWidget(self.form)
        self._layout.addWidget(QLabel(f"<b>{t('pda.chapter.rewards')}</b>"))
        self.rewards = RewardsEditor()
        self._layout.addWidget(self.rewards)
        self._build_advanced(self._layout)
        self._layout.addStretch()

    def load(self, entry):
        self.entry = entry
        self._loading = True
        self._load_title(entry)
        values = {}
        for spec in TASK_FIELDS:
            if spec.kind in (schema.KIND_NAMES, schema.KIND_TYPES):
                values[spec.key] = self.model.get_list(entry, spec.key)
            else:
                values[spec.key] = self.model.scalar(entry, spec.key)
        self.form.build(TASK_FIELDS, values)
        self.rewards.set_values(self.model.rewards(entry))
        self._loading = False
        covered = {spec.key for spec in TASK_FIELDS} | set(TASK_STRUCTURE_KEYS) | {"TaskTitle"}
        self._update_advanced(entry, covered)

    def _on_field_changed(self, key, value):
        if self._loading or self.entry is None:
            return
        self._track(key)
        if isinstance(value, list):
            self.model.set_list(self.entry, key, value)
        else:
            self.model.set_scalar(self.entry, key, value)

    def save(self):
        if self.entry is None:
            return
        dlg = self._dlg()
        if dlg is not None:
            dlg.push_undo((id(self.entry), "__save__"))
        for key, value in self.form.collect_values().items():
            old = self.model.get_list(self.entry, key) if isinstance(value, list) \
                else self.model.scalar(self.entry, key)
            if old == value:
                continue
            if isinstance(value, list):
                self.model.set_list(self.entry, key, value)
            else:
                self.model.set_scalar(self.entry, key, value)
            if dlg is not None:
                dlg._log_field(self.kind, self.entry, key)
        old_rewards = self.model.rewards(self.entry)
        new_rewards = self.rewards.values()
        if old_rewards != new_rewards:
            self.model.set_rewards(self.entry, new_rewards)
            if dlg is not None:
                dlg._log_field(self.kind, self.entry, "Rewards")


class _ActionPanel(_BasePanel):
    title_key = "ActionTitle"
    title_limit = TITLE_LIMITS["ActionTitle"]   # 24 : limite HUD du jeu

    def __init__(self, model, suggestions, parent=None):
        super().__init__(model, suggestions, parent)
        self.kind = _K_ACTION
        self._layout = QVBoxLayout(self._container)
        self._build_title_row(self._layout, "pda.action.title")
        check_row = QHBoxLayout()
        check_row.addWidget(QLabel(t("pda.action.check")))
        self.check_combo = SearchCombo([""] + list(_all_checks()))
        self.check_combo.currentTextChanged.connect(self._on_check_changed)
        check_row.addWidget(self.check_combo, 1)
        self._layout.addLayout(check_row)
        self.check_desc = QLabel("")
        self.check_desc.setWordWrap(True)
        self._layout.addWidget(self.check_desc)
        self.form = SpecForm(self.model, self._suggestions_provider())
        self.form.changed.connect(self._on_field_changed)
        self._layout.addWidget(self.form)
        # A2/A7 (12/09/2026) : bandeau LIVE des problemes de l'action en
        # cours (CompletedMessage manquant, NAMES/TYPES requis par le Check,
        # champs non supportes...). Regles : core/pda/validation.py.
        self.issues_label = QLabel("")
        self.issues_label.setWordWrap(True)
        self.issues_label.setTextFormat(Qt.TextFormat.RichText)
        self.issues_label.setStyleSheet("color: #E8555A; font-size: 11px;")
        self.issues_label.hide()
        self._layout.addWidget(self.issues_label)
        self._build_advanced(self._layout)
        self._layout.addStretch()

    def load(self, entry):
        self.entry = entry
        self._loading = True
        self._load_title(entry)
        check = self.model.action_check(entry)
        self.check_combo.setCurrentText(check)
        self._build_fields(check)
        self._loading = False
        self._refresh_issues()

    def _refresh_issues(self):
        """A2/A7 en live : regles du guide appliquees a CETTE action
        (core/pda/validation.validate_action), affichees dans le bandeau."""
        dlg = self._dlg()
        if dlg is None or self.entry is None:
            self.issues_label.hide()
            return
        data = dlg._current_data()
        chapter = dlg._parent_entry_of(data, _K_CHAPTER) if data else None
        task = dlg._parent_entry_of(data, _K_TASK) if data else None
        if chapter is None or task is None:
            self.issues_label.hide()
            return
        issues = validate_action(self.model, chapter, task, self.entry)
        if not issues:
            self.issues_label.hide()
            return
        self.issues_label.setText(
            "<br>".join(f"&bull; {i.message}" for i in issues))
        self.issues_label.setVisible(True)

    def _build_fields(self, check):
        fields = action_fields(check)
        values = {}
        for spec in fields:
            if spec.kind in (schema.KIND_NAMES, schema.KIND_TYPES):
                values[spec.key] = self.model.get_list(self.entry, spec.key)
            else:
                values[spec.key] = self.model.scalar(self.entry, spec.key)
        self.form.build(fields, values)
        self.check_desc.setText(t(check_spec(check).desc_key))
        # Check est affiche par le combo dedie, pas par le SpecForm : il fait
        # partie des couverts (sinon la section Avance afficherait
        # 'Check = ...' sur CHAQUE action).
        covered = {spec.key for spec in fields} | {"ActionTitle", "Check"}
        self._update_advanced(self.entry, covered)

    def _on_check_changed(self, text):
        if self._loading or self.entry is None:
            return
        text = text.strip()
        self._track("Check")
        node = self.model._child(self.entry, "Check")
        if text == "":
            if node is not None:
                self.entry.children.remove(node)
        else:
            self.model.set_scalar(self.entry, "Check", text)
        self._build_fields(text)
        self._refresh_issues()

    def _on_field_changed(self, key, value):
        if self._loading or self.entry is None:
            return
        self._track(key)
        if isinstance(value, list):
            self.model.set_list(self.entry, key, value)
        else:
            self.model.set_scalar(self.entry, key, value)
        if key == "Description":
            self._notify_title_change()
        self._refresh_issues()

    def _notify_title_change(self):
        # Meme discipline que le panneau chapitre : jamais de reload complet
        # pendant une frappe clavier.
        dlg = self._dlg()
        if dlg is not None:
            dlg.refresh_tree_item_text(self.entry)

    def save(self):
        if self.entry is None:
            return
        dlg = self._dlg()
        if dlg is not None:
            dlg.push_undo((id(self.entry), "__save__"))
        for key, value in self.form.collect_values().items():
            if not isinstance(value, list):
                continue
            if self.model.get_list(self.entry, key) == value:
                continue
            self.model.set_list(self.entry, key, value)
            if dlg is not None:
                dlg._log_field(self.kind, self.entry, key)


def _all_checks():
    """Checks tries par libelle pour le combo ('' = sans Check, en tete)."""
    entries = [(t(spec.label_key), check) for check, spec in schema.CHECKS.items()]
    entries.sort(key=lambda pair: pair[0].lower())
    return [check for _label, check in entries]
