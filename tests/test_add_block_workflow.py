"""
Tests du flux complet de creation guidee de bloc/item + Template associe
(gui/add_block_dialog.py + EcfEditWidget._add_block_dialog) -- bases sur de
vrais extraits de BlocksConfig.ecf/ItemsConfig.ecf/Templates.ecf.
"""
import shutil
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QDialog, QMessageBox

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "block_creation_scenario"


@pytest.fixture(autouse=True)
def _stub_localization_offer(monkeypatch):
    """Le flux de creation propose desormais aussi le nom affiche
    (Localization.csv -- obligation no 3, voir core/ecf/creation_check.py) :
    dialogue modal hors perimetre de ces tests, stubbe en refus silencieux."""
    from gui.localization_adjust_dialog import LocalizationAdjustDialog
    monkeypatch.setattr(LocalizationAdjustDialog, "exec",
                        lambda self: QDialog.DialogCode.Rejected)


@pytest.fixture
def window_with_scenario(qapp, tmp_path):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from core.scanner import scan_scenario
    from core.workspace import Workspace

    apply_theme(qapp)
    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    for name in ("BlocksConfig.ecf", "ItemsConfig.ecf", "Templates.ecf"):
        shutil.copy(FIXTURE_DIR / name, config_dir / name)

    scenario = scan_scenario(tmp_path)
    window = MainWindow()
    window.workspace = Workspace(source_a=scenario, source_a_root=tmp_path,
                                  working=scenario, working_root=tmp_path)
    return window, config_dir


def _open_blocks_edit_widget(window, config_dir):
    widget = window.open_working_file_tab(config_dir / "BlocksConfig.ecf")
    return widget.edit_widget


def test_sibling_ecf_files_correctly_transmitted(window_with_scenario):
    window, config_dir = window_with_scenario
    edit_widget = _open_blocks_edit_widget(window, config_dir)
    assert edit_widget.sibling_ecf_files is not None
    names = {p.name for p in edit_widget.sibling_ecf_files}
    assert names == {"BlocksConfig.ecf", "ItemsConfig.ecf", "Templates.ecf"}


def test_ingredients_players_only_checkbox_filters_new_rows(qapp):
    """La case a cocher au-dessus des ingredients doit filtrer la liste
    proposee pour les LIGNES AJOUTEES APRES son activation (voir
    core.ecf.block_creation.list_craftable_names, players_only=True)."""
    from gui.add_block_dialog import PropertyTableDialog, IdentityModeDialog
    from core.yamllite.parser import parse_yaml_text  # noqa: F401 (garde l'import group coherent)
    from core.ecf.parser import parse_ecf_text

    doc = parse_ecf_text("{ Template Name: X\n}\n")
    dialog = PropertyTableDialog(
        doc, IdentityModeDialog.MODE_NAME_ONLY, set(), enable_ingredients=True,
        craftable_names=["IronIngot", "PoiOnlyDecoration"],
        craftable_names_players_only=["IronIngot"])
    assert dialog.ingredients_players_only_check is not None

    dialog._add_ingredient_row()
    combo_before = dialog.ingredients_table.cellWidget(0, 0)
    items_before = [combo_before.itemText(i) for i in range(combo_before.count())]
    assert "PoiOnlyDecoration" in items_before

    dialog.ingredients_players_only_check.setChecked(True)
    dialog._add_ingredient_row()
    combo_after = dialog.ingredients_table.cellWidget(1, 0)
    items_after = [combo_after.itemText(i) for i in range(combo_after.count())]
    assert items_after == ["IronIngot"]


def test_ingredients_no_players_only_checkbox_without_filtered_list(qapp):
    from gui.add_block_dialog import PropertyTableDialog, IdentityModeDialog
    from core.ecf.parser import parse_ecf_text

    doc = parse_ecf_text("{ Template Name: X\n}\n")
    dialog = PropertyTableDialog(
        doc, IdentityModeDialog.MODE_NAME_ONLY, set(), enable_ingredients=True,
        craftable_names=["IronIngot"])
    assert dialog.ingredients_players_only_check is None


