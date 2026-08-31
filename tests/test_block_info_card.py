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



def _expected_label(key: str) -> str:
    """Libelle attendu pour une cle ECF : traduction app si definie
    (cle 'ecfprop.<propriete>' -- 30/08/2026), sinon la cle brute."""
    from core.i18n import t
    i18n_key = f"ecfprop.{key}"
    label = t(i18n_key)
    return label if label != i18n_key else key


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


# --------------------------------------- blocs CREES sans attribut display
# (retour utilisateur du 30/08/2026 : la fiche d'un bloc/Template cree par
# l'application n'affichait que le nom et les ingredients -- ses proprietes
# n'ont aucun attribut 'display' et etaient toutes exclues du scan)

CREATED_TEMPLATE_TEXT = """{ Template Name: MaVariante
  CraftTime: 30
  Target: "BaseC"
  OutputCount: 2
  { Child Inputs
    SteelPlate: 5
    Electronics: 2
  }
}
"""


def _make_doc(text):
    from core.ecf.parser import parse_ecf_text
    return parse_ecf_text(text)


def test_created_template_shows_all_scalars_without_display_attr():
    """Repli 30/08/2026 : aucune propriete ne porte 'display' -> on affiche
    les proprietes du bloc (CraftTime, Target...) au lieu d'une fiche vide."""
    doc = _make_doc(CREATED_TEMPLATE_TEXT)
    template = next(doc.iter_blocks())
    card = build_block_info_card(template, _load_loc_index(), "fr")
    by_label = {f.label: f.value for f in card.stat_fields}
    assert by_label.get(_expected_label("CraftTime")) == "30"
    # 'Target' est desormais une valeur-liste : chaque code constructeur
    # est traduit individuellement (demande du 30/08/2026).
    from core.i18n import t
    basec = t("ecfprop.BaseC")
    assert by_label.get(_expected_label("Target")) == (basec if basec != "ecfprop.BaseC" else "BaseC")


def test_created_template_child_inputs_never_in_stat_fields():
    """Separation demandee le 30/08/2026 : le contenu de '{ Child Inputs }'
    vit DANS la section craft (ingredients), JAMAIS dans les statistiques."""
    doc = _make_doc(CREATED_TEMPLATE_TEXT)
    template = next(doc.iter_blocks())
    card = build_block_info_card(template, _load_loc_index(), "fr")
    all_labels = {f.label for f in card.stat_fields}
    assert "SteelPlate" not in all_labels
    assert "Electronics" not in all_labels
    # ... et la section craft les affiche bien, elle.
    assert card.crafting_header is not None
    ingredient_names = {i.name for i in card.ingredients}
    assert any("SteelPlate" in n for n in ingredient_names)


def test_created_template_output_count_in_dedicated_section_only():
    """OutputCount : section dediee 'quantite produite', jamais en doublon
    dans les statistiques."""
    doc = _make_doc(CREATED_TEMPLATE_TEXT)
    template = next(doc.iter_blocks())
    card = build_block_info_card(template, _load_loc_index(), "fr")
    assert "OutputCount" not in {f.label for f in card.stat_fields}
    assert card.output_count.value == "2"
    # Source brute conservee pour l'edition depuis la fiche (31/08/2026).
    assert card.output_count.source_key == "OutputCount"
    assert card.output_count.source_raw_value == "2"


def test_ingredients_carry_raw_source_for_editing():
    """Demande du 31/08/2026 (fiche editable) : chaque ingredient conserve la
    paire BRUTE (cle, quantite) du 'Child Inputs' du Template."""
    doc = _make_doc(CREATED_TEMPLATE_TEXT)
    template = next(doc.iter_blocks())
    card = build_block_info_card(template, _load_loc_index(), "fr")
    by_raw = {i.source_key: i.source_raw_value for i in card.ingredients}
    assert by_raw["SteelPlate"] == "5"
    assert by_raw["Electronics"] == "2"


# --------------------------------------- bascule vue COMPLETE / vue JEU
# (demande du 31/08/2026 : par defaut TOUTES les proprietes sont affichees,
# meme 'display: false' ; show_all=False retablit la fide lite F3 du jeu)

def test_complete_view_shows_display_false_by_default():
    """Vue COMPLETE (defaut 31/08/2026) : 'je veux tout voir sur la fiche' --
    une propriete 'display: false' est AFFICHEE par defaut."""
    text = """{ Template Name: X
  CraftTime: 10
  Target: "BaseC", display: false
}
"""
    doc = _make_doc(text)
    template = next(doc.iter_blocks())
    card = build_block_info_card(template, _load_loc_index(), "fr", show_all=True)
    by_label = {f.label: f.value for f in card.stat_fields}
    from core.i18n import t
    basec = t("ecfprop.BaseC")
    assert by_label.get(_expected_label("Target")) == (basec if basec != "ecfprop.BaseC" else "BaseC")
    assert by_label.get(_expected_label("CraftTime")) == "10"


