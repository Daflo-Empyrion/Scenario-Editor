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

"""Tests du controle BBCode des CSV traduits (core/bbcode_check.py) et du
dialogue de reparation (gui/bbcode_check_dialog.py).

Regle centrale verifiee partout : la colonne anglaise fait foi ; une anomalie
deja presente dans la source n'est pas signalee, et la reparation ne retire
JAMAIS le texte (bug attrape en mise au point : la premiere version ne
reassemblait que les balises)."""
import pytest

from core.bbcode_check import (check_cell, check_table, language_columns,
                               repair_richtext, repair_text, source_column,
                               structure)


# ----------------------------------------------------------------------
# Structure
# ----------------------------------------------------------------------
def test_missing_closer_is_detected_and_closed():
    report = check_cell("[0AC9F9]Bloc Alien")
    assert report is not None
    assert "unclosed" in report.kinds
    assert report.repairable
    # adapt. 04/11 : hexa nu -> bloc [c] ouvert, ferme AVANT... ici sans \n :
    # fermeture en fin, et [-] obligatoire devant [/c] (bloc colore)
    assert report.after == "[c][0AC9F9]Bloc Alien[-][/c]"


def test_text_is_preserved_by_repair():
    """Non-regression : la reparation ne doit pas ejecter le texte."""
    assert repair_text("[c][FF4500]Texte") \
        == "[c][FF4500]Texte[-][/c]"


def test_orphan_closer_becomes_complete_block():
    """Adapt. 04/11 : hexa nu avec [-][/c] mais sans [c] : on ouvre le bloc
    plutot que retirer la fermeture orpheline (regle du correcteur externe)."""
    report = check_cell("[0AC9F9]Bloc[-][/c]")
    assert "orphan" in report.kinds
    assert report.after == "[c][0AC9F9]Bloc[-][/c]"


def test_wrong_nesting_is_reordered():
    report = check_cell("[b][u]x[/b][/u]")
    assert "nesting" in report.kinds
    assert report.after == "[b][u]x[/u][/b]"


def test_invalid_colour_is_dropped():
    report = check_cell("[ZZZZZZ]Texte")
    assert "invalid" in report.kinds
    assert report.after == "Texte"


def test_coherent_extra_tags_are_kept():
    """Retour du 31/10/2026 : une traduction qui ajoute une mise en forme
    coherente que l'anglais n'a pas ne doit NI etre signalee NI retiree."""
    assert check_cell("[b]Texte[/b]") is None
    assert check_cell("[c][FFFF00]Texte[-][/c]") is None


def test_unclosed_colour_added_by_translation_is_closed():
    """L'anglais n'a aucune balise, la traduction a ouvert une couleur : la
    fermeture manque dans la traduction, c'est donc a elle de la recevoir."""
    report = check_cell("[0AC9F9]Bloc Alien")
    assert report.after == "[c][0AC9F9]Bloc Alien[-][/c]"


def test_two_colour_blocks_with_one_closer_are_split():
    """Cas reel signale le 31/10/2026 : '[c][00FF00]A[c][FFFFFF]B[-][/c]'
    (deux ouvertures de bloc, une seule fermeture). La reparation doit
    ressortir deux blocs complets, pas empiler une fermeture de plus."""
    text = "[c][00FF00]Barre outils[c][FFFFFF] inventaire[-][/c]"
    report = check_cell(text)
    assert report.repairable
    assert report.after == ("[c][00FF00]Barre outils[-][/c]"
                            "[c][FFFFFF] inventaire[-][/c]")
    assert not structure(report.after)[1]


def test_colour_is_a_state_not_a_nested_tag():
    """Changer de couleur dans un bloc [c] est normal : ce n'est pas une
    imbrication, et rien ne doit etre signale."""
    text = "[c][FF0000]A[c][00FF00]B[-][/c]C[/c]"
    assert check_cell(text) is None
    assert check_cell("[c][00FF00]A[FFFFFF]B[-][/c]") is None


def test_true_nesting_gets_the_missing_reset():
    report = check_cell("[c][FF0000]text[/c]")
    assert report.kinds == ["nesting"]
    assert report.after == "[c][FF0000]text[-][/c]"


def test_empty_target_is_ignored():
    assert check_cell("") is None


# ----------------------------------------------------------------------
# Adaptation du correcteur externe (04/11)
# ----------------------------------------------------------------------
def test_close_inserted_before_newline():
    """La fermeture manquante doit se mettre AVANT le '\\n' litteral :
    fermee en fin de texte, le jeu prolonge la couleur sur la ligne suivante."""
    assert repair_text("[c][FF0000]Bonjour[\\n]Suite") \
        == "[c][FF0000]Bonjour[-][/c][\\n]Suite"


def test_reset_added_before_closer_of_coloured_block():
    assert repair_text("[c][00FF00]Texte[/c]") == "[c][00FF00]Texte[-][/c]"


