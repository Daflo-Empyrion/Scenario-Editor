# Empyrion Scenario Editor
# Copyright (C) 2026  Daflo
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Tests d'integration widget pour la duplication de bloc/ligne (simple et
multi-variantes) -- gui/ecf_edit_widget.py::_duplicate_block_action et
_duplicate_row_action, cables au VRAI widget Qt."""
import shutil
from pathlib import Path

import pytest

from core.ecf.model import EcfBlock, EcfProperty

BLOCKS_FIXTURE = Path(__file__).parent / "fixtures" / "block_creation_scenario" / "BlocksConfig.ecf"
LOOTGROUPS_FIXTURE = Path(__file__).parent / "fixtures" / "block_creation_scenario" / "LootGroups.ecf"


@pytest.fixture
def blocks_widget(qapp, tmp_path):
    from gui.ecf_edit_widget import EcfEditWidget
    working_copy = tmp_path / "BlocksConfig.ecf"
    shutil.copy(BLOCKS_FIXTURE, working_copy)
    return EcfEditWidget(working_copy)


@pytest.fixture
def lootgroups_widget(qapp, tmp_path):
    from gui.ecf_edit_widget import EcfEditWidget
    working_copy = tmp_path / "LootGroups.ecf"
    shutil.copy(LOOTGROUPS_FIXTURE, working_copy)
    return EcfEditWidget(working_copy)


def _select_block_by_name(widget, name):
    for block in widget.doc.iter_blocks():
        if block.get_property("Name") == name:
            widget._current_block = block
            widget._refresh_props_table()
            return block
    raise AssertionError(f"bloc {name} introuvable dans le fixture")


@pytest.fixture(autouse=True)
def _no_blocking_message_boxes(monkeypatch):
    """Empeche tout QMessageBox.warning/information/question de bloquer
    l'execution des tests en mode headless (une vraie boite modale
    attendrait indefiniment un clic utilisateur qui ne viendra jamais) --
    filet de securite en plus des monkeypatch explicites par test."""
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)


# ---------------------------------------------------------------------
# Duplication de bloc -- mode simple
# ---------------------------------------------------------------------

def test_duplicate_block_simple_inserts_new_block(blocks_widget, monkeypatch):
    from gui.duplicate_variants_dialog import DuplicateVariantsDialog
    from PyQt6.QtWidgets import QDialog

    block = _select_block_by_name(blocks_widget, "IronResource")

    def fake_exec(self):
        self.result_new_name = "IronResourceCopy"
        self.result_new_id = None
        self.result_remove_id = True  # sinon collision sur l'Id d'origine inchange
        self.result_multi = None
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(DuplicateVariantsDialog, "exec", fake_exec)
    blocks_widget._duplicate_block_action(block)

    names = [b.get_property("Name") for b in blocks_widget.doc.iter_blocks()]
    assert "IronResourceCopy" in names
    assert blocks_widget.is_modified()


def test_duplicate_block_simple_blocks_collision(blocks_widget, monkeypatch, qapp):
    from gui.duplicate_variants_dialog import DuplicateVariantsDialog
    from PyQt6.QtWidgets import QDialog, QMessageBox

    block = _select_block_by_name(blocks_widget, "IronResource")
    other_name = next(
        b.get_property("Name") for b in blocks_widget.doc.iter_blocks()
        if b.get_property("Name") and b.get_property("Name") != "IronResource"
    )

    def fake_exec(self):
        self.result_new_name = other_name  # collision volontaire
        self.result_new_id = None
        self.result_remove_id = False
        self.result_multi = None
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(DuplicateVariantsDialog, "exec", fake_exec)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)

    before_count = sum(1 for _ in blocks_widget.doc.iter_blocks())
    blocks_widget._duplicate_block_action(block)
    after_count = sum(1 for _ in blocks_widget.doc.iter_blocks())
    assert before_count == after_count  # rien insere en cas de collision


# ---------------------------------------------------------------------
# Duplication de bloc -- mode multi-variantes
# ---------------------------------------------------------------------

def test_duplicate_block_multi_variant_creates_named_variants(blocks_widget, monkeypatch, qapp):
    from gui.duplicate_variants_dialog import DuplicateVariantsDialog
    from PyQt6.QtWidgets import QDialog, QMessageBox

    block = _select_block_by_name(blocks_widget, "IronResource")

    def fake_exec(self):
        self.result_multi = {
            'num_variants': 3, 'varying_fields': ['XpFactor'],
            'total_percent': 20.0, 'first_is_original': True,
        }
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(DuplicateVariantsDialog, "exec", fake_exec)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)

    blocks_widget._duplicate_block_action(block)

    names = [b.get_property("Name") for b in blocks_widget.doc.iter_blocks()]
    assert "IronResourceT1" in names
    assert "IronResourceT2" in names
    assert "IronResourceT3" in names
    assert blocks_widget.is_modified()


def test_duplicate_block_multi_variant_inserted_right_after_source(blocks_widget, monkeypatch, qapp):
    from gui.duplicate_variants_dialog import DuplicateVariantsDialog
    from PyQt6.QtWidgets import QDialog, QMessageBox

    block = _select_block_by_name(blocks_widget, "IronResource")

    def fake_exec(self):
        self.result_multi = {
            'num_variants': 2, 'varying_fields': [], 'total_percent': 10.0, 'first_is_original': True,
        }
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(DuplicateVariantsDialog, "exec", fake_exec)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)

    blocks_widget._duplicate_block_action(block)

    top_level_names = [n.get_property("Name") for n in blocks_widget.doc.nodes if isinstance(n, EcfBlock)]
    idx_source = top_level_names.index("IronResource")
    assert top_level_names[idx_source + 1] == "IronResourceT1"
    assert top_level_names[idx_source + 2] == "IronResourceT2"


# ---------------------------------------------------------------------
# Duplication de ligne (mode tableau) -- simple et multi-variantes
# ---------------------------------------------------------------------

def _find_row_by_value(block, value):
    for child in block.children:
        if isinstance(child, EcfProperty) and child.pairs and child.pairs[0][1] == value:
            return child
    raise AssertionError(f"ligne avec valeur {value} introuvable")


def test_duplicate_row_simple_inserts_new_row(lootgroups_widget, monkeypatch, qapp):
    from gui.duplicate_variants_dialog import DuplicateVariantsDialog
    from PyQt6.QtWidgets import QDialog

    block = _select_block_by_name(lootgroups_widget, "EscapePodEasy")
    row = _find_row_by_value(block, "WaterBottle")

    def fake_exec(self):
        self.result_new_name = "WaterBottleCopy"
        self.result_multi = None
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(DuplicateVariantsDialog, "exec", fake_exec)
    lootgroups_widget._duplicate_row_action(row)

    values = [c.pairs[0][1] for c in block.children if isinstance(c, EcfProperty) and c.pairs]
    assert "WaterBottleCopy" in values
    assert lootgroups_widget.is_modified()


def test_duplicate_row_multi_variant_creates_named_variants_with_percent(lootgroups_widget, monkeypatch, qapp):
    from gui.duplicate_variants_dialog import DuplicateVariantsDialog
    from PyQt6.QtWidgets import QDialog, QMessageBox

    block = _select_block_by_name(lootgroups_widget, "EscapePodEasy")
    row = _find_row_by_value(block, "WaterBottle")

    def fake_exec(self):
        self.result_multi = {
            'num_variants': 3, 'varying_fields': ['param1'],
            'total_percent': 100.0, 'first_is_original': True,
        }
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(DuplicateVariantsDialog, "exec", fake_exec)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)

    lootgroups_widget._duplicate_row_action(row)

    new_rows = {
        c.pairs[0][1]: c.get("param1")
        for c in block.children if isinstance(c, EcfProperty) and c.pairs
        and c.pairs[0][1] in ("WaterBottleT1", "WaterBottleT2", "WaterBottleT3")
    }
    assert new_rows["WaterBottleT1"] == "5"
    assert new_rows["WaterBottleT2"] == "8"
    assert new_rows["WaterBottleT3"] == "10"


def test_duplicate_row_blocks_name_collision(lootgroups_widget, monkeypatch, qapp):
    from gui.duplicate_variants_dialog import DuplicateVariantsDialog
    from PyQt6.QtWidgets import QDialog, QMessageBox

    block = _select_block_by_name(lootgroups_widget, "EscapePodEasy")
    row = _find_row_by_value(block, "WaterBottle")

    def fake_exec(self):
        self.result_new_name = "EmergencyRations"  # deja utilise par une autre ligne
        self.result_multi = None
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(DuplicateVariantsDialog, "exec", fake_exec)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)

    before_count = len([c for c in block.children if isinstance(c, EcfProperty)])
    lootgroups_widget._duplicate_row_action(row)
    after_count = len([c for c in block.children if isinstance(c, EcfProperty)])
    assert before_count == after_count


# ---------------------------------------------------------------------
# Apercu editable des proprietes pendant la duplication (demande explicite
# de l'utilisateur, session du 29/08/2026) -- gui/property_edit_table.py,
# DuplicateVariantsDialog.result_field_overrides
# ---------------------------------------------------------------------

def test_duplicate_block_simple_applies_field_overrides(blocks_widget, monkeypatch):
    """L'apercu editable applique bien les valeurs modifiees au duplicata --
    pas seulement Id/Name (deja geres), mais n'importe quel autre champ."""
    from gui.duplicate_variants_dialog import DuplicateVariantsDialog
    from PyQt6.QtWidgets import QDialog

    block = _select_block_by_name(blocks_widget, "IronResource")

    def fake_exec(self):
        self.result_new_name = "IronResourceCopy"
        self.result_new_id = None
        self.result_remove_id = True
        self.result_multi = None
        self.result_field_overrides = {"Material": "resourcehard", "XpFactor": "9.5"}
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(DuplicateVariantsDialog, "exec", fake_exec)
    blocks_widget._duplicate_block_action(block)

    new_block = next(b for b in blocks_widget.doc.iter_blocks() if b.get_property("Name") == "IronResourceCopy")
    assert new_block.get_property("Material") == "resourcehard"
    assert new_block.get_property("XpFactor") == "9.5"
    # L'original ne doit JAMAIS etre touche.
    assert block.get_property("Material") == "resourcesoft"
    assert block.get_property("XpFactor") == "2.0"


