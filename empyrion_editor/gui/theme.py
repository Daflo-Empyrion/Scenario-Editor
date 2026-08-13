"""
Theme visuel de l'application, inspire d'un tableau de bord admin moderne (bleu/marine,
cartes arrondies, icones vectorielles). Un seul point d'entree : apply_theme(app).

Palette extraite d'une reference visuelle fournie par l'utilisateur (capture d'ecran
d'un dashboard admin) : bleu primaire vif, fond gris-bleu tres clair, cartes blanches
a coins arrondis, accents vert/orange/rouge pour les statuts, marine fonce pour les
zones de navigation.
"""
from PyQt6.QtGui import QIcon, QFont, QFontDatabase
from PyQt6.QtCore import QSize

try:
    import qtawesome as qta
    _HAS_QTA = True
except ImportError:
    _HAS_QTA = False


# ------------------------------------------------------------------
# Palette
# ------------------------------------------------------------------
PRIMARY = "#4a7dfc"
PRIMARY_DARK = "#3a63d8"
PRIMARY_DARKER = "#2f52b8"
PRIMARY_LIGHT = "#7ba3f5"
PRIMARY_BG_TINT = "#eaf0fe"

NAVY = "#131a2e"
NAVY_LIGHT = "#1c2440"

BG = "#eef1f6"
CARD_BG = "#ffffff"
BORDER = "#e2e6f0"
BORDER_STRONG = "#c9d0e0"

TEXT_DARK = "#1a1f36"
TEXT_GRAY = "#7c859c"
TEXT_ON_PRIMARY = "#ffffff"

GREEN = "#22c55e"
ORANGE = "#f5a623"
RED = "#ef4444"
RED_DARK = "#dc2626"

FONT_FAMILY = "Segoe UI"


# ------------------------------------------------------------------
# Icones (qtawesome si disponible -- degrade proprement sinon : QIcon() vide,
# les boutons gardent alors juste leur texte, rien ne casse).
# ------------------------------------------------------------------
def icon(name: str, color: str = TEXT_DARK, size: int = 16) -> QIcon:
    if not _HAS_QTA:
        return QIcon()
    try:
        return qta.icon(name, color=color)
    except Exception:
        return QIcon()


def icon_size() -> QSize:
    return QSize(15, 15)


