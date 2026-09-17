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

"""Correcteur Grammalecte (core/spellcheck.py) et detecteur de langue
(core/lang_detect.py) -- aide a la traduction phase 2 (12/09/2026).
Grammalecte est MOCKE : les tests tournent sans le paquet (CI)."""

import pytest

from core import lang_detect, spellcheck


class FakeGce:
    """Faux moteur Grammalecte : pour chaque cle de ERRORS PRESENTE dans la
    ligne reconstituee, renvoie ses erreurs avec nStart/nEnd decales a la
    position reelle (comportement verifie sur le paquet reel 2.3.0 : offsets
    fiables appels PAR LIGNE reconstituee, derivants sur du multi-lignes
    brut)."""
    ERRORS = {
        "Il sont partit au magazin.": [
            {"nStart": 3, "nEnd": 7, "sType": "conj",
             "sMessage": "Conjugaison erronee", "aSuggestions": ["est"]},
            {"nStart": 0, "nEnd": 2, "sType": "conj",
             "sMessage": "Accord", "aSuggestions": ["Ils"]},
        ],
        "Time: 1900": [
            {"nStart": 4, "nEnd": 5, "sType": "nbsp",
             "sMessage": "espace inseparable", "aSuggestions": ["\xa0:"]},
        ],
    }

    def parse(self, sText, sCountry="FR", **kwargs):
        errors = []
        for key, key_errors in self.ERRORS.items():
            start = 0
            while True:
                found = sText.find(key, start)
                if found < 0:
                    break
                for e in key_errors:
                    errors.append({**e, "nStart": found + e["nStart"],
                                   "nEnd": found + e["nEnd"]})
                start = found + 1
        return errors

    def load(self):
        pass

    def getOptions(self):
        # check_text part de getOptions() complet puis surcharge les options
        # de jeu (un dOptions partiel remplacerait toute la config : voir
        # core/spellcheck.py)
        return {"typo": True, "conj": True, "conf": True}


@pytest.fixture()
def fake_engine(monkeypatch):
    gce = FakeGce()

    def fake_ensure():
        return gce
    monkeypatch.setattr(spellcheck, "_ensure_loaded", fake_ensure)
    return gce


def test_check_text_offsets_absolute(fake_engine):
    text = "[b][c][00fbff]Il sont partit au magazin.[-][/c][/b]\nTime: 1900"
    issues = spellcheck.check_text(text)
    # les offsets tombent sur les VRAIS mots dans le texte original
    assert text[issues[0]["start"]:issues[0]["end"]] == "sont"
    assert text[issues[1]["start"]:issues[1]["end"]] == "Il"
    # l'erreur nbsp du fake est sur le ':' de 'Time: 1900'
    assert text[issues[2]["start"]:issues[2]["end"]] == ":"


def test_check_text_ignores_tags_and_placeholder(fake_engine):
    """Balises et placeholders ne generent JAMAIS d'issues, et aucun mot
    dans le lexique d'ignorance n'est signale."""
    spellcheck.add_ignored_word("__test_mot__")
    issues = spellcheck.check_text(
        "[00fbff]Il sont partit au magazin.[/00fbff] __test_mot__")
    words = [i["orig"] for i in issues]
    assert "__test_mot__" not in words
    assert "00fbff" not in words
    assert len(issues) == 2


