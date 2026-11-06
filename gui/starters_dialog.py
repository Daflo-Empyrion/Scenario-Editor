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

"""Starters : liste des planetes de la galaxie, case a cocher = « depart
propose au menu Nouvelle partie », edition du kit (4 niveaux + Food/Health),
fiche de depart inseree devant la Description du playfield.

Un depart tient a deux fichiers (voir core/starters.py) : la ligne de
`Sectors.yaml` et le bloc `POIs > FixedPlayerStart` du `playfield_static.yaml`.
Le kit d'une planete sans bloc reprend celui d'Akua (comme le corpus).

Rappel affiche : le jeu charge la COPIE du Sectors.yaml faite dans la
sauvegarde — ces changements ne valent que pour une NOUVELLE partie.
"""
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QLabel,
                             QLineEdit, QPlainTextEdit, QPushButton,
                             QTextBrowser, QTreeWidget, QTreeWidgetItem,
                             QVBoxLayout, QWidget)

from core import settings
from core.i18n import t
from core.starters import (AKUA_ITEMS, AKUA_STATUS, MARKER, StartKit,
                           card_preview, check_kit, check_playfield,
                           clear_starts, ensure_final_eol, find_planets,
                           load_validated, mark_validated, prepend_start_card,
                           preview_markers, read_kit, render_kit, set_starts,
                           static_path, write_kit)
from core.playfield_reintegrate import sectors_yaml
from gui.busy import run_long
from gui.ewa_async import async_call
from gui.module_info import add_info_button
from gui.msgboxes import ask_yes_no, info
from gui.window_geometry import track

_COLUMNS = ("starters.col_start", "starters.col_system", "starters.col_sector",
            "starters.col_name", "starters.col_type", "starters.col_origin",
            "starters.col_kit", "starters.col_card")


def _levels(text: str, default) -> tuple:
    """Exactement 4 niveaux : une ligne non vide par niveau."""
    values = [line.strip() for line in text.splitlines() if line.strip()]
    values = values[:4]
    return tuple(values + [default[i] for i in range(len(values), 4)])


