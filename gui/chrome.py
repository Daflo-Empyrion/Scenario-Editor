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

"""Chrome de fenetre style webapp (demande du 31/10, suite du chantier
socle design apres l'ecran arbre technologique en HTML) :

  - fenetre SANS barre de titre Windows (FramelessWindowHint) ;
  - barre maison : logo, nom de l'appli, fil d'Ariane du projet ouvert,
    boutons reduire/agrandir/fermer (qframelesswindow.TitleBar, deja
    installe comme dependance de PyQt-Fluent-Widgets) ;
  - ombre DWM, animation, redimensionnement par les bords (WM_NCHITTEST)
    et suppression du cadre natif (WM_NCCALCSIZE) -- logique reprise de
    qframelesswindow.WindowsFramelessWindow (GPL v3, meme licence que le
    projet) car FramelessWindow herite de QWidget alors que MainWindow est
    un QMainWindow (menus, barre d'etat, central widget) : la logique est
    appliquee PAR COMPOSITION (handle_native_event/on_chrome_resize appeles
    depuis MainWindow), pas par heritage.

REVERSIBILITE (meme motif que fluent_pilot) :
  - reglage persistant titlebar_custom_enabled (Options > Interface,
    pris en compte au PROCHAIN lancement) ;
  - DEGRADE GRACIEUX : si qframelesswindow manque, ou plateforme non
    Windows, install() retourne False et la fenetre garde sa barre native
    -- aucune difference fonctionnelle.

Particularite setMenuWidget : la barre de titre est posee AU-DESSUS de la
barre de menus en remplacant le widget d'entete de QMainWindow par un
conteneur vertical (titre custom + QMenuBar existant) -- QMainWindow.
menuBar() reste fonctionnel (menus, raccourcis, retranslation).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Tuple

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

try:
    from qframelesswindow import TitleBar
    from qframelesswindow.utils import win32_utils as _win_utils
    from qframelesswindow.utils.win32_utils import Taskbar
    from qframelesswindow.windows.window_effect import WindowsWindowEffect
    from qframelesswindow.windows.c_structures import LPNCCALCSIZE_PARAMS
    import win32api
    import win32con
    import win32gui
    from ctypes import cast
    from ctypes.wintypes import LPRECT, MSG
    _FRAMELESS_OK = True
except Exception:
    _FRAMELESS_OK = False

_FRAMELESS_NATIVE = _FRAMELESS_OK and sys.platform == "win32"

_BORDER_WIDTH = 5
_APP_NAME = "Empyrion Scenario Editor"


def is_available() -> bool:
    """Chrome custom possible : qframelesswindow importable ET Windows
    (ombre DWM et redimensionnement natif sont specifiques Windows ; le
    projet cible Windows -- on reste conservateur)."""
    return _FRAMELESS_NATIVE


def _logo_pixmap() -> Optional[QPixmap]:
    """Icone de l'appli (meme .ico que l'exe, voir main()) si trouvable."""
    if getattr(sys, "frozen", False):
        p = Path(sys._MEIPASS) / "assets" / "icon.ico"
    else:
        p = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"
    if p.is_file():
        icon = QIcon(str(p))
        if not icon.isNull():
            return icon.pixmap(QSize(18, 18))
    return None


if _FRAMELESS_OK:

    class AppTitleBar(TitleBar):
        """Barre maison : logo + nom + projet a gauche, boutons fenetre a
        droite (herites). Le glisser, le double-clic maximiser et les
        Aero-snaps viennent de TitleBarBase."""

        def __init__(self, parent):
            super().__init__(parent)
            self.setFixedHeight(46)
            self.setObjectName("appTitleBar")
            # OBLIGATOIRE pour qu'un sous-classe de QWidget peigne son fond
            # QSS (sinon la barre reste transparente et se confond avec la
            # barre native — vecu 01/11)
            self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            self._project_label = QLabel("")
            self._project_label.setObjectName("chromeProject")

            pm = _logo_pixmap()
            logo = QLabel()
            if pm is not None:
                logo.setPixmap(pm)
                logo.setFixedSize(20, 20)
                logo.setScaledContents(True)
            title = QLabel(_APP_NAME)
            title.setObjectName("chromeTitle")

            lay = self.hBoxLayout
            lay.insertSpacing(0, 14)
            if pm is not None:
                lay.insertWidget(1, logo, 0, Qt.AlignmentFlag.AlignVCenter)
                lay.insertSpacing(2, 9)
            lay.insertWidget(3, title, 0, Qt.AlignmentFlag.AlignVCenter)
            lay.insertSpacing(4, 12)
            lay.insertWidget(5, self._project_label, 0,
                             Qt.AlignmentFlag.AlignVCenter)
            lay.insertStretch(6, 1)
            self.apply_chrome_style()

        def apply_chrome_style(self):
            """Habillage verre de la maquette (degrade bleu nuit, filet cyan,
            projet en pastille) aux couleurs du theme courant -- rejoue a
            chaque changement de theme via set_project (appele par
            _refresh_panel_and_status_labels)."""
            from gui import theme as _theme
            dark = getattr(_theme, "BG", "#05070D")
            surface = getattr(_theme, "SURFACE_ALT", "#1B2337")
            accent = getattr(_theme, "PRIMARY", "#00E5FF")
            text = getattr(_theme, "TEXT_DARK", "#E9F2FA")
            muted = getattr(_theme, "TEXT_GRAY", "#8FA3B8")
            self.setStyleSheet(f"""
                QWidget#appTitleBar {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 rgba(0, 229, 255, 0.14), stop:0.25 {surface},
                        stop:0.6 {dark}, stop:1 {surface});
                    border-bottom: 2px solid rgba(0, 229, 255, 0.55);
                }}
                QLabel#chromeTitle {{
                    color: {text}; font-size: 13px; font-weight: 600;
                    letter-spacing: 0.6px;
                }}
                QLabel#chromeProject {{
                    color: {accent}; font-size: 11.5px; font-weight: 600;
                    background: rgba(0, 229, 255, 0.10);
                    border: 1px solid rgba(0, 229, 255, 0.30);
                    border-radius: 9px; padding: 3px 12px;
                }}
                QLabel#chromeProject:empty {{
                    background: transparent; border: none; padding: 0;
                }}
                QToolButton, QPushButton {{
                    background: transparent; color: {muted};
                    border: none; border-radius: 6px;
                }}
                QToolButton:hover, QPushButton:hover {{
                    background: rgba(0, 229, 255, 0.14); color: {text};
                }}
            """)

        def set_project(self, name: str) -> None:
            """Fil d'Ariane : nom du dossier du scenario ouvert ('' = aucun).
            Rejoue aussi l'habillage (le theme a pu changer)."""
            self._project_label.setText(name or "")
            self._project_label.setVisible(bool(name))
            self.apply_chrome_style()

