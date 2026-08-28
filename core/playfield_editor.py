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
Edition structuree (en tableau) de sections precises d'un playfield.yaml --
Ressources aleatoires, Ressources d'asteroides, POI et Creatures -- plutot que
de naviguer le YAML brut ligne par ligne. Complement a core/yamllite (le
parseur generique), pas un remplacement : le reste du playfield (atmosphere,
ciel, brouillard...) continue de s'editer via l'arbre YAML classique.

Portee etablie a partir d'un vrai playfield.yaml et de vrais BlocksConfig.ecf/
ItemsConfig.ecf (pas devinee) :
- Les noms de ressources ("IronResource", "CopperResource"...) sont des BLOCS
  (BlocksConfig.ecf), PAS des items -- confirmed par recherche directe. Liste
  deroulante fiable pour l'ajout de nouvelles ressources.
- Les GroupName de POI ("R2DroneBase"...) ne correspondent a aucun nom trouve
  dans BlocksConfig.ecf ni ItemsConfig.ecf -- pas de source fiable pour une
  liste deroulante de *nouveaux* POI. Seule l'edition des POI DEJA PRESENTS
  est proposee (parametres : delais, difficulte, distances...), jamais
  l'ajout d'un nouveau POI par selection de type.
- Meme constat et meme limitation pour les noms de creatures/drones
  ("RipperDog", "Spiders01"...) -- absents des deux fichiers verifies,
  probablement definis par le jeu de base plutot que par le scenario.

Piege des commentaires a indentation zero (playfield_static.yaml, Sectors.yaml
-- fichiers reels) : CORRIGE A LA RACINE dans core/yamllite/parser.py (un
commentaire n'etablit/ne rompt plus jamais un niveau d'imbrication). Les
fonctions par plage d'indices ci-dessous (_section_index_range et consorts)
restent en place comme filet de securite redondant mais ne sont plus
necessaires au fonctionnement correct -- voir list_items() pour le detail de
la verification.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from core.yamllite.model import YamlEntry, YamlDocument, create_entry, remove_entry
from core.yamllite.parser import parse_yaml_file


# ============================================================================
# Localisation des sections dans le document
# ============================================================================

def find_top_level_key(doc: YamlDocument, key: str) -> Optional[YamlEntry]:
    for node in doc.nodes:
        if isinstance(node, YamlEntry) and node.key == key:
            return node
    return None


def list_items(doc: YamlDocument, section_key: str, item_key: str = "Name") -> List[YamlEntry]:
    """Renvoie les items d'une sequence de niveau racine (RandomResources,
    AsteroidResources, Resources...) -- chaque item est reperable par sa
    PREMIERE cle (`item_key`, generalement 'Name' ou 'GroupName') marquee
    is_sequence_item=True.

    Cherche par PLAGE D'INDICES au sein du document plutot que par simple
    descente dans les enfants directs de la section -- a l'origine
    necessaire car des commentaires a indentation zero au milieu d'une liste
    (frequents dans de vrais fichiers : "# Smaller scattered around planet",
    "### Resource Asteroids"...) cassaient le rattachement hierarchique du
    parseur ; les items qui suivaient un tel commentaire "fuyaient" alors au
    niveau racine du document plutot que de rester enfants de la section.
    CORRIGE A LA RACINE depuis dans core/yamllite/parser.py (un commentaire
    n'etablit/ne rompt plus jamais un niveau d'imbrication, quelle que soit
    son indentation) -- verifie sur playfield_static.yaml/Sectors.yaml
    (fichiers reels) : une simple descente dans section.children retrouve
    desormais exactement le meme compte qu'ici. Cette fonction par plage
    d'indices est conservee telle quelle (filet de securite redondant mais
    inoffensif) plutot que remplacee par une descente directe, pour ne pas
    reintroduire de risque de regression sur du code GUI deja teste pour un
    gain desormais purement cosmetique. Meme principe deja utilise par
    find_poi_items()/find_creature_items(), desormais partage par toutes les
    sections via cette fonction unique."""
    rng = _section_index_range(doc, section_key)
    if rng is None:
        return []
    return _find_items_in_range(doc, rng[0], rng[1], item_key)


