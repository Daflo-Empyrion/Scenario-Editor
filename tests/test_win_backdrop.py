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

"""Tests du materiau de fond Windows 11 parametrable (core/win_backdrop.py) :
Mica (theme "j" -- Nuit Mica) et acrylique (theme "h" -- Verriere) partagent
la meme recette DWM (DWMWA_SYSTEMBACKDROP_TYPE + cadre etendu), seul le
materiau demande change."""

import core.win_backdrop as win_backdrop


def test_backdrop_constants_cover_known_materials():
    assert win_backdrop._BACKDROP_CONSTANTS["mica"] == win_backdrop._DWMSBT_MAINWINDOW
    assert win_backdrop._BACKDROP_CONSTANTS["acrylic"] == win_backdrop._DWMSBT_ACRYLIC


def test_enable_backdrop_rejects_unknown_material(qapp):
    # Offscreen (et/ou kind inconnu) -> False sans jamais planter ni rendre
    # la fenetre translucide (invariant de lisibilite).
    assert win_backdrop.enable_backdrop(qapp, "verre_depoli") is False


def test_enable_acrylic_wrapper_matches_generic(qapp):
    # Le wrapper historique de Verriere delegue au passage generique.
    assert win_backdrop.enable_acrylic(qapp) == \
        win_backdrop.enable_backdrop(qapp, "acrylic")


def test_theme_nuit_mica_declares_mica_material():
    from core.themes import THEMES
    palette = THEMES["j"]
    assert palette["acrylic"] is True           # veut un materiau DWM
    assert palette["backdrop"] == "mica"        # Mica, pas le verre depoli
    assert "glass_qss" in palette               # teinte semi-transparente propre
    assert palette["glass_qss"].startswith("QMainWindow { background-color: rgba(30, 30, 36")
    # extra_qss equilibre : une regle ouverte non fermee casserait TOUTE la
    # feuille de style de l'application.
    extra = palette.get("extra_qss", "")
    assert extra.count("{") == extra.count("}") > 0
