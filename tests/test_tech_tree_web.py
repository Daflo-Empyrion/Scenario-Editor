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

"""Tests du pont de la vue web de l'arbre technologique (31/10/2026).

HORS LIGNE volontairement : on teste le payload (shape + coherence avec
compute_layout), le pont JSON et les signaux -- JAMAIS TechTreeWebView
(QWebEngineView lance Chromium, hostile a l'offscreen ; la vue elle-meme
n'est pas testable ici). Voir gui/tech_tree_web.py.
"""
import json
import shutil
from pathlib import Path

import pytest

from core.scanner import scan_scenario
from core.workspace import Workspace

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "tech_tree_scenario"

pytest.importorskip("PyQt6.QtWebChannel")  # le pont en depend


@pytest.fixture
def tree_factory(tmp_path):
    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    shutil.copy(FIXTURE_DIR / "BlocksConfig.ecf", config_dir / "BlocksConfig.ecf")
    shutil.copy(FIXTURE_DIR / "ItemsConfig.ecf", config_dir / "ItemsConfig.ecf")
    from core.tech_tree import load_tech_tree
    return load_tech_tree(config_dir / "BlocksConfig.ecf", config_dir / "ItemsConfig.ecf")


# -- payload ---------------------------------------------------------------

def test_payload_shape_matches_layout(tree_factory):
    from gui.tech_tree_web import build_category_payload
    from core.tech_tree_layout import compute_layout
    tree = tree_factory
    for category in tree.categories():
        lay = compute_layout(tree, category)
        payload = build_category_payload(tree, category)
        assert payload["cat"] == category
        assert payload["levels"] == lay.levels
        assert len(payload["nodes"]) == len(lay.draw_order)
        for n in payload["nodes"]:
            p = lay.positions[n["name"]]
            assert n["col"] == int(p.x_fraction)
            assert n["row"] == p.row
            assert n["parent"] == (p.parent_name or "")
            node = tree.get(n["name"])
            assert n["lv"] == node.unlock_level and n["cost"] == node.unlock_cost


def test_payload_is_json_serializable(tree_factory):
    from gui.tech_tree_web import build_category_payload
    for category in tree_factory.categories():
        out = json.dumps(build_category_payload(tree_factory, category), ensure_ascii=False)
        assert json.loads(out)["cat"] == category


def test_payload_of_unknown_category_is_empty(tree_factory):
    from gui.tech_tree_web import build_category_payload
    payload = build_category_payload(tree_factory, "Categorie-Inexistante")
    assert payload["levels"] == [] and payload["nodes"] == []


# -- pont -------------------------------------------------------------------

def test_bridge_read_slots(tree_factory, qapp):
    from gui.tech_tree_web import TechTreeBridge, build_labels
    bridge = TechTreeBridge(tree_factory, build_labels())
    cats = json.loads(bridge.get_categories())
    assert cats == tree_factory.categories()
    labels = json.loads(bridge.get_labels())
    assert all(isinstance(v, str) and v for v in labels.values())
    payload = json.loads(bridge.get_category(cats[0]))
    assert payload["cat"] == cats[0]
    # categorie inconnue : payload vide, jamais d'exception
    assert json.loads(bridge.get_category("Nimport"))["nodes"] == []


def test_bridge_write_slots_emit_signals(tree_factory, qapp):
    from gui.tech_tree_web import TechTreeBridge, build_labels
    bridge = TechTreeBridge(tree_factory, build_labels())
    seen = []
    bridge.level_changed.connect(lambda n, v: seen.append(("lv", n, v)))
    bridge.cost_changed.connect(lambda n, v: seen.append(("cost", n, v)))
    bridge.parent_changed.connect(lambda n, v: seen.append(("parent", n, v)))
    bridge.category_changed.connect(lambda n, v: seen.append(("cat", n, v)))
    bridge.node_selected.connect(lambda n: seen.append(("sel", n)))
    bridge.node_activated.connect(lambda n: seen.append(("act", n)))
    bridge.category_displayed.connect(lambda n: seen.append(("disp", n)))
    bridge.set_unlock_level("X", 3)
    bridge.set_unlock_cost("X", 12)
    bridge.set_parent("X", "")
    bridge.set_category("X", "Weapons")
    bridge.select_node("X")
    bridge.activate_node("X")
    bridge.notify_category("Weapons")
    assert seen == [
        ("lv", "X", 3), ("cost", "X", 12), ("parent", "X", ""),
        ("cat", "X", "Weapons"), ("sel", "X"), ("act", "X"), ("disp", "Weapons"),
    ]


