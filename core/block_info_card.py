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
cette fiche. Seule exception confirmee par la capture : MarketPrice a
'display: false' sur le vrai fichier mais est neanmoins toujours affiche --
traite a part, inconditionnellement.

DEUX MODES D'AFFICHAGE (demande explicite de l'utilisateur du 31/08/2026,
remplace l'ancienne regle figee "fidelite F3 uniquement") :
  - Vue COMPLETE (defaut) : TOUTES les proprietes sont affichees, y compris
    celles portant 'display: false' -- l'editeur veut TOUT voir pour
    equilibrer un scenario sans ouvrir le fichier.
  - Vue JEU (fidelle F3) : l'ancienne regle stricte (ce qui n'a pas
    'display' actif n'est pas affiche), utile pour comparer avec la fiche
    telle que le jeu la montre.
La bascule entre les deux vit dans gui/block_info_card_widget.py ; ce module
recoit simplement le boolen `show_all` (True = vue complete).

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
# deux fois. OutputCount : section dediee 'Quantite produite' de la zone de
# craft (ajoute le 30/08/2026, sinon duplique quand on clique un Template
# lui-meme, depuis que le repli sans 'display' inclut ses proprietes).
_EXCLUDED_FROM_GENERIC_SCAN = {
    "Info", "UnlockCost", "UnlockLevel", "MarketPrice", "Name", "Id",
    "CustomIcon", "TechTreeParent", "TechTreeNames", "OutputCount",
}

# Proprietes dont la valeur est une LISTE de codes eux-memes traduisibles
# individuellement (confirme sur AllowPlacingAt="Base,MS" -> deux entrees
# 'Base'/'MS' ayant CHACUNE sa propre cle de traduction, avec balisage
# couleur integre -- voir docstring du module). Target ajoute le 30/08/2026
# (demande explicite de l'utilisateur) : valeur "SurvC,SmallC,..." -- chaque
# code de constructeur est traduit separement.
_LIST_VALUE_KEYS = {"AllowPlacingAt", "Target"}

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
    # Cle/valeur BRUTES de l'ingredient dans la section 'Child Inputs' du
    # Template (Templates.ecf) -- indispensables depuis que la fiche est
    # EDITABLE (31/08/2026) : elles permettent de retrouver la paire exacte
    # a modifier, au meme titre que source_key/source_raw_value des
    # InfoCardField. Videntes pour un ingredient sans quantite.
    source_key: Optional[str] = None
    source_raw_value: Optional[str] = None


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
    output_count: Optional[InfoCardField] = None
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
    """Traduit le LABEL d'une propriete (la cle ECF EST la cle de traduction
    du jeu). Trois sources, dans l'ordre :
    1. Localisation du jeu (scenario d'abord, pack vanilla en repli) ;
    2. Repli APPLICATION (demande du 30/08/2026) : certaines proprietes ECF
       n'ont AUCUNE chaine UI dans le jeu (verifie dans le pack vanilla :
       'CraftTime', 'Target', 'OutputCount'... introuvables) -- l'application
       fournit ses propres libelles traduits, cles 'ecfprop.<propriete>' de
       data/i18n_strings.json ;
    3. Repli final : la cle brute (jamais d'invention)."""
    translated = loc.get(key, language)
    if translated:
        return _bbcode_to_html(translated)
    from .i18n import t
    i18n_key = f"ecfprop.{key}"
    app_label = t(i18n_key)
    if app_label != i18n_key:  # t() retourne la cle elle-meme si absente
        return _bbcode_to_html(app_label)
    return key


def _translate_value_token(token: str, loc: LocalizationIndex, language: str) -> str:
    """Traduit UN token d'une valeur-liste (ex: un code constructeur de
    Target : 'SurvC', 'AdvC'...). Priorite :
    1. Localisation du jeu (scenario puis vanilla) -- un scenario peut
       definir ses propres codes ;
    2. Repli APPLICATION (demande du 30/08/2026, 'lie a la fiche une bonne
       fois pour toute') : les codes constructeur sont documentes dans le
       glossaire Templates.ecf de l'application mais ABSENTS du
       Localization.csv du jeu (verifie : aucune ligne SurvC/AdvC/...) --
       traduits via les cles 'ecfprop.<code>' de i18n_strings.json ;
    3. Repli final : le token brut."""
    translated = loc.get(token, language)
    if translated:
        return _bbcode_to_html(translated)
    from .i18n import t
    i18n_key = f"ecfprop.{token}"
    app_label = t(i18n_key)
    if app_label != i18n_key:  # t() retourne la cle elle-meme si absente
        return app_label
    return token