def _section_index_range(doc: YamlDocument, section_key: str) -> Optional[tuple]:
    """Indices (debut inclus, fin exclue) delimitant une section de niveau racine
    dans doc.nodes, du noeud lui-meme jusqu'au prochain noeud de niveau racine
    (indent vide) -- ou la fin du document. A l'origine utilisee plutot qu'une
    simple descente recursive car certains fichiers reels contenaient des
    commentaires a indentation zero cassant le rattachement hierarchique du
    parseur -- CORRIGE A LA RACINE depuis dans core/yamllite/parser.py (voir
    list_items() ci-dessus pour le detail et la verification sur fichiers
    reels). Fonction conservee en l'etat comme filet de securite redondant."""
    start = None
    for i, node in enumerate(doc.nodes):
        if isinstance(node, YamlEntry) and node.key == section_key and node.indent == "":
            start = i
            break
    if start is None:
        return None
    end = len(doc.nodes)
    for i in range(start + 1, len(doc.nodes)):
        node = doc.nodes[i]
        if isinstance(node, YamlEntry) and node.key is not None and node.indent == "":
            end = i
            break
    return start, end


def _find_items_in_range(doc: YamlDocument, start: int, end: int, item_key: str) -> List[YamlEntry]:
    """Cherche toutes les entrees `item_key:` (marquees is_sequence_item=True) dans
    la plage d'indices [start, end) de doc.nodes, en descendant recursivement
    dans les enfants de chaque noeud de la plage -- couvre a la fois les items
    normalement imbriques ET ceux qui ont 'fui' au niveau racine (voir
    _section_index_range)."""
    found: List[YamlEntry] = []

    def walk(nodes):
        for node in nodes:
            if isinstance(node, YamlEntry):
                if node.is_sequence_item and node.key == item_key:
                    found.append(node)
                walk(node.children)

    walk(doc.nodes[start:end])
    return found


def _find_items_with_subsection_tracking(doc: YamlDocument, start: int, end: int, item_key: str,
                                          subsection_keys: List[str]) -> List[tuple]:
    """Comme _find_items_in_range(), mais associe en plus a chaque item trouve la
    DERNIERE cle de sous-section (parmi `subsection_keys`) rencontree avant lui
    dans l'ORDRE DU TEXTE -- necessaire quand plusieurs listes distinctes
    partagent la meme cle d'item (ex: 'FreeDrones' et 'SpaceVessels' utilisent
    toutes deux 'Name:') au sein d'une meme section de niveau racine. Le
    parcours se fait dans l'ordre naturel du fichier (doc.nodes preserve cet
    ordre, meme pour les noeuds "fuis" par le piege des commentaires a
    indentation variable), donc suivre la derniere sous-section vue reste
    fiable meme quand la vraie imbrication est cassee. Retourne une liste de
    tuples (item, sous_section_ou_None)."""
    found: List[tuple] = []
    current = [None]

    def walk(nodes):
        for node in nodes:
            if isinstance(node, YamlEntry):
                if node.key in subsection_keys:
                    current[0] = node.key
                if node.is_sequence_item and node.key == item_key:
                    found.append((node, current[0]))
                walk(node.children)

    walk(doc.nodes[start:end])
    return found


def find_poi_items(doc: YamlDocument) -> List[YamlEntry]:
    """Toutes les entrees POI ('GroupName:') de la section POIs, quel que soit
    leur niveau d'imbrication reel dans l'arbre (voir _section_index_range)."""
    return list_items(doc, "POIs", "GroupName")


def find_creature_items(doc: YamlDocument) -> List[YamlEntry]:
    """Toutes les entrees creature ('Name:') de la section CreatureSpawning.

    Chaque item retourne porte en plus un attribut dynamique `.biome` (chaine,
    ex: '[Grassland]') indiquant la zone de biome a laquelle il appartient --
    indispensable car un MEME nom de creature (ex: 'Spiders01') apparait
    couramment dans plusieurs zones differentes avec des parametres
    differents, impossible a distinguer sans cette info (signale directement
    par retour utilisateur sur un vrai scenario).

    Contrairement a find_poi_items(), descend par vraie hierarchie d'arbre
    (CreatureSpawning > Biomes > Entities > Name) plutot que par plage
    d'indices -- structure confirmee intacte ici (le nombre trouve est
    identique par les deux methodes sur un vrai fichier), pas affectee par le
    piege des commentaires a indentation zero qui touche la section POI."""
    section = find_top_level_key(doc, "CreatureSpawning")
    if section is None:
        return []

    found: List[YamlEntry] = []

    def walk(nodes, biome: str):
        for node in nodes:
            if isinstance(node, YamlEntry):
                if node.is_sequence_item and node.key == "Name":
                    node._biome = biome
                    found.append(node)
                walk(node.children, biome)

    for child in section.children:
        if isinstance(child, YamlEntry) and child.key == "Biomes":
            walk(child.children, child.value)

    return found


