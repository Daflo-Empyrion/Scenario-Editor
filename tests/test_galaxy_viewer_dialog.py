"""
Tests du dialogue de la carte de galaxie (gui/galaxy_viewer_dialog.py).
"""
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from core.yamllite.parser import parse_yaml_file

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "galaxy_scenario" / "Sectors.yaml"


@pytest.fixture
def galaxy_doc():
    return parse_yaml_file(FIXTURE_PATH)


def test_dialog_extracts_all_systems(qapp, galaxy_doc):
    from gui.theme import apply_theme
    from gui.galaxy_viewer_dialog import GalaxyViewerDialog
    apply_theme(qapp)
    dialog = GalaxyViewerDialog(galaxy_doc)
    assert len(dialog.systems) == 4


def test_selecting_system_updates_info_label(qapp, galaxy_doc):
    from gui.theme import apply_theme
    from gui.galaxy_viewer_dialog import GalaxyViewerDialog
    apply_theme(qapp)
    dialog = GalaxyViewerDialog(galaxy_doc)
    alpha = next(s for s in dialog.systems if s.name == "Alpha")
    dialog._on_system_selected(alpha)
    assert "Alpha" in dialog.info_label.text()
    assert "GStartingSystem" in dialog.info_label.text()


def test_role_vs_spectral_classification_reflected_in_label(qapp, galaxy_doc):
    from gui.theme import apply_theme
    from gui.galaxy_viewer_dialog import GalaxyViewerDialog
    from core.i18n import t
    apply_theme(qapp)
    dialog = GalaxyViewerDialog(galaxy_doc)
    alphalan = next(s for s in dialog.systems if s.name == "Alphalan")
    dialog._on_system_selected(alphalan)
    assert t("galaxy.spectral") in dialog.info_label.text()


def test_refresh_recomputes_systems(qapp, galaxy_doc):
    from gui.theme import apply_theme
    from gui.galaxy_viewer_dialog import GalaxyViewerDialog
    apply_theme(qapp)
    dialog = GalaxyViewerDialog(galaxy_doc)
    dialog.refresh()
    assert len(dialog.systems) == 4


def test_export_includes_all_systems(qapp, galaxy_doc, monkeypatch, tmp_path):
    from gui.theme import apply_theme
    from gui.galaxy_viewer_dialog import GalaxyViewerDialog
    apply_theme(qapp)
    dialog = GalaxyViewerDialog(galaxy_doc)

    export_path = tmp_path / "export.txt"
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                         staticmethod(lambda *a, **k: (str(export_path), "")))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    dialog._export()

    content = export_path.read_text(encoding="utf-8")
    for s in dialog.systems:
        assert s.name in content


def test_dialog_is_read_only_no_move_mechanism(qapp, galaxy_doc):
    """Contrairement au canvas de playfield, ce dialogue ne doit exposer
    aucun mecanisme de deplacement -- verifie l'absence de la methode/signal
    correspondant."""
    from gui.theme import apply_theme
    from gui.galaxy_viewer_dialog import GalaxyViewerDialog
    apply_theme(qapp)
    dialog = GalaxyViewerDialog(galaxy_doc)
    assert not hasattr(dialog, "modified")


def test_menu_action_shows_info_when_no_workspace(qapp, monkeypatch):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from PyQt6.QtWidgets import QMessageBox
    apply_theme(qapp)
    window = MainWindow()
    window.workspace = None

    called = []
    monkeypatch.setattr(QMessageBox, "information",
                         staticmethod(lambda *a, **k: called.append(True)))
    window._open_galaxy_viewer()
    assert called == [True]


def test_menu_action_shows_info_when_no_sectors_file(qapp, monkeypatch, tmp_path):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from PyQt6.QtWidgets import QMessageBox
    from core.scanner import scan_scenario
    from core.workspace import Workspace
    apply_theme(qapp)

    (tmp_path / "Content" / "Configuration").mkdir(parents=True)
    scenario = scan_scenario(tmp_path)
    window = MainWindow()
    window.workspace = Workspace(source_a=scenario, source_a_root=tmp_path,
                                  working=scenario, working_root=tmp_path)

    called = []
    monkeypatch.setattr(QMessageBox, "information",
                         staticmethod(lambda *a, **k: called.append(True)))
    window._open_galaxy_viewer()
    assert called == [True]