def _format_value(key: str, raw_value: str, formatter: Optional[str],
                   loc: LocalizationIndex, language: str) -> str:
    value = raw_value.strip().strip('"')
    if key in _LIST_VALUE_KEYS:
        parts = [p.strip() for p in value.split(',') if p.strip()]
        translated = [_translate_value_token(p, loc, language) for p in parts]
        return ", ".join(translated)
    suffix = _FORMATTER_SUFFIX.get(formatter, "") if formatter else ""
    return _bbcode_to_html(value) + suffix


def _collect_display_fields(block: EcfBlock, loc: LocalizationIndex, language: str,
                             show_all: bool = True) -> List[InfoCardField]:
    """Scan GENERIQUE, RECURSIF (voir REECRIT 29/08/2026 ci-dessous), des
    proprietes a afficher, selon le mode choisi par `show_all` :
      - show_all=True (VUE COMPLETE, defaut depuis le 31/08/2026) : TOUTES
        les proprietes, y compris celles portant 'display: false' -- demande
        explicite de l'utilisateur ("je veux tout voir sur la fiche").
      - show_all=False (VUE JEU) : l'ancienne regle stricte -- uniquement les
        proprietes dont l'attribut 'display' n'est pas litteralement
        'false', pour rester fidele a la fiche F3 en jeu (voir docstring du
        module pour la confirmation contre de vraies donnees).
    Ordre = ordre d'apparition dans le fichier (parcours en profondeur).

    REECRIT le 29/08/2026 (retour utilisateur) : un item comme AssaultRifle
    (ItemsConfig.ecf) declare ses statistiques reelles (ROF, Automatic,
    BulletSpread, Recoil, Damage, AmmoCapacity, AmmoType, ReloadDelay...)
    DANS UN SOUS-BLOC IMBRIQUE ('{ Child 0 ... }'), pas directement sur le
    bloc racine -- confirme sur le vrai fichier. L'ancien scan ne regardait
    que les enfants DIRECTS du bloc racine et manquait donc entierement ces
    donnees. Descend maintenant recursivement dans TOUT sous-bloc EcfBlock
    imbrique, SAUF '{ Child Inputs }' (complement du 30/08/2026, retour
    utilisateur) : le contenu d'un Template vit dans une section CRAFTING
    dediee (voir build_block_info_card), jamais melange aux proprietes du
    bloc -- dans un sens comme dans l'autre.

    REPLI sans attribut 'display' (ajout du 30/08/2026, retour utilisateur,
    mode VUE JEU uniquement) : un bloc/item/Template VIENT D'ETRE CREE par
    l'application (creation guidee, duplication, fusion...) -> ses
    proprietes n'ont AUCUN attribut 'display', l'ancienne regle 'display
    present et != false' les excluait toutes et la fiche n'affichait que le
    nom et les ingredients de craft. Si AUCUNE propriete du bloc
    (recursivement) ne porte d'attribut 'display', le fichier n'utilise
    clairement pas ce systeme : on affiche alors TOUTES les proprietes (hors
    exclusions ci-dessus). Des qu'UNE SEULE propriete porte un 'display', on
    est sur un vrai fichier du jeu : regle stricte d'origine, pour rester
    fidele a la fiche F3 en jeu."""
    fields: List[InfoCardField] = []
    seen: set = set()
    uses_display_system = _block_uses_display_system(block)

    def _walk(node: EcfBlock) -> None:
        for child in node.children:
            if isinstance(child, EcfBlock):
                if getattr(child, 'kind', None) == 'Child Inputs':
                    continue  # section CRAFTING dediee -- jamais ici
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
            if not show_all:  # mode VUE JEU : l'attribut 'display' filtre
                if display_value is None:
                    if uses_display_system:
                        continue
                elif display_value.strip().lower() == 'false':
                    continue
            seen.add(main_key)
            label = _translate_label(main_key, loc, language)
            value = _format_value(main_key, main_value, formatter, loc, language)
            fields.append(InfoCardField(label=label, value=value,
                                         source_key=main_key, source_raw_value=main_value))

    _walk(block)
    return fields


def _block_uses_display_system(block: EcfBlock) -> bool:
    """True si au moins UNE propriete du bloc (recursivement) porte un
    attribut 'display' ACTIF (valeur differente de 'false') -- dans ce cas
    on est sur un vrai fichier du jeu et la regle stricte s'applique (ce
    qui n'a pas 'display' n'est PAS affiche en jeu, confirme par la capture
    F3 du 29/08/2026). False pour un bloc cree par l'application, dont
    aucune propriete n'a cet attribut. Un 'display: false' ISOLE ne compte
    pas comme une utilisation du systeme : il cache sa propre propriete
    (intention explicite) mais ne doit pas masquer toutes les autres."""
    def _walk(node: EcfBlock) -> bool:
        for child in node.children:
            if isinstance(child, EcfBlock):
                if _walk(child):
                    return True
            elif isinstance(child, EcfProperty):
                for k2, v2 in child.pairs:
                    if k2 == 'display' and v2.strip().lower() != 'false':
                        return True
        return False
    return _walk(block)


