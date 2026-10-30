"""Vocabulaire des declencheurs PDA (core/pda/event_types.py) : completude du
vocabulaire, detection d'un Check inconnu, et integration au bilan (W350)."""

from pathlib import Path

from core.pda.event_types import (GAME_EVENT_TYPES, known_checks,
                                  unknown_pda_checks)
from core.pda.schema import CHECKS


PDA_GOOD = """Chapters:
  - ChapterTitle: pda_a
    Tasks:
      - TaskTitle: pda_b
        Actions:
          - Check: ItemsConsumed
            Types:
              - Bandages
          - Check: AttackWave
            WaveStart:
              Name: Level1
          - Check: WaveDestroyed
"""

PDA_TYPO = """Chapters:
  - ChapterTitle: pda_a
    Actions:
      - Check: ItemsConsumd
      - Check: NoSuchTrigger
      - Check: ItemsConsumed
"""


def _scenario(tmp_path: Path, text: str) -> Path:
    pda = tmp_path / "Extras" / "PDA"
    pda.mkdir(parents=True)
    (pda / "PDA.yaml").write_text(text, encoding="utf-8")
    return tmp_path


def test_official_enum_present():
    for value in ("AttackWave", "WaveDestroyed", "SetTimer", "NpcCorePlaced",
                  "InventoryContainsCountOfItem", "SubjectKilled",
                  "PlayfieldTypeEntered"):
        assert value in GAME_EVENT_TYPES


def test_observed_checks_declared():
    # les declencheurs reellement utilises par les fichiers du jeu doivent etre
    # dans le schema (sinon l'editeur les affiche comme "inconnus")
    for value in ("ItemsConsumed", "HoldingItem", "ArmorEquipped",
                  "ArmorBoostEquipped", "ConstructionQueueContains",
                  "StructureProduced", "ViewSelected", "AttackWave",
                  "WaveDestroyed", "SetTimer"):
        assert value in CHECKS, value


def test_known_checks_is_union():
    known = known_checks()
    assert "NearPoi" in known and "ViewSelected" in known
    assert "AttackWave" in known and "ItemsConsumed" in known
    assert "PasUnTrigger" not in known


def test_unknown_detected(tmp_path):
    root = _scenario(tmp_path, PDA_TYPO)
    found = unknown_pda_checks(root)
    assert [(v, c) for _p, v, c in found] == [("ItemsConsumd", 1),
                                              ("NoSuchTrigger", 1)]


def test_real_checks_accepted(tmp_path):
    assert unknown_pda_checks(_scenario(tmp_path, PDA_GOOD)) == []


def test_missing_pda_dir(tmp_path):
    assert unknown_pda_checks(tmp_path) == []


def test_launch_check_reports_unknown_pda(tmp_path):
    from core.launch_check import run_launch_checks
    sectors = tmp_path / "Sectors"
    sectors.mkdir()
    (sectors / "Sectors.yaml").write_text(
        "SolarSystems:\n  - Name: Sys1\n    Sectors:\n"
        "      - ['0, 0, 0', Soleil1, Sun, '']\n", encoding="utf-8")
    _scenario(tmp_path, PDA_TYPO)
    issues = [i for i in run_launch_checks(tmp_path, "") if i.check == "pda"]
    assert len(issues) == 2
    assert all(i.severity == "warning" for i in issues)
    assert issues[0].path == "Extras/PDA/PDA.yaml"
    assert "W350" in issues[0].message
