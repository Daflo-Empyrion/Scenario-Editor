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


# -------------------------------- apprentissage du corpus (demande 12/11)

def test_remember_adds_a_missing_key(tmp_path, monkeypatch):
    """Une cle absente est AJOUTEE au corpus perso : le scenario suivant la
    reprendra sans payer d'IA."""
    monkeypatch.setattr("core.settings.get_corpus_trad_dir",
                        lambda: str(tmp_path / "corpus"))
    path = trad_corpus.remember("localization", "bkiNew",
                                {"English": "Cred Token", "Français": "Jeton"},
                                header=["KEY", "English", "Français"])
    assert path is not None and path.is_file()
    assert path.read_text(encoding="utf-8").splitlines() == [
        "KEY,English,Français", "bkiNew,Cred Token,Jeton"]
    # visible tout de suite : le cache est invalide a l'ecriture
    assert trad_corpus.lookup("localization", "bkiNew")["Français"] == "Jeton"


def test_remember_never_overwrites_and_completes_empty_cells(tmp_path, monkeypatch):
    corpus = tmp_path / "corpus"
    _write_csv(corpus, "Localization.csv", HEADER + "k1,One,Un,\n")
    monkeypatch.setattr("core.settings.get_corpus_trad_dir", lambda: str(corpus))
    trad_corpus.remember("localization", "k1",
                         {"Français": "AUTRE", "Deutsch": "Eins"})
    text = (corpus / "Localization.csv").read_text(encoding="utf-8")
    assert "AUTRE" not in text          # une cellule remplie n'est jamais ecrasee
    assert "Eins" in text               # une cellule vide est completee
    assert "Un" in text


def test_remember_adds_a_missing_language_column(tmp_path, monkeypatch):
    corpus = tmp_path / "corpus"
    _write_csv(corpus, "Dialogues.csv", "KEY,English\nDlg1,Hello\n")
    monkeypatch.setattr("core.settings.get_corpus_trad_dir", lambda: str(corpus))
    trad_corpus.remember("dialogues", "Dlg1", {"Français": "Bonjour"})
    text = (corpus / "Dialogues.csv").read_text(encoding="utf-8")
    assert text.splitlines()[0] == "KEY,English,Français"
    assert "Dlg1,Hello,Bonjour" in text


def test_remember_ignores_an_unknown_kind(tmp_path, monkeypatch):
    monkeypatch.setattr("core.settings.get_corpus_trad_dir", lambda: str(tmp_path))
    assert trad_corpus.remember("inconnu", "k", {"Français": "x"}) is None


def test_personal_dir_falls_back_to_the_home_corpus(monkeypatch):
    monkeypatch.setattr("core.settings.get_corpus_trad_dir", lambda: "")
    assert trad_corpus.personal_dir() == (
        Path.home() / ".empyrion_editor" / "corpus")
    monkeypatch.setattr("core.settings.get_corpus_trad_dir", lambda: "C:/corpus")
    assert trad_corpus.personal_dir() == Path("C:/corpus")


def test_translation_validee_est_archivee_dans_le_corpus(qapp, tmp_path, monkeypatch):
    """Une traduction IA VALIDEE sur une cle inconnue est ecrite dans le
    corpus perso (cle ajoutee), puis servie sans IA au tour suivant."""
    corpus = tmp_path / "corpus"
    monkeypatch.setattr("core.settings.get_corpus_trad_dir", lambda: str(corpus))
    import gui.csv_edit_widget as W
    from gui.theme import apply_theme
    apply_theme(qapp)
    path = tmp_path / "Localization.csv"
    path.write_text("KEY,English,Français\r\nbkiNew,New Token,\r\n",
                    encoding="utf-8", newline="")
    widget = W.CsvEditWidget(path, editable=True)

    monkeypatch.setattr(W.translation, "is_available", lambda: True)
    monkeypatch.setattr(W.translation, "translate_text_with_source",
                        lambda text, target=None: ("Jeton neuf", "auto"))
    monkeypatch.setattr(W.translation_memory, "store", lambda *a, **k: None)
    monkeypatch.setattr("core.glossary.add_entry", lambda *a, **k: None)

    class _Dialog:
        accepted_replace = True
        def __init__(self, *args, **kwargs):
            pass
        def exec(self):
            return 1                     # QDialog.Accepted
        def result_text(self):
            return "Jeton neuf"

    monkeypatch.setattr(W, "TranslationResultDialog", _Dialog)
    widget._translate_single_cell(widget.table.item(0, 1), "New Token",
                                 "fr", "Français")

    written = (corpus / "Localization.csv").read_text(encoding="utf-8")
    assert "bkiNew,New Token,Jeton neuf" in written
    assert widget._corpus_value(0, "fr", "Français") == "Jeton neuf"