def test_duplicate_block_simple_field_overrides_reach_nested_sub_block(blocks_widget, monkeypatch):
    """Un champ situe dans un sous-bloc imbrique ('{ Child DropOnDestroy }')
    doit lui aussi etre modifiable via l'apercu -- meme mecanisme que
    set_block_field, deja recursif."""
    from gui.duplicate_variants_dialog import DuplicateVariantsDialog
    from PyQt6.QtWidgets import QDialog

    block = _select_block_by_name(blocks_widget, "IronResource")

    def fake_exec(self):
        self.result_new_name = "IronResourceCopy2"
        self.result_new_id = None
        self.result_remove_id = True
        self.result_multi = None
        self.result_field_overrides = {"Prob": "0.99"}  # dans Child DropOnDestroy
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(DuplicateVariantsDialog, "exec", fake_exec)
    blocks_widget._duplicate_block_action(block)

    from core.ecf.variants import get_block_field
    new_block = next(b for b in blocks_widget.doc.iter_blocks() if b.get_property("Name") == "IronResourceCopy2")
    assert get_block_field(new_block, "Prob") == "0.99"
    assert get_block_field(block, "Prob") == "0.6"  # original inchange


def test_duplicate_block_multi_variant_applies_overrides_to_all(blocks_widget, monkeypatch, qapp):
    """En mode multi-variantes, les ajustements de l'apercu s'appliquent a
    TOUTES les variantes creees (demande explicite de l'utilisateur)."""
    from gui.duplicate_variants_dialog import DuplicateVariantsDialog
    from PyQt6.QtWidgets import QDialog

    block = _select_block_by_name(blocks_widget, "IronResource")

    def fake_exec(self):
        self.result_multi = {
            'num_variants': 2, 'varying_fields': [], 'total_percent': 0.0,
            'first_is_original': True,
        }
        self.result_field_overrides = {"Material": "resourcehard"}
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(DuplicateVariantsDialog, "exec", fake_exec)
    blocks_widget._duplicate_block_action(block)

    variants = [b for b in blocks_widget.doc.iter_blocks()
                if b.get_property("Name") in ("IronResourceT1", "IronResourceT2")]
    assert len(variants) == 2
    for v in variants:
        assert v.get_property("Material") == "resourcehard"


