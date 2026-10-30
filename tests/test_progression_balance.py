"""Danger & progression (core/progression_balance.py) : danger par playfield
vs mediane du meme type, recompenses des chapitres vs mediane de categorie,
cout des attaques vs mediane, export CSV."""

from pathlib import Path

from core.progression_balance import export_csv, scan

PLAYFIELD = """---
PlayfieldType: Planet
PvPProb: 0

POIs:
    Random:
        - GroupName: Small
          CountMinMax: [ 1, 2 ]
        - GroupName: Small2
          CountMinMax: [ 1, 2 ]
"""

PLAYFIELD_BIG = """---
PlayfieldType: Planet

POIs:
    Random:
        - GroupName: Huge
          CountMinMax: [ 90, 100 ]
"""

PLAYFIELD_SPACE = """---
PlayfieldType: Space

DroneBaseSetup:
    SpaceVessels:
        - Name: [V1]
          CountMinMax: [ 5, 10 ]
          Probability: 1
"""

PDA = """Chapters:
  - ChapterTitle: pda_a
    Category: SoloMission
    Rewards:
      - Type: XP
        Count: 1000
      - Type: UP
        Count: 5
  - ChapterTitle: pda_b
    Category: SoloMission
    Rewards:
      - Type: XP
        Count: 5000
      - Type: UP
        Count: 8
  - ChapterTitle: pda_c
    Category: SoloMission
    Rewards:
      - Type: XP
        Count: 50000
  - ChapterTitle: pda_faq
    Category: Knowledgebase
"""

WARFARE = """{ Element Name: FactionSettings
  Faction: Talon
  Lvl1MinPrice: 80
  Lvl10MaxPrice: 1200
}
{ Element Name: FactionSettings
  Faction: Zirax
  { Child BaseAttack_ScenarioPrice
    PlayFieldLvl1Min: 15
    PlayFieldLvl10Max: 80
  }
  SDScenarioGroup: ZiraxSpaceDefense
}
"""


def _scenario(tmp_path: Path) -> Path:
    for name, text in (("Calm", PLAYFIELD), ("Huge", PLAYFIELD_BIG)):
        pf = tmp_path / "Playfields" / name
        pf.mkdir(parents=True)
        (pf / "playfield_static.yaml").write_text(text, encoding="utf-8")
    space = tmp_path / "Playfields" / "Orbit"
    space.mkdir(parents=True)
    (space / "space_dynamic.yaml").write_text(PLAYFIELD_SPACE, encoding="utf-8")
    pda = tmp_path / "Extras" / "PDA"
    pda.mkdir(parents=True)
    (pda / "PDA.yaml").write_text(PDA, encoding="utf-8")
    conf = tmp_path / "Content" / "Configuration"
    conf.mkdir(parents=True)
    (conf / "FactionWarfare.ecf").write_text(WARFARE, encoding="utf-8")
    return tmp_path


def test_playfield_danger_and_outlier(tmp_path):
    report = scan(_scenario(tmp_path))
    by_name = {p.playfield: p for p in report.playfields}
    assert by_name["Calm"].danger_max == 4
    assert by_name["Huge"].danger_max == 100
    assert by_name["Orbit"].danger_max == 10
    # mediane Planet = (4 + 100) / 2 = 52 -> Huge (100) hors mediane (> 2x ? non)
    assert by_name["Huge"].status == "ok"      # 100 < 2 x 52
    assert by_name["Calm"].status == "ok"


def test_playfield_outlier_threshold(tmp_path):
    root = _scenario(tmp_path)
    extra = root / "Playfields" / "Calm2"
    extra.mkdir()
    (extra / "playfield_static.yaml").write_text(PLAYFIELD, encoding="utf-8")
    by_name = {p.playfield: p for p in scan(root).playfields}
    # medianes Planet = (4, 4, 100) -> 4 ; Huge 100 > 8 -> outlier
    assert by_name["Huge"].status == "outlier"
    assert by_name["Calm"].status == "ok"


def test_chapter_rewards_and_medians(tmp_path):
    report = scan(_scenario(tmp_path))
    chapters = {c.title: c for c in report.chapters}
    assert chapters["pda_a"].xp == 1000 and chapters["pda_a"].up == 5
    assert chapters["pda_a"].rewards == 2
    assert chapters["pda_faq"].status == "no_reward"
    # medianes SoloMission sur les chapitres recompenses : xp = 5000
    # (1000 / 5000 / 50000), up = 5 (5 / 8 / 0)
    med = report.chapter_medians["SoloMission"]
    assert med["xp"] == 5000 and med["up"] == 5
    # pda_c : xp au-dessus mais up en dessous -> statut mixte 'ok'
    assert chapters["pda_c"].status == "ok"
    # pda_b : xp 5000 == mediane, up 8 > 5 -> mixte 'ok'
    assert chapters["pda_b"].status == "ok"


def test_chapter_below(tmp_path):
    root = _scenario(tmp_path)
    pda = root / "Extras" / "PDA" / "PDA.yaml"
    nl = chr(10)
    pda.write_text(nl.join([
        "Chapters:",
        "  - ChapterTitle: pda_small",
        "    Category: SoloMission",
        "    Rewards:",
        "      - Type: XP",
        "        Count: 1000",
        "      - Type: UP",
        "        Count: 2",
        "  - ChapterTitle: pda_big",
        "    Category: SoloMission",
        "    Rewards:",
        "      - Type: XP",
        "        Count: 5000",
        "      - Type: UP",
        "        Count: 8",
    ]), encoding="utf-8")
    chapters = {c.title: c for c in scan(root).chapters}
    # medianes (3000, 5) : les deux dimensions de pda_small sont en dessous
    assert chapters["pda_small"].status == "below"
    assert chapters["pda_big"].status == "above"


def test_attack_costs(tmp_path):
    report = scan(_scenario(tmp_path))
    by_faction = {a.faction: a for a in report.attacks}
    assert by_faction["Talon"].lvl1_min == 80
    assert by_faction["Talon"].lvl10_max == 1200
    assert by_faction["Zirax"].lvl10_max == 80
    assert by_faction["Zirax"].sd_group == "ZiraxSpaceDefense"
    # mediane lvl10 = (1200 + 80)/2 = 640 -> 1200 < 2x640 : ok
    assert by_faction["Talon"].status == "ok"


def test_export_csv(tmp_path):
    report = scan(_scenario(tmp_path))
    out = export_csv(report, tmp_path / "out.csv")
    text = out.read_text(encoding="utf-8-sig")
    assert "volet;nom;groupe" in text
    assert "playfield;Calm;Planet" in text
    assert "chapitre;pda_a;SoloMission" in text
    assert "attaque;Talon" in text


def test_empty_scenario(tmp_path):
    report = scan(tmp_path)
    assert report.playfields == [] and report.chapters == [] \
        and report.attacks == []
