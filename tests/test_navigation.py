"""
Tests de la navigation "cliquer pour aller directement au bon endroit" -- ajoutee
suite au dialogue "References croisees" (gui/cross_reference_dialog.py), mais les
methodes testees ici sont reutilisables par tout futur appelant.
"""
import shutil
from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTreeWidgetItemIterator

from core.ecf.model import block_identity

FIXTURE = Path(__file__).parent / "fixtures" / "sample.ecf"


@pytest.fixture
def ecf_widget(qapp, tmp_path):
    from gui.ecf_edit_widget import EcfEditWidget
    working_copy = tmp_path / "sample.ecf"
    shutil.copy(FIXTURE, working_copy)
    return EcfEditWidget(working_copy)


@pytest.fixture
def yaml_widget(qapp, tmp_path):
    from gui.yaml_edit_widget import YamlEditWidget
    path = tmp_path / "test.yaml"
    path.write_text("POIs:\n  - Prefab: MissingPOI\n  - Prefab: OtherPOI\n", encoding="utf-8")
    return YamlEditWidget(path)


def test_select_block_by_identity_top_level(ecf_widget):
    found = ecf_widget.select_block_by_identity("399")
    assert found is True
    assert ecf_widget.tree.currentItem().text(0) == "Block [399]  - ConcreteBlocks"


def test_select_block_by_identity_not_found(ecf_widget):
    found = ecf_widget.select_block_by_identity("nonexistent-id-xyz")
    assert found is False


def test_select_block_by_identity_descends_into_nested_subblock(ecf_widget):
    found = ecf_widget.select_block_by_identity("5", prop_key="Name_0", prop_value="IronOre")
    assert found is True
    # Doit avoir navigue jusqu'au sous-bloc "Child Items", pas etre reste sur la
    # racine "+Container [5]" ou cette valeur n'est pas visible dans le tableau.
    assert ecf_widget.tree.currentItem().text(0) == "Child Items"
    assert ecf_widget.props_table.currentItem().text() == "IronOre"


def test_select_block_by_identity_falls_back_to_root_when_prop_not_found(ecf_widget):
    # La propriete demandee n'existe nulle part -- doit quand meme selectionner le
    # bloc racine plutot que d'echouer completement.
    found = ecf_widget.select_block_by_identity("399", prop_key="Name_0", prop_value="DoesNotExist")
    assert found is True
    assert ecf_widget.tree.currentItem().text(0) == "Block [399]  - ConcreteBlocks"


def test_undo_keeps_selection_when_identity_property_edited(ecf_widget):
    # ECF-005 : editer la propriete Id elle-meme change l'identite du bloc APRES
    # la modification ; l'identite doit avoir ete captee au snapshot (avant
    # modification), sinon l'undo laisse l'arbre en haut sans selection.
    ecf_widget.select_block_by_identity("399")
    block = ecf_widget._current_block
    ecf_widget._snapshot_undo()
    block.set("Id", "99999")
    ecf_widget.undo()
    current = ecf_widget.tree.currentItem()
    assert current is not None
    assert block_identity(current.data(0, Qt.ItemDataRole.UserRole)) == "399"


def test_undo_stays_on_block_clicked_after_edit(ecf_widget):
    # ECF-005 pas 2 : modifier, puis CLIQUER ailleurs dans l'arbre, puis Ctrl+Z
    # -> l'annulation ne doit pas deplacer la selection.
    ecf_widget.select_block_by_identity("399")
    block = ecf_widget._current_block
    ecf_widget._snapshot_undo()
    block.set("HitPoints", "1")
    ecf_widget.select_block_by_identity("5")
    ecf_widget.undo()
    current = ecf_widget.tree.currentItem()
    assert current is not None
    assert block_identity(current.data(0, Qt.ItemDataRole.UserRole)) == "5"


def test_select_entry_by_key_value_found(yaml_widget):
    found = yaml_widget.select_entry_by_key_value("Prefab", "MissingPOI")
    assert found is True
    assert yaml_widget.tree.currentItem().text(0) == "Prefab"
    assert yaml_widget.tree.currentItem().text(1) == "MissingPOI"


def test_select_entry_by_key_value_not_found(yaml_widget):
    found = yaml_widget.select_entry_by_key_value("Prefab", "NoSuchValue")
    assert found is False


