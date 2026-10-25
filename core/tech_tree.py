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
Arbre technologique (F3 en jeu) : lit/ecrit les proprietes ECF qui pilotent
l'arbre de deblocage par niveau de joueur, communes a BlocksConfig.ecf et
ItemsConfig.ecf. Structure CONFIRMEE sur de vrais BlocksConfig.ecf/
ItemsConfig.ecf (session du 28/08/2026, capture d'ecran F3 fournie par
l'utilisateur avec legende annotee) :

  UnlockLevel   : niveau joueur requis (int). Colonnes REELLEMENT observees :
                  0, 1, 2, 3, 4, 5, 7, 10, 12, 15, 20, 25 (union Blocks+Items).
  UnlockCost    : cout en points de deblocage a ce niveau (int).
  TechTreeNames : categorie(s) -- un seul onglet ("Weapons") ou plusieurs
                  ("Base,Capital Vessel", alors TOUJOURS entre guillemets vu
                  que le parseur ECF scinde une liste non protegee en plusieurs
                  paires -- voir core.ecf.validation._check_unquoted_commas).
                  "Hidden" (ou vide, ou commentee) = jamais affiche dans
                  l'arbre -- confirme sur un vrai item (TechTreeNames: Hidden
                  avec UnlockLevel: 1 tout de meme present : c'est bien la
                  VALEUR de la categorie qui exclut, pas la simple absence
                  d'UnlockLevel).
  TechTreeParent: Name du noeud parent (racine si absent). Un noeud racine
                  reel n'a PAS cette propriete du tout (pas de valeur vide).
  TechTreeSortIndex: ordre des voies au sein d'un parent et ordre des
                  onglets via « Nom$N » dans TechTreeNames (regles du
                  moteur, session du 25/10/2026 -- la vanilla ne les
                  utilise pas ; voir core/tech_tree_layout.py).
  CustomIcon    : nom d'icone explicite a utiliser (repli sur Name si absent)
                  -- confirme par le commentaire d'en-tete du vrai
                  BlocksConfig.ecf : "Use with an existing Icon to show it
                  ingame, f.ex. 'CustomIcon: DetectorSVT1'".

Categories reelles observees (ordre confirme identique a l'UI F3) : Base,
Capital Vessel, Small Vessel, Hover Vessel, Misc, Tools, Weapons.

Ne couvre PAS les barres de couleur "constructeur capable de crafter" (issues
de Target: dans Templates.ecf) -- explicitement hors perimetre de la V1 a la
demande de l'utilisateur, faute de vrai Templates.ecf disponible cette
session pour verifier le mapping exact code -> libelle affiche.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .ecf.model import EcfBlock, EcfProperty, add_property_line, remove_property_line
from .ecf.doc_cache import get_parsed_doc
from .ecf.parser import parse_ecf_file
from .fsutil import atomic_write_text
from .parsers_utils import parse_quoted_list

# Ordre confirme par la capture d'ecran F3 fournie (onglets de gauche a
# droite). Sert uniquement a trier les categories connues en premier ; toute
# categorie presente dans les fichiers mais absente d'ici (scenario modde
# avec ses propres categories) est ajoutee a la suite, triee alphabetiquement,
# plutot que d'etre perdue.
KNOWN_CATEGORY_ORDER = [
    "Base", "Capital Vessel", "Small Vessel", "Hover Vessel", "Misc", "Tools", "Weapons",
]

# Valeurs de TechTreeNames qui excluent un noeud de l'arbre affiche -- voir
# le docstring du module (cas reel confirme : HeavyPistol a la fois
# TechTreeNames=Hidden ET UnlockLevel=1).
_EXCLUDED_CATEGORY_VALUES = {"Hidden", ""}


@dataclass
class TechTreeNode:
    """Un bloc ou item present dans l'arbre technologique."""
    name: str                          # Name ECF -- identite unique dans son fichier
    source: str                        # 'block' ou 'item'
    unlock_level: int
    unlock_cost: int
    categories: List[str]              # ex: ['Base', 'Capital Vessel']
    parent_name: Optional[str] = None  # None = noeud racine
    icon_key: str = ""                 # CustomIcon si present, sinon Name
    ecf_id: Optional[str] = None       # Id ECF si present (Items/certains Blocks)
    sort_index: int = 0                # TechTreeSortIndex (tri des voies, voir layout)
    seq: int = 0                       # ordre de declaration dans le fichier


@dataclass
class TechTree:
    """Ensemble des noeuds de l'arbre, indexes pour un acces rapide par
    categorie et par nom. Construit par load_tech_tree() ci-dessous."""
    nodes: List[TechTreeNode] = field(default_factory=list)
    _by_name: Dict[str, TechTreeNode] = field(default_factory=dict, repr=False)
    # Indice d'onglet explicite « Nom$N » vu dans un TechTreeNames (jeu :
    # ConfigTree.OpenNetwork). Première rencontre gagne ; vide en vanilla.
    category_sort_index: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._by_name = {n.name: n for n in self.nodes}

    def get(self, name: str) -> Optional[TechTreeNode]:
        return self._by_name.get(name)

    def categories(self) -> List[str]:
        """Categories reellement affichables (Hidden exclu), ordonnees comme
        le F3 : categories a indice explicite $N d'abord (croissant), puis
        l'ordre vanilla confirme par captures, puis le reste par ordre
        alphabetique (repli : entre egaux le jeu conserve un ordre de hachage
        Mono non reproductible -- voir core/tech_tree_layout.py, regle 6)."""
        found = set()
        for n in self.nodes:
            found.update(c for c in n.categories if c not in _EXCLUDED_CATEGORY_VALUES)
        known = [c for c in KNOWN_CATEGORY_ORDER if c in found]
        extra = sorted(found - set(KNOWN_CATEGORY_ORDER))

        def _key(c: str) -> Tuple:
            idx = self.category_sort_index.get(c, 0)
            ordered = idx if idx > 0 else None
            fallback = known.index(c) if c in known else len(known) + extra.index(c)
            return (0 if ordered is not None else 1, ordered if ordered is not None else 0, fallback)

        return sorted(found, key=_key)

    def nodes_in_category(self, category: str) -> List[TechTreeNode]:
        """Noeuds DECLARANT la categorie (feuilles potentielles -- le jeu
        n'en garde que celles avec UnlockLevel >= 1, voir tech_tree_layout ;
        l'arbre affiche inclut en plus leurs ancetres, qui peuvent ne pas
        declarer la categorie)."""
        return [n for n in self.nodes if category in n.categories]

    def levels(self) -> List[int]:
        """Colonnes de niveau reellement utilisees, triees -- pas une liste
        figee, pour rester correct sur un scenario qui introduirait un
        palier absent des fichiers vanilla observes."""
        return sorted({n.unlock_level for n in self.nodes})

    def children_of(self, name: str) -> List[TechTreeNode]:
        return [n for n in self.nodes if n.parent_name == name]


def _node_name(block: EcfBlock) -> Optional[str]:
    return block.get('Name') or block.get_property('Name')


def _index_by_name(doc, accepted_kinds, patches_only: bool = False) -> Dict[str, EcfBlock]:
    """Index Name -> bloc. La DERNIERE declaration gagne (convention du
    projet, voir market_balance.load_index). patches_only ne garde que les
    '+Block'/'+Item', seules declarations de la config de base que le jeu
    reporte sur les blocs du scenario (voir _effective)."""
    index: Dict[str, EcfBlock] = {}
    for b in doc.iter_blocks():
        if patches_only:
            if not b.kind.startswith('+'):
                continue
        elif b.kind not in accepted_kinds:
            continue
        name = _node_name(b)
        if name:
            index[name] = b
    return index


def _base_patches(path: Path, vanilla_root: Optional[str]) -> Dict[str, EcfBlock]:
    """Patchs '+Block'/'+Item' de la config de BASE du jeu pour le meme
    fichier (vanilla_root pointe sur le dossier Content de l'installation).
    Vide si le chemin n'est pas renseigne ou le fichier absent."""
    if not vanilla_root:
        return {}
    base = Path(vanilla_root) / 'Configuration' / path.name
    if not base.exists():
        return {}
    return _index_by_name(get_parsed_doc(base), set(), patches_only=True)


def _effective(index: Dict[str, EcfBlock], patches: Dict[str, EcfBlock],
               name: str, key: str, depth: int = 0):
    """Valeur d'une propriete telle que le JEU la voit, dans cet ordre :
    1. declaration du scenario, 2. patch '+Block'/'+Item' de la config de
    base, 3. chaine Ref (memes regles, garde de profondeur 12).

    Le point 2 est le piege du 24/10/2026 : OreScanner n'a AUCUNE propriete
    d'arbre dans le scenario (les quatre lignes sont commentees), affiche
    pourtant dans l'onglet Outils en jeu -- la vanilla le patche en '+Item'
    avec TechTreeNames: Tools, et le jeu reporte ce patch. Commenter une
    propriete dans le scenario ne l'efface donc pas : il faut la redeclarer
    explicitement pour la neutraliser."""
    b = index.get(name)
    if b is not None:
        value = b.get_property(key)
        if value is not None:
            return value
    patch = patches.get(name)
    if patch is not None:
        value = patch.get_property(key)
        if value is not None:
            return value
    if depth >= 12:
        return None
    ref = b.get_property('Ref') if b is not None else None
    if not ref and patch is not None:
        ref = patch.get_property('Ref')
    if not ref:
        return None
    return _effective(index, patches, ref.strip().strip('"'), key, depth + 1)


def _split_category_token(token: str) -> Tuple[str, Optional[int]]:
    """Un jeton TechTreeNames peut porter un indice d'onglet explicite
    « Nom$2 » que le jeu strip et memorise (ConfigTree.OpenNetwork : le nom
    SANS le suffixe devient la categorie, le numero son ordre d'onglet).
    Retourne (nom_nettoye, indice ou None)."""
    token = token.strip()
    if '$' not in token:
        return token, None
    name, _, suffix = token.rpartition('$')
    try:
        return name, int(suffix.strip())
    except ValueError:
        return token, None


def _extract_nodes(path: Path, source: str, vanilla_root: Optional[str] = None,
                   category_index: Optional[Dict[str, int]] = None) -> List[TechTreeNode]:
    # Parse via le CACHE (voir core/ecf/doc_cache.py -- retour utilisateur du
    # 31/08/2026 : latence de plusieurs secondes a chaque clic dans l'arbre,
    # chaque clic re-parsant des fichiers entiers) : l'ouverture du dialogue
    # pre-chauffe ainsi le cache, et les clics suivants ne re-parsent plus
    # rien tant que les fichiers ne changent pas. Lecture seule : les
    # TechTreeNode construits ci-dessous sont des copies, jamais le document.
    doc = get_parsed_doc(path)
    base_kind = 'Block' if source == 'block' else 'Item'
    # Un vrai BlocksConfig.ecf/ItemsConfig.ecf vanilla (confirme sur le fichier
    # Steam reel, session du 29/08/2026) contient aussi des blocs '+Block'/
    # '+Item' (patch/hotfix officiel qui modifie un bloc existant par Id/Ref
    # plutot que de le redefinir integralement) -- exclus a tort par un filtre
    # sur 'Block' seul, ce qui faisait chuter le nombre de noeuds detectes de
    # 367 a 13 sur ce fichier reel. Les deux variantes portent les memes
    # proprietes (TechTreeNames etc.) directement sur elles-memes, sans
    # necessiter de resolution via la chaine Ref -- confirme sur
    # FuelTankMSLarge (+Block), TechTreeNames present explicitement.
    accepted_kinds = {base_kind, '+' + base_kind}
    index = _index_by_name(doc, accepted_kinds)
    patches = _base_patches(path, vanilla_root)
    nodes: List[TechTreeNode] = []
    seq = 0
    for b in doc.iter_blocks():
        if b.kind not in accepted_kinds:
            continue
        name = _node_name(b)
        if not name:
            continue
        seq += 1
        categories: List[str] = []
        for token in parse_quoted_list(_effective(index, patches, name, 'TechTreeNames')) or []:
            clean, tab_index = _split_category_token(token)
            if not clean:
                continue
            categories.append(clean)
            if tab_index is not None and category_index is not None:
                # Premiere rencontre gagne ; le jeu LEVE une exception sur un
                # conflit d'indices -- l'editeur reste permissif.
                category_index.setdefault(clean, tab_index)
        # Un noeud sans AUCUNE propriete d'arbre n'entre jamais dans le
        # modele. Un noeud avec TechTreeParent est garde MEME si toutes ses
        # categories sont exclues (Hidden) ou sans UnlockLevel : le jeu
        # l'insere quand meme comme ANCIEN des chaines qui le referencent
        # (ConfigTree.RebuildSelection ne filtre que les FEUILLES) -- c'est
        # le piege du 24/10 : commenter/masquer n'efface pas un ancetre.
        has_parent = _effective(index, patches, name, 'TechTreeParent')
        if not categories and not has_parent:
            continue
        level_raw = _effective(index, patches, name, 'UnlockLevel')
        try:
            unlock_level = int(level_raw.strip()) if level_raw is not None else 0
        except (ValueError, AttributeError):
            unlock_level = 0
        cost_raw = _effective(index, patches, name, 'UnlockCost')
        try:
            unlock_cost = int(cost_raw.strip()) if cost_raw is not None else 0
        except ValueError:
            unlock_cost = 0
        parent = has_parent.strip().strip('"') or None if has_parent else None
        custom_icon = _effective(index, patches, name, 'CustomIcon')
        icon_key = custom_icon.strip() if custom_icon else name
        sort_raw = _effective(index, patches, name, 'TechTreeSortIndex')
        try:
            sort_index = int(sort_raw.strip()) if sort_raw is not None else 0
        except (ValueError, AttributeError):
            sort_index = 0
        nodes.append(TechTreeNode(
            name=name, source=source, unlock_level=unlock_level, unlock_cost=unlock_cost,
            categories=categories, parent_name=parent, icon_key=icon_key, ecf_id=b.get('Id'),
            sort_index=sort_index, seq=seq,
        ))
    return nodes


def load_tech_tree(blocks_path: Optional[Path], items_path: Optional[Path],
                   vanilla_root: Optional[str] = None) -> TechTree:
    """Charge l'arbre technologique complet a partir des fichiers de la copie
    de travail. L'un des deux chemins peut etre None (fichier absent du
    scenario) -- l'arbre est alors construit avec ce qui est disponible.

    vanilla_root = dossier Content de l'installation du jeu (defaut : reglage
    de l'application) ; sert a reporter les patchs '+Block'/'+Item' de la
    config de base que le jeu applique sur les blocs du scenario. Passe ""
    pour un arbre strictement limite au scenario (tests, CLI)."""
    if vanilla_root is None:
        from .settings import get_vanilla_content_path
        vanilla_root = get_vanilla_content_path()
    nodes: List[TechTreeNode] = []
    category_index: Dict[str, int] = {}
    if blocks_path is not None and blocks_path.exists():
        nodes.extend(_extract_nodes(blocks_path, 'block', vanilla_root, category_index))
    if items_path is not None and items_path.exists():
        nodes.extend(_extract_nodes(items_path, 'item', vanilla_root, category_index))
    return TechTree(nodes=nodes, category_sort_index=category_index)


def set_unlock_level(path: Path, name: str, new_level: int) -> bool:
    """Ecrit un nouveau UnlockLevel sur le bloc/item identifie par Name, dans
    le fichier donne, et sauvegarde. CREE la propriete si elle est absente :
    l'arbre affiche aussi les noeuds dont le niveau vient d'un patch de la
    config de base ou d'un Ref (voir _effective) -- sans creation, editer
    OreScanner echouerait au lieu de fixer explicitement la valeur."""
    doc = parse_ecf_file(path)
    for b in doc.iter_blocks():
        if b.get('Name') == name or b.get_property('Name') == name:
            if b.get_property('UnlockLevel') is None:
                add_property_line(b, [('UnlockLevel', str(new_level))])
            elif not b.set_property('UnlockLevel', str(new_level)):
                return False
            atomic_write_text(path, doc.render())
            return True
    return False


def set_unlock_cost(path: Path, name: str, new_cost: int) -> bool:
    """Meme principe que set_unlock_level, pour UnlockCost (edition par
    double-clic, voir gui/tech_tree_widget.py)."""
    doc = parse_ecf_file(path)
    for b in doc.iter_blocks():
        if b.get('Name') == name or b.get_property('Name') == name:
            if b.get_property('UnlockCost') is None:
                add_property_line(b, [('UnlockCost', str(new_cost))])
            elif not b.set_property('UnlockCost', str(new_cost)):
                return False
            atomic_write_text(path, doc.render())
            return True
    return False


def move_to_category(path: Path, name: str, new_category: str) -> bool:
    """Deplace le bloc/item vers une nouvelle categorie UNIQUE -- remplace
    integralement TechTreeNames (ne conserve pas les anciennes categories),
    comportement confirme aupres de l'utilisateur ('deplacer', pas
    'ajouter'). La valeur est reecrite entre guillemets meme pour une seule
    categorie (compatible avec le parseur dans tous les cas, evite tout
    risque de scission accidentelle si le nom de categorie contenait une
    virgule). CREE la propriete si elle vient d'un patch/Ref."""
    doc = parse_ecf_file(path)
    for b in doc.iter_blocks():
        if b.get('Name') == name or b.get_property('Name') == name:
            if b.get_property('TechTreeNames') is None:
                add_property_line(b, [('TechTreeNames', f'"{new_category}"')])
            elif not b.set_property('TechTreeNames', f'"{new_category}"'):
                return False
            atomic_write_text(path, doc.render())
            return True
    return False


def set_tech_tree_parent(path: Path, name: str, new_parent: Optional[str]) -> bool:
    """Change le parent (TechTreeParent) du bloc/item -- utilise par le
    glisser-deposer vertical avec selection de parent (voir
    gui/tech_tree_widget.py, demande explicite de l'utilisateur du
    29/08/2026). Contrairement a set_unlock_level/set_unlock_cost/
    move_to_category, PEUT creer la propriete si elle est absente (noeud
    auparavant racine) : action explicite et deliberee de l'utilisateur
    (choix direct du parent dans l'interface), pas une supposition -- voir
    add_property_line. new_parent=None supprime la propriete (redevient
    racine), coherent avec le fait qu'un vrai noeud racine n'a jamais cette
    propriete du tout (jamais une valeur vide -- voir docstring du module)."""
    doc = parse_ecf_file(path)
    for b in doc.iter_blocks():
        if b.get('Name') == name or b.get_property('Name') == name:
            if new_parent is None:
                # TechTreeParent est presque toujours sa PROPRE ligne
                # (EcfProperty enfant), pas une paire sur la ligne
                # d'ouverture -- block.remove() seul ne suffit pas (bug reel
                # trouve en testant cette fonction : la suppression semblait
                # reussir mais ne persistait rien). Deja absent = etat deja
                # atteint, pas un echec.
                b.remove('TechTreeParent')
                for child in list(b.children):
                    if isinstance(child, EcfProperty) and child.get('TechTreeParent') is not None:
                        remove_property_line(b, child)
            elif b.get_property('TechTreeParent') is not None:
                if not b.set_property('TechTreeParent', new_parent):
                    return False
            else:
                add_property_line(b, [('TechTreeParent', new_parent)])
            atomic_write_text(path, doc.render())
            return True
    return False


# ---------------------------------------------------------------------------
# Edition GENERIQUE depuis la fiche d'information de l'arbre technologique
# (demande du 31/08/2026 : equilibrage rapide directement depuis l'arbre).
# Meme discipline que les fonctions ci-dessus : parse -> mutation precise ->
# reecriture atomique round-trip ; jamais de creation a l'aveugle (les
# fonctions add_* sont les seules a creer, sur action explicite).
# ---------------------------------------------------------------------------

def find_block_by_name(path: Path, name: str) -> Optional[EcfBlock]:
    """Retrouve le bloc/item par Name dans le fichier donne. Parse via le
    CACHE de documents (core/ecf/doc_cache.py -- lectures fiche uniquement ;
    apres toute ecriture, le (mtime, taille) change et la lecture suivante
    re-parse un document frais). None si absent."""
    if path is None or not path.exists():
        return None
    doc = get_parsed_doc(path)
    for b in doc.iter_blocks():
        if b.get('Name') == name or b.get_property('Name') == name:
            return b
    return None


def _locate_property(block: EcfBlock, key: str, old_value: Optional[str]):
    """Retrouve la cible d'une edition : l'EcfBlock si la paire est sur sa
    ligne d'ouverture, sinon la premiere EcfProperty (recursivement, ordre du
    fichier) portant la paire (key, old_value) -- ou (key, n'importe quelle
    valeur) si old_value est None. None si introuvable."""
    for k, v in block.pairs:
        if k == key and (old_value is None or v == old_value):
            return block

    def _walk(node: EcfBlock):
        for child in node.children:
            if isinstance(child, EcfProperty):
                for k, v in child.pairs:
                    if k == key and (old_value is None or v == old_value):
                        return child
            elif isinstance(child, EcfBlock):
                found = _walk(child)
                if found is not None:
                    return found
        return None
    return _walk(block)


def set_block_property(path: Path, name: str, key: str, new_value: str,
                        old_value: Optional[str] = None) -> bool:
    """Modifie UNE propriete du bloc/item identifie par Name (peu importe sa
    position : ligne d'ouverture ou ligne enfant, meme imbriquee) et
    sauvegarde. Retourne False si le bloc ou la propriete est introuvable."""
    doc = parse_ecf_file(path)
    for b in doc.iter_blocks():
        if b.get('Name') == name or b.get_property('Name') == name:
            target = _locate_property(b, key, old_value)
            if target is None:
                return False
            if isinstance(target, EcfBlock):
                if not target.set(key, new_value):
                    return False
            else:
                for i, (k, v) in enumerate(target.pairs):
                    if k == key and (old_value is None or v == old_value):
                        target.pairs[i] = (key, new_value)
                        target.dirty = True
                        break
                else:
                    return False
            atomic_write_text(path, doc.render())
            return True
    return False


def add_block_property(path: Path, name: str, key: str, value: str) -> bool:
    """Ajoute UNE propriete au bloc/item identifie par Name (action explicite
    de l'utilisateur depuis la fiche). Retourne False si le bloc est
    introuvable ou la cle vide."""
    if not key.strip():
        return False
    doc = parse_ecf_file(path)
    for b in doc.iter_blocks():
        if b.get('Name') == name or b.get_property('Name') == name:
            add_property_line(b, [(key.strip(), value)])
            atomic_write_text(path, doc.render())
            return True
    return False


def remove_block_property(path: Path, name: str, key: str,
                           old_value: Optional[str] = None) -> bool:
    """Supprime UNE propriete (ligne enfant uniquement -- les paires de la
    ligne d'ouverture comme Id/Name sont structurelles et ne sont JAMAIS
    supprimees depuis la fiche). Retourne False si introuvable."""
    doc = parse_ecf_file(path)
    for b in doc.iter_blocks():
        if b.get('Name') == name or b.get_property('Name') == name:
            for child in list(b.children):
                if isinstance(child, EcfProperty):
                    for k, v in child.pairs:
                        if k == key and (old_value is None or v == old_value):
                            remove_property_line(b, child)
                            atomic_write_text(path, doc.render())
                            return True
            return False
    return False


def _find_template_block(path: Path, template_name: str):
    doc = parse_ecf_file(path)
    for b in doc.iter_blocks():
        if b.kind in ("Template", "+Template") and \
                (b.get('Name') == template_name or b.get_property('Name') == template_name):
            return doc, b
    return doc, None


def _template_child_inputs(template: EcfBlock) -> Optional[EcfBlock]:
    for child in template.children:
        if isinstance(child, EcfBlock) and child.kind == 'Child Inputs':
            return child
    return None


def set_template_ingredient(templates_path: Path, template_name: str, key: str,
                             new_quantity: str, old_quantity: Optional[str] = None) -> bool:
    """Modifie la quantite d'UN ingredient (section 'Child Inputs' du
    Template) dans Templates.ecf -- edition directe depuis la fiche de
    l'arbre technologique. Retourne False si Template/ingredient introuvable."""
    doc, template = _find_template_block(templates_path, template_name)
    if template is None:
        return False
    child_inputs = _template_child_inputs(template)
    if child_inputs is None:
        return False
    for child in child_inputs.children:
        if isinstance(child, EcfProperty):
            for i, (k, v) in enumerate(child.pairs):
                if k == key and (old_quantity is None or v == old_quantity):
                    child.pairs[i] = (key, new_quantity)
                    child.dirty = True
                    atomic_write_text(templates_path, doc.render())
                    return True
    return False


def add_template_ingredient(templates_path: Path, template_name: str,
                             key: str, quantity: str) -> bool:
    """Ajoute UN ingredient au Template (action explicite depuis la fiche) --
    passe par add_child_inputs qui cree OU complete la section 'Child
    Inputs' avec l'indent correct quel que soit le niveau."""
    if not key.strip():
        return False
    from .ecf.block_creation import add_child_inputs
    doc, template = _find_template_block(templates_path, template_name)
    if template is None:
        return False
    add_child_inputs(template, [(key.strip(), quantity)])
    atomic_write_text(templates_path, doc.render())
    return True


def remove_template_ingredient(templates_path: Path, template_name: str, key: str,
                                old_quantity: Optional[str] = None) -> bool:
    """Supprime UN ingredient du Template. Retourne False si introuvable."""
    doc, template = _find_template_block(templates_path, template_name)
    if template is None:
        return False
    child_inputs = _template_child_inputs(template)
    if child_inputs is None:
        return False
    for child in list(child_inputs.children):
        if isinstance(child, EcfProperty):
            for k, v in child.pairs:
                if k == key and (old_quantity is None or v == old_quantity):
                    remove_property_line(child_inputs, child)
                    atomic_write_text(templates_path, doc.render())
                    return True
    return False


def set_template_output_count(templates_path: Path, template_name: str,
                               new_count: str) -> bool:
    """Modifie OutputCount (scalaire du Template). Retourne False si absent
    (pas de creation a l'aveugle -- coherent avec set_unlock_level)."""
    doc, template = _find_template_block(templates_path, template_name)
    if template is None:
        return False
    if template.get_property('OutputCount') is None:
        return False
    if not template.set_property('OutputCount', new_count):
        return False
    atomic_write_text(templates_path, doc.render())
    return True
