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

"""Vue web du CSV (gui/csv_web_view.py, 01/11) : pont JSON + bascule +
MIROIR des editions dans la table Qt (source de verite). HORS LIGNE
volontairement : pas de rendu Chromium (meme parti pris que la vue web de
l'arbre technologique)."""
import json
import shutil
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "tech_tree_scenario"
pytest.importorskip("PyQt6.QtWebChannel")


@pytest.fixture
def csv_widget(qapp, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: None)
    src = tmp_path / "Extras" / "Localization.csv"
    src.parent.mkdir(parents=True)
    shutil.copy(Path(__file__).parent / "fixtures" / "localization_small.csv",
                src)
    from gui.csv_edit_widget import CsvEditWidget
    w = CsvEditWidget(src, editable=True)
    yield w
    w.deleteLater()


def test_bridge_meta_and_rows(csv_widget):
    from gui.csv_web_view import CsvWebBridge
    bridge = CsvWebBridge(csv_widget)
    meta = json.loads(bridge.get_meta())
    assert meta["rows"] == csv_widget.table.rowCount()
    assert meta["header"] == csv_widget.doc.header
    assert meta["editable"] is True
    payload = json.loads(bridge.get_rows(0, 2))
    assert payload["start"] == 0
    assert len(payload["rows"]) == min(2, meta["rows"])
    # bornes serrees : au-dela de la fin -> vide, jamais d'exception
    assert json.loads(bridge.get_rows(meta["rows"] + 10, 5))["rows"] == []


def test_bridge_set_cell_mirrors_to_table(csv_widget):
    """Edition web -> la TABLE Qt est mise a jour (source de verite) : le
    doc/_sync, l'undo et toutes les fonctions existantes restent justes."""
    from gui.csv_web_view import CsvWebBridge
    bridge = CsvWebBridge(csv_widget)
    row, col = 0, 1
    old = csv_widget.table.item(row, col).text()
    bridge.set_cell(row, col, old + " XX")
    assert csv_widget.table.item(row, col).text() == old + " XX"
    assert csv_widget.is_modified() is True
    # snapshot undo pris une fois par salve (pas par cellule)
    assert len(csv_widget._undo_stack) == 1
    bridge.set_cell(row, col, old + " YY")
    assert len(csv_widget._undo_stack) == 1


def test_web_undo_restores_table(csv_widget):
    from gui.csv_web_view import CsvWebBridge
    bridge = CsvWebBridge(csv_widget)
    old = csv_widget.table.item(0, 1).text()
    bridge.set_cell(0, 1, old + " MOD")
    csv_widget.undo()
    assert csv_widget.table.item(0, 1).text() == old


def test_search_returns_row_indices(csv_widget):
    from gui.csv_web_view import CsvWebBridge
    bridge = CsvWebBridge(csv_widget)
    # cherche une valeur connue du fixture
    target = csv_widget.table.item(0, 0).text()
    hits = json.loads(bridge.search(target[:8].lower(), -1))
    # paires [ligne, colonne] pour le surlignage cote page
    assert all(isinstance(h, list) and len(h) == 2 for h in hits)
    # portee par colonne : la colonne 1 (English) ne contient pas la cle
    assert json.loads(bridge.search(target[:8].lower(), 1)) == []
    assert [h for h in json.loads(bridge.search(target[:8].lower(), 0))
            if h[1] == 0]
    assert json.loads(bridge.search("", -1)) == []


def test_toggle_creates_web_view(csv_widget, monkeypatch):
    from PyQt6.QtWidgets import QWidget
    from gui import csv_web_view as cwv
    if not cwv.is_available():
        pytest.skip("WebEngine indisponible")

    class _StubView(QWidget):
        def refresh(self):
            pass

    # N° cree JAMAIS le vrai QWebEngineView sous pytest offscreen : le
    # demarrage de Chromium y bloque (vecu 01/11). On stub la vue — le
    # rendu reel est valide a la main dans l'application.
    monkeypatch.setattr(cwv, "make_web_view",
                        lambda widget, parent=None: (_StubView(), cwv.CsvWebBridge(widget)))
    csv_widget._toggle_web_view(True)
    assert csv_widget._web_view is not None
    assert csv_widget._stack.currentWidget() is csv_widget._web_view
    csv_widget._toggle_web_view(False)
    assert csv_widget._stack.currentWidget() is csv_widget.table
    # la table reste complete apres aller-retour
    assert csv_widget.table.rowCount() == len(csv_widget.doc.rows)