def test_select_entry_by_key_value_distinguishes_same_key_different_value(yaml_widget):
    found_first = yaml_widget.select_entry_by_key_value("Prefab", "MissingPOI")
    assert found_first is True
    first_selection = yaml_widget.tree.currentItem()

    found_second = yaml_widget.select_entry_by_key_value("Prefab", "OtherPOI")
    assert found_second is True
    second_selection = yaml_widget.tree.currentItem()

    assert first_selection is not second_selection


@pytest.fixture
def workspace_with_scenario(tmp_path):
    from core.scanner import scan_scenario
    from core.workspace import Workspace

    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    shutil.copy(
        Path(__file__).parent / "fixtures" / "cross_ref_scenario" / "Containers.ecf",
        config_dir / "Containers.ecf")
    shutil.copy(
        Path(__file__).parent / "fixtures" / "cross_ref_scenario" / "TokenConfig.ecf",
        config_dir / "TokenConfig.ecf")

    scenario = scan_scenario(tmp_path)
    return Workspace(source_a=scenario, source_a_root=tmp_path, working=scenario, working_root=tmp_path)


def test_dialog_navigate_opens_and_selects_correct_cell(qapp, workspace_with_scenario):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from gui.cross_reference_dialog import CrossReferenceDialog

    apply_theme(qapp)
    window = MainWindow()
    window.workspace = workspace_with_scenario

    dialog = CrossReferenceDialog(workspace_with_scenario, window, parent=window)
    dialog._do_run()
    assert dialog.results_list.count() >= 1

    dialog._navigate_to_issue(dialog.results_list.item(0))

    assert window.tabs.count() == 1
    widget = window.tabs.currentWidget()
    edit_widget = getattr(widget, "edit_widget", widget)
    assert edit_widget.path.name == "Containers.ecf"


def test_dialog_navigate_reuses_existing_tab_instead_of_duplicating(qapp, workspace_with_scenario):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from gui.cross_reference_dialog import CrossReferenceDialog

    apply_theme(qapp)
    window = MainWindow()
    window.workspace = workspace_with_scenario

    dialog = CrossReferenceDialog(workspace_with_scenario, window, parent=window)
    dialog._do_run()
    assert dialog.results_list.count() >= 2  # NonExistentItem + Token:9999, meme fichier

    dialog._navigate_to_issue(dialog.results_list.item(0))
    dialog._navigate_to_issue(dialog.results_list.item(1))

    assert window.tabs.count() == 1  # meme fichier -> reactive l'onglet, n'en cree pas un second


def test_tree_has_no_icons(ecf_widget, qapp, tmp_path):
    """Retour utilisateur 09/09/2026 : les icones de l'ARBRE etaient trop
    longues a charger sur les gros fichiers -> retirees volontairement (elles
    restent dans la fiche info, le catalogue, le tableau economie et la table
    d'ingredients)."""
    ecf_widget.working_root = tmp_path
    ecf_widget._info_card_icon_index = {}
    ecf_widget._populate_tree()
    for _ in range(10):
        qapp.processEvents()
    it = QTreeWidgetItemIterator(ecf_widget.tree)
    while it.value():
        assert it.value().icon(0).isNull()
        it += 1


# ------------------------- mode ingredients RE2 (Child Inputs 'Item: qty') --

RE2_STYLE = """{ +Template Id: 4000, Name: GrowingPotRE2
  { Child Inputs
    RockDust: 25
    NutrientSolution: 2
  }
}

{ Block Name: LegacyForcefield
  Material: metal
}
"""


@pytest.fixture
def re2_widget(qapp, tmp_path):
    from gui.ecf_edit_widget import EcfEditWidget
    working_copy = tmp_path / "Templates.ecf"
    working_copy.write_text(RE2_STYLE, encoding="utf-8")
    widget = EcfEditWidget(working_copy)
    widget.show()
    yield widget
    widget.close()


def _find_block_item(widget, needle):
    it = QTreeWidgetItemIterator(widget.tree)
    while it.value():
        item = it.value()
        if needle in item.text(0):
            return item
        it += 1
    return None


