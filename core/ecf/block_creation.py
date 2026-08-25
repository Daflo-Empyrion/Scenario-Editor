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
Logique de creation guidee d'un nouveau bloc/item, avec suggestion des
proprietes pertinentes (issues du fichier de travail lui-meme) et, pour les
Templates, des ingredients de craft (Child Inputs).

Structure Child Inputs confirmee sur un vrai Templates.ecf (925+ recettes) :
contrairement a 'Child Items' (motif numerote Name_0/Name_1/...), chaque
ligne d'ingredient utilise DIRECTEMENT le nom de l'item/bloc comme cle (ex:
'RockDust: 25', jusqu'a 14 ingredients differents sur un craft complexe) --
add_repeating_item_row() (concue pour le motif numerote) ne s'applique donc
pas ici, add_property_line() suffit.
"""
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .model import EcfBlock, EcfProperty, EcfDocument, create_block, add_property_line


def scan_kind_frequency(doc: EcfDocument) -> Counter:
    """Compte les occurrences de chaque genre de bloc racine (ex: 'Block',
    '+Container', '+Template'...) dans un document -- utilise pour proposer le
    genre le plus frequent comme valeur par defaut a la creation."""
    counts = Counter()
    for node in doc.nodes:
        if isinstance(node, EcfBlock):
            counts[node.kind] += 1
    return counts


def scan_properties_for_kind(doc: EcfDocument, kind: str) -> Dict[str, Counter]:
    """Pour un genre de bloc donne (ex: 'Block'), renvoie {cle_propriete:
    Counter(valeurs)} -- l'union des proprietes directes (pas les
    sous-structures comme Child Items/Child Inputs, non pertinentes pour une
    case a cocher simple) reellement utilisees par les blocs de ce genre dans
    le document, avec la frequence de chaque valeur (pour proposer la plus
    courante comme point de depart)."""
    result: Dict[str, Counter] = {}
    for node in doc.nodes:
        if not (isinstance(node, EcfBlock) and node.kind == kind):
            continue
        for child in node.children:
            if not isinstance(child, EcfProperty):
                continue
            for key, value in child.pairs:
                if key is None or value is None:
                    continue
                result.setdefault(key, Counter())[value] += 1
    return result


def most_common_value(counter: Counter) -> str:
    """Valeur la plus frequemment observee pour une propriete -- utilisee comme
    suggestion de depart dans le tableau de creation, jamais imposee."""
    return counter.most_common(1)[0][0] if counter else ""


def create_new_block(kind: str, id_value: Optional[str], name_value: Optional[str],
                      properties: List[Tuple[str, str]], eol: str = "\r\n") -> EcfBlock:
    """Cree un nouveau bloc racine avec Id et/ou Name en en-tete, puis les
    proprietes cochees en corps de bloc. Au moins l'un de id_value/name_value
    doit etre fourni (l'appelant est responsable de cette validation, deja
    geree par le dialogue GUI en amont)."""
    header_pairs: List[Tuple[Optional[str], str]] = []
    if id_value:
        header_pairs.append(('Id', id_value))
    if name_value:
        header_pairs.append(('Name', name_value))

    block = create_block(kind, header_pairs, eol=eol)
    for key, value in properties:
        add_property_line(block, [(key, value)])
    return block


def add_child_inputs(block: EcfBlock, ingredients: List[Tuple[str, str]], eol: str = "\r\n") -> EcfBlock:
    """Ajoute (ou complete si deja presente) le sous-bloc 'Child Inputs' d'un
    Template, une ligne par ingredient (nom_ingredient: quantite) -- structure
    confirmee sur un vrai Templates.ecf, differente du motif numerote Name_N
    utilise ailleurs (Child Items).

    N'utilise PAS add_property_line() pour les lignes d'ingredients : cette
    fonction partagee suppose un indent fixe de 2 espaces adapte aux
    proprietes de premier niveau, mais un sous-bloc imbrique comme
    Child Inputs a besoin d'un indent calcule par rapport a SON PROPRE
    niveau (confirme sur un vrai fichier : Container a indent='', Child Items
    a indent='  ', ses proprietes a indent='    ') -- gere ici manuellement
    pour rester correct quel que soit le niveau d'imbrication du bloc
    parent."""
    child_inputs = None
    for child in block.children:
        if isinstance(child, EcfBlock) and child.kind == 'Child Inputs':
            child_inputs = child
            break
    if child_inputs is None:
        nested_indent = block.indent + "  "
        child_inputs = create_block('Child Inputs', [], eol=eol)
        child_inputs.indent = nested_indent
        child_inputs.close_raw = f"{nested_indent}}}{eol}"
        block.children.append(child_inputs)

    ingredient_indent = child_inputs.indent + "  "
    for ingredient_name, quantity in ingredients:
        new_prop = EcfProperty(raw="", indent=ingredient_indent, pairs=[(ingredient_name, quantity)],
                                comment=None, eol=eol, dirty=True)
        child_inputs.children.append(new_prop)
    return child_inputs


def find_file_by_name(ecf_files: List[Path], filename: str) -> Optional[Path]:
    """Cherche un fichier par son nom exact (insensible a la casse) dans une
    liste de chemins -- utilise pour localiser Templates.ecf/ItemsConfig.ecf/
    BlocksConfig.ecf dans le scenario courant."""
    target = filename.lower()
    for path in ecf_files:
        if path.name.lower() == target:
            return path
    return None


def is_player_placeable_block(block: EcfBlock) -> bool:
    """True si ce bloc porte une 'AllowPlacingAt' non vide -- la propriete qui
    liste les types de structure (Base/MS/SS/GV) ou un JOUEUR peut le poser
    via le constructeur (confirmee dans le glossaire et les tutoriels de
    l'application). Un bloc sans cette propriete du tout n'est jamais posable
    par un joueur : il n'existe que dans des blueprints de POI places par le
    scenario/les devs (bloc 'reserve POI'). Ne s'applique qu'aux BLOCS
    (BlocksConfig.ecf) -- les items (ItemsConfig.ecf) n'ont pas ce concept de
    restriction, voir list_craftable_names ci-dessous."""
    return bool(block.get_property('AllowPlacingAt'))


def list_craftable_names(items_path: Optional[Path], blocks_path: Optional[Path],
                          players_only: bool = False) -> List[str]:
    """Union triee des Name reellement definis dans ItemsConfig.ecf et
    BlocksConfig.ecf -- utilise pour peupler la liste deroulante d'ingredients
    lors de la creation d'un Template (memes deux fichiers deja utilises comme
    pool combine par la verification croisee 'Items/blocs references', voir
    core/ecf/cross_reference_check.py).

    players_only : si True, exclut les blocs de BlocksConfig.ecf sans
    'AllowPlacingAt' (voir is_player_placeable_block) -- typiquement des blocs
    reserves aux POI, jamais posables par un joueur. Les items d'ItemsConfig.ecf
    restent TOUJOURS inclus (aucune propriete equivalente fiable pour eux)."""
    from .parser import parse_ecf_file

    names: set = set()
    for path, is_blocks_file in ((items_path, False), (blocks_path, True)):
        if path is None:
            continue
        try:
            doc = parse_ecf_file(path)
        except Exception:
            continue
        for block in doc.iter_blocks():
            if players_only and is_blocks_file and not is_player_placeable_block(block):
                continue
            name = block.get_property('Name')
            if name:
                names.add(name)
    return sorted(names)