def test_duplicate_dialog_property_table_populated_from_source_block(qapp):
    """Le tableau d'apercu est bien rempli avec les vraies proprietes du
    bloc source quand source_block est fourni."""
    from gui.duplicate_variants_dialog import DuplicateVariantsDialog
    from core.ecf.parser import parse_ecf_text

    text = "{ Block Id: 1, Name: Test\n  Material: resourcehard\n  XpFactor: 6.0\n}\n"
    doc = parse_ecf_text(text)
    block = next(doc.iter_blocks())

    dialog = DuplicateVariantsDialog("1", "Test", [], [], source_block=block)
    assert dialog.property_table is not None
    keys = [dialog.property_table.item(r, 0).text() for r in range(dialog.property_table.rowCount())]
    assert "Material" in keys
    assert "XpFactor" in keys
    assert "Id" not in keys
    assert "Name" not in keys


def test_duplicate_dialog_no_property_table_without_source_block(qapp):
    """Sans source_block (ex: mode ligne de tableau), pas de section
    d'apercu -- comportement inchange pour ce cas."""
    from gui.duplicate_variants_dialog import DuplicateVariantsDialog

    dialog = DuplicateVariantsDialog(None, "Test", [], [], show_id_field=False)
    assert dialog.property_table is None


# ---------------------------------------------------------------------
# Ajustement du/des Template(s) auto-cree(s) (demande explicite de
# l'utilisateur, session du 29/08/2026) -- gui/template_adjust_dialog.py,
# gui/ecf_edit_widget.py::_create_templates_for_variants
# ---------------------------------------------------------------------

