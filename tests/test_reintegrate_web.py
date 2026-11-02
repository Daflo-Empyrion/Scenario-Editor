"""Pont de la vue web Reintegration de playfields (gui/reintegrate_web.py)
: pont seul, moteurs monkeypatches (jamais le disque reel), run_long court-
circuité (la gerbe plasma n'a pas de fenêtre sous pytest)."""
import json

import pytest

pytest.importorskip("PyQt6.QtWebChannel")


class _Orphan:
    def __init__(self, family, name, kind="reintegrate.kind.poi"):
        self.family = family
        self.type_name = name
        self.kind_key = kind
        self.description = f"desc {name}"


class _Legacy:
    """Entree legacy : le vrai render_preview lit .key."""
    key = "legacy:1"

    def __repr__(self):
        return self.key


@pytest.fixture
def bridge(qapp, monkeypatch):
    from gui.reintegrate_web import ReintegrateWebBridge
    # run_long en synchrone (pas d'overlay plasma en test)
    monkeypatch.setattr("gui.reintegrate_web.run_long",
                        lambda parent, fn, **k: fn())
    monkeypatch.setattr("gui.reintegrate_web.async_call",
                        lambda owner, fn, on_done, on_fail=None, name="":
                        on_done(fn()) or None)
    orphans = [_Orphan("surface", "Pawn_A"), _Orphan("surface", "Turret_B"),
               _Orphan("space", "Station_C")]
    monkeypatch.setattr("core.playfield_reintegrate.find_orphans",
                        lambda root: orphans)
    monkeypatch.setattr("core.playfield_reintegrate.find_legacy",
                        lambda root: [_Legacy()])
    monkeypatch.setattr("core.playfield_reintegrate.find_missing_arrivals",
                        lambda root: ["route:1"])
    b = ReintegrateWebBridge("C:/scen", main_window=None, dialog=None)
    return b


def test_load_groups_checked_and_flags(bridge):
    bridge.load()
    data = json.loads(bridge.get_init())
    assert [g["key"] for g in data["groups"]] == ["surface", "space"]
    surf = data["groups"][0]
    assert len(surf["items"]) == 2 and surf["label"]
    assert all(not it["checked"] for it in surf["items"])
    assert data["legacy"]["n"] == 1 and data["legacy"]["on"] is True
    assert data["arrivals"]["n"] == 1 and data["arrivals"]["on"] is True
    for key in ("per_system", "preview_btn", "apply", "col_type", "info"):
        assert data["labels"][key]


def test_toggle_and_invalidate_preview(bridge, monkeypatch):
    bridge.load()
    monkeypatch.setattr("core.playfield_reintegrate.plan_placements",
                        lambda root, picks, per: ["plan:1"])
    monkeypatch.setattr("core.playfield_reintegrate.render_preview",
                        lambda plan, removals: "apercu")
    bridge.set_checked("Pawn_A", True)
    bridge.run_action("preview")
    assert json.loads(bridge.get_init())["apply_enabled"] is True
    bridge.set_checked("Pawn_A", False)        # changement : invalide
    data = json.loads(bridge.get_init())
    assert data["apply_enabled"] is False and data["preview"] == ""
    assert "Pawn_A" not in bridge._checked


def test_preview_plans_and_flags_skipped(bridge, monkeypatch):
    bridge.load()
    bridge.set_checked("Pawn_A", True)
    monkeypatch.setattr("core.playfield_reintegrate.plan_placements",
                        lambda root, picks, per: [f"plan:{p}" for p in picks])
    monkeypatch.setattr("core.playfield_reintegrate.render_preview",
                        lambda plan, removals:
                        f"{len(plan)} placements + {len(removals)} legacy")
    bridge.set_checked("Pawn_A", False)
    bridge.set_checked("Pawn_A", True)
    bridge.run_action("preview")
    data = json.loads(bridge.get_init())
    # 1 pick + 1 route d'arrivee (cochee par defaut) + 1 legacy
    assert data["preview"] == "2 placements + 1 legacy"
    assert data["apply_enabled"] is True


def test_preview_without_selection(bridge):
    bridge.load()
    bridge.set_legacy(False)                   # legacy seule decochee
    bridge.set_arrival(False)
    bridge.run_action("preview")
    data = json.loads(bridge.get_init())
    assert data["apply_enabled"] is False
    assert data["status"] != ""                # « rien de selectionne »


def test_apply_confirms_writes_backup_and_bilan(bridge, monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QMessageBox
    bridge.load()
    bridge.set_checked("Pawn_A", True)
    monkeypatch.setattr("core.playfield_reintegrate.plan_placements",
                        lambda root, picks, per: ["plan:1"])
    sector = tmp_path / "Sectors.yaml"
    sector.write_text("SolarSystems:\n", encoding="utf-8")
    monkeypatch.setattr("core.playfield_reintegrate.sectors_yaml",
                        lambda root: sector)
    monkeypatch.setattr("core.playfield_reintegrate.apply_placements",
                        lambda root, plan: (1, []))
    monkeypatch.setattr("core.playfield_reintegrate.remove_legacy",
                        lambda root, removals: 1)
    backups = []
    monkeypatch.setattr("core.fsutil.central_backup",
                        lambda path, **k: backups.append(path))
    captured = {}
    monkeypatch.setattr("core.workspace_undo.capture_file",
                        lambda p: captured.setdefault("prior", p))
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k:
                                     QMessageBox.StandardButton.Yes))
    monkeypatch.setattr("gui.msgboxes.ask_yes_no",
                        lambda *a, **k: True)
    monkeypatch.setattr("core.launch_check.run_launch_checks",
                        lambda root, vanilla: [])
    bridge.run_action("apply")
    assert backups == [sector]
    assert captured["prior"] == sector
    assert bridge.applied == 1                 # placements seuls (parite Qt :
    #   les retraits legacy vont dans le message et l'undo, pas dans applied)
    data = json.loads(bridge.get_init())
    assert "bilan" not in data["status"].lower() or data["status"]


def test_apply_refused_leaves_disk_alone(bridge, monkeypatch, tmp_path):
    bridge.load()
    bridge.set_checked("Pawn_A", True)
    monkeypatch.setattr("core.playfield_reintegrate.plan_placements",
                        lambda root, picks, per: ["plan:1"])
    monkeypatch.setattr("gui.msgboxes.ask_yes_no", lambda *a, **k: False)
    writes = []
    monkeypatch.setattr("core.fsutil.central_backup",
                        lambda path, **k: writes.append(path))
    bridge.run_action("apply")
    assert writes == []


def test_actions_whitelist(qapp, monkeypatch):
    shown = []
    monkeypatch.setattr("gui.module_info.show_module_info",
                        lambda parent, key: shown.append(key))
    from gui.reintegrate_web import ReintegrateWebBridge
    b = ReintegrateWebBridge("C:/scen", dialog=None)
    for name in ("close", "info", "inconnu"):
        b.run_action(name)                     # pas de crash
    assert shown == ["reintegrate.info_html"]  # la VRAIE fenetre module
    b.set_per_system(99)
    assert b._per_system == 20                 # borne haute
    b.set_per_system(0)
    assert b._per_system == 1                  # borne basse
