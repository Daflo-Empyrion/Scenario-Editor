"""Tests de la reparation des niveaux d'arbre technologique
(core/tech_tree_levels.py)."""

from core.tech_tree_levels import (apply_unlock_progression, next_level,
                                   plan_unlock_progression,
                                   remaining_violations)


def _files(tmp_path, blocks, items=""):
    b = tmp_path / "BlocksConfig.ecf"
    i = tmp_path / "ItemsConfig.ecf"
    b.write_bytes(blocks.encode("utf-8"))
    i.write_bytes(items.encode("utf-8"))
    return b, i


def test_ladder_and_beyond():
    assert next_level(1) == 3
    assert next_level(7) == 10
    assert next_level(25) == 26


def test_child_at_parent_level_is_raised(tmp_path):
    b, i = _files(tmp_path,
                  "{ Block Id: 1, Name: Parent\n"
                  "  TechTreeNames: Base\n  UnlockLevel: 5\n}\n"
                  "{ Block Id: 2, Name: Child\n  TechTreeParent: Parent\n"
                  "  TechTreeNames: Base\n  UnlockLevel: 5\n}\n")
    plan = plan_unlock_progression(b, i, "")
    assert [(f.name, f.current, f.new_level) for f in plan.fixes] == [
        ("Child", 5, 7)]
    assert apply_unlock_progression(plan) == 1
    assert remaining_violations(b, i, "") == []


def test_raising_parent_cascades_to_child(tmp_path):
    b, i = _files(tmp_path,
                  "{ Block Id: 1, Name: Root\n"
                  "  TechTreeNames: Base\n  UnlockLevel: 7\n}\n"
                  "{ Block Id: 2, Name: Mid\n  TechTreeParent: Root\n"
                  "  TechTreeNames: Base\n  UnlockLevel: 7\n}\n"
                  "{ Block Id: 3, Name: Leaf\n  TechTreeParent: Mid\n"
                  "  TechTreeNames: Base\n  UnlockLevel: 10\n}\n")
    plan = plan_unlock_progression(b, i, "")
    levels = {f.name: f.new_level for f in plan.fixes}
    # Mid releve a 10, ce qui invalide Leaf (10) -> 12
    assert levels == {"Mid": 10, "Leaf": 12}
    assert apply_unlock_progression(plan) == 2
    assert remaining_violations(b, i, "") == []


def test_valid_tree_is_a_noop(tmp_path):
    b, i = _files(tmp_path,
                  "{ Block Id: 1, Name: Parent\n"
                  "  TechTreeNames: Base\n  UnlockLevel: 1\n}\n"
                  "{ Block Id: 2, Name: Child\n  TechTreeParent: Parent\n"
                  "  TechTreeNames: Base\n  UnlockLevel: 3\n}\n")
    plan = plan_unlock_progression(b, i, "")
    assert plan.nothing_to_do
    assert apply_unlock_progression(plan) == 0
