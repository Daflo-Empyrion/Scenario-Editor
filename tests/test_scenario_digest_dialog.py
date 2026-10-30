"""Dialogue Fiche du scenario (gui/scenario_digest_dialog.py) :
construction et chemin connecte (generation -> apercu -> export .md)."""

from pathlib import Path

from gui.scenario_digest_dialog import ScenarioDigestDialog

from test_scenario_digest import _scenario


def test_dialog_builds(qapp):
    dlg = ScenarioDigestDialog(None)
    assert dlg.windowTitle()
    assert dlg.btn_export.isEnabled() is False
    assert dlg.preview.isReadOnly() is True


def test_full_flow(qapp, tmp_path, monkeypatch):
    root, vanilla = _scenario(tmp_path)
    monkeypatch.setattr(
        "gui.scenario_digest_dialog.async_call",
        lambda owner, fn, on_done, on_fail=None, name="": on_done(fn()))
    monkeypatch.setattr(
        "gui.scenario_digest_dialog.get_vanilla_content_path",
        lambda: str(vanilla / "Content"))
    out = tmp_path / "fiche.md"
    monkeypatch.setattr(
        "gui.scenario_digest_dialog.QFileDialog.getSaveFileName",
        lambda *a, **k: (str(out), "Markdown (*.md)"))

    dlg = ScenarioDigestDialog(None, working_root=str(root))
    dlg._run()
    text = dlg.preview.toPlainText()
    assert "## FR" in text and "## EN" in text
    assert "Contenu joueur" in text
    assert dlg.btn_export.isEnabled() is True

    dlg._export()
    assert out.is_file()
    content = out.read_text(encoding="utf-8")
    assert content == text
    assert "Fiche exportée" in dlg.status_label.text()


def test_export_without_generation_is_noop(qapp, tmp_path):
    dlg = ScenarioDigestDialog(None, working_root=str(tmp_path))
    dlg._export()
    assert list(Path(tmp_path).glob("*.md")) == []
