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
Disposition des noeuds de l'arbre technologique (F3) -- REECRIT le 25/10/2026
sur l'ALGORITHME EXACT DU JEU (fenetre PanelTechTree : construction de
l'arbre par le chargeur de configs, disposition par la fenetre ; regles
verifiees contre le chargement reel du jeu, build 25/09/2026).

Toutes les regles ci-dessous sont celles du moteur, pas des deductions :

1. ARBRE PAR CATEGORIE = union des CHAINES. Pour chaque feuille (item ou bloc
   declarant la categorie avec UnlockLevel >= 1), le jeu remonte la chaine
   TechTreeParent (parent resolu par NOM, item d'abord puis bloc ; max 7
   ancetres) et insere la chaine racine -> feuille dans l'arbre de la
   categorie. Un ANCIEN de la chaine peut ne PAS declarer la categorie
   (ex: TechTreeNames: Hidden) : il apparait quand meme comme noeud interne
   -- c'est ce que l'ancienne heuristique « memes categories » approximait.

2. ORDRE D'INSERTION = ordre de traitement des feuilles : ITEMS d'abord (Id
   croissant), PUIS BLOCS (Id croissant pour les blocs avec Id, puis ordre de
   declaration pour les sans-Id ; en vanilla ce second ordre == ordre du
   fichier). Un enfant apparait a la position ou la PREMIERE feuille de son
   sous-arbre a ete traitee.

