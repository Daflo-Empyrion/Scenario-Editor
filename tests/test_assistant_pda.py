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

"""Surface PDA : champs autorises, remplissage du formulaire guide (B3) et
statut de generation. L'IA ne cree rien : le wizard reste la revue."""
from pathlib import Path

import pytest

from core.ai.assistant.changeset import Change, ChangeSet
from core.ai.assistant.surfaces import pda as surface
from core.csv_handler import parse_csv_text
from core.yamllite.parser import parse_yaml_file

PDA_YAML = Path(__file__).parent / "fixtures" / "pda_scenario" / "PDA.yaml"
PDA_CSV = Path(__file__).parent / "fixtures" / "pda_scenario" / "PDA.csv"


@pytest.fixture(autouse=True)
def _force_fr_labels(monkeypatch):
    import core.settings
    monkeypatch.setattr(core.settings, "get_language", lambda: "fr")


@pytest.fixture
def dialog(qapp):
    from gui.theme import apply_theme
    from gui.pda_mission_dialog import PdaMissionDialog
    apply_theme(qapp)
    doc = parse_yaml_file(PDA_YAML)
    csv_doc = parse_csv_text(PDA_CSV.read_text(encoding="utf-8"))
    return PdaMissionDialog(doc, csv_doc)


def _change(target, new="x"):
    return Change(kind="pda_field", target=target, new=new)


def test_validate_accepts_form_fields_only():
    assert surface.validate([_change("Tier1.TitleEN"),
                             _change("Category", "SoloMission")]) == []
    assert surface.validate([_change("Tier5.TitleEN")]) == [
        "pda_field_unknown"]
    assert surface.validate([_change("TitleEN")]) == ["pda_field_unknown"]
    assert surface.validate([Change(kind="ecf_set", target="x")]) == [
        "pda_kind_unsupported"]


def test_values_keeps_only_known_fields():
    values = surface.values([_change("Tier1.TitleEN", "Raid"),
                             _change("Tier9.TitleEN", "nope")])
    assert values == {"Tier1.TitleEN": "Raid"}


def test_truthy_and_as_int():
    assert surface.truthy("TRUE") is True and surface.truthy("oui") is True
    assert surface.truthy("non") is False
    assert surface.as_int(" 12 ") == 12
    assert surface.as_int("douze") is None


def test_apply_generated_fields_fills_widgets(dialog):
    applied = dialog._apply_generated_fields({
        "Category": "FactionMission",
        "Tier1.TitleEN": "Raid the depot",
        "Tier1.TitleFR": "Raid du depot",
        "Tier1.DescriptionEN": "Destroy the crates",
        "Tier1.DescriptionFR": "Detruis les caisses",
        "Tier1.Check": "BlockDestroyed",
        "Tier1.Names": "IronOre, CopperOre",
        "Tier1.Types": "Building",
        "Tier1.Amount": "9999999",
        "Tier2.TitleEN": "Second wave",
    })
    assert applied == 10
    tier = dialog.tier_widgets[0]
    assert tier.title_en_edit.text() == "Raid the depot"
    assert tier.title_fr_edit.text() == "Raid du depot"
    assert tier.check_combo.currentData() == "BlockDestroyed"
    names = [tier.names_editor.list_widget.item(i).text()
             for i in range(tier.names_editor.list_widget.count())]
    assert names == ["IronOre", "CopperOre"]
    assert tier.amount_spin.value() == tier.amount_spin.maximum()
    assert dialog.category_combo.currentText() == "FactionMission"
    assert len(dialog.tier_widgets) == 2
    assert dialog.tier_widgets[1].title_en_edit.text() == "Second wave"


def test_unknown_category_and_check_are_ignored(dialog):
    applied = dialog._apply_generated_fields({"Category": "Nope",
                                              "Tier1.Check": "Kill"})
    assert applied == 0
    assert dialog.category_combo.currentText() == "SoloMission"


def test_generated_answer_fills_and_reports(dialog):
    from core.ai.assistant import engine
    changeset = ChangeSet(changes=[_change("Tier1.TitleEN", "Raid")])
    dialog._on_ai_generated(engine.Answer(text="ok", changeset=changeset))
    assert dialog.tier_widgets[0].title_en_edit.text() == "Raid"
    assert "rempli" in dialog.ai_status.text()
    assert dialog._ai_worker is None


def test_invalid_changeset_reports_and_fills_nothing(dialog):
    from core.ai.assistant import engine
    answer = engine.Answer(text="ok", changeset=ChangeSet(
        changes=[_change("Tier9.TitleEN", "x")]),
        changeset_problems=["pda_field_unknown"])
    dialog._on_ai_generated(answer)
    assert "inconnu" in dialog.ai_status.text()
    assert dialog.tier_widgets[0].title_en_edit.text() == ""


def test_dialog_refuses_to_close_while_generating(dialog):
    dialog.setResult(5)
    dialog._ai_worker = object()
    dialog.reject()
    assert dialog.result() == 5
    dialog._ai_worker = None
    dialog.reject()
    assert dialog.result() == 0