def test_spaces_are_glued():
    assert repair_text("[c][00FF00]A[-] [/c][\\n]B") \
        == "[c][00FF00]A[-][/c][\\n]B"


def test_richtext_missing_close_is_added():
    report = check_cell("<b>Salut le monde")
    assert report is not None
    assert "richtext" in report.kinds
    assert report.after == "<b>Salut le monde</b>"


def test_richtext_crossed_nesting_is_repaired():
    report = check_cell("<b><i>x</b></i>")
    assert "richtext" in report.kinds
    assert report.after == "<b><i>x</i></b>"


def test_richtext_closed_before_newline_token():
    assert repair_richtext("<color=#ff0000>A[\\n]B") \
        == "<color=#ff0000>A</color>[\\n]B"


def test_macros_are_never_touched():
    """<DISCOUNTTEXT> est une macro du jeu : le correcteur externe la
    corrumpait en </discounttext> — jamais chez nous."""
    text = "<DISCOUNTTEXT> et a < b"
    assert repair_richtext(text) == text


def test_richtext_orphan_close_is_removed():
    assert repair_richtext("Texte</b> suite") == "Texte suite"


# ----------------------------------------------------------------------
# Colonnes de langue
# ----------------------------------------------------------------------
def test_language_columns_and_english_source():
    header = ["KEY", "English", "Français", "Deutsch"]
    assert language_columns(header) == [1, 2, 3]
    assert source_column(header, [1, 2, 3]) == 1


def test_mojibake_header_is_recognised():
    # 'Français' double-encode (scenarios d'origine russe)
    header = ["KEY", "English", "FranГ§ais"]
    assert 2 in language_columns(header)


def test_fallback_when_no_language_header():
    header = ["KEY", "Texte 1", "Texte 2"]
    assert language_columns(header) == [1, 2]
    assert source_column(header, [1, 2]) == 1


def test_check_table_can_restrict_to_one_column():
    rows = [["k1", "[0AC9F9]Alien Block[-]", "[0AC9F9]Bloc Alien", "[0AC9F9]Alien Block"]]
    header = ["KEY", "English", "Français", "Deutsch"]
    reports, source, columns = check_table(rows, header, only=[2])
    assert source == 1
    assert columns == [2]
    assert [(r, c) for r, c, _ in reports] == [(0, 2)]


def test_check_table_skips_the_source_column():
    rows = [["k1", "[0AC9F9]Alien Block[-]", "[0AC9F9]Bloc Alien"]]
    reports, source, columns = check_table(rows, ["KEY", "English", "Français"])
    assert source == 1
    assert columns == [1, 2]
    assert [(r, c) for r, c, _ in reports] == [(0, 2)]
    assert reports[0][2].after == "[c][0AC9F9]Bloc Alien[-][/c]"


# ----------------------------------------------------------------------
# Dialogue
# ----------------------------------------------------------------------
def test_dialog_applies_fixes_and_writes_backup(qapp, tmp_path, monkeypatch):
    from gui.theme import apply_theme
    from gui.csv_edit_widget import CsvEditWidget
    apply_theme(qapp)
    monkeypatch.setattr("gui.bbcode_check_dialog.info", lambda *a, **k: None)
    # sauvegarde centralisee redirigee vers tmp : jamais le vrai dossier home
    def _backup(path, kind="localization"):
        dst = path.parent / (path.stem + "-backup.bak")
        dst.write_bytes(path.read_bytes())
        return dst
    monkeypatch.setattr("gui.bbcode_check_dialog.central_backup", _backup)

    path = tmp_path / "Localization.csv"
    path.write_text("KEY,English,Français\r\n"
                    "b1,[0AC9F9]Alien Block[-],[0AC9F9]Bloc Alien\r\n",
                    encoding="utf-8", newline="")

    widget = CsvEditWidget(path, editable=True)
    from gui.bbcode_check_dialog import BbcodeCheckDialog
    dialog = BbcodeCheckDialog(widget)
    assert dialog.table.rowCount() == 1
    dialog._apply()

    saved = path.read_text(encoding="utf-8")
    assert "[c][0AC9F9]Bloc Alien[-][/c]" in saved
    assert not (tmp_path / "Localization.csv.bak").exists()   # rien a cote du CSV
    assert (tmp_path / "Localization-backup.bak").exists()
    # l'editeur garde la trace de la modification pour l'undo
    assert widget.is_modified() is False  # save() a remis le drapeau a zero