TEMPLATES_FIXTURE = Path(__file__).parent / "fixtures" / "block_creation_scenario" / "Templates.ecf"


@pytest.fixture
def blocks_widget_with_templates(qapp, tmp_path):
    """Comme blocks_widget, mais avec Templates.ecf comme fichier voisin ET
    un faux 'main_window.open_working_file_tab' qui ouvre reellement un
    EcfEditWidget sur Templates.ecf (reutilise a chaque appel, comme un
    vrai onglet) -- necessaire pour tester le flux complet de creation de
    Template."""
    from gui.ecf_edit_widget import EcfEditWidget

    blocks_path = tmp_path / "BlocksConfig.ecf"
    templates_path = tmp_path / "Templates.ecf"
    shutil.copy(BLOCKS_FIXTURE, blocks_path)
    shutil.copy(TEMPLATES_FIXTURE, templates_path)

    widget = EcfEditWidget(blocks_path, sibling_ecf_files=[blocks_path, templates_path])

    opened = {}

    class _FakeMainWindow:
        def open_working_file_tab(self, path):
            key = str(path)
            if key not in opened:
                opened[key] = EcfEditWidget(path)
            return opened[key]

    fake_window = _FakeMainWindow()
    widget.window = lambda: fake_window
    widget._opened_tabs = opened  # expose pour verification dans les tests
    return widget


def test_duplicate_multi_variant_within_working_copy_proposes_and_creates_templates(
        blocks_widget_with_templates, monkeypatch):
    """Retour utilisateur clarifie (29/08/2026) : la demande initiale
    concernait bien la duplication AU SEIN de la copie de travail -- la
    proposition de creation de Template(s) doit s'y declencher."""
    from gui.duplicate_variants_dialog import DuplicateVariantsDialog
    from gui.template_adjust_dialog import TemplateAdjustDialog
    from PyQt6.QtWidgets import QDialog, QMessageBox

    widget = blocks_widget_with_templates
    block = _select_block_by_name(widget, "IronResource")

    def fake_exec(self):
        self.result_multi = {
            'num_variants': 2, 'varying_fields': [], 'total_percent': 0.0,
            'first_is_original': True,
        }
        self.result_field_overrides = {}
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(DuplicateVariantsDialog, "exec", fake_exec)
    monkeypatch.setattr(QMessageBox, "exec", _msgbox_yes)
    monkeypatch.setattr(TemplateAdjustDialog, "exec", lambda self: QDialog.DialogCode.Accepted)

    widget._duplicate_block_action(block)

    templates_widget = widget._opened_tabs[str(widget.sibling_ecf_files[1])]
    names = [b.get_property("Name") for b in templates_widget.doc.iter_blocks()]
    assert "IronResourceT1" in names
    assert "IronResourceT2" in names


