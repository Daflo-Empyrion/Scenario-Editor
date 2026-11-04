"""Tests du module de nettoyage des declarations ECF desactivees
(core/ecf/inactive_declarations.py) -- repris de la manipulation manuelle
du 04/11/2026 sur ItemsConfig/BlocksConfig."""

from pathlib import Path

from core.ecf.inactive_declarations import apply_plan, scan_file
from core.ecf.parser import parse_ecf_file

SAMPLE = (
    "{ Item Id: 1, Name: ActiveItem\r\n"
    "  MarketPrice: 10\r\n"
    "}\r\n"
    "{ Item Id: 3, Name: DroppedItem\r\n"
    "  MarketPrice: 11\r\n"
    "}\r\n"
    "# CONFLIT D'ID 1 (+Item) : la copie de travail utilise deja cet Id\r\n"
    "# { +Item Id: 1, Name: DroppedItem\r\n"
    "#   MarketPrice: 5\r\n"
    "#   { Child 0\r\n"
    "#     Damage: 3\r\n"
    "\r\n"
    "#   }\r\n"
    "# }\r\n"
    "# DOUBLON DE NOM \"MissingItem\" : variante conservee en commentaire.\r\n"
    "# { Item Id: 2, Name: MissingItem, Ref: MissingTemplate\r\n"
    "#   MarketPrice: 7\r\n"
    "# }\r\n"
    "# DOUBLON DE NOM \"FreeItem\" : variante conservee en commentaire.\r\n"
    "# { Item Id: 99, Name: FreeItem\r\n"
    "#   MarketPrice: 9\r\n"
    "# }\r\n"
)


def _write(tmp_path, text=SAMPLE):
    path = tmp_path / "ItemsConfig.ecf"
    path.write_bytes(text.encode("utf-8"))
    return path


def test_scan_extracts_commented_declarations(tmp_path):
    plan = scan_file(_write(tmp_path))
    assert [d.name for d in plan.inactive] == ["DroppedItem", "MissingItem", "FreeItem"]
    assert plan.active_names == {"ActiveItem", "DroppedItem"}
    assert plan.inactive[0].header.startswith("# CONFLIT D'ID 1")
    assert plan.inactive[0].text.startswith("{ +Item Id: 1, Name: DroppedItem\r\n")


def test_plan_restores_missing_and_drops_homonyms(tmp_path):
    plan = scan_file(_write(tmp_path))
    assert [d.name for d in plan.to_restore] == ["MissingItem", "FreeItem"]
    # Id 2 est libre : conserve ; Id 99 est libre : conserve.
    assert plan.id_dropped == []
    assert [d.name for d in plan.to_drop] == ["DroppedItem"]


def test_plan_drops_id_already_taken(tmp_path):
    text = (
        "{ Item Id: 99, Name: Other\r\n}\r\n"
        "# DOUBLON DE NOM \"Mine\" : variante conservee en commentaire.\r\n"
        "# { Item Id: 99, Name: Mine\r\n# }\r\n"
    )
    plan = scan_file(_write(tmp_path, text))
    assert [d.name for d in plan.to_restore] == ["Mine"]
    assert plan.id_dropped == ["Mine"]


def test_apply_restores_and_removes(tmp_path):
    path = _write(tmp_path)
    plan = scan_file(path)
    result = apply_plan(plan)
    assert result.restored == 2
    assert result.dropped == 1
    text = path.read_bytes().decode("utf-8")
    # les declarations actives restent, les inactives disparaissent
    doc = parse_ecf_file(path)
    names = {b.get_property("Name") for b in doc.nodes if hasattr(b, "kind")}
    assert {"ActiveItem", "MissingItem", "FreeItem"} <= names
    # l'homonyme actif reste, mais la copie commentee a disparu
    assert text.count("Name: DroppedItem") == 1
    # plus aucune ligne commentee de declaration, plus d'en-tete de fusion
    assert "# { +Item" not in text and "# { Item" not in text
    assert "CONFLIT D'ID" not in text and "DOUBLON DE NOM" not in text
    # les blocs reactives sont decommentes et le contenu actif intact
    assert "{ Item Id: 2, Name: MissingItem, Ref: MissingTemplate" in text
    assert "  MarketPrice: 10" in text
    assert text.count("\r\n") > 0


def test_apply_without_removal_keeps_dropped_commented(tmp_path):
    path = _write(tmp_path)
    result = apply_plan(scan_file(path), remove_dropped=False)
    assert result.restored == 2 and result.dropped == 0
    text = path.read_bytes().decode("utf-8")
    assert "# { +Item Id: 1, Name: DroppedItem" in text
    # pas de doublon : la version decommentee n'existe qu'une fois
    assert text.count("{ Item Id: 2, Name: MissingItem") == 1


def test_apply_drops_conflicting_id(tmp_path):
    text = (
        "{ Item Id: 5, Name: Other\r\n}\r\n"
        "# DOUBLON DE NOM \"Mine\" : variante conservee en commentaire.\r\n"
        "# { Item Id: 5, Name: Mine\r\n# }\r\n"
    )
    path = _write(tmp_path, text)
    apply_plan(scan_file(path))
    out = path.read_bytes().decode("utf-8")
    assert "{ Item Name: Mine" in out
    assert "Id: 5, Name: Mine" not in out


def test_no_inactive_is_a_noop(tmp_path):
    path = _write(tmp_path, "{ Item Id: 1, Name: Only\r\n}\r\n")
    plan = scan_file(path)
    assert plan.nothing_to_do
    result = apply_plan(plan)
    assert result.restored == 0 and result.backup is None
    assert path.read_bytes().decode("utf-8") == "{ Item Id: 1, Name: Only\r\n}\r\n"


def test_malformed_commented_block_is_ignored(tmp_path):
    text = (
        "{ Item Id: 1, Name: Active\r\n}\r\n"
        "# { Item Id: 2, Name: Broken\r\n"
        "  MarketPrice: 1\r\n"          # ligne non commentee : bloc illisible
        "# }\r\n"
    )
    plan = scan_file(_write(tmp_path, text))
    assert plan.inactive == []
    assert plan.nothing_to_do
