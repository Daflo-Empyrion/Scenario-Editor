"""Pont de la vue web Look cartoon (gui/cartoon_web.py) : pont seul,
async_call synchrone et core.cartoon_look monkeypatché (jamais le disque
reel) — même parti pris que les autres ponts."""
import json

import pytest

pytest.importorskip("PyQt6.QtWebChannel")


@pytest.fixture
def bridge(qapp, monkeypatch):
    from gui.cartoon_web import CartoonWebBridge
    monkeypatch.setattr("gui.cartoon_web.async_call",
                        lambda owner, fn, on_done, on_fail=None, name="":
                        on_done(fn()) or None)
    monkeypatch.setattr("core.cartoon_look.list_backups",
                        lambda: [])
    monkeypatch.setattr("core.cartoon_look.load_stored_preset",
                        lambda: {"saturation": 0.9})
    b = CartoonWebBridge(dialog=None, working_root="C:/scen")
    return b


def test_get_init_payload_carries_factors(bridge):
    data = json.loads(bridge.get_init())
    keys = [f["key"] for f in data["factors"]]
    assert "saturation" in keys and len(keys) == 8
    sat = next(f for f in data["factors"] if f["key"] == "saturation")
    assert sat["label"] and sat["tip"] and sat["min"] < sat["max"]
    for key in ("scenario", "browse", "force", "preview", "apply",
                "defaults", "colors", "backups", "restore"):
        assert data["labels"][key]
    assert data["path"] == "C:/scen"


def test_set_factor_clamps_to_spec(bridge):
    bridge.set_factor("saturation", 99.0)
    data = json.loads(bridge.get_init())
    sat = next(f for f in data["factors"] if f["key"] == "saturation")
    assert sat["value"] == sat["max"]
    bridge.set_factor("cle_inconnue", 1.0)         # ignore silencieusement


def test_defaults_reset_factors(bridge):
    bridge.set_factor("saturation", 0.1)
    bridge.run_action("defaults")
    data = json.loads(bridge.get_init())
    from core.cartoon_look import DEFAULT_PRESET
    assert next(f for f in data["factors"]
                if f["key"] == "saturation")["value"] == DEFAULT_PRESET["saturation"]


def test_meta_loads_playfields_and_preset(bridge, tmp_path, monkeypatch):
    pfs = tmp_path / "Playfields"
    (pfs / "Alpha").mkdir(parents=True)
    (pfs / "+Hidden").mkdir()
    from core.cartoon_look import TARGET_NAMES
    (pfs / "Alpha" / TARGET_NAMES[0]).write_text("x", encoding="utf-8")
    monkeypatch.setattr("core.cartoon_look.list_backups",
                        lambda: [])
    bridge._path = str(tmp_path)
    bridge._refresh_meta()
    data = json.loads(bridge.get_init())
    assert data["playfields"] == ["Alpha"]
    assert data["pf"] == "Alpha"
    # preset stocke applique aux facteurs
    sat = next(f for f in data["factors"] if f["key"] == "saturation")
    assert sat["value"] == 0.9


def test_preview_dry_run_report(bridge, monkeypatch):
    calls = {}
    monkeypatch.setattr("core.cartoon_look.save_preset",
                        lambda preset: calls["saved"] == preset or None)
    monkeypatch.setattr("core.cartoon_look.run_preset",
                        lambda scenario, dry_run, force, preset:
                        {"touched": [("Playfields/Alpha/terrain.ecf", 12)],
                         "invalid": [], "total": 12, "dry_run": True})
    bridge.run_action("preview")
    data = json.loads(bridge.get_init())
    assert data["report"].startswith("+ Playfields/Alpha/terrain.ecf")
    assert data["running"] is False


def test_apply_persists_preset_and_reports(bridge, monkeypatch):
    saved = []
    presets_seen = []
    monkeypatch.setattr("core.cartoon_look.save_preset",
                        lambda preset: saved.append(preset))
    monkeypatch.setattr("core.cartoon_look.run_preset",
                        lambda scenario, dry_run, force, preset:
                        presets_seen.append(preset)
                        or {"touched": [("a", 1)], "invalid": [], "total": 1,
                            "dry_run": False, "backup_dir": "C:/bak",
                            "prod": False})
    bridge.run_action("apply")
    # le preset PERSISTE est celui passe au moteur (apres coup, la meta se
    # recharge et reapplique le preset stocke : ne pas comparer apres)
    assert saved and saved[0] is presets_seen[0]
    data = json.loads(bridge.get_init())
    assert "C:/bak" in data["status"]


def test_apply_blocked_and_error_paths(bridge, monkeypatch):
    monkeypatch.setattr("core.cartoon_look.run_preset",
                        lambda scenario, dry_run, force, preset:
                        {"marker_blocked": True})
    bridge.run_action("apply")
    assert json.loads(bridge.get_init())["status"]
    monkeypatch.setattr("core.cartoon_look.run_preset",
                        lambda scenario, dry_run, force, preset:
                        {"error": True})
    bridge.run_action("apply")
    assert json.loads(bridge.get_init())["status"]


def test_restore_needs_confirm_and_names(bridge, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    asked = []
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k:
                                     asked.append(True)
                                     or QMessageBox.StandardButton.No))
    monkeypatch.setattr("core.cartoon_look.restore_backup",
                        lambda scenario, d: {"copied": 3})
    bridge.run_action("restore")
    assert asked == []                     # aucun backup : rien demande
    bridge._backups = {"passe1": "C:/bak1"}
    bridge._backup = "passe1"
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k:
                                     asked.append(True)
                                     or QMessageBox.StandardButton.No))
    bridge.run_action("restore")           # Non : rien
    assert asked == [True]
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k:
                                     asked.append(True)
                                     or QMessageBox.StandardButton.Yes))
    bridge.run_action("restore")           # Oui : restaure
    assert asked == [True, True]
    assert "3" in json.loads(bridge.get_init())["status"]


def test_actions_whitelist(qapp, monkeypatch):
    shown = []
    monkeypatch.setattr("gui.module_info.show_module_info",
                        lambda parent, key: shown.append(key))
    from gui.cartoon_web import CartoonWebBridge
    b = CartoonWebBridge(dialog=None, working_root="")
    for name in ("close", "info", "inconnu", "refresh_meta"):
        b.run_action(name)                 # pas de crash, liste blanche
    assert shown == ["cartoon.info_html"]  # la VRAIE fenetre module
