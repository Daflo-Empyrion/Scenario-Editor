"""Jetons de quete (gui/token_config_dialog.py) : construction et chemin
CONNECTE scan -> edition du nom -> bascule de drapeau -> nouveau jeton ->
enregistrement (ecriture reelle). Async synchrone, boites patchees."""

from pathlib import Path

from PyQt6.QtCore import Qt

from gui.token_config_dialog import TokenConfigDialog

TOKENS = """# doc a PRESERVER
{ Token Id: 4001, Name: Carte Titan
  Description: Carte du vaisseau.
}
"""


def _scenario(tmp_path: Path) -> Path:
    conf = tmp_path / "Content" / "Configuration"
    conf.mkdir(parents=True)
    (conf / "TokenConfig.ecf").write_text(TOKENS, encoding="utf-8")
    return tmp_path


def test_dialog_builds(qapp):
    dlg = TokenConfigDialog(None)
    assert dlg.table.columnCount() == 7
    assert dlg.btn_new.isEnabled() is False
    assert dlg.btn_save.isEnabled() is False


def test_full_flow(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "gui.token_config_dialog.async_call",
        lambda owner, fn, on_done, on_fail=None, name="": on_done(fn()))
    seen = []
    monkeypatch.setattr("gui.token_config_dialog.info",
                        lambda *a, **k: seen.append(a))
    monkeypatch.setattr("gui.token_config_dialog.ask_yes_no",
                        lambda *a, **k: True)
    root = _scenario(tmp_path)
    dlg = TokenConfigDialog(None, str(root))
    dlg._analyze()
    assert dlg.table.rowCount() == 1
    assert dlg.btn_save.isEnabled() is True

    # edition du nom par la cellule
    dlg.table.item(0, 1).setText("Carte Titan v2")
    # bascule d'un drapeau
    dlg.table.item(0, 4).setCheckState(Qt.CheckState.Checked)
    # creation d'un jeton a Id libre
    dlg._create()
    dlg.edit_filter.setText("")
    assert dlg.table.rowCount() == 2

    dlg._save()
    text = (root / "Content/Configuration/TokenConfig.ecf").read_text(
        encoding="utf-8")
    assert "# doc a PRESERVER" in text
    assert "Name: Carte Titan v2" in text
    assert "RemoveOnUse: true" in text
    assert "Token Id: 4002" in text
    assert seen, "message de confirmation"
