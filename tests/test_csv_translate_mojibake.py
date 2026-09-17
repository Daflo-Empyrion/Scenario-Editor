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

"""Bug vecu 12/09/2026 : traduction d'une cellule EN vers FR dans un CSV
dont l'en-tete de la colonne francaise est 'double-encode' (UTF-8 lu en
CP1251 : 'Français' -> 'FranГ§ais', cas reel atlantis/Extras/PDA/PDA.csv,
scenario d'origine russe) -- la colonne n'etait pas reconnue et la
traduction ecrasait la cellule source, la cellule FR restant vide.
Fix : reparation mojibake dans le matching des en-tetes + avertissement
explicite dans le dialogue quand aucune colonne cible n'est trouvee."""

from PyQt6.QtWidgets import QDialog

from core.translation import _normalize, find_language_aliases, repair_mojibake

# En-tete EXACT du fichier reel (octets verifies au diagnostic).
MOJIBAKE_HEADER = "KEY,English,Deutsch,Fran\u0413\u00a7ais,Italiano,Spanish"


def test_repair_mojibake_repairs_real_header():
    assert repair_mojibake("Fran\u0413\u00a7ais") == "Français"


def test_repair_mojibake_leaves_clean_text_unchanged():
    for clean in ("Français", "Francais", "English", "", "Deutsch"):
        assert repair_mojibake(clean) == clean


def test_repair_mojibake_keeps_legitimate_cyrillic():
    # Texte russe AUTHENTIQUE : le re-encodage CP1251 -> UTF-8 echoue, la
    # chaine doit revenir intacte (jamais d'alteration de contenu reel).
    for legit in ("Привет мир", "Russian: Тест"):
        assert repair_mojibake(legit) == legit


def test_mojibake_header_now_matches_fr_aliases():
    repaired = _normalize(repair_mojibake("Fran\u0413\u00a7ais"))
    assert repaired in find_language_aliases("fr", "Francais")


def _make_widget(qapp, tmp_path, header: str):
    from gui.theme import apply_theme
    from gui.csv_edit_widget import CsvEditWidget
    apply_theme(qapp)
    path = tmp_path / "PDA.csv"
    path.write_text(f"{header}\r\npda_1,Hello world,\r\n",
                    encoding="utf-8", newline="")
    return CsvEditWidget(path, editable=True)


def test_find_language_column_recognizes_mojibake_header(qapp, tmp_path):
    widget = _make_widget(qapp, tmp_path, MOJIBAKE_HEADER)
    assert widget._find_language_column("fr", "Francais") == 3


def test_find_language_column_still_finds_clean_headers(qapp, tmp_path):
    widget = _make_widget(qapp, tmp_path, "KEY,English,Français,Deutsch")
    assert widget._find_language_column("fr", "Francais") == 2
    assert widget._find_language_column("en", "Anglais") == 1


def test_translate_single_cell_fills_mojibake_column(qapp, tmp_path, monkeypatch):
    """Le flux complet : cellule EN -> Traduire vers FR -> la traduction doit
    aller dans la colonne 'FranГ§ais' (mojibake), la cellule EN restant intacte."""
    from core import translation
    from gui.csv_edit_widget import CsvEditWidget, TranslationResultDialog

    widget = _make_widget(qapp, tmp_path, MOJIBAKE_HEADER)
    monkeypatch.setattr(translation, "is_available", lambda: True)
    monkeypatch.setattr(translation, "translate_text",
                        lambda text, target, **kwargs: "Bonjour le monde")

    def fake_dialog_exec(self):
        self.accepted_replace = True
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(TranslationResultDialog, "exec", fake_dialog_exec)

    source_item = widget.table.item(0, 1)
    widget._translate_single_cell(source_item, source_item.text(), "fr", "Francais")

    assert widget.table.item(0, 1).text() == "Hello world"  # source intacte
    assert widget.table.item(0, 3).text() == "Bonjour le monde"  # colonne FR mojibake


def test_translate_dialog_warns_when_no_target_column(qapp, tmp_path, monkeypatch):
    """Sans aucune colonne FR reconnaissable, le dialogue doit AFFICHER un
    avertissement (ne plus jamais ecraser la cellule source en silence)."""
    from core import translation
    from gui.csv_edit_widget import CsvEditWidget, TranslationResultDialog

    widget = _make_widget(qapp, tmp_path, "KEY,English,Custom")
    monkeypatch.setattr(translation, "is_available", lambda: True)
    monkeypatch.setattr(translation, "translate_text",
                        lambda text, target, **kwargs: "Bonjour le monde")

    captured = {}
    original_init = TranslationResultDialog.__init__

    def spy_init(self, original, translated, parent=None,
                 destination_label=None, destination_warning=None):
        captured["warning"] = destination_warning
        original_init(self, original, translated, parent,
                      destination_label=destination_label,
                      destination_warning=destination_warning)
    monkeypatch.setattr(TranslationResultDialog, "__init__", spy_init)

    def fake_dialog_exec(self):
        self.accepted_replace = True
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(TranslationResultDialog, "exec", fake_dialog_exec)

    source_item = widget.table.item(0, 1)
    widget._translate_single_cell(source_item, source_item.text(), "fr", "Francais")

    assert captured["warning"]  # avertissement affiche, quelle que soit la langue UI
    # comportement de repli conserve : la cellule source est remplacee
    assert widget.table.item(0, 1).text() == "Bonjour le monde"
