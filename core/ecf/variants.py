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
Duplication multi-variantes -- extension du dialogue "Dupliquer" existant
(core.ecf.model.duplicate_block) : au lieu de creer UNE copie, cree N
variantes nommees {NomBase}T1, {NomBase}T2 ... {NomBase}TN, avec une
variation lineaire en pourcentage sur les champs numeriques choisis par
l'utilisateur.

S'applique a deux contextes :
- Un bloc ECF entier (ex: dupliquer 'IronResource' en 3 variantes avec
  XpFactor variant de 0% a +20%).
- Une ligne de structure repetitive en mode tableau (ex: dupliquer une
  entree 'Item: IronOre, param1: 3' de LootGroups.ecf en plusieurs
  variantes avec param1/Prob variant).

Toujours identifie par Name seul (Id retire), coherent avec le
comportement du dialogue de duplication simple existant.
"""
import copy as _copy
from typing import List, Optional

from core.ecf.model import EcfBlock, EcfProperty, duplicate_block


def _unwrap_quotes(value: str) -> "tuple[str, bool]":
    """Retire une paire de guillemets doubles englobante si presente (ex:
    '"600"' -> ('600', True)) -- certains fichiers ECF reels citent des
    valeurs numeriques simples entre guillemets, pas seulement les plages
    ('"1,4"'). Retourne (valeur_interieure, etait_entre_guillemets)."""
    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        return value[1:-1], True
    return value, False


def is_numeric_value(value: Optional[str]) -> bool:
    """Une valeur est consideree numerique si elle se parse directement en
    nombre (entier ou decimal), y compris entre guillemets simples (ex:
    '"600"') -- les plages comme '1,4' ou '"1,4"' et les textes libres ne
    le sont pas, et ne sont donc pas proposes automatiquement dans la liste
    a cocher (l'utilisateur peut toujours taper leur nom manuellement, mais
    leur variation ne serait pas fiable ici)."""
    if value is None:
        return False
    inner, _ = _unwrap_quotes(value)
    try:
        float(inner)
        return True
    except ValueError:
        return False


def compute_variant_values(original_value: str, num_variants: int,
                            total_percent: float, first_is_original: bool) -> List[str]:
    """Calcule les N valeurs interpolees lineairement pour un champ
    numerique, en preservant le nombre de decimales de la valeur
    d'origine (ex: '2.0' -> resultats a 1 decimale, '10' -> entiers).

    - `total_percent` est l'ECART TOTAL entre le premier et le dernier
      variant (ex: 20.0 signifie que TN vaut 20% de plus que T1 en valeur
      relative -- voir les deux modes ci-dessous).
    - `first_is_original` = True : T1 = valeur d'origine exacte (0%), la
      variation va de 0% (T1) a +total_percent% (TN).
    - `first_is_original` = False : la plage est centree sur la valeur
      d'origine, de -total_percent/2% (T1) a +total_percent/2% (TN).

    Retourne toujours une liste de longueur `num_variants`, meme si
    `original_value` n'est pas numerique (valeur repetee sans
    modification dans ce cas -- jamais d'exception ici, la verification
    se fait en amont via is_numeric_value)."""
    if not is_numeric_value(original_value):
        return [original_value] * num_variants

    inner, was_quoted = _unwrap_quotes(original_value)
    base = float(inner)
    decimals = len(inner.split('.')[-1]) if '.' in inner else 0

    results = []
    for i in range(num_variants):
        frac = (i / (num_variants - 1)) if num_variants > 1 else 0.0
        if first_is_original:
            pct = (total_percent / 100.0) * frac
        else:
            pct = (total_percent / 100.0) * (frac - 0.5)
        value = base * (1 + pct)
        results.append(_format_variant_value(value, decimals, was_quoted))
    return results


def _format_variant_value(value: float, decimals: int, was_quoted: bool) -> str:
    """Formate une valeur calculee en preservant le nombre de decimales de
    l'original ('2.0' -> 1 decimale, '10' -> entier) et en la remettant
    entre guillemets si l'originale l'etait."""
    if decimals > 0:
        text = f"{value:.{decimals}f}"
    else:
        text = str(int(round(value)))
    return f'"{text}"' if was_quoted else text


def compute_single_variant_value(original_value: str, percent: float) -> str:
    """Calcule UNE nouvelle valeur = original * (1 + percent/100) --
    utilise pour le mode simple (une seule copie) du dialogue de
    duplication, quand l'utilisateur veut appliquer une variation en
    pourcentage sur sa copie unique sans creer plusieurs variantes.
    Retourne `original_value` inchangee si elle n'est pas numerique
    (jamais d'exception -- la verification se fait en amont via
    is_numeric_value)."""
    if not is_numeric_value(original_value):
        return original_value
    inner, was_quoted = _unwrap_quotes(original_value)
    base = float(inner)
    decimals = len(inner.split('.')[-1]) if '.' in inner else 0
    value = base * (1 + percent / 100.0)
    return _format_variant_value(value, decimals, was_quoted)


def set_template_ingredient(template: EcfBlock, ingredient_name: str, quantity: str) -> None:
    """Ajoute ou met a jour un ingredient dans le sous-bloc
    '{ Child Inputs }' d'un Template -- le CREE s'il n'existe pas encore
    (Template sans aucun ingredient au depart). Demande explicite de
    l'utilisateur (session du 29/08/2026) : pouvoir AJOUTER un nouvel
    ingredient a la recette (via une liste deroulante de blocs/items
    valides, voir gui/template_recipe_editor.py), pas seulement ajuster la
    quantite d'un ingredient existant."""
    from .model import create_block, add_property_line, EcfProperty as _EcfProperty

    child_inputs = None
    for child in template.children:
        if getattr(child, 'kind', None) == "Child Inputs":
            child_inputs = child
            break
    if child_inputs is None:
        # Indentation coherente avec de vrais fichiers (confirme sur
        # FuelTankMSLarge/Templates.ecf) : le sous-bloc s'aligne avec les
        # proprietes du parent, ses PROPRES enfants un niveau plus profond,
        # sa ligne de fermeture alignee avec sa propre ouverture -- le
        # parser capture cette info pour un bloc existant, mais un bloc
        # cree de toutes pieces (create_block) doit la reconstruire a la
        # main.
        eol = template.eol or "\r\n"
        parent_indent = "  "
        for pc in template.children:
            if isinstance(pc, _EcfProperty):
                parent_indent = pc.indent
                break
        child_inputs = create_block("Child Inputs", [], eol=eol)
        child_inputs.indent = parent_indent
        child_inputs.close_raw = f"{parent_indent}}}{eol}"
        template.children.append(child_inputs)
        # Premiere propriete : construite directement (pas via
        # add_property_line, dont l'indentation par defaut ne connait pas
        # la profondeur d'imbrication d'un bloc tout juste cree).
        child_inputs.children.append(_EcfProperty(
            raw="", indent=parent_indent + "  ", pairs=[(ingredient_name, quantity)],
            comment=None, eol=eol, dirty=True))
        return

    for prop in child_inputs.children:
        if isinstance(prop, EcfProperty) and prop.set(ingredient_name, quantity):
            return
    add_property_line(child_inputs, [(ingredient_name, quantity)])


