"""Tests presets & variantes economie (core/economy/presets.py) + branchement
dans le dialogue (inflation/penurie/variante/profils types)."""
import json

import pytest

from core.ecf.parser import parse_ecf_text
from core.economy.trader_config import TraderConfigDoc

SAMPLE = (
    "{ Trader Name: Bertrams\n"
    "  SellingGoods: \"trwSpecial\"\n"
    "  Discount: 0.08\n"
    "  Item1: \"CannedVegetables, 100-150, 3-5, 85-150, 55-150\"\n"
    "  Item2: \"HoverbikeHowler, mf=1.1-1.2, 10-50\"\n"
    "}\n"
    "\n"
    "{ Trader Name: Medic\n"
    "  SellingGoods: \"trwMedicine\"\n"
    "  Item1: \"MedPack, 50-60, 10\"\n"
    "}\n"
)


def _doc():
    return TraderConfigDoc(parse_ecf_text(SAMPLE))


# ------------------------------------------------------------------- core

def test_scale_prices_multiplies_both_sides():
    cfg = _doc()
    n = __import__("core.economy.presets", fromlist=["scale_profile_prices"]) \
        .scale_profile_prices(cfg, "Bertrams", 1.5)
    assert n == 2
    out = cfg.doc.render()
    assert '"CannedVegetables, 150-225, 3-5, 128-225, 55-150"' in out  # 127.5 -> 128
    assert '"HoverbikeHowler, mf=1.65-1.8, 10-50"' in out       # facteur aussi, stock intact


def test_scale_stocks_divides():
    from core.economy.presets import scale_profile_stocks
    cfg = _doc()
    assert scale_profile_stocks(cfg, "Bertrams", 2) == 2
    out = cfg.doc.render()
    assert "2-3" in out              # 3-5 / 2 -> arrondi superieur (1.5->2, 2.5->3)
    assert "5-25" in out             # 10-50 / 2
    assert "100-150" in out          # prix intact


def test_scale_unknown_trader_is_noop():
    from core.economy.presets import scale_profile_prices
    cfg = _doc()
    assert scale_profile_prices(cfg, "Inconnu", 2.0) == 0
    assert cfg.doc.render() == SAMPLE


def test_replace_profile_items_renumbers_and_sets_card():
    from core.economy.model import RangeSpec, TradeItem
    from core.economy.presets import replace_profile_items
    cfg = _doc()
    items = [TradeItem(name="MedPack", sell_price=RangeSpec.parse("50-60"),
                       sell_stock=RangeSpec.parse("10")),
             TradeItem(name="O2Bottle", sell_price=RangeSpec.parse("mf=1-1.2"),
                       sell_stock=RangeSpec.parse("5-10"))]
    assert replace_profile_items(cfg, "Bertrams", items, goods="trwMedicine", discount="0.1")
    out = cfg.doc.render()
    assert "CannedVegetables" not in out
    assert 'Item1: "MedPack, 50-60, 10"' in out
    assert 'Item2: "O2Bottle, mf=1-1.2, 5-10"' in out
    assert 'SellingGoods: "trwMedicine"' in out
    assert "Discount: 0.1" in out
    re_parsed = TraderConfigDoc(parse_ecf_text(out))
    assert len(re_parsed.find("Bertrams").children) >= 2 + 2


def test_snapshot_and_apply_roundtrip():
    from core.economy.presets import apply_snapshot, snapshot_profile
    cfg = _doc()
    view = next(v for v in cfg.views() if v.name == "Bertrams")
    snap = snapshot_profile(view)
    assert snap["name"] == "Bertrams"
    assert snap["items"][0].startswith('"CannedVegetables')
    assert apply_snapshot(cfg, "Medic", snap)
    out = cfg.doc.render()
    assert '"MedPack' not in out
    assert 'Item1: "CannedVegetables, 100-150, 3-5, 85-150, 55-150"' in out
    assert 'SellingGoods: "trwSpecial"' in out
    assert "Discount: 0.08" in out


def test_create_scaled_variant(tmp_path=None):
    from core.economy.presets import create_scaled_variant
    cfg = _doc()
    name = create_scaled_variant(cfg, "Bertrams", 1.5)
    assert name == "Bertrams @+50%"
    out = cfg.doc.render()
    assert 'Trader Name: "Bertrams @+50%"' in out
    assert '"CannedVegetables, 150-225, 3-5, 128-225, 55-150"' in out
    # le profil source est intact
    assert '"CannedVegetables, 100-150, 3-5, 85-150, 55-150"' in out
    # doublon -> suffixe -2
    name2 = create_scaled_variant(cfg, "Bertrams", 1.5)
    assert name2 == "Bertrams @+50%-2"
    assert create_scaled_variant(cfg, "Inconnu", 1.5) is None
    assert create_scaled_variant(cfg, "Bertrams", 1.0) is None


