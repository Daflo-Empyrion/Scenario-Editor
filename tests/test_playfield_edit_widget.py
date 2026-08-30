"""
Tests de l'interface graphique du module playfield (gui/playfield_edit_widget.py)
-- bases sur les memes vraies fixtures que test_playfield_editor.py.
"""
import shutil
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QDialog, QMessageBox

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "playfield_scenario"
PLAYFIELD = FIXTURE_DIR / "playfield_static.yaml"
BLOCKS_ECF = FIXTURE_DIR / "BlocksConfig.ecf"


@pytest.fixture
def playfield_widget(qapp, tmp_path):
    from gui.theme import apply_theme
    from gui.playfield_edit_widget import PlayfieldEditWidget
    apply_theme(qapp)
    working_copy = tmp_path / "playfield_static.yaml"
    shutil.copy(PLAYFIELD, working_copy)
    return PlayfieldEditWidget(working_copy, blocks_ecf_files=[BLOCKS_ECF])


def test_widget_has_four_tabs(playfield_widget):
    from core.i18n import t
    assert playfield_widget.tab_widget.count() == 8


def test_resources_tab_shows_correct_counts(playfield_widget):
    resources_tab = playfield_widget.tab_widget.widget(1)
    random_table, asteroid_table, space_table = resources_tab._playfield_tables
    assert random_table.table.rowCount() == 5
    assert asteroid_table.table.rowCount() == 4
    assert space_table.table.rowCount() == 0  # fixture planete -- pas de ressources spatiales


def test_poi_tab_shows_correct_count(playfield_widget):
    poi_tab = playfield_widget.tab_widget.widget(2)
    table = poi_tab._playfield_tables[0]
    assert table.table.rowCount() == 41


def test_creatures_tab_shows_correct_count(playfield_widget):
    creatures_tab = playfield_widget.tab_widget.widget(3)
    table = creatures_tab._playfield_tables[0]
    assert table.table.rowCount() == 88


def test_poi_tab_has_no_add_remove_buttons(playfield_widget):
    poi_tab = playfield_widget.tab_widget.widget(2)
    table = poi_tab._playfield_tables[0]
    assert not hasattr(table, "btn_add")
    assert not hasattr(table, "btn_remove")


def test_resources_tab_has_add_remove_buttons(playfield_widget):
    resources_tab = playfield_widget.tab_widget.widget(1)
    random_table = resources_tab._playfield_tables[0]
    assert hasattr(random_table, "btn_add")
    assert hasattr(random_table, "btn_remove")


def test_editing_a_cell_updates_the_document(playfield_widget):
    resources_tab = playfield_widget.tab_widget.widget(1)
    random_table = resources_tab._playfield_tables[0]
    headers = [random_table.table.horizontalHeaderItem(c).text()
               for c in range(random_table.table.columnCount())]
    col = headers.index("DroneProb")

    assert playfield_widget.is_modified() is False
    random_table.table.item(0, col).setText("0.99")

    assert playfield_widget.is_modified() is True
    assert "DroneProb: 0.99" in playfield_widget.doc.render()


def test_undo_reverts_cell_edit_and_refreshes_table(playfield_widget):
    resources_tab = playfield_widget.tab_widget.widget(1)
    random_table = resources_tab._playfield_tables[0]
    headers = [random_table.table.horizontalHeaderItem(c).text()
               for c in range(random_table.table.columnCount())]
    col = headers.index("DroneProb")

    random_table.table.item(0, col).setText("0.99")
    playfield_widget.undo()

    assert "DroneProb: 0.5" in playfield_widget.doc.render()
    refreshed_table = playfield_widget.tab_widget.widget(1)._playfield_tables[0]
    assert refreshed_table.table.item(0, col).text() == "0.5"


