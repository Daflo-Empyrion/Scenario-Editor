"""Tests du reordonnancement des declarations ECF (core/ecf/ref_order.py)."""

from pathlib import Path

from core.ecf.parser import parse_ecf_file
from core.ecf.ref_order import (apply_ref_order, find_offenders,
                                plan_ref_order)


def _write(tmp_path, text):
    path = tmp_path / "BlocksConfig.ecf"
    path.write_bytes(text.encode("utf-8"))
    return path


def test_no_offender_when_target_first(tmp_path):
    path = _write(tmp_path,
                  "{ Block Id: 1, Name: Base\n}\n"
                  "{ Block Id: 2, Name: Child, Ref: Base\n}\n")
    plan = plan_ref_order(path)
    assert plan.nothing_to_do
    assert apply_ref_order(plan) == 0


def test_offender_detected_and_target_moved(tmp_path):
    path = _write(tmp_path,
                  "{ Block Id: 2, Name: Child, Ref: Base\n}\n"
                  "{ Block Id: 1, Name: Base\n}\n")
    plan = plan_ref_order(path)
    assert [(f.target, f.user) for f in plan.fixes] == [("Base", "Child")]
    assert apply_ref_order(plan) == 1
    doc = parse_ecf_file(path)
    assert find_offenders(doc) == []
    names = [b.get_property('Name') for b in doc.nodes if hasattr(b, 'kind')]
    assert names.index("Base") < names.index("Child")


def test_multiple_users_need_one_move(tmp_path):
    path = _write(tmp_path,
                  "{ Block Id: 2, Name: ChildA, Ref: Base\n}\n"
                  "{ Block Id: 3, Name: ChildB, Ref: Base\n}\n"
                  "{ Block Id: 1, Name: Base\n}\n")
    plan = plan_ref_order(path)
    assert len(plan.fixes) == 2
    assert apply_ref_order(plan) == 1
    assert find_offenders(parse_ecf_file(path)) == []


def test_cycle_is_reported_and_not_written(tmp_path):
    text = ("{ Block Id: 1, Name: Alpha, Ref: Beta\n}\n"
            "{ Block Id: 2, Name: Beta, Ref: Alpha\n}\n")
    path = _write(tmp_path, text)
    plan = plan_ref_order(path)
    assert plan.fixes == []
    assert {c for c in plan.cycles} == {"Alpha -> Beta", "Beta -> Alpha"}
    assert apply_ref_order(plan) == 0
    assert path.read_bytes().decode("utf-8") == text


def test_unknown_ref_is_not_touched(tmp_path):
    path = _write(tmp_path, "{ Block Id: 1, Name: Alone, Ref: Ghost\n}\n")
    assert plan_ref_order(path).nothing_to_do
