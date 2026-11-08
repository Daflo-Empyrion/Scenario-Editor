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

"""Tests du dialogue Audit IA (gui/ai_audit_dialog.py) : l'audit est affiché
à l'ouverture, la simulation ne touche à rien, l'application écrit avec
backups puis ré-audite (constats résolus)."""
from pathlib import Path

import pytest

BR = chr(10)

PLAYFIELD = BR.join([
    "DroneBaseSetup:",
    "  Random:",
    "    - GroupName: Base",
    "      Difficulty: 6",
    "POIs:",
    "  Random:",
    "    - GroupName: ZiraxBase",
    "      DroneProb: 0",
    "      ReserveCount: 0",
    "SpawnZones:",
    "  - SpawnAt: [ Ruins ]",
    "    Entities:",
    "      - Names: [ZiraxMinigunPatrol]",
    "        Amount: 75",
    "        DelayMinMax: [-1, -1]",
    "",
])


@pytest.fixture
def scenario(tmp_path):
    root = tmp_path / "Mini"
    cfg = root / "Content" / "Configuration"
    cfg.mkdir(parents=True)
    (root / "Playfields" / "P").mkdir(parents=True)
    (root / "Prefabs").mkdir()
    for name in ("EClassConfig.ecf", "EGroupsConfig.ecf", "DefReputation.ecf"):
        (cfg / name).write_text("# vide" + BR, encoding="utf-8", newline="")
    (root / "Playfields" / "P" / "playfield_static.yaml").write_text(
        PLAYFIELD, encoding="utf-8", newline="")
    return root


def test_dialog_shows_audit_on_open(qapp, scenario):
    from gui.ai_audit_dialog import AiAuditDialog
    dlg = AiAuditDialog(None, scenario)
    ids = {dlg.tree.topLevelItem(i).text(0) for i in range(dlg.tree.topLevelItemCount())}
    assert {"baiconfig", "animations", "drone_zero", "patrol_norepop"} <= ids


def test_dry_run_writes_nothing(qapp, scenario):
    from gui.ai_audit_dialog import AiAuditDialog
    pf = scenario / "Playfields" / "P" / "playfield_static.yaml"
    before = pf.read_bytes()
    dlg = AiAuditDialog(None, scenario)
    dlg._do_dry()
    assert pf.read_bytes() == before
    assert "SIMULATION" in dlg.log.toPlainText() or "SIMULATION" in dlg.log.toPlainText().upper()


def test_apply_fixes_then_reaudit(qapp, scenario, monkeypatch):
    from gui import ai_audit_dialog as mod
    monkeypatch.setattr(mod, "ask_yes_no", lambda *a, **k: True)
    dlg = mod.AiAuditDialog(None, scenario)
    dlg._do_apply()
    ids = {dlg.tree.topLevelItem(i).text(0) for i in range(dlg.tree.topLevelItemCount())}
    assert not {"baiconfig", "animations", "drone_zero", "patrol_norepop"} & ids
    backups = scenario.parent / (scenario.name + "_ai_backups")
    assert backups.exists() and any(backups.iterdir())