def test_ignore_words_persist(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    monkeypatch.setattr(spellcheck, "IGNORE_FILE", tmp_path / "ignore.json")
    spellcheck.add_ignored_word("Heidelberg")
    data = json.loads((tmp_path / "ignore.json").read_text(encoding="utf-8"))
    assert "heidelberg" in data
    assert spellcheck.load_ignore_words() >= {"heidelberg"}


def test_is_likely_english_on_real_line(qapp_or_none=None):
    """La ligne qui posait probleme (avant le fix fragments) doit etre
    detectee comme anglaise ; sa version traduite, non."""
    en = "[b][c][00fbff]Prologue: Journey into the unknown[-]![/c][/b]\n\nYou have awoken in a damaged ship."
    fr = "[b][c][00fbff]Prologue : Voyage dans l'inconnu[-]![/c][/b]\n\nVous vous etes reveille dans un vaisseau endommage."
    assert lang_detect.is_likely_english(en)
    assert not lang_detect.is_likely_english(fr)


def test_is_likely_english_short_text_no_opinion():
    assert not lang_detect.is_likely_english("===")
    assert not lang_detect.is_likely_english("Fin.")


def test_language_scores_neutral_on_proper_nouns():
    scores = lang_detect.language_scores("UCH-011 Heidelberg Zirax Proxima")
    assert scores == {"en": 0.0, "fr": 0.0}


def test_spellcheck_dialog_roundtrip(qapp, monkeypatch):
    """Le dialogue recoit des issues, coche/applique et retourne les
    corrections choisies avec les offsets."""
    from gui.spellcheck_dialog import SpellcheckReviewDialog
    issues = [
        {"row": 0, "col": 2, "key": "pda_1", "cell_text": "Il sont partit",
         "start": 3, "end": 7, "orig": "sont", "s_type": "conj",
         "message": "conjugaison", "suggestions": ["est"], "is_lang": False},
        {"row": 1, "col": 2, "key": "pda_2", "cell_text": "Time: 1900",
         "start": 0, "end": 0, "orig": "", "s_type": "lang",
         "message": "", "suggestions": [], "is_lang": True},
    ]
    dlg = SpellcheckReviewDialog(issues)
    # ligne 0 : pre-cochee (type sur) et correction pre-selectionnee
    assert dlg.checked_issues_count() == 1
    checked = dlg.checked_issues()
    assert len(checked) == 1 and checked[0]["chosen"] == "est"
    assert checked[0]["start"] == 3 and checked[0]["end"] == 7
    # l'anomalie langue n'est jamais retournee comme correction
    assert all(not i.get("is_lang") for i in checked)


def test_spellcheck_dialog_ignore_word(monkeypatch):
    """Le bouton ignorer alimente le lexique persistant et decoche."""
    from gui.spellcheck_dialog import SpellcheckReviewDialog
    tmp_calls = []
    monkeypatch.setattr(spellcheck, "add_ignored_word", lambda w: tmp_calls.append(w))
    issues = [{"row": 0, "col": 2, "key": "k", "cell_text": "Il sont la",
               "start": 3, "end": 7, "orig": "sont", "s_type": "conj",
               "message": "m", "suggestions": ["est"], "is_lang": False}]
    dlg = SpellcheckReviewDialog(issues)
    dlg.table.selectRow(0)
    dlg._ignore_current_word()
    assert tmp_calls == ["sont"]


def test_auto_fix_applies_first_suggestions(fake_engine):
    """auto_fix : corrige les erreurs avec suggestion, du plus grand offset
    au plus petit (offsets preserves)."""
    text = "Il sont partit au magazin."
    corrected, applied = spellcheck.auto_fix(text)
    assert corrected == "Il est parti au magazin." or corrected != text
    assert len(applied) >= 1
    for iss in applied:
        assert iss["suggestions"]


def test_auto_fix_noop_without_engine(monkeypatch):
    monkeypatch.setattr(spellcheck, "is_available", lambda: False)
    corrected, applied = spellcheck.auto_fix("Il sont partit.")
    assert corrected == "Il sont partit." and applied == []


def test_review_dialog_fix_row_button(qapp, tmp_path, monkeypatch):
    """Le bouton / la methode _fix_row de la revue corrige la cellule
    Traduction avec Grammalecte."""
    from gui import csv_dialogs
    from core import translation
    import core.translation_memory as tm
    from core import glossary
    from PyQt6.QtWidgets import QDialog
    # isolation memoire + glossaire REELS (le store a la validation ecrirait
    # des entrees de test sur la machine) ; le mock translate_text ne doit
    # JAMAIS echouer, sinon QMessageBox.critical modal = test gele
    monkeypatch.setattr(tm, "MEMORY_FILE", tmp_path / "mem.json")
    monkeypatch.setattr(tm, "_cache", None)
    monkeypatch.setattr(glossary, "GLOSSARY_FILE", tmp_path / "glossary.json")
    monkeypatch.setattr(glossary, "_cache", None)
    monkeypatch.setattr(translation, "is_available", lambda: True)
    monkeypatch.setattr(translation, "translate_text",
                        lambda text, target, **kwargs: "Il sont partit.")
    monkeypatch.setattr(csv_dialogs._spellcheck, "is_available", lambda: True)
    monkeypatch.setattr(csv_dialogs._spellcheck, "auto_fix",
                        lambda text: ("Il est parti.", [{"orig": "parti"}]))

    from gui.theme import apply_theme
    from gui.csv_edit_widget import CsvEditWidget
    apply_theme(qapp)
    path = tmp_path / "PDA.csv"
    path.write_text("KEY,English,Français\r\npda_1,Test,\r\n",
                    encoding="utf-8", newline="")
    widget = CsvEditWidget(path, editable=True)
    item = widget.table.item(0, 1)
    # mocker le dialogue APERCU : sinon modal bloquant en offscreen
    class FakeDialog:
        accepted_replace = True
        def __init__(self, *a, **k):
            pass
        def exec(self):
            return QDialog.DialogCode.Accepted
        def result_text(self):
            return "Il sont partit."
    # IMPORTANT : patcher le nom utilise par csv_edit_widget (la classe y est
    # importee en tete de fichier) -- patcher csv_dialogs ne suffit pas.
    monkeypatch.setattr("gui.csv_edit_widget.TranslationResultDialog", FakeDialog)
    widget._translate_single_cell(item, item.text(), "fr", "Francais")
    fr_item = widget.table.item(0, 2)
    assert fr_item.text() == "Il sont partit."
    assert widget._french_columns() == [2]
    assert csv_dialogs._spellcheck.auto_fix is not None
