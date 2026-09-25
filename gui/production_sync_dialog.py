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

"""Synchronisation vers le scenario EN PRODUCTION (demande utilisateur
24/09/2026) : a la fermeture de l'application (et depuis le menu Projet),
proposer de copier (remplacer) tous les fichiers modifies dans l'appli
vers le repertoire du scenario que charge le jeu — plus de copier-coller
manuel. Les fichiers ecrases sont sauvegardes avant remplacement."""
import time
from pathlib import Path

from PyQt6.QtWidgets import (QCheckBox, QDialog, QFileDialog, QHBoxLayout,
                             QLabel, QListWidget, QListWidgetItem,
                             QPushButton, QVBoxLayout)

from core.i18n import t
from gui.window_geometry import track


class ProductionSyncDialog(QDialog):
    """Liste les fichiers modifies (vs source A), laisse choisir le dossier
    de production (deduit du nom une premiere fois, persiste ensuite),
    sauvegarde les fichiers ecrases puis copie (remplace)."""

    def __init__(self, main_window, parent=None, from_close: bool = False):
        from PyQt6.QtWidgets import QWidget
        # main_window sert aux chemins ; seul un QWidget reel peut servir
        # de parent Qt (les tests passent un simple namespace)
        qt_parent = parent if isinstance(parent, QWidget) else (
            main_window if isinstance(main_window, QWidget) else None)
        super().__init__(qt_parent)
        self.setWindowTitle(t("prodsync.title"))
        self.main_window = main_window
        self._from_close = from_close
        self._files = []
        self._backup_root = None
        track(self, "production_sync", (760, 520))
        self._build_ui()
        self._scan()

    # ------------------------------------------------------------- construction

    def _build_ui(self):
        lay = QVBoxLayout(self)

        ws = self.main_window.workspace if self.main_window else None
        self._working_root = Path(ws.working_root) if ws else None

        lay.addWidget(QLabel(t("prodsync.target_label")))
        row = QHBoxLayout()
        self.target_edit = self._line_edit()
        row.addWidget(self.target_edit, 1)
        self.btn_browse = QPushButton(t("prodsync.browse"))
        self.btn_browse.clicked.connect(self._pick_target)
        row.addWidget(self.btn_browse)
        lay.addLayout(row)

        self.hint_label = QLabel("")
        self.hint_label.setStyleSheet("color: gray;")
        self.hint_label.setWordWrap(True)
        lay.addWidget(self.hint_label)

        self.files_label = QLabel(t("prodsync.scanning"))
        lay.addWidget(self.files_label)
        self.list_files = QListWidget()
        lay.addWidget(self.list_files, 1)

        self.chk_backup = QCheckBox(t("prodsync.backup_box"))
        self.chk_backup.setChecked(True)
        lay.addWidget(self.chk_backup)

        row_btn = QHBoxLayout()
        self.btn_copy = QPushButton(t("prodsync.copy_btn"))
        self.btn_copy.setObjectName("primaryButton")
        self.btn_copy.setEnabled(False)
        self.btn_copy.clicked.connect(self._do_copy)
        row_btn.addWidget(self.btn_copy, 1)
        self.btn_close = QPushButton(t("prodsync.close_btn"))
        self.btn_close.clicked.connect(self.reject)
        row_btn.addWidget(self.btn_close)
        lay.addLayout(row_btn)

        self.chk_ask = QCheckBox(t("prodsync.no_more_propose"))
        from core.settings import get_propose_sync_on_close
        self.chk_ask.setChecked(not get_propose_sync_on_close())
        self.chk_ask.toggled.connect(
            lambda on: self._set_propose(not on))
        lay.addWidget(self.chk_ask)

    def _line_edit(self):
        from PyQt6.QtWidgets import QLineEdit
        edit = QLineEdit()
        edit.textEdited.connect(lambda _t: self._refresh_buttons())
        # changement de dossier (Entree / sortie de champ) : recalcul — la
        # liste est une DIFFERENCE AVEC LA PRODUCTION, pas avec la source
        edit.editingFinished.connect(self._scan)
        return edit

    # ------------------------------------------------------------- donnees

    def _scan(self):
        """Liste les fichiers DIFFERENTS DU DOSSIER DE PRODUCTION (hors
        thread GUI). Vecu 24/09 : une difference vs la source A listait a
        l'infini les memes fichiers — apres une copie reussie, production
        == copie de travail, donc plus rien a proposer."""
        from gui.busy import run_long
        self._files = []
        self.list_files.clear()
        if self._working_root is None:
            self.files_label.setText(t("prodsync.no_project"))
            self._refresh_buttons()
            return
        self._autodetect_target()
        target = self.target_edit.text().strip()
        if not target or not Path(target).is_dir():
            self.files_label.setText(t("prodsync.choose_target"))
            self._refresh_buttons()
            return
        from gui.modified_files_dialog import list_changed_files
        self._files = run_long(
            self, lambda: list_changed_files(self._working_root,
                                             Path(target)))
        for src, state in self._files:
            key = ("prodsync.state_added" if state == "added"
                   else "prodsync.state_modified")
            rel = Path(src).relative_to(self._working_root)
            self.list_files.addItem(QListWidgetItem(f"[{t(key)}] {rel}"))
        self.files_label.setText(t("prodsync.files", n=len(self._files)))
        self._refresh_buttons()

    def _autodetect_target(self):
        """Dossier de production MEMORISE POUR CE PROJET, sinon deduit du
        nom (<vanille>/Content/Scenarios/<copie de travail>)."""
        from core.production_sync import find_default_production_root
        from core.settings import get_production_scenario_path
        target = get_production_scenario_path(str(self._working_root))
        if target and Path(target).is_dir():
            self.target_edit.setText(target)
            self.hint_label.setText(t("prodsync.hint_saved"))
            return
        from core.settings import get_vanilla_content_path
        guess = find_default_production_root(get_vanilla_content_path(),
                                             self._working_root)
        if guess is not None:
            self.target_edit.setText(str(guess))
            self.hint_label.setText(t("prodsync.hint_detected"))
        else:
            self.hint_label.setText(t("prodsync.hint_manual"))

    def _pick_target(self):
        start = self.target_edit.text() or str(self._working_root or ".")
        chosen = QFileDialog.getExistingDirectory(self, t("prodsync.browse"),
                                                  start)
        if chosen:
            self.target_edit.setText(chosen)
            self._scan()

    def has_files(self) -> bool:
        return bool(self._files)

    def _refresh_buttons(self):
        target = self.target_edit.text().strip()
        self.btn_copy.setEnabled(
            bool(self._files) and target
            and Path(target).is_dir()
            and Path(target).resolve() != (
                self._working_root.resolve()
                if self._working_root else None))

    # ------------------------------------------------------------- action

    def _do_copy(self):
        """Copie (remplace) vers la production, hors du thread GUI, avec
        sauvegarde prealable des fichiers ecrases. A la reussite : message
        de confirmation puis fermeture du dialogue (demande 24/09/2026)."""
        from core.production_sync import sync_to_production
        from core.settings import set_production_scenario_path
        from gui.busy import run_long
        from gui.msgboxes import critical, info

        prod = Path(self.target_edit.text().strip())
        set_production_scenario_path(str(self._working_root), str(prod))
        backup = None
        if self.chk_backup.isChecked():
            backup = (Path.home() / ".empyrion_editor" / "production_sync"
                      / time.strftime("%Y%m%d_%H%M%S"))
        try:
            copied, saved = run_long(
                self, lambda: sync_to_production(self._files,
                                                 self._working_root,
                                                 prod, backup))
        except Exception as e:  # noqa: BLE001 - message et dialogue ouvert
            critical(self, t("err.title"),
                     t("prodsync.copy_failed", error=e))
            return
        self._backup_root = saved
        self.files_label.setText(t("prodsync.done", n=copied))
        msg = t("prodsync.done_msg", n=copied,
                target=prod)
        if saved is not None:
            self.hint_label.setText(t("prodsync.saved_to", path=saved))
            msg += "\n" + t("prodsync.saved_to", path=saved)
        info(self, t("prodsync.done_title"), msg)
        self.accept()

    def _set_propose(self, on: bool):
        from core.settings import set_propose_sync_on_close
        set_propose_sync_on_close(on)
