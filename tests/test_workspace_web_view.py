"""Arbre du workspace en vue web (gui/workspace_web_view.py) : pont seul,
meme parti pris que les autres vues web (jamais de QWebEngineView reel)."""
import json

import pytest

pytest.importorskip("PyQt6.QtWebChannel")


@pytest.fixture
def panel(qapp, tmp_path):
    """Fenetre principale avec un scenario minimal (working tree peuplee)."""
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from core.scanner import scan_scenario
    from core.workspace import Workspace
    apply_theme(qapp)
    config = tmp_path / "Content" / "Configuration"
    config.mkdir(parents=True)
    (config / "ItemsConfig.ecf").write_text("{ Item Name: Rock\n}\n",
                                            encoding="utf-8")
    scenario = scan_scenario(tmp_path)
    win = MainWindow()
    win.workspace = Workspace(source_a=scenario, source_a_root=tmp_path,
                              working=scenario, working_root=tmp_path)
    win._populate_tree(win.tree_working, win.workspace.working)
    yield win
    win.close()


def test_bridge_lists_folders_and_files(panel):
    from gui.workspace_web_view import WorkspaceWebBridge
    bridge = WorkspaceWebBridge(panel, panel.tree_working)
    data = json.loads(bridge.get_entries())
    kinds = [e["kind"] for e in data["entries"]]
    assert kinds[0] == "folder"                    # racine
    labels = [e["label"] for e in data["entries"]]
    assert "Content" in labels and "Configuration" in labels
    assert "ItemsConfig.ecf" in labels
    # profondeur croissante : racine 0, Content 1, Configuration 2, fichier 3
    by_label = {e["label"]: e["depth"] for e in data["entries"]}
    assert by_label["Content"] == 1
    assert by_label["Configuration"] == 2
    assert by_label["ItemsConfig.ecf"] == 3
    assert data["labels"]["search"]


def test_open_entry_opens_file_tab_like_qt_double_click(panel):
    """open_entry rejoue le chemin EXACT du double-clic Qt
    (_on_working_double_clicked -> open_working_file_tab)."""
    from gui.workspace_web_view import WorkspaceWebBridge
    bridge = WorkspaceWebBridge(panel, panel.tree_working)
    data = json.loads(bridge.get_entries())
    idx = next(i for i, e in enumerate(data["entries"])
               if e["label"] == "ItemsConfig.ecf")
    bridge.open_entry(idx)
    assert panel.tabs.count() == 1
    assert panel.tabs.tabToolTip(0).endswith("ItemsConfig.ecf")


def test_open_entry_ignores_folders_and_ranges(panel):
    from gui.workspace_web_view import WorkspaceWebBridge
    bridge = WorkspaceWebBridge(panel, panel.tree_working)
    bridge.get_entries()
    bridge.open_entry(0)          # racine : dossier, rien a ouvrir
    bridge.open_entry(9999)
    bridge.open_entry(-1)
    assert panel.tabs.count() == 0


def test_populate_tree_repushes_when_web_checked(panel):
    """L'arbre reste source de verite : un repeuplement re-pousse vers la
    page (par le canal), mais seulement si la vue web est affichee."""
    from gui.workspace_web_view import WorkspaceWebBridge
    bridge = WorkspaceWebBridge(panel, panel.tree_working)
    # _web_pair pre-rempli (vue stub) — jamais le vrai QWebEngineView ici ;
    # le vrai bouton est coché SANS signal (le toggle creerait la vue)
    panel.tree_working._web_pair = (object(), bridge)
    panel._btn_ws_web.blockSignals(True)
    panel._btn_ws_web.setChecked(True)
    panel._btn_ws_web.blockSignals(False)
    seen = []
    bridge.data_changed.connect(seen.append)
    # bouton coche : un refresh explicite pousse immediatement
    panel._workspace_web_refresh(panel.tree_working)
    assert len(seen) == 1
    panel._populate_tree(panel.tree_working, panel.workspace.working)
    assert len(seen) == 2, "aucune re-poussée apres populate"


def test_toggle_creates_web_view(panel, monkeypatch):
    from PyQt6.QtWidgets import QWidget
    from gui import workspace_web_view as wwv
    monkeypatch.setattr(wwv, "is_available", lambda: True)

    class _StubView(QWidget):
        def refresh(self):
            pass

    from gui.workspace_web_view import WorkspaceWebBridge
    monkeypatch.setattr(wwv, "make_web_view",
                        lambda mw, tree, parent=None, opener=None: (
                            _StubView(), WorkspaceWebBridge(mw, tree,
                                                            opener=opener)))
    panel._btn_ws_web.setVisible(True)
    panel._btn_ws_web.setChecked(True)          # declenche le toggle du helper
    assert panel.tree_working._web_pair is not None
    assert panel._ws_stack.currentWidget() is panel.tree_working._web_pair[0]
    panel._btn_ws_web.setChecked(False)
    assert panel._ws_stack.currentWidget() is panel.tree_working


def test_source_tree_web_opens_read_only_tab(panel, monkeypatch):
    """Scenario A : open_entry rejoue _on_source_double_clicked -> onglet
    lecture seule source_root=working_root."""
    from gui.workspace_web_view import WorkspaceWebBridge, make_web_view
    # le panneau B existe (masque) avec sa pile et son bouton
    assert panel._b_stack is not None and panel._btn_b_web is not None
    bridge = WorkspaceWebBridge(
        panel, panel.tree_a,
        opener=lambda item: panel._on_source_double_clicked(item,
                                                            panel._root_a))
    panel._populate_tree(panel.tree_a, panel.workspace.source_a)
    data = json.loads(bridge.get_entries())
    idx = next(i for i, e in enumerate(data["entries"])
               if e["label"] == "ItemsConfig.ecf")
    bridge.open_entry(idx)
    assert panel.tabs.count() == 1
    # l'onglet source est en lecture seule (titre du widget != working)
    assert panel.tabs.tabToolTip(0).endswith("ItemsConfig.ecf")
