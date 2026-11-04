"""Dialogue « declarations inactives » (gui/inactive_declarations_dialog.py) :
construction + chemin connecte analyse -> application, sur un faux workspace."""

from pathlib import Path

from PyQt6.QtWidgets import QMessageBox

SAMPLE = (
    "{ Item Id: 1, Name: Active\r\n}\r\n"
    "# DOUBLON DE NOM \"Mine\" : variante conservee en commentaire.\r\n"
    "# { Item Id: 1, Name: Mine\r\n# }\r\n"
)


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
        self.undo = None
        self.reloaded = None

    def statusBar(self):
        return _Status(self.messages)

    def _push_workspace_undo(self, action):
        self.undo = action

    def _reload_tab_if_open_and_unmodified(self, path):
        self.reloaded = path


def test_dialog_lists_ecf_files(qapp, tmp_path):
    from gui.inactive_declarations_dialog import InactiveDeclarationsDialog
    path = tmp_path / "ItemsConfig.ecf"
    path.write_bytes(SAMPLE.encode("utf-8"))
    dlg = InactiveDeclarationsDialog(_MW([path]))
    assert dlg.combo.count() == 1
    assert dlg.combo.currentData() == str(path)


def test_analyse_then_apply(qapp, tmp_path, monkeypatch):
    from gui.inactive_declarations_dialog import InactiveDeclarationsDialog
    path = tmp_path / "ItemsConfig.ecf"
    path.write_bytes(SAMPLE.encode("utf-8"))
    mw = _MW([path])
    dlg = InactiveDeclarationsDialog(mw)
    dlg._analyse()
    assert "Mine" in dlg.report.toPlainText()
    assert dlg.btn_apply.isEnabled()
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Yes)
    dlg._apply()
    text = path.read_bytes().decode("utf-8")
    assert "{ Item Name: Mine" in text
    assert "# { Item Id: 1, Name: Mine" not in text
    assert mw.workspace.rescanned == 1
    assert mw.undo is not None and mw.reloaded == path