def test_full_workflow_creates_block_and_template(window_with_scenario, monkeypatch):
    from gui.add_block_dialog import IdentityModeDialog, PropertyTableDialog
    window, config_dir = window_with_scenario
    edit_widget = _open_blocks_edit_widget(window, config_dir)

    def fake_mode_exec(self):
        self.radio_id_name.setChecked(True)
        self._on_next()
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(IdentityModeDialog, "exec", fake_mode_exec)

    call_count = [0]

    def fake_table_exec(self):
        call_count[0] += 1
        if call_count[0] == 1:
            self.edit_id.setText("999")
            self.edit_name.setText("MyTestBlock")
            self.combo_kind.setCurrentText("Block")
            for checkbox, key, value_combo in self._all_rows:
                if key == "Material":
                    checkbox.setChecked(True)
                    value_combo.setCurrentText("Concrete")
        else:
            self._add_ingredient_row()
            combo = self.ingredients_table.cellWidget(0, 0)
            combo.setCurrentText("IronOre")
            self.ingredients_table.cellWidget(0, 1).setCurrentText("5")
        self._on_validate()
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(PropertyTableDialog, "exec", fake_table_exec)
    monkeypatch.setattr(QMessageBox, "exec", _msgbox_yes)

    edit_widget._add_block_dialog()

    new_block = next((b for b in edit_widget.doc.iter_blocks()
                       if b.get_property("Name") == "MyTestBlock"), None)
    assert new_block is not None
    assert new_block.get("Id") == "999"
    assert new_block.get_property("Material") == "Concrete"
    assert edit_widget.is_modified() is True

    assert window.tabs.count() == 2
    templates_edit = window.tabs.widget(1).edit_widget
    new_template = next((b for b in templates_edit.doc.iter_blocks()
                          if b.get_property("Name") == "MyTestBlock"), None)
    assert new_template is not None
    assert templates_edit.is_modified() is True

    from core.ecf.model import EcfBlock
    child_inputs = [c for c in new_template.children if isinstance(c, EcfBlock) and c.kind == "Child Inputs"]
    assert len(child_inputs) == 1
    ingredient_pairs = [p.pairs[0] for p in child_inputs[0].children if hasattr(p, "pairs")]
    assert ("IronOre", "5") in ingredient_pairs


def test_template_name_prefilled_and_readonly(window_with_scenario, monkeypatch):
    from gui.add_block_dialog import IdentityModeDialog, PropertyTableDialog
    window, config_dir = window_with_scenario
    edit_widget = _open_blocks_edit_widget(window, config_dir)

    monkeypatch.setattr(IdentityModeDialog, "exec", lambda self: (
        self.radio_id_name.setChecked(True), self._on_next(), QDialog.DialogCode.Accepted)[-1])

    captured = {}
    call_count = [0]

    def fake_table_exec(self):
        call_count[0] += 1
        if call_count[0] == 1:
            self.edit_id.setText("999")
            self.edit_name.setText("ExactNameMatch")
        else:
            captured["prefilled_name"] = self.edit_name.text()
            captured["readonly"] = self.edit_name.isReadOnly()
        self._on_validate()
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(PropertyTableDialog, "exec", fake_table_exec)
    monkeypatch.setattr(QMessageBox, "exec", _msgbox_yes)

    edit_widget._add_block_dialog()

    assert captured["prefilled_name"] == "ExactNameMatch"
    assert captured["readonly"] is True


def test_declining_template_prompt_skips_template_creation(window_with_scenario, monkeypatch):
    from gui.add_block_dialog import IdentityModeDialog, PropertyTableDialog
    window, config_dir = window_with_scenario
    edit_widget = _open_blocks_edit_widget(window, config_dir)

    monkeypatch.setattr(IdentityModeDialog, "exec", lambda self: (
        self.radio_id_name.setChecked(True), self._on_next(), QDialog.DialogCode.Accepted)[-1])

    def fake_table_exec(self):
        self.edit_id.setText("999")
        self.edit_name.setText("MyTestBlock")
        self._on_validate()
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(PropertyTableDialog, "exec", fake_table_exec)
    monkeypatch.setattr(QMessageBox, "exec", _msgbox_no)

    edit_widget._add_block_dialog()

    assert window.tabs.count() == 1  # pas de deuxieme onglet Templates.ecf ouvert