def get_creature_biome(item: YamlEntry) -> str:
    """Zone de biome ('.biome', voir find_creature_items) d'une entree creature
    -- chaine vide si absente (ne devrait arriver que sur un item construit a
    la main hors de find_creature_items, ex: dans un test)."""
    return getattr(item, "_biome", "")


def _find_subsection_items(doc: YamlDocument, section_key: str, item_key: str,
                            subsection_keys: List[str], target_subsection: str) -> List[YamlEntry]:
    """Combine _section_index_range + _find_items_with_subsection_tracking + filtre
    sur `target_subsection` -- factorise le motif partage par toutes les
    sections ou plusieurs listes distinctes cohabitent sous la meme cle de
    niveau racine (POIs > Fixed/Random/FixedPlayerStart,
    DroneBaseSetup > Stock/FreeDrones/SpaceVessels)."""
    rng = _section_index_range(doc, section_key)
    if rng is None:
        return []
    tagged = _find_items_with_subsection_tracking(doc, rng[0], rng[1], item_key, subsection_keys)
    return [item for item, subsection in tagged if subsection == target_subsection]


def find_fixed_poi_items(doc: YamlDocument) -> List[YamlEntry]:
    """Entrees 'POIs > Fixed' -- POI a position absolue fixe (cle d'item 'Type',
    PAS 'GroupName' comme les entrees Random -- confirme sur un vrai
    playfield_akua.yaml : '- Type: BA_Player / Name: ... / Pos: [x,y,z]').
    Utilise le suivi de sous-section (comme FreeDrones/SpaceVessels) car
    'Fixed' 'fuit' au niveau racine sur ce meme fichier reel a cause du meme
    piege des commentaires a indentation zero deja rencontre pour 'Random' --
    une simple descente dans les enfants directs de POIs ne suffit pas.

    'FixedPlayerStart' est inclus dans les cles de sous-section suivies (mais
    jamais retourne ici) uniquement pour delimiter correctement les zones --
    confirme sur un vrai fichier ou 'FixedPlayerStart' est imbrique ENTRE deux
    occurrences successives de 'Random:' (meme fichier reutilisant deux fois
    ce marqueur), sans quoi les items suivant la reprise de 'Random:' apres
    'FixedPlayerStart' resteraient a tort tagues avec l'ancienne sous-section."""
    return _find_subsection_items(doc, "POIs", "Type", ["Fixed", "Random", "FixedPlayerStart"], "Fixed")


def find_random_poi_items(doc: YamlDocument) -> List[YamlEntry]:
    """Entrees 'POIs > Random' uniquement (sous-ensemble de find_poi_items(),
    qui remonte TOUTES les entrees POI -- utile quand on doit specifiquement
    distinguer Fixed de Random, ex: le canvas 2D ou seules les Fixed ont une
    position absolue directement exploitable). Voir find_fixed_poi_items()
    pour le role de 'FixedPlayerStart' dans les cles de sous-section suivies."""
    return _find_subsection_items(doc, "POIs", "GroupName", ["Fixed", "Random", "FixedPlayerStart"], "Random")


def find_fixed_player_start_items(doc: YamlDocument) -> List[YamlEntry]:
    """Entrees 'POIs > FixedPlayerStart' -- points d'apparition fixes du joueur
    par Mode (Debug/Survival/Creative...), cle d'item 'Mode'. Confirme
    imbrique sous POIs (indentation non-zero), PAS une cle de niveau racine
    comme suppose initialement -- 4 entrees trouvees sur un vrai
    playfield_static.yaml, entre les deux occurrences de 'Random:' de ce meme
    fichier."""
    return _find_subsection_items(doc, "POIs", "Mode", ["Fixed", "Random", "FixedPlayerStart"], "FixedPlayerStart")


