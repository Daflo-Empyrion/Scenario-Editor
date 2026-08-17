import pytest
from pathlib import Path

from core.ecf.parser import parse_ecf_file
from core.ecf.transform import TransformRule, apply_transform

FIXTURE = Path(__file__).parent / "fixtures" / "sample.ecf"


def test_recursive_transform_applies_exactly_once_per_value():
    """Regression : doc.iter_blocks() parcourt deja recursivement TOUS les blocs
    (y compris imbriques comme 'Child Items'), donc iterer dessus PUIS laisser
    _find_matching_pairs redescendre en plus provoquait un double comptage --
    chaque proprietee imbriquee etait modifiee deux fois. Verifie que ce n'est
    plus le cas."""
    doc = parse_ecf_file(FIXTURE)
    rule = TransformRule(property_key="param1", operation="multiply", amount=2.0,
                          recursive=True)
    report = apply_transform(doc, rule)
    assert len(report.changes) == 2
    values = sorted(c.new_value for c in report.changes)
    assert values == ["0.6", "1"]


def test_non_recursive_transform_ignores_nested_blocks():
    doc = parse_ecf_file(FIXTURE)
    rule = TransformRule(property_key="param1", operation="multiply", amount=2.0,
                          recursive=False)
    report = apply_transform(doc, rule)
    assert len(report.changes) == 0


def test_transform_filters_by_block_kind():
    doc = parse_ecf_file(FIXTURE)
    rule = TransformRule(property_key="Count", operation="set", amount=99,
                          block_kind="+Container")
    report = apply_transform(doc, rule)
    assert len(report.changes) == 1
    assert report.changes[0].new_value == '"99,99"'


def test_transform_filters_by_block_ids():
    doc = parse_ecf_file(FIXTURE)
    rule = TransformRule(property_key="HitPoints", operation="multiply", amount=1.5,
                          block_ids=["399"])
    report = apply_transform(doc, rule)
    assert len(report.changes) == 1
    assert report.changes[0].new_value == "900"


def test_transform_clamp_operation():
    doc = parse_ecf_file(FIXTURE)
    rule = TransformRule(property_key="HitPoints", operation="clamp",
                          min_value=1000, max_value=None)
    report = apply_transform(doc, rule)
    assert len(report.changes) == 1
    assert report.changes[0].new_value == "1000"


def test_transform_no_matching_key_yields_no_changes():
    doc = parse_ecf_file(FIXTURE)
    rule = TransformRule(property_key="ThisKeyDoesNotExist", operation="add", amount=1.0)
    report = apply_transform(doc, rule)
    assert len(report.changes) == 0


def test_preview_transform_does_not_mutate_document():
    from core.ecf.transform import preview_transform
    doc = parse_ecf_file(FIXTURE)
    original_rendered = doc.render()

    rule = TransformRule(property_key="param1", operation="multiply", amount=2.0,
                          recursive=True)
    report = preview_transform(doc, rule)

    assert len(report.changes) == 2
    # Le document ne doit PAS avoir change -- seul un futur appel explicite a
    # apply_transform (ou l'application manuelle des references) doit muter.
    assert doc.render() == original_rendered


def test_preview_transform_changes_carry_references_for_manual_apply():
    from core.ecf.transform import preview_transform
    doc = parse_ecf_file(FIXTURE)
    rule = TransformRule(property_key="param1", operation="multiply", amount=2.0,
                          recursive=True)
    report = preview_transform(doc, rule)

    for change in report.changes:
        assert change.prop_node is not None
        assert change.pair_index is not None
        assert change.property_key is not None

    # Simule une edition manuelle d'une ligne (ex: forcer MaxCount a 1 sur un bloc
    # precis malgre la regle generale) puis applique seulement les references
    # retenues -- exactement le mecanisme utilise par TransformDialog._do_apply.
    chosen = report.changes[0]
    manual_value = "999"
    chosen.prop_node.pairs[chosen.pair_index] = (chosen.property_key, manual_value)

    rendered = doc.render()
    assert "999" in rendered


def test_format_block_label_shows_id_and_name_together():
    from core.ecf.transform import preview_transform, format_block_label
    doc = parse_ecf_file(FIXTURE)
    rule = TransformRule(property_key="HitPoints", operation="multiply", amount=1.5)
    report = preview_transform(doc, rule)

    labels = {format_block_label(c) for c in report.changes}
    # Le bloc Id=399/Name=ConcreteBlocks doit afficher les deux ensemble
    assert "Block [399] ConcreteBlocks" in labels
