"""
Dialogue "Nouveau projet" : choix du scenario A (base), optionnellement du scenario B
(pour la fusion), et de l'emplacement ou creer la copie de travail modifiable.
"""
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QCheckBox, QDialogButtonBox, QFileDialog, QLabel, QMessageBox,
)

from core.i18n import t


class NewProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("newproj.title"))
        self.setMinimumWidth(520)

        self.source_a_path: Optional[Path] = None
        self.source_b_path: Optional[Path] = None
        self.dest_path: Optional[Path] = None

        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.edit_a = QLineEdit()
        self.edit_a.setPlaceholderText(t("newproj.scenario_a_placeholder"))
        btn_a = QPushButton(t("newproj.browse"))
        btn_a.clicked.connect(lambda: self._browse(self.edit_a))
        row_a = QHBoxLayout()
        row_a.addWidget(self.edit_a)
        row_a.addWidget(btn_a)
        form.addRow(t("newproj.scenario_a"), row_a)

        self.checkbox_merge = QCheckBox(t("newproj.merge_mode"))
        self.checkbox_merge.toggled.connect(self._on_merge_toggled)
        form.addRow("", self.checkbox_merge)

        self.edit_b = QLineEdit()
        self.edit_b.setPlaceholderText(t("newproj.scenario_b_placeholder"))
        self.edit_b.setEnabled(False)
        self.btn_b = QPushButton(t("newproj.browse"))
        self.btn_b.setEnabled(False)
        self.btn_b.clicked.connect(lambda: self._browse(self.edit_b))
        row_b = QHBoxLayout()
        row_b.addWidget(self.edit_b)
        row_b.addWidget(self.btn_b)
        form.addRow(t("newproj.scenario_b"), row_b)

        self.edit_dest = QLineEdit()
        self.edit_dest.setPlaceholderText(t("newproj.working_copy_placeholder"))
        btn_dest = QPushButton(t("newproj.browse"))
        btn_dest.clicked.connect(self._browse_dest)
        row_dest = QHBoxLayout()
        row_dest.addWidget(self.edit_dest)
        row_dest.addWidget(btn_dest)
        form.addRow(t("newproj.working_copy"), row_dest)

        layout.addLayout(form)

        info = QLabel(t("newproj.info"))
        info.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(info)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setObjectName("secondaryButton")
        layout.addWidget(buttons)

    def _browse(self, target_edit: QLineEdit):
        folder = QFileDialog.getExistingDirectory(self, t("newproj.choose_scenario_folder"))
        if folder:
            target_edit.setText(folder)

    def _browse_dest(self):
        folder = QFileDialog.getExistingDirectory(self, t("newproj.choose_parent_folder"))
        if folder:
            # On propose un sous-dossier par defaut plutot que d'ecrire directement
            # dans le dossier choisi (qui pourrait deja contenir des choses).
            suggested = str(Path(folder) / "copie_de_travail")
            self.edit_dest.setText(suggested)

    def _on_merge_toggled(self, checked: bool):
        self.edit_b.setEnabled(checked)
        self.btn_b.setEnabled(checked)

    def _on_accept(self):
        if not self.edit_a.text().strip():
            QMessageBox.warning(self, t("err.missing_field"), t("newproj.scenario_a_placeholder"))
            return
        if not self.edit_dest.text().strip():
            QMessageBox.warning(self, t("err.missing_field"), t("newproj.working_copy_placeholder"))
            return

        source_a = Path(self.edit_a.text().strip())
        dest = Path(self.edit_dest.text().strip())

        if not source_a.exists():
            QMessageBox.warning(self, t("err.invalid_path"), f"{source_a}")
            return
        if dest.exists():
            QMessageBox.warning(self, t("err.dest_exists"), f"{dest}")
            return

        source_b = None
        if self.checkbox_merge.isChecked():
            if not self.edit_b.text().strip():
                QMessageBox.warning(self, t("err.missing_field"), t("newproj.scenario_b_placeholder"))
                return
            source_b = Path(self.edit_b.text().strip())
            if not source_b.exists():
                QMessageBox.warning(self, t("err.invalid_path"), f"{source_b}")
                return

        self.source_a_path = source_a
        self.source_b_path = source_b
        self.dest_path = dest
        self.accept()