def test_no_template_prompt_when_editing_templates_file_itself(window_with_scenario, monkeypatch):
    from gui.add_block_dialog import IdentityModeDialog, PropertyTableDialog
    window, config_dir = window_with_scenario
    widget = window.open_working_file_tab(config_dir / "Templates.ecf")
    edit_widget = widget.edit_widget

    monkeypatch.setattr(IdentityModeDialog, "exec", lambda self: (
        self.radio_name_only.setChecked(True), self._on_next(), QDialog.DialogCode.Accepted)[-1])

    def fake_table_exec(self):
        self.edit_name.setText("SomeNewTemplate")
        self._on_validate()
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(PropertyTableDialog, "exec", fake_table_exec)

    called = []
    def _spy_exec(box):
        called.append(True)
        box.buttons()[0].click()
        return 0
    monkeypatch.setattr(QMessageBox, "exec", _spy_exec)

    edit_widget._add_block_dialog()
    assert called == []  # jamais demande, on est deja dans Templates.ecf


def test_saved_block_and_template_survive_reparse(window_with_scenario, monkeypatch):
    from gui.add_block_dialog import IdentityModeDialog, PropertyTableDialog
    from core.ecf.parser import parse_ecf_file
    window, config_dir = window_with_scenario
    edit_widget = _open_blocks_edit_widget(window, config_dir)

    monkeypatch.setattr(IdentityModeDialog, "exec", lambda self: (
        self.radio_id_name.setChecked(True), self._on_next(), QDialog.DialogCode.Accepted)[-1])

    call_count = [0]

    def fake_table_exec(self):
        call_count[0] += 1
        if call_count[0] == 1:
            self.edit_id.setText("999")
            self.edit_name.setText("MyTestBlock")
        else:
            self._add_ingredient_row()
            self.ingredients_table.cellWidget(0, 0).setCurrentText("IronOre")
            self.ingredients_table.cellWidget(0, 1).setCurrentText("5")
        self._on_validate()
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(PropertyTableDialog, "exec", fake_table_exec)
    monkeypatch.setattr(QMessageBox, "exec", _msgbox_yes)

    edit_widget._add_block_dialog()
    window.tabs.widget(0).save()
    window.tabs.widget(1).save()

    blocks_reparsed = parse_ecf_file(config_dir / "BlocksConfig.ecf")
    assert any(b.get_property("Name") == "MyTestBlock" for b in blocks_reparsed.iter_blocks())
    templates_reparsed = parse_ecf_file(config_dir / "Templates.ecf")
    assert any(b.get_property("Name") == "MyTestBlock" for b in templates_reparsed.iter_blocks())


def test_undo_removes_created_block(window_with_scenario, monkeypatch):
    from gui.add_block_dialog import IdentityModeDialog, PropertyTableDialog
    window, config_dir = window_with_scenario
    edit_widget = _open_blocks_edit_widget(window, config_dir)

    monkeypatch.setattr(IdentityModeDialog, "exec", lambda self: (
        self.radio_id_name.setChecked(True), self._on_next(), QDialog.DialogCode.Accepted)[-1])

    def fake_table_exec(self):
        self.edit_id.setText("999")
        self.edit_name.setText("MyTestBlock")
        self._on_validate()
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(PropertyTableDialog, "exec", fake_table_exec)
    monkeypatch.setattr(QMessageBox, "exec", _msgbox_no)

    edit_widget._add_block_dialog()
    assert any(b.get_property("Name") == "MyTestBlock" for b in edit_widget.doc.iter_blocks())

    edit_widget.undo()
    assert not any(b.get_property("Name") == "MyTestBlock" for b in edit_widget.doc.iter_blocks())


