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

"""Réparation du glossaire : tri, vanille, propositions, application
avec sauvegarde, export, dialogue de revue. Aucun réseau (IA mockée)."""
import json

import pytest
from PyQt6 import sip
from PyQt6.QtCore import Qt

from core import glossary, glossary_repair as gr, settings, vanilla_memory
from core.ai import budget


@pytest.fixture(autouse=True)
def _iso(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(glossary, "GLOSSARY_FILE", tmp_path / "glossary.json")
    glossary.reset_cache()
    monkeypatch.setattr(gr, "PROPOSAL_FILE", tmp_path / "proposal.json")
    monkeypatch.setattr(gr, "_provider", lambda: {
        "preset": "openrouter", "base_url": "https://x.test", "key": "k"})
    monkeypatch.setattr(vanilla_memory, "vanilla_pairs",
                        lambda target="fr": {})
    settings.set_ai_paid_enabled(True)
    settings.set_ai_monthly_cap_usd(10.0)
    budget.reset()
    yield
    glossary.reset_cache()
    budget.reset()


def _write(entries):
    glossary.GLOSSARY_FILE.write_text(json.dumps(entries), encoding="utf-8")
    glossary.reset_cache()


def _entry(src, dst, target="fr", on=True):
    return {"src": src, "dst": dst, "target": target, "on": on}


def test_base_items_duplicates_target_and_official(monkeypatch):
    _write([
        _entry("Warp Drive", "moteur de distorsion"),
        _entry("Warp Drive", "moteur de distorsion"),
        _entry("Steel Block", "acier", target="FranГ§ais"),
        _entry("Carapace", "Carapace"),
    ])
    monkeypatch.setattr(vanilla_memory, "vanilla_pairs",
                        lambda target="fr": {"Steel Block": "Bloc acier"})
    items = gr._base_items(gr.MODEL)
    assert items[1]["action"] == "remove" and items[1]["reason"] == "duplicate"
    assert items[2]["target"] == "fr" and items[2]["action"] == "translate"
    assert items[2]["new"] == "Bloc acier"
    assert items[3]["reason"] == "src=dst"


def test_analyze_disables_phrases_and_translates_terms(monkeypatch):
    _write([_entry("Warp Drive", "moteur de distortion"),
            _entry("Hello world", "Bonjour le monde")])

    def fake_ai(rows, model):
        out = {}
        for row in rows:
            phrase = row["src"] == "Hello world"
            out[row["id"]] = {
                "kind": "phrase" if phrase else "term",
                "fr": row["dst"].replace("distortion", "distorsion"),
                "keep": True,
                "reason": "ordinary" if phrase else "technical"}
        return out, 0.0

    monkeypatch.setattr(gr, "_ask_ai", fake_ai)
    result = gr.analyze()
    assert result["stats"]["disable"] == 1
    assert result["stats"]["translate"] == 1
    actions = {i["src"]: i["action"] for i in result["items"]}
    assert actions["Hello world"] == "disable"
    assert actions["Warp Drive"] == "translate"
    cached = gr.load_proposal()
    assert cached and cached["complete"]


def test_analyze_local_disables_phrases_and_applies_fixes(tmp_path, monkeypatch):
    _write([_entry("Hello world", "Bonjour le monde"),
            _entry("Cook", "Cuisiner"),
            _entry("Mass", "Masse"),
            _entry("Nest", "Nid")])
    fixes = tmp_path / "fixes.json"
    fixes.write_text(json.dumps({
        "terms": {"Cook": "Cuisinier"},
        "skip_official": ["Nest"]}), encoding="utf-8")
    monkeypatch.setattr(gr, "FIXES_FILE", fixes)
    monkeypatch.setattr(vanilla_memory, "vanilla_pairs",
                        lambda target="fr": {"Nest": "Paisible"})
    res = gr.analyze_local()
    actions = {i["src"]: i["action"] for i in res["items"]}
    assert actions["Hello world"] == "disable"
    assert actions["Cook"] == "translate"
    assert "Nest" not in actions  # officiel ecarte, ancienne traduction gardee
    assert res["stats"]["disable"] == 1


def test_apply_updates_disables_removes_and_backs_up():
    _write([
        _entry("Warp Drive", "moteur de distortion"),
        _entry("Hello world", "Bonjour le monde"),
        _entry("Dup", "Doublon"),
        _entry("Dup", "Doublon"),
    ])
    items = [
        {"id": 0, "src": "Warp Drive", "target": "fr",
         "old": "moteur de distortion", "new": "moteur de distorsion",
         "action": "translate"},
        {"id": 1, "src": "Hello world", "target": "fr",
         "old": "Bonjour le monde", "new": "Bonjour le monde",
         "action": "disable"},
        {"id": 2, "src": "Dup", "target": "fr", "old": "Doublon",
         "new": "Doublon", "action": "remove"},
        {"id": 99, "src": "inconnu", "target": "fr", "old": "x",
         "new": "y", "action": "translate"},
    ]
    result = gr.apply(items)
    assert result["updated"] == 1 and result["disabled"] == 1
    assert result["removed"] == 1 and result["skipped"] == 1
    entries = glossary.entries()
    by_src = {}
    for entry in entries:
        by_src.setdefault(entry["src"], []).append(entry)
    assert by_src["Warp Drive"][0]["dst"] == "moteur de distorsion"
    assert by_src["Hello world"][0]["on"] is False
    assert len(by_src["Dup"]) == 1  # jamais les deux doublons supprimés


def test_export_csv(tmp_path):
    items = [{"action": "translate", "kind": "term", "src": "A",
              "old": "B", "new": "C", "reason": "wrong"}]
    path = tmp_path / "out.csv"
    assert gr.export_csv(items, path) == 1
    text = path.read_text(encoding="utf-8-sig")
    assert "translate" in text and "A" in text and "C" in text


def test_dialog_loads_and_applies_selection(qapp, tmp_path, monkeypatch):
    _write([_entry("Warp Drive", "moteur de distortion")])
    proposal = {
        "complete": True, "model": gr.MODEL, "cost": 0.01,
        "stats": {"translate": 1, "disable": 0, "remove": 0},
        "items": [{"id": 0, "src": "Warp Drive", "target": "fr",
                   "old": "moteur de distortion",
                   "new": "moteur de distorsion", "kind": "term",
                   "action": "translate", "reason": "wrong"}],
    }
    gr.PROPOSAL_FILE.write_text(json.dumps(proposal), encoding="utf-8")
    from gui.glossary_repair_dialog import GlossaryRepairDialog
    dialog = GlossaryRepairDialog()
    called = {}

    def fake_apply(items):
        called["items"] = items
        return {"updated": 1, "disabled": 0, "removed": 0, "skipped": 0,
                "backup": "x"}

    monkeypatch.setattr(gr, "apply", fake_apply)
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    try:
        assert dialog.table.rowCount() == 1
        dialog.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        dialog._apply()
        assert len(called["items"]) == 1
    finally:
        sip.delete(dialog)
