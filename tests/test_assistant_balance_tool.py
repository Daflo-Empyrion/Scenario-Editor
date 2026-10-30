"""Outil de lecture 'scenario_balance_report' de l'assistant : enregistre avec
la surface scenario quand un scenario est ouvert, lit le tableau de bord
danger/progression, et N'ECRIT RIEN (contrat des surfaces : les outils de
lecture ne modifient jamais le disque)."""

from pathlib import Path

from core.ai.assistant.surfaces import scenario
from core.ai.assistant.tools import ToolRegistry

PLAYFIELD = """---
PlayfieldType: Planet

POIs:
    Random:
        - GroupName: Small
          CountMinMax: [ 1, 2 ]
"""

PDA = """Chapters:
  - ChapterTitle: pda_a
    Category: SoloMission
    Rewards:
      - Type: XP
        Count: 1000
      - Type: UP
        Count: 2
"""


def _scenario(tmp_path: Path) -> Path:
    pf = tmp_path / "Playfields" / "Calm"
    pf.mkdir(parents=True)
    (pf / "playfield_static.yaml").write_text(PLAYFIELD, encoding="utf-8")
    pda = tmp_path / "Extras" / "PDA"
    pda.mkdir(parents=True)
    (pda / "PDA.yaml").write_text(PDA, encoding="utf-8")
    return tmp_path


def test_tool_registered_read_only(tmp_path):
    tools = ToolRegistry()
    scenario.add_tools(tools, _scenario(tmp_path), "s1")
    names = tools.names("s1")
    assert "scenario_balance_report" in names
    assert not any("write" in n or "apply" in n for n in names)


def test_tool_reports_danger_chapters_attacks(tmp_path):
    tools = ToolRegistry()
    scenario.add_tools(tools, _scenario(tmp_path), "s1")
    tool = tools._tools["scenario_balance_report"]
    result = tool.handler({"limit": 5})
    text = result["text"]
    assert "PLAYFIELDS" in text and "Calm" in text
    assert "PDA CHAPTERS" in text and "pda_a" in text
    assert "ATTACK COSTS" in text
    assert result["playfields"] == 1 and result["chapters"] == 1


def test_tool_limit_clamped(tmp_path):
    tools = ToolRegistry()
    scenario.add_tools(tools, _scenario(tmp_path), "s1")
    tool = tools._tools["scenario_balance_report"]
    result = tool.handler({"limit": 9999})
    # borne haute appliquee, pas d'exception
    assert "PLAYFIELDS" in result["text"]
