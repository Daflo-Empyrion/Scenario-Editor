"""Pont de la vue web Contrôle de cohérence (gui/coherence_web.py) : pont
seul (jamais de QWebEngineView sous offscreen), async_call monkeypatché en
synchrone comme dans test_coherence_dialog.py."""
import json

ITEMS = """{ Item Name: RockDust
  MarketPrice: 2
}
{ Item Name: PistolA
  MarketPrice: 100
}
"""
TEMPLATES = """{ Template Name: PistolA
  CraftTime: 10
  { Child Inputs
    RockDust: 10
  }
}
"""


def _sync_async(monkeypatch):
    monkeypatch.setattr("gui.coherence_web.async_call",
                        lambda owner, fn, on_done, on_fail=None, name="":
                        on_done(fn()))


def _scenario(tmp_path):
    cdir = tmp_path / "Content" / "Configuration"
    cdir.mkdir(parents=True)
    (cdir / "ItemsConfig.ecf").write_text(ITEMS, encoding="utf-8")
    (cdir / "Templates.ecf").write_text(TEMPLATES, encoding="utf-8")
    (cdir / "BlocksConfig.ecf").write_text(
        "{ Block Id: 500, Name: Pillar\n  MarketPrice: 40\n}\n",
        encoding="utf-8")
    return str(tmp_path)


def _bridge(working_root=""):
    from gui.coherence_web import CoherenceWebBridge
    return CoherenceWebBridge(None, working_root=working_root)


def test_get_init_payload(qapp):
    data = json.loads(_bridge("C:/scen").get_init())
    assert data["path"] == "C:/scen"
    assert data["rows"] == [] and data["running"] is False
    assert data["export_enabled"] is False
    assert data["status"]                        # accueil = coh.hint
    # tout texte visible passe par t() : libelles presents
    for key in ("scenario", "browse", "analyze", "export", "col_domain"):
        assert data["labels"][key]


def test_run_without_scenario(qapp, monkeypatch):
    bridge = _bridge("")
    seen = []
    bridge.data_changed.connect(seen.append)
    bridge.run()
    data = json.loads(seen[-1])
    assert data["running"] is False          # rien lance
    assert data["status"] != ""              # message « scenario requis »


def test_run_fills_rows_and_enables_export(qapp, tmp_path, monkeypatch):
    _sync_async(monkeypatch)
    bridge = _bridge(_scenario(tmp_path))
    bridge.run()
    data = json.loads(bridge.get_init())
    assert len(data["rows"]) >= 4
    assert data["export_enabled"] is True
    assert data["running"] is False
    assert "Termin" in data["status"]
    # tri par severite : error avant warning avant info
    order = {"error": 0, "warning": 1, "info": 2}
    sevs = [order[r["sev_key"]] for r in data["rows"]]
    assert sevs == sorted(sevs)
    assert all(r["section"] for r in data["rows"])   # libelles presents


def test_export_csv(qapp, tmp_path, monkeypatch):
    _sync_async(monkeypatch)
    bridge = _bridge(_scenario(tmp_path))
    bridge.run()
    out = tmp_path / "export.csv"
    monkeypatch.setattr("PyQt6.QtWidgets.QFileDialog.getSaveFileName",
                        staticmethod(lambda *a, **k: (str(out), "")))
    bridge.export()
    text = out.read_bytes().decode("utf-8-sig")
    lines = text.strip().splitlines()
    assert len(lines) >= 5                       # entete + constatations
    assert lines[0].count(";") == 4
    assert any("PistolA" in line for line in lines)   # exemples exportes
    assert str(out) in json.loads(bridge.get_init())["status"]


def test_browse_updates_path_and_pushes(qapp, tmp_path, monkeypatch):
    bridge = _bridge("")
    seen = []
    bridge.data_changed.connect(seen.append)
    monkeypatch.setattr("PyQt6.QtWidgets.QFileDialog.getExistingDirectory",
                        staticmethod(lambda *a, **k: str(tmp_path)))
    bridge.browse()
    assert json.loads(seen[-1])["path"] == str(tmp_path)


def test_actions_whitelist_and_close_without_dialog(qapp):
    _bridge().run_action("action_inconnue")      # ignore, pas de crash
    _bridge().run_action("close")                # dialog=None : pas de crash
    _bridge().run_action("export")               # sans rapport : no-op
