"""
Fenetre generique de sauvegarde/restauration, reutilisee pour deux besoins :
  - kind='scenario' : sauvegarder la version vanille d'un scenario avant une mise a
    jour Steam Workshop (qui ecrase le dossier en place), pour pouvoir la comparer
    plus tard a la nouvelle version.
  - kind='savegame' : sauvegarder/restaurer la progression de partie.

Accessible independamment de tout projet ouvert (Fichier > ...).
"""
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QLabel, QFileDialog, QMessageBox, QListWidget, QListWidgetItem, QProgressDialog,
    QApplication,
)
from PyQt6.QtCore import Qt
import os
import subprocess
import sys

from core.i18n import t
from core import settings, backup_manager
from gui.theme import icon, icon_size


class BackupManagerDialog(QDialog):
    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self.kind = kind  # 'scenario' ou 'savegame'
        title_key = "backup.title_scenario" if kind == 'scenario' else "backup.title_savegame"
        self.setWindowTitle(t(title_key))
        self.resize(750, 600)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.edit_source = QLineEdit()
        btn_source = QPushButton(t("newproj.browse"))
        btn_source.clicked.connect(lambda: self._browse(self.edit_source))
        row_source = QHBoxLayout()
        row_source.addWidget(self.edit_source)
        row_source.addWidget(btn_source)
        source_label_key = "backup.source_scenario" if kind == 'scenario' else "backup.source_savegame"
        form.addRow(t(source_label_key), row_source)

        self.edit_storage = QLineEdit(settings.get_backup_root(kind))
        btn_storage = QPushButton(t("newproj.browse"))
        btn_storage.clicked.connect(lambda: self._browse(self.edit_storage, remember=True))
        row_storage = QHBoxLayout()
        row_storage.addWidget(self.edit_storage)
        row_storage.addWidget(btn_storage)
        form.addRow(t("backup.storage_folder"), row_storage)

        self.edit_label = QLineEdit()
        form.addRow(t("backup.label"), self.edit_label)
        layout.addLayout(form)

        btn_create = QPushButton(icon("fa5s.save", "#ffffff"), t("backup.create"))
        btn_create.setIconSize(icon_size())
        btn_create.clicked.connect(self._create_backup)
        layout.addWidget(btn_create)

        layout.addWidget(QLabel(t("backup.existing_list")))
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget, 1)

        actions_row = QHBoxLayout()
        btn_restore = QPushButton(icon("fa5s.undo", "#4a7dfc"), t("backup.restore"))
        btn_restore.setIconSize(icon_size())
        btn_restore.setObjectName("secondaryButton")
        btn_restore.clicked.connect(self._restore_selected)
        actions_row.addWidget(btn_restore)

        if kind == 'scenario':
            btn_compare = QPushButton(icon("fa5s.balance-scale", "#4a7dfc"), t("backup.compare_with"))
            btn_compare.setIconSize(icon_size())
            btn_compare.setObjectName("secondaryButton")
            btn_compare.clicked.connect(self._compare_selected)
            actions_row.addWidget(btn_compare)

        btn_open = QPushButton(icon("fa5s.folder-open", "#4a7dfc"), t("backup.open_folder"))
        btn_open.setIconSize(icon_size())
        btn_open.setObjectName("secondaryButton")
        btn_open.clicked.connect(self._open_selected_folder)
        actions_row.addWidget(btn_open)

        btn_delete = QPushButton(icon("fa5s.trash-alt", "#ef4444"), t("backup.delete"))
        btn_delete.setIconSize(icon_size())
        btn_delete.setObjectName("secondaryButton")
        btn_delete.clicked.connect(self._delete_selected)
        actions_row.addWidget(btn_delete)
        actions_row.addStretch()
        layout.addLayout(actions_row)

        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        btn_close = QPushButton(t("btn.close"))
        btn_close.setObjectName("secondaryButton")
        btn_close.clicked.connect(self.accept)
        bottom_row.addWidget(btn_close)
        layout.addLayout(bottom_row)

        self._refresh_list()

    def _browse(self, target_edit: QLineEdit, remember: bool = False):
        folder = QFileDialog.getExistingDirectory(self, t("compare.choose_folder"))
        if folder:
            target_edit.setText(folder)
            if remember:
                settings.set_backup_root(self.kind, folder)

    def _current_backup_root(self) -> Optional[Path]:
        text = self.edit_storage.text().strip()
        return Path(text) if text else None

    def _refresh_list(self):
        self.list_widget.clear()
        root = self._current_backup_root()
        if not root or not root.exists():
            return
        records = backup_manager.list_backups(root, kind=self.kind)
        if not records:
            item = QListWidgetItem(t("backup.none_yet"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(item)
            return
        for record in records:
            size = backup_manager.format_size(backup_manager.backup_size_bytes(record))
            item = QListWidgetItem(f"{record.display_name()}   ({size})")
            item.setData(Qt.ItemDataRole.UserRole, record)
            item.setToolTip(record.source_path)
            self.list_widget.addItem(item)

    def _selected_record(self):
        item = self.list_widget.currentItem()
        if not item:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _create_backup(self):
        source_text = self.edit_source.text().strip()
        storage_text = self.edit_storage.text().strip()
        if not source_text:
            QMessageBox.warning(self, t("err.missing_field"), t("backup.source_required"))
            return
        if not storage_text:
            QMessageBox.warning(self, t("err.missing_field"), t("backup.storage_required"))
            return

        source = Path(source_text)
        storage = Path(storage_text)
        settings.set_backup_root(self.kind, storage_text)

        progress = QProgressDialog(t("progress.please_wait"), None, 0, 0, self)
        progress.setWindowTitle(t("progress.please_wait"))
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()

        try:
            record = backup_manager.create_backup(source, storage, self.edit_label.text().strip() or None, self.kind)
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, t("backup.error"), str(e))
            return
        progress.close()

        QMessageBox.information(self, t("backup.created_title"),
                                 t("backup.created_msg", path=record.backup_path))
        self.edit_label.clear()
        self._refresh_list()

    def _restore_selected(self):
        record = self._selected_record()
        if not record:
            QMessageBox.information(self, t("err.missing_field"), t("backup.select_one"))
            return

        default_dest = record.source_path or ""
        dest_text, ok = self._ask_destination(default_dest)
        if not ok or not dest_text.strip():
            return
        destination = Path(dest_text.strip())

        confirm = QMessageBox.question(
            self, t("backup.confirm_restore"),
            f"{t('backup.restore_warning')}\n\n{destination}"
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        progress = QProgressDialog(t("progress.please_wait"), None, 0, 0, self)
        progress.setWindowTitle(t("progress.please_wait"))
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()

        try:
            safety = backup_manager.restore_backup(
                record, destination, safety_backup_root=self._current_backup_root()
            )
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, t("backup.restore_error"), str(e))
            return
        progress.close()

        msg = t("backup.restore_done_msg", path=destination)
        if safety:
            msg += t("backup.restore_done_with_safety", label=safety.label)
        QMessageBox.information(self, t("backup.restore_done_title"), msg)
        self._refresh_list()

    def _ask_destination(self, default_text: str):
        from PyQt6.QtWidgets import QInputDialog
        return QInputDialog.getText(self, t("backup.restore_title"),
                                     t("backup.restore_destination"), text=default_text)

    def _delete_selected(self):
        record = self._selected_record()
        if not record:
            QMessageBox.information(self, t("err.missing_field"), t("backup.select_one"))
            return
        confirm = QMessageBox.question(
            self, t("backup.confirm_delete_title"),
            t("backup.confirm_delete_msg", label=record.label)
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        backup_manager.delete_backup(record)
        self._refresh_list()

    def _open_selected_folder(self):
        record = self._selected_record()
        if not record:
            QMessageBox.information(self, t("err.missing_field"), t("backup.select_one"))
            return
        path = record.backup_path
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)])
        else:
            subprocess.run(["xdg-open", str(path)])

    def _compare_selected(self):
        record = self._selected_record()
        if not record:
            QMessageBox.information(self, t("err.missing_field"), t("backup.select_one"))
            return
        from gui.scenario_compare_dialog import ScenarioCompareDialog
        dialog = ScenarioCompareDialog(self)
        dialog.edit_a.setText(str(record.content_path()))
        dialog.exec()
