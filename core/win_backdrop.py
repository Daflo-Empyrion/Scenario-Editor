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
Flou acrylique Windows 11 pour la fenetre principale (themes qui le
demandent -- cle optionnelle "acrylic" de core/themes.py).

Compatibilite, DEMANDE EXPLICITE de l'utilisateur :
- l'API utilisee (DwmSetWindowAttribute + DWMWA_SYSTEMBACKDROP_TYPE)
  n'existe qu'a partir de Windows 11 22H2 (build 22621) ; sur Windows 10,
  Windows 11 anterieur, macOS ou Linux, acrylic_supported() retourne False
  et enable_acrylic() n'est MEME PAS APPELEE ;
- l'appel est tout de meme encadre (try/except + code retour verifie) : un
  echec (bureau a distance, mode compatibilite, DLL absente...) laisse
  simplement la fenetre telle quelle ;
- INVARIANT DE LISIBILITE : la translucence de la fenetre n'est activee
  QU'APRES la confirmation du flou -- jamais l'inverse (une fenetre
  translucide sans flou rendrait le texte illisible). Sur les systemes sans
  support, le theme reste entierement peint par sa feuille de style, sans
  aucune difference de mise en page.
"""
import ctypes
import ctypes.wintypes
import os
import sys

# DWMWA_SYSTEMBACKDROP_TYPE (documente a partir de Win11 22H2)
_DWMWA_SYSTEMBACKDROP_TYPE = 38
# Materiaux systeme (valeurs DWMWA_SYSTEMBACKDROP_TYPE) :
#   2 = DWMSBT_MAINWINDOW  -> Mica (discret, teinte par le fond d'ecran)
#   3 = DWMSBT_ACRYLIC     -> flou acrylique prononce (verre depoli)
_DWMSBT_MAINWINDOW = 2
_DWMSBT_ACRYLIC = 3
_BACKDROP_CONSTANTS = {"mica": _DWMSBT_MAINWINDOW, "acrylic": _DWMSBT_ACRYLIC}

_WIN11_22H2_BUILD = 22621


def acrylic_supported() -> bool:
    """True uniquement sur Windows >= 11 22H2 (build 22621). Aucun appel
    systeme : simple lecture de la version, utilisable avant creation de
    fenetre (pour la feuille de style comme pour le branchement).
    La plateforme Qt "offscreen" (tests/CI) n'a ni DWM ni HWND reel :
    toujours False, sinon DwmSetWindowAttribute sur un faux HWND crashe."""
    if sys.platform != "win32":
        return False
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        return False
    try:
        return sys.getwindowsversion().build >= _WIN11_22H2_BUILD
    except (AttributeError, ValueError):
        return False


class _MARGINS(ctypes.Structure):
    _fields_ = [("cxLeftWidth", ctypes.c_int), ("cxRightWidth", ctypes.c_int),
                ("cyTopHeight", ctypes.c_int), ("cyBottomHeight", ctypes.c_int)]


def enable_backdrop(widget, kind: str = "acrylic") -> bool:
    """Active un materiau de fond Windows 11 DERRIERE la fenetre `widget`
    ("mica" ou "acrylic"). Retourne True si (et seulement si) le systeme a
    confirme l'application -- l'appelant ne doit activer la moindre
    translucence QUE sur cette valeur.

    GUI-002 (corrige le 07/09/2026) : poser DWMWA_SYSTEMBACKDROP_TYPE seul
    ne produit AUCUN effet visible (fond opaque, verifie par capture d'ecran
    cote a cote) -- DWM ne peint le materiau que dans le cadre ETENDU dans
    la zone cliente. La recette complete est donc : attribut backdrop PUIS
    DwmExtendFrameIntoClientArea(-1, -1, -1, -1). Les deux codes retour
    doivent etre S_OK, sinon on declare l'echec (invariant : jamais
    translucide sans materiau)."""
    constant = _BACKDROP_CONSTANTS.get(kind)
    if constant is None:
        return False
    if not acrylic_supported():
        return False
    try:
        hwnd = int(widget.winId())
        backdrop = ctypes.c_int(constant)
        result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, _DWMWA_SYSTEMBACKDROP_TYPE,
            ctypes.byref(backdrop), ctypes.sizeof(backdrop))
        if result != 0:
            return False
        margins = _MARGINS(-1, -1, -1, -1)
        result = ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(
            hwnd, ctypes.byref(margins))
        return result == 0  # S_OK
    except (OSError, AttributeError, ValueError):
        return False


def enable_acrylic(widget) -> bool:
    """Active le flou acrylique DERRIERE la fenetre `widget` (theme
    Verriere). Wrapper historique de enable_backdrop(widget, "acrylic")."""
    return enable_backdrop(widget, "acrylic")
