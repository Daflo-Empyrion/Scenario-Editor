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

"""Fenetre externe « Vue 3D » d'un .epb (systeme EPD) : cubes de surface
colores avec la palette du jeu, camera orbitale, selection au clic."""
import pytest

from test_epb_blueprint import build_epb

from core.epb_blueprint import EpbBlueprint


@pytest.fixture
def colored_bp(tmp_path):
    """3 blocs dont un rouge (couleur 2) et un gris (16)."""
    colored = {cell: 2 for cell in {0: 412, 5: 7500, 11: 2050}}
    colored[11] = 16
    epb = build_epb(tmp_path / "colored.epb", colors=colored)
    return EpbBlueprint(epb, ecf_paths=[]).parse()


def test_window_renders_and_summarizes(qapp, colored_bp):
    from PyQt6 import sip
    from gui.epb_3d_window import Epb3dWindow
    win = Epb3dWindow(colored_bp)
    try:
        win.resize(900, 640)
        assert "3×2×2" in win.lbl_summary.text()
        assert "3 blocs" in win.lbl_summary.text()
        win.grab()                          # paintEvent sans erreur
    finally:
        sip.delete(win)


def test_window_select_shows_block_info(qapp, colored_bp):
    from PyQt6 import sip
    from gui.epb_3d_window import Epb3dWindow
    win = Epb3dWindow(colored_bp)
    try:
        block = win._view._cubes[0]
        win._view.blockSelected.emit(block)
        text = win.lbl_block.toPlainText()
        assert str(block[0]) in text        # x
        assert "Couleur : 2" in text
        win.grab()
    finally:
        sip.delete(win)


def test_dialog_button_opens_the_window(qapp, tmp_path, monkeypatch):
    from PyQt6 import sip
    from gui import epb_check_dialog as mod
    ecf = tmp_path / "BlocksConfig.ecf"
    ecf.write_text("{ Block Id: 412, Name: HullTest\n}\n", encoding="utf-8")
    epb = build_epb(tmp_path / "test.epb")
    dlg = mod.EpbCheckDialog(None, catalog_paths=[str(ecf)])
    try:
        dlg.path_edit.setText(str(epb))
        dlg._analyze()
        assert dlg.btn_view3d.isEnabled()
        dlg._open_view3d()                  # appel direct : la connection du
        win = dlg._view3d_window            # bouton est posee a l'init
        assert win is not None and win.isVisible()
        assert "3×2×2" in win.lbl_summary.text()
        win.grab()
    finally:
        if dlg._view3d_window is not None:
            sip.delete(dlg._view3d_window)
        sip.delete(dlg)