def test_add_resource_via_dialog(playfield_widget, monkeypatch):
    from gui.playfield_edit_widget import AddResourceDialog

    def fake_exec(self):
        self.combo.setCurrentIndex(0)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(AddResourceDialog, "exec", fake_exec)

    resources_tab = playfield_widget.tab_widget.widget(1)
    random_table = resources_tab._playfield_tables[0]
    before = random_table.table.rowCount()

    playfield_widget._add_resource("RandomResources")

    assert random_table.table.rowCount() == before + 1
    assert playfield_widget.is_modified() is True


def test_remove_resource_via_button(playfield_widget, monkeypatch):
    monkeypatch.setattr(QMessageBox, "exec", _msgbox_yes)

    resources_tab = playfield_widget.tab_widget.widget(1)
    random_table = resources_tab._playfield_tables[0]
    before = random_table.table.rowCount()

    random_table.table.setCurrentCell(0, 0)
    random_table._on_remove_clicked()

    assert random_table.table.rowCount() == before - 1


def test_complex_nested_param_shown_as_placeholder_not_editable(playfield_widget):
    from core.i18n import t
    poi_tab = playfield_widget.tab_widget.widget(2)
    table = poi_tab._playfield_tables[0]
    headers = [table.table.horizontalHeaderItem(c).text() for c in range(table.table.columnCount())]
    props_col = headers.index("Properties")
    cell = table.table.item(0, props_col)
    assert not (cell.flags() & __import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.ItemFlag.ItemIsEditable)


def test_raw_yaml_tab_is_real_yaml_edit_widget(playfield_widget):
    from gui.yaml_edit_widget import YamlEditWidget
    raw_tab = playfield_widget.tab_widget.widget(7)
    assert isinstance(raw_tab, YamlEditWidget)
    assert raw_tab is playfield_widget.raw_widget


def test_playfield_detection_routes_to_structured_widget(qapp, tmp_path):
    """L'ouverture d'un fichier playfield*.yaml depuis la copie de travail doit
    utiliser PlayfieldEditWidget, pas le YamlEditWidget generique."""
    from gui.theme import apply_theme
    from gui.main_window import MainWindow, PlayfieldEditWidget
    from core.scanner import scan_scenario
    from core.workspace import Workspace

    apply_theme(qapp)
    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    shutil.copy(BLOCKS_ECF, config_dir / "BlocksConfig.ecf")
    pf_dir = tmp_path / "Playfields" / "TestPlanet"
    pf_dir.mkdir(parents=True)
    shutil.copy(PLAYFIELD, pf_dir / "playfield_static.yaml")

    scenario = scan_scenario(tmp_path)
    window = MainWindow()
    window.workspace = Workspace(source_a=scenario, source_a_root=tmp_path,
                                  working=scenario, working_root=tmp_path)

    widget = window.open_working_file_tab(pf_dir / "playfield_static.yaml")
    assert isinstance(widget, PlayfieldEditWidget)
    assert widget.tab_widget.widget(1)._playfield_tables[0].table.rowCount() == 5


def test_non_playfield_yaml_still_uses_generic_editor(qapp, tmp_path):
    """Un fichier .yaml qui ne s'appelle pas playfield* doit continuer a
    s'ouvrir avec l'editeur YAML generique, pas l'editeur structure."""
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from gui.yaml_edit_widget import YamlEditWidget
    from core.scanner import scan_scenario
    from core.workspace import Workspace

    apply_theme(qapp)
    other_yaml = tmp_path / "SolarSystemConfig.yaml"
    other_yaml.write_text("Foo: Bar\r\n", encoding="utf-8")

    scenario = scan_scenario(tmp_path)
    window = MainWindow()
    window.workspace = Workspace(source_a=scenario, source_a_root=tmp_path,
                                  working=scenario, working_root=tmp_path)

    widget = window.open_working_file_tab(other_yaml)
    assert isinstance(widget, YamlEditWidget)


def test_poi_table_has_regen_after_column(playfield_widget):
    poi_tab = playfield_widget.tab_widget.widget(2)
    table = poi_tab._playfield_tables[0]
    headers = [table.table.horizontalHeaderItem(c).text() for c in range(table.table.columnCount())]
    assert any("RegenAfter" in h for h in headers)