def test_builtin_type_profiles_apply():
    from core.economy.presets import BUILTIN_TYPE_PROFILES, replace_profile_items
    cfg = _doc()
    p = BUILTIN_TYPE_PROFILES["military"]
    assert replace_profile_items(cfg, "Medic", p.items,
                                 goods=p.selling_goods, discount=p.discount)
    out = cfg.doc.render()
    assert 'Item1: "PulseRifle' in out
    assert 'SellingGoods: "trwWeapons"' in out
    assert TraderConfigDoc(parse_ecf_text(out)).names() == ["Bertrams", "Medic"]


# --------------------------------------------------------------- stockage

def test_user_preset_storage(tmp_path, monkeypatch):
    from core.economy import presets
    monkeypatch.setattr(presets, "CONFIG_DIR", tmp_path)
    presets.save_user_preset("Zone Est / Agricole", {"items": ['"A, 1-2"'], "name": "x"})
    stored = presets.list_user_presets()
    assert len(stored) == 1
    assert stored[0]["items"] == ['"A, 1-2"']
    assert presets.delete_user_preset("Zone Est / Agricole") is True
    assert presets.list_user_presets() == []
    assert presets.delete_user_preset("inexistant") is False


# ------------------------------------------------------------------- GUI

def test_dialog_variant_and_preset_buttons(qapp, monkeypatch, tmp_path):
    from gui.economy_editor_dialog import EconomyEditorDialog
    from core.economy import presets
    from PyQt6.QtWidgets import QInputDialog

    monkeypatch.setattr(presets, "CONFIG_DIR", tmp_path)
    dlg = EconomyEditorDialog(_doc(), {})
    dlg.show()

    QInputDialog.getDouble = staticmethod(lambda *a, **k: (1.5, True))
    dlg._select_trader_by_name("Bertrams")
    dlg._create_variant()
    assert "Bertrams @+50%" in dlg.config.names()
    assert dlg._current is not None and dlg._current.name == "Bertrams @+50%"

    QInputDialog.getDouble = staticmethod(lambda *a, **k: (10.0, True))
    dlg.preset_only_selected.setChecked(True)
    dlg._apply_inflation()
    out = dlg.config.doc.render()
    assert '"CannedVegetables, 165-248, 3-5, 141-248, 55-150"' in out  # +50 puis +10, entiers
    assert '"MedPack, 50-60, 10"' in out                                      # Medic touche

    QInputDialog.getDouble = staticmethod(lambda *a, **k: (2.0, True))
    dlg._apply_scarcity()
    assert "2-3" in dlg.config.doc.render()          # 3-5 / 2, arrondi superieur

    # profils types embarques -> remplace le catalogue du marchand courant
    dlg.type_profile_combo.setCurrentIndex(0)  # militaire
    dlg._apply_type_profile()
    assert 'Item1: "PulseRifle' in dlg.config.doc.render()

    # sauvegarde du marchand courant comme profil type utilisateur
    QInputDialog.getText = staticmethod(lambda *a, **k: ("MonProfil", True))
    dlg._save_type_profile()
    assert any(s["name"] == "MonProfil" for s in presets.list_user_presets())
    assert dlg.type_profile_combo.count() == 3

    # supprimer le profil utilisateur : le reselectionner d'abord (le rebuild
    # de la combo remet l'index 0 = builtin militaire)
    dlg.type_profile_combo.setCurrentIndex(2)
    assert dlg.type_profile_combo.currentData() == "user:MonProfil"
    dlg._delete_type_profile()
    assert presets.list_user_presets() == []
    dlg.close()


def test_status_message_stays_short_for_many_targets(qapp):
    """Regression : sur un fichier vanilla (65 marchands), le message
    'Preset applique a : <tous les noms>' tirait la fenetre hors ecran."""
    from gui.economy_editor_dialog import EconomyEditorDialog
    from PyQt6.QtWidgets import QInputDialog
    dlg = EconomyEditorDialog(_doc(), {})
    for i in range(40):
        dlg.config.create_trader(f"T{i:02d}")
    dlg._refresh_traders()
    QInputDialog.getDouble = staticmethod(lambda *a, **k: (10.0, True))
    dlg._apply_inflation()
    assert "42" in dlg.status.text()                       # 2 du fixture + 40 crees
    assert "T00" not in dlg.status.text()                  # aucun nom liste
    assert len(dlg.status.text()) < 120
    assert dlg.status.wordWrap() is True
    dlg.close()
