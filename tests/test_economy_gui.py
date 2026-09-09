"""Tests du dialogue editeur d'economie (gui/economy_editor_dialog.py).

Le dialogue est construit hors MainWindow (crochets on_before_mutate /
on_mutate = compteurs de test) : on verifie les mutations SEMANTIQUES et
leur reflet dans le document ECF partage, pas l'habillage.
"""
from pathlib import Path

import pytest

from core.ecf.parser import parse_ecf_text
from core.economy.trader_config import TraderConfigDoc

SAMPLE = (
    "{ Trader Name: TraderDefault\n"
    "  SellingText: \"Hi, I am trader <NAME>\\nI am selling <GOODS>.\"\n"
    "  SellingGoods: \"trwFood\"\n"
    "  Item1: \"CannedVegetables, 100-150, 3-5, 85-150, 55-150\"\n"
    "  Item2: \"CannedMeat, 222-333, 3-5, 178-222,55-150\"\n"
    "}\n"
    "\n"
    "{ Trader Name: Bertrams\n"
    "  SellingText: \"Welcome to Bertrams!\"\n"
    "  SellingGoods: \"trwSpecial\"\n"
    "  Discount: 0.08\n"
    "  Item1: \"HoverbikeHowler, mf=1.1-1.2, 10-50, mf=0.4-0.5, 55-150\"\n"
    "}\n"
)

MARKET = {"CannedVegetables": 126.0, "CannedMeat": 244.0, "HoverbikeHowler": 9000.0,
          "MedPack": 100.0}


@pytest.fixture
def dialog(qapp):
    from gui.economy_editor_dialog import EconomyEditorDialog
    doc = TraderConfigDoc(parse_ecf_text(SAMPLE))
    calls = {"before": 0, "after": 0}
    dlg = EconomyEditorDialog(
        doc, MARKET,
        on_before_mutate=lambda: calls.__setitem__("before", calls["before"] + 1),
        on_mutated=lambda: calls.__setitem__("after", calls["after"] + 1))
    dlg.calls = calls
    dlg.show()
    yield dlg
    dlg.close()


def _row_by_name(dlg, frag):
    # colonne 1 = nom (colonne 0 = icone)
    for r in range(dlg.table.rowCount()):
        it = dlg.table.item(r, 1)
        if it is None:
            continue
        if frag in (it.text() or ""):
            return r
    return -1


def test_dialog_lists_traders_and_selects(dialog):
    assert dialog.trader_list.count() == 2
    dialog._select_trader_by_name("Bertrams")
    assert dialog._current is not None and dialog._current.name == "Bertrams"
    assert dialog.table.rowCount() == 1
    assert "HoverbikeHowler" in dialog.table.item(0, 1).text()
    assert "Item1" in dialog.table.item(0, 1).text()
    # colonne prix en facteur, telle quelle (colonne 3, apres icone+nom)
    assert dialog.table.item(0, 3).text() == "mf=1.1-1.2"


def test_add_item_via_catalog_calls_hooks(dialog):
    dialog._select_trader_by_name("TraderDefault")
    before = dialog.config.doc.render()
    dialog._add_catalog_item("MedPack")
    out = dialog.config.doc.render()
    assert out != before
    assert '"MedPack, 100, 10-50"' in out                 # prix = MarketPrice (regle)
    assert dialog.calls["before"] == 1 and dialog.calls["after"] == 1
    assert dialog.table.rowCount() == 3                    # 2 + MedPack


def test_cell_edit_price_updates_doc(dialog):
    dialog._select_trader_by_name("TraderDefault")
    r = _row_by_name(dialog, "CannedVegetables")
    dialog.table.setCurrentCell(r, 3)
    dialog.table.item(r, 3).setText("200-250")             # declenche itemChanged
    out = dialog.config.doc.render()
    assert '"CannedVegetables, 200-250, 3-5, 85-150, 55-150"' in out
    assert dialog.calls["before"] == 1


def test_cell_edit_invalid_value_reverts(dialog):
    dialog._select_trader_by_name("TraderDefault")
    r = _row_by_name(dialog, "CannedVegetables")
    dialog.table.setCurrentCell(r, 3)
    dialog.table.item(r, 3).setText("prix-nul")
    assert dialog.calls["before"] == 0                     # rien ecrit
    assert "200" not in dialog.config.doc.render()            # ligne d'origine intacte


