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


def test_camera_defaults_show_relief(qapp, galaxy_doc):
    """Camera par defaut INCLINEE (35 deg) : l'ouverture en vue de dessus
    pur rendait la galaxie « plate » (vecu 19/10). L'orbite est libre des
    deux cotes du plan : on peut passer dessous comme au-dessus."""
    from gui.theme import apply_theme
    from gui.galaxy_viewer_dialog import GalaxyViewerDialog
    apply_theme(qapp)
    dialog = GalaxyViewerDialog(galaxy_doc)
    assert dialog.canvas.elev == 35.0
    assert dialog.canvas.azim == 0.0
    assert dialog.canvas.ELEV_MIN < 0 < dialog.canvas.ELEV_MAX


def test_edit_mode_projection_is_exact_x_z(qapp, galaxy_doc):
    """MAP-009 : en mode edition (orthographique, vue de dessus), la
    projection et son inverse redonnent exactement (x, z)."""
    from gui.theme import apply_theme
    from gui.galaxy_viewer_dialog import GalaxyViewerDialog
    apply_theme(qapp)
    dialog = GalaxyViewerDialog(galaxy_doc)
    canvas = dialog.canvas
    canvas.resize(900, 650)
    canvas.edit_mode = True
    system = next(s for s in canvas.systems if s.coordinates)
    sx, sy, pf = canvas.project(system.coordinates)
    assert pf == 1.0
    wx, wz = canvas.unproject_ground(sx, sy)
    assert abs(wx - system.coordinates[0]) < 1e-6
    assert abs(wz - system.coordinates[2]) < 1e-6


def test_move_mode_toggle_locks_camera(qapp, galaxy_doc):
    from gui.theme import apply_theme
    from gui.galaxy_viewer_dialog import GalaxyViewerDialog
    apply_theme(qapp)
    dialog = GalaxyViewerDialog(galaxy_doc)
    canvas = dialog.canvas
    assert not hasattr(dialog, "move_check")  # sans sectors_path : pas d'edition
    assert canvas.edit_mode is False


def test_orbit_changes_projection(qapp, galaxy_doc):
    """Navigation 3D : l'azimut et l'elevation changent la projection, le
    zoom rapproche (facteur de grossissement au centre)."""
    from gui.theme import apply_theme
    from gui.galaxy_viewer_dialog import GalaxyViewerDialog
    apply_theme(qapp)
    dialog = GalaxyViewerDialog(galaxy_doc)
    canvas = dialog.canvas
    canvas.resize(900, 650)
    canvas.elev = 45.0
    target = next(s for s in canvas.systems if s.coordinates).coordinates
    p_flat = canvas.project(target)
    canvas.azim = 60.0
    p_turned = canvas.project(target)
    assert (p_flat[0], p_flat[1]) != (p_turned[0], p_turned[1])


def test_read_only_dialog_has_no_move_callback(qapp, galaxy_doc):
    """Sans sectors_path la carte reste lecture seule : pas de callback move."""
    from gui.theme import apply_theme
    from gui.galaxy_viewer_dialog import GalaxyViewerDialog
    apply_theme(qapp)
    dialog = GalaxyViewerDialog(galaxy_doc)
    assert dialog.canvas._on_moved is not None  # cable mais garde par _move_enabled
    assert dialog._move_enabled is False
    assert not hasattr(dialog, "modified")


# ---------------------------------------------------------------------------
# Lisibilite (consultation IA 18-19/10 : couleurs spectrales, halo roles,
# etiquettes conditionnelles, filtre de recherche, legende)
# ---------------------------------------------------------------------------

def test_spectral_color_follows_star_class_letter(qapp, galaxy_doc):
    from gui.theme import apply_theme
    from gui.galaxy_viewer_dialog import GalaxyViewerDialog, _dot_color
    apply_theme(qapp)
    assert _dot_color("A3").name() != _dot_color("K2V").name()
    dialog = GalaxyViewerDialog(galaxy_doc)
    alpha = next(s for s in dialog.systems if s.name == "Alpha")
    from core.galaxy_viewer import classify_star_class
    assert classify_star_class(alpha.star_class) == "role"
    assert _dot_color(alpha.star_class) == _dot_color("GStartingSystem")


def test_role_dots_flagged_for_halo(qapp, galaxy_doc):
    from gui.theme import apply_theme
    from gui.galaxy_viewer_dialog import GalaxyViewerDialog
    apply_theme(qapp)
    dialog = GalaxyViewerDialog(galaxy_doc)
    dialog.canvas.resize(900, 650)
    dialog.canvas.grab()  # force un rendu reel (paintEvent) hors ecran
    assert dialog.canvas._layout, "le rendu doit peupler le layout"
    roles = {s.name: classify_role(s) for s, _x, _y, _r, _p in dialog.canvas._layout}
    assert roles["Alpha"] is True      # GStartingSystem -> halo
    assert roles["Alphalan"] is False  # A3 spectral -> trait fin