def test_game_view_hides_display_false():
    """Vue JEU (show_all=False) : l'ancienne regle stricte -- 'display:
    false' masque la propriete, meme sur un bloc sans systeme display."""
    text = """{ Template Name: X
  CraftTime: 10
  Target: "BaseC", display: false
}
"""
    doc = _make_doc(text)
    template = next(doc.iter_blocks())
    card = build_block_info_card(template, _load_loc_index(), "fr", show_all=False)
    by_label = {f.label: f.value for f in card.stat_fields}
    assert _expected_label("Target") not in by_label
    assert by_label.get(_expected_label("CraftTime")) == "10"


def test_game_view_keeps_strict_rule_on_real_display_files():
    """Vue JEU (show_all=False) : des qu'UNE propriete porte 'display' (vrai
    fichier du jeu), une propriete SANS display n'est pas affichee --
    fidelite a la fiche F3 preservee dans ce mode."""
    text = """{ Template Name: Y
  CraftTime: 10, display: true
  InternalThing: whatever
}
"""
    doc = _make_doc(text)
    template = next(doc.iter_blocks())
    card = build_block_info_card(template, _load_loc_index(), "fr", show_all=False)
    by_label = {f.label: f.value for f in card.stat_fields}
    assert by_label.get(_expected_label("CraftTime")) == "10"
    assert "InternalThing" not in by_label


def test_complete_view_shows_everything_on_real_display_files():
    """Vue COMPLETE : sur le meme fichier a systeme display, les proprietes
    sans attribut ET celles en 'display: false' apparaissent toutes."""
    text = """{ Template Name: Y
  CraftTime: 10, display: true
  InternalThing: whatever
  SecretStat: 42, display: false
}
"""
    doc = _make_doc(text)
    template = next(doc.iter_blocks())
    card = build_block_info_card(template, _load_loc_index(), "fr", show_all=True)
    by_label = {f.label: f.value for f in card.stat_fields}
    assert by_label.get(_expected_label("CraftTime")) == "10"
    assert by_label.get("InternalThing") == "whatever"
    assert by_label.get("SecretStat") == "42"


def test_ecfprop_keys_actually_defined():
    """Garde : les cles ecfprop.* utilisees par le repli de traduction des
    fiches DOIVENT exister dans i18n_strings.json (sinon retour silencieux
    a la cle brute, et la fiche redevient non traduite)."""
    from core.i18n import t
    for key in ("CraftTime", "Target", "OutputCount", "BaseItem",
                "Deconstructor", "DeconOverride"):
        assert t(f"ecfprop.{key}") != f"ecfprop.{key}", f"cle ecfprop.{key} absente"


def test_target_constructor_codes_translated_individually():
    """Demande explicite du 30/08/2026 ('lie le a la fiche une bonne fois
    pour toute') : les codes de constructeurs de Target (SurvC, AdvC...)
    s'affichent traduits, un par un. Ces codes sont ABSENTS du
    Localization.csv du jeu (verifie) : le repli application ecfprop.* les
    fournit ; un scenario peut toujours les surdefinir."""
    from core.localization_lookup import _parse_csv_text, LocalizationIndex
    from core.i18n import t
    doc = _make_doc('{ Template Name: X\n  Target: "SurvC,SmallC,CodeInconnu"\n}\n')
    template = next(doc.iter_blocks())
    empty_loc = LocalizationIndex(_parse_csv_text("KEY,English,Français\n"))
    card = build_block_info_card(template, empty_loc, "fr")
    value = next(f.value for f in card.stat_fields if f.label == _expected_label("Target"))
    assert t("ecfprop.SurvC") in value      # Constructeur portable
    assert t("ecfprop.SmallC") in value     # Constructeur SV
    assert "CodeInconnu" in value  # code inconnu -> affiche brut  # inconnu -> brut


def test_target_values_still_come_from_game_localization_first():
    """Un scenario qui definit ses propres codes (Localization.csv) est
    respecte : priorite jeu, repli application ensuite."""
    from core.localization_lookup import _parse_csv_text, LocalizationIndex
    doc = _make_doc('{ Template Name: X\n  Target: "SurvC"\n}\n')
    template = next(doc.iter_blocks())
    loc = LocalizationIndex(_parse_csv_text(
        "KEY,English,Français\nSurvC,Ma Version,Mon Constructeur Perso\n"))
    card = build_block_info_card(template, loc, "fr")
    value = next(f.value for f in card.stat_fields if f.label == _expected_label("Target"))
    assert value == "Mon Constructeur Perso"
