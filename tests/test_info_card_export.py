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

"""Tests de l'export Markdown de la fiche d'information (ajoute apres l'audit
du 30/08/2026) : rendu pur (card_to_markdown, sans Qt) et parcours complet du
bouton d'export de la fiche affichee (dialogue fichier simule, ecriture reelle
sur disque)."""
from pathlib import Path

import pytest

from core.block_info_card import (
    BlockInfoCard, InfoCardField, InfoCardIngredient, card_to_markdown,
)


def _sample_card() -> BlockInfoCard:
    return BlockInfoCard(
        title="<b>Constructeur portable</b>",
        icon_key="SurvC",
        root_identity="SurvC",
        description_html="Un <u>constructeur</u> de base.<br>Ligne deux.",
        stat_fields=[
            InfoCardField(label="Hitpoints", value="1200",
                          source_key="HitPoints", source_raw_value="1200"),
            InfoCardField(label="Mass", value="420", source_key="Mass",
                          source_raw_value="420"),
        ],
        unlock_fields=[
            InfoCardField(label="Niveau", value="7", source_key="UnlockLevel",
                          source_raw_value="7"),
        ],
        crafting_header="Fabrication",
        input_items_label="Ingrédients",
        ingredients=[InfoCardIngredient(name="Plaque en acier", quantity="5")],
        output_count_label="Quantité produite",
        output_count_value="1",
        market_price=InfoCardField(label="Prix du marché", value="1 234"),
    )


def test_card_to_markdown_full_structure():
    md = card_to_markdown(_sample_card())
    assert md.startswith("# Constructeur portable\n")
    assert "Un constructeur de base.\nLigne deux." in md   # HTML depouille, <br> -> retour ligne
    assert "- **Hitpoints** : 1200" in md
    assert "- **Mass** : 420" in md
    assert "- **Niveau** : 7" in md
    assert "## Fabrication" in md
    assert "**Ingrédients**" in md
    assert "- Plaque en acier : 5" in md
    assert "- **Quantité produite** : 1" in md
    assert "- **Prix du marché** : 1 234" in md
    assert md.endswith("\n")
    assert not md.endswith("\n\n")  # pas de lignes vides traînantes


def test_card_to_markdown_minimal_card():
    card = BlockInfoCard(title="BlocNu", icon_key="BlocNu", root_identity="BlocNu")
    md = card_to_markdown(card)
    assert md == "# BlocNu\n"


def test_card_to_markdown_never_leaks_html_tags():
    md = card_to_markdown(_sample_card())
    for tag in ("<b>", "</b>", "<u>", "<u/>", "</u>", "<br>", "<span"):
        assert tag not in md


def test_export_button_writes_selected_file(qapp, tmp_path, monkeypatch):
    """Parcours reel : fiche affichee -> clic export -> dialogue fichier simule
    -> fichier Markdown ecrit sur disque avec le rendu de la fiche."""
    from gui.theme import apply_theme
    from gui.block_info_card_widget import BlockInfoCardWidget
    apply_theme(qapp)

    widget = BlockInfoCardWidget()
    card = _sample_card()
    widget.show_card("SurvC", card, None)

    target = tmp_path / "fiche.md"
    monkeypatch.setattr(
        "gui.results_window_helpers.QFileDialog.getSaveFileName",
        staticmethod(lambda *a, **k: (str(target), "Markdown (*.md)")))
    # La confirmation de fin d'export est une QMessageBox modale : simulee
    # (sinon elle bloquerait le test en attente d'un clic).
    monkeypatch.setattr(
        "gui.results_window_helpers.QMessageBox.information",
        staticmethod(lambda *a, **k: None))
    widget.btn_export.click()

    assert target.exists()
    assert target.read_text(encoding="utf-8") == card_to_markdown(card)
    widget.close()


def test_export_button_without_shown_card_does_nothing(qapp, monkeypatch):
    from gui.theme import apply_theme
    from gui.block_info_card_widget import BlockInfoCardWidget
    apply_theme(qapp)

    widget = BlockInfoCardWidget()
    monkeypatch.setattr(
        "gui.results_window_helpers.QFileDialog.getSaveFileName",
        staticmethod(lambda *a, **k: pytest.fail("dialogue non attendu")))
    widget.btn_export.click()  # aucune fiche affichee : no-op, pas de dialogue