def test_duplicate_simple_within_working_copy_proposes_and_creates_template(
        blocks_widget_with_templates, monkeypatch):
    """Meme comportement en mode copie unique (pas seulement multi-variantes)."""
    from gui.duplicate_variants_dialog import DuplicateVariantsDialog
    from gui.template_adjust_dialog import TemplateAdjustDialog
    from PyQt6.QtWidgets import QDialog, QMessageBox

    widget = blocks_widget_with_templates
    block = _select_block_by_name(widget, "IronResource")

    def fake_exec(self):
        self.result_new_id = None
        self.result_new_name = "IronResourceCopy"
        self.result_remove_id = True
        self.result_multi = None
        self.result_field_overrides = {}
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(DuplicateVariantsDialog, "exec", fake_exec)
    monkeypatch.setattr(QMessageBox, "exec", _msgbox_yes)
    monkeypatch.setattr(TemplateAdjustDialog, "exec", lambda self: QDialog.DialogCode.Accepted)

    widget._duplicate_block_action(block)

    templates_widget = widget._opened_tabs[str(widget.sibling_ecf_files[1])]
    names = [b.get_property("Name") for b in templates_widget.doc.iter_blocks()]
    assert "IronResourceCopy" in names


def test_template_adjust_dialog_overrides_applied_when_invoked_directly(qapp):
    """La mecanique d'ajustement du Template elle-meme (TemplateAdjustDialog
    + list_editable_fields_block + set_block_field) reste correcte et
    testee independamment de son declenchement automatique."""
    from core.ecf.parser import parse_ecf_text
    from core.ecf.variants import list_editable_fields_block, set_block_field, get_block_field
    import copy as _copy

    text = (
        "{ Template Name: IronResource\n"
        "  CraftTime: 3\n"
        "  { Child Inputs\n"
        "    RockDust: 10\n"
        "  }\n"
        "}\n"
    )
    doc = parse_ecf_text(text)
    source_template = next(doc.iter_blocks())

    fields = list_editable_fields_block(source_template)
    assert dict(fields)["CraftTime"] == "3"

    new_template = _copy.deepcopy(source_template)
    set_block_field(new_template, "CraftTime", "99")
    assert get_block_field(new_template, "CraftTime") == "99"
    assert source_template.get_property("CraftTime") == "3"  # original inchange


def test_template_adjust_dialog_populated_from_source_template_fields(qapp):
    from gui.template_adjust_dialog import TemplateAdjustDialog
    from core.ecf.parser import parse_ecf_text
    from core.ecf.variants import list_template_scalar_fields, list_template_ingredients

    text = (
        "{ Template Name: Test\n"
        "  CraftTime: 5\n"
        "  { Child Inputs\n"
        "    RockDust: 25\n"
        "  }\n"
        "}\n"
    )
    doc = parse_ecf_text(text)
    tpl = next(doc.iter_blocks())

    dialog = TemplateAdjustDialog(
        ["TestT1", "TestT2"], list_template_scalar_fields(tpl), list_template_ingredients(tpl),
        ["Electronics", "RockDust"])
    editor = dialog._editors["TestT1"]
    scalar_keys = [editor.scalar_table.item(r, 0).text() for r in range(editor.scalar_table.rowCount())]
    ingredient_keys = [editor.ingredients_table.item(r, 0).text() for r in range(editor.ingredients_table.rowCount())]
    assert "CraftTime" in scalar_keys
    assert "RockDust" in ingredient_keys


# ---------------------------------------------------------------------
# Nom affiche (Localization.csv) pendant la duplication (demande explicite
# de l'utilisateur, session du 29/08/2026) -- gui/localization_adjust_dialog.py
# ---------------------------------------------------------------------

@pytest.fixture
def blocks_widget_with_localization(qapp, tmp_path):
    """Comme blocks_widget, avec en plus Extras/Localization.csv contenant
    une traduction pour IronResource, servant de base pre-remplie."""
    from gui.ecf_edit_widget import EcfEditWidget
    working_copy = tmp_path / "BlocksConfig.ecf"
    shutil.copy(BLOCKS_FIXTURE, working_copy)
    extras_dir = tmp_path / "Extras"
    extras_dir.mkdir(parents=True)
    (extras_dir / "Localization.csv").write_text(
        "KEY,English,Français\nIronResource,Iron Resource,Ressource de Fer\n", encoding='utf-8')
    return EcfEditWidget(working_copy, working_root=tmp_path)


