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

"""Look Relief phase 2 (12/09/2026) : theme clair "l", pack de glyphes SVG
maison (gui/relief_glyphs), utilitaires d'ombre flottante (gui/relief_effects),
animations de pression (gui/press_feedback)."""

import pytest

from core.themes import THEMES, THEME_ORDER
from gui import relief_effects, relief_glyphs, press_feedback
import gui.theme as gui_theme

REQUIRED_KEYS = ("bg", "surface", "surface_alt", "border", "border_strong",
                 "text_primary", "text_muted", "text_on_primary", "accent",
                 "accent_hover", "accent_pressed", "accent_bg_tint",
                 "nav_gradient", "nav_text", "success", "warning", "danger",
                 "danger_dark", "font_family", "label")


def test_theme_l_declare():
    assert "l" in THEMES and "l" in THEME_ORDER
    for key in REQUIRED_KEYS:
        assert key in THEMES["l"], f"cle obligatoire absente: {key}"


def test_themes_relief_portent_bevel_card():
    for tid in ("k", "l"):
        bevel = THEMES[tid].get("bevel_card")
        assert bevel and len(bevel) == 4, f"bevel_card manquant sur {tid}"


def test_is_relief_theme_k_et_l(qapp, monkeypatch):
    for tid in ("k", "l"):
        monkeypatch.setattr(gui_theme, "CURRENT_THEME_ID", tid)
        assert gui_theme.is_relief_theme()
    monkeypatch.setattr(gui_theme, "CURRENT_THEME_ID", "classic")
    assert not gui_theme.is_relief_theme()


@pytest.mark.parametrize("name", sorted(relief_glyphs._G))
def test_glyphes_relief_rendent(name, qapp):
    ic = relief_glyphs.relief_icon(name, "#e3e3e3")
    assert ic is not None and not ic.isNull()
    assert not ic.availableSizes()[0].isEmpty()


def test_relief_icon_nom_inconnu_renvoie_none(qapp):
    assert relief_glyphs.relief_icon("fa5s.inexistant", "#ffffff") is None


def test_relief_icon_cache(qapp):
    a = relief_glyphs.relief_icon("fa5s.save", "#abcd01")
    b = relief_glyphs.relief_icon("fa5s.save", "#abcd01")
    assert a is b


def test_theme_icon_passe_par_relief_sur_theme_l(qapp, monkeypatch):
    monkeypatch.setattr(gui_theme, "CURRENT_THEME_ID", "l")
    assert not gui_theme.icon("fa5s.globe").isNull()


def test_shadow_container_hors_relief(qapp, monkeypatch):
    from PyQt6.QtWidgets import QDialog
    monkeypatch.setattr(relief_effects, "is_relief_active", lambda: False)
    dlg = QDialog()
    w, lay = relief_effects.shadow_container(dlg, bg="#111111", border="#3a3a3a")
    assert w is dlg
    assert lay.contentsMargins().left() == 6


def test_shadow_container_en_relief(qapp, monkeypatch):
    from PyQt6.QtWidgets import QDialog, QFrame
    monkeypatch.setattr(relief_effects, "is_relief_active", lambda: True)
    dlg = QDialog()
    w, lay = relief_effects.shadow_container(dlg, bg="#111111", border="#3a3a3a")
    assert isinstance(w, QFrame) and w is not dlg
    assert dlg.testAttribute(
        __import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.WidgetAttribute.WA_TranslucentBackground)
    m = dlg.layout().contentsMargins()
    assert (m.left(), m.top(), m.right(), m.bottom()) == relief_effects.SHADOW_MARGINS


def test_press_enabled_suit_option_et_theme(qapp, monkeypatch):
    monkeypatch.setattr(gui_theme, "is_relief_theme", lambda: True)
    monkeypatch.setattr(press_feedback.settings, "get_press_anim_enabled", lambda: True)
    press_feedback.refresh_enabled()
    assert press_feedback.enabled()
    monkeypatch.setattr(press_feedback.settings, "get_press_anim_enabled", lambda: False)
    press_feedback.refresh_enabled()
    assert not press_feedback.enabled()
    monkeypatch.setattr(gui_theme, "is_relief_theme", lambda: False)
    monkeypatch.setattr(press_feedback.settings, "get_press_anim_enabled", lambda: True)
    press_feedback.refresh_enabled()
    assert not press_feedback.enabled()
    press_feedback.refresh_enabled()


def test_press_anim_settings_roundtrip():
    from core import settings
    old = settings.get_press_anim_enabled()
    try:
        settings.set_press_anim_enabled(False)
        assert settings.get_press_anim_enabled() is False
        settings.set_press_anim_enabled(True)
        assert settings.get_press_anim_enabled() is True
    finally:
        settings.set_press_anim_enabled(old)


def test_install_idempotent(qapp):
    press_feedback.install(qapp)
    press_feedback.install(qapp)
    assert press_feedback._instance is not None


def test_press_feedback_anim_geometry(qapp, monkeypatch):
    """Un press/reel press deplace la geometry de +2px puis la retablit."""
    from PyQt6.QtCore import QEvent, QPointF, Qt
    from PyQt6.QtGui import QMouseEvent
    from PyQt6.QtWidgets import QPushButton
    monkeypatch.setattr(gui_theme, "is_relief_theme", lambda: True)
    monkeypatch.setattr(press_feedback.settings, "get_press_anim_enabled", lambda: True)
    press_feedback.refresh_enabled()
    fb = press_feedback._PressFeedback()
    btn = QPushButton("ok")
    btn.resize(60, 24)
    btn.move(11, 13)
    press = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(5, 5), QPointF(5, 5),
                        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                        Qt.KeyboardModifier.NoModifier)
    assert not fb.eventFilter(btn, press)
    assert id(btn) in fb._pressed
    release = QMouseEvent(QEvent.Type.MouseButtonRelease, QPointF(5, 5), QPointF(5, 5),
                          Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton,
                          Qt.KeyboardModifier.NoModifier)
    assert not fb.eventFilter(btn, release)
    assert id(btn) not in fb._pressed