def test_action_combo_adds_and_removes_buy(dialog):
    # CannedVegetables a DEJA sa partie achat dans le fixture : ajout teste sur
    # un item sans achat (MedPack), retrait sur CannedVegetables.
    dialog._select_trader_by_name("TraderDefault")
    from core.economy.model import TradeItem, RangeSpec
    dialog.config.add_item(dialog.config.find("TraderDefault"),
                           TradeItem(name="MedPack", sell_price=RangeSpec.parse("50-60"),
                                     sell_stock=RangeSpec.parse("10")))
    dialog._reload_current()
    dialog._refresh_table()
    r = _row_by_name(dialog, "MedPack")
    combo = dialog.table.cellWidget(r, 2)
    assert combo.currentIndex() == 0                        # vend seul
    combo.setCurrentIndex(1)                                # Vend + rachete
    assert '"MedPack, 50-60, 10, mf=0.4-0.5, 55-150"' in dialog.config.doc.render()
    r2 = _row_by_name(dialog, "CannedVegetables")
    combo2 = dialog.table.cellWidget(r2, 2)
    assert combo2.currentIndex() == 1
    combo2.setCurrentIndex(0)                               # retour Vend seul
    assert '"CannedVegetables, 100-150, 3-5"' in dialog.config.doc.render()


def test_convert_to_factor_and_back(dialog):
    dialog._select_trader_by_name("TraderDefault")
    r = _row_by_name(dialog, "CannedVegetables")
    dialog.table.setCurrentCell(r, 0)
    dialog._convert_selected(True)
    # 100/126=0.79, 150/126=1.19
    assert dialog.table.item(r, 3).text() == "mf=0.79-1.19"
    dialog.table.setCurrentCell(r, 0)                       # le rebuild remet currentRow a -1
    dialog._convert_selected(False)
    # REGLE MODULE : prix absolu = entiers (ceil) -> retour EXACT a 100-150
    assert dialog.table.item(r, 3).text() == "100-150"


def test_convert_without_market_price_is_blocked(dialog):
    dialog._select_trader_by_name("TraderDefault")
    r = _row_by_name(dialog, "CannedMeat")
    dialog.table.setCurrentCell(r, 0)
    dialog.market_index.pop("CannedMeat")
    dialog._convert_selected(True)
    assert dialog.table.item(r, 3).text() == "222-333"     # inchangé


def test_create_duplicate_delete_trader(dialog):
    from PyQt6.QtWidgets import QInputDialog
    QInputDialog.getText = staticmethod(
        lambda *a, **k: ("NouveauMarchand", True))         # pas d'interaction
    dialog._add_trader()
    assert "NouveauMarchand" in dialog.config.names()

    dialog._select_trader_by_name("Bertrams")
    QInputDialog.getText = staticmethod(
        lambda *a, **k: ("BertramsCopie", True))
    dialog._duplicate_trader()
    out = dialog.config.doc.render()
    assert "BertramsCopie" in dialog.config.names()
    assert 'Item1: "HoverbikeHowler, mf=1.1-1.2, 10-50, mf=0.4-0.5, 55-150"' in out

    dialog._select_trader_by_name("NouveauMarchand")
    from PyQt6.QtWidgets import QMessageBox
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    dialog._remove_trader()
    assert "NouveauMarchand" not in dialog.config.names()
    # le document reste re-parsable apres tous ces allers-retours
    from core.economy.trader_config import TraderConfigDoc
    assert TraderConfigDoc(parse_ecf_text(dialog.config.doc.render())).names() == \
        dialog.config.names()


def test_apply_card_text_and_discount(dialog):
    dialog._select_trader_by_name("Bertrams")
    dialog.card_text.setPlainText("Bonjour\nA plus")
    dialog.card_discount.setText("0.10")
    dialog._apply_card()
    out = dialog.config.doc.render()
    assert 'SellingText: "Bonjour\\nA plus"' in out
    assert "Discount: 0.10" in out
    # re-parsage : le texte deshape revient tel quel
    from core.economy.trader_config import TraderConfigDoc
    v = [x for x in TraderConfigDoc(parse_ecf_text(out)).views() if x.name == "Bertrams"][0]
    assert v.selling_text == "Bonjour\nA plus"
    assert v.discount == "0.10"


def test_dialog_undo_calls_target_and_refresh(dialog):
    dialog._dialog_undo()      # sans undo_target : ne doit rien casser
    assert dialog.trader_list.count() == 2


def test_byte_perfect_after_dialog_load_only():
    from gui.economy_editor_dialog import EconomyEditorDialog
    doc = TraderConfigDoc(parse_ecf_text(SAMPLE))
    dlg = EconomyEditorDialog(doc, MARKET)
    assert doc.doc.render() == SAMPLE                         # aucune ecriture parasite
    dlg.close()


# ---------------- Integration MainWindow (menu + fichier de depart) ----------

@pytest.fixture
def window_with_scenario(qapp, tmp_path):
    import shutil
    from core.scanner import scan_scenario
    from core.workspace import Workspace
    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    shutil.copy(Path(__file__).parent / "fixtures" / "sample.ecf",
                config_dir / "BlocksConfig.ecf")
    scenario = scan_scenario(tmp_path)
    ws = Workspace(source_a=scenario, source_a_root=tmp_path,
                   working=scenario, working_root=tmp_path)
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    apply_theme(qapp)
    win = MainWindow()
    win.workspace = ws
    yield win, ws, tmp_path
    win.close()