def test_multi_variant_duplication_offers_localization_per_variant(
        blocks_widget_with_localization, monkeypatch):
    from gui.duplicate_variants_dialog import DuplicateVariantsDialog
    from gui.localization_adjust_dialog import LocalizationAdjustDialog
    from PyQt6.QtWidgets import QDialog, QMessageBox

    widget = blocks_widget_with_localization
    block = _select_block_by_name(widget, "IronResource")

    def fake_exec(self):
        self.result_multi = {
            'num_variants': 2, 'varying_fields': [], 'total_percent': 0.0,
            'first_is_original': True,
        }
        self.result_field_overrides = {}
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(DuplicateVariantsDialog, "exec", fake_exec)
    monkeypatch.setattr(QMessageBox, "exec", _msgbox_no)

    captured_names = []

    def fake_loc_exec(self):
        captured_names.extend(self._new_names)
        self.table.item(0, 1).setText("Ressource de Fer T1")
        self.table.item(1, 1).setText("Ressource de Fer T2")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(LocalizationAdjustDialog, "exec", fake_loc_exec)

    widget._duplicate_block_action(block)

    assert captured_names == ["IronResourceT1", "IronResourceT2"]
    from core.localization_lookup import build_localization_index
    loc = build_localization_index(widget.working_root)
    assert loc.get("IronResourceT1", "fr") == "Ressource de Fer T1"
    assert loc.get("IronResourceT2", "fr") == "Ressource de Fer T2"


def test_localization_dialog_prefilled_from_source_translation(
        blocks_widget_with_localization, monkeypatch):
    from gui.duplicate_variants_dialog import DuplicateVariantsDialog
    from gui.localization_adjust_dialog import LocalizationAdjustDialog
    from PyQt6.QtWidgets import QDialog, QMessageBox

    widget = blocks_widget_with_localization
    block = _select_block_by_name(widget, "IronResource")

    def fake_exec(self):
        self.result_new_id = None
        self.result_new_name = "IronResourceCopy"
        self.result_remove_id = True
        self.result_multi = None
        self.result_field_overrides = {}
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(DuplicateVariantsDialog, "exec", fake_exec)
    monkeypatch.setattr(QMessageBox, "exec", _msgbox_no)

    prefilled = []

    def fake_loc_exec(self):
        prefilled.append(self.table.item(0, 1).text())
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(LocalizationAdjustDialog, "exec", fake_loc_exec)

    widget._duplicate_block_action(block)

    assert prefilled == ["Ressource de Fer"]  # traduction du bloc source


def test_localization_dialog_cancel_writes_nothing(blocks_widget_with_localization, monkeypatch):
    from gui.duplicate_variants_dialog import DuplicateVariantsDialog
    from gui.localization_adjust_dialog import LocalizationAdjustDialog
    from PyQt6.QtWidgets import QDialog, QMessageBox

    widget = blocks_widget_with_localization
    block = _select_block_by_name(widget, "IronResource")

    def fake_exec(self):
        self.result_new_id = None
        self.result_new_name = "IronResourceCopy2"
        self.result_remove_id = True
        self.result_multi = None
        self.result_field_overrides = {}
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(DuplicateVariantsDialog, "exec", fake_exec)
    monkeypatch.setattr(QMessageBox, "exec", _msgbox_no)
    monkeypatch.setattr(LocalizationAdjustDialog, "exec", lambda self: QDialog.DialogCode.Rejected)

    widget._duplicate_block_action(block)

    from core.localization_lookup import build_localization_index
    loc = build_localization_index(widget.working_root)
    assert loc.get("IronResourceCopy2", "fr") is None


def test_no_localization_dialog_without_working_root(blocks_widget, monkeypatch):
    """Sans working_root (contexte de scenario absent), la proposition est
    silencieusement sautee -- ne doit jamais planter."""
    from gui.duplicate_variants_dialog import DuplicateVariantsDialog
    from PyQt6.QtWidgets import QDialog, QMessageBox

    block = _select_block_by_name(blocks_widget, "IronResource")
    assert blocks_widget.working_root is None

    def fake_exec(self):
        self.result_new_id = None
        self.result_new_name = "IronResourceCopy3"
        self.result_remove_id = True
        self.result_multi = None
        self.result_field_overrides = {}
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(DuplicateVariantsDialog, "exec", fake_exec)
    monkeypatch.setattr(QMessageBox, "exec", _msgbox_no)

    blocks_widget._duplicate_block_action(block)  # ne doit pas lever

    names = [b.get_property("Name") for b in blocks_widget.doc.iter_blocks()]
    assert "IronResourceCopy3" in names


