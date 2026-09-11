"""Tests du catalogue global (core/item_catalog.py) et de la fenetre
selectionneuse (gui/item_catalog_dialog.py), puis son branchement economie.
"""
from pathlib import Path

import pytest

from core.item_catalog import (SOURCE_BLOCK, SOURCE_ITEM, CatalogEntry,
                               build_catalog, price_index)


@pytest.fixture
def catalog_files(tmp_path):
    items = tmp_path / "ItemsConfig.ecf"
    items.write_text(
        "{ Item Name: MedPack\n"
        "  Category: Medical\n"
        "  CustomIcon: MedPackCustom\n"
        "  MarketPrice: 126, display: false\n"
        "}\n"
        "{ Item Name: CannedVegetables\n"
        "  Category: Food\n"
        "}\n"
        "{ Item Name: SansCat\n"
        "  MarketPrice: 50\n"
        "}\n", encoding="utf-8")
    blocks = tmp_path / "BlocksConfig.ecf"
    blocks.write_text(
        "{ Block Id: 1314, Name: Trader\n"
        "  Category: Devices\n"
        "  MarketPrice: 500\n"
        "}\n"
        "{ Block Id: 2000, Name: MedPack\n"
        "  Category: Devices\n"
        "}\n", encoding="utf-8")
    return [items, blocks]


# ------------------------------------------------------------------ core

def test_build_catalog_entries_and_sources(catalog_files):
    entries = build_catalog(catalog_files)
    keys = [e.key for e in entries]
    # MedPack existe dans les DEUX fichiers : deux entrees, pas de fusion
    assert keys.count("item:MedPack") == 1 and keys.count("block:MedPack") == 1
    med = next(e for e in entries if e.key == "item:MedPack")
    assert med.category == "Medical" and med.market_price == 126.0
    assert med.icon_key == "MedPackCustom"   # CustomIcon prioritaire (regle fiche)
    assert next(e for e in entries if e.name == "SansCat").icon_key == "SansCat"
    blk = next(e for e in entries if e.key == "block:Trader")
    assert blk.source == SOURCE_BLOCK and blk.market_price == 500.0
    # categorie absente -> chaine vide
    assert next(e for e in entries if e.name == "SansCat").category == ""
    # prix index pour les fonctions economie existantes
    idx = price_index(entries)
    assert idx["MedPack"] == 126.0 and idx["SansCat"] == 50.0


def test_build_catalog_missing_files_and_cache(catalog_files):
    assert build_catalog([Path("nullepart/ItemsConfig.ecf")]) == []
    a = build_catalog(catalog_files)
    assert build_catalog(catalog_files) is a     # cache (meme objet)


# ------------------------------------------------------------------ dialog

@pytest.fixture
def dialog(qapp, catalog_files):
    from gui.item_catalog_dialog import ItemCatalogDialog
    entries = build_catalog(catalog_files)
    dlg = ItemCatalogDialog(entries, display_name=lambda e: e.name.upper()
                            if e.source == SOURCE_ITEM else None)
    dlg.show()
    yield dlg
    dlg.close()


def _tree_leaves(dlg):
    out = []
    for i in range(dlg.cat_tree.topLevelItemCount()):
        root = dlg.cat_tree.topLevelItem(i)
        for j in range(root.childCount()):
            cat = root.child(j)
            for k in range(cat.childCount()):
                out.append((root.text(0), cat.text(0), cat.child(k)))
    return out


def _tree_leaves(dlg):
    out = []
    for i in range(dlg.cat_tree.topLevelItemCount()):
        root = dlg.cat_tree.topLevelItem(i)
        for j in range(root.childCount()):
            cat = root.child(j)
            for k in range(cat.childCount()):
                out.append((root.text(0), cat.text(0), cat.child(k)))
    return out


def _open_tab(dlg, idx):
    """Active un onglet liste comme l'utilisateur : construction LAZY depuis
    la regression 11/09/2026 (les onglets A-Z / Tout ne sont peuples qu'a
    leur premiere activation, pour une ouverture quasi instantanee)."""
    dlg.tabs.setCurrentIndex(idx)
    dlg._on_tab_changed(idx)


