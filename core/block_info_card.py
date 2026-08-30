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
Assemble le contenu de la fiche d'information d'un bloc/item (voir
gui/block_info_card_widget.py), reproduisant la fiche affichee EN JEU --
CONFIRME champ par champ sur un vrai BlocksConfig.ecf/Templates.ecf/
Localization.csv (session du 29/08/2026, capture d'ecran F3 fournie par
l'utilisateur pour 'Réservoir de carburant v2' = FuelTankMSLarge).

REECRIT le 29/08/2026 (retour utilisateur) -- l'ancienne liste FIXE de
proprietes affichees (HitPoints/Mass/Volume/...) en oubliait -- CONFIRME sur
le vrai FuelTankMSLarge que l'attribut ECF 'display' (present sur la MEME
ligne qu'une propriete, ex: 'HitPoints: 80, type: int, display: true')
identifie EXACTEMENT et EXHAUSTIVEMENT quelles proprietes le jeu affiche dans
cette fiche : scan generique de TOUTE propriete dont 'display' n'est pas
litteralement 'false' (inclut 'display: true' ET les valeurs speciales comme
'display: RadiationLevel', confirme sur Radiation). Seule exception confirmee
par la capture : MarketPrice a 'display: false' sur le vrai fichier mais est
neanmoins toujours affiche -- traite a part, inconditionnellement.

BBCODE : le balisage riche-texte du jeu ([c][RRGGBB]...[-][/c], [u], [sup]...)
n'apparait pas SEULEMENT dans le texte 'Info:' -- CONFIRME que les valeurs de
certaines proprietes elles-memes en contiennent (ex: AllowPlacingAt="Base,MS"
se traduit en "[c][ff7300]Base[-][/c], [c][fdff7d]CV[-][/c]" une fois chaque
code traduit via Localization.csv). _bbcode_to_html() est donc applique
SYSTEMATIQUEMENT a tout label et toute valeur affiches, pas seulement a la
description.
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .ecf.model import EcfBlock, EcfDocument, EcfProperty, block_identity
from .localization_lookup import LocalizationIndex

# Proprietes gerees a PART (sections dediees : titre/icone, description,
# deblocage, prix) -- exclues du scan generique pour ne jamais les afficher
# deux fois.
_EXCLUDED_FROM_GENERIC_SCAN = {
    "Info", "UnlockCost", "UnlockLevel", "MarketPrice", "Name", "Id",
    "CustomIcon", "TechTreeParent", "TechTreeNames",
}

# Proprietes dont la valeur est une LISTE de codes eux-memes traduisibles
# individuellement (confirme sur AllowPlacingAt="Base,MS" -> deux entrees
# 'Base'/'MS' ayant CHACUNE sa propre cle de traduction, avec balisage
# couleur integre -- voir docstring du module).
_LIST_VALUE_KEYS = {"AllowPlacingAt"}

# Suffixe d'unite simple derive de l'attribut 'formatter' de la propriete ECF
# (ex: 'Mass: 2513, formatter: Kilogram' -- confirme reel) -- PAS de
# conversion d'unite (ex: kg -> tonnes vu sur la capture) : affiche la valeur
# BRUTE du fichier avec juste un suffixe, pour ne jamais afficher un nombre
# invente/recalcule.
_FORMATTER_SUFFIX = {
    "Kilogram": " kg",
    "Liter": " L",
    "Watt": " W",
}


@dataclass
class InfoCardField:
    label: str
    value: str
    # Cle/valeur BRUTES (non traduites/formatees) de la propriete source,
    # utilisees UNIQUEMENT pour la navigation "cliquer pour modifier" (voir
    # gui/block_info_card_widget.py) -- permet de retrouver exactement la
    # bonne ligne dans le fichier via select_block_by_identity(prop_key=...,
    # prop_value=...), y compris pour un champ provenant d'un sous-bloc
    # imbrique (ex: 'Child 0' d'une arme) sans avoir a suivre explicitement
    # dans quel sous-bloc il se trouve -- ce mecanisme de recherche existe
    # deja (voir gui/ecf_edit_widget.py::_find_tree_item_with_property).
    source_key: Optional[str] = None
    source_raw_value: Optional[str] = None


@dataclass
class InfoCardIngredient:
    name: str
    quantity: str


@dataclass
class BlockInfoCard:
    title: str
    icon_key: str
    root_identity: str = ""
    description_html: Optional[str] = None
    stat_fields: List[InfoCardField] = field(default_factory=list)
    unlock_fields: List[InfoCardField] = field(default_factory=list)
    crafting_header: Optional[str] = None
    input_items_label: Optional[str] = None
    ingredients: List[InfoCardIngredient] = field(default_factory=list)
    output_count_label: Optional[str] = None
    output_count_value: Optional[str] = None
    market_price: Optional[InfoCardField] = None


def _bbcode_to_html(text: str) -> str:
    """Convertit le balisage riche-texte utilise dans Localization.csv (ex:
    '[c][00FF00]texte[-][/c]', '[u]souligne[/u]', '[sup]exposant[/sup]',
    '\\n') en HTML basique affichable par un QLabel/QTextEdit Qt -- confirme
    present a la fois dans les textes 'Info:' ET dans certaines VALEURS de
    proprietes (voir docstring du module). Applique SYSTEMATIQUEMENT a tout
    texte affiche, jamais seulement a la description. Tolerant aux balises
    couleur a 8 chiffres hexa (avec canal alpha) ET aux entrees MAL FORMEES
    rencontrees dans la vraie source du jeu (ex: bkiFuelTank contient un
    '[c][ffffffff]. ][/c]' incoherent -- ne pas planter dessus)."""
    if not text:
        return text
    html = text.replace("\\n", "<br>")
    html = re.sub(r"\[c\]\[([0-9A-Fa-f]{6,8})\]", lambda m: f'<span style="color:#{m.group(1)[:6]}">', html)
    html = html.replace("[-][/c]", "</span>")
    html = html.replace("[/c]", "</span>")  # repli pour balises mal formees dans la source
    html = html.replace("[u]", "<u>").replace("[/u]", "</u>")
    html = html.replace("[b]", "<b>").replace("[/b]", "</b>")
    html = html.replace("[i]", "<i>").replace("[/i]", "</i>")
    html = html.replace("[sup]", "<sup>").replace("[/sup]", "</sup>")
    return html


def _translate_label(key: str, loc: LocalizationIndex, language: str) -> str:
    return _bbcode_to_html(loc.get(key, language) or key)


def _format_value(key: str, raw_value: str, formatter: Optional[str],
                   loc: LocalizationIndex, language: str) -> str:
    value = raw_value.strip().strip('"')
    if key in _LIST_VALUE_KEYS:
        parts = [p.strip() for p in value.split(',') if p.strip()]
        translated = [loc.get(p, language) or p for p in parts]
        return _bbcode_to_html(", ".join(translated))
    suffix = _FORMATTER_SUFFIX.get(formatter, "") if formatter else ""
    return _bbcode_to_html(value) + suffix


def _collect_display_fields(block: EcfBlock, loc: LocalizationIndex, language: str) -> List[InfoCardField]:
    """Scan GENERIQUE, RECURSIF (voir REECRIT 29/08/2026 ci-dessous), de
    toute propriete dont l'attribut 'display' n'est pas litteralement
    'false' -- voir docstring du module pour la confirmation contre de
    vraies donnees. Ordre = ordre d'apparition dans le fichier (parcours en
    profondeur).

    REECRIT le 29/08/2026 (retour utilisateur) : un item comme AssaultRifle
    (ItemsConfig.ecf) declare ses statistiques reelles (ROF, Automatic,
    BulletSpread, Recoil, Damage, AmmoCapacity, AmmoType, ReloadDelay...)
    DANS UN SOUS-BLOC IMBRIQUE ('{ Child 0 ... }'), pas directement sur le
    bloc racine -- confirme sur le vrai fichier. L'ancien scan ne regardait
    que les enfants DIRECTS du bloc racine et manquait donc entierement ces
    donnees. Descend maintenant recursivement dans TOUT sous-bloc EcfBlock
    imbrique."""
    fields: List[InfoCardField] = []
    seen: set = set()

    def _walk(node: EcfBlock) -> None:
        for child in node.children:
            if isinstance(child, EcfBlock):
                _walk(child)
                continue
            if not isinstance(child, EcfProperty) or not child.pairs:
                continue
            main_key, main_value = child.pairs[0]
            if not main_key or main_key in _EXCLUDED_FROM_GENERIC_SCAN or main_key in seen:
                continue
            display_value = None
            formatter = None
            for k2, v2 in child.pairs:
                if k2 == 'display':
                    display_value = v2
                elif k2 == 'formatter':
                    formatter = v2
            if display_value is None or display_value.strip().lower() == 'false':
                continue
            seen.add(main_key)
            label = _translate_label(main_key, loc, language)
            value = _format_value(main_key, main_value, formatter, loc, language)
            fields.append(InfoCardField(label=label, value=value,
                                         source_key=main_key, source_raw_value=main_value))

    _walk(block)
    return fields


def _find_template(templates_doc: Optional[EcfDocument], name: str):
    if templates_doc is None:
        return None
    for b in templates_doc.iter_blocks():
        if b.kind in ("Template", "+Template") and (b.get('Name') == name or b.get_property('Name') == name):
            return b
    return None


def build_block_info_card(block: EcfBlock, loc: LocalizationIndex, language: str,
                           templates_doc: Optional[EcfDocument] = None) -> BlockInfoCard:
    """Construit la fiche d'information complete pour `block` -- voir
    docstring du module pour le detail de chaque champ et sa verification
    contre de vraies donnees."""
    name = block.get('Name') or block.get_property('Name') or ""
    title = _bbcode_to_html((loc.get(name, language) if name else None) or name)
    custom_icon = block.get_property('CustomIcon')
    icon_key = (custom_icon.strip() if custom_icon else name) or ""

    description_html = None
    info_key = block.get_property('Info')
    if info_key:
        info_text = loc.get(info_key.strip(), language)
        if info_text:
            description_html = _bbcode_to_html(info_text)

    card = BlockInfoCard(
        title=title,
        icon_key=icon_key,
        root_identity=block_identity(block) or name,
        description_html=description_html,
        stat_fields=_collect_display_fields(block, loc, language),
    )

    for key in ("UnlockCost", "UnlockLevel"):
        raw = block.get_property(key)
        if raw is not None:
            card.unlock_fields.append(InfoCardField(
                label=_translate_label(key, loc, language),
                value=_format_value(key, raw, None, loc, language),
                source_key=key, source_raw_value=raw))

    market_price_raw = block.get_property("MarketPrice")
    if market_price_raw is not None:
        card.market_price = InfoCardField(
            label=_translate_label("MarketPrice", loc, language),
            value=_format_value("MarketPrice", market_price_raw, None, loc, language),
            source_key="MarketPrice", source_raw_value=market_price_raw)

    template = _find_template(templates_doc, name)
    if template is not None:
        card.crafting_header = _translate_label("biwHeaderCrafting", loc, language)
        card.input_items_label = _translate_label("biwInputItems", loc, language)
        for child in template.children:
            if getattr(child, 'kind', None) == "Child Inputs":
                for prop in child.children:
                    for k, v in getattr(prop, 'pairs', []):
                        if k:
                            card.ingredients.append(InfoCardIngredient(
                                name=_translate_label(k, loc, language), quantity=_bbcode_to_html(v)))
        output_count = template.get_property('OutputCount')
        if output_count is not None:
            card.output_count_label = _translate_label("biwOutputCount", loc, language)
            card.output_count_value = _bbcode_to_html(output_count.strip())

    return card
