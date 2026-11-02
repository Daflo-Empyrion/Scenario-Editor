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

"""Vue web de l'editeur ECF (gui/ecf_web_view.py) : pont JSON + bascule,
meme parti pris que test_csv_web_view — HORS LIGNE volontairement (pas de
rendu Chromium, un QWebEngineView reel sous offscreen bloque)."""
import json

import pytest

pytest.importorskip("PyQt6.QtWebChannel")

ECF = (
    "# === Groupes de test ===\n"
    "{ +Container Id: 1\n"
    "  Name: Caisse\n"
    "  { Child Items\n"
    "    Name_0: Fiber, param1: 0.5\n"
    "  }\n"
    "}\n"
    "{ +Container Id: 2\n"
    "  Name: AutreCaisse\n"
    "}\n"
)


@pytest.fixture
def ecf_widget(qapp, tmp_path):
    from gui.theme import apply_theme
    from gui.ecf_edit_widget import EcfEditWidget
    apply_theme(qapp)
    path = tmp_path / "Containers.ecf"
    path.write_text(ECF, encoding="utf-8")
    w = EcfEditWidget(path)
    yield w
    w.deleteLater()


def test_bridge_payload_kinds_and_depth(ecf_widget):
    """Entetes de groupe (repères), blocs selectionnables et blocs enfants
    indentes arrivent dans l'ordre d'affichage de l'arbre Qt."""
    from gui.ecf_web_view import EcfWebBridge
    bridge = EcfWebBridge(ecf_widget)
    data = json.loads(bridge.get_entries())
    assert data["name"] == "Containers.ecf"
    kinds = [e["kind"] for e in data["entries"]]
    assert kinds == ["header", "block", "block", "block"]
    assert data["entries"][0]["label"].startswith("\u25a0")   # repere de groupe
    assert data["entries"][2]["depth"] == 1                   # Child Items
    assert data["entries"][1]["depth"] == 0
    assert data["selected"] == -1                             # rien de choisi
    assert data["labels"]["search"]
    # la recherche porte sur Name (meme liste que la recherche Qt)
    caisse = data["entries"][1]
    assert "caisse" in caisse["search"]


def test_select_entry_mirrors_to_tree(ecf_widget):
    """Clic page -> le MEME item devient courant dans l'arbre Qt (source de
    verite), parents replies, table de proprietes suit (_on_block_selected)."""
    from gui.ecf_web_view import EcfWebBridge
    bridge = EcfWebBridge(ecf_widget)
    bridge.get_entries()
    child_idx = 2                              # bloc enfant 'Child Items'
    bridge.select_entry(child_idx)
    assert ecf_widget.tree.currentItem() is bridge._items[child_idx]
    assert ecf_widget.tree.currentItem().parent().isExpanded() is True
    assert ecf_widget._current_block is not None   # le detail a suivi
    assert json.loads(bridge.get_entries())["selected"] == child_idx


def test_select_entry_pushes_light_state(ecf_widget):
    """select_entry pousse l'ETAT LEGER : detail de la table de proprietes
    (cellules {texte, editable}) + selection — jamais les libelles de tout
    l'arbre (gros fichiers)."""
    from gui.ecf_web_view import EcfWebBridge
    bridge = EcfWebBridge(ecf_widget)
    bridge.get_entries()
    seen = []
    bridge.data_changed.connect(seen.append)
    bridge.select_entry(1)                     # bloc +Container Id: 1
    state = json.loads(seen[-1])
    assert "entries" not in state              # etat LEGER
    assert state["selected"] == 1
    det = state["detail"]
    assert det["mode"] == "flat"
    assert det["cols"] == ["Propriete", "Valeur"]
    assert any(row[0]["t"] == "Name" and row[1]["t"] == "Caisse"
               and row[1]["e"] for row in det["rows"])


