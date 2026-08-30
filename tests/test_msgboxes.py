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

"""Tests des dialogues de confirmation a boutons APPLICATION (gui/msgboxes.py) :
les libelles doivent venir de t() (i18n_strings.json), jamais des boutons
standards de Qt dessines via qtbase_<lang>.qm -- demande explicite de
l'utilisateur apres l'audit i18n. Technique de simulation : monkeypatch de
QMessageBox.exec avec clic programmatique sur le bouton vise (meme pattern
que tests/test_add_block_workflow.py)."""
import pytest
from PyQt6.QtWidgets import QMessageBox

from core.i18n import t
from gui.msgboxes import ask_save_discard_cancel, ask_yes_no


def _click_button(label):
    """Remplace QMessageBox.exec : ferme la boite en cliquant le bouton porte
    le libelle demande. Par libelle (pas par indice) : Qt reordonne les
    boutons selon la plate-forme, l'ordre d'ajout n'est pas celui de
    buttons()."""

    def _exec(box):
        for b in box.buttons():
            if b.text() == label:
                b.click()
                return
        raise AssertionError(f"bouton introuvable : {label}")

    return _exec


def test_ask_yes_no_returns_true_on_yes(qapp, monkeypatch):
    monkeypatch.setattr(QMessageBox, "exec", _click_button(t("btn.yes")))
    assert ask_yes_no(None, "titre", "texte") is True


def test_ask_yes_no_returns_false_on_no(qapp, monkeypatch):
    monkeypatch.setattr(QMessageBox, "exec", _click_button(t("btn.no")))
    assert ask_yes_no(None, "titre", "texte") is False


def test_ask_yes_no_buttons_are_application_translated(qapp, monkeypatch):
    """Les deux boutons portent EXACTEMENT les libelles t("btn.yes")/t("btn.no")
    -- si une regression revenait aux boutons standards de Qt, ce test echoue
    des que qtbase n'est pas traduit (c'est le bug d'origine)."""
    seen = []

    def _exec(box):
        seen.extend(b.text() for b in box.buttons())

    monkeypatch.setattr(QMessageBox, "exec", _exec)
    ask_yes_no(None, "titre", "texte")
    assert sorted(seen) == sorted([t("btn.yes"), t("btn.no")])


@pytest.mark.parametrize("label,expected", [
    (t("btn.save_files"), "save"),
    (t("btn.discard"), "discard"),
    (t("btn.cancel"), "cancel"),
])
def test_ask_save_discard_cancel_routes_click(qapp, monkeypatch, label, expected):
    monkeypatch.setattr(QMessageBox, "exec", _click_button(label))
    assert ask_save_discard_cancel(None, "titre", "texte") == expected


def test_ask_save_discard_cancel_buttons_are_application_translated(qapp, monkeypatch):
    seen = []

    def _exec(box):
        seen.extend(b.text() for b in box.buttons())

    monkeypatch.setattr(QMessageBox, "exec", _exec)
    ask_save_discard_cancel(None, "titre", "texte")
    assert sorted(seen) == sorted(
        [t("btn.save_files"), t("btn.discard"), t("btn.cancel")])
