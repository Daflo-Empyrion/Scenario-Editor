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

"""Tests du pilote PyQt-Fluent-Widgets (gui/fluent_pilot.py, decision du
09/09/2026) : fabriques de widgets, degrade gracieux sans qfluentwidgets,
suivi de theme (clair/sombre + accent) et branchement sur la fenetre
principale. Le reglage persistant est isole dans un settings.json temporaire
comme dans test_privacy_settings.py."""
import pytest

from PyQt6.QtWidgets import QPushButton, QLabel

import core.settings as settings
import gui.fluent_pilot as fluent_pilot
from gui.theme import icon


@pytest.fixture()
def isolated_settings(tmp_path, monkeypatch):
    """settings.json temporaire -- ne touche jamais la vraie config."""
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    return tmp_path / "settings.json"


@pytest.fixture()
def fluent_on(isolated_settings):
    """Pilote ACTIF : bibliotheque disponible (reelle) + reglage par defaut."""
    assert fluent_pilot.is_available() is True
    fluent_pilot.set_enabled(True)
    yield
    fluent_pilot.set_enabled(False)


@pytest.fixture()
def fluent_off(isolated_settings):
    fluent_pilot.set_enabled(False)
    yield


# ---------------------------------------------------------------------------
# Reglage persistant + disponibilite
# ---------------------------------------------------------------------------

def test_pilot_enabled_by_default(isolated_settings):
    # settings.json inexistant -> valeur par defaut True (pilote visible)
    assert isolated_settings.exists() is False
    assert settings.get_fluent_pilot_enabled() is True
    assert fluent_pilot.is_enabled() is True


def test_pilot_setting_roundtrip(isolated_settings):
    settings.set_fluent_pilot_enabled(False)
    assert settings.get_fluent_pilot_enabled() is False
    assert fluent_pilot.is_enabled() is False
    settings.set_fluent_pilot_enabled(True)
    assert fluent_pilot.is_enabled() is True


def test_pilot_disabled_when_library_missing(monkeypatch, isolated_settings):
    # Degrade gracieux : qfluentwidgets non importable -> is_enabled False
    # meme avec le reglage actif (exe construit sans la dependance).
    monkeypatch.setattr(fluent_pilot, "_AVAILABLE", False)
    assert fluent_pilot.is_available() is False
    assert fluent_pilot.is_enabled() is False


def test_pilot_availability_cached(monkeypatch):
    # L'echec d'import est mis en cache : pas de retest a chaque fabrique.
    # sys.modules['qfluentwidgets'] = None -> "import qfluentwidgets" leve
    # ImportError (mecanisme standard Python, simule une bibliotheque absente).
    monkeypatch.setitem(__import__("sys").modules, "qfluentwidgets", None)
    monkeypatch.setattr(fluent_pilot, "_AVAILABLE", None)
    assert fluent_pilot.is_available() is False
    assert fluent_pilot._AVAILABLE is False


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------

def test_toolbar_button_fluent_when_enabled(fluent_on, qapp):
    from qfluentwidgets import PushButton, PrimaryPushButton
    btn = fluent_pilot.make_toolbar_button(icon("fa5s.save"), "Enregistrer", accent=True)
    assert isinstance(btn, PrimaryPushButton)
    assert isinstance(btn, QPushButton)  # meme API que QPushButton
    plain = fluent_pilot.make_toolbar_button(icon("fa5s.globe"), "FR")
    assert isinstance(plain, PushButton)
    assert isinstance(plain, QPushButton)


def test_toolbar_button_vanilla_when_disabled(fluent_off, qapp):
    btn = fluent_pilot.make_toolbar_button(icon("fa5s.save"), "Enregistrer", accent=True)
    assert type(btn) is QPushButton


def test_panel_label_fluent_when_enabled(fluent_on, qapp):
    from qfluentwidgets import StrongBodyLabel
    lbl = fluent_pilot.make_panel_label("Scenario A")
    assert isinstance(lbl, StrongBodyLabel)
    assert isinstance(lbl, QLabel)


def test_panel_label_vanilla_when_disabled(fluent_off, qapp):
    lbl = fluent_pilot.make_panel_label("Scenario A")
    assert type(lbl) is QLabel


def test_icon_color_adapts_to_button_kind(fluent_on, qapp):
    # Standard Fluent = fond clair -> icone couleur texte (pas blanc) ;
    # accent = fond colore -> icone blanche, comme avant le pilote.
    assert fluent_pilot.icon_color(accent=False) != "#ffffff"
    assert fluent_pilot.icon_color(accent=True) == "#ffffff"


# ---------------------------------------------------------------------------
# Suivi du theme
# ---------------------------------------------------------------------------

def test_is_dark_bg_thresholds():
    assert fluent_pilot._is_dark_bg("#04060D") is True   # Verriere
    assert fluent_pilot._is_dark_bg("#eef1f6") is False  # classic
    assert fluent_pilot._is_dark_bg("n'importe quoi") is False


def test_sync_theme_follows_current_theme(fluent_on, qapp):
    from gui.theme import apply_theme
    from qfluentwidgets import qconfig, Theme
    apply_theme(qapp, "classic")  # clair
    fluent_pilot.sync_theme()
    assert qconfig.theme == Theme.LIGHT
    apply_theme(qapp, "h")        # Verriere = sombre
    fluent_pilot.sync_theme()
    assert qconfig.theme == Theme.DARK
    apply_theme(qapp, "classic")  # restaure pour les autres tests


def test_sync_theme_noop_when_disabled(fluent_off, qapp):
    # Ne doit ni planter ni toucher la config Fluent
    fluent_pilot.sync_theme()
    assert True


# ---------------------------------------------------------------------------
# Branchement fenetre principale
# ---------------------------------------------------------------------------

def _fresh_window(qapp):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    apply_theme(qapp, "classic")
    fluent_pilot.sync_theme()
    win = MainWindow()
    return win


def test_main_window_toolbar_uses_fluent_buttons(fluent_on, qapp):
    win = _fresh_window(qapp)
    for attr in ("btn_toolbar_save", "btn_toolbar_search", "btn_workspace_undo",
                 "btn_language", "btn_report_issue"):
        btn = getattr(win, attr)
        assert btn is not None
        assert isinstance(btn, QPushButton)
        assert btn.icon().isNull() is False
    from qfluentwidgets import PrimaryPushButton, PushButton
    assert isinstance(win.btn_toolbar_save, PrimaryPushButton)
    assert isinstance(win.btn_toolbar_search, PushButton)
    win.btn_toolbar_save.click()  # aucun onglet -> no-op, ne doit rien casser
    win.close()


def test_main_window_toolbar_vanilla_when_pilot_off(fluent_off, qapp):
    win = _fresh_window(qapp)
    assert type(win.btn_toolbar_save) is QPushButton
    assert type(win.label_a) is QLabel
    win.close()


def test_main_window_panel_labels_fluent(fluent_on, qapp):
    win = _fresh_window(qapp)
    from qfluentwidgets import StrongBodyLabel
    assert isinstance(win.label_a, StrongBodyLabel)
    assert isinstance(win.label_working, StrongBodyLabel)
    assert isinstance(win.label_b, StrongBodyLabel)
    win.close()


def test_options_menu_toggle_persists(fluent_on, qapp):
    win = _fresh_window(qapp)
    action = win.action_fluent_pilot
    assert action.isCheckable() is True
    assert action.isChecked() is True
    action.setChecked(False)  # declenche toggled -> persiste
    assert settings.get_fluent_pilot_enabled() is False
    win.close()
