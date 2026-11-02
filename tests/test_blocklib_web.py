"""Pont de la vue web Bibliotheque de blocs (gui/blocklib_web.py) : pont
seul, logique metier partagee avec le dialogue Qt (fonctions module)."""
import json

import pytest

pytest.importorskip("PyQt6.QtWebChannel")


@pytest.fixture
def bridge(qapp, monkeypatch):
    from gui.blocklib_web import BlocklibWebBridge
    store = {"p1": "CargoBox -- Helios", "p2": "Thruster -- T2 SV"}
    monkeypatch.setattr("core.block_library.list_snippets",
                        lambda: [{"name": n, "path": p}
                                 for p, n in store.items()])
    monkeypatch.setattr("core.block_library.load_snippet",
                        lambda p: f"[texte de {p}]")
    deleted = []
    monkeypatch.setattr("core.block_library.delete_snippet",
                        lambda p: deleted.append(p) or store.pop(p))
    inserted = []

    class _MW:
        workspace = None
        opened = []

    def _fake_insert(mw, path, parent):
        inserted.append(path)
        mw.opened.append("msgbox")

    monkeypatch.setattr("gui.block_library_dialog.insert_snippet",
                        _fake_insert)
    monkeypatch.setattr("gui.block_library_dialog.export_block",
                        lambda mw, parent: inserted.append("export"))
    b = BlocklibWebBridge(_MW(), dialog=None)
    b._fake = {"deleted": deleted, "inserted": inserted}
    return b


def test_payload_lists_snippets(bridge):
    data = json.loads(bridge.get_init())
    assert [s["name"] for s in data["snippets"]] == \
        ["CargoBox -- Helios", "Thruster -- T2 SV"]
    assert data["selected"] == -1 and data["preview"] == ""
    for key in ("hint", "search", "insert", "delete", "export", "refresh"):
        assert data["labels"][key]


def test_select_loads_preview_light_state(bridge):
    bridge.get_init()
    seen = []
    bridge.data_changed.connect(seen.append)
    bridge.select(1)
    state = json.loads(seen[-1])
    assert "snippets" not in state                 # etat LEGER
    assert state["selected"] == 1
    assert state["preview"] == "[texte de p2]"


def test_select_out_of_range_ignored(bridge):
    bridge.get_init()
    bridge.select(99)
    bridge.select(-1)
    assert bridge._selected == -1


def test_delete_uses_shared_confirmed_function(bridge, monkeypatch):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QMessageBox
    bridge.get_init()
    bridge.select(0)
    # confirmation « Oui » : la fonction PARTAGEE fait la suppression
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    bridge.run_action("delete")
    assert bridge._fake["deleted"] == ["p1"]
    data = json.loads(bridge.get_init())
    assert data["selected"] == -1                  # selection purgee
    assert len(data["snippets"]) == 1              # re-charge apres deletion

    # refus : rien n'est supprime
    bridge.select(0)
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    bridge.run_action("delete")
    assert bridge._fake["deleted"] == ["p1"]


def test_insert_and_export_replay_shared_logic(bridge):
    bridge.get_init()
    bridge.select(1)
    bridge.run_action("insert")
    assert bridge._fake["inserted"] == ["p2"]      # fonction partagee
    bridge.run_action("export")
    assert bridge._fake["inserted"] == ["p2", "export"]
    bridge.run_action("n_importe")                 # liste blanche : ignore
    assert len(bridge._fake["inserted"]) == 2