def test_dialog_three_tabs_populated(dialog):
    assert dialog.tabs.count() == 3
    groups = {g for g, _, _ in _tree_leaves(dialog)}
    assert any("ItemsConfig" in g for g in groups)
    assert any("BlocksConfig" in g for g in groups)
    categories = {c for _, c, _ in _tree_leaves(dialog)}
    assert "Medical" in categories and "Devices" in categories
    _open_tab(dialog, 1)
    _open_tab(dialog, 2)
    assert dialog.az_list.count() == 5
    assert dialog.all_list.count() == 5


def test_dialog_checkboxes_shared_across_tabs(dialog):
    med = next(leaf for _, _, leaf in _tree_leaves(dialog)
               if leaf.data(0, 0x0100) == "item:MedPack")
    med.setCheckState(0, __import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.CheckState.Checked)
    assert "item:MedPack" in dialog._checked
    # l'onglet A->Z suit (etat partage par cle)
    _open_tab(dialog, 1)
    az_state = None
    for i in range(dialog.az_list.count()):
        it = dialog.az_list.item(i)
        if it.data(0x0100) == "item:MedPack":
            az_state = it.checkState()
    assert az_state == __import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.CheckState.Checked
    assert "1" in dialog.btn_add.text()


def test_dialog_search_filters_all_tabs(dialog):
    dialog.search.setText("medpack")
    leaves = _tree_leaves(dialog)
    assert len(leaves) == 2                     # item + bloc MedPack
    _open_tab(dialog, 1)                        # construit avec le filtre actif
    assert dialog.az_list.count() == 2
    dialog.search.setText("")                   # onglet A-Z deja construit
    assert dialog.az_list.count() == 5


def test_dialog_hide_no_price_filter(dialog):
    _open_tab(dialog, 1)
    dialog.hide_no_price.setChecked(True)
    assert dialog.az_list.count() == 3          # MedPack x2 + SansCat ont un prix


def test_dialog_selection_and_quick_pick(dialog):
    picked = []
    dialog.ITEM_CHOSEN.connect(lambda e: picked.append(e))
    accepted = []
    dialog.SELECTION_ACCEPTED.connect(lambda l: accepted.append(l))
    med = next(leaf for _, _, leaf in _tree_leaves(dialog)
               if leaf.data(0, 0x0100) == "item:MedPack")
    med.setCheckState(0, __import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.CheckState.Checked)
    trader = next(leaf for _, _, leaf in _tree_leaves(dialog)
                  if leaf.data(0, 0x0100) == "block:Trader")
    trader.setCheckState(0, __import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.CheckState.Checked)
    dialog._accept_selection()
    assert len(accepted[0]) == 2                # les deux, ordre catalogue
    assert [e.name for e in accepted[0]] == ["MedPack", "Trader"]
    # double-clic = ajout rapide d'une seule entree
    _open_tab(dialog, 1)
    med_item = next(it for it in [dialog.az_list.item(i) for i in range(dialog.az_list.count())]
                    if it.data(0x0100) == "item:MedPack")
    dialog._on_list_double_clicked(med_item)
    assert [e.key for e in picked] == ["item:MedPack"]


# ------------------------------------------------- branchement economie

