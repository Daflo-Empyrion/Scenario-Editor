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

"""Dialogue « Verifier les references croisees » : construction + chemin
VERIF-006 (proposition de correction d'une reference de dialogue cassee).
Regression 04/10/2026 : l'import errone `from core.fsutil import
capture_file` (la fonction vit dans core.workspace_undo) faisait une
ImportError au double-clic sur un resultat — aucun test GUI ne couvrait
ce dialogue."""
from pathlib import Path

from PyQt6.QtWidgets import QDialog

from core.ecf.cross_reference_check import CrossRefIssue
from gui.cross_reference_dialog import CrossReferenceDialog


class _FakeWorking:
    configuration = []


class _FakeWorkspace:
    working = _FakeWorking()


class _FakeMain:
    def _is_path_modified(self, path):
        return False


def _issue(tmp_path):
    return CrossRefIssue(
        source_file=tmp_path / "Dialogues.ecf",
        source_kind="+Dialogue",
        source_identity="RP_Tut_3",
        ref_key="OptionNext_1",
        ref_value="RP_Tut_3_Guide",
        check_id="dialogue_refs",
    )


def test_construction(qapp):
    dlg = CrossReferenceDialog(_FakeWorkspace(), _FakeMain())
    assert dlg.results_list is not None
    assert dlg.checkboxes


def test_dialogue_fix_import_and_cancel(qapp, tmp_path, monkeypatch):
    """La fenetre de correction s'ouvre (imports valides — l'import
    errone de capture_file depuis core.fsutil plantait ici, vecu 04/10)
    et se ferme sans rien ecrire (exec simule Refuse)."""
    dlg = CrossReferenceDialog(_FakeWorkspace(), _FakeMain())
    src = tmp_path / "Dialogues.ecf"
    src.write_text("+Dialogue\n{\n Id: 1\n}\n", encoding="utf-8")
    monkeypatch.setattr(QDialog, "exec",
                        lambda self: QDialog.DialogCode.Rejected)
    # exec simule un refus sans passer par le bouton Annuler : le dialogue
    # rapporte « voir sans corriger » (False) et le fichier reste intact
    assert dlg._propose_dialogue_fix(_issue(tmp_path)) is False
    assert "Id: 1" in src.read_text(encoding="utf-8")