def _find_template(templates_doc: Optional[EcfDocument], name: str):
    if templates_doc is None:
        return None
    for b in templates_doc.iter_blocks():
        if b.kind in ("Template", "+Template") and (b.get('Name') == name or b.get_property('Name') == name):
            return b
    return None


def _strip_html(html: str) -> str:
    """Retire les balises HTML produites par _bbcode_to_html pour un rendu
    texte brut (les <br> deviennent de vrais retours a la ligne)."""
    text = re.sub(r"<br\s*/?>", "\n", html)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def card_to_markdown(card: BlockInfoCard) -> str:
    """Rend la fiche en Markdown, MIROIR de ce que show_card() affiche (meme
    ordre : description, statistiques, deblocage, fabrication, prix du
    marche). Les libelles/valeurs sont deja traduits et formates dans la
    fiche au moment de sa construction -- aucune nouvelle traduction ni
    mise en forme ici, on deplace seulement le rendu vers un fichier."""
    lines: List[str] = []
    title = _strip_html(card.title) if card.title else card.root_identity
    lines.append(f"# {title}")
    lines.append("")
    if card.description_html:
        lines.append(_strip_html(card.description_html))
        lines.append("")
    for f in card.stat_fields:
        lines.append(f"- **{_strip_html(f.label)}** : {_strip_html(f.value)}")
    if card.stat_fields:
        lines.append("")
    for f in card.unlock_fields:
        lines.append(f"- **{_strip_html(f.label)}** : {_strip_html(f.value)}")
    if card.unlock_fields:
        lines.append("")
    if card.crafting_header:
        lines.append(f"## {_strip_html(card.crafting_header)}")
        lines.append("")
        if card.input_items_label and card.ingredients:
            lines.append(f"**{_strip_html(card.input_items_label)}**")
            lines.append("")
            for ing in card.ingredients:
                lines.append(f"- {ing.name} : {ing.quantity}")
            lines.append("")
        if card.output_count is not None:
            lines.append(f"- **{_strip_html(card.output_count.label or '')}** : "
                         f"{_strip_html(card.output_count.value)}")
            lines.append("")
    if card.market_price:
        lines.append(f"- **{_strip_html(card.market_price.label)}** : "
                     f"{_strip_html(card.market_price.value)}")
        lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def build_block_info_card(block: EcfBlock, loc: LocalizationIndex, language: str,
                           templates_doc: Optional[EcfDocument] = None,
                           show_all: bool = True) -> BlockInfoCard:
    """Construit la fiche d'information complete pour `block` -- voir
    docstring du module pour le detail de chaque champ et sa verification
    contre de vraies donnees. `show_all=True` (defaut depuis le 31/08/2026)
    = vue COMPLETE (toutes les proprietes, meme 'display: false') ;
    False = vue JEU fidele a la fiche F3."""
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
        stat_fields=_collect_display_fields(block, loc, language, show_all=show_all),
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
    if template is None and block.kind in ("Template", "+Template"):
        # On clique le Template LUI-MEME dans Templates.ecf : la section
        # craft se construit depuis ce bloc, sans dependre d'une recherche
        # reussie dans templates_doc (ajout du 30/08/2026, retour
        # utilisateur : fiche incomplete sur un Template fraichement cree).
        template = block
    if template is not None:
        card.crafting_header = _translate_label("biwHeaderCrafting", loc, language)
        card.input_items_label = _translate_label("biwInputItems", loc, language)
        for child in template.children:
            if getattr(child, 'kind', None) == "Child Inputs":
                for prop in child.children:
                    pairs = getattr(prop, 'pairs', [])
                    if not pairs:
                        continue
                    k, v = pairs[0]
                    if k:
                        # source_key/source_raw_value = paire BRUTE dans le
                        # Template -- requis pour l'edition d'ingredient
                        # directement depuis la fiche (demande du 31/08/2026).
                        card.ingredients.append(InfoCardIngredient(
                            name=_translate_label(k, loc, language),
                            quantity=_bbcode_to_html(v),
                            source_key=k, source_raw_value=v))
        output_count = template.get_property('OutputCount')
        if output_count is not None:
            card.output_count = InfoCardField(
                label=_translate_label("biwOutputCount", loc, language),
                value=_bbcode_to_html(output_count.strip()),
                source_key="OutputCount", source_raw_value=output_count)

    return card
