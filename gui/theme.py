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

"""
Theme visuel de l'application -- systeme multi-themes selectionnable (voir
core/themes.py pour le registre des palettes). Un seul point d'entree :
apply_theme(app, theme_id=None).

Historique : theme unique a l'origine (palette 'classic' ci-dessous, un
tableau de bord admin bleu/marine), etendu en systeme multi-themes suite a
une demande utilisateur de plusieurs propositions visuelles (maquettes A a
G, voir core/themes.py). 'classic' reste le theme par defaut pour ne rien
changer visuellement tant que l'utilisateur n'a pas choisi explicitement un
autre theme dans Options > Theme.

LIMITE ASSUMEE : PyQt6 Widgets ne supporte pas le vrai flou d'arriere-plan
(backdrop-filter) des maquettes HTML d'origine -- necessiterait soit l'API
Acrylic/Mica propre a Windows 11, soit une reecriture en Qt Quick/QML.
L'approximation ici reste fidele en couleurs/degrades/coins arrondis mais
sans le flou litteral.

IMPORTANT (evite un piege de staleness Python) : les constantes de module
ci-dessous (PRIMARY, TEXT_DARK, etc.) sont REASSIGNEES a chaque appel de
apply_theme() -- tout code qui les utilise doit donc y acceder via
'from gui import theme' puis 'theme.PRIMARY' (acces d'attribut, toujours a
jour), JAMAIS via 'from gui.theme import PRIMARY' (copie figee a l'import,
ne reverra plus les changements de theme a l'execution).
"""
from PyQt6.QtGui import QIcon, QFont, QFontDatabase
from PyQt6.QtCore import QSize

from core.themes import get_palette, DEFAULT_THEME_ID

try:
    import qtawesome as qta
    _HAS_QTA = True
except ImportError:
    _HAS_QTA = False


# ------------------------------------------------------------------
# Palette active -- reassignee par apply_theme() a chaque changement de
# theme. Valeurs de depart = palette 'classic', pour que tout code appele
# avant le tout premier apply_theme() (ne devrait pas arriver en usage
# normal) ait quand meme des couleurs valides plutot qu'un crash.
# ------------------------------------------------------------------
_INITIAL = get_palette(DEFAULT_THEME_ID)

PRIMARY = _INITIAL["accent"]
PRIMARY_DARK = _INITIAL["accent_hover"]
PRIMARY_DARKER = _INITIAL["accent_pressed"]
PRIMARY_LIGHT = _INITIAL["accent_hover"]
PRIMARY_BG_TINT = _INITIAL["accent_bg_tint"]

NAVY = _INITIAL["nav_gradient"]
NAVY_LIGHT = _INITIAL["surface_alt"]

BG = _INITIAL["bg"]
CARD_BG = _INITIAL["surface"]
BORDER = _INITIAL["border"]
BORDER_STRONG = _INITIAL["border_strong"]

TEXT_DARK = _INITIAL["text_primary"]
TEXT_GRAY = _INITIAL["text_muted"]
TEXT_ON_PRIMARY = _INITIAL["text_on_primary"]

GREEN = _INITIAL["success"]
ORANGE = _INITIAL["warning"]
RED = _INITIAL["danger"]
RED_DARK = _INITIAL["danger_dark"]

FONT_FAMILY = _INITIAL["font_family"]

CURRENT_THEME_ID = DEFAULT_THEME_ID


# ------------------------------------------------------------------
# Icones (qtawesome si disponible -- degrade proprement sinon : QIcon() vide,
# les boutons gardent alors juste leur texte, rien ne casse).
# ------------------------------------------------------------------
def icon(name: str, color: str = None, size: int = 16) -> QIcon:
    """color=None (par defaut) lit TEXT_DARK au moment de l'APPEL, pas a la
    definition de la fonction -- un defaut d'argument fige en Python
    n'aurait capture qu'une seule fois la couleur du tout premier theme
    charge, jamais mise a jour lors d'un changement de theme a l'execution."""
    if color is None:
        color = TEXT_DARK
    if not _HAS_QTA:
        return QIcon()
    try:
        return qta.icon(name, color=color)
    except Exception:
        return QIcon()


def icon_size() -> QSize:
    return QSize(15, 15)