else:  # dependance absente : stub jamais instancie (install() refuse)

    class AppTitleBar:  # noqa: D101
        pass


class NavRail(QWidget):
    """Rail de navigation vertical facon webapp (demande du 31/10) : une
    colonne d'icônes a gauche du contenu, lancant les ecrans les plus
    utilises (memes handlers que le menu Outils). Re-styled a chaque
    changement de theme via restyle()."""

    # (icone qtawesome, cle i18n du libelle, nom de methode MainWindow)
    ITEMS = [
        ("fa5s.sitemap", "menu.tools.tech_tree", "_open_tech_tree_dialog"),
        ("fa5s.globe", "menu.tools.galaxy_viewer", "_open_galaxy_viewer"),
        ("fa5s.search", "menu.file.search_scenario", "_open_search_dialog"),
        ("fa5s.scroll", "menu.tools.pda_mission", "_open_pda_mission_dialog"),
        ("fa5s.coins", "menu.tools.economy", "_open_economy_editor"),
        ("fa5s.check-double", "menu.tools.coherence", "_open_coherence_dialog"),
        ("fa5s.tachometer-alt", "menu.tools.dashboard", "_open_dashboard"),
        ("fa5s.rocket", "menu.tools.yaml_check", "_open_yaml_check"),
    ]
    WIDTH = 56

    def __init__(self, main_window):
        super().__init__(main_window)
        self.setObjectName("navRail")
        self.setFixedWidth(self.WIDTH)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 10, 6, 10)
        lay.setSpacing(6)
        self._buttons = []
        try:
            import qtawesome as qta
            has_qta = True
        except ImportError:
            has_qta = False
        for icon_name, label_key, method_name in self.ITEMS:
            from PyQt6.QtWidgets import QPushButton
            btn = QPushButton()
            if has_qta:
                btn.setIcon(qta.icon(icon_name, color="#8FA3B8"))
            btn.setFixedSize(44, 40)
            btn.setToolTip(t(label_key))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(getattr(main_window, method_name))
            lay.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)
            self._buttons.append((btn, icon_name))
        lay.addStretch(1)
        self.apply_rail_style()

    def apply_rail_style(self):
        """Style aux couleurs du theme courant (re-joue au changement)."""
        from gui import theme as _theme
        surface = getattr(_theme, "SURFACE_ALT", "#1B2337")
        dark = getattr(_theme, "BG", "#05070D")
        self.setStyleSheet(f"""
            QWidget#navRail {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {surface}, stop:1 {dark});
                border-right: 1px solid rgba(0, 229, 255, 0.25);
            }}
            QPushButton {{
                background: transparent; border: 1px solid transparent;
                border-radius: 9px;
            }}
            QPushButton:hover {{
                background: rgba(0, 229, 255, 0.12);
                border: 1px solid rgba(0, 229, 255, 0.35);
            }}
            QPushButton:pressed {{ background: rgba(0, 229, 255, 0.22); }}
        """)
        # les icônes QImage ne suivent pas le QSS : couleur fixe (#8FA3B8),
        # le halo du bouton fait l'etat actif.

