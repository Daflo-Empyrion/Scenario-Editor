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
Registre des palettes de themes selectionnables (voir gui/theme.py pour la
construction de la feuille de style Qt a partir d'une palette).

Chaque palette est une approximation fidele en couleurs/degrades des
maquettes HTML validees avec l'utilisateur (A a G), MAIS sans le vrai flou
d'arriere-plan (backdrop-filter) des maquettes web -- PyQt6 Widgets ne le
supporte pas nativement (necessiterait soit l'API Acrylic/Mica propre a
Windows 11, soit une reecriture en Qt Quick/QML). L'esprit visuel (couleurs,
degrades, coins arrondis, bordures lumineuses) reste fidele.

'classic' est la palette d'origine de l'application (tableau de bord admin
bleu/marine) -- reste le theme par defaut pour ne rien changer visuellement
tant que l'utilisateur n'a pas choisi explicitement un autre theme.

Cles obligatoires de chaque palette (voir gui/theme.py:build_stylesheet) :
  bg, surface, surface_alt, border, border_strong,
  text_primary, text_muted, text_on_primary,
  accent, accent_hover, accent_pressed, accent_bg_tint,
  nav_gradient (fragment QSS qlineargradient/qradialgradient/qconicalgradient
                pour QMenuBar/QToolBar), nav_text,
  success, warning, danger, danger_dark, font_family, label (nom affiche)