# ============================================================================
# Lecture/ecriture des parametres d'un item (colonnes du tableau)
# ============================================================================

def get_item_params(item: YamlEntry) -> List[tuple]:
    """Paires (cle, valeur) des parametres directs d'un item de liste (ignore
    lignes vides/commentaires) -- devient les colonnes du tableau."""
    return [
        (child.key, child.value)
        for child in item.children
        if isinstance(child, YamlEntry) and child.key is not None
    ]


def set_item_param(item: YamlEntry, key: str, value: str) -> bool:
    """Modifie un parametre existant de l'item. Retourne False si la cle
    n'existe pas sur cet item precis (ne cree jamais une cle absente -- des
    items differents du meme type de liste n'ont pas toujours les memes
    parametres, ex: DroneProb absent sur certains POI)."""
    return item.set(key, value)


def get_properties_value(item: YamlEntry, prop_key: str) -> Optional[str]:
    """Lit une valeur imbriquee dans le bloc 'Properties:' d'un item (structure
    confirmee sur un vrai POI : 'Properties: > - Key: RegenAfter > Value:
    4320') -- utilise notamment pour exposer RegenAfter comme une colonne a
    part entiere du tableau, plutot que de le laisser cache dans la valeur
    structuree generique 'Properties' (non editable directement, voir
    _is_complex_param cote GUI). Retourne None si le bloc Properties est
    absent ou si cette cle precise n'y figure pas -- toutes les entrees n'ont
    pas forcement de RegenAfter (ex: POI jamais detruits/regeneres)."""
    for child in item.children:
        if isinstance(child, YamlEntry) and child.key == "Properties":
            for prop_entry in child.children:
                if isinstance(prop_entry, YamlEntry) and prop_entry.key == "Key" and prop_entry.value == prop_key:
                    for sub in prop_entry.children:
                        if isinstance(sub, YamlEntry) and sub.key == "Value":
                            return sub.value
    return None


def set_properties_value(item: YamlEntry, prop_key: str, new_value: str) -> bool:
    """Modifie une valeur imbriquee dans 'Properties:' (voir
    get_properties_value). Ne cree jamais une entree absente -- retourne False
    si le bloc Properties ou cette cle precise n'existent pas deja sur cet
    item, coherent avec set_item_param() qui a la meme regle pour les
    parametres directs."""
    for child in item.children:
        if isinstance(child, YamlEntry) and child.key == "Properties":
            for prop_entry in child.children:
                if isinstance(prop_entry, YamlEntry) and prop_entry.key == "Key" and prop_entry.value == prop_key:
                    for sub in prop_entry.children:
                        if isinstance(sub, YamlEntry) and sub.key == "Value":
                            sub.set_own_value(new_value)
                            return True
    return False


# ============================================================================
# Ajout/suppression d'une ressource (RandomResources / AsteroidResources
# uniquement -- seule section ou l'ajout est propose, voir le commentaire de
# portee en tete de module)
# ============================================================================

# Historique : "AsteroidVoxel*" avait ete exclu par prudence sur simple
# hypothese ; confirme depuis par retour direct sur un vrai fichier de
# playfield spatial (space_dynamic.yaml) qu'il s'agit de VRAIES ressources
# d'asteroides spatiaux, dans une categorie distincte des ressources
# planetaires -- desormais traitees separement (voir
# find_space_resource_items / add_space_resource_item ci-dessous) plutot
# qu'exclues.
_EXCLUDED_RESOURCE_PATTERNS = []


def list_resource_block_names(blocks_ecf_files: List[Path]) -> List[str]:
    """Noms de blocs plausibles comme ressource minable -- ceux dont le Name se
    termine par 'Resource' (motif confirme sur un vrai BlocksConfig.ecf :
    IronResource, CopperResource, PromethiumResource...). Utilise pour peupler
    la liste deroulante d'ajout d'une nouvelle ressource.

    Certains noms sont explicitement EXCLUS malgre le motif (voir
    _EXCLUDED_RESOURCE_PATTERNS) -- ex: "AsteroidVoxel*Resource", signale comme
    a risque : leur comportement exact n'est pas confirme et d'autres entrees
    correspondent deja au meme materiau, donc mieux vaut ne pas les proposer
    du tout que risquer un bug aleatoire en jeu."""
    from core.ecf.parser import parse_ecf_file

    names: List[str] = []
    pattern = re.compile(r'Resource$')
    for path in blocks_ecf_files:
        try:
            doc = parse_ecf_file(path)
        except Exception:
            continue
        for block in doc.iter_blocks():
            name = block.get_property('Name')
            if not name or not pattern.search(name):
                continue
            if any(excl.search(name) for excl in _EXCLUDED_RESOURCE_PATTERNS):
                continue
            names.append(name)
    return sorted(set(names))


