"""Classements du PDA (core/sql_rankings.py) : parsing INI-like avec
requetes SQL multi-lignes, etat actif/desactive, titre editable ligne a
ligne (commentaires preserves), desactivation et retour aux defauts."""

from pathlib import Path

from core.sql_rankings import (disable_rankings, restore_default_rankings, scan,
                               set_box_title)

ACTIVE = """# Documentaion a PRESERVER
- RankingBox1,1 = RkgKills

- RkgKills.Name = KILLS

- RkgKills.PlayersTop10.Query = 
    SELECT name FROM Entities
    ORDER BY kills DESC
    LIMIT 10
- RkgKills.PlayersTop10.CacheTime = 120

- RkgKills.LocalPlayer.Query =
    SELECT name FROM Entities
- RkgKills.CacheTime = 120
"""

# boite avec LocalPlayer mais sans PlayersTop10 -> W341
PARTIAL = """- RankingBox1,1 = RkgOdd
- RkgOdd.LocalPlayer.Query =
    SELECT 1
"""


def _scenario(tmp_path: Path, text: str = ACTIVE) -> Path:
    conf = tmp_path / "Content" / "Configuration"
    conf.mkdir(parents=True)
    (conf / "SqlQueries.txt").write_text(text, encoding="utf-8")
    return tmp_path


def test_scan_active(tmp_path):
    res = scan(_scenario(tmp_path))
    assert res.path is not None and res.active
    assert len(res.boxes) == 1
    box = res.boxes[0]
    assert box.name == "RkgKills"
    assert box.positions == ["RankingBox1,1"]
    assert box.title == "KILLS"
    assert box.cache_time == "120"
    assert len(box.queries["PlayersTop10"].splitlines()) == 3
    assert box.queries.get("FactionTop10", "") == ""
    assert res.issues == []


def test_scan_partial_warns(tmp_path):
    res = scan(_scenario(tmp_path, PARTIAL))
    assert [i.code for i in res.issues] == ["W341"]
    assert "PlayersTop10" in res.issues[0].message


def test_scan_disabled_style(tmp_path):
    text = ("- RankingBox1,1 = Off\n- Off.Name = OFF\n"
            "- Off.PlayersTop10.Query = \n- Off.LocalPlayer.Query = \n")
    res = scan(_scenario(tmp_path, text))
    assert res.active is False
    assert res.issues == []                 # boite volontairement vide


def test_set_title_preserves_file(tmp_path):
    root = _scenario(tmp_path)
    res = scan(root)
    box = res.boxes[0]
    assert set_box_title(res, box, "NOUVEAU TITRE")
    text = (root / "Content/Configuration/SqlQueries.txt").read_text(
        encoding="utf-8")
    assert "# Documentaion a PRESERVER" in text
    assert "- RkgKills.Name = NOUVEAU TITRE" in text
    assert "ORDER BY kills DESC" in text     # SQL intact
    assert box.title == "NOUVEAU TITRE"


def test_disable_then_restore(tmp_path):
    root = _scenario(tmp_path)
    path = disable_rankings(root)
    assert path.is_file()
    res = scan(root)
    assert res.active is False
    assert [b.name for b in res.boxes] == ["RankingsDisabled"]
    backup = restore_default_rankings(root)
    assert backup is not None
    assert not path.exists()
    assert scan(root).path is None           # le jeu reprend la base


def test_missing_file(tmp_path):
    res = scan(tmp_path)
    assert res.path is None and res.boxes == [] and res.active is False
    assert restore_default_rankings(tmp_path) is None
