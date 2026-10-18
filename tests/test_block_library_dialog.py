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

"""Bibliotheque de blocs (gui/block_library_dialog.py) : regle projet =
test de CONSTRUCTION + test du CHEMIN CONNECTE du filtre de recherche
(textChanged -> visibilite des items)."""


def _snippets():
    return [{"name": "CargoBox -- Helios", "path": "p1"},
            {"name": "Thruster -- T2 SV", "path": "p2"},
            {"name": "Turret -- Cannon CV", "path": "p3"}]


def _dialog(monkeypatch):
    from gui.block_library_dialog import BlockLibraryDialog
    monkeypatch.setattr("core.block_library.list_snippets", _snippets)
    return BlockLibraryDialog(None)


def test_dialog_construction(qapp, monkeypatch):
    dlg = _dialog(monkeypatch)
    assert dlg.list_widget.count() == 3
    assert all(not dlg.list_widget.item(i).isHidden()
               for i in range(dlg.list_widget.count()))


def test_search_filter_hides_non_matching(qapp, monkeypatch):
    dlg = _dialog(monkeypatch)
    dlg.search.setText("thruster")
    visible = [dlg.list_widget.item(i).text()
               for i in range(dlg.list_widget.count())
               if not dlg.list_widget.item(i).isHidden()]
    assert visible == ["Thruster -- T2 SV"]
    dlg.search.setText("")
    assert all(not dlg.list_widget.item(i).isHidden()
               for i in range(dlg.list_widget.count()))
