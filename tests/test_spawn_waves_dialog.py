"""Ondes de spawn (gui/spawn_waves_dialog.py) : construction, chemin
CONNECTE scan -> filtres -> coche -> apercu MODIFIABLE -> application
(ecriture reelle + re-scan automatique). Async synchrone, boites patchees
(regle du 11/10)."""

from pathlib import Path

from PyQt6.QtCore import Qt

from gui.spawn_waves_dialog import SpawnWavesDialog

PLANET_STATIC = """---
PlayfieldType: Planet

POIs:
    Random:
        - GroupName: OutpostA
          Faction: Zirax
          CountMinMax: [ 2, 5 ]

        - GroupName: OutpostB
          Faction: Polaris
          CountMinMax: [ 1, 1 ]

DroneSpawning:
    Random:
        - DronesMinMax: [ 4, 6 ]
          CenterX: -5000
"""

SPACE_DYNAMIC = """---
PlayfieldType: Space

DroneBaseSetup:
    SpaceVessels:
        - Name: [OPVZirax]
          Faction: Zirax
          CountMinMax: [5, 10]
          Probability: 1
"""


def _scenario(tmp_path: Path) -> Path:
    p1 = tmp_path / "Playfields" / "TestPlanet"
    p2 = tmp_path / "Playfields" / "TestSpace"
    p1.mkdir(parents=True)
    p2.mkdir(parents=True)
    (p1 / "playfield_static.yaml").write_text(PLANET_STATIC, encoding="utf-8")
    (p2 / "space_dynamic.yaml").write_text(SPACE_DYNAMIC, encoding="utf-8")
    return tmp_path


def test_dialog_builds(qapp):
    dlg = SpawnWavesDialog(None)
    assert dlg.tabs.count() == 2
    assert dlg.table_summary.columnCount() == 9
    assert dlg.table_groups.columnCount() == 9
    assert dlg.btn_apply.isEnabled() is False
    assert dlg.btn_preview.isEnabled() is False


def _row_of_prop(dlg, prop_idx: int) -> int:
    for row in range(dlg.table_groups.rowCount()):
        it = dlg.table_groups.item(row, 0)
        if it is not None and it.prop_idx == prop_idx:
            return row
    raise AssertionError(f"ligne introuvable pour prop {prop_idx}")


def test_full_flow_scan_filter_check_preview_edit_apply(qapp, tmp_path,
                                                        monkeypatch):
    monkeypatch.setattr(
        "gui.spawn_waves_dialog.async_call",
        lambda owner, fn, on_done, on_fail=None, name="": on_done(fn()))
    seen = []
    monkeypatch.setattr("gui.spawn_waves_dialog.info",
                        lambda *a, **k: seen.append(a))
    monkeypatch.setattr("gui.spawn_waves_dialog.ask_yes_no",
                        lambda *a, **k: True)
    root = _scenario(tmp_path)
    dlg = SpawnWavesDialog(None, str(root))

    dlg._analyze()
    assert dlg.table_summary.rowCount() == 2
    assert dlg.table_groups.rowCount() == 4      # 2 POI + 1 patrouille + 1 vaisseau
    assert dlg.btn_apply.isEnabled() is True

    # filtre par type : le vaisseau seul reste visible
    dlg.cmb_kind.setCurrentIndex(dlg.cmb_kind.findData("vessel"))
    visible = [r for r in range(dlg.table_groups.rowCount())
               if not dlg.table_groups.isRowHidden(r)]
    assert len(visible) == 1

    # rien de precoche
    assert dlg._checked_rows() == []
    idx = dlg.table_groups.item(visible[0], 0).prop_idx
    row = _row_of_prop(dlg, idx)
    dlg.table_groups.item(row, 0).setCheckState(Qt.CheckState.Checked)

    # apercu : facteur x2.0 -> colonnes modifiables remplies
    dlg.spin_factor.setValue(200)
    dlg._preview()
    row = _row_of_prop(dlg, idx)
    assert (dlg.table_groups.item(row, 7).text(),
            dlg.table_groups.item(row, 8).text()) == ("10", "20")
    # apercu MODIFIABLE : l'utilisateur corrige le max a la main
    dlg.table_groups.item(row, 8).setText("25")

    dlg._apply()
    text = (root / "Playfields/TestSpace/space_dynamic.yaml").read_text(
        encoding="utf-8")
    assert "CountMinMax: [10, 25]" in text
    assert "Probability: 1" in text              # autre param intact
    assert seen, "confirmation affichee"
    # re-scan automatique : la synthese reflechit la nouvelle valeur
    space = next(s for s in dlg._result.summaries if s.pf_type == "Space")
    assert space.vessels_min == 10 and space.vessels_max == 25


def test_preview_requires_check(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "gui.spawn_waves_dialog.async_call",
        lambda owner, fn, on_done, on_fail=None, name="": on_done(fn()))
    seen = []
    monkeypatch.setattr("gui.spawn_waves_dialog.info",
                        lambda *a, **k: seen.append(a))
    dlg = SpawnWavesDialog(None, str(_scenario(tmp_path)))
    dlg._analyze()
    dlg._preview()
    assert seen, "message 'cochez au moins un groupe'"
