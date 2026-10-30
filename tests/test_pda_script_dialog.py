"""Scripts de gameplay (gui/pda_script_dialog.py) : construction, changement
de modele, apercu modifiable, verification de compilation reelle et ecriture
dans Extras/PDA/Scripts/."""

import os
from pathlib import Path

import pytest

from core.pda.script_gen import find_csc
from gui.pda_script_dialog import PdaScriptDialog

MANAGED = None
for _base in (r"C:\Program Files (x86)\Steam\steamapps\common",
              r"D:\Steam\steamapps\common", r"E:\Steam\steamapps\common"):
    _cand = Path(_base) / "Empyrion - Galactic Survival" / "Client" / \
        "Empyrion_Data" / "Managed"
    if (_cand / "Assembly-CSharp.dll").is_file():
        MANAGED = _cand
        break

requires_game = pytest.mark.skipif(
    find_csc() is None or MANAGED is None,
    reason="csc.exe ou assemblies du jeu absents")


def test_dialog_builds(qapp):
    dlg = PdaScriptDialog(None)
    assert dlg.cmb_template.count() == 3
    assert dlg.preview.toPlainText().strip()
    assert dlg.form.rowCount() == len(
        __import__("core.pda.script_gen", fromlist=["TEMPLATES"])
        .TEMPLATES["chapter_near_poi"].params)


def test_template_switch_changes_form(qapp):
    dlg = PdaScriptDialog(None)
    dlg.cmb_template.setCurrentIndex(1)          # chapter_basic (6 params)
    assert dlg.form.rowCount() == 6
    assert "NearPoiAction" not in dlg.preview.toPlainText()


def test_parameters_reach_preview(qapp):
    dlg = PdaScriptDialog(None)
    dlg._edits["chapter_title"].setText("Ma mission")
    dlg._edits["poi_name"].setCurrentText("MonPOI")   # combo editable
    dlg._rebuild()
    assert "Ma mission" in dlg.preview.toPlainText()
    assert "MonPOI" in dlg.preview.toPlainText()


def test_write_refuses_silent_overwrite(qapp, tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr("gui.pda_script_dialog.info",
                        lambda *a, **k: seen.append(a))
    monkeypatch.setattr("gui.pda_script_dialog.ask_yes_no",
                        lambda *a, **k: False)
    monkeypatch.setattr(
        "gui.pda_script_dialog.async_call",
        lambda owner, fn, on_done, on_fail=None, name="": on_done(fn()))
    dlg = PdaScriptDialog(None, str(tmp_path))
    dlg._write()
    path = tmp_path / "Extras/PDA/Scripts/MissionScript.cs"
    assert path.is_file()
    first = path.read_text(encoding="utf-8")
    dlg.preview.setPlainText("// modifie")
    dlg._write()                                  # refus d'ecrasement
    assert path.read_text(encoding="utf-8") == first


@requires_game
def test_full_flow_check_then_write(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("EMPYRION_MANAGED_DIR", str(MANAGED))
    seen = []
    monkeypatch.setattr("gui.pda_script_dialog.info",
                        lambda *a, **k: seen.append(a))
    monkeypatch.setattr("gui.pda_script_dialog.ask_yes_no",
                        lambda *a, **k: True)
    # async synchrone
    monkeypatch.setattr(
        "gui.pda_script_dialog.async_call",
        lambda owner, fn, on_done, on_fail=None, name="": on_done(fn()))
    dlg = PdaScriptDialog(None, str(tmp_path))
    dlg._check()
    assert "réussie" in dlg.status_label.text().lower()
    dlg._write()
    path = tmp_path / "Extras/PDA/Scripts/MissionScript.cs"
    assert path.is_file()
    assert "PdaScript" in path.read_text(encoding="utf-8")
    assert seen, "confirmation d'ecriture"


@requires_game
def test_broken_preview_reported(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("EMPYRION_MANAGED_DIR", str(MANAGED))
    monkeypatch.setattr(
        "gui.pda_script_dialog.async_call",
        lambda owner, fn, on_done, on_fail=None, name="": on_done(fn()))
    dlg = PdaScriptDialog(None, str(tmp_path))
    dlg.preview.setPlainText(dlg.preview.toPlainText().replace(
        "CommitActions();", "CommitActions("))
    dlg._check()
    assert "échec" in dlg.status_label.text().lower()


def test_poi_names_from_prefabs(tmp_path):
    """Le pool de POIs lit les prefabs .epb (racine OU Content/) et propose
    le Name INTERNE de l'en-tete EN PLUS du nom de fichier (89 % different
    sur RE2)."""
    import struct

    from core.epb_blueprint import EPB_MAGIC
    from gui.pda_script_dialog import _poi_names

    def epb_with_name(path, name):
        raw = name.encode("utf-8")
        path.write_bytes(
            struct.pack("<I", EPB_MAGIC) + struct.pack("<I", 3) + b"\x00"
            + struct.pack("<iii", 0, 0, 0) + struct.pack("<H", 0)
            + struct.pack("<H", 1)                       # 1 propriete
            + struct.pack("<i", 7) + b"\x00\x00\x00" + b"\x00"
            + bytes([len(raw)]) + raw)                   # longueur 7 bits

    (tmp_path / "Prefabs").mkdir()
    epb_with_name(tmp_path / "Prefabs" / "FichierA.epb", "NomInterneA")
    (tmp_path / "Prefabs" / "FichierB.epb").write_bytes(b"pas un epb")
    (tmp_path / "Prefabs" / "sous").mkdir()
    (tmp_path / "Prefabs" / "sous" / "FichierC.epb").write_bytes(b"x")
    names = _poi_names(tmp_path)
    assert "FichierA" in names and "NomInterneA" in names
    assert "FichierC" in names                          # recursif
    assert "FichierB" in names                          # illisible : stem garde
    alt = tmp_path / "Content" / "Prefabs"
    alt.mkdir(parents=True)
    (alt / "Troisieme.epb").write_bytes(b"x")
    assert _poi_names(tmp_path / "Content") == ["Troisieme"]
    assert _poi_names(tmp_path / "vide") == []
