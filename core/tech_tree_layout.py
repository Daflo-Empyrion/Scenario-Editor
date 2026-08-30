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
Positionnement visuel des noeuds de l'arbre technologique pour une categorie
donnee -- REECRIT le 28/08/2026 apres comparaison directe avec des captures
d'ecran F3 EN JEU (10 captures fournies par l'utilisateur) et les vraies
valeurs ECF correspondantes. Deux erreurs corrigees par rapport a la version
precedente :

1. GRILLE DE NIVEAUX FIXE, pas une colonne par valeur reellement trouvee dans
   les fichiers. Les 9 jalons ci-dessous (MILESTONE_LEVELS) sont ceux
   affiches en-tete du vrai F3 (identiques sur les 10 captures). Un noeud
   dont le niveau tombe ENTRE deux jalons (ex: niveau 2 ou 4, confirmes
   presents dans ItemsConfig.ecf/BlocksConfig.ecf reels alors qu'ils
   n'apparaissent PAS en en-tete) est positionne par INTERPOLATION LINEAIRE
   entre les deux jalons encadrants, pas sur une colonne dediee.

2. DISPOSITION EN VOIES (lanes), pas une ligne par enfant. Verifie sur 2
   chaines reelles completes (recoupees avec les couts affiches sur les
   captures, qui correspondent exactement) :
   - Core(cout 0) -> CPUExtenderBAT2(7) -> CPUExtenderBAT3(12) ->
     CPUExtenderBAT4R(20) -> CPUExtenderBAT5(25)
   - GeneratorBA(4) -> GeneratorMS(14) -> GeneratorMST2(20) ->
     FusionReactorSmall(30) -> FusionReactorLarge(40)
   Regle deduite et confirmee sur ces deux chaines (et leurs branches
   secondaires, ex: Core a aussi CoreT2Large(20) et Eden_CPUExtenderAuxCV(150)
   qui NE continuent PAS la voie principale) : quand un noeud a plusieurs
   enfants, SEUL celui au UnlockCost LE PLUS BAS continue sur la MEME voie
   (meme ligne horizontale) ; chaque AUTRE enfant demarre une NOUVELLE voie,
   reliee par un coude (segment vertical puis horizontal) -- voir
   gui/tech_tree_widget.py pour le dessin du coude.

3. ORDRE VERTICAL des voies (quelle voie apparait au-dessus de quelle autre) :
   verifie le 29/08/2026 sur le vrai BlocksConfig.ecf Steam vanilla -- la voie
   'GeneratorBA' (Id ECF 498, cout 4) apparait AU-DESSUS de la voie 'Core'
   (Id ECF 558, cout 0) dans le jeu, alors que le cout est plus bas pour
   Core -- un tri par cout donnerait donc l'ordre INVERSE de la realite.
   L'ordre reel suit l'Id ECF croissant (probablement l'ordre de declaration
   dans le fichier, dont l'Id est un proxy fiable). S'applique a la fois aux
   racines (voies independantes) et aux branchements (enfants qui ne
   continuent pas la voie de leur parent) -- la SELECTION du continuateur
   reste basee sur le cout le plus bas (deja verifiee independamment), seul
   l'ORDRE D'AFFICHAGE des voies change de critere.

Isole de gui/tech_tree_widget.py pour rester testable sans PyQt6.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional

from .tech_tree import TechTreeNode

# Jalons de niveau REELS affiches en en-tete du F3 en jeu (identiques sur les
# 10 captures d'ecran fournies par l'utilisateur, section Base ET les autres
# onglets) -- valeur fixe du jeu, PAS derivee des donnees du scenario.
MILESTONE_LEVELS: List[int] = [1, 3, 5, 7, 10, 12, 15, 20, 25]


def level_to_x_fraction(level: int, milestones: List[int] = MILESTONE_LEVELS) -> float:
    """Position horizontale continue en 'unites de colonne' (0.0 = premier
    jalon, len(milestones)-1 = dernier), interpolee lineairement entre les
    deux jalons qui encadrent `level`. Clampee aux bornes si `level` est
    en-dehors de la plage des jalons (ex: niveau 30 -> meme position que le
    dernier jalon 25, confirme sur les captures ou plusieurs noeuds de
    niveau > 25 restent alignes avec la derniere colonne 'Niveau 25')."""
    if not milestones:
        return 0.0
    if level <= milestones[0]:
        return 0.0
    if level >= milestones[-1]:
        return float(len(milestones) - 1)
    for i in range(len(milestones) - 1):
        lo, hi = milestones[i], milestones[i + 1]
        if lo <= level <= hi:
            return i + ((level - lo) / (hi - lo) if hi != lo else 0.0)
    return 0.0


def x_fraction_to_level(x_fraction: float, milestones: List[int] = MILESTONE_LEVELS) -> int:
    """Inverse de level_to_x_fraction, utilise lors d'un glisser (voir
    gui/tech_tree_widget.py) : aimante sur le JALON le plus proche (index
    entier le plus proche), pas sur une valeur interpolee -- glisser une
    icone doit toujours la deposer sur l'un des 9 niveaux reels du jeu, jamais
    sur une valeur arbitraire entre deux jalons."""
    if not milestones:
        return int(round(x_fraction))
    idx = max(0, min(len(milestones) - 1, round(x_fraction)))
    return milestones[idx]


@dataclass
class NodePosition:
    node_name: str
    x_fraction: float  # voir level_to_x_fraction -- position continue, pas un index de colonne
    row: int
    branches_from_parent: bool  # True = demarre une NOUVELLE voie (coude a dessiner), False = continue la voie de son parent (ou racine de voie)


def compute_node_positions(nodes: List[TechTreeNode],
                            milestones: List[int] = MILESTONE_LEVELS) -> Dict[str, NodePosition]:
    """Calcule (x_fraction, ligne, branchement) pour chaque noeud d'UNE
    categorie (deja filtree par l'appelant, voir TechTree.nodes_in_category()).
    Voir le docstring du module pour les deux regles verifiees sur donnees
    reelles : continuation de voie par cout le plus bas (point 2), ordre
    d'affichage des voies par Id ECF croissant (point 3) -- deux criteres
    DISTINCTS, verifies independamment l'un de l'autre."""
    by_name = {n.name: n for n in nodes}
    children_of: Dict[str, List[TechTreeNode]] = {}
    roots: List[TechTreeNode] = []
    for n in nodes:
        if n.parent_name and n.parent_name in by_name:
            children_of.setdefault(n.parent_name, []).append(n)
        else:
            roots.append(n)

    def _id_sort_key(n: TechTreeNode):
        """Ordre d'affichage des voies -- Id ECF croissant (verifie sur
        donnees reelles, voir docstring du module). Repli sur le nom pour
        les rares noeuds sans Id numerique, apres tous les noeuds avec Id."""
        try:
            return (0, int(n.ecf_id))
        except (TypeError, ValueError):
            return (1, n.name)

    def _continuation_sort_key(n: TechTreeNode):
        """Selection du SEUL enfant qui continue la voie de son parent --
        cout le plus bas (verifie independamment sur donnees reelles, voir
        docstring du module)."""
        return (n.unlock_cost, n.unlock_level, n.name)

    roots_display_order = sorted(roots, key=_id_sort_key)
    children_by_continuation: Dict[str, List[TechTreeNode]] = {
        parent: sorted(kids, key=_continuation_sort_key) for parent, kids in children_of.items()
    }
    children_by_display_order: Dict[str, List[TechTreeNode]] = {
        parent: sorted(kids, key=_id_sort_key) for parent, kids in children_of.items()
    }

    positions: Dict[str, NodePosition] = {}
    visited: set = set()
    row_state = {'next': -1}

    def _new_row() -> int:
        row_state['next'] += 1
        return row_state['next']

    def _place(node: TechTreeNode, row: int, branches: bool) -> None:
        if node.name in visited:
            return  # garde-fou anti-cycle (TechTreeParent invalide/circulaire)
        visited.add(node.name)
        x = level_to_x_fraction(node.unlock_level, milestones)
        positions[node.name] = NodePosition(node_name=node.name, x_fraction=x, row=row, branches_from_parent=branches)
        kids_for_continuation = children_by_continuation.get(node.name)
        if not kids_for_continuation:
            return
        continuing = kids_for_continuation[0]
        _place(continuing, row, False)  # cout le plus bas -> continue CETTE voie
        for kid in children_by_display_order.get(node.name, []):
            if kid is not continuing:
                _place(kid, _new_row(), True)  # les autres -> nouvelle voie, ordre par Id

    for root in roots_display_order:
        _place(root, _new_row(), False)

    # Filet de securite : tout noeud non atteint (cycle TechTreeParent) est
    # tout de meme place, pour ne jamais faire disparaitre un noeud reel.
    for n in nodes:
        if n.name not in positions:
            _place(n, _new_row(), True)

    return positions
