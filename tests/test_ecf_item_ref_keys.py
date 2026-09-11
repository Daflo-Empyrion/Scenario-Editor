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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  Aucune garantie.
#
# Tests du retrofit catalogue (10/09/2026) : cles qui referencent un item
# (regles fichier+cle issues de tools/inventaire_cles_items.py, decision
# utilisateur "ok pour tout"), application du remplacement selon le mode
# et chemin d'ecriture reel (item.setText -> _on_cell_changed).

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTableWidgetItem

from core.ecf.model import EcfBlock, EcfProperty
from gui.ecf_edit_widget import EcfEditWidget, item_ref_target, apply_item_ref


# ------------------------------------------------------------------ regles

@pytest.mark.parametrize("filename,key,mode", [
    ("TraderNPCConfig.ecf", "Item1", "first_field"),
    ("TraderNPCConfig.ecf", "Item30", "first_field"),
    ("Containers.ecf", "Name_0", "value"),
    ("Containers.ecf", "Name_12", "value"),
    ("LootGroups.ecf", "Item_0", "value"),
    ("LootGroups.ecf", "Item_7", "value"),
    ("EClassConfig.ecf", "ItemsOnEnterGame", "value"),
    ("EClassConfig.ecf", "HandItem", "value"),
    ("EClassConfig.ecf", "ItemOnPickup", "value"),
    ("EClassConfig.ecf", "DropInventoryItem", "value"),
    ("TokenConfig.ecf", "CustomIcon", "value"),
    ("ItemsConfig.ecf", "AmmoType", "value"),
    ("ItemsConfig.ecf", "TechTreeParent", "value"),
    ("ItemsConfig.ecf", "FoodDecayedItem", "value"),
    ("ItemsConfig.ecf", "CustomIcon", "value"),
    ("ItemsConfig.ecf", "Meshfile", "value"),
    ("BlockGroupsConfig.ecf", "Blocks", "append_csv"),
])
def test_item_ref_targets_validated_keys(filename, key, mode):
    assert item_ref_target(filename, key) == mode


@pytest.mark.parametrize("filename,key", [
    ("Factions.ecf", "ForceAttack"),        # factions : jamais des items
    ("TraderNPCConfig.ecf", "Money"),       # cle non-item du meme fichier
    ("TraderNPCConfig.ecf", "ItemRange"),   # Item suivi de lettres : non
    ("Containers.ecf", "Name"),             # sans suffixe numerique : non
    ("ItemsConfig.ecf", "Name"),            # definition, pas une reference
    ("GalaxyConfig.ecf", "Name"),           # bruit de l'inventaire
    ("Dialogues.ecf", "Execute"),           # cas a part (commandes) : non branche
])
def test_item_ref_targets_rejects_non_item_keys(filename, key):
    assert item_ref_target(filename, key) is None


# ------------------------------------------------------- remplacements

def test_apply_first_field_keeps_rest_byte_for_byte():
    old = "CannedVegetables, 100-150, 3-5, 85-150, 55-150"
    assert apply_item_ref(old, "AutoMinerCore", "first_field") == \
        "AutoMinerCore, 100-150, 3-5, 85-150, 55-150"


def test_apply_value_replaces_entirely():
    assert apply_item_ref("Fiber", "TitanOre", "value") == "TitanOre"


def test_apply_append_csv_quoted_list():
    old = '"WeaponSV01,WeaponSV02"'
    assert apply_item_ref(old, "WeaponSV03", "append_csv") == \
        '"WeaponSV01,WeaponSV02,WeaponSV03"'


def test_apply_append_csv_skips_duplicate():
    old = '"WeaponSV01,WeaponSV02"'
    assert apply_item_ref(old, "WeaponSV01", "append_csv") == old


def test_apply_append_csv_empty_value():
    assert apply_item_ref("", "WeaponSV01", "append_csv") == "WeaponSV01"


# ------------------------------------------------------- chemin reel GUI

LOOT_ECF = (
    "{ +LootGroup Name: G1\r\n"
    "  Item_0: WaterBottle, param1: 5\r\n"
    "  Item_1: Fiber, param1: 1\r\n"
    "}\r\n"
)


def test_replace_cell_from_catalog_writes_through_model(qapp, tmp_path,
                                                        monkeypatch):
    """Le remplacement catalogue passe par le chemin unique : item.setText ->
    itemChanged -> _on_cell_changed (snapshot undo + mark modifiee), jamais
    une ecriture dedoublonnee."""
    from gui.theme import apply_theme
    apply_theme(qapp)
    path = tmp_path / "LootGroups.ecf"
    path.write_text(LOOT_ECF, encoding="utf-8", newline="")
    widget = EcfEditWidget(path)

    block = next(n for n in widget.doc.nodes if isinstance(n, EcfBlock))
    prop = next(c for c in block.children if isinstance(c, EcfProperty))
    item = QTableWidgetItem(prop.get("Item_0"))
    item.setData(Qt.ItemDataRole.UserRole, (prop, "Item_0"))
    # setItem exige une ligne EXISTANTE (aucun refresh sans bloc selectionne)
    widget.props_table.setRowCount(1)
    widget.props_table.setItem(0, 1, item)  # setItem n'emette pas itemChanged

    monkeypatch.setattr(widget, "_pick_catalog_entry", lambda: "TitanOre")
    widget._replace_cell_from_catalog(item, "value")

    assert prop.get("Item_0") == "TitanOre"
    assert id(prop) in widget._edited_prop_nodes
    # le fichier physique n'est PAS touche : seul le modele est modifie
    assert "WaterBottle" in path.read_text(encoding="utf-8")


def test_replace_cell_from_catalog_first_field_trader(qapp, tmp_path,
                                                      monkeypatch):
    """Mode 'first_field' (stocks marchands) : seul le nom change, prix et
    stocks restent identiques octet pour octet."""
    from gui.theme import apply_theme
    apply_theme(qapp)
    trader_ecf = (
        "{ Trader\r\n"
        "  Item1: CannedVegetables, 100-150, 3-5\r\n"
        "}\r\n"
    )
    path = tmp_path / "TraderNPCConfig.ecf"
    path.write_text(trader_ecf, encoding="utf-8", newline="")
    widget = EcfEditWidget(path)

    block = next(n for n in widget.doc.nodes if isinstance(n, EcfBlock))
    prop = next(c for c in block.children if isinstance(c, EcfProperty))
    item = QTableWidgetItem(prop.get("Item1"))
    item.setData(Qt.ItemDataRole.UserRole, (prop, "Item1"))
    widget.props_table.setRowCount(1)
    widget.props_table.setItem(0, 1, item)

    monkeypatch.setattr(widget, "_pick_catalog_entry", lambda: "Rifle")
    widget._replace_cell_from_catalog(item, "first_field")

    # Le parser a deja separe la ligne en paires : la cellule ne porte que
    # le nom, les fragments anonymes (prix/stocks) restent INTACTS et le
    # rendu regenere la ligne CSV complete.
    assert prop.get("Item1") == "Rifle"
    assert prop.pairs[1:] == [(None, "100-150"), (None, "3-5")]
    # le rendu regenere le CSV complet (une annotation '# original ...'
    # peut etre ajoutee selon les reglages utilisateur)
    assert prop.render().startswith("  Item1: Rifle, 100-150, 3-5")
