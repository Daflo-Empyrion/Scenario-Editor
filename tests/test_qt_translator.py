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

"""Traductions standard de Qt (core/qt_translator.py) -- cause principale des
boutons restes en ANGLAIS sous langue francaise (demande d'audit du
30/08/2026) : les Yes/No/OK/Cancel des QMessageBox.question, QDialogButtonBox
et QInputDialog sont traduits par le fichier qtbase_<lang>.qm de Qt, qu'il
faut installer explicitement sur la QApplication. Sans ce module, t() ne sert
a rien pour ces boutons-la."""
from PyQt6.QtWidgets import QApplication, QMessageBox

from core.qt_translator import install_qt_language


def _yes_button_text() -> str:
    box = QMessageBox(QMessageBox.Icon.Question, "x", "y")
    box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    return box.button(QMessageBox.StandardButton.Yes).text()


def test_french_translates_standard_buttons(qapp):
    assert install_qt_language("fr") is True
    text = _yes_button_text()
    assert "Yes" not in text  # traduit (Oui), quel que soit le mnemonique &


def test_english_restores_source_language(qapp):
    assert install_qt_language("en") is False  # rien a charger : langue source
    assert _yes_button_text().replace("&", "") == "Yes"


def test_unknown_language_falls_back_to_english_gracefully(qapp):
    # Pas d'exception : retombe sur l'anglais (langue source de Qt).
    assert install_qt_language("zz") is False
    assert _yes_button_text().replace("&", "") == "Yes"


def test_reinstall_switches_language(qapp):
    install_qt_language("en")
    text_en = _yes_button_text().replace("&", "")
    install_qt_language("fr")
    text_fr = _yes_button_text()
    assert text_en == "Yes"
    assert "Yes" not in text_fr
    install_qt_language("en")  # remise en etat pour les tests suivants


def test_ask_yes_no_returns_true_on_yes(qapp, monkeypatch):
    """Les boutons Oui/Non sont CREES par l'application (i18n_strings.json,
    cles btn.yes/btn.no) -- jamais les boutons standards de Qt : demande
    explicite de l'utilisateur (30/08/2026) pour une traduction garantie."""
    from gui.msgboxes import ask_yes_no

    def fake_exec(box):
        yes_btn, no_btn = box.buttons()[0], box.buttons()[1]
        assert yes_btn.text() == "Oui" and no_btn.text() == "Non"
        yes_btn.click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    assert ask_yes_no(None, "titre", "message ?") is True


def test_ask_yes_no_returns_false_on_no(qapp, monkeypatch):
    from gui.msgboxes import ask_yes_no

    def fake_exec(box):
        box.buttons()[1].click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    assert ask_yes_no(None, "titre", "message ?") is False


def test_ask_yes_no_labels_come_from_app_i18n(qapp, monkeypatch):
    """Les libelles affiches sont exactement t("btn.yes")/t("btn.no") --
    pas 'Yes'/'No' generes par Qt."""
    from gui.msgboxes import ask_yes_no
    from core.i18n import t
    captured = {}

    def fake_exec(box):
        captured["texts"] = [b.text() for b in box.buttons()]
        return 0

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    ask_yes_no(None, "t", "m")
    assert captured["texts"] == [t("btn.yes"), t("btn.no")]