def test_id_validation_rejects_duplicate(window_with_scenario):
    from gui.add_block_dialog import IdentityModeDialog, PropertyTableDialog
    window, config_dir = window_with_scenario
    edit_widget = _open_blocks_edit_widget(window, config_dir)

    existing_id = next(b.get("Id") for b in edit_widget.doc.iter_blocks() if b.get("Id"))
    existing_ids = {b.get('Id') for b in edit_widget.doc.iter_blocks() if b.get('Id')}

    dialog = PropertyTableDialog(edit_widget.doc, IdentityModeDialog.MODE_ID_AND_NAME,
                                  existing_ids, default_kind="Block", parent=edit_widget)
    dialog.edit_id.setText(existing_id)
    dialog.edit_name.setText("Whatever")
    assert existing_id in dialog.id_warning_label.text() or dialog.id_warning_label.text() != ""


def test_id_validation_rejects_over_limit(window_with_scenario):
    from gui.add_block_dialog import IdentityModeDialog, PropertyTableDialog
    from core.ecf.validation import MAX_BLOCK_ID
    window, config_dir = window_with_scenario
    edit_widget = _open_blocks_edit_widget(window, config_dir)

    dialog = PropertyTableDialog(edit_widget.doc, IdentityModeDialog.MODE_ID_AND_NAME,
                                  set(), default_kind="Block", parent=edit_widget)
    dialog.edit_id.setText(str(MAX_BLOCK_ID))
    assert dialog.id_warning_label.text() != ""


def test_property_table_prefills_most_common_value(window_with_scenario):
    from gui.add_block_dialog import IdentityModeDialog, PropertyTableDialog
    window, config_dir = window_with_scenario
    edit_widget = _open_blocks_edit_widget(window, config_dir)

    dialog = PropertyTableDialog(edit_widget.doc, IdentityModeDialog.MODE_ID_AND_NAME,
                                  set(), default_kind="Block", parent=edit_widget)
    material_row = next((r for r in dialog._all_rows if r[1] == "Material"), None)
    assert material_row is not None
    assert material_row[2].currentText() != ""  # une valeur suggeree, pas vide


def test_property_value_is_dropdown_with_all_distinct_values(window_with_scenario):
    """Ajout demande par l'utilisateur : la valeur doit etre un menu deroulant
    (toutes les valeurs distinctes reellement trouvees pour cette propriete,
    pas seulement la plus frequente en texte libre), tout en restant
    editable si aucune ne convient."""
    from gui.add_block_dialog import IdentityModeDialog, PropertyTableDialog
    from PyQt6.QtWidgets import QComboBox
    window, config_dir = window_with_scenario
    edit_widget = _open_blocks_edit_widget(window, config_dir)

    dialog = PropertyTableDialog(edit_widget.doc, IdentityModeDialog.MODE_ID_AND_NAME,
                                  set(), default_kind="Block", parent=edit_widget)
    material_row = next((r for r in dialog._all_rows if r[1] == "Material"), None)
    combo = material_row[2]
    assert isinstance(combo, QComboBox)
    assert combo.isEditable() is True
    assert combo.count() >= 1


def test_name_always_required_even_in_id_and_name_mode(window_with_scenario, monkeypatch):
    """Ajout demande par l'utilisateur : Name n'est jamais reellement
    optionnel (soit Id+Name, soit Name seul) -- doit refuser un Name vide
    meme en mode Id+Name, plutot que de le laisser passer silencieusement."""
    from gui.add_block_dialog import IdentityModeDialog, PropertyTableDialog
    from PyQt6.QtWidgets import QMessageBox
    window, config_dir = window_with_scenario
    edit_widget = _open_blocks_edit_widget(window, config_dir)

    dialog = PropertyTableDialog(edit_widget.doc, IdentityModeDialog.MODE_ID_AND_NAME,
                                  set(), default_kind="Block", parent=edit_widget)
    dialog.edit_id.setText("500")
    dialog.edit_name.setText("")

    warned = []
    monkeypatch.setattr(QMessageBox, "warning",
                         staticmethod(lambda *a, **k: warned.append(True)))
    dialog._on_validate()

    assert warned == [True]
    assert dialog.result_name is None  # jamais valide


