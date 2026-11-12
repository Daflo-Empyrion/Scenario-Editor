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

"""Sauvegardes automatiques (`central_backup`) : lister, restaurer, nettoyer.

Les `*.bak` de `~/.empyrion_editor/backups/<type>/` n'avaient AUCUN chemin de
restauration dans l'application : il fallait recopier le fichier a la main.
Le nom ne porte pas l'emplacement d'origine (`<Nom>-<horodatage>.<ext>.bak`),
la destination est donc choisie par l'utilisateur, pre-remplie avec le nom
reconstitue ; l'actuel fichier est sauvegarde avant remplacement.

Les DOSSIERS de sauvegarde de scenario (`_backup_info.json`) ne sont pas
listes ici : ils appartiennent a `gui/backup_dialog.py`.
"""
import time
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel,
                             QMessageBox, QPushButton, QTreeWidget,
                             QTreeWidgetItem, QVBoxLayout)

from core.backup_manager import format_size
from core.fsutil import (BACKUP_KEEP, BACKUP_MAX_AGE_DAYS,
                         apply_backup_cleanup, list_backup_files,
                         original_name, plan_backup_cleanup,
                         restore_backup_file)
from core.i18n import t
from gui.msgboxes import ask_yes_no
from gui.theme import icon, icon_size


class BackupFilesDialog(QDialog):
    """Liste par type, date et taille ; restaurer vers un fichier choisi ;
    menage des plus anciennes."""

    def __init__(self, parent=None, root=None, start_dir: str = ""):
        super().__init__(parent)
        self._root = root                    # tests : arbre temporaire
        self._start_dir = start_dir
        self.setWindowTitle(t("bkf.title"))
        self.resize(780, 560)

        layout = QVBoxLayout(self)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels([t("bkf.col_name"), t("bkf.col_date"),
                                   t("bkf.col_size")])
        self.tree.setRootIsDecorated(True)
        self.tree.itemSelectionChanged.connect(self._update_buttons)
        layout.addWidget(self.tree)

        row = QHBoxLayout()
        self.info = QLabel("")
        row.addWidget(self.info, 1)
        self.btn_restore = QPushButton(icon("fa5s.undo", "#4a7dfc"),
                                       t("bkf.restore"))
        self.btn_restore.setIconSize(icon_size())
        self.btn_restore.clicked.connect(self._restore)
        row.addWidget(self.btn_restore)
        self.btn_clean = QPushButton(icon("fa5s.broom", "#d08b00"),
                                     t("bkf.clean"))
        self.btn_clean.setIconSize(icon_size())
        self.btn_clean.clicked.connect(self._clean)
        row.addWidget(self.btn_clean)
        btn_close = QPushButton(t("btn.close"))
        btn_close.clicked.connect(self.accept)
        row.addWidget(btn_close)
        layout.addLayout(row)

        self.reload()

    # ------------------------------------------------------------------ etat
    def reload(self) -> None:
        self.tree.clear()
        rows = list_backup_files(self._root)
        by_kind: dict = {}
        for path, kind, mtime, size in rows:
            by_kind.setdefault(kind, []).append((path, mtime, size))
        for kind in sorted(by_kind):
            parent = QTreeWidgetItem([kind, "", ""])
            parent.setFlags(parent.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            for path, mtime, size in by_kind[kind]:
                child = QTreeWidgetItem([
                    path.name,
                    time.strftime("%d/%m/%Y %H:%M", time.localtime(mtime)),
                    format_size(size)])
                child.setData(0, Qt.ItemDataRole.UserRole, str(path))
                parent.addChild(child)
            parent.setExpanded(True)
            self.tree.addTopLevelItem(parent)
        self.info.setText("" if rows else t("bkf.empty"))
        self._update_buttons()

    def _selected_file(self):
        item = self.tree.currentItem()
        if item is None or item.parent() is None:
            return None
        value = item.data(0, Qt.ItemDataRole.UserRole)
        return Path(value) if value else None

    def _update_buttons(self) -> None:
        self.btn_restore.setEnabled(self._selected_file() is not None)

    # ------------------------------------------------------------ restauration
    def _restore(self) -> None:
        backup = self._selected_file()
        if backup is None:
            return
        start = Path(self._start_dir) if self._start_dir else Path.home()
        target, _filt = QFileDialog.getSaveFileName(
            self, t("bkf.pick_title"), str(start / original_name(backup)),
            t("bkf.pick_filter"))
        if not target:
            return
        if Path(target).is_file() and not ask_yes_no(
                self, t("bkf.title"),
                t("bkf.confirm_replace", path=target,
                  name=backup.name)):
            return
        try:
            safety = restore_backup_file(backup, target)
        except OSError as exc:
            QMessageBox.critical(self, t("bkf.title"),
                                 t("bkf.error", error=str(exc)))
            return
        QMessageBox.information(
            self, t("bkf.title"),
            t("bkf.done", path=target,
              safety=str(safety) if safety else t("bkf.no_safety")))
        self.reload()

    # ----------------------------------------------------------------- menage
    def _clean(self) -> None:
        plan = plan_backup_cleanup(self._root)
        if not plan:
            QMessageBox.information(self, t("backups.title"),
                                    t("backups.nothing", keep=BACKUP_KEEP))
            return
        if not ask_yes_no(self, t("backups.title"),
                          t("backups.confirm", n=len(plan),
                            size=format_size(sum(plan.values())),
                            keep=BACKUP_KEEP, days=BACKUP_MAX_AGE_DAYS)):
            return
        count, freed = apply_backup_cleanup(plan)
        QMessageBox.information(self, t("backups.title"),
                                t("backups.done", n=count,
                                  size=format_size(freed)))
        self.reload()


def open_backup_files(parent, start_dir: str = "") -> None:
    """Point d'entree (menu Outils > Fichiers)."""
    dialog = BackupFilesDialog(parent, start_dir=start_dir)
    dialog.exec()