# ------------------------------------------------------------------
# Feuille de style Qt (QSS) globale
# ------------------------------------------------------------------
STYLESHEET = f"""
* {{
    font-family: "{FONT_FAMILY}", "Segoe UI", sans-serif;
}}

QMainWindow, QWidget {{
    background-color: {BG};
    color: {TEXT_DARK};
}}

QDialog {{
    background-color: {CARD_BG};
}}

/* --- Barre de menus --- */
QMenuBar {{
    background-color: {NAVY};
    color: #ffffff;
    padding: 4px;
    font-weight: 600;
}}
QMenuBar::item {{
    background: transparent;
    padding: 6px 12px;
    border-radius: 6px;
    margin: 2px;
}}
QMenuBar::item:selected {{
    background-color: {PRIMARY};
}}
QMenu {{
    background-color: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px;
}}
QMenu::item {{
    padding: 7px 24px 7px 12px;
    border-radius: 6px;
    color: {TEXT_DARK};
}}
QMenu::item:selected {{
    background-color: {PRIMARY_BG_TINT};
    color: {PRIMARY_DARK};
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 6px 8px;
}}

/* --- Barre d'outils --- */
QToolBar {{
    background-color: {NAVY};
    border: none;
    padding: 6px;
    spacing: 6px;
}}

/* --- Barre de statut --- */
QStatusBar {{
    background-color: {CARD_BG};
    color: {TEXT_GRAY};
    border-top: 1px solid {BORDER};
    padding: 2px 8px;
}}

/* --- Boutons --- */
QPushButton {{
    background-color: {PRIMARY};
    color: {TEXT_ON_PRIMARY};
    border: none;
    border-radius: 8px;
    padding: 7px 16px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: {PRIMARY_DARK};
}}
QPushButton:pressed {{
    background-color: {PRIMARY_DARKER};
}}
QPushButton:disabled {{
    background-color: {BORDER_STRONG};
    color: {TEXT_GRAY};
}}
QPushButton:checked {{
    background-color: {PRIMARY_DARKER};
}}

/* Boutons secondaires (fond clair) -- utiliser objectName "secondaryButton" */
QPushButton#secondaryButton {{
    background-color: {CARD_BG};
    color: {TEXT_DARK};
    border: 1px solid {BORDER_STRONG};
}}
QPushButton#secondaryButton:hover {{
    background-color: {PRIMARY_BG_TINT};
    border-color: {PRIMARY};
    color: {PRIMARY_DARK};
}}
QPushButton#secondaryButton:disabled {{
    background-color: {BG};
    color: {BORDER_STRONG};
    border: 1px solid {BORDER};
}}

/* --- Champs de saisie --- */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {CARD_BG};
    border: 1.5px solid {BORDER};
    border-radius: 8px;
    padding: 6px 10px;
    selection-background-color: {PRIMARY_LIGHT};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {PRIMARY};
}}

/* --- Tableaux et arbres --- */
QTableWidget, QTreeWidget, QListWidget {{
    background-color: {CARD_BG};
    alternate-background-color: {PRIMARY_BG_TINT};
    border: 1px solid {BORDER};
    border-radius: 10px;
    gridline-color: {BORDER};
    selection-background-color: {PRIMARY};
    selection-color: {TEXT_ON_PRIMARY};
}}
QHeaderView::section {{
    background-color: {BG};
    color: {TEXT_GRAY};
    padding: 6px 8px;
    border: none;
    border-bottom: 2px solid {BORDER};
    font-weight: 700;
}}
QTreeWidget::item, QListWidget::item {{
    padding: 3px;
    border-radius: 4px;
}}
QTreeWidget::item:selected, QListWidget::item:selected {{
    background-color: {PRIMARY};
    color: {TEXT_ON_PRIMARY};
}}
QTableWidget::item:selected {{
    background-color: {PRIMARY};
    color: {TEXT_ON_PRIMARY};
}}

/* --- Onglets --- */
QTabWidget::pane {{
    background-color: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 10px;
    top: -1px;
}}
QTabBar::tab {{
    background-color: {BG};
    color: {TEXT_GRAY};
    padding: 8px 16px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-weight: 600;
}}
QTabBar::tab:selected {{
    background-color: {PRIMARY};
    color: {TEXT_ON_PRIMARY};
}}
QTabBar::tab:hover:!selected {{
    background-color: {PRIMARY_BG_TINT};
    color: {PRIMARY_DARK};
}}
QTabBar::close-button {{
    subcontrol-position: right;
}}

/* --- Cases a cocher --- */
QCheckBox {{
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1.5px solid {BORDER_STRONG};
    background-color: {CARD_BG};
}}
QCheckBox::indicator:checked {{
    background-color: {PRIMARY};
    border-color: {PRIMARY};
}}

/* --- Barres de defilement --- */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_STRONG};
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {PRIMARY_LIGHT};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER_STRONG};
    border-radius: 5px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {PRIMARY_LIGHT};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* --- Splitters --- */
QSplitter::handle {{
    background-color: {BORDER};
}}
QSplitter::handle:hover {{
    background-color: {PRIMARY_LIGHT};
}}

/* --- Progression --- */
QProgressDialog {{
    background-color: {CARD_BG};
}}
QProgressBar {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    background-color: {BG};
    text-align: center;
    height: 16px;
}}
QProgressBar::chunk {{
    background-color: {PRIMARY};
    border-radius: 7px;
}}

/* --- Info-bulles --- */
QToolTip {{
    background-color: {NAVY};
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 6px 10px;
}}

/* --- ComboBox --- */
QComboBox {{
    background-color: {CARD_BG};
    border: 1.5px solid {BORDER};
    border-radius: 8px;
    padding: 5px 10px;
}}
QComboBox:hover {{
    border-color: {PRIMARY};
}}
QComboBox QAbstractItemView {{
    background-color: {CARD_BG};
    border: 1px solid {BORDER};
    selection-background-color: {PRIMARY_BG_TINT};
    selection-color: {PRIMARY_DARK};
}}

/* --- Labels d'info secondaires (objectName "mutedLabel") --- */
QLabel#mutedLabel {{
    color: {TEXT_GRAY};
    font-size: 11px;
}}
"""


def apply_theme(app):
    """A appeler une seule fois, juste apres la creation de QApplication."""
    app.setStyleSheet(STYLESHEET)