def test_name_label_does_not_say_optional(window_with_scenario):
    """Confirme que le libelle du champ Name n'utilise plus la cle partagee
    'ecf.name_optional_label' (mention 'optionnel' trompeuse dans ce
    dialogue, ou Name est en realite toujours requis)."""
    from core.i18n import t
    assert "optionnel" not in t("addblock.name_label").lower()
    assert "optional" not in t("addblock.name_label").lower()


def test_property_filter_hides_non_matching_rows(window_with_scenario):
    from gui.add_block_dialog import IdentityModeDialog, PropertyTableDialog
    window, config_dir = window_with_scenario
    edit_widget = _open_blocks_edit_widget(window, config_dir)

    dialog = PropertyTableDialog(edit_widget.doc, IdentityModeDialog.MODE_ID_AND_NAME,
                                  set(), default_kind="Block", parent=edit_widget)
    dialog.edit_filter.setText("Material")
    material_rows = [i for i, (_, key, _) in enumerate(dialog._all_rows) if key == "Material"]
    other_rows = [i for i, (_, key, _) in enumerate(dialog._all_rows) if key != "Material"]
    if material_rows:
        assert dialog.table.isRowHidden(material_rows[0]) is False
    if other_rows:
        assert dialog.table.isRowHidden(other_rows[0]) is True


# ============================================================================
# Menu deroulant d'items pour LootGroups.ecf (bouton "+ Ligne") -- confirme
# sur un vrai LootGroups.ecf : un seul prefixe utilise ('Item'), toujours des
# noms reels d'ItemsConfig.ecf/BlocksConfig.ecf.
# ============================================================================

def test_add_row_dialog_shows_dropdown_for_lootgroups(window_with_scenario):
    from gui.ecf_edit_widget import AddTableRowDialog
    from core.ecf.block_creation import find_file_by_name, list_craftable_names
    from PyQt6.QtWidgets import QComboBox
    window, config_dir = window_with_scenario

    items_path = find_file_by_name([config_dir / "ItemsConfig.ecf"], "ItemsConfig.ecf")
    suggestions = list_craftable_names(items_path, None)
    dialog = AddTableRowDialog([], ["Item"], None, value_suggestions=suggestions)
    assert isinstance(dialog.value_edit, QComboBox)
    assert dialog.value_edit.isEditable() is True


def test_add_row_dialog_stays_free_text_without_suggestions(window_with_scenario):
    from gui.ecf_edit_widget import AddTableRowDialog
    from PyQt6.QtWidgets import QLineEdit
    window, config_dir = window_with_scenario
    dialog = AddTableRowDialog([], ["Name"], None, value_suggestions=None)
    assert isinstance(dialog.value_edit, QLineEdit)


def test_add_row_dialog_reads_value_from_combobox_correctly(window_with_scenario):
    from gui.ecf_edit_widget import AddTableRowDialog
    window, config_dir = window_with_scenario
    dialog = AddTableRowDialog([], ["Item"], None, value_suggestions=["EmergencyRations", "WaterBottle"])
    dialog.value_edit.setCurrentText("WaterBottle")
    dialog.type_combo.setCurrentText("Item")
    dialog._on_accept()
    assert dialog.result_value == "WaterBottle"
    assert dialog.result_type == "Item"


def test_add_row_dialog_players_only_checkbox_toggles_suggestions(window_with_scenario):
    """La case 'Uniquement les blocs autorises aux joueurs' doit basculer le
    contenu du menu deroulant, sans effacer un texte deja saisi."""
    from gui.ecf_edit_widget import AddTableRowDialog
    window, config_dir = window_with_scenario
    dialog = AddTableRowDialog(
        [], ["Item"], None,
        value_suggestions=["IronIngot", "PoiOnlyDecoration"],
        value_suggestions_players_only=["IronIngot"])
    assert dialog.players_only_check is not None
    assert dialog.value_edit.count() == 2

    dialog.players_only_check.setChecked(True)
    items = [dialog.value_edit.itemText(i) for i in range(dialog.value_edit.count())]
    assert items == ["IronIngot"]

    dialog.players_only_check.setChecked(False)
    items = [dialog.value_edit.itemText(i) for i in range(dialog.value_edit.count())]
    assert "PoiOnlyDecoration" in items


