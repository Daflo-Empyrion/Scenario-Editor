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
Tests de core.tech_tree_layout -- chaque regle testee ici reproduit un
comportement du chargeur et de la fenetre F3 du jeu (regles verifiees contre
le chargement reel du jeu, session du 25/10/2026, build 25/09/2026). Ce
n'est plus de la deduction a partir de captures : les deux chaines
« reelles » des anciens tests restent, revaluees avec les VRAIES regles.
"""
from core.tech_tree import TechTree, TechTreeNode
from core.tech_tree_layout import compute_layout, nearest_level


def _node(name, level, cost=0, parent=None, ecf_id=None, source='block',
          categories=('Base',), sort_index=0, seq=None):
    return TechTreeNode(name=name, source=source, unlock_level=level, unlock_cost=cost,
                        categories=list(categories), parent_name=parent, icon_key=name,
                        ecf_id=ecf_id, sort_index=sort_index,
                        seq=seq if seq is not None else 0)


def _layout(nodes, category="Base"):
    return compute_layout(TechTree(nodes=list(nodes)), category)


# ---------------------------------------------------------------------------
# Regle 5 -- lignes : les enfants continuent la ligne du parent, une FEUILLE
# la termine (ToggleDomain) ; plus de « continuateur » choisi par categories.
# ---------------------------------------------------------------------------

def test_chain_of_single_children_stays_on_one_row():
    lay = _layout([_node("A", 1), _node("B", 5, parent="A"), _node("C", 10, parent="B")])
    assert lay.positions["A"].row == lay.positions["B"].row == lay.positions["C"].row == 0
    assert all(lay.positions[n].branches_from_parent is False for n in "ABC")


def test_leaf_terminates_row_and_next_sibling_starts_below():
    """Deux feuilles sous un meme parent : la premiere reste sur la ligne du
    parent puis la COUPE, la seconde demarre dessous (c'est le mecanisme
    reellement a l'oeuvre derriere l'ancienne regle « continuateur »)."""
    lay = _layout([_node("Root", 1, ecf_id=1),
                   _node("Leaf1", 5, parent="Root", ecf_id=2),
                   _node("Leaf2", 7, parent="Root", ecf_id=3)])
    assert lay.positions["Leaf1"].row == lay.positions["Root"].row
    assert lay.positions["Leaf1"].branches_from_parent is False
    assert lay.positions["Leaf2"].row == lay.positions["Root"].row + 1
    assert lay.positions["Leaf2"].branches_from_parent is True


def test_second_sibling_new_row_and_its_child_continues_it():
    """Vecu 24/10 reformule avec la vraie regle : ThrusterSVRoundBlocks a
    deux filles-feuilles ; la premiere garde la ligne du parent, la seconde
    part dessous -- et la fille de CETTE seconde continue SA ligne."""
    lay = _layout([_node("Blocks", 7, ecf_id=545),
                   _node("NormalT2", 10, parent="Blocks", ecf_id=546),
                   _node("Large", 10, parent="Blocks", ecf_id=547),
                   _node("LargeT2", 12, parent="Large", ecf_id=548)])
    assert lay.positions["NormalT2"].row == lay.positions["Blocks"].row
    assert lay.positions["Large"].row == lay.positions["Blocks"].row + 1
    assert lay.positions["LargeT2"].row == lay.positions["Large"].row
    assert lay.positions["LargeT2"].branches_from_parent is False


def test_root_after_previous_subtree_starts_new_row():
    lay = _layout([_node("R1", 1, ecf_id=1), _node("L1", 5, parent="R1", ecf_id=2),
                   _node("R2", 1, ecf_id=3)])
    assert lay.positions["R2"].row == lay.positions["R1"].row + 1


# ---------------------------------------------------------------------------
# Regle 4 -- colonnes = INDEX du niveau parmi les niveaux distincts de la
# categorie (ResolveProcess : tierColumn), pas la valeur brute ni une grille
# fixe.
# ---------------------------------------------------------------------------

def test_columns_are_tier_indices_not_raw_levels():
    lay = _layout([_node("A", 2), _node("B", 9, parent="A")])
    assert lay.levels == [2, 9]
    assert lay.positions["A"].x_fraction == 0
    assert lay.positions["B"].x_fraction == 1


def test_levels_are_distinct_and_sorted():
    lay = _layout([_node("A", 10), _node("B", 3, parent="A"), _node("C", 10, parent="A")])
    assert lay.levels == [3, 10]


def test_gaps_in_levels_do_not_create_columns():
    """Un scenario avec les niveaux 1, 5 et 25 a TROIS colonnes -- l'ancienne
    grille fixe [1,3,5,7,10,12,15,20,25] en affichait neuf."""
    lay = _layout([_node("A", 1), _node("B", 5, parent="A"), _node("C", 25, parent="B")])
    assert lay.levels == [1, 5, 25]
    assert lay.positions["C"].x_fraction == 2


# ---------------------------------------------------------------------------
# Regle 1 -- ancetres : l'arbre d'une categorie inclut les ANCIENS des
# chaines meme s'ils ne declarent PAS la categorie (RebuildSelection ne
# filtre que les feuilles).
# ---------------------------------------------------------------------------

def test_hidden_ancestor_is_drawn_in_the_tree():
    """Le piege vecu : un intermediaire TechTreeNames: Hidden reste un noeud
    interne de l'arbre (masquer n'efface pas un ancetre)."""
    lay = _layout([_node("Hidden1", 3, categories=("Hidden",), ecf_id=1),
                   _node("Leaf", 10, parent="Hidden1", ecf_id=2)])
    assert "Hidden1" in lay.positions
    assert lay.positions["Leaf"].parent_name == "Hidden1"


def test_ancestor_without_category_connects_leaf_to_grandparent():
    lay = _layout([_node("Top", 1, ecf_id=1),
                   _node("Mid", 3, categories=("Hidden",), parent="Top", ecf_id=2),
                   _node("Leaf", 7, parent="Mid", ecf_id=3)])
    assert lay.positions["Mid"].parent_name == "Top"
    assert lay.positions["Leaf"].parent_name == "Mid"
    assert lay.positions["Leaf"].row == lay.positions["Top"].row


def test_leaf_with_unknown_parent_is_its_own_root():
    lay = _layout([_node("Orphan", 5, parent="NotInModel")])
    assert "Orphan" in lay.positions
    assert lay.positions["Orphan"].parent_name is None


def test_leaf_with_level_zero_is_not_a_leaf_but_still_an_ancestor():
    """UnlockLevel 0 n'est jamais une feuille (filtre >= 1 du jeu) -- le
    noeud n'apparait que si une chaine le reference comme ancetre."""
    lay = _layout([_node("Zero", 0, ecf_id=1),
                   _node("Kid", 5, parent="Zero", ecf_id=2)])
    assert "Zero" in lay.positions          # ancetre de Kid
    zero_alone = _layout([_node("Zero", 0, ecf_id=1)])
    assert zero_alone.positions == {}       # jamais feuille seule


