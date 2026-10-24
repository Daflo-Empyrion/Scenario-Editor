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

"""Bouton « Expliquer avec l'IA » du bilan de validation : la question
contient le fichier, le bloc, le code et le message d'origine."""
from pathlib import Path

from core.ecf.parser import parse_ecf_text
from core.ecf.validation import validate_document
from gui.validation_dialog import explain_question

RAW = "\n".join([
    "{ Block Id: 7, Name: BadBlock",
    "  Count: 3,4",
    "}",
    "",
])


def test_explain_question_carries_the_real_issue():
    doc = parse_ecf_text(RAW)
    issues = validate_document(doc, Path("BlocksConfig.ecf"))
    issue = next(i for i in issues if i.code == "E004")
    question = explain_question(issue)
    assert "BlocksConfig.ecf" in question
    assert "BadBlock" in question
    assert "E004" in question
    assert "Virgule non protegee" in question
    assert "outils" in question
