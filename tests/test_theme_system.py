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
Tests du systeme de themes multiples : registre (core/themes.py), application
a l'execution (gui/theme.py), persistance (core/settings.py) et selecteur de
menu (gui/main_window.py).
"""
import pytest


def test_theme_registry_has_all_expected_ids():
    from core.themes import THEMES, THEME_ORDER
    assert set(THEME_ORDER) == set(THEMES.keys())
    assert THEME_ORDER == ["classic", "a", "b", "c", "d", "e", "f", "g", "h"]


REQUIRED_PALETTE_KEYS = {
    "label", "bg", "surface", "surface_alt", "border", "border_strong",
    "text_primary", "text_muted", "text_on_primary",
    "accent", "accent_hover", "accent_pressed", "accent_bg_tint",
    "nav_gradient", "nav_text",
    "success", "warning", "danger", "danger_dark", "font_family",
}


def test_every_theme_has_all_required_keys():
    from core.themes import THEMES
    for theme_id, palette in THEMES.items():
        missing = REQUIRED_PALETTE_KEYS - set(palette.keys())
        assert not missing, f"Theme '{theme_id}' -- cles manquantes : {missing}"


def test_get_palette_falls_back_to_default_for_unknown_id():
    from core.themes import get_palette, DEFAULT_THEME_ID, THEMES
    assert get_palette("un_theme_qui_nexiste_pas") == THEMES[DEFAULT_THEME_ID]


def test_get_palette_returns_requested_theme():
    from core.themes import get_palette, THEMES
    assert get_palette("g") == THEMES["g"]


def test_build_stylesheet_contains_palette_colors(qapp):
    from gui.theme import build_stylesheet
    from core.themes import get_palette
    palette = get_palette("d")
    css = build_stylesheet(palette)
    assert palette["accent"] in css
    assert palette["bg"] in css
    assert palette["text_primary"] in css


def test_apply_theme_updates_live_module_attributes(qapp):
    """Verifie le point critique du refactor : les attributs de module
    (gui.theme.PRIMARY etc.) doivent bien changer apres apply_theme, pour
    que le code y accedant via 'theme.PRIMARY' (jamais 'from gui.theme
    import PRIMARY') lise toujours la valeur a jour."""
    from gui import theme
    from gui.theme import apply_theme
    from core.themes import get_palette

    apply_theme(qapp, "a")
    assert theme.PRIMARY == get_palette("a")["accent"]
    assert theme.CURRENT_THEME_ID == "a"

    apply_theme(qapp, "g")
    assert theme.PRIMARY == get_palette("g")["accent"]
    assert theme.CURRENT_THEME_ID == "g"
    # La reassignation doit bien avoir change la valeur (pas rester bloquee
    # sur l'ancien theme 'a').
    assert theme.PRIMARY != get_palette("a")["accent"]


def test_apply_theme_with_unknown_id_falls_back_to_default_without_crashing(qapp):
    from gui import theme
    from gui.theme import apply_theme
    apply_theme(qapp, "theme_inexistant")
    assert theme.CURRENT_THEME_ID == "classic"


def test_apply_theme_none_reads_persisted_setting(qapp, monkeypatch):
    from gui import theme
    from gui.theme import apply_theme
    import core.settings as settings
    monkeypatch.setattr(settings, "get_theme", lambda: "b")
    apply_theme(qapp, None)
    assert theme.CURRENT_THEME_ID == "b"


def test_settings_theme_roundtrip(tmp_path, monkeypatch):
    import core.settings as settings
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings, "CONFIG_DIR", tmp_path)
    assert settings.get_theme() == "classic"
    settings.set_theme("g")
    assert settings.get_theme() == "g"


def test_icon_color_default_reads_current_theme_live(qapp):
    """Bug potentiel evite : un defaut d'argument Python fige (color=
    TEXT_DARK au moment de la DEFINITION de la fonction) n'aurait jamais
    reflete un changement de theme a l'execution -- icon() doit lire
    theme.TEXT_DARK au moment de l'APPEL (color=None puis resolu dans le
    corps de la fonction)."""
    import inspect
    from gui.theme import icon
    sig = inspect.signature(icon)
    assert sig.parameters["color"].default is None


def test_status_colors_reflect_current_theme(qapp):
    """gui.scenario_compare_dialog : STATUS_COLORS etait un dict fige au
    niveau module (jamais mis a jour) -- doit maintenant etre une fonction
    lisant le theme actif a chaque appel."""
    from gui.scenario_compare_dialog import _status_colors
    from gui.theme import apply_theme
    from core.themes import get_palette

    apply_theme(qapp, "c")
    colors_c = _status_colors()
    assert colors_c["added"] == get_palette("c")["success"]

    apply_theme(qapp, "e")
    colors_e = _status_colors()
    assert colors_e["added"] == get_palette("e")["success"]
    assert colors_c["added"] != colors_e["added"]


def test_main_window_theme_menu_lists_all_themes(qapp):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from core.themes import THEME_ORDER

    apply_theme(qapp)
    window = MainWindow()
    assert set(window._theme_actions.keys()) == set(THEME_ORDER)
    for theme_id, action in window._theme_actions.items():
        assert action.isCheckable()


def test_main_window_default_theme_checked_on_open(qapp, monkeypatch):
    import core.settings as settings
    from gui.theme import apply_theme
    from gui.main_window import MainWindow

    monkeypatch.setattr(settings, "get_theme", lambda: "f")
    apply_theme(qapp)
    window = MainWindow()
    assert window._theme_actions["f"].isChecked()
    assert not window._theme_actions["classic"].isChecked()


def test_main_window_set_theme_updates_check_state_and_persists(qapp, monkeypatch, tmp_path):
    import core.settings as settings
    from gui import theme
    from gui.theme import apply_theme
    from gui.main_window import MainWindow

    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings, "CONFIG_DIR", tmp_path)

    apply_theme(qapp)
    window = MainWindow()
    window._set_theme("g")

    assert window._theme_actions["g"].isChecked()
    assert not window._theme_actions["classic"].isChecked()
    assert theme.CURRENT_THEME_ID == "g"
    assert settings.get_theme() == "g"
