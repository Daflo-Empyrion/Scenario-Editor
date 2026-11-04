"""Dialogue « reparations automatiques » (gui/auto_repair_dialog.py) :
analyse puis application sur un faux workspace."""

from pathlib import Path

from PyQt6.QtWidgets import QMessageBox

BLOCKS = (
    "{ Block Id: 2, Name: Child, Ref: Base\n"
    "  TechTreeParent: Parent\n  TechTreeNames: Base\n  UnlockLevel: 5\n}\n"
    "{ Block Id: 1, Name: Base\n}\n"
    "{ Block Id: 3, Name: Parent\n  TechTreeNames: Base\n  UnlockLevel: 5\n}\n"
)
ITEMS = "{ Item Id: 9, Name: Thing\n  TechTreeNames: Base\n  UnlockLevel: 1\n}\n"


class _Cfg:
    def __init__(self, path):
        self.path = path
        self.extension = ".ecf"


class _Working:
    def __init__(self, files):
        self.configuration = [_Cfg(p) for p in files]


class _WS:
    def __init__(self, files):
        self.working = _Working(files)
        self.rescanned = 0

    def rescan_working(self):
        self.rescanned += 1


class _Status:
    def __init__(self, out):
        self.out = out

    def showMessage(self, message, _timeout=0):
        self.out.append(message)


class _MW:
    def __init__(self, files):
        self.workspace = _WS(files)
        self.messages = []
        self.undos = []
        self.reloaded = []

    def statusBar(self):
        return _Status(self.messages)

    def _push_workspace_undo(self, action):
        self.undos.append(action)

    def _reload_tab_if_open_and_unmodified(self, path):
        self.reloaded.append(path)


def test_analyse_lists_both_repairs(qapp, tmp_path):
    from gui.auto_repair_dialog import AutoRepairDialog
    b, i = tmp_path / "BlocksConfig.ecf", tmp_path / "ItemsConfig.ecf"
    b.write_bytes(BLOCKS.encode("utf-8"))
    i.write_bytes(ITEMS.encode("utf-8"))
    dlg = AutoRepairDialog(_MW([b, i]))
    text = dlg.report.toPlainText()
    assert "corriger" in text and "relever" in text
    assert dlg.btn_apply.isEnabled()


def test_apply_fixes_both_files(qapp, tmp_path, monkeypatch):
    from gui.auto_repair_dialog import AutoRepairDialog
    from core.ecf.ref_order import find_offenders
    from core.ecf.parser import parse_ecf_file
    from core.tech_tree_levels import remaining_violations
    b, i = tmp_path / "BlocksConfig.ecf", tmp_path / "ItemsConfig.ecf"
    b.write_bytes(BLOCKS.encode("utf-8"))
    i.write_bytes(ITEMS.encode("utf-8"))
    mw = _MW([b, i])
    dlg = AutoRepairDialog(mw)
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Yes)
    dlg._apply()
    assert find_offenders(parse_ecf_file(b)) == []
    assert remaining_violations(b, i, "") == []
    assert mw.workspace.rescanned == 1
    # seul BlocksConfig portait des corrections : un undo, un rechargement
    assert len(mw.undos) == 1 and mw.reloaded == [b]
