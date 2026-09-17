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

"""Sous-menu Options > Traduction > Moteur de traduction (demande du
17/09/2026) : radios exclusives Google / Argos / NLLB. L'ancienne case
binaire « Traduction hors ligne (Argos) » ne disait pas quel moteur tournait
et NLLB n'y figurait pas. La case « Traduction en ligne (Google) » reste une
PERMISSION de confidentialite, distincte du choix du moteur."""

import pytest


@pytest.fixture()
def win(qapp, tmp_path, monkeypatch):
    """MainWindow reelle avec settings isoles et disponibilites moteurs
    simulees (on ne depend pas de ce qui est installe sur la machine)."""
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from core import settings, argos_provider, nllb_provider
    apply_theme(qapp, "classic")
    monkeypatch.setattr(settings, "SETTINGS_FILE",
                        tmp_path / "settings.json")
    monkeypatch.setattr(argos_provider, "packages_on_disk", lambda: 2)
    monkeypatch.setattr(nllb_provider, "is_installed",
                        lambda variant: variant == "600M")
    w = MainWindow()
    yield w
    w.close()


def test_exactly_one_engine_radio_checked(win):
    from core.settings import get_translation_engine
    radios = (win.action_engine_google, win.action_engine_argos,
              win.action_engine_nllb)
    assert sum(1 for a in radios if a.isChecked()) == 1
    engine = get_translation_engine()
    checked = {a for a, e in zip(radios, ("google", "argos", "nllb"))
               if a.isChecked()}
    assert next(iter(checked)) is getattr(win, f"action_engine_{engine}")


def test_engine_switch_persists(win, monkeypatch):
    """Cliquer une radio persiste le moteur et decoche les autres
    (exclusivite du QActionGroup)."""
    from core import settings
    win.action_engine_nllb.trigger()
    assert settings.get_translation_engine() == "nllb"
    assert win.action_engine_nllb.isChecked()
    assert not win.action_engine_google.isChecked()
    assert not win.action_engine_argos.isChecked()
    win.action_engine_google.trigger()
    assert settings.get_translation_engine() == "google"
    assert not win.action_engine_nllb.isChecked()


def test_engine_availability_greys_radios(qapp, tmp_path, monkeypatch):
    """Argos grise sans modele ; NLLB grise sans modele telecharge."""
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from core import settings, argos_provider, nllb_provider
    apply_theme(qapp, "classic")
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(argos_provider, "packages_on_disk", lambda: 0)
    monkeypatch.setattr(nllb_provider, "is_installed", lambda variant: False)
    w = MainWindow()
    try:
        assert not w.action_engine_argos.isEnabled()
        assert not w.action_engine_nllb.isEnabled()
        assert w.action_engine_google.isEnabled()
        # le moteur courant indisponible : sa radio est grisee, non cohee
        assert not w.action_engine_argos.isChecked()
        assert not w.action_engine_nllb.isChecked()
    finally:
        w.close()


def test_engine_nllb_tooltip_shows_active_variant(win, monkeypatch):
    """Le tooltip NLLB du sous-menu Moteur affiche la variante ACTIVE
    (demande 17/09/2026 : 600M et 1.3B peuvent etre installes tous les deux)."""
    from core import settings
    monkeypatch.setattr(settings, "get_nllb_variant", lambda: "1.3B")
    win._refresh_engine_menu()
    assert "1.3B" in win.action_engine_nllb.toolTip()
    monkeypatch.setattr(settings, "get_nllb_variant", lambda: "600M")
    win._refresh_engine_menu()
    assert "600M" in win.action_engine_nllb.toolTip()
