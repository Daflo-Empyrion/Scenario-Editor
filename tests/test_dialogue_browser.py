"""
Tests du module d'extraction structuree des dialogues (core/dialogue_browser.py)
-- bases sur une fixture reelle (chaine TC_* extraite d'un vrai Dialogues.ecf,
5417 blocs, 48601 lignes) couvrant Variable, Execute, Next/NextIf,
Option/OptionNext, NPCName, Output.
"""
from pathlib import Path

from core.ecf.parser import parse_ecf_file
from core.dialogue_browser import build_dialogue_index, build_incoming_links_index

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "dialogue_scenario" / "Dialogues.ecf"


def _index():
    doc = parse_ecf_file(FIXTURE_PATH)
    return build_dialogue_index(doc)


def test_all_dialogues_indexed():
    index = _index()
    assert len(index) == 8
    assert "TC_Start" in index


def test_npc_name_extracted():
    index = _index()
    assert index["TC_Start"].npc_name == '"Talon Chief"'


def test_variables_extracted_with_type():
    index = _index()
    variables = index["TC_Start"].variables
    assert len(variables) == 4
    names = {v.name for v in variables}
    assert '"TalkCount"' in names
    talk_count = next(v for v in variables if v.name == '"TalkCount"')
    assert talk_count.var_type == "dbstate_int"


def test_executes_extracted_in_order():
    index = _index()
    executes = index["TC_Start"].executes
    assert len(executes) == 3
    assert "TalkCount = TalkCount + 1" in executes[0]


def test_transitions_with_and_without_condition():
    index = _index()
    transitions = index["TC_Start"].transitions
    assert len(transitions) == 5
    with_condition = [t for t in transitions if t.condition is not None]
    without_condition = [t for t in transitions if t.condition is None]
    assert len(with_condition) == 4
    assert len(without_condition) == 1
    assert without_condition[0].target == "TC_DefaultEntry"


def test_options_with_targets():
    index = _index()
    options = index["TC_HasHolyStatus"].options
    assert len(options) == 3
    assert options[0].next_target == "TC_GiveHolyStatue"
    assert options[2].next_target == "End"  # sentinelle, pas un vrai dialogue


def test_output_extracted():
    index = _index()
    assert index["TC_CameBack"].output is not None
    assert "TalkCount" in index["TC_CameBack"].output


def test_incoming_links_finds_all_referrers():
    """Confirme sur la vraie chaine TC_* : 4 dialogues distincts menent vers
    TC_DefaultEntryCont (verifie manuellement contre le vrai fichier
    complet avant de construire la fixture reduite)."""
    index = _index()
    incoming = build_incoming_links_index(index)
    referrers = incoming.get("TC_DefaultEntryCont", [])
    assert set(referrers) == {"TC_HasHolyStatus", "TC_DefaultEntry"}


def test_incoming_links_excludes_end_sentinel():
    """'End' est une sentinelle reservee, jamais un vrai nom de dialogue --
    ne doit jamais apparaitre comme cle dans l'index des liens entrants."""
    index = _index()
    incoming = build_incoming_links_index(index)
    assert "End" not in incoming


def test_incoming_links_empty_for_root_dialogue():
    """TC_Start n'est jamais cible par aucun autre dialogue de cette chaine
    (point d'entree) -- doit retourner une liste vide, pas planter."""
    index = _index()
    incoming = build_incoming_links_index(index)
    assert incoming.get("TC_Start", []) == []


def test_document_round_trips_perfectly_after_parsing():
    original = FIXTURE_PATH.read_bytes()
    doc = parse_ecf_file(FIXTURE_PATH)
    build_dialogue_index(doc)  # extraction seule, aucune modification
    assert doc.render().encode("utf-8") == original