# ------------------------------------------------------------------
# Feuille de style Qt (QSS) -- construite a partir d'une palette (voir
# core/themes.py). Les noms de variables gardent leur forme historique
# (PRIMARY, NAVY, BG...) par souci de continuite avec le reste du code.
# ------------------------------------------------------------------
def build_stylesheet(palette: dict) -> str:
    PRIMARY = palette["accent"]
    PRIMARY_DARK = palette["accent_hover"]
    PRIMARY_DARKER = palette["accent_pressed"]
    PRIMARY_LIGHT = palette["accent_hover"]
    PRIMARY_BG_TINT = palette["accent_bg_tint"]
    NAVY = palette["nav_gradient"]
    BG = palette["bg"]
    CARD_BG = palette["surface"]
    BORDER = palette["border"]
    BORDER_STRONG = palette["border_strong"]
    TEXT_DARK = palette["text_primary"]
    TEXT_GRAY = palette["text_muted"]
    TEXT_ON_PRIMARY = palette["text_on_primary"]
    NAV_TEXT = palette["nav_text"]
    FONT_FAMILY = palette["font_family"]

    base = f"""
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
    background: {NAVY};
    color: {NAV_TEXT};
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
    color: {TEXT_ON_PRIMARY};
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
    background: {NAVY};
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

/* --- Boutons radio (meme traitement : sans regle dediee, l'indicateur
       natif est quasi invisible sur les themes sombres -- retour utilisateur
       du 30/08/2026 sur le dialogue de session du protocole) --- */
QRadioButton {{
    spacing: 8px;
}}
QRadioButton::indicator {{
    width: 14px;
    height: 14px;
    border-radius: 7px;
    border: 1.5px solid {BORDER_STRONG};
    background-color: {CARD_BG};
}}
QRadioButton::indicator:checked {{
    background-color: {PRIMARY};
    border-color: {PRIMARY};
}}
QRadioButton:checked {{
    color: {PRIMARY};
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
    background: {NAVY};
    color: {NAV_TEXT};
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
    # Themes a identite renforcee (ex: "h" -- Verriere) ajoutent leur QSS
    # specifique (verre/gloss/biseaux) EN FIN de feuille : a specificite
    # egale, ces regles gagnent sur la generale, sans affecter les autres
    # themes (cle optionnelle absente -> chaine vide).
    return base + palette.get("extra_qss", "")


def apply_theme(app, theme_id: str = None):
    """A appeler une premiere fois juste apres la creation de QApplication,
    puis a nouveau a chaque changement de theme choisi par l'utilisateur
    (voir MainWindow._set_theme). theme_id=None relit le theme persiste
    (voir core.settings.get_theme), ou 'classic' par defaut."""
    global PRIMARY, PRIMARY_DARK, PRIMARY_DARKER, PRIMARY_LIGHT, PRIMARY_BG_TINT
    global NAVY, NAVY_LIGHT, BG, CARD_BG, BORDER, BORDER_STRONG
    global TEXT_DARK, TEXT_GRAY, TEXT_ON_PRIMARY, GREEN, ORANGE, RED, RED_DARK
    global FONT_FAMILY, CURRENT_THEME_ID

    if theme_id is None:
        from core.settings import get_theme
        theme_id = get_theme()

    palette = get_palette(theme_id)
    CURRENT_THEME_ID = theme_id if theme_id in _known_theme_ids() else DEFAULT_THEME_ID

    PRIMARY = palette["accent"]
    PRIMARY_DARK = palette["accent_hover"]
    PRIMARY_DARKER = palette["accent_pressed"]
    PRIMARY_LIGHT = palette["accent_hover"]
    PRIMARY_BG_TINT = palette["accent_bg_tint"]
    NAVY = palette["nav_gradient"]
    NAVY_LIGHT = palette["surface_alt"]
    BG = palette["bg"]
    CARD_BG = palette["surface"]
    BORDER = palette["border"]
    BORDER_STRONG = palette["border_strong"]
    TEXT_DARK = palette["text_primary"]
    TEXT_GRAY = palette["text_muted"]
    TEXT_ON_PRIMARY = palette["text_on_primary"]
    GREEN = palette["success"]
    ORANGE = palette["warning"]
    RED = palette["danger"]
    RED_DARK = palette["danger_dark"]
    FONT_FAMILY = palette["font_family"]

    app.setStyleSheet(build_stylesheet(palette))


def _known_theme_ids():
    from core.themes import THEMES
    return THEMES.keys()
