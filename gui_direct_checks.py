# -*- coding: utf-8 -*-
"""Validation directe de l'application reelle -- scenario complet propre."""
import os, shutil
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path

REPO = Path(__file__).resolve().parent
SRC_A = REPO / "gui_test_scenario"
PROJ = REPO / "gui_test_project"
WORKING = PROJ / "copie_de_travail"
BLOCKS = WORKING / "Content" / "Configuration" / "BlocksConfig.ecf"
BLOCKS_A = SRC_A / "Content" / "Configuration" / "BlocksConfig.ecf"

# --- fixtures propres --------------------------------------------------------
BASE = (
    "{ Block Id: 100, Name: TestBlockA\r\n"
    "  HitPoints: 100\r\n"
    "  Material: stone\r\n"
    "  Ref: BaseBlock\r\n"
    "}\r\n"
    "{ Block Id: 200, Name: TestBlockB\r\n"
    "  HitPoints: 250\r\n"
    "}\r\n"
)
if SRC_A.exists():
    shutil.rmtree(SRC_A)
if PROJ.exists():
    shutil.rmtree(PROJ)
(SRC_A / "Content" / "Configuration").mkdir(parents=True)
BLOCKS_A.write_text(BASE, encoding="utf-8")
from core.workspace import create_working_copy
create_working_copy(SRC_A, WORKING)

def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ((" -- " + detail) if detail else ""))
    return ok

from PyQt6.QtWidgets import QApplication, QDialog
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
app = QApplication(["t"])
from core.workspace import load_existing_workspace
from gui.main_window import MainWindow
import gui.merge_preview_dialog as mpd

ws = load_existing_workspace(SRC_A, WORKING)
win = MainWindow()
win.show()
app.processEvents()
win.workspace = ws
win._refresh_all_trees()
app.processEvents()

results = []

# 1. ouverture onglet + edition + Ctrl+Z (dispatch direct : QTest ne declenche
#    pas les QShortcut en offscreen)
widget = win.open_working_file_tab(BLOCKS)
app.processEvents()
edit = getattr(widget, "edit_widget", widget)
block = next(iter(edit.doc.iter_blocks()))
edit.select_block_by_identity(block.get("Id"))
app.processEvents()
row = next(r for r in range(edit.props_table.rowCount())
           if edit.props_table.item(r, 0).text() == "HitPoints")
edit.props_table.item(row, 1).setText("999")
edit._on_cell_changed(edit.props_table.item(row, 1))
app.processEvents()
results.append(check("ECF-005 edition annulee via _global_undo",
                     win._global_undo() is None and "999" not in edit.doc.render()))
results.append(check("ECF-017 bloc courant conserve apres annulation",
                     edit._current_block is not None))

# 2. marqueur d'onglet modifie
row = next(r for r in range(edit.props_table.rowCount())
           if edit.props_table.item(r, 0).text() == "HitPoints")
edit.props_table.item(row, 1).setText("999")
edit._on_cell_changed(edit.props_table.item(row, 1))
app.processEvents()
idx = win.tabs.indexOf(widget)
icon = win.tabs.tabIcon(idx)
color = win.tabs.tabBar().tabTextColor(idx)
results.append(check("OPEN-011 marqueur + icone sur onglet modifie",
                     win.tabs.tabText(idx).startswith("●") and not icon.isNull()))
results.append(check("OPEN-011 texte d'onglet rouge", color.red() > 180))

# 3. enregistre (nettoie l'etat pour la fusion) puis fusion avec apercu
widget.save()
app.processEvents()

# source A : ajoute Armor: 7 (nouvelle propriete) -- read_text a traduit les
# CRLF en LF : remplacer sur '\n' seul
txt = BLOCKS_A.read_text(encoding="utf-8")
BLOCKS_A.write_text(txt.replace("  Ref: BaseBlock\n", "  Ref: BaseBlock\n  Armor: 7\n"),
                    encoding="utf-8", newline="")

captured = {}
def fake_exec_factory(uncheck_armor):
    def exec_(self):
        captured["rows"] = [(self.table.item(r, 2).text(), self.table.item(r, 3).text())
                            for r in range(self.table.rowCount())]
        for r in range(self.table.rowCount()):
            if self.table.item(r, 3).text() == "Armor":
                self.table.item(r, 0).setCheckState(
                    Qt.CheckState.Unchecked if uncheck_armor else Qt.CheckState.Checked)
        # mimique _on_accept (le vrai bouton OK) : arbitrage puis accept
        self.apply_selected()
        return QDialog.DialogCode.Accepted
    return exec_

mpd.MergePreviewDialog.exec = fake_exec_factory(uncheck_armor=True)
win._merge_ecf_with_preview(BLOCKS_A, BLOCKS, "Scenario A")
app.processEvents()
disk1 = BLOCKS.read_text(encoding="utf-8")
print("DEBUG rows:", captured.get("rows"))
results.append(check("ECF-030 apercu liste la propriete ajoutee 'Armor'",
                     any(cle == "Armor" for _b, cle in captured.get("rows", []))))
results.append(check("FUS-010 ligne decochee NON ecrite", "Armor:" not in disk1))
results.append(check("FUS-010 round-trip intact", "HitPoints: 100" in disk1))
results.append(check("FUS-010 undo global actif apres fusion",
                     win.btn_workspace_undo.isEnabled()))

mpd.MergePreviewDialog.exec = fake_exec_factory(uncheck_armor=False)
win._merge_ecf_with_preview(BLOCKS_A, BLOCKS, "Scenario A")
app.processEvents()
disk2 = BLOCKS.read_text(encoding="utf-8")
results.append(check("FUS-010 ligne cochee ECRITE", "Armor: 7" in disk2))

# 4. undo global ramene l'etat d'avant fusion
win._undo_workspace_action()
app.processEvents()
disk3 = BLOCKS.read_text(encoding="utf-8")
results.append(check("FUS-010 undo global annule la fusion", "Armor: 7" not in disk3))

win.close()
app.processEvents()

ok = sum(1 for v in results if v)
print(f"===== {ok}/{len(results)} OK =====")