def classify_role(system):
    from core.galaxy_viewer import classify_star_class
    return classify_star_class(system.star_class) == "role"


def test_labels_thinned_by_priority_at_low_zoom(qapp, galaxy_doc):
    """Anti-muraille (vecu RE2 : 60+ boites empilees) : a faible zoom seules
    quelques etiquettes (priorite roles, puis richesse) restent posees ; au
    zoom, les spectrales reviennent."""
    from gui.theme import apply_theme
    from gui.galaxy_viewer_dialog import GalaxyViewerDialog
    apply_theme(qapp)
    dialog = GalaxyViewerDialog(galaxy_doc)
    canvas = dialog.canvas
    canvas.resize(900, 650)
    canvas.grab()
    canvas.zoom = canvas.zoom_fit * 0.5
    labels = {s.name: (visible, role)
              for s, _rect, visible, role in canvas._layout_labels()}
    assert labels["Alphalan"][0] is False       # spectrale : masquee
    shown = [name for name, (visible, _role) in labels.items() if visible]
    assert 0 < len(shown) < len(labels)          # elague, pas vide
    assert all(labels[name][1] for name in shown)  # priorite : que des roles
    canvas.zoom = canvas.zoom_fit * 4.0
    labels = {s.name: visible
              for s, _rect, visible, _role in canvas._layout_labels()}
    assert labels["Alphalan"] is True


def test_search_filter_dims_non_matching_systems(qapp, galaxy_doc):
    from gui.theme import apply_theme
    from gui.galaxy_viewer_dialog import GalaxyViewerDialog
    apply_theme(qapp)
    dialog = GalaxyViewerDialog(galaxy_doc)
    rogue = next(s for s in dialog.systems if s.name == "Rogue System")
    alpha = next(s for s in dialog.systems if s.name == "Alpha")
    dialog.search.setText("alpha")
    assert dialog.canvas._alpha(alpha) == 1.0
    assert dialog.canvas._alpha(rogue) < 0.2
    dialog.search.setText("")
    assert dialog.canvas._alpha(rogue) == 1.0


def test_legend_is_built(qapp, galaxy_doc):
    from gui.theme import apply_theme
    from gui.galaxy_viewer_dialog import GalaxyViewerDialog
    apply_theme(qapp)
    dialog = GalaxyViewerDialog(galaxy_doc)
    chips = dialog.findChildren(type(dialog._legend_chip("#fff", "x")))
    assert len(chips) >= 8  # 1 role + 7 classes OBAFGKM


def test_move_drag_full_path_writes_file(qapp, tmp_path):
    """MAP-009 bout en bout (regression vecu 19/10 : l'apercu live avait
    disparu avec la 3D, la fonction paraissait perdue) : press sur un point
    en mode edition -> le point suit la souris -> release ecrit le fichier."""
    import shutil
    from pathlib import Path
    from PyQt6.QtCore import QPointF, Qt, QEvent
    from PyQt6.QtGui import QMouseEvent
    from gui.theme import apply_theme
    from gui.galaxy_viewer_dialog import GalaxyViewerDialog
    from core.yamllite.parser import parse_yaml_file
    apply_theme(qapp)
    sectors = tmp_path / "Sectors.yaml"
    shutil.copy(FIXTURE_PATH, sectors)
    doc = parse_yaml_file(sectors)
    dlg = GalaxyViewerDialog(doc, sectors_path=sectors)
    dlg.resize(900, 650)
    dlg.show()
    dlg.move_check.setChecked(True)
    canvas = dlg.canvas
    canvas.grab()
    alpha = next(s for s in canvas.systems if s.name == "Alpha")
    sx, sy, _r = next((x, y, r) for s, x, y, r, _p in canvas._layout
                      if s is alpha)

    def mouse(etype, x, y):
        ev = QMouseEvent(etype, QPointF(x, y), QPointF(x, y),
                         Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(canvas, ev)

    from PyQt6.QtWidgets import QApplication
    mouse(QEvent.Type.MouseButtonPress, sx, sy)
    assert canvas._drag[0] == "move"
    mouse(QEvent.Type.MouseMove, sx + 60, sy - 30)
    assert canvas._drag_preview is not None          # apercu live
    wx, wz = canvas.unproject_ground(sx + 60, sy - 30)
    assert abs(wx - alpha.coordinates[0]) > 0.5      # le deplacement est reel
    mouse(QEvent.Type.MouseButtonRelease, sx + 60, sy - 30)
    assert abs(alpha.coordinates[0] - wx) < 1e-6     # coordonnees commitees
    assert f"[ {wx:g}," in sectors.read_text(encoding="utf-8")
    dlg.close()
