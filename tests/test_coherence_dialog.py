"""Dialogue Contrôle de cohérence global (gui/coherence_dialog.py) :
construction, chemin câblé au menu Outils, flux analyse -> table."""

from gui.coherence_dialog import CoherenceDialog

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


def test_dialog_builds(qapp):
    dlg = CoherenceDialog(None)
    assert dlg.table.columnCount() == 5
    assert dlg.btn_run.isEnabled() and not dlg.btn_export.isEnabled()


def test_menu_path_and_flow(qapp, tmp_path, monkeypatch):
    cdir = tmp_path / "Content" / "Configuration"
    cdir.mkdir(parents=True)
    (cdir / "ItemsConfig.ecf").write_text(ITEMS, encoding="utf-8")
    (cdir / "Templates.ecf").write_text(TEMPLATES, encoding="utf-8")
    (cdir / "BlocksConfig.ecf").write_text(
        "{ Block Id: 500, Name: Pillar\n  MarketPrice: 40\n}\n",
        encoding="utf-8")
    monkeypatch.setattr("gui.coherence_dialog.async_call",
                        lambda owner, fn, on_done, on_fail=None, name="":
                        on_done(fn()))
    # chemin menu : _open_coherence_dialog instancie avec le working root
    from gui.main_window import MainWindow
    win = MainWindow()
    win.workspace = None
    calls = {}

    class _Stub:
        def __init__(self, parent, working_root=""):
            calls["root"] = working_root

        def exec(self):
            calls["exec"] = True

    monkeypatch.setattr("gui.coherence_dialog.CoherenceDialog", _Stub)
    win._open_coherence_dialog()
    assert calls == {"root": "", "exec": True}
    win.close()

    # flux analyse -> table remplie
    dlg = CoherenceDialog(None, working_root=str(tmp_path))
    dlg._analyze()
    assert dlg.table.rowCount() >= 4
    assert dlg.btn_export.isEnabled()
    assert "Terminé" in dlg.status_label.text() or "Termin" in dlg.status_label.text()
