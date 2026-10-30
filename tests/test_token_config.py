"""Jetons de quete (core/token_config.py) : lecture d'un TokenConfig.ecf
synthetique, usages 'Token:<id>' reels, creation a Id libre, ecriture qui
preserve commentaires et blocs non touches, controles E321/W320/W322."""

from pathlib import Path

from core.token_config import (count_usages, create_token, find_token_file,
                               next_free_id, save, scan, set_field, set_flag)

TOKENS = """# documentation a PRESERVER
{ Token Id: 4001, Name: UCH Keycard
  CustomIcon: UCHKeycard
  Description: Carte du vaisseau Titan.
}

{ Token Id: 4002, Name: [c][FF0000]Charge[/c]（Demo Charge）
  RemoveOnUse: true
  DropOnDeath: false
  Description: Explosif de demolition.
}

# doublon d'Id + Id hors bornes + sans Name
{ Token Id: 4002, Name: Doublon
}
{ Token Id: 12000, Name: TropGrand
}
{ Token Id: 4003
  Description: sans nom
}
"""

PDA = """Chapters:
  - Name: Mission
    Reward:
      - Type: Item
        Value: Token:4001
"""


def _scenario(tmp_path: Path) -> Path:
    conf = tmp_path / "Content" / "Configuration"
    conf.mkdir(parents=True)
    (conf / "TokenConfig.ecf").write_text(TOKENS, encoding="utf-8")
    pda = tmp_path / "Extras" / "PDA"
    pda.mkdir(parents=True)
    (pda / "PDA.yaml").write_text(PDA, encoding="utf-8")
    return tmp_path


def test_scan_entries_and_fields(tmp_path):
    res = scan(_scenario(tmp_path))
    assert res.editable
    assert [e.token_id for e in res.entries] == [4001, 4002, 4002, 12000, 4003]
    first = res.entries[0]
    assert first.name == "UCH Keycard"
    assert first.custom_icon == "UCHKeycard"
    assert "Titan" in first.description
    assert first.usages == 1                     # reference dans PDA.yaml
    second = res.entries[1]
    assert second.remove_on_use is True
    assert second.drop_on_death is False
    assert second.usages == 0
    assert res.entries[2].usages == 0            # doublon non reference


def test_scan_issues(tmp_path):
    res = scan(_scenario(tmp_path))
    codes = sorted(i.code for i in res.issues)
    assert codes == ["E321", "W320", "W322"]
    dup = next(i for i in res.issues if i.code == "W320")
    assert "4002" in dup.message
    rng = next(i for i in res.issues if i.code == "E321")
    assert "12000" in rng.message


def test_next_free_id(tmp_path):
    res = scan(_scenario(tmp_path))
    assert next_free_id(res.entries) == 4004
    assert next_free_id([]) == 4000


def test_count_usages_only_real_locations(tmp_path):
    root = _scenario(tmp_path)
    pf = root / "Playfields" / "Pf"          # hors perimetre du scan
    pf.mkdir(parents=True)
    (pf / "playfield_static.yaml").write_text(
        "POIs:\n  Random:\n    - GroupName: X\n", encoding="utf-8")
    assert count_usages(root) == {4001: 1}


def test_edit_create_and_save(tmp_path):
    root = _scenario(tmp_path)
    res = scan(root)
    first = res.entries[0]
    assert set_field(first, "Name", "Carte Titan")
    assert set_field(first, "Description", "Nouvelle description")
    assert set_flag(first, "RemoveOnUse", True)
    assert set_field(first, "CustomIcon", "")     # vidage conserve la cle
    new = create_token(res.doc, res.path, next_free_id(res.entries),
                       "Jeton Test", "Description test", "IconeTest")
    res.entries.append(new)
    assert save(res) == res.path
    text = res.path.read_text(encoding="utf-8")
    assert "# documentation a PRESERVER" in text
    assert "{ Token Id: 4001, Name: Carte Titan" in text
    assert "RemoveOnUse: true" in text
    assert "{ Token Id: 4004, Name: Jeton Test" in text
    assert "IconeTest" in text
    assert "Doublon" in text and "TropGrand" in text   # blocs intacts
    # relecture : les nouveaux etats sont bien ceux ecrits
    again = scan(root)
    edited = next(e for e in again.entries if e.token_id == 4001)
    assert edited.name == "Carte Titan"
    assert edited.remove_on_use is True
    assert any(e.token_id == 4004 and e.name == "Jeton Test"
               for e in again.entries)


def test_flag_removal(tmp_path):
    root = _scenario(tmp_path)
    res = scan(root)
    second = res.entries[1]
    assert set_flag(second, "DropOnDeath", True)
    assert set_flag(second, "RemoveOnUse", False)
    save(res)
    text = res.path.read_text(encoding="utf-8")
    section = text.split("Token Id: 4002")[1].split("}")[0]
    assert "RemoveOnUse" not in section
    assert "DropOnDeath: true" in section


def test_missing_file(tmp_path):
    res = scan(tmp_path)
    assert find_token_file(tmp_path) is None
    assert not res.editable
    assert res.entries == [] and res.issues == []