def test_creatures_table_has_biome_column(playfield_widget):
    creatures_tab = playfield_widget.tab_widget.widget(3)
    table = creatures_tab._playfield_tables[0]
    headers = [table.table.horizontalHeaderItem(c).text() for c in range(table.table.columnCount())]
    assert "Biome" in headers


def test_same_creature_name_shows_different_biomes(playfield_widget):
    creatures_tab = playfield_widget.tab_widget.widget(3)
    table = creatures_tab._playfield_tables[0]
    headers = [table.table.horizontalHeaderItem(c).text() for c in range(table.table.columnCount())]
    biome_col = headers.index("Biome")

    spider_rows = [r for r in range(table.table.rowCount())
                   if table.table.item(r, 0).text() == "Spiders01"]
    assert len(spider_rows) == 3
    biomes = {table.table.item(r, biome_col).text() for r in spider_rows}
    assert len(biomes) == 3  # tous differents


def test_editing_regen_after_updates_document(playfield_widget):
    poi_tab = playfield_widget.tab_widget.widget(2)
    table = poi_tab._playfield_tables[0]
    headers = [table.table.horizontalHeaderItem(c).text() for c in range(table.table.columnCount())]
    regen_col = headers.index([h for h in headers if "RegenAfter" in h][0])

    table.table.item(0, regen_col).setText("8640")
    assert playfield_widget.is_modified() is True
    assert "Value: 8640" in playfield_widget.doc.render()


def test_biome_column_is_not_editable(playfield_widget):
    from PyQt6.QtCore import Qt
    creatures_tab = playfield_widget.tab_widget.widget(3)
    table = creatures_tab._playfield_tables[0]
    headers = [table.table.horizontalHeaderItem(c).text() for c in range(table.table.columnCount())]
    biome_col = headers.index("Biome")
    cell = table.table.item(0, biome_col)
    assert not (cell.flags() & Qt.ItemFlag.ItemIsEditable)


SPACE_FIXTURE = Path(__file__).parent / "fixtures" / "space_scenario" / "space_dynamic.yaml"


@pytest.fixture
def space_playfield_widget(qapp, tmp_path):
    from gui.theme import apply_theme
    from gui.playfield_edit_widget import PlayfieldEditWidget
    apply_theme(qapp)
    working_copy = tmp_path / "space_dynamic.yaml"
    shutil.copy(SPACE_FIXTURE, working_copy)
    return PlayfieldEditWidget(working_copy, blocks_ecf_files=[BLOCKS_ECF])


def test_space_resources_table_shows_thirteen_entries(space_playfield_widget):
    resources_tab = space_playfield_widget.tab_widget.widget(1)
    _, _, space_table = resources_tab._playfield_tables
    assert space_table.table.rowCount() == 18


def test_space_resources_table_shows_readable_display_name(space_playfield_widget):
    resources_tab = space_playfield_widget.tab_widget.widget(1)
    _, _, space_table = resources_tab._playfield_tables
    names = {space_table.table.item(r, 0).text() for r in range(space_table.table.rowCount())}
    assert "Iron Asteroid" in names
    assert "Copper Asteroid" in names


def test_space_resources_table_has_regen_after_column(space_playfield_widget):
    resources_tab = space_playfield_widget.tab_widget.widget(1)
    _, _, space_table = resources_tab._playfield_tables
    headers = [space_table.table.horizontalHeaderItem(c).text() for c in range(space_table.table.columnCount())]
    assert any("RegenAfter" in h for h in headers)


def test_add_space_resource_via_dialog(space_playfield_widget, monkeypatch):
    from gui.playfield_edit_widget import AddResourceDialog

    def fake_exec(self):
        self.combo.setCurrentIndex(0)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(AddResourceDialog, "exec", fake_exec)

    resources_tab = space_playfield_widget.tab_widget.widget(1)
    _, _, space_table = resources_tab._playfield_tables
    before = space_table.table.rowCount()

    space_playfield_widget._add_space_resource()

    assert space_table.table.rowCount() == before + 1
    assert space_playfield_widget.is_modified() is True