def test_add_row_dialog_no_players_only_checkbox_without_filtered_list(window_with_scenario):
    from gui.ecf_edit_widget import AddTableRowDialog
    window, config_dir = window_with_scenario
    dialog = AddTableRowDialog([], ["Item"], None, value_suggestions=["IronIngot"])
    assert dialog.players_only_check is None


def test_add_row_dialog_group_type_lists_loot_groups(window_with_scenario):
    """Type = 'Group' -> le menu Valeur liste les +LootGroup de LootGroups.ecf
    (ex: Eden_OptronicsT1), Type = 'Name' -> items/blocs du catalogue ; la
    bascule conserve le texte saisi et l'acceptation rend le couple type/valeur."""
    from gui.ecf_edit_widget import AddTableRowDialog
    window, config_dir = window_with_scenario
    dialog = AddTableRowDialog(
        [], ["Name", "Group"], None,
        value_suggestions=["IronOre", "SteelPlate"],
        value_suggestions_players_only=["IronOre"],
        group_suggestions=["Eden_OptronicsT1", "BasicComponents"])

    def _items(dlg):
        return [dlg.value_edit.itemText(i) for i in range(dlg.value_edit.count())]

    assert "IronOre" in _items(dialog)                    # defaut : items
    dialog.type_combo.setCurrentText("Group")             # chemin connecte
    assert "Eden_OptronicsT1" in _items(dialog)
    assert "IronOre" not in _items(dialog)
    dialog.value_edit.setCurrentText("Eden_OptronicsT1")
    dialog.type_combo.setCurrentText("Name")              # texte conserve
    assert dialog.value_edit.currentText() == "Eden_OptronicsT1"
    assert "IronOre" in _items(dialog)
    dialog.players_only_check.setChecked(True)            # filtre joueurs = items seuls
    assert _items(dialog) == ["IronOre"]
    dialog.type_combo.setCurrentText("Group")             # retour groupes
    dialog._on_accept()
    assert dialog.result_type == "Group"
    assert dialog.result_value == "Eden_OptronicsT1"


def test_add_table_row_dialog_wires_lootgroups_suggestions(qapp, tmp_path):
    """Test d'integration complet : ouvre un vrai LootGroups.ecf reduit dans
    un scenario, verifie que _add_table_row_dialog propose bien les vraies
    suggestions -- sans passer par .exec() (bloquant), verifie juste la
    construction du dialogue via un monkeypatch."""
    import shutil
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from gui.ecf_edit_widget import AddTableRowDialog
    from core.scanner import scan_scenario
    from core.workspace import Workspace
    from PyQt6.QtWidgets import QDialog, QComboBox

    apply_theme(qapp)
    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    fixture_dir = FIXTURE_DIR
    shutil.copy(fixture_dir / "LootGroups.ecf", config_dir / "LootGroups.ecf")
    shutil.copy(fixture_dir / "ItemsConfig.ecf", config_dir / "ItemsConfig.ecf")
    shutil.copy(fixture_dir / "BlocksConfig.ecf", config_dir / "BlocksConfig.ecf")

    scenario = scan_scenario(tmp_path)
    window = MainWindow()
    window.workspace = Workspace(source_a=scenario, source_a_root=tmp_path,
                                  working=scenario, working_root=tmp_path)
    widget_wrapper = window.open_working_file_tab(config_dir / "LootGroups.ecf")
    edit_widget = widget_wrapper.edit_widget

    first_block = next(b for b in edit_widget.doc.iter_blocks() if b.get_property("Name") == "EscapePodEasy")
    edit_widget._current_block = first_block
    edit_widget._table_mode = True

    captured = {}
    original_init = AddTableRowDialog.__init__

    def capturing_init(self, *args, **kwargs):
        captured["value_suggestions"] = kwargs.get("value_suggestions")
        original_init(self, *args, **kwargs)

    import unittest.mock
    with unittest.mock.patch.object(AddTableRowDialog, "__init__", capturing_init):
        with unittest.mock.patch.object(QDialog, "exec", lambda self: QDialog.DialogCode.Rejected):
            edit_widget._add_table_row_dialog()

    assert captured["value_suggestions"] is not None
    assert "IronOre" in captured["value_suggestions"]