# -- bascule du dialogue ----------------------------------------------------

@pytest.fixture
def dialog_factory(tmp_path, monkeypatch):
    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    shutil.copy(FIXTURE_DIR / "BlocksConfig.ecf", config_dir / "BlocksConfig.ecf")
    shutil.copy(FIXTURE_DIR / "ItemsConfig.ecf", config_dir / "ItemsConfig.ecf")
    scenario = scan_scenario(tmp_path)
    ws = Workspace(source_a=scenario, source_a_root=tmp_path, working=scenario, working_root=tmp_path)

    def _make():
        from gui.tech_tree_dialog import TechTreeDialog
        return TechTreeDialog(ws)

    return config_dir, _make


def test_dialog_web_enabled_but_unavailable_keeps_qt_tabs(dialog_factory, monkeypatch):
    from core import settings
    from gui import tech_tree_web
    monkeypatch.setattr(settings, "get_tech_tree_web_enabled", lambda: True)
    monkeypatch.setattr(tech_tree_web, "is_available", lambda: False)
    config_dir, make_dialog = dialog_factory
    dlg = make_dialog()
    assert dlg._web_view is None
    from core.tech_tree import load_tech_tree
    tree = load_tech_tree(config_dir / "BlocksConfig.ecf", config_dir / "ItemsConfig.ecf")
    assert dlg.tabs.count() == len(tree.categories())


def test_dialog_default_setting_keeps_qt_tabs(dialog_factory, monkeypatch):
    from core import settings
    monkeypatch.setattr(settings, "get_tech_tree_web_enabled", lambda: False)
    _config_dir, make_dialog = dialog_factory
    dlg = make_dialog()
    assert dlg._web_view is None
    assert dlg.tabs is not None


# -- edition enrichie de la fiche integree (31/10) --------------------------

@pytest.fixture
def web_edit_factory(tmp_path, monkeypatch):
    """Scenario de test avec Templates.ecf et Extras/Localization.csv, et le
    dialogue en mode Qt (les handlers d'ecriture web sont independants de la
    vue). Ajoute une propriete Info sur FuelTankMSSmall."""
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    # info() du projet (boite modale reelle) : le flux de traduction l'appelle
    monkeypatch.setattr("gui.msgboxes.info", lambda *a, **k: None)
    # choix des langues cibles : AUCUNE par defaut dans les tests (pas d'UI)
    monkeypatch.setattr(
        "gui.tech_tree_dialog.TechTreeDialog._ask_translate_languages",
        lambda self, header, columns: [])

    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    blocks = (FIXTURE_DIR / "BlocksConfig.ecf").read_text(encoding="utf-8")
    blocks = blocks.replace(
        "{ Block Id: 261, Name: FuelTankMSSmall\n  Material: Device",
        "{ Block Id: 261, Name: FuelTankMSSmall\n  Material: Device\n"
        "  Info: desc_fuel_small, display: true")
    (config_dir / "BlocksConfig.ecf").write_text(blocks, encoding="utf-8")
    shutil.copy(FIXTURE_DIR / "ItemsConfig.ecf", config_dir / "ItemsConfig.ecf")
    (config_dir / "Templates.ecf").write_text(
        "{ Template Id: 501, Name: FuelTankMSSmall\n"
        "  CraftType: MS\n"
        "  OutputCount: 1\n"
        "  { Child Inputs\n"
        "    IronIngot: 5\n"
        "  }\n"
        "}\n", encoding="utf-8")
    extras = tmp_path / "Extras"
    extras.mkdir()
    (extras / "Localization.csv").write_text(
        "Key,English,French\r\n"
        "desc_fuel_small,Small fuel tank,Petit reservoir\r\n", encoding="utf-8")

    from core.scanner import scan_scenario
    from core.workspace import Workspace
    scenario = scan_scenario(tmp_path)
    ws = Workspace(source_a=scenario, source_a_root=tmp_path,
                   working=scenario, working_root=tmp_path)
    from gui.tech_tree_dialog import TechTreeDialog
    dlg = TechTreeDialog(ws)
    return tmp_path, dlg


