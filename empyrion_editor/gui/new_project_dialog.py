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


class NewProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nouveau projet")
        self.setMinimumWidth(520)

        self.source_a_path: Optional[Path] = None
        self.source_b_path: Optional[Path] = None
        self.dest_path: Optional[Path] = None

        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.edit_a = QLineEdit()
        self.edit_a.setPlaceholderText("Dossier racine du scenario de base...")
        btn_a = QPushButton("Parcourir...")
        btn_a.clicked.connect(lambda: self._browse(self.edit_a))
        row_a = QHBoxLayout()
        row_a.addWidget(self.edit_a)
        row_a.addWidget(btn_a)
        form.addRow("Scenario A (base) :", row_a)

        self.checkbox_merge = QCheckBox("Mode fusion (ajouter un second scenario source B)")
        self.checkbox_merge.toggled.connect(self._on_merge_toggled)
        form.addRow("", self.checkbox_merge)

        self.edit_b = QLineEdit()
        self.edit_b.setPlaceholderText("Dossier racine du scenario B...")
        self.edit_b.setEnabled(False)
        self.btn_b = QPushButton("Parcourir...")
        self.btn_b.setEnabled(False)
        self.btn_b.clicked.connect(lambda: self._browse(self.edit_b))
        row_b = QHBoxLayout()
        row_b.addWidget(self.edit_b)
        row_b.addWidget(self.btn_b)
        form.addRow("Scenario B (source, optionnel) :", row_b)

        self.edit_dest = QLineEdit()
        self.edit_dest.setPlaceholderText("Nouvel emplacement pour la copie de travail...")
        btn_dest = QPushButton("Parcourir...")
        btn_dest.clicked.connect(self._browse_dest)
        row_dest = QHBoxLayout()
        row_dest.addWidget(self.edit_dest)
        row_dest.addWidget(btn_dest)
        form.addRow("Copie de travail (modifiable) :", row_dest)

        layout.addLayout(form)

        info = QLabel(
            "La copie de travail sera une copie physique complete du scenario A, creee\n"
            "au nouvel emplacement choisi. Les scenarios A et B restent en lecture seule\n"
            "et ne seront jamais modifies."
        )
        info.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(info)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self, target_edit: QLineEdit):
        folder = QFileDialog.getExistingDirectory(self, "Choisir un dossier de scenario")
        if folder:
            target_edit.setText(folder)

    def _browse_dest(self):
        folder = QFileDialog.getExistingDirectory(self, "Choisir le dossier PARENT de la copie de travail")
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
            QMessageBox.warning(self, "Champ manquant", "Choisis le scenario A (base).")
            return
        if not self.edit_dest.text().strip():
            QMessageBox.warning(self, "Champ manquant", "Choisis l'emplacement de la copie de travail.")
            return

        source_a = Path(self.edit_a.text().strip())
        dest = Path(self.edit_dest.text().strip())

        if not source_a.exists():
            QMessageBox.warning(self, "Chemin invalide", f"Le scenario A n'existe pas :\n{source_a}")
            return
        if dest.exists():
            QMessageBox.warning(self, "Destination existante",
                                 f"Ce dossier existe deja, choisis un nouvel emplacement :\n{dest}")
            return

        source_b = None
        if self.checkbox_merge.isChecked():
            if not self.edit_b.text().strip():
                QMessageBox.warning(self, "Champ manquant", "Choisis le scenario B, ou decoche le mode fusion.")
                return
            source_b = Path(self.edit_b.text().strip())
            if not source_b.exists():
                QMessageBox.warning(self, "Chemin invalide", f"Le scenario B n'existe pas :\n{source_b}")
                return

        self.source_a_path = source_a
        self.source_b_path = source_b
        self.dest_path = dest
        self.accept()