def test_add_table_row_dialog_wires_suggestions_for_non_lootgroups_files(qapp, tmp_path):
    """Generalisation demandee par l'utilisateur : la liste deroulante
    d'items/blocs du scenario ne doit plus se limiter a LootGroups.ecf --
    disponible sur TOUS les fichiers en mode tableau (le champ reste editable
    dans tous les cas, donc aucun risque a proposer ces suggestions meme sur
    un fichier ou 'Valeur' n'est pas un nom d'item/bloc)."""
    import shutil
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from gui.ecf_edit_widget import AddTableRowDialog
    from core.scanner import scan_scenario
    from core.workspace import Workspace
    from PyQt6.QtWidgets import QDialog

    apply_theme(qapp)
    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    fixture_dir = FIXTURE_DIR
    shutil.copy(fixture_dir / "Containers.ecf", config_dir / "Containers.ecf")
    shutil.copy(fixture_dir / "LootGroups.ecf", config_dir / "LootGroups.ecf")
    shutil.copy(fixture_dir / "ItemsConfig.ecf", config_dir / "ItemsConfig.ecf")
    shutil.copy(fixture_dir / "BlocksConfig.ecf", config_dir / "BlocksConfig.ecf")

    scenario = scan_scenario(tmp_path)
    window = MainWindow()
    window.workspace = Workspace(source_a=scenario, source_a_root=tmp_path,
                                 working=scenario, working_root=tmp_path)
    widget_wrapper = window.open_working_file_tab(config_dir / "Containers.ecf")
    edit_widget = widget_wrapper.edit_widget

    first_block = next(b for b in edit_widget.doc.iter_blocks() if b.get_property("Name") == "SupplyCrateEasy")
    edit_widget._current_block = first_block
    edit_widget._table_mode = True

    captured = {}
    original_init = AddTableRowDialog.__init__

    def capturing_init(self, *args, **kwargs):
        captured["prefixes"] = args[1]
        captured["value_suggestions"] = kwargs.get("value_suggestions")
        captured["group_suggestions"] = kwargs.get("group_suggestions")
        original_init(self, *args, **kwargs)

    import unittest.mock
    with unittest.mock.patch.object(AddTableRowDialog, "__init__", capturing_init):
        with unittest.mock.patch.object(QDialog, "exec", lambda self: QDialog.DialogCode.Rejected):
            edit_widget._add_table_row_dialog()

    assert captured["value_suggestions"] is not None
    assert "IronOre" in captured["value_suggestions"]
    # Type = 'Group' sur Containers.ecf : les +LootGroup du scenario (fixtures)
    # sont proposes a la place des items -- vecu : Eden_OptronicsT1 absent.
    assert captured["group_suggestions"] is not None
    assert "EscapePodEasy" in captured["group_suggestions"]
    # Les deux conventions vanilla de Child Items toujours proposees, meme si
    # le bloc ne contient que des Item_N -- vecu : ajout d'item impossible.
    assert "Name" in captured["prefixes"]
    assert "Group" in captured["prefixes"]


def _msgbox_yes(box):
    """Simule un clic OUI sur une boite a boutons APPLICATION
    (gui.msgboxes.ask_yes_no : boutons[0] = Oui, boutons[1] = Non)."""
    box.buttons()[0].click()
    return 0


def _msgbox_no(box):
    """Simule un clic NON sur une boite a boutons APPLICATION."""
    box.buttons()[1].click()
    return 0