def add_resource_item(doc: YamlDocument, section_key: str, name: str, params: List[tuple]) -> Optional[YamlEntry]:
    """Ajoute une nouvelle ressource a la fin d'une section (RandomResources ou
    AsteroidResources), avec l'indentation et la fin de ligne calquees sur un
    item existant de la meme section pour un rendu coherent -- si la section
    est vide, utilise des valeurs par defaut raisonnables (4 espaces / CRLF,
    coherentes avec un vrai playfield.yaml verifie). Retourne None si la
    section n'existe pas dans ce document."""
    section = find_top_level_key(doc, section_key)
    if section is None:
        return None

    existing_items = list_items(doc, section_key, "Name")
    if existing_items:
        item_indent = existing_items[0].indent
        eol = existing_items[0].eol
        child_indent = None
        for child in existing_items[0].children:
            if isinstance(child, YamlEntry):
                child_indent = child.indent
                break
    else:
        item_indent = "    "
        eol = "\r\n"
        child_indent = "      "
    if child_indent is None:
        child_indent = item_indent + "  "

    new_item = create_entry("Name", name, indent=item_indent, is_sequence_item=True, eol=eol)
    for key, value in params:
        new_item.children.append(
            create_entry(key, value, indent=child_indent, is_sequence_item=False, eol=eol))

    section.children.append(new_item)
    return new_item


def remove_resource_item(doc: YamlDocument, section_key: str, item: YamlEntry) -> bool:
    section = find_top_level_key(doc, section_key)
    if section is None:
        return False
    return remove_entry(section.children, item)


# ============================================================================
# Ressources spatiales (asteroides) -- section "Resources:" des playfields
# ESPACE, structure differente des sections planetaires ci-dessus :
# - "Name:" contient une LISTE de variantes (ex: "[AsteroidVoxel01Iron,
#   AsteroidVoxel02Iron, AsteroidVoxel03Iron]"), pas un nom de bloc unique
# - "DisplayName:" porte le nom lisible ("Iron Asteroid") -- utilise pour
#   l'affichage, bien plus lisible que la liste technique brute
# - Le materiau ("Iron", "Copper"...) ne correspond a AUCUN bloc reel dans
#   BlocksConfig.ecf (verifie : "AsteroidVoxel01Iron" n'existe pas comme
#   Name de bloc) -- seul le materiau de base, SANS le suffixe technique
#   "AsteroidVoxel0N", correspond au meme materiau que les ressources
#   planetaires (ex: "IronResource" -> "Iron"). Confirme sur un vrai
#   space_dynamic.yaml : 13 materiaux suivent ce motif a 3 variantes.
# ============================================================================

_SPACE_RESOURCE_NAME_PATTERN = re.compile(r'AsteroidVoxel\d+([A-Za-z]+)')


def find_space_resource_items(doc: YamlDocument) -> List[YamlEntry]:
    """Entrees de ressources d'asteroides spatiaux (section 'Resources:' d'un
    playfield ESPACE) -- ne retient QUE celles dont la valeur de 'Name:'
    correspond au motif confirme 'AsteroidVoxel0N<Materiau>' (liste de
    variantes), pour laisser de cote les nombreuses autres entrees de cette
    meme section qui ne sont PAS des ressources minables (champs d'asteroides
    decoratifs, structures composees -- ex: 'AsteroidFieldBoxExclude',
    'CompoundAsteroidT1' -- hors de portee ici, modifiables via l'onglet YAML
    complet)."""
    section = find_top_level_key(doc, "Resources")
    if section is None:
        return []
    items = list_items(doc, "Resources", "Name")
    return [item for item in items if _SPACE_RESOURCE_NAME_PATTERN.search(item.value or "")]