def list_template_ingredients(template: EcfBlock) -> List["tuple[str, str]"]:
    """Liste les ingredients (cle=nom du bloc/item, valeur=quantite) du
    sous-bloc '{ Child Inputs ... }' d'un Template -- SEPARE des champs
    scalaires (voir list_template_scalar_fields) pour permettre une edition
    dediee par ingredient (ajout/quantite) plutot qu'un simple tableau
    cle/valeur generique -- demande explicite de l'utilisateur (session du
    29/08/2026)."""
    for child in template.children:
        if getattr(child, 'kind', None) == "Child Inputs":
            return [(k, v) for prop in child.children for k, v in getattr(prop, 'pairs', []) if k]
    return []


def remove_template_ingredient(template: EcfBlock, ingredient_name: str) -> bool:
    """Retire un ingredient du sous-bloc '{ Child Inputs }' d'un Template
    (complement de set_template_ingredient -- demande explicite de
    l'utilisateur du 30/08/2026 : pouvoir AJOUTER ET SUPPRIMER des
    ingredients dans TOUS les modes de creation/edition de Template).
    Retourne False si l'ingredient n'y etait pas. Le sous-bloc Child Inputs
    reste en place meme vide (structure standard des vrais fichiers)."""
    for child in template.children:
        if getattr(child, 'kind', None) == "Child Inputs":
            for prop in child.children:
                if isinstance(prop, EcfProperty) and any(k == ingredient_name for k, _v in prop.pairs):
                    child.children.remove(prop)
                    return True
            return False
    return False