def test_run_action_whitelist_add_and_delete_row(csv_widget):
    """La barre web passe par une liste blanche de methodes EXISTANTES du
    widget — ajout/suppression de ligne inclus (selection Qt mirroiree)."""
    from gui.csv_web_view import CsvWebBridge
    bridge = CsvWebBridge(csv_widget)
    before = csv_widget.table.rowCount()
    bridge.run_action("add_row")
    assert csv_widget.table.rowCount() == before + 1
    # suppression : la page selectionne d'abord la ligne courante
    bridge.set_current_row(before)          # la ligne ajoutee
    assert csv_widget.table.currentRow() == before
    bridge.run_action("delete_row")
    assert csv_widget.table.rowCount() == before
    assert csv_widget.is_modified() is True


def test_run_action_unknown_name_ignored(csv_widget):
    """Un nom d'action venu de la page ne doit JAMAIS atteindre getattr
    libre (liste blanche stricte)."""
    from gui.csv_web_view import CsvWebBridge
    bridge = CsvWebBridge(csv_widget)
    before = csv_widget.table.rowCount()
    bridge.run_action("save")               # n'est PAS dans la liste blanche... si, il y est
    bridge.run_action("__init__")           # intrusif : ignore silencieusement
    assert csv_widget.table.rowCount() == before


def test_run_action_readonly_refused(tmp_path, qapp, monkeypatch):
    from gui.csv_web_view import CsvWebBridge
    shutil.copy(Path(__file__).parent / "fixtures" / "localization_small.csv",
                tmp_path / "L.csv")
    from gui.csv_edit_widget import CsvEditWidget
    w = CsvEditWidget(tmp_path / "L.csv", editable=False)
    bridge = CsvWebBridge(w)
    before = w.table.rowCount()
    bridge.run_action("add_row")
    assert w.table.rowCount() == before     # lecture seule : refuse
    w.deleteLater()


def test_ctx_labels_and_languages_in_meta(csv_widget):
    """Le menu contextuel FR/EN : libelles via t() et langues du pipeline."""
    from gui.csv_web_view import CsvWebBridge
    bridge = CsvWebBridge(csv_widget)
    meta = json.loads(bridge.get_meta())
    for key in ("edit", "copy", "cut", "paste", "clear",
                "translate_to", "explain", "bold", "color"):
        assert meta["ctx"][key]
    assert meta["languages"][0][1] == "fr"


def test_clipboard_cells(csv_widget, monkeypatch):
    from PyQt6.QtGui import QGuiApplication
    from gui.csv_web_view import CsvWebBridge
    bridge = CsvWebBridge(csv_widget)
    old = csv_widget.table.item(0, 1).text()
    bridge.copy_cell(0, 1)
    assert QGuiApplication.clipboard().text() == old
    bridge.paste_cell(1, 1)
    assert csv_widget.table.item(1, 1).text() == old
    bridge.cut_cell(0, 1)
    assert csv_widget.table.item(0, 1).text() == ""
    assert QGuiApplication.clipboard().text() == old
    bridge.clear_cell(1, 1)
    assert csv_widget.table.item(1, 1).text() == ""
    assert csv_widget.is_modified() is True


def test_wrap_bbcode(csv_widget):
    from gui.csv_web_view import CsvWebBridge
    bridge = CsvWebBridge(csv_widget)
    old = csv_widget.table.item(0, 1).text()
    bridge.wrap_bbcode(0, 1, "[b]", "[/b]")
    assert csv_widget.table.item(0, 1).text() == f"[b]{old}[/b]"
    # lecture seule : refuse
    csv_widget.editable = False
    bridge.wrap_bbcode(0, 1, "[b]", "[/b]")
    assert csv_widget.table.item(0, 1).text() == f"[b]{old}[/b]"
    csv_widget.editable = True


def test_bbcode_blacklist_names_ignored(csv_widget):
    """wrap/ctx n'acceptent que des balises construites cote Python — la
    page n'envoie que des noms d'effet ; run_action reste liste blanche."""
    from gui.csv_web_view import CsvWebBridge
    bridge = CsvWebBridge(csv_widget)
    before = csv_widget.table.rowCount()
    bridge.run_action("eval")        # intrusif : ignore
    bridge.run_action("delete_row")  # sans selection : no-op
    assert csv_widget.table.rowCount() == before


def test_wrap_and_paste_emit_data_changed(csv_widget):
    """Tout slot de menu qui modifie la table doit pousser data_changed a
    la page (vecu 01/11 : le wrap BBCode ne se voyait pas a l'ecran)."""
    from gui.csv_web_view import CsvWebBridge
    bridge = CsvWebBridge(csv_widget)
    seen = []
    bridge.data_changed.connect(lambda p: seen.append(1))
    bridge.wrap_bbcode(0, 1, "[b]", "[/b]")
    bridge.paste_cell(1, 1)
    bridge.clear_cell(1, 1)
    bridge.cut_cell(0, 1)
    assert len(seen) == 4
    # copy ne modifie pas : pas de push
    bridge.copy_cell(0, 1)
    assert len(seen) == 4