# ------------------------------------ en-tetes mojibake ('FranГ§ais', 12/09)

MOJI = "Fran" + "\u0413\u00a7" + "ais"        # ce que donne 'Français' relu en CP1251


def test_mojibake_header_still_matches_the_corpus(tmp_path, monkeypatch):
    """Un CSV d'origine russe porte 'FranГ§ais' : la colonne doit quand meme
    etre appariee au corpus (sinon l'import ne remplit rien en silence)."""
    from types import SimpleNamespace
    corpus = tmp_path / "corpus"
    _write_csv(corpus, "Localization.csv", HEADER + "k1,One,Un,Ein\n")
    monkeypatch.setattr("core.settings.get_corpus_trad_dir", lambda: str(corpus))
    doc = SimpleNamespace(header=["KEY", "English", MOJI, "Deutsch"],
                          rows=[["k1", "One", "", ""]])
    filled = trad_corpus.fill_document(doc, "localization")
    assert doc.rows[0][2] == "Un"            # accent mojibake apparié
    assert (0, 2) in filled


def test_remember_never_writes_a_mojibake_column(tmp_path, monkeypatch):
    """A l'ecriture, l'en-tete est repare : le corpus ne stocke jamais
    'FranГ§ais' (ce serait un libelle mort pour tous les autres fichiers)."""
    corpus = tmp_path / "corpus"
    monkeypatch.setattr("core.settings.get_corpus_trad_dir", lambda: str(corpus))
    trad_corpus.remember("localization", "k2", {MOJI: "Deux"},
                         header=["KEY", "English", MOJI])
    text = (corpus / "Localization.csv").read_text(encoding="utf-8")
    assert text.splitlines()[0] == "KEY,English,Français"
    assert "k2,,Deux" in text   # seule la colonne fournie est remplie
    assert MOJI not in text


def test_remember_repairs_the_header_of_an_existing_corpus_file(tmp_path, monkeypatch):
    """Un corpus deja ecrit avec 'FranГ§ais' est remis d'aplomb a la premiere
    ecriture, sans perdre ses lignes."""
    corpus = tmp_path / "corpus"
    _write_csv(corpus, "PDA.csv", "KEY,English," + MOJI + "\np1,Title,Titre\n")
    monkeypatch.setattr("core.settings.get_corpus_trad_dir", lambda: str(corpus))
    trad_corpus.remember("pda", "p2", {"Français": "Deuxieme titre"})
    text = (corpus / "PDA.csv").read_text(encoding="utf-8")
    assert text.splitlines()[0] == "KEY,English,Français"
    assert "p1,Title,Titre" in text
    assert "p2,,Deuxieme titre" in text


# --------------------------- remontee manuelle dans le corpus (demande 12/11)

def test_harvest_reports_what_would_change(tmp_path, monkeypatch):
    """Le bilan annonce cles nouvelles / cellules ajoutees / valeurs
    remplacees, sans rien ecrire : l'utilisateur decide ensuite."""
    corpus = tmp_path / "corpus"
    _write_csv(corpus, "Localization.csv",
               HEADER + "k1,One,Un,Eins\n")
    monkeypatch.setattr("core.settings.get_corpus_trad_dir", lambda: str(corpus))
    header = ["KEY", "English", "Français", "Deutsch"]
    rows = [["k1", "One", "Un corrige", "Eins"],     # valeur FR corrigee
            ["k2", "Two", "Deux", ""]]               # cle nouvelle
    entries, report = trad_corpus.harvest("localization", header, rows)
    assert set(entries) == {"k1", "k2"}
    assert report == {"new_keys": 1, "added": 2, "changed": 1}
    # rien n'a ete ecrit
    assert "corrige" not in (corpus / "Localization.csv").read_text(
        encoding="utf-8")


def test_remember_many_overwrite_replaces_a_value(tmp_path, monkeypatch):
    corpus = tmp_path / "corpus"
    _write_csv(corpus, "Localization.csv", HEADER + "k1,One,Un,Eins\n")
    monkeypatch.setattr("core.settings.get_corpus_trad_dir", lambda: str(corpus))
    trad_corpus.remember_many("localization",
                              {"k1": {"Français": "Un corrige"}},
                              overwrite=True)
    assert trad_corpus.lookup("localization", "k1")["Français"] == "Un corrige"
    # sans overwrite : la reference est conservee
    trad_corpus.remember("localization", "k1", {"Français": "Encore autre"})
    assert trad_corpus.lookup("localization", "k1")["Français"] == "Un corrige"