# ---------------------------------------------------------------------------
# Regle 2 -- ordre de traitement des feuilles : ITEMS d'abord (Id croissant)
# puis BLOCS (Id croissant, sans-Id apres).
# ---------------------------------------------------------------------------

def test_items_processed_before_blocks_regardless_of_ids():
    lay = _layout([_node("BlockKid", 5, parent="Root", ecf_id=1, source='block'),
                   _node("ItemKid", 5, parent="Root", ecf_id=900, source='item'),
                   _node("Root", 1, ecf_id=2, source='block')])
    # ItemKid insere avant BlockKid sous Root -> ItemKid garde la ligne
    assert lay.positions["ItemKid"].row == lay.positions["Root"].row
    assert lay.positions["BlockKid"].row == lay.positions["Root"].row + 1


def test_child_position_follows_earliest_descendant_leaf():
    """Cas RepairStation reel (vanilla) : RepairBayConsole (Id 1490) existe,
    mais la chaine de RepairBayBA (Id 1111) passe par FieldRepairStation et
    cree CE noeud sous RepairStation AVANT que celle de RepairBayConsole
    n'arrive -- l'ordre des enfants suit la PREMIERE feuille descendante."""
    lay = _layout([_node("ArmorLocker", 1, ecf_id=100),
                   _node("RepairStation", 5, parent="ArmorLocker", ecf_id=200),
                   _node("RepairBayConsole", 12, parent="RepairStation", ecf_id=1490),
                   _node("RepairBayBA", 10, parent="FieldRepairStation", ecf_id=1111),
                   _node("FieldRepairStation", 7, parent="RepairStation", ecf_id=None, seq=2523)])
    assert lay.positions["FieldRepairStation"].row == lay.positions["RepairStation"].row
    assert lay.positions["RepairBayConsole"].row == lay.positions["RepairStation"].row + 1


