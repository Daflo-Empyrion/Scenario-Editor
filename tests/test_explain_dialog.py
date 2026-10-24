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

"""Popup « Expliquer avec IA » : affichage des faits et rendu de la reponse.
Aucun appel reseau -- _ask est neutralise (l'appel IA reel est couvert par
gui/assistant_worker.py)."""
from core.explain import ExplainContext
from gui.explain_dialog import ExplainDialog


def _ctx():
    return ExplainContext(title="BlocksConfig.ecf — GenA / EnergyOut",
                          subject="EnergyOut", current="150",
                          glossary="energie produite",
                          vanilla="120", observed="3 valeurs, mediane 150",
                          suggestions=["120 (valeur vanille du jeu)"])


def test_dialog_shows_facts_without_calling_ai(qapp, monkeypatch):
    monkeypatch.setattr(ExplainDialog, "_ask", lambda self: None)
    dlg = ExplainDialog(_ctx())
    text = dlg.ctx_view.toPlainText()
    assert "energie produite" in text
    assert "150" in text and "120" in text
    dlg.close()


def test_dialog_renders_answer_and_status(qapp):
    dlg = ExplainDialog(_ctx())
    assert dlg._worker is None  # _ask interrompu faute de fournisseur : rien ici
    dlg._on_delta("Role")
    dlg._on_done("**Role** du champ", "DeepSeek", True)
    assert "Role" in dlg.ai_view.toPlainText()
    assert "DeepSeek" in dlg.status.text()
    assert dlg.btn_again.isEnabled()
    dlg.close()


def test_dialog_reports_ai_failure(qapp):
    dlg = ExplainDialog(_ctx())
    dlg._on_failed("cle absente")
    assert "cle absente" in dlg.status.text()
    assert dlg.btn_again.isEnabled()
    dlg.close()