def test_harvest_button_updates_the_corpus(qapp, tmp_path, monkeypatch):
    """Une cellule corrigee a la main remonte dans le corpus APRES
    confirmation, et seulement la."""
    from PyQt6.QtWidgets import QMessageBox

    import gui.csv_edit_widget as W
    from gui.theme import apply_theme
    apply_theme(qapp)
    corpus = tmp_path / "corpus"
    _write_csv(corpus, "Localization.csv", HEADER + "k1,One,Un,Eins\n")
    monkeypatch.setattr("core.settings.get_corpus_trad_dir", lambda: str(corpus))
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Yes)

    path = tmp_path / "scenario" / "Localization.csv"
    path.parent.mkdir()
    path.write_text("KEY,English,Français,Deutsch\r\nk1,One,Un,Eins\r\n",
                    encoding="utf-8", newline="")
    widget = W.CsvEditWidget(path, editable=True)
    widget.table.item(0, 2).setText("Un corrigé")

    widget._harvest_corpus()

    assert trad_corpus.lookup("localization", "k1")["Français"] == "Un corrigé"
    assert trad_corpus.lookup("localization", "k1")["Deutsch"] == "Eins"


def test_harvest_button_refused_writes_nothing(qapp, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    import gui.csv_edit_widget as W
    from gui.theme import apply_theme
    apply_theme(qapp)
    corpus = tmp_path / "corpus"
    _write_csv(corpus, "Localization.csv", HEADER + "k1,One,Un,Eins\n")
    monkeypatch.setattr("core.settings.get_corpus_trad_dir", lambda: str(corpus))
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.No)
    path = tmp_path / "scenario" / "Localization.csv"
    path.parent.mkdir()
    path.write_text("KEY,English,Français,Deutsch\r\nk1,One,Autre,Eins\r\n",
                    encoding="utf-8", newline="")
    widget = W.CsvEditWidget(path, editable=True)
    widget._harvest_corpus()
    assert trad_corpus.lookup("localization", "k1")["Français"] == "Un"


# ------------------------- sauvegarde avant ecriture du corpus (12/11)

def test_overwrite_always_backs_up_the_corpus_file(tmp_path, monkeypatch):
    """Un ecrasement de reference est TOUJOURS sauvegarde, meme si une copie
    recente existe : c'est le seul cas ou une valeur est perdue."""
    corpus = tmp_path / "corpus"
    _write_csv(corpus, "Localization.csv", HEADER + "k1,One,Un,Eins\n")
    monkeypatch.setattr("core.settings.get_corpus_trad_dir", lambda: str(corpus))
    monkeypatch.setattr(trad_corpus, "_recent_backup", lambda path: True)
    calls = []
    monkeypatch.setattr("core.fsutil.central_backup",
                        lambda path, kind="sectors": calls.append((path, kind)))
    trad_corpus.remember_many("localization", {"k1": {"Français": "Corrige"}},
                              overwrite=True)
    assert calls and calls[0][1] == "corpus"
    assert calls[0][0].name == "Localization.csv"


def test_append_does_not_back_up_when_a_recent_copy_exists(tmp_path, monkeypatch):
    """Un ajout de cle ne perd rien : une seule copie par heure suffit
    (sinon un CSV de plusieurs Mo serait dupé a chaque traduction)."""
    corpus = tmp_path / "corpus"
    _write_csv(corpus, "Localization.csv", HEADER + "k1,One,Un,Eins\n")
    monkeypatch.setattr("core.settings.get_corpus_trad_dir", lambda: str(corpus))
    monkeypatch.setattr(trad_corpus, "_recent_backup", lambda path: True)
    calls = []
    monkeypatch.setattr("core.fsutil.central_backup",
                        lambda path, kind="sectors": calls.append(kind))
    trad_corpus.remember("localization", "k2", {"Français": "Deux"})
    assert calls == []


def test_first_write_of_a_new_corpus_file_has_nothing_to_back_up(tmp_path,
                                                                monkeypatch):
    monkeypatch.setattr("core.settings.get_corpus_trad_dir",
                        lambda: str(tmp_path / "corpus"))
    calls = []
    monkeypatch.setattr("core.fsutil.central_backup",
                        lambda path, kind="sectors": calls.append(kind))
    trad_corpus.remember("localization", "k1", {"Français": "Un"})
    assert calls == []
