"""
Tests du module de detection de definitions non utilisees
(core/ecf/orphan_check.py) -- suggestion de Begebum (commentaire Steam),
volontairement restreint aux jetons (voir docstring de tete de module pour
le raisonnement complet sur pourquoi les blocs/items generiques ne sont PAS
couverts -- risque de faux positifs massif confirme).
"""
from pathlib import Path

from core.ecf.orphan_check import find_unused_tokens

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "orphan_scenario"


def test_finds_only_genuinely_unused_token():
    files = list(FIXTURE_DIR.glob("*.ecf"))
    unused = find_unused_tokens(files)
    assert len(unused) == 1
    assert unused[0].identifier == "3"
    assert unused[0].label == "UnusedToken"


def test_token_referenced_in_blocks_config_not_flagged():
    files = list(FIXTURE_DIR.glob("*.ecf"))
    unused = find_unused_tokens(files)
    identifiers = {u.identifier for u in unused}
    assert "1" not in identifiers  # KeyCardRed, reference dans BlocksConfig.ecf


def test_token_referenced_in_dialogues_not_flagged():
    files = list(FIXTURE_DIR.glob("*.ecf"))
    unused = find_unused_tokens(files)
    identifiers = {u.identifier for u in unused}
    assert "2" not in identifiers  # KeyCardGreen, reference dans Dialogues.ecf


def test_returns_empty_list_when_no_token_config_present():
    files = [FIXTURE_DIR / "BlocksConfig.ecf"]
    assert find_unused_tokens(files) == []


def test_returns_empty_list_for_empty_file_list():
    assert find_unused_tokens([]) == []


def test_display_includes_id_name_and_source_file():
    files = list(FIXTURE_DIR.glob("*.ecf"))
    unused = find_unused_tokens(files)
    text = unused[0].display()
    assert "Token:3" in text
    assert "UnusedToken" in text
    assert "TokenConfig.ecf" in text


def test_handles_unparseable_file_gracefully(tmp_path):
    bad_file = tmp_path / "TokenConfig.ecf"
    bad_file.write_text("{ this is not valid ECF at all {{{ ", encoding="utf-8")
    result = find_unused_tokens([bad_file])
    assert result == []
