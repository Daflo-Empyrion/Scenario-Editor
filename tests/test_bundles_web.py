"""Pont de la vue web Comparateur de bundles (gui/bundles_web.py) : pont
seul, compare_bundles monkeypatché — même parti pris que les autres ponts."""
import json

import pytest

pytest.importorskip("PyQt6.QtWebChannel")


class _Diff:
    def __init__(self):
        self.na = 2
        self.nb = 3
        self.added = {"new.bundle": "Texture2D"}
        self.removed = {"old.bundle": "Texture2D"}
        self.changed = {"mod.bundle": ("Texture2D", "Shader")}
        self.same = 10


@pytest.fixture
def bridge(qapp, monkeypatch):
    from gui.bundles_web import BundlesWebBridge
    # async_call en SYNCHRONE : le vrai thread daemon delivrerait son
    # signal apres le teardown du pont (crash natif) et les assertions
    # courraient avant la livraison — meme garde que les autres ponts
    monkeypatch.setattr("gui.bundles_web.async_call",
                        lambda owner, fn, on_done, on_fail=None, name="":
                        on_done(fn()) or None)
    b = BundlesWebBridge(dialog=None)
    monkeypatch.setattr(b, "_compute",
                        lambda pa, pb: (_Diff(), ""))
    return b


def test_get_init_payload(qapp):
    from gui.bundles_web import BundlesWebBridge
    data = json.loads(BundlesWebBridge(dialog=None).get_init())
    assert data["paths"] == {"a": "", "b": ""}
    assert data["rows"] == [] and data["export_enabled"] is False
    for key in ("intro", "path_a", "browse", "compare", "col_status",
                "export"):
        assert data["labels"][key]


def test_run_without_paths(qapp):
    from gui.bundles_web import BundlesWebBridge
    bridge = BundlesWebBridge(dialog=None)
    seen = []
    bridge.data_changed.connect(seen.append)
    bridge.run()
    state = json.loads(seen[-1])
    assert state["running"] is False and state["status"] != ""


def test_run_fills_rows_sorted_with_sev(qapp, bridge):
    bridge.set_path("a", "C:/a.bundle")
    bridge.set_path("b", "C:/b.bundle")
    bridge.run()
    data = json.loads(bridge.get_init())
    assert data["export_enabled"] is True
    assert [r["sev"] for r in data["rows"]] == \
        ["added", "removed", "changed"]
    assert data["rows"][1]["ta"] == "Texture2D"    # removed : type A
    assert data["rows"][2]["tb"] == "Shader"       # changed : type B
    assert "2" in data["status"] and "10" in data["status"]


def test_run_empty_container_warning(qapp, bridge):
    from core.i18n import t
    d = _Diff()
    d.na = 0
    bridge._compute = lambda pa, pb: (d, "")
    bridge.set_path("a", "C:/a.bundle")
    bridge.set_path("b", "C:/b.bundle")
    bridge.run()
    # container vide : l'avertissement precedence la synthese
    assert json.loads(bridge.get_init())["status"].startswith(t("bundles.empty"))


def test_error_path(qapp, monkeypatch):
    from gui.bundles_web import BundlesWebBridge
    monkeypatch.setattr("gui.bundles_web.async_call",
                        lambda owner, fn, on_done, on_fail=None, name="":
                        on_done(fn()) or None)
    bridge = BundlesWebBridge(dialog=None)
    bridge._compute = lambda pa, pb: (None, "boom")
    bridge.set_path("a", "C:/a")
    bridge.set_path("b", "C:/b")
    bridge.run()
    data = json.loads(bridge.get_init())
    assert data["export_enabled"] is False
    assert "boom" in data["status"]


def test_export_csv(qapp, bridge, tmp_path, monkeypatch):
    bridge.set_path("a", "C:/alpha.bundle")
    bridge.set_path("b", "C:/b.bundle")
    bridge.run()
    out = tmp_path / "diff.csv"
    monkeypatch.setattr("PyQt6.QtWidgets.QFileDialog.getSaveFileName",
                        staticmethod(lambda *a, **k: (str(out), "")))
    bridge.export()
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 4                          # entete + 3 lignes
    assert lines[0].count(";") == 3
    assert "mod.bundle" in lines[3]


def test_export_without_diff_is_noop(qapp, tmp_path):
    from gui.bundles_web import BundlesWebBridge
    BundlesWebBridge(dialog=None).export()
    assert list(tmp_path.glob("*.csv")) == []


def test_actions_whitelist(qapp):
    from gui.bundles_web import BundlesWebBridge
    b = BundlesWebBridge(dialog=None)
    b.run_action("close")            # dialog=None : pas de crash
    b.run_action("inconnu")          # liste blanche : ignore
    b.browse("zzz")                  # cle inconnue : ignore (dialog=None,
    #                                  le QFileDialog natif ne s'ouvre pas ici)