def test_economy_add_entries_uses_market_price_default(qapp):
    from core.ecf.parser import parse_ecf_text
    from core.economy.trader_config import TraderConfigDoc
    from gui.economy_editor_dialog import EconomyEditorDialog

    sample = ('{ Trader Name: T\n  Item1: "A, 10-20, 5"\n}\n')
    dlg = EconomyEditorDialog(TraderConfigDoc(parse_ecf_text(sample)),
                              {"MedPack": 126.0, "Mystere": None})
    dlg._select_trader_by_name("T")
    from core.item_catalog import CatalogEntry
    dlg._add_catalog_entries([CatalogEntry(name="MedPack", source="item",
                                           category="Medical", market_price=126.0,
                                           icon_key="MedPack"),
                              CatalogEntry(name="Mystere", source="item",
                                           category="", market_price=None,
                                           icon_key="Mystere")])
    out = dlg.config.doc.render()
    # prix = REPRISE DU MARKETPRICE en absolu ; sans prix -> repli mf=
    assert '"MedPack, 126, 10-50"' in out
    assert '"Mystere, mf=1.1-1.2, 10-50"' in out
    # ajout simple (recherche inline / drag&drop) : meme regle de prix
    dlg._add_catalog_item("MedPack")
    assert out.count("MedPack") == 1 and '"MedPack, 126, 10-50"' in dlg.config.doc.render()


def test_dialog_label_callback_called_once_per_entry(qapp, catalog_files):
    """Regression 11/09/2026 : le callback display_name etait appele PAR
    ENTREE x 3 VUES (plus de 13 000 appels sur un vrai scenario, chacun
    relisant l'index de localisation disque) -> gel de plusieurs secondes
    A CHAQUE ouverture du catalogue, meme a chaud. Le memo limite a une
    fois par entree et par reconstruction."""
    from gui.item_catalog_dialog import ItemCatalogDialog
    entries = build_catalog(catalog_files)
    calls = []

    def display(e):
        calls.append(e.key)
        return e.name

    dlg = ItemCatalogDialog(entries, display_name=display)
    assert len(calls) == len(entries)           # une fois par entree, pas x3
    calls.clear()
    dlg.search.setText("med")                   # refiltrage : memo retombe
    # le filtrage consulte display une fois par entree + une fois par ligne
    # rendue (devenu bon marché : l'index couteux est lu une seule fois par
    # ouverture via _catalog_display_name_factory)
    assert len(calls) < 2 * len(entries)
    dlg.close()


def test_icons_load_on_tree_and_list_views(qapp, catalog_files):
    """Regression : _apply_icon appelait setIcon(0, ic) (signature
    QTreeWidgetItem) sur les items de LISTE (setIcon(ic), 1 seul argument)
    -> TypeError dans le slot QTimer = crash silencieux, zero icone affichee."""
    from PyQt6.QtGui import QPixmap
    from gui.item_catalog_dialog import ItemCatalogDialog
    entries = build_catalog(catalog_files)
    pm = QPixmap(16, 16)
    pm.fill()
    dlg = ItemCatalogDialog(entries, icon_loader=lambda e: pm)
    dlg.show()
    for _ in range(30):
        qapp.processEvents()
    assert len(dlg._icon_cache) == len(entries)
    n_tree = n_tree_ok = 0
    for i in range(dlg.cat_tree.topLevelItemCount()):
        root = dlg.cat_tree.topLevelItem(i)
        for j in range(root.childCount()):
            cat = root.child(j)
            for k in range(cat.childCount()):
                leaf = cat.child(k)
                n_tree += 1
                if not leaf.icon(0).isNull():
                    n_tree_ok += 1
    assert n_tree_ok == n_tree == len(entries)
    _open_tab(dlg, 1)                           # construction LAZY de l'onglet
    for _ in range(10):
        qapp.processEvents()
    n_list_ok = sum(1 for i in range(dlg.az_list.count())
                    if not dlg.az_list.item(i).icon().isNull())
    assert n_list_ok == dlg.az_list.count()
    # les icones ne touchent pas aux cases a cocher
    assert len(dlg._checked) == 0
    dlg.close()


