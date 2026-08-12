"""
Visualiseur de wiki integre a l'application : affiche les fichiers Markdown de docs/
dans une fenetre avec rendu (titres, listes, tableaux, code) via QTextBrowser.
"""
from pathlib import Path

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt

from core import i18n


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
        btn_close = QPushButton(i18n.t("btn.close"))
        btn_close.clicked.connect(self.accept)
        buttons.addWidget(btn_close)
        layout.addLayout(buttons)


def open_wiki(parent, title: str, base_filename: str):
    """Ouvre docs/<base_filename>_<langue>.md, choisissant la langue active
    (docs/wiki_app_fr.md ou docs/wiki_app_en.md par ex.), avec repli sur le francais si
    la traduction demandee est introuvable."""
    docs_dir = Path(__file__).resolve().parent.parent / "docs"
    lang = i18n.get_language()
    path = docs_dir / f"{base_filename}_{lang}.md"
    if not path.exists():
        path = docs_dir / f"{base_filename}_fr.md"
    dialog = WikiDialog(title, path, parent)
    dialog.exec()