class StartersDialog(QDialog):
    """Cocher = ce playfield est un depart. Le kit s'edite pour la planete
    selectionnee ; il n'est ecrit que s'il differe de celui du disque."""

    def __init__(self, root, parent=None, main_window=None):
        super().__init__(parent)
        self.setWindowTitle(t("starters.title"))
        self.setMinimumSize(900, 700)
        self._root = Path(root)
        self._main = main_window
        self._rows = []
        self._by_key = {}
        self._drafts = {}
        self._current = None
        self.applied = 0

        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText(t("starters.filter_tip"))
        layout.addWidget(self.search)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([t(key) for key in _COLUMNS])
        self.tree.setColumnWidth(0, 70)
        self.tree.setColumnWidth(1, 130)
        self.tree.setColumnWidth(2, 110)
        self.tree.setColumnWidth(3, 200)
        layout.addWidget(self.tree, 1)

        layout.addWidget(QLabel(t("starters.levels_tip")))
        kit_row = QHBoxLayout()
        self.items_edit = QPlainTextEdit()
        self.items_edit.setFixedHeight(96)
        self.status_edit = QPlainTextEdit()
        self.status_edit.setFixedHeight(96)
        kit_row.addWidget(self._labelled("starters.items_label", self.items_edit))
        kit_row.addWidget(self._labelled("starters.status_label", self.status_edit))
        layout.addLayout(kit_row)
        self.spawn_label = QLabel("")
        layout.addWidget(self.spawn_label)

        self.card_check = QCheckBox(t("starters.card_check"))
        self.card_check.setChecked(True)
        layout.addWidget(self.card_check)

        layout.addWidget(QLabel(t("starters.card_view")))
        self.card_view = QTextBrowser()
        self.card_view.setFixedHeight(150)
        layout.addWidget(self.card_view)

        layout.addWidget(QLabel(t("starters.preview")))
        self.preview_box = QPlainTextEdit()
        self.preview_box.setReadOnly(True)
        self.preview_box.setFixedHeight(140)
        layout.addWidget(self.preview_box)

        buttons = QHBoxLayout()
        self.btn_preview = QPushButton(t("starters.preview_btn"))
        self.btn_apply = QPushButton(t("starters.apply"))
        self.btn_apply.setObjectName("primaryButton")
        self.btn_apply.setEnabled(False)
        self.btn_validated = QPushButton(t("starters.validated_btn"))
        self.btn_validated.setToolTip(t("starters.validated_btn.tip"))
        self.btn_validated.setEnabled(False)
        btn_close = QPushButton(t("starters.close"))
        buttons.addWidget(self.btn_preview)
        buttons.addWidget(self.btn_apply)
        buttons.addWidget(self.btn_validated)
        add_info_button(buttons, "starters.info_html")
        buttons.addStretch(1)
        buttons.addWidget(btn_close)
        layout.addLayout(buttons)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.search.textChanged.connect(self._filter)
        self.tree.itemChanged.connect(self._toggle)
        self.tree.currentItemChanged.connect(self._selection_changed)
        self.items_edit.textChanged.connect(self._stash)
        self.status_edit.textChanged.connect(self._stash)
        self.card_check.toggled.connect(self._invalidated)
        self.card_check.toggled.connect(self._refresh_card)
        self.btn_preview.clicked.connect(self._preview)
        self.btn_apply.clicked.connect(self._apply)
        self.btn_validated.clicked.connect(self._mark_validated)
        btn_close.clicked.connect(self.reject)

        self._load()
        track(self, "starters", (940, 740))

    def _labelled(self, key: str, widget):
        box = QWidget()
        column = QVBoxLayout(box)
        column.setContentsMargins(0, 0, 0, 0)
        column.addWidget(QLabel(t(key)))
        column.addWidget(widget)
        return box

    # ------------------------------------------------------------- lecture

    def _load(self) -> None:
        self._rows = run_long(self, lambda: find_planets(self._root))
        self._by_key = {row.key: row for row in self._rows}
        self._validated, cache_exists = run_long(
            self, lambda: load_validated(self._root))
        if not cache_exists:
            self._seed_validated()
        self.tree.blockSignals(True)
        self.tree.clear()
        for row in self._rows:
            item = QTreeWidgetItem([
                row.marker, row.system,
                f"[{row.sector[0]}, {row.sector[1]}, {row.sector[2]}]",
                row.name, row.type_name,
                self._status_text(row),
                t("starters.yes") if row.has_kit else t("starters.no"),
                t("starters.yes") if row.has_card else t("starters.no")])
            item.setFlags(Qt.ItemFlag.ItemIsUserCheckable
                          | Qt.ItemFlag.ItemIsEnabled
                          | Qt.ItemFlag.ItemIsSelectable)
            item.setCheckState(0, Qt.CheckState.Checked if row.is_start
                               else Qt.CheckState.Unchecked)
            item.setData(0, Qt.ItemDataRole.UserRole, row.key)
            self.tree.addTopLevelItem(item)
        self.tree.blockSignals(False)
        self._invalidated()
        if not self._rows:
            self.status.setText(t("starters.none"))
        self._filter(self.search.text())

    def _status_text(self, row) -> str:
        if not row.is_start:
            return ""
        return (t("starters.validated") if row.type_name in self._validated
                else t("starters.untested"))

    def _seed_validated(self) -> None:
        """Premiere ouverture du module sur ce scenario : les departs DEJA
        marques sont presumes valides (c'est l'etat que l'utilisateur a).
        Refus -> cache vide, tout depart sera « a tester »."""
        marked = [row.type_name for row in self._rows if row.is_start]
        if not marked:
            return
        if ask_yes_no(self, t("starters.title"), t("starters.seed")):
            mark_validated(self._root, marked)
            self._validated, _ = load_validated(self._root)

    def _filter(self, text: str) -> None:
        needle = text.strip().casefold()
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            haystack = " ".join(item.text(column) for column in range(1, 5))
            item.setHidden(bool(needle) and needle not in haystack.casefold())

    def _selection_changed(self, current, _previous) -> None:
        self._stash()
        if current is None:
            self._current = None
            self.btn_validated.setEnabled(False)
            return
        row = self._by_key.get(current.data(0, Qt.ItemDataRole.UserRole))
        if row is None:
            self._current = None
            self.btn_validated.setEnabled(False)
            return
        self._current = row.type_name
        self.btn_validated.setEnabled(row.is_start)
        kit = self._drafts.get(row.type_name) \
            or run_long(self, lambda: read_kit(self._root, row.type_name))
        self.items_edit.blockSignals(True)
        self.status_edit.blockSignals(True)
        self.items_edit.setPlainText("\n".join(kit.items))
        self.status_edit.setPlainText("\n".join(kit.status))
        self.items_edit.blockSignals(False)
        self.status_edit.blockSignals(False)
        self.spawn_label.setText(t("starters.spawn_label", spawn=kit.spawn,
                                   pos=kit.pos))
        self.card_check.setChecked(not row.has_card)
        self._refresh_card()

    def _current_row(self):
        item = self.tree.currentItem()
        if item is None:
            return None
        return self._by_key.get(item.data(0, Qt.ItemDataRole.UserRole))

    def _refresh_card(self, *_args) -> None:
        """Canevas : la carte telle que le jeu la lira (BBCode converti)."""
        row = self._current_row()
        if row is None:
            self.card_view.clear()
            return
        from core.block_info_card import description_html
        text = run_long(self, lambda: card_preview(
            self._root, row, self.card_check.isChecked()))
        self.card_view.setHtml(description_html(text))

    def _mark_validated(self) -> None:
        """L'utilisateur a joue un depart sans crash : il l'enregistre pour
        que le module et le bilan cessent de le signaler."""
        row = self._current_row()
        if row is None or not row.is_start:
            return
        mark_validated(self._root, [row.type_name])
        self._validated, _ = load_validated(self._root)
        self._load()
        self.status.setText(t("starters.validated_done", name=row.name))

    def _stash(self) -> None:
        if self._current is None:
            return
        self._drafts[self._current] = StartKit(
            status=_levels(self.status_edit.toPlainText(), AKUA_STATUS),
            items=_levels(self.items_edit.toPlainText(), AKUA_ITEMS))
        self._invalidated()

    def _toggle(self, item, _column) -> None:
        item.setText(0, MARKER if item.checkState(0) == Qt.CheckState.Checked
                     else "")
        self._invalidated()

    def _invalidated(self, *_args) -> None:
        self.btn_apply.setEnabled(False)
        self.preview_text = ""

    # --------------------------------------------------------------- plan

    def _changes(self):
        """(departs a activer, a desactiver, kits a ecrire, cartes a ecrire)."""
        enabled, disabled = [], []
        checked_rows = {}      # type_name -> row (departs RESTES coches inclus)
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            row = self._by_key.get(item.data(0, Qt.ItemDataRole.UserRole))
            if row is None:
                continue
            checked = item.checkState(0) == Qt.CheckState.Checked
            if checked:
                checked_rows.setdefault(row.type_name, row)
            if checked and not row.is_start:
                enabled.append(row)
            elif not checked and row.is_start:
                disabled.append(row)
        kits = {}
        for type_name, row in checked_rows.items():
            disk = run_long(self, lambda tn=type_name: read_kit(self._root, tn))
            draft = self._drafts.get(type_name)
            if not row.has_kit:
                # activer un depart SANS kit = joueur sans items : ecrire
                # celui affiche (repli Akua, ou la variante editee)
                kits[type_name] = draft or disk
            elif draft is not None and draft != disk:
                kits[type_name] = draft
        cards = [row for row in enabled
                 if self.card_check.isChecked() and not row.has_card]
        return enabled, disabled, kits, cards

    def _preview(self) -> None:
        enabled, disabled, kits, cards = self._changes()
        lines = []
        for label, picks, marker in (("activer", enabled, MARKER),
                                     ("desactiver", disabled, "")):
            for name, before, after in run_long(
                    self, lambda p=picks, m=marker:
                    preview_markers(self._root, p, m)):
                lines.append(f"# {label} {name}")
                lines.append(f"- {before}")
                lines.append(f"+ {after}")
        for type_name, kit in kits.items():
            lines.append(f"# kit {type_name}")
            lines.extend(render_kit(kit).splitlines())
        for row in cards:
            lines.append(f"# fiche {row.name} -> {row.type_name}")
        text = "\n".join(lines)
        if not text:
            self.status.setText(t("starters.none_selected"))
            return
        self.preview_text = text
        self.preview_box.setPlainText(text)
        self.btn_apply.setEnabled(True)
        warnings = self._kit_warnings(kits)
        experimental = [row.name for row in enabled if row.type_name
                        not in self._validated]
        message = (t("starters.plan_ready", n=len(enabled) + len(disabled),
                     k=len(kits), c=len(cards))
                   + "\n" + t("starters.new_game"))
        if experimental:
            message += "\n" + t("starters.untested_warn",
                                names=", ".join(experimental[:4]))
        if warnings:
            message += "\n" + t("starters.kit_warn", n=len(warnings))
            message += "\n" + "\n".join(warnings[:6])
        self.status.setText(message)

    def _kit_warnings(self, kits) -> list:
        """Un item inconnu est ignore en silence par le jeu : on le dit avant
        d'ecrire (le controle ne bloque pas)."""
        if not kits:
            return []
        vanilla = settings.get_vanilla_content_path() or ""
        warnings = []
        for type_name, kit in kits.items():
            for problem in check_kit(self._root, kit, vanilla):
                warnings.append(f"{type_name} : {problem}")
        return warnings

    def _broken_playfields(self, rows) -> list:
        """Playfields qu'on ne peut pas declarer comme depart : leur donnee ne
        se charge pas (cle racine dupliquee sans valeur) — le menu perdrait
        TOUS les departs et le client planterait (vecu 05/11)."""
        problems = []
        for type_name in sorted({row.type_name for row in rows}):
            for problem in check_playfield(self._root, type_name):
                problems.append(t("starters.playfield_broken",
                                  type=type_name, msg=problem))
        return problems

    def _apply(self) -> None:
        enabled, disabled, kits, cards = self._changes()
        if not (enabled or disabled or kits or cards):
            self.status.setText(t("starters.none_selected"))
            return
        broken = self._broken_playfields(enabled)
        if broken:
            self.status.setText("\n".join(broken[:4]))
            return
        if not ask_yes_no(self, t("starters.title"),
                          t("starters.confirm", n=len(enabled) + len(disabled),
                            k=len(kits), c=len(cards))):
            return
        path = sectors_yaml(self._root)
        if path is None:
            self.status.setText(t("starters.no_sectors"))
            return
        files = [path]
        touched = {row.type_name for row in enabled} | set(kits)
        touched |= {row.type_name for row in cards}
        for type_name in touched:
            static = static_path(self._root, type_name)
            if static is not None and static not in files:
                files.append(static)
        from core.workspace_undo import FileStateUndo, MultiFileStateUndo, capture_file
        prior = {candidate: capture_file(candidate) for candidate in files}
        written, cleared, kit_results, card_results, details = run_long(
            self, lambda: self._run_changes(enabled, disabled, kits, cards))
        if not written and not cleared and not kit_results and not card_results:
            self.status.setText("\n".join(details)
                                or t("starters.none_selected"))
            return
        self._backup(files)
        self.applied += written + cleared
        main = self._main
        if main is not None:
            undo = getattr(main, "_push_workspace_undo", None)
            if undo is not None:
                undo(MultiFileStateUndo(
                    [FileStateUndo(candidate, data, candidate.name)
                     for candidate, data in prior.items()],
                    t("starters.undo", n=len(files))))
            reload_tab = getattr(main, "_reload_tab_if_open_and_unmodified", None)
            if reload_tab is not None:
                for candidate in files:
                    reload_tab(candidate)
            ws = getattr(main, "workspace", None)
            if ws is not None:
                ws.rescan_working()
        message = (t("starters.done", n=written, r=cleared, k=len(kit_results),
                     c=len(card_results)) + "\n" + t("starters.new_game"))
        if details:
            message += "\n" + "\n".join(details[:5])
        self.status.setText(message)
        self._drafts.clear()
        self._load()
        self._run_bilan(message)

    def _run_changes(self, enabled, disabled, kits, cards):
        written, details = set_starts(self._root, enabled) if enabled else (0, [])
        cleared, extra = clear_starts(self._root, disabled) if disabled else (0, [])
        details += extra
        # le static et le dynamic sont lus dans un MEME flux par le jeu : un
        # fichier sans saut final casse le playfield entier (vecu 05/11)
        for type_name in sorted({row.type_name for row in enabled}):
            if ensure_final_eol(self._root, type_name):
                details.append(f"{type_name} : saut de ligne final ajoute")
        kit_results = []
        for type_name, kit in kits.items():
            result = write_kit(self._root, type_name, kit)
            if result not in ("updated", "created"):
                details.append(result)
            kit_results.append((type_name, result))
        card_results = []
        for row in cards:
            result = prepend_start_card(self._root, row)
            if result not in ("added", "already"):
                details.append(result)
            card_results.append((row.name, result))
        return written, cleared, kit_results, card_results, details

    def _backup(self, files) -> None:
        from core.fsutil import central_backup
        for candidate in files:
            central_backup(candidate, "starters")

    def _run_bilan(self, message: str) -> None:
        vanilla = settings.get_vanilla_content_path() or ""

        def work():
            from core.launch_check import run_launch_checks
            return run_launch_checks(self._root, vanilla)

        def done(issues):
            errors = sum(1 for i in issues if i.severity == "error")
            warnings = len(issues) - errors
            self.status.setText(message + "\n"
                                + t("starters.bilan", e=errors, w=warnings))

        def failed(error):
            self.status.setText(message + "\n"
                                + t("starters.bilan_failed", msg=str(error)))

        async_call(self, work, on_done=done, on_fail=failed,
                   name="starters-bilan")


def open_starters(parent, main_window=None) -> bool:
    ws = getattr(main_window, "workspace", None)
    root = getattr(ws, "working_root", None) if ws is not None else None
    if root is None:
        info(parent, t("starters.title"), t("starters.no_workspace"))
        return False
    dialog = StartersDialog(root, parent=parent, main_window=main_window)
    dialog.exec()
    return dialog.applied > 0
