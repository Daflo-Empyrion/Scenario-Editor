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

"""
Tests de CsvEditWidget (gui/csv_edit_widget.py) -- en particulier le bug
reel signale par un utilisateur (mission PDA cree, jeton brut affiche en
jeu au lieu du texte) : des lignes ajoutees a self.doc.rows APRES la
creation initiale de la table (ex: par PdaMissionDialog via
core.pda_mission.add_pda_text_entries, puis _populate_table() rappelee par
gui.main_window._open_pda_mission_dialog) disparaissaient silencieusement
a l'enregistrement, car _populate_table() ne redimensionnait jamais la
QTableWidget sur le nouveau nombre de lignes.
"""
import pytest


def test_populate_table_after_external_row_addition_keeps_new_rows(qapp, tmp_path):
    """Reproduit exactement le bug reel : le doc.rows est agrandi par du
    code EXTERIEUR au widget (comme le fait PdaMissionDialog), puis
    _populate_table() est rappelee -- les nouvelles lignes doivent survivre
    a un save()."""
    from gui.theme import apply_theme
    from gui.csv_edit_widget import CsvEditWidget
    apply_theme(qapp)

    path = tmp_path / "PDA.csv"
    path.write_text("KEY,English,Français\r\npda_old1,Old title,Ancien titre\r\n",
                     encoding="utf-8", newline="")

    widget = CsvEditWidget(path, editable=True)
    assert widget.table.rowCount() == 1

    # Simule exactement ce que fait core.pda_mission.add_pda_text_entries :
    # ajout direct de nouvelles lignes a doc.rows, sans passer par la table.
    widget.doc.rows.append(["pda_new1", "New title", "Nouveau titre"])
    widget.doc.rows.append(["pda_new2", "New description", "Nouvelle description"])

    # Simule ce que fait gui.main_window._open_pda_mission_dialog juste apres
    # la fermeture (acceptee) du dialogue de mission.
    widget._populate_table()
    assert widget.table.rowCount() == 3

    widget.save()

    saved_content = path.read_text(encoding="utf-8")
    assert "pda_new1" in saved_content
    assert "pda_new2" in saved_content
    assert "New title" in saved_content
    assert "pda_old1" in saved_content  # l'ancienne ligne doit rester intacte


def test_populate_table_after_external_row_removal_shrinks_table(qapp, tmp_path):
    """Symetrique : si doc.rows est REDUIT depuis l'exterieur, la table doit
    aussi retrecir (sinon d'anciennes lignes fantomes resteraient visibles
    et seraient re-sauvegardees a tort)."""
    from gui.theme import apply_theme
    from gui.csv_edit_widget import CsvEditWidget
    apply_theme(qapp)

    path = tmp_path / "test.csv"
    path.write_text("KEY,English\r\nrow1,A\r\nrow2,B\r\nrow3,C\r\n",
                     encoding="utf-8", newline="")

    widget = CsvEditWidget(path, editable=True)
    assert widget.table.rowCount() == 3

    widget.doc.rows = widget.doc.rows[:1]
    widget._populate_table()
    assert widget.table.rowCount() == 1

    widget.save()
    saved_content = path.read_text(encoding="utf-8")
    assert "row2" not in saved_content
    assert "row3" not in saved_content
    assert "row1" in saved_content


def test_pda_mission_creation_survives_csv_save_roundtrip(qapp, tmp_path):
    """Test d'integration bout-en-bout du scenario reel rapporte : creation
    d'une mission PDA puis sauvegarde de l'onglet PDA.csv -- le texte doit
    etre lisible dans le fichier final, pas juste le jeton brut."""
    from gui.theme import apply_theme
    from gui.csv_edit_widget import CsvEditWidget
    from core.pda_mission import add_pda_text_entries
    apply_theme(qapp)

    fixtures_dir = __import__("pathlib").Path(__file__).parent / "fixtures" / "pda_scenario"
    csv_path = fixtures_dir / "PDA.csv"

    # Copie de travail du CSV fixture dans un repertoire temporaire (jamais
    # ecrire dans tests/fixtures).
    import shutil
    work_csv = tmp_path / "PDA.csv"
    shutil.copy(csv_path, work_csv)

    csv_widget = CsvEditWidget(work_csv, editable=True)
    before_rows = csv_widget.table.rowCount()

    add_pda_text_entries(csv_widget.doc, [
        ("pda_testTitle1", "Test Mission Title", "Titre de mission de test"),
        ("pda_testDesc1", "Test Mission Description", "Description de mission de test"),
    ])
    csv_widget._populate_table()
    assert csv_widget.table.rowCount() == before_rows + 2

    csv_widget.save()

    saved_content = work_csv.read_text(encoding="utf-8")
    assert "pda_testTitle1" in saved_content
    assert "Test Mission Title" in saved_content
    assert "Titre de mission de test" in saved_content


def test_repair_headers_action_fixes_mojibake_headers(qapp, tmp_path, monkeypatch):
    """CSV d'origine russe : l'en-tete affiche 'FranГ§ais'. L'action le repare
    en memoire (bouton visible seulement dans ce cas), marque le document
    modifie, et save() ecrit le bon libelle."""
    from PyQt6.QtWidgets import QMessageBox

    import gui.csv_edit_widget as W
    from gui.theme import apply_theme
    apply_theme(qapp)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)

    moji = "Fran" + "\u0413\u00a7" + "ais"
    path = tmp_path / "Localization.csv"
    path.write_text("KEY,English," + moji + "\r\nk1,One,Un\r\n",
                    encoding="utf-8", newline="")

    widget = W.CsvEditWidget(path, editable=True)
    assert widget._mojibake_columns() == [2]
    assert widget.table.horizontalHeaderItem(2).text() == moji
    from PyQt6.QtWidgets import QPushButton
    assert any(b.text() == W.t("btn.repair_headers")
               for b in widget.findChildren(QPushButton)), "bouton absent"

    widget._repair_headers()

    assert widget.doc.header[2] == "Français"
    assert widget.table.horizontalHeaderItem(2).text() == "Français"
    assert widget.is_modified()

    widget.save()
    assert "Français" in path.read_text(encoding="utf-8")


def test_repair_headers_action_is_a_no_op_without_mojibake(qapp, tmp_path,
                                                          monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    import gui.csv_edit_widget as W
    from gui.theme import apply_theme
    apply_theme(qapp)
    seen = []
    monkeypatch.setattr(QMessageBox, "information",
                        lambda *a, **k: seen.append(a))
    path = tmp_path / "Localization.csv"
    path.write_text("KEY,English,Français\r\nk1,One,Un\r\n",
                    encoding="utf-8", newline="")

    widget = W.CsvEditWidget(path, editable=True)
    assert widget._mojibake_columns() == []
    widget._repair_headers()
    assert seen                                  # message « aucun en-tete abime »
    assert not widget.is_modified()
