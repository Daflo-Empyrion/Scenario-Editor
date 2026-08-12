"""
Dialogue affiche au demarrage (s'il existe des projets recents) : reprendre le dernier
projet en un clic, en choisir un autre dans la liste, ou en creer un nouveau.
"""
from typing import List, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton,
    QLabel,
)

from core.project_store import ProjectRecord
from core.i18n import t


class StartupDialog(QDialog):
    def __init__(self, projects: List[ProjectRecord], parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("startup.title"))
        self.setMinimumSize(560, 360)

        self.projects = projects
        self.chosen_project: Optional[ProjectRecord] = None
        self.want_new_project = False
        self.project_to_remove: Optional[ProjectRecord] = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(t("startup.subtitle")))

        self.list_widget = QListWidget()
        for p in projects:
            item = QListWidgetItem(p.display_name())
            item.setToolTip(f"A: {p.source_a}\nTravail: {p.working}" +
                             (f"\nB: {p.source_b}" if p.source_b else ""))
            item.setData(1000, p)
            self.list_widget.addItem(item)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
        self.list_widget.itemDoubleClicked.connect(self._on_open)
        layout.addWidget(self.list_widget)

        btn_row = QHBoxLayout()
        btn_open = QPushButton(t("startup.open_selected"))
        btn_open.clicked.connect(self._on_open)
        btn_row.addWidget(btn_open)

        btn_remove = QPushButton(t("startup.remove"))
        btn_remove.setObjectName("secondaryButton")
        btn_remove.clicked.connect(self._on_remove)
        btn_row.addWidget(btn_remove)

        btn_new = QPushButton(t("startup.new_project"))
        btn_new.clicked.connect(self._on_new)
        btn_row.addWidget(btn_new)

        btn_close = QPushButton(t("btn.close"))
        btn_close.setObjectName("secondaryButton")
        btn_close.clicked.connect(self.reject)
        btn_row.addWidget(btn_close)

        layout.addLayout(btn_row)

    def _on_open(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        self.chosen_project = item.data(1000)
        self.accept()

    def _on_new(self):
        self.want_new_project = True
        self.accept()

    def _on_remove(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        self.project_to_remove = item.data(1000)
        row = self.list_widget.row(item)
        self.list_widget.takeItem(row)