# ---------------------------------------------------------------------
# Noms de variantes personnalisables (demande explicite de l'utilisateur,
# session du 29/08/2026)
# ---------------------------------------------------------------------

def test_variant_names_list_prefilled_with_default_pattern(qapp):
    from gui.duplicate_variants_dialog import DuplicateVariantsDialog
    dialog = DuplicateVariantsDialog("1", "IronResource", [], [])
    dialog.count_spin.setValue(3)
    names = [dialog.variant_names_list.item(i).text() for i in range(dialog.variant_names_list.count())]
    assert names == ["IronResourceT1", "IronResourceT2", "IronResourceT3"]


def test_variant_names_editable_items(qapp):
    from gui.duplicate_variants_dialog import DuplicateVariantsDialog
    from PyQt6.QtCore import Qt
    dialog = DuplicateVariantsDialog("1", "IronResource", [], [])
    assert dialog.variant_names_list.item(0).flags() & Qt.ItemFlag.ItemIsEditable


def test_increasing_count_preserves_manually_edited_names(qapp):
    from gui.duplicate_variants_dialog import DuplicateVariantsDialog
    dialog = DuplicateVariantsDialog("1", "IronResource", [], [])
    dialog.count_spin.setValue(2)
    dialog.variant_names_list.item(0).setText("CustomFirst")
    dialog.count_spin.setValue(4)
    names = [dialog.variant_names_list.item(i).text() for i in range(dialog.variant_names_list.count())]
    assert names[0] == "CustomFirst"  # preserve
    assert names[2] == "IronResourceT3"  # nouvelle ligne, valeur par defaut
    assert names[3] == "IronResourceT4"


def test_duplicate_multi_variant_uses_custom_names(blocks_widget, monkeypatch):
    from gui.duplicate_variants_dialog import DuplicateVariantsDialog
    from PyQt6.QtWidgets import QDialog, QMessageBox

    block = _select_block_by_name(blocks_widget, "IronResource")

    def fake_exec(self):
        self.result_multi = {
            'num_variants': 2, 'varying_fields': [], 'total_percent': 0.0,
            'first_is_original': True, 'variant_names': ['FerLeger', 'FerLourd'],
        }
        self.result_field_overrides = {}
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(DuplicateVariantsDialog, "exec", fake_exec)
    monkeypatch.setattr(QMessageBox, "exec", _msgbox_no)

    blocks_widget._duplicate_block_action(block)

    names = [b.get_property("Name") for b in blocks_widget.doc.iter_blocks()]
    assert "FerLeger" in names
    assert "FerLourd" in names
    assert "IronResourceT1" not in names  # le pattern automatique n'a pas ete utilise


def test_duplicate_multi_variant_without_custom_names_still_uses_default_pattern(blocks_widget, monkeypatch):
    """Non-regression : sans 'variant_names' dans result_multi (ancien
    comportement/appelant), le pattern T1..TN automatique continue de
    fonctionner."""
    from gui.duplicate_variants_dialog import DuplicateVariantsDialog
    from PyQt6.QtWidgets import QDialog, QMessageBox

    block = _select_block_by_name(blocks_widget, "IronResource")

    def fake_exec(self):
        self.result_multi = {
            'num_variants': 2, 'varying_fields': [], 'total_percent': 0.0,
            'first_is_original': True,
        }
        self.result_field_overrides = {}
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(DuplicateVariantsDialog, "exec", fake_exec)
    monkeypatch.setattr(QMessageBox, "exec", _msgbox_no)

    blocks_widget._duplicate_block_action(block)

    names = [b.get_property("Name") for b in blocks_widget.doc.iter_blocks()]
    assert "IronResourceT1" in names
    assert "IronResourceT2" in names


