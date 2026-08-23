"""
Tests du dialogue de l'inspecteur de POI (gui/poi_inspector_dialog.py).
"""
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from core.yamllite.parser import parse_yaml_file

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "playfield_scenario"


@pytest.fixture
def static_doc():
    return parse_yaml_file(FIXTURE_DIR / "playfield_static.yaml")


def test_dialog_populates_detail_table(qapp, static_doc):
    from gui.theme import apply_theme
    from gui.poi_inspector_dialog import PoiInspectorDialog
    apply_theme(qapp)
    dialog = PoiInspectorDialog(static_doc)
    assert dialog.detail_table.rowCount() == 41


def test_dialog_populates_faction_table(qapp, static_doc):
    from gui.theme import apply_theme
    from gui.poi_inspector_dialog import PoiInspectorDialog
    apply_theme(qapp)
    dialog = PoiInspectorDialog(static_doc)
    assert dialog.faction_table.rowCount() == 6


def test_faction_table_sorted_by_drone_count_descending(qapp, static_doc):
    from gui.theme import apply_theme
    from gui.poi_inspector_dialog import PoiInspectorDialog
    apply_theme(qapp)
    dialog = PoiInspectorDialog(static_doc)
    maxes = []
    for row in range(dialog.faction_table.rowCount()):
        drones_text = dialog.faction_table.item(row, 2).text()
        maxes.append(int(drones_text.split("-")[1]))
    assert maxes == sorted(maxes, reverse=True)


def test_refresh_recomputes_stats(qapp, static_doc):
    from gui.theme import apply_theme
    from gui.poi_inspector_dialog import PoiInspectorDialog
    apply_theme(qapp)
    dialog = PoiInspectorDialog(static_doc)
    dialog.refresh()
    assert dialog.detail_table.rowCount() == 41


def test_export_writes_all_stats(qapp, static_doc, monkeypatch, tmp_path):
    from gui.theme import apply_theme
    from gui.poi_inspector_dialog import PoiInspectorDialog
    apply_theme(qapp)
    dialog = PoiInspectorDialog(static_doc)

    export_path = tmp_path / "export.txt"
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                         staticmethod(lambda *a, **k: (str(export_path), "")))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    dialog._export()

    content = export_path.read_text(encoding="utf-8")
    for s in dialog.stats:
        assert s.name in content


def test_poi_inspector_button_opens_non_modal_dialog_from_playfield_widget(qapp):
    from gui.theme import apply_theme
    from gui.playfield_edit_widget import PlayfieldEditWidget
    apply_theme(qapp)
    widget = PlayfieldEditWidget(FIXTURE_DIR / "playfield_static.yaml")
    widget._open_poi_inspector()
    dialog = widget._poi_inspector_dialog
    assert dialog.isVisible() is True
    assert dialog.isModal() is False
    assert dialog.detail_table.rowCount() == 41
    dialog.close()