def test_add_row_dialog_group_preselected_shows_loot_groups_immediately(window_with_scenario):
    """Vecu 18/10 : bloc ne contenant QUE des Group_N -> le dialogue ouvre avec
    Type='Group' DEJA selectionne et la liste Valeur montrait les items, car le
    remplissage groups ne se declenchait qu'en CHANGEANT le type. Des
    l'ouverture, Type=Group doit lister les loot groups."""
    from gui.ecf_edit_widget import AddTableRowDialog
    window, config_dir = window_with_scenario
    dialog = AddTableRowDialog(
        [], ["Group"], None,
        value_suggestions=["IronOre", "SteelPlate"],
        group_suggestions=["Eden_OptronicsT1", "BasicComponents"])
    assert dialog.type_combo.currentText() == "Group"      # preselectionne
    items = [dialog.value_edit.itemText(i) for i in range(dialog.value_edit.count())]
    assert "Eden_OptronicsT1" in items
    assert "IronOre" not in items


def test_grid_shows_numbered_type_keys(qapp, tmp_path):
    """Vecu 18/10 : la colonne Type du mode tableau n'affichait pas la
    numerotation (Type='Group' au lieu de 'Group_0'). Affichage de la cle
    COMPLETE, et la saisie d'un nouveau type tolere le suffixe (le N reste
    gere par l'appli, jamais saisi a la main)."""
    from gui.theme import apply_theme
    from gui.ecf_edit_widget import EcfEditWidget
    from core.ecf.model import EcfBlock, EcfProperty
    apply_theme(qapp)
    path = tmp_path / "Containers.ecf"
    path.write_text(
        "{ +Container Id: 1\n"
        "  { Child Items\n"
        "    Name_0: Fiber, param1: 0.5\n"
        "    Name_1: CopperOre, param1: 0.4\n"
        "    Group_0: OresBasic, param1: 0.1\n"
        "  }\n"
        "}\n", encoding="utf-8")
    widget = EcfEditWidget(path)
    container = next(b for b in widget.doc.iter_blocks() if b.kind == "+Container")
    child = next(c for c in container.children if isinstance(c, EcfBlock))
    widget._current_block = child
    widget._refresh_props_table()
    assert widget._table_mode is True
    # numerotation visible dans la colonne Type
    assert widget.props_table.item(0, 0).text() == "Name_0"
    assert widget.props_table.item(1, 0).text() == "Name_1"
    assert widget.props_table.item(2, 0).text() == "Group_0"
    # bascule du type avec suffixe tape : le N existant est conserve
    widget.props_table.item(1, 0).setText("Group_3")       # 'Group_3' = 'Group'
    keys = [c.pairs[0][0] for c in child.children if isinstance(c, EcfProperty)]
    assert "Group_1" in keys                               # suffixe 1 conserve


def test_empty_child_items_containers_stays_table_mode(qapp, tmp_path):
    """Vecu 18/10 : apres suppression de toutes les lignes Group (pour repartir
    de zero avec les lootgroups RE2), le Child Items vide basculait en mode
    ingredients -- '+ Ligne' ouvrait le catalogue d'items au lieu du formulaire
    Name_N/Group_N. Un Child Items vide de Containers.ecf reste en TABLEAU."""
    from gui.theme import apply_theme
    from gui.ecf_edit_widget import EcfEditWidget
    from core.ecf.model import EcfBlock
    apply_theme(qapp)
    path = tmp_path / "Containers.ecf"
    path.write_text("{ +Container Id: 1\n  { Child Items\n  }\n}\n", encoding="utf-8")
    widget = EcfEditWidget(path)
    container = next(b for b in widget.doc.iter_blocks() if b.kind == "+Container")
    child = next(c for c in container.children if isinstance(c, EcfBlock))
    widget._current_block = child
    widget._refresh_props_table()
    assert widget._table_mode is True
    assert widget._ingredient_mode is False
    assert widget.btn_add_row.isVisibleTo(widget) is True
    assert widget.btn_add_prop.isVisibleTo(widget) is False