def remove_template_scalar(template: EcfBlock, key: str) -> bool:
    """Retire un champ SCALAIRE d'un Template (complement de
    set_block_field -- demande explicite de l'utilisateur du 30/08/2026 :
    le Template de base pre-rempli avec TOUTES les proprietes des autres
    Templates doit permettre d'en SUPPRIMER, pas seulement d'en modifier).
    Cherche la cle sur la ligne d'ouverture du bloc puis sur ses proprietes
    enfants directes, SANS jamais descendre dans '{ Child Inputs }' (les
    ingredients ont leur propre retrait via remove_template_ingredient).
    Si la ligne enfant porte plusieurs paires (ex: 'display: X, type: Y'),
    seule la paire concernee est retiree ; la ligne entiere si c'etait la
    seule. Retourne False si la cle n'y etait pas."""
    if template.remove(key):
        return True
    for child in template.children:
        if isinstance(child, EcfProperty) and any(k == key for k, _v in child.pairs):
            if len(child.pairs) == 1:
                template.children.remove(child)
            else:
                child.pairs = [(k, v) for k, v in child.pairs if k != key]
                child.dirty = True
            return True
    return False


def list_template_scalar_fields(template: EcfBlock) -> List["tuple[str, str]"]:
    """Liste les champs SCALAIRES d'un Template (CraftTime, Target,
    OutputCount...) -- EXCLUT deliberement le contenu de '{ Child Inputs }'
    (voir list_template_ingredients, edite separement) ainsi qu'Id/Name
    (geres a part)."""
    fields: List["tuple[str, str]"] = []
    seen: set = set()
    for k, v in template.pairs:
        if k and k not in ('Id', 'Name') and k not in seen:
            seen.add(k)
            fields.append((k, v))
    for child in template.children:
        if isinstance(child, EcfProperty) and child.pairs:
            main_key, main_value = child.pairs[0]
            if main_key and main_key not in ('Id', 'Name', 'display', 'type', 'formatter') and main_key not in seen:
                seen.add(main_key)
                fields.append((main_key, main_value))
    return fields


def list_editable_fields_block(block: EcfBlock) -> List["tuple[str, str]"]:
    """Liste TOUS les champs (cle, valeur) d'un bloc -- ligne d'ouverture,
    proprietes enfants directes, ET sous-blocs imbriques recursivement
    (meme parcours que get_block_field/set_block_field) -- utilisee pour
    l'aperetu editable propose pendant la duplication (voir
    gui/duplicate_variants_dialog.py, demande explicite de l'utilisateur du
    29/08/2026 : pouvoir ajuster les proprietes du duplicata EN MEME TEMPS
    que la duplication, sans repasser dessus apres coup). 'Id'/'Name' sont
    exclus : geres par des champs dedies du dialogue. Pas de filtre
    numerique ici (contrairement a detect_numeric_fields_block) -- tout
    champ simple est editable, y compris du texte."""
    fields: List["tuple[str, str]"] = []
    seen: set = set()

    def scan(b: EcfBlock):
        for k, v in b.pairs:
            if k and k not in ('Id', 'Name') and k not in seen:
                seen.add(k)
                fields.append((k, v))
        for child in b.children:
            if isinstance(child, EcfProperty):
                for k, v in child.pairs:
                    if k and k not in ('Id', 'Name', 'display', 'type', 'formatter') and k not in seen:
                        seen.add(k)
                        fields.append((k, v))
        for child in b.children:
            if isinstance(child, EcfBlock):
                scan(child)

    scan(block)
    return fields


