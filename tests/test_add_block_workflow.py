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
            self.ingredients_table.item(0, 1).setText("5")
        self._on_validate()
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(PropertyTableDialog, "exec", fake_table_exec)
    monkeypatch.setattr(QMessageBox, "question",
                         staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))

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
    monkeypatch.setattr(QMessageBox, "question",
                         staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))

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
    monkeypatch.setattr(QMessageBox, "question",
                         staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))

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
    monkeypatch.setattr(QMessageBox, "question",
                         staticmethod(lambda *a, **k: called.append(True) or QMessageBox.StandardButton.Yes))

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
            self.ingredients_table.item(0, 1).setText("5")
        self._on_validate()
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(PropertyTableDialog, "exec", fake_table_exec)
    monkeypatch.setattr(QMessageBox, "question",
                         staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))

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
    monkeypatch.setattr(QMessageBox, "question",
                         staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))

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
