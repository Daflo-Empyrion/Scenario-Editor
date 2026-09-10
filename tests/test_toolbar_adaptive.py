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

"""Tests de la barre d'outils ADAPTATIVE de la fenetre principale (retour
utilisateur du 09/09/2026 : textes tronques au redimensionnement -- le layout
de QToolBar comprime les boutons Fluent sous leur taille conseillee au lieu
de basculer en chevron). La barre degrade maintenant son texte en 3 modes :
0 = tous les textes, 1 = seul "Enregistrer" garde son texte, 2 = icones
seuls, avec hysteresis au retour."""
import core.settings as settings
import gui.fluent_pilot as fluent_pilot
import pytest


@pytest.fixture()
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")


@pytest.fixture()
def fresh_window(qapp, isolated_settings):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    fluent_pilot.set_enabled(True)
    apply_theme(qapp, "classic")
    win = MainWindow()
    # show() OBLIGATOIRE : Qt ne livre pas les QResizeEvent aux widgets
    # caches, et toute la logique adaptative se declenche dans resizeEvent.
    win.show()
    try:
        yield win
    finally:
        win.close()
        fluent_pilot.set_enabled(False)


def _mode(win) -> int:
    return win._toolbar_text_mode


def test_toolbar_full_text_when_wide(fresh_window):
    win = fresh_window
    win.resize(2400, 800)
    assert _mode(win) == 0
    for attr in ("btn_toolbar_save", "btn_toolbar_search", "btn_toolbar_galaxy",
                 "btn_workspace_undo", "btn_language", "btn_report_issue"):
        assert getattr(win, attr).text() != "", attr


def test_toolbar_secondary_icons_when_narrow(fresh_window):
    win = fresh_window
    # etroit mais pas extreme : les boutons secondaires perdent leur texte,
    # l'action primaire (Enregistrer) le garde -- mode 1.
    win.resize(1150, 800)
    assert _mode(win) == 1
    assert win.btn_toolbar_search.text() == ""
    assert win.btn_toolbar_galaxy.text() == ""
    assert win.btn_toolbar_center.text() == ""
    assert win.btn_toolbar_save.text() != ""
    # les tooltips restent la seule source d'info des boutons en mode icone
    assert win.btn_toolbar_search.toolTip() != ""


def test_toolbar_all_icons_when_very_narrow(fresh_window):
    win = fresh_window
    win.resize(340, 800)
    assert _mode(win) == 2
    assert win.btn_toolbar_save.text() == ""


def test_toolbar_text_restored_when_widened(fresh_window):
    win = fresh_window
    win.resize(340, 800)
    win.resize(2400, 800)
    assert _mode(win) == 0
    assert win.btn_toolbar_search.text() != ""
    assert win.btn_toolbar_save.text() != ""


def test_toolbar_hysteresis_prevents_flicker(fresh_window):
    """Le retour au mode riche exige une marge (hysteresis) : juste EN DESSOUS
    du seuil de retour la barre reste compressee, au-dessus elle se recharge."""
    win = fresh_window
    win.resize(2500, 800)
    assert _mode(win) == 0
    win.resize(win._toolbar_needed_width(0) - 10, 800)
    assert _mode(win) >= 1
    # juste sous le seuil de decompression (needed0 + hysteresis) : on reste
    # en mode compresse malgre la place "presque" suffisante
    win.resize(win._toolbar_needed_width(0) + win._TOOLBAR_HYSTERESIS_PX - 5, 800)
    assert _mode(win) == 1
    # au-dessus du seuil : retour au mode riche
    win.resize(win._toolbar_needed_width(0) + win._TOOLBAR_HYSTERESIS_PX + 15, 800)
    assert _mode(win) == 0


def test_vanilla_pilot_off_toolbar_also_adapts(qapp, isolated_settings):
    """Pilote Fluent DESACTIVE : la barre adaptative doit quand meme eviter
    la compression des QPushButton vanilla (memes seuils de confort)."""
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    fluent_pilot.set_enabled(False)
    apply_theme(qapp, "classic")
    win = MainWindow()
    win.show()
    try:
        win.resize(1150, 800)
        assert win.btn_toolbar_search.text() == ""
        assert win.btn_toolbar_save.text() != ""
    finally:
        win.close()


def test_toolbar_texts_survive_language_retext(fresh_window):
    """Changement de langue : les libelles sont re-mesures et le mode courant
    re-applique (un bouton en mode icone ne doit pas ressusciter son texte)."""
    from core import i18n
    win = fresh_window
    win.resize(1150, 800)
    assert _mode(win) == 1
    old = i18n.get_language()
    try:
        i18n.set_language("en")
        win._apply_language()  # re-texte global + re-mesure barre adaptative
        assert _mode(win) == 1
        assert win.btn_toolbar_search.text() == ""
        assert win.btn_toolbar_save.text() != ""
        assert win.btn_toolbar_save.text() == i18n.t("menu.file.save")
    finally:
        i18n.set_language(old)
        win._apply_language()
