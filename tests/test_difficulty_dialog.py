"""Reglage du danger (gui/difficulty_dialog.py) : construction, palier qui
preremplit les coefficients, apercu MODIFIABLE, application reelle puis
annulation."""

from pathlib import Path

from PyQt6.QtCore import Qt

from gui.difficulty_dialog import DifficultyDialog

PLAYFIELD = """---
PlayfieldType: Planet

POIs:
    Random:
        - GroupName: Normal
          CountMinMax: [ 10, 20 ]
        - GroupName: Starting
          CountMinMax: [ 3, 6 ]
          SpawnPOINear: [START]
"""


def _scenario(tmp_path: Path) -> Path:
    pf = tmp_path / "Playfields" / "Pf"
    pf.mkdir(parents=True)
    (pf / "playfield_static.yaml").write_text(PLAYFIELD, encoding="utf-8")
    return tmp_path


def test_dialog_builds(qapp):
    dlg = DifficultyDialog(None)
    assert dlg.cmb_preset.count() == 5
    assert len(dlg.spins) == 5
    # 'normal' selectionne par defaut : tous les coefficients a 100 %
    assert {v.value() for v in dlg.spins.values()} == {100}
    assert dlg.btn_apply.isEnabled() is False


def test_preset_fills_coefficients(qapp):
    dlg = DifficultyDialog(None)
    dlg.cmb_preset.setCurrentIndex(4)          # cauchemar
    dlg._apply_preset()
    assert dlg._coefficients()["spawns"] == 1.8
    assert dlg._coefficients()["loot"] == 0.6


def test_full_flow(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "gui.difficulty_dialog.async_call",
        lambda owner, fn, on_done, on_fail=None, name="": on_done(fn()))
    seen = []
    monkeypatch.setattr("gui.difficulty_dialog.info",
                        lambda *a, **k: seen.append(a))
    monkeypatch.setattr("gui.difficulty_dialog.ask_yes_no",
                        lambda *a, **k: True)
    root = _scenario(tmp_path)
    dlg = DifficultyDialog(None, str(root))
    dlg.spins["spawns"].setValue(150)
    dlg._build()
    assert dlg.table.rowCount() >= 1
    # garde-fou START present et non coché par "tout cocher"
    dlg._check_all()
    checked_targets = [dlg._plan.entries[r].target
                       for r in dlg._checked()]
    assert not any("Starting" in t for t in checked_targets)

    # apercu MODIFIABLE : on corrige la nouvelle valeur d'une ligne
    row = dlg._checked()[0]
    dlg.table.item(row, 4).setText("40")
    dlg._apply()
    text = (root / "Playfields/Pf/playfield_static.yaml").read_text(
        encoding="utf-8")
    assert "CountMinMax: [15, 40]" in text
    assert "CountMinMax: [ 3, 6 ]" in text      # START intact
    assert seen, "confirmation d'application"

    # annulation : le fichier revient a son contenu d'origine
    dlg._undo_apply()
    restored = (root / "Playfields/Pf/playfield_static.yaml").read_text(
        encoding="utf-8")
    assert "CountMinMax: [ 10, 20 ]" in restored


# -- annulation DURABLE (29/10) : snapshot disque + bouton Restaurer --------

