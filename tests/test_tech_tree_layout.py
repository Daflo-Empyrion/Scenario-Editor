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
Tests de core.tech_tree_layout -- verifie a la fois la logique unitaire et,
surtout, la reproduction EXACTE de deux chaines reelles confirmees contre de
vraies captures d'ecran F3 (session du 28/08/2026, voir docstring du module
teste) : Core > CPUExtenderBAT2/3/4R/5 et GeneratorBA > GeneratorMS >
GeneratorMST2 > FusionReactorSmall > FusionReactorLarge.
"""
from core.tech_tree import TechTreeNode
from core.tech_tree_layout import (
    level_to_x_fraction, x_fraction_to_level, compute_node_positions, MILESTONE_LEVELS,
)


def _node(name, level, cost=0, parent=None, ecf_id=None):
    return TechTreeNode(name=name, source='block', unlock_level=level, unlock_cost=cost,
                         categories=['Base'], parent_name=parent, icon_key=name, ecf_id=ecf_id)


# ---------------------------------------------------------------------------
# level_to_x_fraction / x_fraction_to_level
# ---------------------------------------------------------------------------

def test_level_to_x_fraction_exact_milestones():
    for i, level in enumerate(MILESTONE_LEVELS):
        assert level_to_x_fraction(level) == i


def test_level_to_x_fraction_interpolates_between_milestones():
    # Niveau 2 est exactement a mi-chemin entre les jalons 1 et 3 (index 0 et 1).
    assert level_to_x_fraction(2) == 0.5
    # Niveau 4 est a mi-chemin entre les jalons 3 et 5 (index 1 et 2).
    assert level_to_x_fraction(4) == 1.5


def test_level_to_x_fraction_clamped_below_and_above():
    assert level_to_x_fraction(0) == 0.0
    assert level_to_x_fraction(30) == len(MILESTONE_LEVELS) - 1
    assert level_to_x_fraction(999) == len(MILESTONE_LEVELS) - 1


def test_x_fraction_to_level_snaps_to_nearest_milestone():
    assert x_fraction_to_level(0.0) == 1
    assert x_fraction_to_level(3.0) == 7
    assert x_fraction_to_level(3.4) == 7
    assert x_fraction_to_level(3.6) == 10
    assert x_fraction_to_level(8.0) == 25


# ---------------------------------------------------------------------------
# compute_node_positions -- logique generique
# ---------------------------------------------------------------------------

def test_root_starts_new_lane_at_row_zero():
    nodes = [_node("A", 1, cost=0)]
    positions = compute_node_positions(nodes)
    assert positions["A"].row == 0
    assert positions["A"].branches_from_parent is False


def test_lowest_cost_child_continues_same_lane():
    nodes = [_node("Root", 1, cost=0),
             _node("Cheap", 10, cost=5, parent="Root"),
             _node("Expensive", 10, cost=20, parent="Root")]
    positions = compute_node_positions(nodes)
    assert positions["Cheap"].row == positions["Root"].row
    assert positions["Cheap"].branches_from_parent is False
    assert positions["Expensive"].row != positions["Root"].row
    assert positions["Expensive"].branches_from_parent is True


def test_chain_of_single_children_stays_on_one_lane():
    nodes = [_node("A", 1, cost=0), _node("B", 5, cost=1, parent="A"), _node("C", 10, cost=2, parent="B")]
    positions = compute_node_positions(nodes)
    assert positions["A"].row == positions["B"].row == positions["C"].row


def test_multiple_branches_each_get_distinct_rows():
    nodes = [_node("Root", 1, cost=0),
             _node("A", 5, cost=1, parent="Root"),
             _node("B", 5, cost=2, parent="Root"),
             _node("C", 5, cost=3, parent="Root")]
    positions = compute_node_positions(nodes)
    rows = {positions["A"].row, positions["B"].row, positions["C"].row}
    assert len(rows) == 3  # A continue Root, B et C branchent chacun sur une nouvelle voie


def test_parent_outside_category_treated_as_root():
    nodes = [_node("Orphan", 5, cost=1, parent="NotInThisList")]
    positions = compute_node_positions(nodes)
    assert "Orphan" in positions
    assert positions["Orphan"].branches_from_parent is False


def test_handles_cycle_without_infinite_loop():
    nodes = [_node("A", 1, parent="B"), _node("B", 1, parent="A")]
    positions = compute_node_positions(nodes)
    assert "A" in positions and "B" in positions


def test_deterministic_ordering_independent_of_input_order():
    nodes_a = [_node("Root", 1, cost=0), _node("Zeta", 5, cost=2, parent="Root"),
               _node("Alpha", 5, cost=1, parent="Root")]
    nodes_b = list(reversed(nodes_a))
    pos_a = compute_node_positions(nodes_a)
    pos_b = compute_node_positions(nodes_b)
    assert pos_a["Alpha"].branches_from_parent == pos_b["Alpha"].branches_from_parent
    assert pos_a["Zeta"].branches_from_parent == pos_b["Zeta"].branches_from_parent


def test_root_display_order_follows_ecf_id_not_cost():
    """Verifie le 29/08/2026 sur le vrai BlocksConfig.ecf Steam vanilla :
    GeneratorBA (Id 498, cout 4) apparait AU-DESSUS de Core (Id 558, cout 0)
    dans le jeu -- un tri par cout donnerait l'ordre inverse. Voir docstring
    du module (point 3)."""
    nodes = [_node("Core", 1, cost=0, ecf_id="558"),
             _node("GeneratorBA", 3, cost=4, ecf_id="498")]
    positions = compute_node_positions(nodes)
    assert positions["GeneratorBA"].row < positions["Core"].row


def test_branch_display_order_follows_ecf_id_not_cost():
    """Meme principe pour les branchements (enfants qui ne continuent pas la
    voie de leur parent) : ordre d'affichage par Id, pas par cout -- la
    selection du CONTINUATEUR reste par cout (voir
    test_lowest_cost_child_continues_same_lane)."""
    nodes = [_node("Root", 1, cost=0, ecf_id="1"),
             _node("Continues", 5, cost=1, parent="Root", ecf_id="100"),  # cout le + bas -> continue
             _node("BranchHighId", 5, cost=5, parent="Root", ecf_id="300"),
             _node("BranchLowId", 5, cost=10, parent="Root", ecf_id="200")]
    positions = compute_node_positions(nodes)
    assert positions["Continues"].branches_from_parent is False
    assert positions["BranchLowId"].row < positions["BranchHighId"].row


def test_nodes_without_numeric_id_sort_after_numbered_ones():
    nodes = [_node("NoId", 1, cost=0, ecf_id=None), _node("WithId", 1, cost=0, ecf_id="1")]
    positions = compute_node_positions(nodes)
    assert positions["WithId"].row < positions["NoId"].row


# ---------------------------------------------------------------------------
# Regression sur donnees REELLES -- verifie contre de vraies captures F3
# (voir docstring de core/tech_tree_layout.py) : deux chaines completes,
# recreees ici avec les vraies valeurs UnlockLevel/UnlockCost/TechTreeParent.
# ---------------------------------------------------------------------------

def _real_cpu_extender_chain():
    return [
        _node("Core", 1, cost=0),
        _node("CPUExtenderBAT2", 7, cost=7, parent="Core"),
        _node("CPUExtenderBAT3", 12, cost=12, parent="CPUExtenderBAT2"),
        _node("CPUExtenderBAT4R", 20, cost=20, parent="CPUExtenderBAT3"),
        _node("CPUExtenderBAT5", 25, cost=25, parent="CPUExtenderBAT4R"),
        _node("CoreT2Large", 20, cost=20, parent="Core"),
        _node("CPUExtenderQuantumLarge", 25, cost=35, parent="CoreT2Large"),
        _node("Eden_CPUExtenderAuxCV", 20, cost=150, parent="Core"),
    ]


def test_real_cpu_extender_chain_stays_on_one_lane():
    positions = compute_node_positions(_real_cpu_extender_chain())
    main_lane = positions["Core"].row
    for name in ["CPUExtenderBAT2", "CPUExtenderBAT3", "CPUExtenderBAT4R", "CPUExtenderBAT5"]:
        assert positions[name].row == main_lane, name
        assert positions[name].branches_from_parent is False, name


def test_real_cpu_extender_secondary_branches_get_own_lanes():
    positions = compute_node_positions(_real_cpu_extender_chain())
    main_lane = positions["Core"].row
    assert positions["CoreT2Large"].row != main_lane
    assert positions["CoreT2Large"].branches_from_parent is True
    assert positions["Eden_CPUExtenderAuxCV"].row != main_lane
    assert positions["Eden_CPUExtenderAuxCV"].row != positions["CoreT2Large"].row
    # CPUExtenderQuantumLarge est le SEUL enfant de CoreT2Large -> continue sa voie.
    assert positions["CPUExtenderQuantumLarge"].row == positions["CoreT2Large"].row


def test_real_cpu_extender_chain_columns_match_milestones():
    positions = compute_node_positions(_real_cpu_extender_chain())
    assert positions["Core"].x_fraction == 0            # Niveau 1
    assert positions["CPUExtenderBAT2"].x_fraction == 3  # Niveau 7
    assert positions["CPUExtenderBAT3"].x_fraction == 5  # Niveau 12
    assert positions["CPUExtenderBAT4R"].x_fraction == 7  # Niveau 20
    assert positions["CPUExtenderBAT5"].x_fraction == 8   # Niveau 25


def _real_generator_chain():
    return [
        _node("GeneratorBA", 3, cost=4),
        _node("GeneratorMS", 10, cost=14, parent="GeneratorBA"),
        _node("PlasmaTurbineT0", 7, cost=15, parent="GeneratorBA"),
        _node("GeneratorMST2", 15, cost=20, parent="GeneratorMS"),
        _node("FusionReactorSmall", 20, cost=30, parent="GeneratorMST2"),
        _node("FusionReactorLarge", 25, cost=40, parent="FusionReactorSmall"),
    ]


def test_real_generator_chain_stays_on_one_lane():
    positions = compute_node_positions(_real_generator_chain())
    main_lane = positions["GeneratorBA"].row
    for name in ["GeneratorMS", "GeneratorMST2", "FusionReactorSmall", "FusionReactorLarge"]:
        assert positions[name].row == main_lane, name
        assert positions[name].branches_from_parent is False, name


def test_real_generator_plasma_turbine_branches_off():
    """PlasmaTurbineT0 (cout 15) est plus cher que GeneratorMS (cout 14) --
    ne doit donc PAS continuer la voie principale."""
    positions = compute_node_positions(_real_generator_chain())
    assert positions["PlasmaTurbineT0"].row != positions["GeneratorBA"].row
    assert positions["PlasmaTurbineT0"].branches_from_parent is True