def test_root_order_follows_leaf_id_not_cost():
    """Verifie le 29/08/2026 sur la vanilla : GeneratorBA (Id 498, cout 4)
    AU-DESSUS de Core (Id 558, cout 0) -- ici parce que les FEUILLES sont
    traitees par Id croissant."""
    lay = _layout([_node("Core", 1, cost=0, ecf_id="558"),
                   _node("GeneratorBA", 3, cost=4, ecf_id="498")])
    assert lay.positions["GeneratorBA"].row < lay.positions["Core"].row


def test_nodes_without_numeric_id_sort_after_numbered_ones():
    lay = _layout([_node("NoId", 1, ecf_id=None, seq=10),
                   _node("WithId", 1, ecf_id="1", seq=20)])
    assert lay.positions["WithId"].row < lay.positions["NoId"].row


# ---------------------------------------------------------------------------
# Regle 3 -- tri stable par TechTreeSortIndex (OrderFunction) : les indices
# POSITIFS passent devant, l'ordre d'insertion est conserve entre egaux.
# ---------------------------------------------------------------------------

def test_positive_sort_index_moves_child_first():
    lay = _layout([_node("Root", 1, ecf_id=1),
                   _node("Second", 5, parent="Root", ecf_id=2),
                   _node("First", 5, parent="Root", ecf_id=3, sort_index=7)])
    assert lay.positions["First"].row == lay.positions["Root"].row
    assert lay.positions["Second"].row == lay.positions["Root"].row + 1


def test_zero_sort_indices_keep_insertion_order():
    lay = _layout([_node("Root", 1, ecf_id=1),
                   _node("A", 5, parent="Root", ecf_id=2),
                   _node("B", 5, parent="Root", ecf_id=3)])
    assert lay.positions["A"].row < lay.positions["B"].row


# ---------------------------------------------------------------------------
# Garde-fous de l'editeur (le jeu leve une exception / casse la config ;
# l'editeur doit toujours afficher quelque chose de coherent).
# ---------------------------------------------------------------------------

def test_handles_cycle_without_infinite_loop():
    lay = _layout([_node("A", 1, parent="B", ecf_id=1), _node("B", 1, parent="A", ecf_id=2)])
    assert "A" in lay.positions and "B" in lay.positions


def test_depth_capped_at_six_ancestors():
    """Le cap de remontee (6 ancetres) s'applique PAR CHAINE : une chaine
    unique de 9 ancetres est tronquee en haut (N3 devient racine), mais si
    des feuilles moins profondes existent, leurs propres chaines rejoignent
    les niveaux superieurs -- l'union reconstitue l'arbre complet."""
    # Une seule feuille (les intermediaires sont Hidden, donc jamais
    # feuilles) : la chaine est tronquee au 6e ancetre.
    single = [_node("N0", 1, ecf_id=1, seq=0, categories=('Hidden',))]
    for i in range(1, 10):
        cats = ('Hidden',) if i < 9 else ('Base',)
        single.append(_node(f"N{i}", i + 1, parent=f"N{i-1}", ecf_id=i + 1, seq=i, categories=cats))
    lay = _layout(single)
    assert lay.positions["N2"].parent_name is None      # troncation au 7e ancetre
    assert lay.positions["N9"].parent_name == "N8"

    # Avec des feuilles intermediaires, l'union des chaines reconstruit tout.
    names = [f"M{i}" for i in range(9)]
    full = [_node(names[i], i + 1, parent=(names[i - 1] if i else None), ecf_id=i + 1, seq=i)
            for i in range(9)]
    lay2 = _layout(full)
    assert lay2.positions["M1"].parent_name == "M0"
    assert lay2.positions["M8"].parent_name == "M7"


# ---------------------------------------------------------------------------
# nearest_level (aimantation du glisser sur les niveaux REELS de la
# categorie, ex-jalons fixes).
# ---------------------------------------------------------------------------

def test_nearest_level_snaps_to_present_levels():
    levels = [1, 3, 10]
    assert nearest_level(0.0, levels) == 1
    assert nearest_level(1.4, levels) == 3
    assert nearest_level(1.6, levels) == 10
    assert nearest_level(2.0, levels) == 10