def test_menu_action_opens_non_modal_dialog_with_real_sectors_file(qapp, tmp_path):
    import shutil
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from core.scanner import scan_scenario
    from core.workspace import Workspace
    apply_theme(qapp)

    sectors_dir = tmp_path / "Sectors"
    sectors_dir.mkdir(parents=True)
    shutil.copy(FIXTURE_PATH, sectors_dir / "Sectors.yaml")

    scenario = scan_scenario(tmp_path)
    window = MainWindow()
    window.workspace = Workspace(source_a=scenario, source_a_root=tmp_path,
                                  working=scenario, working_root=tmp_path)

    window._open_galaxy_viewer()
    dialog = window._galaxy_viewer_dialog
    assert dialog.isVisible() is True
    assert dialog.isModal() is False
    assert len(dialog.systems) == 4
    dialog.close()


def test_tilt_slider_starts_at_zero(qapp, galaxy_doc):
    from gui.theme import apply_theme
    from gui.galaxy_viewer_dialog import GalaxyViewerDialog
    apply_theme(qapp)
    dialog = GalaxyViewerDialog(galaxy_doc)
    assert dialog.tilt_slider.value() == 0


def test_projection_at_zero_tilt_matches_flat_x_z(qapp, galaxy_doc):
    """A 0% d'inclinaison, la projection doit rester une simple vue du dessus
    (X, Z) -- comportement identique a avant l'ajout de cette fonctionnalite."""
    from gui.theme import apply_theme
    from gui.galaxy_viewer_dialog import GalaxyViewerDialog
    apply_theme(qapp)
    dialog = GalaxyViewerDialog(galaxy_doc)
    system = dialog.systems[0]
    x, y, z = system.coordinates
    screen_x, screen_y = dialog._project(x, y, z)
    assert screen_x == x
    assert screen_y == z


def test_tilt_shifts_position_proportionally_to_y(qapp, galaxy_doc):
    """Confirme sur un vrai systeme (Alpha, Y=15) que l'inclinaison decale
    bien la position affichee en fonction de Y -- sans effet quand Y=0."""
    from gui.theme import apply_theme
    from gui.galaxy_viewer_dialog import GalaxyViewerDialog
    apply_theme(qapp)
    dialog = GalaxyViewerDialog(galaxy_doc)
    alpha = next(s for s in dialog.systems if s.name == "Alpha")

    dialog.tilt_slider.setValue(0)
    _, y_flat = dialog._project(*alpha.coordinates)
    dialog.tilt_slider.setValue(100)
    _, y_tilted = dialog._project(*alpha.coordinates)
    assert y_flat != y_tilted


def test_tilt_has_no_effect_when_y_is_zero(qapp, galaxy_doc):
    from gui.theme import apply_theme
    from gui.galaxy_viewer_dialog import GalaxyViewerDialog
    apply_theme(qapp)
    dialog = GalaxyViewerDialog(galaxy_doc)

    dialog.tilt_slider.setValue(0)
    x0, y0 = dialog._project(100.0, 0.0, 200.0)
    dialog.tilt_slider.setValue(100)
    x1, y1 = dialog._project(100.0, 0.0, 200.0)
    assert (x0, y0) == (x1, y1)


def test_moving_tilt_slider_redraws_without_crash(qapp, galaxy_doc):
    from gui.theme import apply_theme
    from gui.galaxy_viewer_dialog import GalaxyViewerDialog
    apply_theme(qapp)
    dialog = GalaxyViewerDialog(galaxy_doc)
    dialog.tilt_slider.setValue(75)
    assert dialog.tilt_value_label.text() == "75%"
    assert len(dialog.scene.items()) > 0


def test_construction_does_not_crash_with_default_tilt_value(qapp, galaxy_doc):
    """Regression : le signal valueChanged du curseur ne doit jamais se
    declencher avant que self.systems existe (ordre de construction dans
    __init__)."""
    from gui.theme import apply_theme
    from gui.galaxy_viewer_dialog import GalaxyViewerDialog
    apply_theme(qapp)
    dialog = GalaxyViewerDialog(galaxy_doc)  # ne doit pas lever d'exception
    assert dialog.systems is not None