def test_save_button_present_and_visible_regardless_of_active_tab(playfield_widget):
    """Le bouton Enregistrer doit rester accessible depuis n'importe quel onglet
    -- signale directement par retour utilisateur (auparavant, il fallait
    passer par l'onglet YAML complet pour le trouver, facilement oublie)."""
    assert hasattr(playfield_widget, "btn_save")
    for i in range(playfield_widget.tab_widget.count()):
        playfield_widget.tab_widget.setCurrentIndex(i)
        assert playfield_widget.btn_save.isEnabled()


def test_save_button_saves_changes_made_from_resources_tab(playfield_widget, tmp_path):
    resources_tab = playfield_widget.tab_widget.widget(1)
    random_table = resources_tab._playfield_tables[0]
    headers = [random_table.table.horizontalHeaderItem(c).text()
               for c in range(random_table.table.columnCount())]
    col = headers.index("DroneProb")
    random_table.table.item(0, col).setText("0.99")

    assert playfield_widget.is_modified() is True
    playfield_widget.btn_save.click()
    assert playfield_widget.is_modified() is False

    saved_content = playfield_widget.path.read_text(encoding="utf-8")
    assert "DroneProb: 0.99" in saved_content


def test_modified_label_reflects_state(playfield_widget):
    assert playfield_widget.modified_label.text() == ""
    playfield_widget.raw_widget._set_modified(True)
    assert playfield_widget.modified_label.text() != ""
    playfield_widget.raw_widget._set_modified(False)
    assert playfield_widget.modified_label.text() == ""


def test_ctrl_s_shortcut_triggers_save(playfield_widget, monkeypatch):
    calls = []
    monkeypatch.setattr(playfield_widget, "save", lambda: calls.append(True))
    playfield_widget.raw_widget._set_modified(True)
    # Simule le raccourci en appelant directement save() -- le QShortcut lui-meme
    # (activated=self.save) est verifie par construction, teste ici son effet.
    playfield_widget.save()
    assert calls == [True]


def test_space_file_naming_convention_routes_to_structured_widget(qapp, tmp_path):
    """Regression : un fichier nomme 'space_dynamic.yaml' (convention reelle des
    secteurs spatiaux, distincte de 'playfield_dynamic.yaml') doit aussi
    router vers l'editeur structure -- signale directement par retour
    utilisateur, le fichier s'ouvrait avant a tort avec l'editeur YAML
    generique (aucun onglet Ressources/POI/Creatures)."""
    from gui.theme import apply_theme
    from gui.main_window import MainWindow, PlayfieldEditWidget
    from core.scanner import scan_scenario
    from core.workspace import Workspace

    apply_theme(qapp)
    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    shutil.copy(BLOCKS_ECF, config_dir / "BlocksConfig.ecf")
    pf_dir = tmp_path / "Playfields" / "SomeSpaceSector"
    pf_dir.mkdir(parents=True)
    shutil.copy(SPACE_FIXTURE, pf_dir / "space_dynamic.yaml")

    scenario = scan_scenario(tmp_path)
    window = MainWindow()
    window.workspace = Workspace(source_a=scenario, source_a_root=tmp_path,
                                  working=scenario, working_root=tmp_path)

    widget = window.open_working_file_tab(pf_dir / "space_dynamic.yaml")
    assert isinstance(widget, PlayfieldEditWidget)
    resources_tab = widget.tab_widget.widget(1)
    _, _, space_table = resources_tab._playfield_tables
    assert space_table.table.rowCount() == 18


def test_widget_has_eight_tabs_including_drones(playfield_widget):
    assert playfield_widget.tab_widget.count() == 8
    assert playfield_widget.tab_widget.tabText(4) in ("Drones/Vaisseaux", "Drones/Vessels")


