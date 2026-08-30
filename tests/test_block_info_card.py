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
Tests de core.block_info_card -- fixtures derivees de VRAIS
BlocksConfig.ecf/Templates.ecf/Localization.csv, verifiees contre une vraie
capture d'ecran F3 fournie par l'utilisateur (session du 29/08/2026, bloc
FuelTankMSLarge = 'Réservoir de carburant v2').
"""
from pathlib import Path

from core.ecf.parser import parse_ecf_file
from core.localization_lookup import _parse_csv_text, LocalizationIndex
from core.block_info_card import build_block_info_card, _bbcode_to_html

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "block_info_card_scenario"


def _load_loc_index() -> LocalizationIndex:
    text = (FIXTURE_DIR / "Localization.csv").read_text(encoding='utf-8')
    return LocalizationIndex(_parse_csv_text(text))


def _get_block(name: str):
    doc = parse_ecf_file(FIXTURE_DIR / "BlocksConfig.ecf")
    for b in doc.iter_blocks():
        if b.get('Name') == name:
            return b
    raise AssertionError(f"bloc {name} introuvable dans la fixture")


def test_title_from_localization():
    block = _get_block("FuelTankMSLarge")
    loc = _load_loc_index()
    card = build_block_info_card(block, loc, "fr")
    assert card.title == "Réservoir de carburant v2"


def test_title_falls_back_to_name_when_no_translation():
    block = _get_block("BlockWithoutInfoOrTemplate")
    loc = _load_loc_index()
    card = build_block_info_card(block, loc, "fr")
    assert card.title == "BlockWithoutInfoOrTemplate"


def test_icon_key_defaults_to_name_without_custom_icon():
    block = _get_block("FuelTankMSLarge")
    loc = _load_loc_index()
    card = build_block_info_card(block, loc, "fr")
    assert card.icon_key == "FuelTankMSLarge"


def test_stat_fields_only_include_display_true_properties():
    block = _get_block("FuelTankMSLarge")
    loc = _load_loc_index()
    card = build_block_info_card(block, loc, "fr")
    all_labels = {f.label for f in card.stat_fields}
    assert "Points dommages" in all_labels  # HitPoints, display: true
    assert "Énergie IN" not in all_labels   # EnergyIn, ABSENT sur ce bloc reel


def test_stat_values_match_real_capture():
    block = _get_block("FuelTankMSLarge")
    loc = _load_loc_index()
    card = build_block_info_card(block, loc, "fr")
    by_label = {f.label: f.value for f in card.stat_fields}
    assert by_label["Points dommages"] == "80"
    assert by_label["CPU"] == "675"
    assert by_label["Volume contenant"] == "2700"
    assert by_label["Poids"] == "2513 kg"
    assert by_label["Dimensions (L, H, P)"] == "1,2,1"


def test_stat_fields_excludes_display_false_property():
    """MarketPrice a display:false sur le vrai fichier -- exclu du scan
    generique (gere a part, inconditionnellement, voir docstring du module)."""
    block = _get_block("FuelTankMSLarge")
    loc = _load_loc_index()
    card = build_block_info_card(block, loc, "fr")
    all_labels = {f.label for f in card.stat_fields}
    assert "Prix moyen du marché" not in all_labels


def test_stat_fields_bbcode_converted_in_value():
    """Cas reel confirme : AllowPlacingAt se traduit en valeurs contenant du
    bbcode couleur -- doit etre converti en HTML, pas laisse brut."""
    block = _get_block("FuelTankMSLarge")
    loc = _load_loc_index()
    card = build_block_info_card(block, loc, "fr")
    compatible = next(f for f in card.stat_fields if f.label == "Compatible")
    assert "[c]" not in compatible.value
    assert "<span" in compatible.value


def test_unlock_fields_present():
    block = _get_block("FuelTankMSLarge")
    loc = _load_loc_index()
    card = build_block_info_card(block, loc, "fr")
    by_label = {f.label: f.value for f in card.unlock_fields}
    assert by_label["Coût déblocage"] == "12"
    assert by_label["Niveau déblocage"] == "10"


def test_market_price_present():
    block = _get_block("FuelTankMSLarge")
    loc = _load_loc_index()
    card = build_block_info_card(block, loc, "fr")
    assert card.market_price.label == "Prix moyen du marché"
    assert card.market_price.value == "3845"


def test_market_price_none_when_absent():
    block = _get_block("BlockWithoutInfoOrTemplate")
    loc = _load_loc_index()
    card = build_block_info_card(block, loc, "fr")
    assert card.market_price is None


def test_description_none_when_info_key_missing_from_localization():
    """BlockWithoutInfoOrTemplate n'a pas de propriete Info du tout."""
    block = _get_block("BlockWithoutInfoOrTemplate")
    loc = _load_loc_index()
    card = build_block_info_card(block, loc, "fr")
    assert card.description_html is None


def test_description_present_and_converted_to_html():
    block = _get_block("FuelTankMSLarge")
    loc = _load_loc_index()
    card = build_block_info_card(block, loc, "fr")
    assert card.description_html is not None
    assert "Accès direct" in card.description_html
    assert "<span" in card.description_html  # balisage couleur converti


def test_crafting_section_matches_real_template():
    block = _get_block("FuelTankMSLarge")
    loc = _load_loc_index()
    templates_doc = parse_ecf_file(FIXTURE_DIR / "Templates.ecf")
    card = build_block_info_card(block, loc, "fr", templates_doc)

    assert card.crafting_header == "FABRICATION"
    assert card.input_items_label == "Composants requis"
    ingredients = {i.name: i.quantity for i in card.ingredients}
    assert ingredients["Composants électroniques"] == "8"
    assert ingredients["Alliage de Cobalt"] == "16"
    assert ingredients["Plaques de Titane"] == "16"
    assert ingredients["Substrat de carbone"] == "32"


def test_no_crafting_section_when_no_matching_template():
    block = _get_block("BlockWithoutInfoOrTemplate")
    loc = _load_loc_index()
    templates_doc = parse_ecf_file(FIXTURE_DIR / "Templates.ecf")
    card = build_block_info_card(block, loc, "fr", templates_doc)
    assert card.crafting_header is None
    assert card.ingredients == []


def test_no_crafting_section_when_templates_doc_not_provided():
    block = _get_block("FuelTankMSLarge")
    loc = _load_loc_index()
    card = build_block_info_card(block, loc, "fr", templates_doc=None)
    assert card.crafting_header is None


# ---------------------------------------------------------------------------
# _bbcode_to_html
# ---------------------------------------------------------------------------

def test_bbcode_color_tag_converted():
    html = _bbcode_to_html("[c][7dbeff]texte[-][/c]")
    assert html == '<span style="color:#7dbeff">texte</span>'


def test_bbcode_underline_converted():
    assert _bbcode_to_html("[u]souligne[/u]") == "<u>souligne</u>"


def test_bbcode_sup_converted():
    assert _bbcode_to_html("[sup]exposant[/sup]") == "<sup>exposant</sup>"


def test_bbcode_newline_converted():
    assert _bbcode_to_html("ligne1\\nligne2") == "ligne1<br>ligne2"


def test_bbcode_tolerates_8digit_color_and_malformed_tags():
    """Cas reel trouve dans bkiFuelTank : '[c][ffffffff]. ][/c]' -- balise
    malformee dans la source du jeu elle-meme, ne doit jamais lever
    d'exception."""
    html = _bbcode_to_html("[c][ffffffff]. ][/c]")
    assert "color:#ffffff" in html
    assert "</span>" in html


def test_bbcode_empty_string():
    assert _bbcode_to_html("") == ""
