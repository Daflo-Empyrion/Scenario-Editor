"""Pont de la vue web Fiche du scenario (gui/digest_web.py) : pont seul
avec async_call monkeypatché en synchrone et la fixture scenario de
test_scenario_digest — même parti pris que test_coherence_web.py."""
import json
from pathlib import Path

from test_scenario_digest import _scenario


def _sync_async(monkeypatch):
    monkeypatch.setattr("gui.digest_web.async_call",
                        lambda owner, fn, on_done, on_fail=None, name="":
                        on_done(fn()))


def test_get_init_payload(qapp):
    from gui.digest_web import DigestWebBridge
    data = json.loads(DigestWebBridge(None, working_root="C:/scen").get_init())
    assert data["path"] == "C:/scen"
    assert data["text"] == "" and data["running"] is False
    assert data["export_enabled"] is False
    # tout texte visible passe par t() : libelles presents
    for key in ("scenario", "browse", "run", "export", "info"):
        assert data["labels"][key]


def test_run_without_scenario(qapp, monkeypatch):
    from gui.digest_web import DigestWebBridge
    bridge = DigestWebBridge(None, working_root="")
    seen = []
    bridge.data_changed.connect(seen.append)
    bridge.run()
    assert seen and json.loads(seen[-1])["running"] is False   # rien lance
    assert json.loads(seen[-1])["status"] != ""                # message requis


def test_run_renders_markdown_and_enables_export(qapp, tmp_path, monkeypatch):
    from gui.digest_web import DigestWebBridge
    root, vanilla = _scenario(tmp_path)
    _sync_async(monkeypatch)
    monkeypatch.setattr("gui.digest_web.get_vanilla_content_path",
                        lambda: str(vanilla / "Content"))
    bridge = DigestWebBridge(None, working_root=str(root))
    bridge.run()
    data = json.loads(bridge.get_init())
    assert data["running"] is False
    assert data["export_enabled"] is True
    assert "## FR" in data["text"] and "## EN" in data["text"]
    assert "Contenu joueur" in data["text"]
    assert data["status"]


def test_export_writes_markdown_file(qapp, tmp_path, monkeypatch):
    from gui.digest_web import DigestWebBridge
    root, vanilla = _scenario(tmp_path)
    _sync_async(monkeypatch)
    monkeypatch.setattr("gui.digest_web.get_vanilla_content_path",
                        lambda: str(vanilla / "Content"))
    bridge = DigestWebBridge(None, working_root=str(root))
    bridge.run()
    out = tmp_path / "fiche.md"
    monkeypatch.setattr("PyQt6.QtWidgets.QFileDialog.getSaveFileName",
                        staticmethod(lambda *a, **k: (str(out), "")))
    bridge.export()
    assert out.is_file()
    assert out.read_text(encoding="utf-8") == json.loads(
        bridge.get_init())["text"]
    assert str(out) in json.loads(bridge.get_init())["status"]


def test_export_without_generation_is_noop(qapp, tmp_path):
    from gui.digest_web import DigestWebBridge
    DigestWebBridge(None, working_root=str(tmp_path)).export()
    assert list(Path(tmp_path).glob("*.md")) == []


def test_actions_whitelist_and_info_window(qapp, monkeypatch):
    from gui.digest_web import DigestWebBridge
    seen = []
    monkeypatch.setattr("gui.module_info.show_module_info",
                        lambda parent, key: seen.append((parent, key)))
    bridge = DigestWebBridge(None, working_root="")
    bridge.run_action("info")
    assert seen[0][1] == "digest.info_html"      # la VRAIE fenetre module
    bridge.run_action("close")                   # dialog=None : pas de crash
    bridge.run_action("action_inconnue")         # liste blanche : ignore
    bridge.set_path("C:/x")
    assert json.loads(bridge.get_init())["path"] == "C:/x"