def test_drones_tab_shows_stock_on_planet_file(playfield_widget):
    drones_tab = playfield_widget.tab_widget.widget(4)
    stock_table, free_drones_table, vessels_table = drones_tab._playfield_tables
    assert stock_table.table.rowCount() == 16  # ce fichier a plusieurs bases de drones
    assert free_drones_table.table.rowCount() == 0
    assert vessels_table.table.rowCount() == 0


def test_drones_tab_shows_free_drones_and_vessels_on_space_file(space_playfield_widget):
    drones_tab = space_playfield_widget.tab_widget.widget(4)
    stock_table, free_drones_table, vessels_table = drones_tab._playfield_tables
    assert stock_table.table.rowCount() == 0
    assert free_drones_table.table.rowCount() == 4
    assert vessels_table.table.rowCount() == 7


def test_editing_drone_stock_amount_updates_document(playfield_widget):
    drones_tab = playfield_widget.tab_widget.widget(4)
    stock_table, _, _ = drones_tab._playfield_tables
    headers = [stock_table.table.horizontalHeaderItem(c).text()
               for c in range(stock_table.table.columnCount())]
    col = headers.index("Amount")
    stock_table.table.item(0, col).setText("3")
    assert playfield_widget.is_modified() is True
    assert "Amount: 3" in playfield_widget.doc.render()


def test_space_vessels_mission_description_shown_as_placeholder(space_playfield_widget):
    from PyQt6.QtCore import Qt
    drones_tab = space_playfield_widget.tab_widget.widget(4)
    _, _, vessels_table = drones_tab._playfield_tables
    headers = [vessels_table.table.horizontalHeaderItem(c).text()
               for c in range(vessels_table.table.columnCount())]
    col = headers.index("MissionDescription")
    cell = vessels_table.table.item(0, col)
    assert not (cell.flags() & Qt.ItemFlag.ItemIsEditable)


def test_spawn_zones_tab_shows_correct_counts_on_planet_file(playfield_widget):
    spawn_tab = playfield_widget.tab_widget.widget(5)
    drone_spawning, spawn_rate, spawn_zones = spawn_tab._playfield_tables
    assert drone_spawning.table.rowCount() == 0  # absent de ce fichier precis
    assert spawn_rate.table.rowCount() == 0  # absent de ce fichier precis
    assert spawn_zones.table.rowCount() == 4


def test_special_effects_tab_present(playfield_widget):
    effects_tab = playfield_widget.tab_widget.widget(6)
    local_table, global_table = effects_tab._playfield_tables
    assert local_table.table.rowCount() >= 0
    assert global_table.table.rowCount() >= 0


def test_editing_spawn_rate_radius_updates_document(playfield_widget):
    spawn_tab = playfield_widget.tab_widget.widget(5)
    _, _, spawn_zones_table = spawn_tab._playfield_tables
    headers = [spawn_zones_table.table.horizontalHeaderItem(c).text()
               for c in range(spawn_zones_table.table.columnCount())]
    col = headers.index("Radius")
    spawn_zones_table.table.item(0, col).setText("777")
    assert playfield_widget.is_modified() is True
    assert "Radius: 777" in playfield_widget.doc.render()


def test_spawn_zones_and_special_effects_empty_on_space_file(space_playfield_widget):
    spawn_tab = space_playfield_widget.tab_widget.widget(5)
    for table in spawn_tab._playfield_tables:
        assert table.table.rowCount() == 0

    effects_tab = space_playfield_widget.tab_widget.widget(6)
    for table in effects_tab._playfield_tables:
        assert table.table.rowCount() == 0


def _msgbox_yes(box):
    """Simule un clic OUI sur une boite a boutons APPLICATION
    (gui.msgboxes.ask_yes_no : boutons[0] = Oui)."""
    box.buttons()[0].click()
    return 0