def test_web_ingredient_qty_edit_writes_templates(web_edit_factory):
    tmp_path, dlg = web_edit_factory
    tpl = tmp_path / "Content" / "Configuration" / "Templates.ecf"
    dlg._on_web_card_ingredient("FuelTankMSSmall", "IronIngot", "qty", "5", "5", "9")
    assert "IronIngot: 9" in tpl.read_text(encoding="utf-8")


def test_web_ingredient_name_edit_swaps_item(web_edit_factory):
    tmp_path, dlg = web_edit_factory
    tpl = tmp_path / "Content" / "Configuration" / "Templates.ecf"
    dlg._on_web_card_ingredient("FuelTankMSSmall", "IronIngot", "name", "5",
                                "IronIngot", "CobaltIngot")
    text = tpl.read_text(encoding="utf-8")
    assert "CobaltIngot: 5" in text
    assert "IronIngot" not in text


def test_web_description_edit_writes_localization(web_edit_factory):
    tmp_path, dlg = web_edit_factory
    loc = tmp_path / "Extras" / "Localization.csv"
    dlg._on_web_card_description("FuelTankMSSmall", "Petit reservoir", "Reservoir compact")
    text = loc.read_text(encoding="utf-8")
    assert "Reservoir compact" in text
    assert "Small fuel tank" in text          # l'anglais n'est pas touche
    # la description refusee par la garde ne casse rien (rien a verifier de plus)


def test_web_description_without_info_is_graceful(web_edit_factory, monkeypatch):
    _tmp_path, dlg = web_edit_factory
    msgs = []
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "information",
                        lambda *a, **k: msgs.append(k[1] if len(k) > 1 else a[1]))
    dlg._on_web_card_description("TurretMSPlasma", "x", "y")   # bloc sans Info
    assert msgs                                                # un message, pas d'exception


def test_translate_pick_dialog_selection(qapp):
    """La boîte de choix des langues : une case par colonne, cochée par
    défaut, l'édité exclue, et la sélection respecte les décochages."""
    from gui.tech_tree_dialog import _WebTranslatePickDialog
    header = ["Key", "English", "French", "German"]
    dlg = _WebTranslatePickDialog(header, [1, 2, 3])
    assert dlg.selected_columns() == [1, 2, 3]      # toutes cochees par defaut
    boxes = dlg.findChildren(__import__("PyQt6.QtWidgets", fromlist=["QCheckBox"]).QCheckBox)
    boxes[1].setChecked(False)                      # decoche French
    assert dlg.selected_columns() == [1, 3]


def test_description_translation_targets_selected_languages(web_edit_factory, monkeypatch):
    """Edition FR -> la traduction n'ecrit QUE les colonnes cochees."""
    tmp_path, dlg = web_edit_factory
    asked = {}
    def fake_ask(header, columns):
        asked["columns"] = list(columns)
        return [1]                                   # anglais uniquement
    monkeypatch.setattr(
        "gui.tech_tree_dialog.TechTreeDialog._ask_translate_languages",
        lambda self, header, columns: fake_ask(header, columns))
    import core.translation as tr
    monkeypatch.setattr(tr, "translate_text",
                        lambda text, target, source="auto", store_in_memory=True:
                        f"[{target}] {text}")
    dlg._on_web_card_description("FuelTankMSSmall", "Petit reservoir", "Reservoir compact")
    text = (tmp_path / "Extras" / "Localization.csv").read_text(encoding="utf-8")
    assert "Reservoir compact" in text
    assert asked["columns"] == [1]                   # propose EN seulement : l'edite (FR) est exclue
    assert "[en] Reservoir compact" in text          # cible cochee traduite
    assert "[de]" not in text                        # cible non cochee epargnee