def get_block_field(block: EcfBlock, key: str) -> Optional[str]:
    """Cherche une cle sur la ligne d'ouverture du bloc (Id, Name,
    Class...), sur ses proprietes enfants directes (Material, XpFactor...
    la majorite des champs reels), ET recursivement dans ses sous-blocs
    imbriques (ex: 'Prob' dans '{ Child DropOnDestroy Item: X, Prob: 0.5 }'
    -- un motif frequent dans BlocksConfig.ecf reel). Retourne la PREMIERE
    occurrence trouvee (ordre : ligne d'ouverture, puis enfants directs
    dans l'ordre, puis sous-blocs recursivement) -- en pratique les vrais
    fichiers ECF n'ont pas de collision de nom de champ entre sous-blocs
    d'un meme bloc parent, mais si c'etait le cas, seule la premiere serait
    lue/modifiee ici."""
    value = block.get(key)
    if value is not None:
        return value
    for child in block.children:
        if isinstance(child, EcfProperty):
            value = child.get(key)
            if value is not None:
                return value
    for child in block.children:
        if isinstance(child, EcfBlock):
            value = get_block_field(child, key)
            if value is not None:
                return value
    return None


def set_block_field(block: EcfBlock, key: str, value: str) -> bool:
    """Meme logique de recherche que get_block_field, mais pour ecrire une
    nouvelle valeur -- s'arrete a la premiere occurrence modifiee."""
    if block.set(key, value):
        return True
    for child in block.children:
        if isinstance(child, EcfProperty):
            if child.set(key, value):
                return True
    for child in block.children:
        if isinstance(child, EcfBlock):
            if set_block_field(child, key, value):
                return True
    return False


def detect_numeric_fields_block(block: EcfBlock) -> List[str]:
    """Liste les cles numeriques d'un bloc : ligne d'ouverture, proprietes
    enfants directes, ET proprietes de sous-blocs imbriques recursivement
    (ex: 'Prob' dans un sous-bloc '{ Child DropOnDestroy ... }') --
    utilisee pour pre-cocher automatiquement les champs candidats a la
    variation dans le dialogue. 'Id' est toujours exclu : il est retire de
    toute facon lors de la generation des variantes (identifiees par Name
    seul), le proposer a cocher serait trompeur. L'ordre suit celui
    d'apparition dans le fichier (bloc parent d'abord, puis sous-blocs)."""
    keys: List[str] = []

    def scan(b: EcfBlock):
        for k, v in b.pairs:
            if k and k != 'Id' and is_numeric_value(v) and k not in keys:
                keys.append(k)
        for child in b.children:
            if isinstance(child, EcfProperty):
                for k, v in child.pairs:
                    if k and is_numeric_value(v) and k not in keys:
                        keys.append(k)
        for child in b.children:
            if isinstance(child, EcfBlock):
                scan(child)

    scan(block)
    return keys


