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

"""Dialogue de fusion SPECIALISEE GalaxyConfig (gui/galaxy_merge_dialog.py,
demande du 01/10/2026) : regle projet = test de CONSTRUCTION + flux
analyze -> coche -> applique sur VRAIS fichiers temporaires (pas de
mock du moteur)."""
import shutil

from core.galaxy_merge import build_plan

# memes fixtures que test_galaxy_merge.py (tests/ n'est pas un package)
WORKING = """{ GalaxyConfig, Name: General
  StarCount: "100, 200"
  Radius: "0, 500"
}
{ GalaxyConfig, Name: G Type Star
  StarClass: G
  Probability: 0.5
}
{ GalaxyConfig, Name: M Type Star
  StarClass: M
  Probability: 0.8
}
"""

SOURCE = """{ GalaxyConfig, Name: General
  StarCount: "500, 900"
  Radius: "0, 500"
}
{ GalaxyConfig, Name: G Type Star
  StarClass: G
  Probability: 0.5
}
{ GalaxyConfig, Name: S Star
  StarClass: S
  Probability: 1
  SolarSystemConfigSuffix: _S
  GalaxySpawnAmount: 0
}
{ GalaxyConfig, Name: S Star Variant
  StarClass: S
  Probability: 0.4
}
"""

PRESET = """  PlanetLists:
    - 'Lava:1.0, DesertX:0.5'
  OrbitTypes:
      - Name: DefaultOrbit
        Playfields:
            - EdenSpace_OrbitX
            - EdenSpace_OrbitY
"""

def _make_scenario(tmp_path):
    w, s = tmp_path / "work", tmp_path / "src"
    for root in (w, s):
        (root / "Content/Configuration").mkdir(parents=True)
        (root / "Sectors").mkdir()
    (w / "Content/Configuration/GalaxyConfig.ecf").write_text(
        WORKING, encoding="utf-8")
    (s / "Content/Configuration/GalaxyConfig.ecf").write_text(
        SOURCE, encoding="utf-8")
    (w / "Sectors/Sectors.yaml").write_text(
        "SolarSystems:\n  - Name: Other System\n", encoding="utf-8")
    rp = s / "RandomPresets"
    rp.mkdir()
    (rp / "SolarSystemConfig_S.yaml").write_text(PRESET, encoding="utf-8")
    (s / "Playfields/DesertX").mkdir(parents=True)
    return w, s


def _make_dialog(qapp, w, s, monkeypatch):
    import types
    from gui.galaxy_merge_dialog import GalaxyMergeDialog
    main = types.SimpleNamespace(workspace=types.SimpleNamespace(
        working_root=w))
    main._push_workspace_undo = lambda undo: None
    main._reload_tab_if_open_and_unmodified = lambda path: None
    dlg = GalaxyMergeDialog(main, s / "Content/Configuration/GalaxyConfig.ecf")
    return dlg


def test_dialog_construction(qapp, tmp_path):
    w, s = _make_scenario(tmp_path)
    dlg = _make_dialog(qapp, w, s, None)
    assert dlg.working_path is not None
    assert dlg.btn_analyze.isEnabled()
    # sans projet ouvert : analyse desactivee
    import types
    from gui.galaxy_merge_dialog import GalaxyMergeDialog
    dlg2 = GalaxyMergeDialog(None,
                             s / "Content/Configuration/GalaxyConfig.ecf")
    assert dlg2.working_path is None
    assert dlg2.btn_analyze.isEnabled() is False


def test_dialog_analyze_groups(qapp, tmp_path):
    w, s = _make_scenario(tmp_path)
    dlg = _make_dialog(qapp, w, s, None)
    dlg._analyze()
    assert dlg.btn_apply.isEnabled()
    assert dlg._plan is not None and dlg._plan.ok
    # arbre : 2 systemes a ajouter + preset + playfield DesertX = 4 coches
    n_checked = 0
    for i in range(dlg.tree.topLevelItemCount()):
        g = dlg.tree.topLevelItem(i)
        for j in range(g.childCount()):
            if g.child(j).checkState(0).name == "Checked":
                n_checked += 1
    assert n_checked == 4


def test_dialog_apply_flow(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr("gui.msgboxes.info", lambda *a, **k: None)
    w, s = _make_scenario(tmp_path)
    dlg = _make_dialog(qapp, w, s, None)
    dlg._analyze()
    dlg._apply()
    gcf = w / "Content/Configuration/GalaxyConfig.ecf"
    txt = gcf.read_text(encoding="utf-8")
    assert "Name: S Star Variant" in txt
    assert "Fusion depuis source" in txt
    assert (w / "RandomPresets/SolarSystemConfig_S.yaml").exists()
    assert (w / "Playfields/DesertX").is_dir()
    assert gcf.with_suffix(".ecf.bak").exists()
    # idempotence : re-analyse = plus rien a ajouter
    dlg._analyze()
    assert dlg._plan.blocks_add == []


def test_dialog_apply_respects_unchecked(qapp, tmp_path, monkeypatch):
    from PyQt6.QtCore import Qt
    monkeypatch.setattr("gui.msgboxes.info", lambda *a, **k: None)
    w, s = _make_scenario(tmp_path)
    dlg = _make_dialog(qapp, w, s, None)
    dlg._analyze()
    # decocher tout
    for i in range(dlg.tree.topLevelItemCount()):
        g = dlg.tree.topLevelItem(i)
        for j in range(g.childCount()):
            it = g.child(j)
            if it.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                it.setCheckState(0, Qt.CheckState.Unchecked)
    dlg._apply()
    gcf = w / "Content/Configuration/GalaxyConfig.ecf"
    txt = gcf.read_text(encoding="utf-8")
    assert "S Star" not in txt, "les lignes decochees ne doivent pas etre ecrites"
    assert not (w / "RandomPresets/SolarSystemConfig_S.yaml").exists()
