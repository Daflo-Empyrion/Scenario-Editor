"""
Visualiseur de wiki integre a l'application : affiche les fichiers Markdown de docs/
dans une fenetre avec rendu (titres, listes, tableaux, code) via QTextBrowser.
"""
from pathlib import Path

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt


class WikiDialog(QDialog):
    def __init__(self, title: str, markdown_path: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(900, 700)

        layout = QVBoxLayout(self)

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        try:
            content = markdown_path.read_text(encoding='utf-8')
            self.browser.setMarkdown(content)
        except Exception as e:
            self.browser.setPlainText(f"Impossible de charger {markdown_path} :\n{e}")
        layout.addWidget(self.browser)

        buttons = QHBoxLayout()
        buttons.addStretch()
        btn_close = QPushButton("Fermer")
        btn_close.clicked.connect(self.accept)
        buttons.addWidget(btn_close)
        layout.addLayout(buttons)


def open_wiki(parent, title: str, filename: str):
    """Ouvre un fichier docs/<filename> dans la fenetre de wiki. Cherche le dossier docs/
    relativement a ce module (fonctionne que l'appli soit lancee depuis n'importe ou)."""
    docs_dir = Path(__file__).resolve().parent.parent / "docs"
    path = docs_dir / filename
    dialog = WikiDialog(title, path, parent)
    dialog.exec()