from core.i18n import t  # noqa: E402  (utilise par NavRail, apres _FRAMELESS_OK)


class _ChromeState:
    """Etat du chrome pose sur une fenetre (absent si non installe)."""
    title_bar = None
    window_effect = None
    resize_enabled = True
    nav_rail = None


def install(win) -> bool:
    """Passe la fenetre en sans-cadre avec barre maison. Retourne True si
    installe ; False = garder la barre native (reglage desactive, plateforme
    non supportee, dependance absente). Appeler APRES la construction des
    menus (setMenuWidget enveloppe la QMenuBar existante)."""
    if not is_available():
        return False
    from core import settings
    if not settings.get_titlebar_custom_enabled():
        return False

    state = _ChromeState()
    try:
        import sys as _sys
        # INSTABILE 02/11 : sur Windows reel, la sequence frameless + DWM +
        # TitleBar (filtre d'evenements natifs du vendor) provoquait un abort
        # silencieux au demarrage (0xC000040D, aucune trace) — desactive par
        # defaut dans core/settings (titlebar_custom_enabled=False) ;
        # a retenter plus tard avec la base FramelessWindow du vendor.
        win.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        state.window_effect = WindowsWindowEffect(win)
        try:
            state.window_effect.addShadowEffect(win.winId())
        except Exception:
            pass

        state.title_bar = AppTitleBar(win)
        # Barre posee EN SURPARTIE au-dessus de la fenetre (meme motif que
        # FramelessWindow du vendor : enfant + raise_, jamais dans un layout).
        # PIEGE vecu 31/10 : passer par setMenuWidget(conteneur) faisait
        # supprimer l'ancienne QMenuBar par Qt via deleteLater -- des qu'une
        # boucle d'evenements pompait (dialog_policy), la QMenuBar et TOUTES
        # ses QMenu mouraient en pleine suite de tests. Ici la QMenuBar reste
        # le menu widget natif de QMainWindow, jamais remplacee ; la barre
        # custom vit au-dessus grace a la marge haute du contenu.
        state.title_bar.raise_()
        # Rail de navigation vertical a gauche du contenu : le central
        # widget existant est enveloppe dans un HBox [rail | contenu].
        try:
            central = win.centralWidget()
            if central is not None:
                from PyQt6.QtWidgets import QHBoxLayout
                rail = NavRail(win)
                box = QWidget(win)
                h = QHBoxLayout(box)
                h.setContentsMargins(0, 0, 0, 0)
                h.setSpacing(0)
                h.addWidget(rail)
                h.addWidget(central)
                win.setCentralWidget(box)
                state.nav_rail = rail
        except Exception:
            pass  # le rail est un confort : jamais bloquant

        win._chrome_state = state
        on_chrome_resize(win)
        _set_top_margin(win)
    except Exception:
        return False
    return True


def restyle(win) -> None:
    """Re-applique les styles du chrome (barre + rail) apres un changement
    de theme -- appele par MainWindow._refresh_panel_and_status_labels."""
    state = getattr(win, "_chrome_state", None)
    if state is None:
        return
    bar = _live_title_bar(win)
    if bar is not None:
        try:
            bar.apply_chrome_style()
        except RuntimeError:
            pass
    if state.nav_rail is not None:
        try:
            state.nav_rail.apply_rail_style()
        except RuntimeError:
            pass


def _set_top_margin(win) -> None:
    """Reserve la hauteur de la barre custom au-dessus du contenu (menus,
    central widget) via les marges du QMainWindow."""
    state = getattr(win, "_chrome_state", None)
    if state is None or state.title_bar is None:
        return
    margins = win.contentsMargins()
    if margins.top() != state.title_bar.height():
        win.setContentsMargins(0, state.title_bar.height(), 0, 0)


