"""Fenetre NON MODALE "Verification economie" : coherence du
TraderNPCConfig.ecf de la copie de travail avec le catalogue (MarketPrice) et
les TraderZone des playfields. Lecture seule -- les corrections se font dans
l'editeur d'economie (menu Outils) ou l'editeur playfield.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QLabel, QListWidget, QListWidgetItem,
                             QPushButton, QVBoxLayout)

from core.i18n import t
from gui.theme import icon


class EconomyCheckDialog(QDialog):
    def __init__(self, issues, parent=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setWindowTitle(t("ecocheck.title"))
        self.setMinimumSize(640, 420)
        layout = QVBoxLayout(self)
        intro = QLabel(t("ecocheck.intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.list_widget = QListWidget()
        for issue in issues:
            loc = ""
            if issue.trader:
                loc = f"[{issue.trader}"
                if issue.item_key:
                    loc += f" / {issue.item_key}"
                loc += "] "
            badge = "ERR" if issue.level == "error" else "ATT"
            text = f"[{badge}] {loc}{t(issue.code, **issue.params)}"
            item = QListWidgetItem(text)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget, 1)

        self.count_label = QLabel(t("ecocheck.count", n=len(issues)))
        layout.addWidget(self.count_label)
        close = QPushButton(icon("fa5s.check", "#ffffff"), t("btn.close"))
        close.clicked.connect(self.accept)
        layout.addWidget(close, 0)
