"""Dialogue Look cartoon (gui/cartoon_dialog.py) : construction, chemin
menu connecte, previsualisation sans ecriture, application avec marqueur
et garde anti-rejeu (facteurs non idempotents)."""

from pathlib import Path

import pytest

from gui.cartoon_dialog import CartoonDialog

TERRAIN = ('{ Material Name: T\n'
           ' { Child 0\n'
           '  Name: "Grass02"\n'
           '  Saturation: "1.02"\n'
           '  Smoothness: "0.09"\n'
           '  RGB: "(2.0, 1.0, 1.0)"\n'
           ' }\n'
           '}\n')
YAML = ('---\n'
        'PlayfieldType: Planet\n'
        'SkyColor: "1, 0.43, 0.1"\n'
        'FogCloudIntensity: 0.8\n')


@pytest.fixture
def scenario(tmp_path):
    pf = tmp_path / "Playfields" / "TestPlanet"
    pf.mkdir(parents=True)
    (pf / "terrain.ecf").write_text(TERRAIN, encoding="utf-8")
    (pf / "playfield_static.yaml").write_text(YAML, encoding="utf-8")
    space = tmp_path / "Playfields" / "TestSpace"
    space.mkdir()
    (space / "space_dynamic.yaml").write_text("---\nPlayfieldType: Space\n",
                                              encoding="utf-8")
    return tmp_path


@pytest.fixture
def no_prod(tmp_path, monkeypatch):
    from core.cartoon_look import DEFAULT_PRESET
    monkeypatch.setattr("core.cartoon_look.get_backup_root",
                        lambda kind: str(tmp_path / "bk"))
    monkeypatch.setattr("core.cartoon_look.get_production_scenario_path",
                        lambda root: "")
    # preset STOCKE de l'utilisateur : les tests exigent les defauts
    monkeypatch.setattr("gui.cartoon_dialog.load_stored_preset",
                        lambda: dict(DEFAULT_PRESET))
    monkeypatch.setattr("gui.cartoon_dialog.async_call",
                        lambda owner, fn, on_done, on_fail=None, name="":
                        on_done(fn()))


def test_dialog_builds(qapp):
    dlg = CartoonDialog(None)
    assert dlg.windowTitle()
    assert dlg.preview.isReadOnly() is True
    assert dlg.btn_preview.isEnabled() and dlg.btn_apply.isEnabled()


def test_menu_path_connected(qapp, monkeypatch):
    from test_theme_verriere_and_reorg import _make_window
    win = _make_window(qapp, monkeypatch, None)
    assert win.action_cartoon in win.menu_tools.actions()
    calls = {}

    class _Stub:
        def __init__(self, parent, working_root=""):
            calls["root"] = working_root

        def exec(self):
            calls["exec"] = True

    monkeypatch.setattr("gui.cartoon_dialog.CartoonDialog", _Stub)
    win._open_cartoon_dialog()
    assert calls == {"root": "", "exec": True}
    win.close()


def test_preview_ne_ecrit_rien(qapp, scenario, no_prod):
    dlg = CartoonDialog(None, working_root=str(scenario))
    dlg._preview()
    terrain = scenario / "Playfields/TestPlanet/terrain.ecf"
    assert "TestPlanet/terrain.ecf" in dlg.preview.toPlainText()
    assert 'Saturation: "1.02"' in terrain.read_text(encoding="utf-8")
    assert not (scenario / "+cartoon_look_applique.txt").exists()


def test_apply_marqueur_et_garde_anti_rejeu(qapp, scenario, no_prod):
    dlg = CartoonDialog(None, working_root=str(scenario))
    dlg._apply()
    terrain = scenario / "Playfields/TestPlanet/terrain.ecf"
    txt = terrain.read_text(encoding="utf-8")
    assert 'Saturation: "1.632"' in txt and 'Smoothness: "-0.25"' in txt
    sky = (scenario / "Playfields/TestPlanet/playfield_static.yaml")
    skytxt = sky.read_text(encoding="utf-8")
    assert 'SkyColor: "1.000, 0.465, 0.155"' in skytxt
    assert "FogCloudIntensity: 0.4" in skytxt
    assert (scenario / "+cartoon_look_applique.txt").exists()
    assert "fichiers transformés" in dlg.status_label.text()

    # 2e passage sans --force : bloque, fichier intact
    dlg._apply()
    assert terrain.read_text(encoding="utf-8") == txt
    assert "Réappliquer" in dlg.status_label.text()

    # avec la case force : les facteurs sont rejoues (clamp haut atteint)
    dlg.force_box.setChecked(True)
    dlg._apply()
    assert 'Saturation: "2.5"' in terrain.read_text(encoding="utf-8")


