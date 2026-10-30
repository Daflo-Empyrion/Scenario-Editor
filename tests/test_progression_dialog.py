"""Tableau de bord danger & progression (gui/progression_dialog.py) :
construction, chemin CONNECTE scan -> trois tableaux -> export CSV."""

from pathlib import Path

from gui.progression_dialog import ProgressionDialog

PLAYFIELD = """---
PlayfieldType: Planet

POIs:
    Random:
        - GroupName: SmallA
          CountMinMax: [ 1, 2 ]
        - GroupName: SmallB
          CountMinMax: [ 2, 3 ]
"""

PDA = """Chapters:
  - ChapterTitle: pda_a
    Category: SoloMission
    Rewards:
      - Type: XP
        Count: 1200
"""


def _scenario(tmp_path: Path) -> Path:
    pf = tmp_path / "Playfields" / "Calm"
    pf.mkdir(parents=True)
    (pf / "playfield_static.yaml").write_text(PLAYFIELD, encoding="utf-8")
    pda = tmp_path / "Extras" / "PDA"
    pda.mkdir(parents=True)
    (pda / "PDA.yaml").write_text(PDA, encoding="utf-8")
    return tmp_path


def test_dialog_builds(qapp):
    dlg = ProgressionDialog(None)
    assert dlg.tabs.count() == 3
    assert dlg.table_pf.columnCount() == 5
    assert dlg.btn_export.isEnabled() is False


def test_full_flow(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "gui.progression_dialog.async_call",
        lambda owner, fn, on_done, on_fail=None, name="": on_done(fn()))
    seen = []
    monkeypatch.setattr("gui.progression_dialog.info",
                        lambda *a, **k: seen.append(a))
    root = _scenario(tmp_path)
    dlg = ProgressionDialog(None, str(root))
    dlg._analyze()
    assert dlg.table_pf.rowCount() == 1
    assert dlg.table_ch.rowCount() == 1
    assert dlg.btn_export.isEnabled() is True
    assert "1 playfields" in dlg.stats_label.text()

    out = tmp_path / "export.csv"
    monkeypatch.setattr(
        "gui.progression_dialog.QFileDialog.getSaveFileName",
        staticmethod(lambda *a, **k: (str(out), "CSV (*.csv)")))
    dlg._export()
    text = out.read_text(encoding="utf-8-sig")
    assert "playfield;Calm;Planet" in text
    assert "chapitre;pda_a;SoloMission" in text
    assert seen, "confirmation d'export"
