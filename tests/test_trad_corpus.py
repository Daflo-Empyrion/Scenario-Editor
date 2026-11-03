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

"""Corpus de traduction par cle (demande 03/11/2026) : les cles deja
traduites dans Localization/Dialogues/PDA evitent une traduction IA."""

from pathlib import Path

import pytest

from core import trad_corpus
from core.csv_handler import CsvHandler


@pytest.fixture(autouse=True)
def _clean():
    trad_corpus.clear_cache()
    yield
    trad_corpus.clear_cache()


def _write_csv(folder: Path, name: str, text: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / name
    p.write_text(text, encoding="utf-8")
    return p


HEADER = "KEY,English,Français,Deutsch\n"


def test_detect_type_by_file_name():
    assert trad_corpus.detect_type("C:/x/Extras/Localization.csv") == "localization"
    assert trad_corpus.detect_type("C:/x/Configuration/Dialogues.csv") == "dialogues"
    assert trad_corpus.detect_type("C:/x/Extras/PDA/PDA.csv") == "pda"
    assert trad_corpus.detect_type("C:/x/Items.csv") is None


def test_personal_folder_is_read_and_cached(tmp_path, monkeypatch):
    _write_csv(tmp_path, "Localization.csv",
               HEADER + "bkiTest,Cred Token,Jeton de credit,Cred-Marke\n")
    monkeypatch.setattr("core.settings.get_corpus_trad_dir", lambda: str(tmp_path))

    row = trad_corpus.lookup("localization", "bkiTest")
    assert row is not None
    assert row["Français"] == "Jeton de credit"
    assert row["Deutsch"] == "Cred-Marke"
    assert trad_corpus.lookup("localization", "cleInconnue") is None
    assert trad_corpus.lookup(None, "bkiTest") is None


def test_personal_folder_has_priority_over_embedded(tmp_path, monkeypatch):
    _write_csv(tmp_path, "PDA.csv",
               HEADER + "pda_x,Hello,Bonjour-personnel,Hallo\n")
    monkeypatch.setattr("core.settings.get_corpus_trad_dir", lambda: str(tmp_path))
    row = trad_corpus.lookup("pda", "pda_x")
    assert row["Français"] == "Bonjour-personnel"


def test_duplicate_key_keeps_first_occurrence(tmp_path, monkeypatch):
    _write_csv(tmp_path, "Dialogues.csv",
               HEADER + "dupe,First,Premier,Erste\ndupe,Second,Deuxieme,Zweite\n")
    monkeypatch.setattr("core.settings.get_corpus_trad_dir", lambda: str(tmp_path))
    assert trad_corpus.lookup("dialogues", "dupe")["Français"] == "Premier"


def test_fill_document_only_completes_empty_cells(tmp_path, monkeypatch):
    _write_csv(tmp_path, "Localization.csv",
               HEADER + "k1,English one,Francais un,Deutsch eins\n")
    monkeypatch.setattr("core.settings.get_corpus_trad_dir", lambda: str(tmp_path))

    doc = CsvHandler().parse(
        "KEY,English,Français,Deutsch\r\nk1,English one,,DEJA\r\nk2,Anglais deux,,\r\n")
    filled = trad_corpus.fill_document(doc, "localization")

    assert len(filled) == 1                   # seule la cellule FR vide de k1
    assert doc.rows[0][2] == "Francais un"    # FR complete
    assert doc.rows[0][3] == "DEJA"           # cellule deja remplie conservee
    assert doc.rows[1][2] == ""               # cle inconnue du corpus : intacte


def test_fill_document_matches_columns_by_name(tmp_path, monkeypatch):
    """Un fichier cible peut avoir un ordre de colonnes different du corpus :
    l'appariement se fait par NOM de colonne, jamais par position."""
    _write_csv(tmp_path, "PDA.csv", HEADER + "k,Hello,Bonjour,Hallo\n")
    monkeypatch.setattr("core.settings.get_corpus_trad_dir", lambda: str(tmp_path))
    doc = CsvHandler().parse("KEY,Deutsch,English,Français\r\nk,,Hello,\r\n")
    assert len(trad_corpus.fill_document(doc, "pda")) == 2
    assert doc.rows[0][1] == "Hallo"
    assert doc.rows[0][3] == "Bonjour"


def test_missing_folder_is_graceful(tmp_path, monkeypatch):
    monkeypatch.setattr("core.settings.get_corpus_trad_dir",
                        lambda: str(tmp_path / "nexiste_pas"))
    # seul le corpus embarque repond (ou rien s'il est absent) : pas d'erreur
    trad_corpus.corpus_index("localization")


def test_embedded_corpus_is_shipped_and_readable():
    """Le zip embarque est un LIVRABLE : s'il disparait ou se corrompt, le
    corpus personnel seul repondrait et les tests d'un simple dossier
    passeraient quand meme (d'ou ce garde-fou)."""
    if not trad_corpus.EMBEDDED_ZIP.is_file():
        pytest.skip("corpus embarqué absent de cette copie de travail")
    for kind in ("localization", "dialogues", "pda"):
        assert len(trad_corpus.corpus_index(kind)) > 1000, kind


def test_widget_import_button_fills_and_marks(qapp, tmp_path, monkeypatch):
    """Chemin complet du widget : le bouton « Importer les traductions
    connues » complete la table, marque les cellules du corpus et laisse les
    cellules deja remplies intactes."""
    corpus = tmp_path / "corpus"
    _write_csv(corpus, "Localization.csv",
               HEADER + "k1,English one,Francais un,Deutsch eins\n")
    monkeypatch.setattr("core.settings.get_corpus_trad_dir", lambda: str(corpus))
    from gui.theme import apply_theme
    from gui.csv_edit_widget import CsvEditWidget, COLOR_CORPUS_CELL
    from PyQt6.QtWidgets import QMessageBox
    apply_theme(qapp)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)

    path = tmp_path / "Localization.csv"
    path.write_text("KEY,English,Français,Deutsch\r\nk1,English one,,DEJA\r\n",
                    encoding="utf-8", newline="")
    widget = CsvEditWidget(path, editable=True)
    assert widget._corpus_kind == "localization"
    assert widget.table.item(0, 2).text() == ""

    widget._import_corpus_translations()

    assert widget.table.item(0, 2).text() == "Francais un"
    assert widget.table.item(0, 2).background().color() == COLOR_CORPUS_CELL.color()
    assert widget.table.item(0, 3).text() == "DEJA"      # jamais ecrasee

    # le lookup par cle alimente la traduction d'une seule cellule (sans IA)
    assert widget._corpus_value(0, "fr", "Français") == "Francais un"