def test_scenario_absent(qapp, tmp_path, no_prod):
    dlg = CartoonDialog(None, working_root=str(tmp_path / "nulle-part"))
    dlg._preview()
    assert "introuvable" in dlg.status_label.text()


def _grid_labels(dlg) -> list:
    from PyQt6.QtWidgets import QLabel
    out = []
    for i in range(dlg.colors_grid.count()):
        w = dlg.colors_grid.itemAt(i).widget()
        if isinstance(w, QLabel):
            out.append(w.text())
    return out


def test_colors_preview_on_open(qapp, scenario, no_prod):
    dlg = CartoonDialog(None, working_root=str(scenario))
    assert dlg.pf_combo.count() == 1
    assert dlg.pf_combo.currentText() == "TestPlanet"
    labels = _grid_labels(dlg)
    assert "SkyColor" in labels and "Grass02" in labels


def test_restore_derniere_passe(qapp, scenario, no_prod, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    dlg = CartoonDialog(None, working_root=str(scenario))
    dlg._apply()
    assert dlg.backup_combo.count() == 1
    marker = scenario / "+cartoon_look_applique.txt"
    assert marker.exists()

    monkeypatch.setattr(
        "gui.cartoon_dialog.QMessageBox.question",
        lambda *a, **k: QMessageBox.StandardButton.No)
    dlg.btn_restore.click()                 # refuse : rien ne change
    assert marker.exists()

    monkeypatch.setattr(
        "gui.cartoon_dialog.QMessageBox.question",
        lambda *a, **k: QMessageBox.StandardButton.Yes)
    dlg.btn_restore.click()
    terrain = scenario / "Playfields/TestPlanet/terrain.ecf"
    assert 'Saturation: "1.02"' in terrain.read_text(encoding="utf-8")
    assert not marker.exists()
    assert "restaurés" in dlg.status_label.text()
    assert dlg.backup_combo.count() == 1    # la passe reste listable


def test_preset_spinboxes_alimentent_l_apercu(qapp, scenario, no_prod,
                                              monkeypatch):
    dlg = CartoonDialog(None, working_root=str(scenario))
    seen = {}
    monkeypatch.setattr(
        "gui.cartoon_dialog.preview_colors",
        lambda s, pf, preset=None: (seen.update(p=preset),
                                    {"ciel": [], "terrain": []})[1])
    dlg.preset_spins["saturation"].setValue(2.5)
    dlg._refresh_colors()
    assert seen["p"]["saturation"] == 2.5


def test_apply_transmet_et_persiste_le_preset(qapp, scenario, no_prod,
                                              monkeypatch):
    dlg = CartoonDialog(None, working_root=str(scenario))
    dlg.preset_spins["rgb_spread"].setValue(2.0)
    seen = {}

    def fake_run(scen, dry_run=False, force=False, no_sync=False,
                 preset=None):
        seen["preset"] = preset
        return {"ok": True, "error": "", "marker_blocked": False,
                "touched": [], "total": 0, "invalid": [], "backup_dir": "",
                "dry_run": dry_run, "prod": "", "copied": 0, "bins": 0}

    monkeypatch.setattr("gui.cartoon_dialog.run_preset", fake_run)
    monkeypatch.setattr("gui.cartoon_dialog.save_preset",
                        lambda p: seen.update(saved=p))
    dlg._apply()
    assert seen["preset"]["rgb_spread"] == 2.0
    assert seen["saved"]["rgb_spread"] == 2.0

    dlg.btn_defaults.click()                # retour aux defauts (1.5)
    assert dlg.preset_spins["rgb_spread"].value() == 1.5


def test_info_button_wired(qapp, tmp_path, monkeypatch):
    """Le bouton « Comprendre le module » ouvre la fiche cartoon."""
    import gui.module_info as mi
    from PyQt6.QtWidgets import QPushButton
    dlg = CartoonDialog(None)
    infos = [b for b in dlg.findChildren(QPushButton)
             if b.objectName() == 'secondaryButton'
             and b.toolTip().startswith('Ce que fait')]
    assert len(infos) == 1
    seen = []
    monkeypatch.setattr(mi, 'show_module_info',
                        lambda parent, key: seen.append(key))
    infos[0].click()
    assert seen == ['cartoon.info_html']