def get_space_resource_display_name(item: YamlEntry) -> str:
    """Nom lisible d'une ressource spatiale -- 'DisplayName' (ex: 'Iron
    Asteroid') si present, sinon repli sur la valeur technique brute."""
    display = item.get("DisplayName")
    return display if display else item.value


def list_space_material_names(blocks_ecf_files: List[Path]) -> List[str]:
    """Materiaux disponibles pour une NOUVELLE ressource spatiale -- reprend le
    meme pool que list_resource_block_names() (blocs '*Resource' reels), mais
    retire le suffixe 'Resource' pour obtenir le materiau de base ('Iron' au
    lieu de 'IronResource'), coherent avec le motif de nommage confirme des
    ressources spatiales."""
    block_names = list_resource_block_names(blocks_ecf_files)
    materials = sorted({name[:-len("Resource")] for name in block_names if name.endswith("Resource")})
    return materials


def add_space_resource_item(doc: YamlDocument, material: str,
                             template_item: Optional[YamlEntry] = None) -> Optional[YamlEntry]:
    """Ajoute une nouvelle ressource spatiale pour `material` (ex: 'Iron') --
    genere le nom technique a 3 variantes 'AsteroidVoxel01<M>,
    AsteroidVoxel02<M>, AsteroidVoxel03<M>' (motif dominant confirme, 13
    materiaux sur un vrai fichier suivent cette convention) et le DisplayName
    correspondant ('<M> Asteroid').

    Duplique la structure complete (Position, Properties/RegenAfter...) d'un
    item existant de la meme section plutot que de la reconstruire a la main
    -- ces sous-structures sont imbriquees sur plusieurs niveaux, dupliquer un
    exemple qui fonctionne deja est plus sur que de recalculer chaque
    indentation. Si aucun item existant n'est fourni comme modele
    (`template_item`), le premier item existant de la section est utilise
    automatiquement s'il y en a un. Retourne None si la section 'Resources'
    n'existe pas dans ce document."""
    import copy

    section = find_top_level_key(doc, "Resources")
    if section is None:
        return None

    if template_item is None:
        existing = find_space_resource_items(doc)
        template_item = existing[0] if existing else None

    if template_item is not None:
        new_item = copy.deepcopy(template_item)
    else:
        # Aucun modele disponible (section vide) -- structure minimale de repli.
        new_item = create_entry("Name", "", indent="    ", is_sequence_item=True, eol="\r\n")
        new_item.children.append(create_entry("DisplayName", "", indent="      ", eol="\r\n"))

    variants = ", ".join(f"AsteroidVoxel0{i}{material}" for i in (1, 2, 3))
    new_item.set_own_value(f"[ {variants}]")
    new_item.dirty = True
    if not new_item.set("DisplayName", f"{material} Asteroid"):
        new_item.children.insert(0, create_entry(
            "DisplayName", f"{material} Asteroid",
            indent=new_item.indent + "  ", eol=new_item.eol))

    section.children.append(new_item)
    return new_item


def remove_space_resource_item(doc: YamlDocument, item: YamlEntry) -> bool:
    section = find_top_level_key(doc, "Resources")
    if section is None:
        return False
    return remove_entry(section.children, item)


# ============================================================================
# DroneBaseSetup -- structure differente entre playfields planete et espace,
# confirmee sur de vrais fichiers (playfield_akua.yaml et space_dynamic.yaml) :
# - PLANETE : DroneBaseSetup > DroneBases > (chaque base) > Stock > (Name +
#   Amount) -- la garnison d'une base de drones au sol, structure simple
# - ESPACE : DroneBaseSetup > FreeDrones (drones de patrouille libres) ET
#   SpaceVessels (vaisseaux, structure BEAUCOUP plus riche : Faction,
#   CountMinMax/Count, Probability, MissionDescription et StockDescription
#   imbriques sur plusieurs niveaux) -- les deux listes partagent la meme cle
#   'Name:', distinguees via _find_items_with_subsection_tracking() par la
#   derniere sous-section rencontree dans l'ordre du texte.
# ============================================================================

