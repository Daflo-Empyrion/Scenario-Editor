"""Pont de la vue web Bilan F5 (gui/health_web.py) : pont seul avec une
fausse fenêtre principale, async_call monkeypatché en synchrone — même
parti pris que test_coherence_web.py (jamais de QWebEngineView reel)."""
import json
import types

import pytest


class _FakeMW:
    """Minimum du contrat main_window consomme par le pont."""
    def __init__(self):
        self.workspace = types.SimpleNamespace(working_root="C:/scen")
        self.opened = []

    def ensure_analysis_fresh_tabs(self):
        self.opened.append("fresh_tabs")

    def check_cross_references_dialog(self):
        self.opened.append("refs")

    def validate_scenario_dialog(self):
        self.opened.append("validation")

    def check_pending_conflicts_dialog(self):
        self.opened.append("pending")

    def _open_orphan_dialog(self):
        self.opened.append("orphans")


def _sync_async(monkeypatch):
    monkeypatch.setattr("gui.health_web.async_call",
                        lambda owner, fn, on_done, on_fail=None, name="":
                        on_done(fn()))


def _bridge():
    from gui.health_web import HealthWebBridge
    mw = _FakeMW()
    return HealthWebBridge(mw, dialog=None), mw


CLEAN = {"refs": 0, "validation": 0, "pending": 0, "orphans": 0,
         "launch_errors": 0}


def test_run_collects_and_builds_rows(qapp, tmp_path, monkeypatch):
    _sync_async(monkeypatch)
    monkeypatch.setattr("gui.health_check_dialog.collect_all_checks",
                        lambda ws: {"refs": 1, "validation": 0, "pending": 0,
                                    "orphans": 2, "launch_errors": 0})
    bridge, mw = _bridge()
    assert json.loads(bridge.get_init())["has_run"] is False   # la page
    bridge.run()                        # declenchera check_all au boot
    data = json.loads(bridge.get_init())
    assert mw.opened == ["fresh_tabs"]             # garde VERIF-001/009
    assert data["has_run"] is True and data["running"] is False
    assert len(data["rows"]) == 5
    refs = next(r for r in data["rows"] if r["key"] == "refs")
    orphans = next(r for r in data["rows"] if r["key"] == "orphans")
    assert refs["ok"] is False and "1" in refs["text"]
    assert orphans["ok"] is False                  # informatif mais affiche
    assert data["summary_state"] == "ko"
    # orphelins EXCLU du total (parite Qt) : seul refs compte -> probleme 1
    assert data["labels"]["intro"] and data["labels"]["check_all"]


def test_clean_scenario_is_all_ok(qapp, monkeypatch):
    _sync_async(monkeypatch)
    monkeypatch.setattr("gui.health_check_dialog.collect_all_checks",
                        lambda ws: dict(CLEAN))
    bridge, mw = _bridge()
    bridge.run()
    data = json.loads(bridge.get_init())
    assert all(r["ok"] for r in data["rows"])
    assert data["summary_state"] == "ok"
    assert data["summary"]


def test_detail_actions_guarded_like_qt(qapp, monkeypatch):
    """Parite Qt : le bouton « Voir le detail » est inactive pour une
    categorie saine — l'action web ne doit rien ouvrir non plus."""
    _sync_async(monkeypatch)
    bridge, mw = _bridge()
    bridge._counts = dict(CLEAN)
    bridge.run_action("open_refs")
    bridge.run_action("open_unknown")
    assert mw.opened == []
    bridge._counts = dict(CLEAN, refs=3)
    bridge.run_action("open_refs")
    assert mw.opened == ["refs"]


def test_launch_detail_opens_real_window(qapp, monkeypatch):
    bridge, mw = _bridge()
    bridge._counts = dict(CLEAN, launch_errors=2)
    shown = []

    class _Stub:
        def __init__(self, parent, working_root=""):
            shown.append(parent)

        def show(self):
            shown.append("show")

    monkeypatch.setattr("gui.launch_check_dialog.LaunchCheckDialog", _Stub)
    bridge.run_action("open_launch")
    assert shown[0] is mw and shown[1] == "show"


def test_run_without_workspace_is_garded(qapp):
    bridge, _mw = _bridge()
    bridge._mw.workspace = None
    seen = []
    bridge.data_changed.connect(seen.append)
    bridge.run()
    data = json.loads(seen[-1])
    assert data["running"] is False
    assert data["summary_state"] == "ko"       # message « projet requis »


def test_routing_stub_covers_both_branches(monkeypatch):
    """Contrat d'entree : web quand is_available(), Qt sinon — stubbe les
    DEUX dialogues, jamais de vrai constructeur (piege offscreen)."""
    from gui.main_window import MainWindow
    shown = []

    class _Stub:
        def __init__(self, *a, **k):
            pass

        def show(self):
            shown.append(True)

    monkeypatch.setattr("gui.health_web.HealthWebDialog", _Stub)
    monkeypatch.setattr("gui.health_check_dialog.HealthCheckDialog", _Stub)

    monkeypatch.setattr("gui.health_web.is_available", lambda: True)
    MainWindow._open_health_check_dialog(
        types.SimpleNamespace(workspace=object()))
    assert shown == [True]

    monkeypatch.setattr("gui.health_web.is_available", lambda: False)
    MainWindow._open_health_check_dialog(
        types.SimpleNamespace(workspace=object()))
    assert shown == [True, True]
