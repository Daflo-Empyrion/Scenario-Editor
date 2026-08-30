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

"""Tests du dialogue Aide > Protocole de test (gui/test_protocol_dialog.py) :
consultation du protocole de test manuel dans l'application (tutoriel +
debogage), avec filtre et export Markdown. Ajoute avec la mise a jour du
protocole (retour utilisateur du 30/08/2026)."""
import importlib.util
from pathlib import Path


def _load_protocol():
    spec = importlib.util.spec_from_file_location(
        "protocole_check", Path(__file__).resolve().parent.parent / "tools" / "protocole_cas.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_protocol_has_gui_category_and_new_cases():
    """Le protocole couvre les nouveautes : theme Verriere/neon/acrylic,
    barre d'outils, raccourcis, compteur bandeau, barre d'etat, boite de
    chargement, regex, export fiche info, protocole in-app."""
    m = _load_protocol()
    ids = {c["id"] for c in m.CASES}
    for expected in ("GUI-001", "GUI-008", "PROJ-015", "COMP-010",
                     "TECH-013", "ROBU-009", "VERIF-015"):
        assert expected in ids
    gui = [c for c in m.CASES if c["cat"] == "GUI"]
    assert len(gui) == 8


def test_protocol_markdown_export_contains_cases():
    m = _load_protocol()
    md = m.protocol_to_markdown()
    assert "228 cas" in md or str(len(m.CASES)) in md
    assert "### PROJ-001" in md
    assert "Resultat attendu" in md
    # les rev d'incrementation apparaissent
    assert "rev 2" in md


def test_protocol_dialog_lists_and_filters_cases(qapp):
    from gui.test_protocol_dialog import TestProtocolDialog
    dlg = TestProtocolDialog()
    total = dlg.tree.topLevelItemCount()
    assert total > 0
    cases_shown = dlg.count_label.text()

    # filtre : un motif qui ne matche rien vide la liste proprement
    dlg.search_edit.setText("zzz_aucune_correspondance")
    assert dlg.tree.topLevelItemCount() == 0
    dlg.search_edit.setText("PROJ-001")
    assert dlg.tree.topLevelItemCount() >= 1
    dlg.search_edit.setText("")
    assert dlg.count_label.text() == cases_shown
    dlg.close()


def test_protocol_dialog_details_show_steps(qapp):
    from gui.test_protocol_dialog import TestProtocolDialog
    dlg = TestProtocolDialog()
    dlg.search_edit.setText("GUI-001")
    dlg.tree.topLevelItem(0).setSelected(True)
    first_child = dlg.tree.topLevelItem(0).child(0)
    dlg.tree.setCurrentItem(first_child)
    html = dlg.details.toHtml()
    assert "GUI-001" in html
    dlg.close()


def test_protocol_menu_entry_opens_dialog(qapp, monkeypatch):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    apply_theme(qapp)
    win = MainWindow()
    assert win.action_test_protocol is not None
    win._open_test_protocol_dialog()
    dlg = win._test_protocol_dialog
    assert dlg.isVisible() is True
    assert dlg.isModal() is False
    # seconde ouverture : la MEME instance est remise en avant
    win._open_test_protocol_dialog()
    assert win._test_protocol_dialog is dlg
    dlg.close()
    win.close()


def test_start_session_button_opens_runner(qapp, monkeypatch):
    """Le bouton 'Commencer une session de tests' ouvre le RUNNER pas-a-pas
    (tools/protocole_test.py) dans le meme processus ; le dialogue de choix
    de session est simule (sinon il bloquerait le test)."""
    from gui import test_protocol_dialog as tp
    runner_module = tp._load_runner_module()
    assert runner_module is not None
    monkeypatch.setattr(runner_module.MainWindow, "_nouvelle_session",
                        lambda self: None)
    dlg = tp.TestProtocolDialog()
    runner = dlg._start_session()
    assert runner is not None and runner.isVisible() is True
    assert runner.windowTitle().startswith("Protocole de test")
    # second appel : la fenetre existante est remise en avant (pas de doublon)
    runner2 = dlg._start_session()
    assert runner2 is runner
    runner.close()
    dlg.close()


def test_start_session_graceful_without_tools(qapp, monkeypatch):
    from gui import test_protocol_dialog as tp
    monkeypatch.setattr(tp, "_load_runner_module", lambda: None)
    infos = []
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: infos.append(True)))
    dlg = tp.TestProtocolDialog()
    assert dlg._start_session() is None
    assert infos == [True]
    dlg.close()


def test_protocol_dialog_graceful_without_tools_folder(qapp, monkeypatch):
    """Installation sans tools/protocole_cas.py : message propre, pas de
    plantage (l'installeur ne embarque pas les outils de developpement)."""
    import gui.test_protocol_dialog as tp
    monkeypatch.setattr(tp, "_load_protocol_module", lambda: None)
    dlg = tp.TestProtocolDialog()
    assert dlg.windowTitle() != ""
    dlg.close()
