"""Defenses de faction (gui/faction_warfare_dialog.py) : construction et
chemin CONNECTE scan -> edition d'un prix -> reglage global -> enregistrement
(ecriture reelle, forme d'origine preservee)."""

from pathlib import Path

from gui.faction_warfare_dialog import FactionWarfareDialog

WARFARE = """{ Element Name: GlobalSettings
  EnableSpaceDefense: True
  PlayerAttackMaxCountFrequencySpawned: 10
  PlayerAttackMaxCountPOISpawned: 10
}

{ Element Name: FactionSettings
  Faction: Talon
  ScenarioGroup: Talon
  Lvl1MinPrice: 80
  Lvl1MaxPrice: 120
}

{ Element Name: FactionSettings
  Faction: Zirax
  ScenarioGroup: Zirax
  { Child BaseAttack_ScenarioPrice
    PlayFieldLvl1Min: 15
    PlayFieldLvl1Max: 30
  }
}
"""


def _scenario(tmp_path: Path) -> Path:
    conf = tmp_path / "Content" / "Configuration"
    conf.mkdir(parents=True)
    (conf / "FactionWarfare.ecf").write_text(WARFARE, encoding="utf-8")
    (conf / "Factions.ecf").write_text(
        '{ Faction Id: 1, Name: "Zirax"\n}\n'
        '{ Faction Id: 2, Name: "Talon"\n}\n', encoding="utf-8")
    return tmp_path


def test_dialog_builds(qapp):
    dlg = FactionWarfareDialog(None)
    assert dlg.tabs.count() == 3
    assert dlg.table.columnCount() == 12
    assert dlg.btn_save.isEnabled() is False


def test_full_flow(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "gui.faction_warfare_dialog.async_call",
        lambda owner, fn, on_done, on_fail=None, name="": on_done(fn()))
    seen = []
    monkeypatch.setattr("gui.faction_warfare_dialog.info",
                        lambda *a, **k: seen.append(a))
    monkeypatch.setattr("gui.faction_warfare_dialog.ask_yes_no",
                        lambda *a, **k: True)
    root = _scenario(tmp_path)
    dlg = FactionWarfareDialog(None, str(root))
    dlg._analyze()
    assert dlg.table.rowCount() == 2
    assert dlg.chk_enabled.isChecked() is True
    # Talon (ligne 0) : prix niveau 1 min edite ; Zirax (ligne 1) garde son bloc
    dlg.table.item(0, 2).setText("95")
    dlg.table.item(1, 2).setText("20")
    dlg.chk_enabled.setChecked(False)
    dlg._save()
    text = (root / "Content/Configuration/FactionWarfare.ecf").read_text(
        encoding="utf-8")
    assert "Lvl1MinPrice: 95" in text
    assert "PlayFieldLvl1Min: 20" in text
    assert "EnableSpaceDefense: False" in text
    assert seen, "confirmation affichee"
    # re-scan : valeurs relues
    dlg._analyze()
    assert dlg.table.item(0, 2).text() == "95"
    assert dlg.table.item(1, 2).text() == "20"