def test_menu_has_economy_action(window_with_scenario):
    win, _ws, _root = window_with_scenario
    assert win.action_economy_editor is not None
    assert win.action_economy_editor.text() != "menu.tools.economy"  # traduite


def test_starter_trader_config_created_and_undoable(window_with_scenario):
    win, ws, root = window_with_scenario
    path = win._create_starter_trader_config()
    assert path is not None and path.name == "TraderNPCConfig.ecf"
    assert path.is_file()
    assert b"{ Trader Name: TraderDefault" in path.read_bytes()
    # le scannaire la voit maintenant dans la configuration
    assert any(f.path.name == "TraderNPCConfig.ecf" for f in ws.working.configuration)
    # undo d'espace de travail -> le fichier disparait
    assert win.workspace_undo.can_undo()
    win.workspace_undo.undo()
    assert not path.exists()


def test_cell_edit_rejects_non_integer_absolute_values(dialog):
    """REGLE MODULE : prix/stocks absolus = entiers. Un decimal absolu est
    refuse (message + revert) ; un facteur mf= decimal reste accepte."""
    dialog._select_trader_by_name("TraderDefault")
    r = _row_by_name(dialog, "CannedVegetables")
    dialog.table.setCurrentCell(r, 4)                      # colonne stock VENTE
    dialog.table.item(r, 4).setText("4.5")
    assert "4.5" not in dialog.config.doc.render()         # refuse
    assert "3-5" in dialog.config.doc.render()             # valeur d'origine intacte
    dialog.table.setCurrentCell(r, 4)
    dialog.table.item(r, 4).setText("mf=0.9-1.0")          # facteur (colonne stock) : passe
    assert "mf=0.9-1.0" in dialog.config.doc.render()


def test_real_catalog_icon_loader_resolves_icons(qapp, tmp_path):
    """Regression 09/09/2026 : QPixmap non importe dans economy_editor_dialog
    -> NameError avale par except Exception -> 'Icones : 0/N' chez l'utilisateur.
    Le test passe par le VRAI loader du dialogue (pas une lambda de test) : les
    replis (pak distribue / itemicons dev) doivent resoudre au moins une icone."""
    from gui.economy_editor_dialog import EconomyEditorDialog
    from core.item_catalog import build_catalog
    cfg = Path(__file__).parent / "fixtures" / "block_creation_scenario"
    entries = build_catalog([cfg / "ItemsConfig.ecf", cfg / "BlocksConfig.ecf"])
    assert entries
    dlg = EconomyEditorDialog(_make_config(), {}, catalog_entries=entries,
                              working_root=tmp_path)
    resolved = [e.name for e in entries[:10]
                if dlg._catalog_icon_loader(e) is not None]
    assert resolved, "aucune icone resolue via le vrai loader du dialogue"
    dlg.close()


def _make_config():
    from core.ecf.parser import parse_ecf_text
    from core.economy.trader_config import TraderConfigDoc
    return TraderConfigDoc(parse_ecf_text('{ Trader Name: T\n}\n'))


def test_icon_double_click_opens_zoom_popup(qapp):
    """Zoom x4 au double-clic sur la colonne icone (demande utilisateur)."""
    from PyQt6.QtGui import QPixmap
    from gui.economy_editor_dialog import EconomyEditorDialog
    dlg = EconomyEditorDialog(_make_config(), {})
    dlg._select_trader_by_name("T")
    dlg.config.doc  # (fixture : trader vide -> ajoute une ligne pour avoir une icone)
    from core.economy.model import TradeItem, RangeSpec
    dlg.config.add_item(dlg.config.find("T"), TradeItem(
        name="MedPack", sell_price=RangeSpec.parse("50-60"),
        sell_stock=RangeSpec.parse("10")))
    dlg._reload_current()
    dlg._refresh_table()
    pm = QPixmap(64, 64)
    pm.fill()
    dlg._icon_pixmap_for = lambda name: pm          # loader redefini pour le test
    r = _row_by_name(dlg, "MedPack")
    dlg._on_cell_double_clicked(r, 0)               # double-clic colonne icone
    popup = getattr(dlg, "_zoom_popup", None)
    assert popup is not None and popup.isVisible()
    label = popup.findChild(__import__("PyQt6.QtWidgets", fromlist=["QLabel"]).QLabel)
    assert label.pixmap().width() == 64 * 3         # zoom x3 (demande utilisateur)
    # croix de fermeture presente et fonctionnelle
    from PyQt6.QtWidgets import QPushButton
    btn = popup.findChild(QPushButton)
    assert btn is not None
    btn.click()
    assert not popup.isVisible()
    # colonne autre que 0 : pas de popup
    dlg._zoom_popup = None
    dlg._on_cell_double_clicked(r, 1)
    assert getattr(dlg, "_zoom_popup", None) is None
