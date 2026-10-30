"""Classements (gui/sql_rankings_dialog.py) : construction + chemin CONNECTE
scan -> selection -> titre applique (fichier reel) -> desactivation."""

from pathlib import Path

from gui.sql_rankings_dialog import SqlRankingsDialog

ACTIVE = """- RankingBox1,1 = RkgKills
- RkgKills.Name = KILLS
- RkgKills.PlayersTop10.Query = 
    SELECT name FROM Entities
- RkgKills.CacheTime = 120
"""


def _scenario(tmp_path: Path) -> Path:
    conf = tmp_path / "Content" / "Configuration"
    conf.mkdir(parents=True)
    (conf / "SqlQueries.txt").write_text(ACTIVE, encoding="utf-8")
    return tmp_path


def test_dialog_builds(qapp):
    dlg = SqlRankingsDialog(None)
    assert dlg.table.columnCount() == 6
    assert dlg.btn_disable.isEnabled() is False


def test_full_flow(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "gui.sql_rankings_dialog.async_call",
        lambda owner, fn, on_done, on_fail=None, name="": on_done(fn()))
    seen = []
    monkeypatch.setattr("gui.sql_rankings_dialog.info",
                        lambda *a, **k: seen.append(a))
    monkeypatch.setattr("gui.sql_rankings_dialog.ask_yes_no",
                        lambda *a, **k: True)
    root = _scenario(tmp_path)
    dlg = SqlRankingsDialog(None, str(root))
    dlg._analyze()
    assert dlg.table.rowCount() == 1
    assert dlg._result.active is True
    dlg.table.selectRow(0)
    assert "SELECT name FROM Entities" in dlg.sql_view.toPlainText()

    dlg.edit_title.setText("TUES")
    dlg._apply_title()
    text = (root / "Content/Configuration/SqlQueries.txt").read_text(
        encoding="utf-8")
    assert "- RkgKills.Name = TUES" in text

    dlg._disable()
    text = (root / "Content/Configuration/SqlQueries.txt").read_text(
        encoding="utf-8")
    assert "RankingsDisabled" in text
    assert "SELECT name FROM Entities" not in text
    assert seen, "confirmations affichees"
