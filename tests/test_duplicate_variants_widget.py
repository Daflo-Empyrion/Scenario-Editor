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