def test_set_cell_mirrors_to_block(ecf_widget):
    """Edition web -> item.setText() -> itemChanged -> _on_cell_changed :
    le chemin EXACT de la table Qt (snapshot undo, ecriture modele,
    annotation, drapeau modifie)."""
    from core.ecf.model import EcfProperty
    from gui.ecf_web_view import EcfWebBridge
    bridge = EcfWebBridge(ecf_widget)
    bridge.get_entries()
    bridge.select_entry(1)
    det = json.loads(bridge._state())["detail"]
    r, c = next((i, j) for i, row in enumerate(det["rows"])
                for j, cell in enumerate(row) if cell["e"])
    bridge.set_cell(r, c, "Caisse Renommee")
    assert ecf_widget.is_modified() is True
    assert len(ecf_widget._undo_stack) == 1        # snapshot undo une fois
    state2 = json.loads(bridge._state())
    assert state2["detail"]["rows"][r][c]["t"] == "Caisse Renommee"
    # la valeur est bien ecrite dans le MODELE — le rendu du doc est ce qui
    # est sauvegarde (la cellule editee peut porter sur le bloc (Id) ou sur
    # une propriete enfant (Name) : le rendu couvre les deux)
    assert "Caisse Renommee" in ecf_widget.doc.render()


def test_set_cell_refuses_out_of_range(ecf_widget):
    from gui.ecf_web_view import EcfWebBridge
    bridge = EcfWebBridge(ecf_widget)
    bridge.get_entries()
    bridge.select_entry(1)
    before = json.dumps(bridge._state())
    bridge.set_cell(999, 0, "x")
    bridge.set_cell(-1, 0, "x")
    bridge.set_cell(0, 99, "x")
    assert json.dumps(bridge._state()) == before
    assert ecf_widget.is_modified() is False


def test_select_entry_skips_headers_and_out_of_range(ecf_widget):
    from gui.ecf_web_view import EcfWebBridge
    bridge = EcfWebBridge(ecf_widget)
    bridge.get_entries()
    bridge.select_entry(0)                     # entete : jamais selectionnable
    assert ecf_widget.tree.currentItem() is None
    bridge.select_entry(9999)                  # hors bornes : ignore
    bridge.select_entry(-1)
    assert ecf_widget.tree.currentItem() is None


def test_populate_tree_repushes_to_page(ecf_widget):
    """L'arbre reste source de verite : apres un _populate_tree la vue web
    recoit le nouvel etat (signal, pas runJavaScript)."""
    from gui.ecf_web_view import EcfWebBridge
    bridge = EcfWebBridge(ecf_widget)
    ecf_widget._web_bridge = bridge
    ecf_widget._web_view = object()            # vue stub (jamais le vrai ici)
    # coche le bouton SANS declencher _toggle_web_view (elle creerait la
    # vraie vue web — impossible sous offscreen)
    ecf_widget.btn_web_view.blockSignals(True)
    ecf_widget.btn_web_view.setChecked(True)
    ecf_widget.btn_web_view.blockSignals(False)
    seen = []
    bridge.data_changed.connect(seen.append)
    ecf_widget._populate_tree()
    assert seen, "aucune re-poussée apres populate"


def test_toggle_creates_web_view(ecf_widget, monkeypatch):
    from PyQt6.QtWidgets import QWidget
    from gui import ecf_web_view as ewv
    # is_available() depend de l'ordre d'import QtWebEngineWidgets/
    # QApplication sous pytest (piege documente) : force True — la vue est
    # stubbee, jamais de vrai QWebEngineView ici.
    monkeypatch.setattr(ewv, "is_available", lambda: True)

    class _StubView(QWidget):
        def refresh(self):
            pass

    from gui.ecf_web_view import EcfWebBridge
    # On ne cree JAMAIS le vrai QWebEngineView sous pytest offscreen : le
    # demarrage de Chromium y bloque (vecu 01/11). On stub la vue.
    monkeypatch.setattr(ewv, "make_web_view",
                        lambda widget, parent=None: (_StubView(), EcfWebBridge(widget)))
    # le bouton n'est visible que si le moteur web est disponible — fige a
    # la construction du widget, on force le monde « disponible »
    ecf_widget.btn_web_view.setVisible(True)
    assert ecf_widget.btn_web_view.isVisibleTo(ecf_widget) is True
    ecf_widget._toggle_web_view(True)
    assert ecf_widget._web_view is not None
    assert ecf_widget._view_stack.currentWidget() is ecf_widget._web_view
    ecf_widget._toggle_web_view(False)
    assert ecf_widget._view_stack.currentWidget() is ecf_widget.tree