def test_empty_variant_name_blocks_accept(qapp, monkeypatch):
    from gui.duplicate_variants_dialog import DuplicateVariantsDialog
    from PyQt6.QtWidgets import QMessageBox

    dialog = DuplicateVariantsDialog("1", "IronResource", [], [])
    dialog.multi_checkbox.setChecked(True)
    dialog.count_spin.setValue(2)
    dialog.variant_names_list.item(0).setText("")

    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warned.append(1))

    dialog._on_accept()

    assert warned == [1]
    assert dialog.result_multi is None


def test_duplicate_variant_name_blocks_accept(qapp, monkeypatch):
    from gui.duplicate_variants_dialog import DuplicateVariantsDialog
    from PyQt6.QtWidgets import QMessageBox

    dialog = DuplicateVariantsDialog("1", "IronResource", [], [])
    dialog.multi_checkbox.setChecked(True)
    dialog.count_spin.setValue(2)
    dialog.variant_names_list.item(0).setText("Meme")
    dialog.variant_names_list.item(1).setText("Meme")

    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warned.append(1))

    dialog._on_accept()

    assert warned == [1]
    assert dialog.result_multi is None


def test_multi_variant_templates_edited_individually_end_to_end(blocks_widget_with_templates, monkeypatch):
    """Test d'integration complet : deux variantes creees, une seule
    ajustee individuellement (CraftTime + ajout d'un ingredient), l'autre
    doit rester identique au Template source -- coeur de la demande
    explicite de l'utilisateur (session du 29/08/2026)."""
    from gui.duplicate_variants_dialog import DuplicateVariantsDialog
    from gui.template_adjust_dialog import TemplateAdjustDialog
    from gui.localization_adjust_dialog import LocalizationAdjustDialog
    from PyQt6.QtWidgets import QDialog, QMessageBox

    widget = blocks_widget_with_templates
    block = _select_block_by_name(widget, "IronResource")

    def fake_exec(self):
        self.result_multi = {
            'num_variants': 2, 'varying_fields': [], 'total_percent': 0.0,
            'first_is_original': True, 'variant_names': ['IronLight', 'IronHeavy'],
        }
        self.result_field_overrides = {}
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(DuplicateVariantsDialog, "exec", fake_exec)
    monkeypatch.setattr(QMessageBox, "exec", _msgbox_yes)
    monkeypatch.setattr(LocalizationAdjustDialog, "exec", lambda self: QDialog.DialogCode.Rejected)

    def fake_adjust_exec(self):
        editor_light = self._editors["IronLight"]
        editor_light.scalar_table.cellWidget(0, 1).setCurrentText("99")
        editor_light.ingredient_combo.setCurrentText("CobaltAlloy")
        editor_light.quantity_combo.setCurrentText("3")
        editor_light._on_add_ingredient()
        # IronHeavy reste volontairement inchange dans ce test.
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(TemplateAdjustDialog, "exec", fake_adjust_exec)

    widget._duplicate_block_action(block)

    from core.ecf.variants import list_template_scalar_fields, list_template_ingredients
    templates_widget = widget._opened_tabs[str(widget.sibling_ecf_files[1])]
    light_tpl = next(b for b in templates_widget.doc.iter_blocks() if b.get_property('Name') == 'IronLight')
    heavy_tpl = next(b for b in templates_widget.doc.iter_blocks() if b.get_property('Name') == 'IronHeavy')
    source_tpl = next(b for b in templates_widget.doc.iter_blocks() if b.get_property('Name') == 'IronResource')

    assert dict(list_template_scalar_fields(light_tpl))["CraftTime"] == "99"
    assert dict(list_template_ingredients(light_tpl))["CobaltAlloy"] == "3"

    # IronHeavy identique au Template source (aucun ajustement fait dessus).
    assert list_template_scalar_fields(heavy_tpl) == list_template_scalar_fields(source_tpl)
    assert list_template_ingredients(heavy_tpl) == list_template_ingredients(source_tpl)

    # Le Template SOURCE ne doit jamais etre modifie.
    assert dict(list_template_scalar_fields(source_tpl))["CraftTime"] == "3"


def _msgbox_yes(box):
    """Simule un clic OUI sur une boite a boutons APPLICATION
    (gui.msgboxes.ask_yes_no : boutons[0] = Oui, boutons[1] = Non)."""
    box.buttons()[0].click()
    return 0


def _msgbox_no(box):
    """Simule un clic NON sur une boite a boutons APPLICATION."""
    box.buttons()[1].click()
    return 0