def test_nearest_level_clamped_and_empty():
    assert nearest_level(99.0, [1, 3]) == 3
    assert nearest_level(-5.0, [1, 3]) == 1
    assert nearest_level(1.0, []) is None


# ---------------------------------------------------------------------------
# Regression sur les DEUX chaines reelles des captures F3 (28/08/2026),
# revaluees avec l'algorithme exact : niveaux presentes {1,7,12,20,25} ->
# colonnes = index, et la branche secondaire de Core part bien dessous.
# ---------------------------------------------------------------------------

def _cpu_extender_nodes():
    return [
        _node("Core", 1, cost=0, ecf_id=558, seq=0),
        _node("CPUExtenderBAT2", 7, cost=7, parent="Core", ecf_id=610, seq=1),
        _node("CPUExtenderBAT3", 12, cost=12, parent="CPUExtenderBAT2", ecf_id=611, seq=2),
        _node("CPUExtenderBAT4R", 20, cost=20, parent="CPUExtenderBAT3", ecf_id=612, seq=3),
        _node("CPUExtenderBAT5", 25, cost=25, parent="CPUExtenderBAT4R", ecf_id=613, seq=4),
        _node("CoreT2Large", 20, cost=20, parent="Core", ecf_id=614, seq=5),
        _node("CPUExtenderQuantumLarge", 25, cost=35, parent="CoreT2Large", ecf_id=615, seq=6),
        _node("Eden_CPUExtenderAuxCV", 20, cost=150, parent="Core", ecf_id=616, seq=7),
    ]


def test_real_cpu_extender_chain_stays_on_one_row():
    lay = _layout(_cpu_extender_nodes())
    main_row = lay.positions["Core"].row
    for name in ("CPUExtenderBAT2", "CPUExtenderBAT3", "CPUExtenderBAT4R", "CPUExtenderBAT5"):
        assert lay.positions[name].row == main_row, name
        assert lay.positions[name].branches_from_parent is False, name


def test_real_cpu_extender_secondary_branches_get_own_rows():
    lay = _layout(_cpu_extender_nodes())
    main_row = lay.positions["Core"].row
    assert lay.positions["CoreT2Large"].row == main_row + 1
    assert lay.positions["CPUExtenderQuantumLarge"].row == main_row + 1  # fille unique de T2
    assert lay.positions["Eden_CPUExtenderAuxCV"].row == main_row + 2


def test_real_cpu_extender_columns_are_tier_indices():
    lay = _layout(_cpu_extender_nodes())
    assert lay.levels == [1, 7, 12, 20, 25]
    assert lay.positions["Core"].x_fraction == 0
    assert lay.positions["CPUExtenderBAT2"].x_fraction == 1
    assert lay.positions["CPUExtenderBAT5"].x_fraction == 4


def _generator_nodes():
    return [
        _node("GeneratorBA", 3, cost=4, ecf_id=498, seq=0),
        _node("GeneratorMS", 10, cost=14, parent="GeneratorBA", ecf_id=499, seq=1),
        _node("PlasmaTurbineT0", 7, cost=15, parent="GeneratorBA", ecf_id=500, seq=2),
        _node("GeneratorMST2", 15, cost=20, parent="GeneratorMS", ecf_id=501, seq=3),
        _node("FusionReactorSmall", 20, cost=30, parent="GeneratorMST2", ecf_id=502, seq=4),
        _node("FusionReactorLarge", 25, cost=40, parent="FusionReactorSmall", ecf_id=503, seq=5),
    ]


def test_real_generator_chain_stays_on_one_row():
    lay = _layout(_generator_nodes())
    main_row = lay.positions["GeneratorBA"].row
    for name in ("GeneratorMS", "GeneratorMST2", "FusionReactorSmall", "FusionReactorLarge"):
        assert lay.positions[name].row == main_row, name
        assert lay.positions[name].branches_from_parent is False, name


def test_real_generator_plasma_turbine_branches_off():
    """PlasmaTurbineT0 arrive APRES GeneratorMS dans l'ordre des feuilles :
    GeneratorMS garde la ligne (sa propre chaine continue), PlasmaTurbine
    demarre dessous -- le cout n'entre plus en jeu du tout."""
    lay = _layout(_generator_nodes())
    assert lay.positions["PlasmaTurbineT0"].row == lay.positions["GeneratorBA"].row + 1
    assert lay.positions["PlasmaTurbineT0"].branches_from_parent is True