def _live_title_bar(win):
    """Barre vivante ou None : une fenetre FERMEE reste referencee quelque
    part (pile undo, tests) mais son QLabel C++ est deja detruit -- tout
    acces leve RuntimeError (vecu en suite complete 31/10)."""
    state = getattr(win, "_chrome_state", None)
    bar = state.title_bar if state is not None else None
    if bar is None:
        return None
    from PyQt6 import sip
    try:
        if sip.isdeleted(bar):
            return None
    except RuntimeError:
        return None
    return bar


def set_project(win, name: str) -> None:
    """Met a jour le fil d'Ariane du projet (sans effet si non installe)."""
    bar = _live_title_bar(win)
    if bar is not None:
        try:
            bar.set_project(name)
        except RuntimeError:
            pass


def on_chrome_resize(win) -> None:
    """Appele depuis MainWindow.resizeEvent : la barre suit la largeur et
    reste en surpartie au-dessus des menus."""
    bar = _live_title_bar(win)
    if bar is not None:
        try:
            bar.setGeometry(0, 0, win.width(), bar.height())
            bar.raise_()
        except RuntimeError:
            pass


def handle_native_event(win, event_type, message) -> Optional[Tuple[bool, int]]:
    """Traite WM_NCHITTEST (bords de redimensionnement) et WM_NCCALCSIZE
    (suppression du cadre natif) -- LOGIQUE REPRISE de
    qframelesswindow.WindowsFramelessWindow.nativeEvent (GPL v3). Retourne
    None si le message ne nous concerne pas (MainWindow chainera super()) --
    y compris quand un message brouillon arrive avant l'installation."""
    state = getattr(win, "_chrome_state", None)
    if state is None:
        return None
    msg = MSG.from_address(int(message))
    if not msg.hWnd:
        return None

    if msg.message == win32con.WM_NCHITTEST and state.resize_enabled:
        x_pos, y_pos = win32gui.ScreenToClient(msg.hWnd,
                                               win32api.GetCursorPos())
        client_rect = win32gui.GetClientRect(msg.hWnd)
        w = client_rect[2] - client_rect[0]
        h = client_rect[3] - client_rect[1]
        # issue zhiyiYo #98 : pas de bords actifs en maximalise/plein ecran
        bw = 0 if _win_utils.isMaximized(msg.hWnd) or \
            _win_utils.isFullScreen(msg.hWnd) else _BORDER_WIDTH
        lx = x_pos < bw
        rx = x_pos > w - bw
        ty = y_pos < bw
        by = y_pos > h - bw
        if lx and ty:
            return True, win32con.HTTOPLEFT
        if rx and by:
            return True, win32con.HTBOTTOMRIGHT
        if rx and ty:
            return True, win32con.HTTOPRIGHT
        if lx and by:
            return True, win32con.HTBOTTOMLEFT
        if ty:
            return True, win32con.HTTOP
        if by:
            return True, win32con.HTBOTTOM
        if lx:
            return True, win32con.HTLEFT
        if rx:
            return True, win32con.HTRIGHT
        return False, 0

    if msg.message == win32con.WM_NCCALCSIZE:
        if msg.wParam:
            rect = cast(msg.lParam, LPNCCALCSIZE_PARAMS).contents.rgrc[0]
        else:
            rect = cast(msg.lParam, LPRECT).contents
        is_max = _win_utils.isMaximized(msg.hWnd)
        is_full = _win_utils.isFullScreen(msg.hWnd)
        if is_max and not is_full:
            rect.top += _win_utils.getResizeBorderThickness(msg.hWnd, False)
            rect.bottom -= _win_utils.getResizeBorderThickness(msg.hWnd, False)
            rect.left += _win_utils.getResizeBorderThickness(msg.hWnd, True)
            rect.right -= _win_utils.getResizeBorderThickness(msg.hWnd, True)
        if (is_max or is_full) and Taskbar.isAutoHide():
            position = Taskbar.getPosition(msg.hWnd)
            if position == Taskbar.LEFT:
                rect.top += Taskbar.AUTO_HIDE_THICKNESS
            elif position == Taskbar.BOTTOM:
                rect.bottom -= Taskbar.AUTO_HIDE_THICKNESS
            elif position == Taskbar.LEFT:
                rect.left += Taskbar.AUTO_HIDE_THICKNESS
            elif position == Taskbar.RIGHT:
                rect.right -= Taskbar.AUTO_HIDE_THICKNESS
        result = 0 if not msg.wParam else win32con.WVR_REDRAW
        return True, result

    return None