def _dialog_for(tmp_path, monkeypatch, csv_text):
    from gui.theme import apply_theme
    from gui.csv_edit_widget import CsvEditWidget
    from PyQt6.QtWidgets import QApplication
    apply_theme(QApplication.instance())
    monkeypatch.setattr("gui.bbcode_check_dialog.info", lambda *a, **k: None)
    # sauvegarde centralisee redirigee vers tmp : jamais le vrai dossier home
    def _backup(path, kind="localization"):
        dst = path.parent / (path.stem + "-backup.bak")
        dst.write_bytes(path.read_bytes())
        return dst
    monkeypatch.setattr("gui.bbcode_check_dialog.central_backup", _backup)
    path = tmp_path / "Localization.csv"
    path.write_text(csv_text, encoding="utf-8", newline="")
    widget = CsvEditWidget(path, editable=True)
    from gui.bbcode_check_dialog import BbcodeCheckDialog
    return path, widget, BbcodeCheckDialog(widget)


def test_proposal_column_is_editable_and_used(qapp, tmp_path, monkeypatch):
    """La proposition peut etre retouchee a la main : c'est le texte SAISI
    qui est applique, pas la correction calculee."""
    path, _widget, dialog = _dialog_for(
        tmp_path, monkeypatch,
        "KEY,English,Français\r\n"
        "b1,[0AC9F9]Alien Block[-],[0AC9F9]Bloc Alien\r\n")
    from PyQt6.QtCore import Qt
    assert dialog.table.item(0, 5).text() == "[c][0AC9F9]Bloc Alien[-][/c]"
    assert dialog.table.item(0, 3).text() == "[0AC9F9]Alien Block[-]"
    assert not (dialog.table.item(0, 2).flags() & Qt.ItemFlag.ItemIsEditable)
    assert not (dialog.table.item(0, 3).flags() & Qt.ItemFlag.ItemIsEditable)
    dialog.table.item(0, 5).setText("[c][0AC9F9]Bloc Alien (manuel)[-][/c]")
    dialog._apply()
    assert "[c][0AC9F9]Bloc Alien (manuel)[-][/c]" in path.read_text(encoding="utf-8")


def test_columns_are_user_resizable(qapp, tmp_path, monkeypatch):
    """Le texte long doit pouvoir etre lu en elargissant la colonne : mode
    Interactive (pas Stretch/Fixed). L'elision reste ACTIVE : ElideNone
    dessine le texte hors de la cellule et les colonnes se superposent
    (constate 31/10/2026) ; le texte complet se lit en infobulle."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QHeaderView
    nl = chr(13) + chr(10)
    _path, _widget, dialog = _dialog_for(
        tmp_path, monkeypatch,
        "KEY,English,Français" + nl
        + "b1,[0AC9F9]Alien Block[-],[0AC9F9]Bloc Alien" + nl)
    for col in range(6):
        assert dialog.table.horizontalHeader().sectionResizeMode(col) \
            == QHeaderView.ResizeMode.Interactive
    assert dialog.table.textElideMode() == Qt.TextElideMode.ElideRight
    assert dialog.table.columnWidth(3) == 380
    assert dialog.table.item(0, 3).toolTip()          # texte complet au survol
    assert dialog.table.item(0, 4).toolTip()


def test_scope_applies_only_the_selected_language(qapp, tmp_path, monkeypatch):
    """Confirmation demandee : avec une langue seule, la validation n'ecrit
    QUE cette colonne ; les autres langues restent intactes."""
    nl = chr(13) + chr(10)
    path, _widget, dialog = _dialog_for(
        tmp_path, monkeypatch,
        "KEY,English,Français,Deutsch" + nl
        + "b1,[0AC9F9]Alien Block[-],[0AC9F9]Bloc Alien,Alien Block" + nl)
    dialog.scope.setCurrentIndex(1)               # Français seulement
    dialog._apply()
    content = path.read_text(encoding="utf-8")
    assert "[c][0AC9F9]Bloc Alien[-][/c]" in content     # corrige
    assert content.splitlines()[-1].endswith("Alien Block")   # Deutsch intact


def test_orphan_closer_removed_even_without_source():
    """Standalone (02/11) : l'orphelin est retire sans regarder la source."""
    report = check_cell("[b]Texte[/b][/b]")
    assert "orphan" in report.kinds
    assert report.after == "[b]Texte[/b]"


def test_invalid_tag_dropped_without_source():
    report = check_cell("[ZZZZZZ]Texte")
    assert "invalid" in report.kinds
    assert report.after == "Texte"


def test_defect_also_in_source_is_now_repaired():
    """Changement du 02/11 : un defaut present AUSSI dans l'anglais est
    desormais signale et repare (plus de tolerance heritee)."""
    report = check_cell("[FF0000]Titre traduit[-][/c]")
    assert report is not None
    assert "orphan" in report.kinds
    assert report.repairable


def test_coherent_additions_still_not_reported():
    """Une cellule sans aucun defaut structurel reste silencieuse, meme si
    elle a plus de balises que sa source."""
    assert check_cell("[c][00FF00]A[FFFFFF]B[-][/c]") is None
