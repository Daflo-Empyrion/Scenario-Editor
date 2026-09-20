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

"""Menu contextuel "Creer un Template pour ce bloc" quand un Template
existe DEJA (retour 19/09/2026 : le menu semblait ne rien faire) --
v1.10.0 : info + bouton "Aller au Template" avec navigation, offre_if_exists
uniquement sur ce chemin (le flux post-fusion reste silencieux), et
comparaison INSENSIBLE a la casse. QMessageBox du MODULE UTILISATEUR
mocke (piege documente)."""

from types import SimpleNamespace

import gui.main_window as mw
from gui.main_window import MainWindow


TEMPLATES_TEXT = """{ Template Name: Fusil
  CraftTime: 10
  Target: "AdvC"
}
"""


class _StubBlock:
    """Duck-typed : seule get_property('Name') est lue."""

    def __init__(self, name):
        self._name = name

    def get_property(self, key):
        return self._name if key == "Name" else None


class _FakeBox:
    """Remplace QMessageBox dans gui.main_window : capture le texte et
    simule le clic sur le PREMIER bouton (Aller au Template)."""

    class Icon:
        Information = 1

    class ButtonRole:
        AcceptRole = 2
        RejectRole = 3

    instances = []

    def __init__(self, parent=None):
        self.buttons = []
        self.text = ""
        self.shown = False
        _FakeBox.instances.append(self)

    def setIcon(self, *a):
        pass

    def setWindowTitle(self, *a):
        pass

    def setText(self, text):
        self.text = text

    def addButton(self, text, role):
        btn = SimpleNamespace(text=text, role=role)
        self.buttons.append(btn)
        return btn

    def exec(self):
        self.shown = True

    def clickedButton(self):
        return self.buttons[0]

    @classmethod
    def information(cls, parent, title, text):
        box = cls(parent)
        box.setText(text)
        box.shown = True
        return box


def _make_window(tmp_path, monkeypatch):
    templates = tmp_path / "Templates.ecf"
    templates.write_text(TEMPLATES_TEXT, encoding="utf-8")
    win = MainWindow.__new__(MainWindow)
    win.workspace = SimpleNamespace(working=SimpleNamespace(configuration=[
        SimpleNamespace(path=templates, extension=".ecf")]))
    nav = {"paths": [], "identities": []}

    class _StubEdit:
        def select_block_by_identity(self, identity, **kwargs):
            nav["identities"].append(identity)

    def fake_open(path):
        nav["paths"].append(path)
        return SimpleNamespace(edit_widget=_StubEdit())
    win.open_working_file_tab = fake_open
    return win, templates, nav


def test_existing_template_informs_and_navigates(qapp, tmp_path, monkeypatch):
    win, templates, nav = _make_window(tmp_path, monkeypatch)
    monkeypatch.setattr(mw, "QMessageBox", _FakeBox)
    _FakeBox.instances.clear()

    win._offer_template_for_merged_block(
        _StubBlock("Fusil"), tmp_path / "ItemsConfig.ecf", offer_if_exists=True)

    assert len(_FakeBox.instances) == 1
    assert "Fusil" in _FakeBox.instances[0].text
    # le clic "Aller au Template" a ouvert Templates.ecf et selectionne le bloc
    assert nav["paths"] == [templates]
    assert nav["identities"] == ["Fusil"]


def test_existing_template_case_insensitive(qapp, tmp_path, monkeypatch):
    win, _templates, nav = _make_window(tmp_path, monkeypatch)
    monkeypatch.setattr(mw, "QMessageBox", _FakeBox)
    _FakeBox.instances.clear()

    win._offer_template_for_merged_block(
        _StubBlock("FUSIL"), tmp_path / "ItemsConfig.ecf", offer_if_exists=True)
    assert len(_FakeBox.instances) == 1  # detecte malgre la casse
    assert nav["identities"] == ["Fusil"]  # navigation vers le VRAI nom


def test_merge_flow_stays_silent_when_exists(qapp, tmp_path, monkeypatch):
    """Flux post-fusion (offer_if_exists=False) : silence conserve -- la
    proposition a deja ete faite une fois, aucun message rejoue."""
    win, _templates, nav = _make_window(tmp_path, monkeypatch)

    def boom(*a, **k):
        raise AssertionError("aucun dialogue attendu dans le flux fusion")
    monkeypatch.setattr(mw, "QMessageBox", boom)

    win._offer_template_for_merged_block(
        _StubBlock("Fusil"), tmp_path / "ItemsConfig.ecf",
        offer_if_exists=False)
    assert nav["paths"] == []  # pas de navigation non plus


def test_no_template_no_box_no_navigation(qapp, tmp_path, monkeypatch):
    """Aucun Template existant : le chemin de CREATION prend le relais
    (question ask_yes_no, declinee ici) -- aucune boite 'existe deja'
    ne doit apparaitre."""
    win, _templates, nav = _make_window(tmp_path, monkeypatch)
    monkeypatch.setattr(mw, "QMessageBox", _FakeBox)
    _FakeBox.instances.clear()
    monkeypatch.setattr(mw, "ask_yes_no", lambda *a, **k: False)

    win._offer_template_for_merged_block(
        _StubBlock("Inconnu"), tmp_path / "ItemsConfig.ecf",
        offer_if_exists=True)
    assert _FakeBox.instances == [] and nav["paths"] == []


def test_templates_ecf_absent_informs(qapp, tmp_path, monkeypatch):
    win = MainWindow.__new__(MainWindow)
    win.workspace = SimpleNamespace(working=SimpleNamespace(configuration=[]))
    monkeypatch.setattr(mw, "QMessageBox", _FakeBox)
    _FakeBox.instances.clear()

    win._offer_template_for_merged_block(
        _StubBlock("Fusil"), tmp_path / "ItemsConfig.ecf", offer_if_exists=True)
    assert len(_FakeBox.instances) == 1
    assert "Templates.ecf" in _FakeBox.instances[0].text