def find_drone_stock_items(doc: YamlDocument) -> List[YamlEntry]:
    """Garnison (Stock) des bases de drones PLANETE -- chaque entree a 'Name' et
    'Amount' (souvent 'Infinite'). Cherche dans TOUTE la section
    DroneBaseSetup par plage d'indices, peu importe le nombre de bases
    definies (DroneBases peut en theorie en contenir plusieurs).

    Utilise le suivi de sous-section (comme FreeDrones/SpaceVessels) pour ne
    retenir QUE les entrees sous 'Stock' -- indispensable sur un playfield
    ESPACE, ou DroneBaseSetup existe aussi mais sans section 'Stock' du tout
    (juste FreeDrones/SpaceVessels) : sans ce filtre, cette fonction
    remontait a tort TOUTES les entrees 'Name:' de la section entiere,
    confondant Stock/FreeDrones/SpaceVessels ensemble."""
    return _find_subsection_items(doc, "DroneBaseSetup", "Name", ["Stock", "FreeDrones", "SpaceVessels"], "Stock")


def find_free_drones_items(doc: YamlDocument) -> List[YamlEntry]:
    """Drones de patrouille libres (playfield ESPACE) -- section 'FreeDrones'
    au sein de DroneBaseSetup. Distingue de SpaceVessels (meme cle 'Name:')
    via la derniere sous-section rencontree dans l'ordre du texte."""
    return _find_subsection_items(doc, "DroneBaseSetup", "Name", ["FreeDrones", "SpaceVessels"], "FreeDrones")


def find_space_vessels_items(doc: YamlDocument) -> List[YamlEntry]:
    """Vaisseaux spatiaux (playfield ESPACE) -- section 'SpaceVessels' au sein de
    DroneBaseSetup. Structure la plus riche du module (Faction, CountMinMax,
    Probability, MissionDescription et StockDescription imbriques sur
    plusieurs niveaux -- non editables directement en tableau, voir
    _is_complex_param cote GUI, seuls les parametres simples type Faction/
    CountMinMax/Probability le sont)."""
    return _find_subsection_items(doc, "DroneBaseSetup", "Name", ["FreeDrones", "SpaceVessels"], "SpaceVessels")


# ============================================================================
# DroneSpawning, SpawnRateZones, SpawnZones, SpecialEffectsLocal/Global --
# sections de niveau racine independantes (contrairement a FreeDrones/
# SpaceVessels qui partagent DroneBaseSetup), pas besoin de suivi de
# sous-section : la plage d'indices standard suffit. Toutes confirmees sur un
# vrai playfield_akua.yaml.
# ============================================================================

def find_drone_spawning_items(doc: YamlDocument) -> List[YamlEntry]:
    """Zones de patrouille de drones planetaires (DroneSpawning > Random) --
    chaque entree a DronesMinMax/CenterX(/CenterY/CenterZ)."""
    return list_items(doc, "DroneSpawning", "DronesMinMax")


def find_spawn_rate_zones_items(doc: YamlDocument) -> List[YamlEntry]:
    """Zones de modulation du taux d'apparition de creatures autour d'un POI --
    chaque entree a SpawnAt (liste de POI ou [START]), Radius, et des
    multiplicateurs de taux."""
    return list_items(doc, "SpawnRateZones", "SpawnAt")


def find_spawn_zones_items(doc: YamlDocument) -> List[YamlEntry]:
    """Zones de creatures liees a un POI (different de CreatureSpawning, qui est
    par biome plutot que par POI) -- chaque entree a SpawnAt, Radius, et une
    sous-liste 'Entities' imbriquee (non editable directement en tableau, voir
    _is_complex_param cote GUI)."""
    return list_items(doc, "SpawnZones", "SpawnAt")


def find_special_effects_local_items(doc: YamlDocument) -> List[YamlEntry]:
    """Petits effets visuels locaux par biome (pollen, papillons, lucioles...) --
    chaque entree a Name, Biome, Time, MaxHeight (optionnel)."""
    return list_items(doc, "SpecialEffectsLocal", "Name")


def find_special_effects_global_items(doc: YamlDocument) -> List[YamlEntry]:
    """Effets globaux (meteo, effets lies au biome a plus grande echelle) --
    melange d'entrees 'Type: Weather' (InitialDelay/Delay/Lifetime) et
    d'entrees biome-specifiques (Biome/PlyDist/SpawnY) -- colonnes
    heterogenes, gerees normalement par l'union des cles existante."""
    return list_items(doc, "SpecialEffectsGlobal", "Name")
