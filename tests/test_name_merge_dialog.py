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

"""Dialogue « Fusion par noms » (gui/name_merge_dialog.py, v1.14.0) :
construction + flux complet sur VRAIS fichiers temporaires (regle
projet)."""
import types

WORKING = "{ EGroup Name: ZiraxPatrol\n  Faction: Zirax\n}\n"
SOURCE = ("{ EGroup Name: ZiraxPatrol\n  Faction: Zirax\n}\n"
          "{ EGroup Name: AbyssalBattleGroupA\n  Faction: Abyssal\n}\n")


def _make(tmp_path):
    w, s = tmp_path / "work", tmp_path / "src"
    for root in (w, s):
        (root / "Content/Configuration").mkdir(parents=True)
    (w / "Content/Configuration/EGroupsConfig.ecf").write_text(
        WORKING, encoding="utf-8")
    (s / "Content/Configuration/EGroupsConfig.ecf").write_text(
        SOURCE, encoding="utf-8")
    return w, s


def _make_dialog(qapp, w, s, pushes, reloaded):
    from gui.name_merge_dialog import NameMergeDialog
    main = types.SimpleNamespace(workspace=types.SimpleNamespace(
        working_root=w))
    main._push_workspace_undo = lambda undo: pushes.append(undo)
    main._reload_tab_if_open_and_unmodified = lambda path: reloaded.append(
        path)
    return NameMergeDialog(main,
                           s / "Content/Configuration/EGroupsConfig.ecf")


def test_dialog_construction(qapp, tmp_path):
    w, s = _make(tmp_path)
    dlg = _make_dialog(qapp, w, s, [], [])
    assert dlg.working_path is not None
    assert dlg.btn_analyze.isEnabled()
    assert dlg.btn_apply.isEnabled() is False


def test_dialog_analyze_groups(qapp, tmp_path):
    w, s = _make(tmp_path)
    dlg = _make_dialog(qapp, w, s, [], [])
    dlg._analyze()
    assert dlg._plan is not None and dlg._plan.ok
    assert [b.name for b in dlg._plan.blocks_add] == \
        ["AbyssalBattleGroupA"]
    assert dlg.btn_apply.isEnabled()
    assert dlg.tree.topLevelItemCount() >= 2     # groupe ajout + bloc


def test_dialog_apply_flow(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr("gui.msgboxes.info", lambda *a, **k: None)
    w, s = _make(tmp_path)
    pushes, reloaded = [], []
    dlg = _make_dialog(qapp, w, s, pushes, reloaded)
    dlg._analyze()
    dlg._apply()
    gcf = w / "Content/Configuration/EGroupsConfig.ecf"
    txt = gcf.read_text(encoding="utf-8")
    assert "Name: AbyssalBattleGroupA" in txt
    assert "Fusion depuis source" in txt
    assert gcf.with_suffix(".ecf.bak").exists()
    assert pushes, "undo espace de travail pousse"
    assert reloaded, "onglet recharge"
    # idempotence
    dlg._analyze()
    assert dlg._plan.blocks_add == []
    assert dlg.btn_apply.isEnabled() is False