"""
from typing import Dict

THEMES: Dict[str, dict] = {
    "classic": {
        "label": "Classique",
        "bg": "#eef1f6", "surface": "#ffffff", "surface_alt": "#eaf0fe",
        "border": "#e2e6f0", "border_strong": "#c9d0e0",
        "text_primary": "#1a1f36", "text_muted": "#7c859c", "text_on_primary": "#ffffff",
        "accent": "#4a7dfc", "accent_hover": "#3a63d8", "accent_pressed": "#2f52b8",
        "accent_bg_tint": "#eaf0fe",
        "nav_gradient": "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                         "stop:0 #131a2e, stop:1 #1c2440)",
        "nav_text": "#ffffff",
        "success": "#22c55e", "warning": "#f5a623", "danger": "#ef4444", "danger_dark": "#dc2626",
        "font_family": "Segoe UI",
    },
    "a": {
        "label": "A — Console de bord",
        "bg": "#0A0D12", "surface": "#12161D", "surface_alt": "#1A2029",
        "border": "#262E3A", "border_strong": "#354055",
        "text_primary": "#E7ECF2", "text_muted": "#8792A3", "text_on_primary": "#0A0D12",
        "accent": "#3CC2D1", "accent_hover": "#4FD8E8", "accent_pressed": "#2AA8B6",
        "accent_bg_tint": "#1D4E56",
        "nav_gradient": "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                         "stop:0 #0A0D12, stop:1 #141B22)",
        "nav_text": "#E7ECF2",
        "success": "#5FD98A", "warning": "#F5A623", "danger": "#E8555A", "danger_dark": "#C23B40",
        "font_family": "Segoe UI",
    },
    "b": {
        "label": "B — Table à dessin",
        "bg": "#EDF1F5", "surface": "#FFFFFF", "surface_alt": "#F5F8FA",
        "border": "#D3DCE4", "border_strong": "#B7C3CF",
        "text_primary": "#1C2733", "text_muted": "#5C6B7A", "text_on_primary": "#FFFFFF",
        "accent": "#2F6FB0", "accent_hover": "#255C93", "accent_pressed": "#1D4A78",
        "accent_bg_tint": "#E4EEF7",
        "nav_gradient": "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                         "stop:0 #FFFFFF, stop:1 #F5F8FA)",
        "nav_text": "#1C2733",
        "success": "#3C8C5D", "warning": "#B8791A", "danger": "#C1443B", "danger_dark": "#9C332A",
        "font_family": "Segoe UI",
    },
    "c": {
        "label": "C — Terminal d'ingénierie",
        "bg": "#171310", "surface": "#201A15", "surface_alt": "#2A231C",
        "border": "#3A322A", "border_strong": "#4C4133",
        "text_primary": "#EDE6DC", "text_muted": "#A89A88", "text_on_primary": "#171310",
        "accent": "#E8892E", "accent_hover": "#F09B47", "accent_pressed": "#B8681A",
        "accent_bg_tint": "#4A2E12",
        "nav_gradient": "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                         "stop:0 #171310, stop:1 #201A15)",
        "nav_text": "#EDE6DC",
        "success": "#4FB89C", "warning": "#E8892E", "danger": "#DB6157", "danger_dark": "#B34E45",
        "font_family": "Segoe UI",
    },
    "d": {
        "label": "D — Cristal nocturne",
        "bg": "#0E0C18", "surface": "#171426", "surface_alt": "#1E1A2E",
        "border": "#332E48", "border_strong": "#453F5E",
        "text_primary": "#F1F4FA", "text_muted": "#A9AEC4", "text_on_primary": "#0E0C18",
        "accent": "#7E68FF", "accent_hover": "#9484FF", "accent_pressed": "#5A48C2",
        "accent_bg_tint": "#241F42",
        "nav_gradient": "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                         "stop:0 #120F1E, stop:0.5 #1A1530, stop:1 #12141E)",
        "nav_text": "#F1F4FA",
        "success": "#46DCA0", "warning": "#FFAF50", "danger": "#E8555A", "danger_dark": "#C23B40",
        "font_family": "Segoe UI",
    },
    "e": {
        "label": "E — Cristal solaire",
        "bg": "#EEF2FF", "surface": "#FFFFFF", "surface_alt": "#F5F8FF",
        "border": "#D8DEF5", "border_strong": "#BFC8ED",
        "text_primary": "#1B2440", "text_muted": "#5B6690", "text_on_primary": "#FFFFFF",
        "accent": "#6E78FF", "accent_hover": "#828BFF", "accent_pressed": "#4750C9",
        "accent_bg_tint": "#E8EAFF",
        "nav_gradient": "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                         "stop:0 #FFFFFF, stop:1 #F1F3FF)",
        "nav_text": "#1B2440",
        "success": "#0D8A5E", "warning": "#B5720A", "danger": "#B23A32", "danger_dark": "#8E2D26",
        "font_family": "Segoe UI",
    },
    "f": {
        "label": "F — Crépuscule",
        "bg": "#1B2030", "surface": "#232838", "surface_alt": "#262C3E",
        "border": "#333A4E", "border_strong": "#454D66",
        "text_primary": "#ECEAE5", "text_muted": "#A6A79E", "text_on_primary": "#12141C",
        "accent": "#7C83FF", "accent_hover": "#9299FF", "accent_pressed": "#545CC9",
        "accent_bg_tint": "#282C4A",
        "nav_gradient": "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                         "stop:0 #181D2A, stop:1 #1F2434)",
        "nav_text": "#ECEAE5",
        "success": "#4FC7C0", "warning": "#F0AD5C", "danger": "#E8746B", "danger_dark": "#C25A52",
        "font_family": "Segoe UI",
    },
    "g": {
        "label": "G — Nacre",
        "bg": "#F3F0FF", "surface": "#FFFFFF", "surface_alt": "#F7F4FF",
        "border": "#E2D9F7", "border_strong": "#CBBBEF",
        "text_primary": "#1B2440", "text_muted": "#5B6690", "text_on_primary": "#FFFFFF",
        "accent": "#8A5FE0", "accent_hover": "#9E77E8", "accent_pressed": "#6A41B8",
        "accent_bg_tint": "#EFE7FF",
        "nav_gradient": "qconicalgradient(cx:0.15, cy:0.15, angle:200, "
                         "stop:0 #F7CCE8, stop:0.25 #C9C6FF, stop:0.5 #B7ECEC, "
                         "stop:0.75 #FBE3B8, stop:1 #F7CCE8)",
        "nav_text": "#1B2440",
        "success": "#0D8A5E", "warning": "#B5720A", "danger": "#B23A32", "danger_dark": "#8E2D26",
        "font_family": "Segoe UI",
    },
}

THEME_ORDER = ["classic", "a", "b", "c", "d", "e", "f", "g"]
DEFAULT_THEME_ID = "classic"


def get_palette(theme_id: str) -> dict:
    """Retourne la palette pour theme_id, ou celle du theme par defaut si
    l'id est inconnu (ex: settings.json corrompu ou theme retire d'une
    version future) -- ne leve jamais d'exception, l'appli doit toujours
    pouvoir demarrer avec un theme valide."""
    return THEMES.get(theme_id, THEMES[DEFAULT_THEME_ID])