3. TRI STABLE par TechTreeSortIndex (valeur <= 0 -> dernier, l'ordre
   d'insertion est conserve entre egaux) applique a CHAQUE niveau, racines
   comprises (tri du chargeur de l'arbre). Vanilla n'utilise jamais cette
   propriete : l'ordre d'insertion decide alors de tout.

4. COLONNES = INDEX DU NIVEAU parmi les niveaux DISTINCTS de l'arbre de la
   categorie, triés (ConfigTree.FindView + ResolveProcess). PAS les valeurs
   brutes, PAS une grille fixe : l'ancienne liste figee MILESTONE_LEVELS
   [1,3,5,7,10,12,15,20,25] n'etait que le resultat de cet algorithme sur la
   vanilla. Un scenario qui n'a que les niveaux 2 et 9 a deux colonnes.

5. LIGNES : parcours en profondeur des enfants dans l'ordre final ; un noeud
   est place a la colonne de son niveau (cellules vides de remplissage si la
   colonne courante est en retard) ; s'il a des enfants ils continuent sur la
   MEME ligne ; une FEUILLE termine sa ligne -- la voie suivante demarre
   dessous (fenetre F3, ToggleDomain). Il n'y a donc pas de
   « continuateur » choisi : TOUS les enfants restent sur la ligne du parent
   tant qu'aucun n'est une feuille, et chaque feuille coupe.
   (L'ancienne regle « premier enfant declare de memes categories continue »
   etait une approximation de ce mecanisme, contredite dans des cas limites.)

6. ORDRE DES ONGLETS : un jeton TechTreeNames peut porter un indice explicite
   « Nom$2 » (le chargeur de l'arbre le strip et le memorise) ; les
   categories avec indice positif viennent d'abord par indice croissant, les
   autres apres, hors « Hidden ». Entre egaux le jeu conserve l'ordre
   d'iteration d'un Dictionary Mono (ordre de hachage, non reproductible
   simplement) : repli de l'editeur = ordre vanilla confirme par captures
   (KNOWN_CATEGORY_ORDER) puis decouvrete. Vanilla n'a aucun $N.

Isole de gui/tech_tree_widget.py pour rester testable sans PyQt6.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .tech_tree import TechTree, TechTreeNode

# Le jeu (ConfigTree.FindDeployment) jette au 8e ANCESTRE d'une chaine
# (compteur global > 5 a l'entree) — l'editeur s'arrete a la meme borne pour
# rester fidele, proprement (sans exception) pour ne jamais faire disparaitre
# le reste de l'arbre.
_MAX_ANCESTORS = 7


@dataclass
class NodePosition:
    node_name: str
    x_fraction: float      # colonne (index du niveau dans CategoryLayout.levels)
    row: int
    branches_from_parent: bool  # True = ligne differente de celle du parent (coude)
    parent_name: Optional[str] = None  # parent DANS l'arbre de la categorie (None = racine)


@dataclass
class CategoryLayout:
    """Resultat du calcul pour UNE categorie : tout ce dont le widget a
    besoin -- niveaux d'en-tete, noeuds a dessiner (l'arbre complet, ancetres
    inclus), position de chacun."""
    levels: List[int] = field(default_factory=list)
    draw_order: List[TechTreeNode] = field(default_factory=list)
    positions: Dict[str, NodePosition] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Ordre de traitement des feuilles (regle 2)
# ---------------------------------------------------------------------------

def _int_id(node: TechTreeNode) -> Optional[int]:
    try:
        return int(str(node.ecf_id).strip())
    except (TypeError, ValueError):
        return None


def _leaf_sort_key(node: TechTreeNode) -> Tuple:
    """Items d'abord (Id croissant), puis blocs avec Id (Id croissant), puis
    blocs sans Id (ordre de declaration). Repli sur l'ordre de declaration
    pour un item sans Id (jamais observe)."""
    iid = _int_id(node)
    if node.source == 'item':
        return (0, iid if iid is not None else 10 ** 9, node.seq)
    if iid is not None:
        return (1, iid, node.seq)
    return (2, 0, node.seq)


def _sort_key_stable(node: TechTreeNode) -> float:
    """Tri stable par TechTreeSortIndex ; <= 0 passe APRES tout indice positif
    (ConfigTree.OrderFunction : OrderBy(v <= 0 ? int.MaxValue : v))."""
    return float('inf') if node.sort_index <= 0 else float(node.sort_index)


@dataclass
class _TreeNode:
    node: TechTreeNode
    children: List['_TreeNode'] = field(default_factory=list)


def _build_category_tree(tree: TechTree, category: str) -> List[_TreeNode]:
    """Reproduit ConfigTree.RebuildSelection : chaines feuille->ancetres
    inserees racine->feuille, puis tri stable par TechTreeSortIndex."""
    by_key: Dict[Tuple[str, str], TechTreeNode] = {(n.source, n.name): n for n in tree.nodes}
    # Le jeu resout un parent par NOM, item d'abord, bloc ensuite
    # (ConfigTree.FindDeployment : DomainLayout.ChangeCondition puis
    # PartitionDictionary.GenerateWindow).
    by_name: Dict[str, TechTreeNode] = {}
    for n in tree.nodes:
        if n.source == 'item':
            by_name.setdefault(n.name, n)
    for n in tree.nodes:
        if n.source == 'block':
            by_name.setdefault(n.name, n)

    roots: List[_TreeNode] = []
    placed: Dict[Tuple[str, str], _TreeNode] = {}

    leaves = [n for n in tree.nodes if category in n.categories and n.unlock_level >= 1]
    for leaf in sorted(leaves, key=_leaf_sort_key):
        # Chaine feuille -> racine (le jeu la construit en remontant puis
        # insere en partant de la racine).
        chain: List[TechTreeNode] = [leaf]
        seen = {(leaf.source, leaf.name)}
        current = leaf
        while len(chain) <= _MAX_ANCESTORS:
            parent_name = current.parent_name
            if not parent_name:
                break
            parent = by_name.get(parent_name)
            if parent is None or (parent.source, parent.name) in seen:
                break
            chain.append(parent)
            seen.add((parent.source, parent.name))
            current = parent
        # Insertion racine -> feuille (ConfigTree.SplitControl)
        level_children = roots
        for tn in reversed(chain):
            key = (tn.source, tn.name)
            existing = placed.get(key)
            if existing is None:
                existing = _TreeNode(node=tn)
                level_children.append(existing)
                placed[key] = existing
            level_children = existing.children

    def _sort_level(children: List[_TreeNode]) -> List[_TreeNode]:
        # Recursif d'abord (ConfigTree.OrderFunction trie les petits avant
        # les grands), puis tri stable du niveau courant.
        for child in children:
            if child.children:
                _sort_level(child.children)
        children.sort(key=lambda tn: _sort_key_stable(tn.node))
        return children

    return _sort_level(roots)


def compute_layout(tree: TechTree, category: str) -> CategoryLayout:
    """Calcule la disposition EXACTE du F3 pour une categorie (voir le
    docstring du module pour l'algorithme et sa source dans le jeu)."""
    roots = _build_category_tree(tree, category)

    draw_order: List[TechTreeNode] = []
    tree_nodes: List[TechTreeNode] = []

    def _collect(tn_list: List[_TreeNode]) -> None:
        for tn in tn_list:
            draw_order.append(tn.node)
            tree_nodes.append(tn.node)
            if tn.children:
                _collect(tn.children)

    _collect(roots)

    levels = sorted({n.unlock_level for n in tree_nodes})
    tier_col = {level: i for i, level in enumerate(levels)}

    positions: Dict[str, NodePosition] = {}
    # Cellule courante (col, row) -- reproduit ToggleDomain : une feuille
    # termine sa ligne, les enfants continuent sur la ligne du parent.
    state = {'col': 0, 'row': 0}

    def _walk(tn_list: List[_TreeNode], tree_parent: Optional[str], parent_row: Optional[int]) -> None:
        for tn in tn_list:
            target = tier_col[tn.node.unlock_level]
            if state['col'] < target:
                state['col'] = target  # cellules vides de remplissage
            col, row = state['col'], state['row']
            name = tn.node.name
            positions[name] = NodePosition(
                node_name=name,
                x_fraction=float(col),
                row=row,
                branches_from_parent=parent_row is not None and row != parent_row,
                parent_name=tree_parent,
            )
            state['col'] = col + 1
            if tn.children:
                _walk(tn.children, name, row)
            else:
                state['row'] += 1  # la feuille coupe la ligne (regle 5)
                state['col'] = 0

    _walk(roots, None, None)

    return CategoryLayout(levels=levels, draw_order=draw_order, positions=positions)


def nearest_level(x_fraction: float, levels: List[int]) -> Optional[int]:
    """Niveau le plus proche d'une abscisse en unites de colonne -- utilisé
    par le glisser-deposer du widget pour aimanter sur un niveau REEL de la
    categorie (les colonnes affichées sont les niveaux presents, regle 4)."""
    if not levels:
        return None
    idx = max(0, min(len(levels) - 1, round(x_fraction)))
    return levels[idx]