def generate_block_variants(block: EcfBlock, name_base: str, num_variants: int,
                             varying_fields: List[str], total_percent: float,
                             first_is_original: bool, variant_names: Optional[List[str]] = None) -> List[EcfBlock]:
    """Genere N blocs variantes independants a partir d'un bloc source.
    Chaque variante : Name = '{name_base}T{i+1}' PAR DEFAUT, ou le nom
    fourni dans `variant_names[i]` si precise (demande explicite de
    l'utilisateur, session du 29/08/2026 : pouvoir personnaliser le nom de
    chaque variante plutot que de subir le suffixe TN automatique). Id
    retire (identifie par Name seul), champs de `varying_fields` interpoles
    lineairement, tous les autres champs identiques au bloc source (copie
    profonde via core.ecf.model.duplicate_block, meme mecanique que la
    duplication simple existante)."""
    variants: List[EcfBlock] = []
    for i in range(num_variants):
        new_name = variant_names[i] if variant_names and i < len(variant_names) else f"{name_base}T{i + 1}"
        new_block = duplicate_block(block, overrides={'Name': new_name}, remove_keys=['Id'])
        for field_key in varying_fields:
            original_value = get_block_field(block, field_key)
            if original_value is None:
                continue
            values = compute_variant_values(original_value, num_variants, total_percent, first_is_original)
            set_block_field(new_block, field_key, values[i])
        variants.append(new_block)
    return variants


def apply_percent_to_block(block: EcfBlock, fields: List[str], percent: float) -> EcfBlock:
    """Retourne une COPIE PROFONDE du bloc avec les `fields` indiques
    modifies par un pourcentage unique par rapport a leur valeur d'origine
    (voir compute_single_variant_value) -- utilise pour le mode simple
    (une seule copie) du dialogue de duplication, quand l'utilisateur veut
    par ex. +15% de HitPoints sur sa copie unique sans creer plusieurs
    variantes. Les champs introuvables ou non numeriques sont ignores
    silencieusement."""
    new_block = _copy.deepcopy(block)
    new_block.dirty = True
    for field_key in fields:
        original_value = get_block_field(block, field_key)
        if original_value is None:
            continue
        new_value = compute_single_variant_value(original_value, percent)
        set_block_field(new_block, field_key, new_value)
    return new_block


def apply_percent_to_row(prop: EcfProperty, fields: List[str], percent: float) -> EcfProperty:
    """Equivalent de apply_percent_to_block pour une ligne de structure
    repetitive en mode tableau (pas de sous-blocs a traverser : une ligne
    est toujours plate)."""
    new_prop = _copy.deepcopy(prop)
    new_prop.dirty = True
    for field_key in fields:
        original_value = prop.get(field_key)
        if original_value is None:
            continue
        new_prop.set(field_key, compute_single_variant_value(original_value, percent))
    return new_prop


def detect_numeric_fields_row(prop: EcfProperty) -> List[str]:
    """Liste les cles numeriques d'une ligne repetitive de mode tableau
    (ex: 'Item: IronOre, param1: 3, Prob: 0.6') -- exclut la premiere
    paire (le nom identifiant l'entree, ex: 'Item')."""
    keys: List[str] = []
    for k, v in prop.pairs[1:]:
        if k and is_numeric_value(v) and k not in keys:
            keys.append(k)
    return keys


def generate_row_variants(prop: EcfProperty, num_variants: int, varying_fields: List[str],
                           total_percent: float, first_is_original: bool) -> List[EcfProperty]:
    """Genere N lignes variantes independantes a partir d'une ligne de
    structure repetitive (mode tableau). Le nom (valeur de la premiere
    paire, ex: 'IronOre' dans 'Item: IronOre, ...') recoit le suffixe
    T1..TN. Les champs de `varying_fields` recoivent la variation
    lineaire ; tous les autres restent identiques (copie profonde)."""
    if not prop.pairs:
        return []
    base_name = prop.pairs[0][1]
    first_key = prop.pairs[0][0]
    variants: List[EcfProperty] = []
    for i in range(num_variants):
        new_prop = _copy.deepcopy(prop)
        new_prop.dirty = True
        new_prop.set(first_key, f"{base_name}T{i + 1}")
        for field_key in varying_fields:
            original_value = prop.get(field_key)
            if original_value is None:
                continue
            values = compute_variant_values(original_value, num_variants, total_percent, first_is_original)
            new_prop.set(field_key, values[i])
        variants.append(new_prop)
    return variants