def test_working_copy_priority_over_vanilla(tmp_path):
    """Retour utilisateur 09/09/2026 : un item present dans la copie de travail
    ET dans la vanille ne doit apparaitre QU'UNE FOIS, avec les donnees de la
    copie de travail (categorie, prix, icone). Idem pour l'index des prix."""
    from core.economy.market_price import build_index
    work = tmp_path / "work"
    van = tmp_path / "van"
    (work / "c").mkdir(parents=True)
    (van / "c").mkdir(parents=True)
    (work / "c" / "ItemsConfig.ecf").write_text(
        "{ Item Name: MedPack\n  Category: Medical\n  MarketPrice: 126\n}\n"
        "{ Item Name: ScenarioSeul\n  MarketPrice: 10\n}\n", encoding="utf-8")
    (van / "c" / "ItemsConfig.ecf").write_text(
        "{ Item Name: MedPack\n  Category: Food\n  MarketPrice: 999\n}\n"
        "{ Item Name: VanillaSeul\n  MarketPrice: 20\n}\n", encoding="utf-8")
    paths = [work / "c" / "ItemsConfig.ecf", van / "c" / "ItemsConfig.ecf"]
    entries = build_catalog(paths)
    med = [e for e in entries if e.name == "MedPack"]
    assert len(med) == 1                              # pas de doublon scenario+vanille
    assert med[0].category == "Medical"               # donnees de la copie de travail
    assert med[0].market_price == 126.0
    names = {e.name for e in entries}
    assert names == {"MedPack", "ScenarioSeul", "VanillaSeul"}
    # index des prix : la copie de travail gagne (126, pas 999)
    assert build_index(paths)["MedPack"] == 126.0


def test_disk_cache_roundtrip_and_refresh(tmp_path, monkeypatch):
    """Cache disque du catalogue : premiere lecture = parse + ecriture ;
    deuxieme lecture (memes mtimes) = lecture du cache, MEME si le fichier
    source change sans changer de signature ; refresh=True ignore le cache."""
    from core import item_catalog as ic
    monkeypatch.setattr(ic, "CONFIG_DIR", tmp_path)
    src = tmp_path / "ItemsConfig.ecf"
    src.write_text("{ Item Name: MedPack\n  MarketPrice: 126\n}\n", encoding="utf-8")
    paths = [src]
    first = ic.load_catalog(paths)
    assert first[0].market_price == 126.0
    # modifie le CONTENU a mtime ET taille constants : la signature ne bouge
    # pas, le cache disque repond donc avec l'ANCIENNE valeur
    import os
    st = src.stat()
    os.utime(src, ns=(st.st_atime_ns, st.st_mtime_ns))
    src.write_text("{ Item Name: MedPack\n  MarketPrice: 999\n}\n", encoding="utf-8")
    os.utime(src, ns=(st.st_atime_ns, st.st_mtime_ns))
    cached = ic.load_catalog(paths)
    assert cached[0].market_price == 126.0
    # refresh=True force la relecture
    refreshed = ic.load_catalog(paths, refresh=True)
    assert refreshed[0].market_price == 999.0
    # et le cache disque est mis a jour
    assert ic.load_catalog(paths)[0].market_price == 999.0


def test_icon_index_disk_cache_roundtrip(tmp_path, monkeypatch):
    """Cache disque de l'index d'icones : le deuxieme appel (memes sources)
    lit le cache ; refresh=True relit les sources."""
    import json
    import zipfile
    from core import tech_tree_icons as tti
    pak = tmp_path / "tech_tree_icons.pak"
    with zipfile.ZipFile(pak, "w") as zf:
        zf.writestr("NOTICE.txt", "propriete Eleon")
        zf.writestr("MedPack.png", b"\x89PNG fake")
    monkeypatch.setattr(tti, "icon_pack_path", lambda: pak)
    monkeypatch.setattr(tti, "bundled_icon_directory", lambda: None)
    monkeypatch.setattr(tti, "icon_directory", lambda root: None)
    monkeypatch.setattr(tti, "_icon_cache_path", lambda: tmp_path / "cache" / "icon_index.json")
    root = tmp_path / "scenario"
    root.mkdir()
    idx = tti.build_icon_index_cached(root)
    assert "medpack" in idx
    # 2e appel : cache disque (objet reconstruit, contenu equivalent)
    idx2 = tti.build_icon_index_cached(root)
    assert set(idx2) == {"medpack"}
    assert idx2["medpack"].member == "MedPack.png"
    assert (tmp_path / "cache" / "icon_index.json").is_file()
