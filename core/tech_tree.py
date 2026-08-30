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
from typing import Dict, List, Optional

from .ecf.model import EcfBlock, EcfProperty, add_property_line, remove_property_line
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


@dataclass
class TechTree:
    """Ensemble des noeuds de l'arbre, indexes pour un acces rapide par
    categorie et par nom. Construit par load_tech_tree() ci-dessous."""
    nodes: List[TechTreeNode] = field(default_factory=list)
    _by_name: Dict[str, TechTreeNode] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self._by_name = {n.name: n for n in self.nodes}

    def get(self, name: str) -> Optional[TechTreeNode]:
        return self._by_name.get(name)

    def categories(self) -> List[str]:
        """Categories reellement presentes, triees : d'abord celles de
        KNOWN_CATEGORY_ORDER (dans cet ordre), puis toute categorie
        supplementaire (scenario modde) par ordre alphabetique."""
        found = set()
        for n in self.nodes:
            found.update(n.categories)
        known = [c for c in KNOWN_CATEGORY_ORDER if c in found]
        extra = sorted(found - set(KNOWN_CATEGORY_ORDER))
        return known + extra

    def nodes_in_category(self, category: str) -> List[TechTreeNode]:
        return [n for n in self.nodes if category in n.categories]

    def levels(self) -> List[int]:
        """Colonnes de niveau reellement utilisees, triees -- pas une liste
        figee, pour rester correct sur un scenario qui introduirait un
        palier absent des fichiers vanilla observes."""
        return sorted({n.unlock_level for n in self.nodes})

    def children_of(self, name: str) -> List[TechTreeNode]:
        return [n for n in self.nodes if n.parent_name == name]


def _extract_nodes(path: Path, source: str) -> List[TechTreeNode]:
    doc = parse_ecf_file(path)
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
    nodes: List[TechTreeNode] = []
    for b in doc.iter_blocks():
        if b.kind not in accepted_kinds:
            continue
        name = b.get('Name') or b.get_property('Name')
        if not name:
            continue
        categories = parse_quoted_list(b.get_property('TechTreeNames'))
        if not categories or all(c in _EXCLUDED_CATEGORY_VALUES for c in categories):
            continue
        level_raw = b.get_property('UnlockLevel')
        if level_raw is None:
            # Un noeud avec une vraie categorie mais sans UnlockLevel n'a
            # jamais ete observe dans les vrais fichiers (voir docstring) --
            # exclu plutot que de deviner un niveau par defaut.
            continue
        try:
            unlock_level = int(level_raw.strip())
        except (ValueError, AttributeError):
            continue
        cost_raw = b.get_property('UnlockCost')
        try:
            unlock_cost = int(cost_raw.strip()) if cost_raw is not None else 0
        except ValueError:
            unlock_cost = 0
        parent = b.get_property('TechTreeParent')
        parent = parent.strip().strip('"') or None if parent else None
        custom_icon = b.get_property('CustomIcon')
        icon_key = custom_icon.strip() if custom_icon else name
        nodes.append(TechTreeNode(
            name=name, source=source, unlock_level=unlock_level, unlock_cost=unlock_cost,
            categories=categories, parent_name=parent, icon_key=icon_key, ecf_id=b.get('Id'),
        ))
    return nodes


def load_tech_tree(blocks_path: Optional[Path], items_path: Optional[Path]) -> TechTree:
    """Charge l'arbre technologique complet a partir des fichiers de la copie
    de travail. L'un des deux chemins peut etre None (fichier absent du
    scenario) -- l'arbre est alors construit avec ce qui est disponible."""
    nodes: List[TechTreeNode] = []
    if blocks_path is not None and blocks_path.exists():
        nodes.extend(_extract_nodes(blocks_path, 'block'))
    if items_path is not None and items_path.exists():
        nodes.extend(_extract_nodes(items_path, 'item'))
    return TechTree(nodes=nodes)


def set_unlock_level(path: Path, name: str, new_level: int) -> bool:
    """Ecrit un nouveau UnlockLevel sur le bloc/item identifie par Name, dans
    le fichier donne, et sauvegarde. Retourne False si le bloc est introuvable
    ou n'a pas de UnlockLevel existant (on ne cree jamais la propriete a
    l'aveugle -- un noeud sans UnlockLevel n'est de toute facon pas affiche
    dans l'arbre, voir _extract_nodes)."""
    doc = parse_ecf_file(path)
    for b in doc.iter_blocks():
        if b.get('Name') == name or b.get_property('Name') == name:
            if b.get_property('UnlockLevel') is None:
                return False
            if not b.set_property('UnlockLevel', str(new_level)):
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
                return False
            if not b.set_property('UnlockCost', str(new_cost)):
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
    virgule)."""
    doc = parse_ecf_file(path)
    for b in doc.iter_blocks():
        if b.get('Name') == name or b.get_property('Name') == name:
            if b.get_property('TechTreeNames') is None:
                return False
            if not b.set_property('TechTreeNames', f'"{new_category}"'):
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