def test_re2_ingredient_mode_ui_and_catalog_insert(re2_widget, qapp, tmp_path):
    from PyQt6.QtGui import QIcon, QPixmap
    re2_widget.working_root = tmp_path
    re2_widget._info_card_icon_index = {}
    # selectionne Child Inputs dans l'arbre
    item = _find_block_item(re2_widget, "Child Inputs")
    re2_widget.tree.setCurrentItem(item)
    re2_widget._on_block_selected(item, 0)
    assert re2_widget._ingredient_mode is True
    assert re2_widget._table_mode is False
    assert re2_widget.btn_add_row.isVisible()
    assert re2_widget.props_table.rowCount() == 2
    assert re2_widget.props_table.item(0, 0).text() == "RockDust"
    # edition inline : quantite (colonne 1)
    re2_widget.props_table.item(0, 1).setText("30")
    assert "RockDust: 30" in re2_widget.doc.render()
    # edition inline : renommage d'item (colonne 0)
    re2_widget.props_table.item(1, 0).setText("CobaltAlloy")
    assert "CobaltAlloy: 2" in re2_widget.doc.render()
    # insertion depuis le catalogue : une seule ligne 'Item: 1' par item choisi
    from core.item_catalog import CatalogEntry
    re2_widget._catalog_entries_cache = [
        CatalogEntry(name="MedPack", source="item", category="Medical",
                     market_price=126.0, icon_key="MedPack")]
    re2_widget._insert_catalog_items(re2_widget._catalog_entries_cache)
    out = re2_widget.doc.render()
    assert "MedPack: 1" in out
    assert re2_widget.props_table.rowCount() == 3
    # le fichier reste re-parsable
    from core.ecf.parser import parse_ecf_text
    assert parse_ecf_text(out) is not None


def test_detect_ingredient_pairs_core(tmp_path):
    """Detection des blocs d'ingredients RE2 ('ItemName: quantite') : accepte
    les paires simples (meme bloc vide -> []), refuse le motif vanilla
    Name_N/param1 (qui reste du ressort de detect_repeating_items)."""
    from core.ecf.parser import parse_ecf_text
    from core.ecf.model import EcfBlock, detect_ingredient_pairs, detect_repeating_items
    text = ("{ +Template Id: 1\n"
            "  { Child Inputs\n"
            "    RockDust: 25\n"
            "  }\n"
            "}\n"
            "{ +Template Id: 2\n"
            "  { Child Inputs\n"
            "  }\n"
            "}\n"
            "{ +Template Id: 3\n"
            "  { Child Items\n"
            "    Name_0: Fiber, param1: 20\n"
            "    Name_1: CopperOre, param1: 30\n"
            "  }\n"
            "}\n")
    doc = parse_ecf_text(text)
    blocks = []

    def walk(b):
        for c in b.children:
            if isinstance(c, EcfBlock):
                blocks.append(c)
                walk(c)

    for n in doc.nodes:
        if isinstance(n, EcfBlock):
            blocks.append(n)
            walk(n)
    inputs = [b for b in blocks if b.kind.lower() == "child inputs"]
    assert detect_ingredient_pairs(inputs[0]) is not None
    assert detect_ingredient_pairs(inputs[1]) == []            # vide mais genre ok
    child_items = [b for b in blocks if b.kind.lower() == "child items"][0]
    assert detect_ingredient_pairs(child_items) is None        # motif vanilla
    assert detect_repeating_items(child_items) is not None


def test_ingredient_table_icons_from_cache(re2_widget, qapp, tmp_path):
    """Icones dans la table Child Inputs : icone devant le nom d'item quand
    resoluble (cache pre-rempli -> deterministe), aucune sinon."""
    from PyQt6.QtGui import QIcon, QPixmap
    re2_widget._info_card_icon_index = {}
    pm = QPixmap(16, 16)
    pm.fill()
    re2_widget._child_icon_cache = {"RockDust": pm}
    item = _find_block_item(re2_widget, "Child Inputs")
    re2_widget.tree.setCurrentItem(item)
    re2_widget._on_block_selected(item, 0)
    assert re2_widget.props_table.item(0, 0).icon().isNull() is False   # RockDust
    assert re2_widget.props_table.item(1, 0).icon().isNull() is True    # NutrientSolution