def test_snapshot_persiste_et_restaure(tmp_path, monkeypatch):
    import json
    from core.difficulty_tuning import (list_undo_snapshots,
                                        restore_undo_snapshot,
                                        save_undo_snapshot,
                                        undo_backup_root)
    pf = _scenario(tmp_path)
    yaml = pf / "Playfields/Pf/playfield_static.yaml"
    original = yaml.read_text(encoding="utf-8")
    (Path(str(yaml) + ".bin")).write_text("cache", encoding="utf-8")
    root = tmp_path / "snapshots"
    monkeypatch.setattr("core.difficulty_tuning.undo_backup_root",
                        lambda: root)
    monkeypatch.setattr("core.fsutil.central_backup",
                        lambda path, kind: root / "safety" / path.name)

    snap = save_undo_snapshot({yaml: original})
    assert snap is not None and snap.is_dir()
    yaml.write_text(original.replace("CountMinMax: [ 10, 20 ]",
                                     "CountMinMax: [ 20, 40 ]"),
                    encoding="utf-8")
    assert [s.name for s in list_undo_snapshots()] == [snap.name]
    manifest = json.loads((snap / "manifest.json").read_text(encoding="utf-8"))
    assert manifest[0]["path"] == str(yaml)

    restored, safety_dir = restore_undo_snapshot(snap)
    assert restored == 1 and "safety" in safety_dir
    assert yaml.read_text(encoding="utf-8") == original
    assert not Path(str(yaml) + ".bin").exists()      # cache invalide
    assert list_undo_snapshots() == [snap]            # la passe reste listable


def test_snapshot_rien_a_archiver(tmp_path, monkeypatch):
    from core.difficulty_tuning import save_undo_snapshot, undo_backup_root
    monkeypatch.setattr("core.difficulty_tuning.undo_backup_root",
                        lambda: tmp_path / "snapshots")
    assert save_undo_snapshot({}) is None
    assert not (tmp_path / "snapshots").exists()   # rien de cree


def test_dialog_restaure_une_passe(qapp, tmp_path, monkeypatch):
    from gui.difficulty_dialog import DifficultyDialog
    pf = _scenario(tmp_path)
    yaml = pf / "Playfields/Pf/playfield_static.yaml"
    original = yaml.read_text(encoding="utf-8")
    root = tmp_path / "snapshots"
    monkeypatch.setattr("core.difficulty_tuning.undo_backup_root",
                        lambda: root)     # pour save_undo_snapshot (core)
    from core.difficulty_tuning import save_undo_snapshot
    snap = save_undo_snapshot({yaml: original})
    yaml.write_text(original.replace("[ 10, 20 ]", "[ 99, 99 ]"),
                    encoding="utf-8")
    # le dialogue utilise SES bindings importes du module core : patcher
    # le dialogue, pas seulement le module
    monkeypatch.setattr("gui.difficulty_dialog.list_undo_snapshots",
                        lambda: [snap])
    monkeypatch.setattr("gui.difficulty_dialog.undo_backup_root",
                        lambda: root)
    monkeypatch.setattr("core.fsutil.central_backup",
                        lambda path, kind: root / "safety" / path.name)
    monkeypatch.setattr("gui.difficulty_dialog.ask_yes_no",
                        lambda parent, title, text: True)
    seen = []
    monkeypatch.setattr("gui.difficulty_dialog.info",
                        lambda parent, title, text: seen.append(text))
    monkeypatch.setattr("gui.difficulty_dialog.async_call",
                        lambda owner, fn, on_done, on_fail=None, name="":
                        on_done(fn()))

    dlg = DifficultyDialog(None, working_root=str(tmp_path))
    assert dlg.cmb_backups.count() == 1
    dlg.btn_restore.click()
    assert yaml.read_text(encoding="utf-8") == original
    assert seen and "1 fichier(s) restauré(s)" in seen[0]


def test_info_button_wired(qapp, tmp_path, monkeypatch):
    """Le bouton « Comprendre le module » ouvre la fiche du danger."""
    import gui.module_info as mi
    dlg = DifficultyDialog(None)
    btn = dlg.findChild(__import__('PyQt6.QtWidgets', fromlist=['QPushButton'])
                        .QPushButton)
    infos = [b for b in dlg.findChildren(type(btn))
             if b.objectName() == 'secondaryButton'
             and b.toolTip().startswith('Ce que fait')]
    assert len(infos) == 1
    seen = []
    monkeypatch.setattr(mi, 'show_module_info',
                        lambda parent, key: seen.append(key))
    infos[0].click()
    assert seen == ['difficulty.info_html']
