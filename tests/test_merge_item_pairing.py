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

"""Fusion de TraderNPCConfig : les listes ItemN sont appariees PAR
IDENTITE (le nom d'item en debut de valeur) et non par numero — vecu
25/09 : deux scenarios n'ordonnent pas leurs items pareil, l'appariement
Item1<->Item1 ecrasait des items differents (HeliumBottle remplace par
ScienceEquipment)."""
import types

import pytest

from core.ecf.parser import parse_ecf_file


def _write(path, text):
    path.write_text(text, encoding="utf-8")
    return path
from gui.merge_preview_dialog import (MergePreviewDialog,
                                      compute_merge_preview)

WORKING_ECF = """{ Trader Name: Spaceport
  SellingText: "scn_Selling_Spaceport"
  Item1: "AlienNPCBlocks, mf=0.25-0.5, 3-10, 0, 0"
  Item2: "HumanNPCBlocks, mf=0.3-0.5, 3-10, 0, 0"
  Item3: "GeneratorMS, mf=1.0-1.5, 80-160, 0, 0"
  Item4: "HeliumBottle, mf=1.25-1.5, 30-60, 0, 0"
}

{ Trader Name: Autre
  Item1: "LocalOnly, mf=1-1, 1-2, 0, 0"
}
"""

SOURCE_ECF = """{ Trader Name: Spaceport
  SellingText: "scn_Selling_Spaceport"
  Item1: "AlienNPCBlocks, mf=0.8-0.9, 1000-1500, 0, 0"
  Item2: "HumanNPCBlocks, mf=0.8-0.9, 1000-1500, 0, 0"
  Item3: "Leather, mf=1.1-1.2, 500-1000, 0, 0"
  Item4: "ScienceEquipment, mf=1.1-1.2, 500-1000, 0, 0"
  Item5: "SpareParts, mf=1.1-1.2, 500-1000, 0, 0"
  Item6: "Liquors, mf=1.1-1.2, 500-1000, 0, 0"
}
"""


@pytest.fixture
def docs(tmp_path):
    wp = tmp_path / "working_TraderNPCConfig.ecf"
    sp = tmp_path / "source_TraderNPCConfig.ecf"
    wp.write_text(WORKING_ECF, encoding="utf-8")
    sp.write_text(SOURCE_ECF, encoding="utf-8")
    return parse_ecf_file(wp), parse_ecf_file(sp)


def _identity_rows(rows):
    return [r for r in rows if r.identity_paired]


def test_rows_paired_by_identity(docs):
    working_doc, source_doc = docs
    _result, rows = compute_merge_preview(working_doc, source_doc, "source")
    ident = _identity_rows(rows)
    changed = [r for r in ident if r.row_type == "changed_property"]
    added = [r for r in ident if r.row_type == "added_property"]
    # AlienNPCBlocks et HumanNPCBlocks : memes items, parametres differents
    assert {r.display_key.split("·")[-1].strip() for r in changed} == {
        "AlienNPCBlocks", "HumanNPCBlocks"}
    for r in changed:
        assert r.row_type == "changed_property" and r.working_key_present
        assert r.prop_key in ("Item1", "Item2")
    # Leather/ScienceEquipment/SpareParts/Liquors : ajouts
    assert {r.display_key.split("·")[-1].strip() for r in added} == {
        "Leather", "ScienceEquipment", "SpareParts", "Liquors"}
    for r in added:
        assert r.working_value == "(absent)"
    # AUCUN appariement croise HeliumBottle/GeneratorMS <-> ScienceEquipment
    for r in ident:
        assert "HeliumBottle" not in r.working_value \
            or "ScienceEquipment" not in r.merged_value
        assert "GeneratorMS" not in r.working_value


def test_apply_all_merges_by_identity(qapp, docs):
    working_doc, source_doc = docs
    result, rows = compute_merge_preview(working_doc, source_doc, "source")
    dlg = MergePreviewDialog(working_doc, source_doc, "source",
                             precomputed=(result, rows))
    dlg._set_all_checks(True)
    dlg.apply_selected()
    trader = next(b for b in result.document.iter_blocks()
                  if (b.get("Name") or "") == "Spaceport")
    values = [v.strip('"') for k, v in trader.pairs + [
        pair for c in trader.children for pair in c.pairs]
        if k and k.startswith("Item")]
    names = [v.split(",")[0].strip() for v in values]
    # UNION : items communs mis a jour + uniques copie de travail conserves
    # + ajouts du scenario source
    assert names == ["AlienNPCBlocks", "HumanNPCBlocks", "GeneratorMS",
                     "HeliumBottle", "Leather", "ScienceEquipment",
                     "SpareParts", "Liquors"]
    # renumerotation contigue Item1..Item8
    slots = [k for k, v in trader.pairs + [
        pair for c in trader.children for pair in c.pairs]
        if k and k.startswith("Item")]
    assert slots == [f"Item{i}" for i in range(1, 9)]
    # les mf du scenario source ont gagne pour les items communs
    assert "mf=0.8-0.9" in values[0]
    # le trader hors fusion est intact
    other = next(b for b in result.document.iter_blocks()
                 if (b.get("Name") or "") == "Autre")
    assert "LocalOnly" in (other.get_property("Item1") or "")


def test_apply_without_additions_preserves_working_items(qapp, docs):
    """Les ajouts decoches disparaissent (renumerotes) et les items propres
    a la copie de travail (GeneratorMS, HeliumBottle) sont intacts."""
    working_doc, source_doc = docs
    result, rows = compute_merge_preview(working_doc, source_doc, "source")
    dlg = MergePreviewDialog(working_doc, source_doc, "source",
                             precomputed=(result, rows))
    for r, row in enumerate(rows):
        check = dlg.table.item(r, 0)
        check.setCheckState(
            __import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.CheckState.Checked
            if row.identity_paired and row.row_type == "changed_property"
            else __import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.CheckState.Unchecked)
    dlg.apply_selected()
    trader = next(b for b in result.document.iter_blocks()
                  if (b.get("Name") or "") == "Spaceport")
    values = [v.strip('"') for k, v in trader.pairs + [
        pair for c in trader.children for pair in c.pairs]
        if k and k.startswith("Item")]
    names = [v.split(",")[0].strip() for v in values]
    # les 2 communs mis a jour + les 2 propres a la copie de travail
    assert names == ["AlienNPCBlocks", "HumanNPCBlocks", "GeneratorMS",
                     "HeliumBottle"]
    assert all("Leather" not in v and "Liquors" not in v for v in values)
    assert "mf=0.8-0.9" in values[0]


def test_child_inputs_rows_carry_parent_template(qapp, tmp_path):
    """Vecu 25/09 (Templates.ecf) : les blocs enfants SANS identite
    ("Child Inputs" de chaque template) partageaient la meme cle dans
    l'apercu — leurs lignes ne disaient pas de quel template elles
    relevaient et pouvaient etre appariees au mauvais parent."""
    GOLD = (
        "{ +Template [GoldOre]\n"
        "  CraftTime: 25\n"
        "  { Child Inputs\n"
        "    IronOre: 5\n"
        "  }\n"
        "}\n"
        "{ +Template [TitaniumPlates]\n"
        "  { Child Inputs\n"
        "    MetalPieces: 10\n"
        "  }\n"
        "}\n")
    GOLD_SRC = (
        "{ +Template [GoldOre]\n"
        "  CraftTime: 90\n"
        "  { Child Inputs\n"
        "    IronOre: 5\n"
        "    TitaniumPlates: 24\n"
        "  }\n"
        "}\n"
        "{ +Template [TitaniumPlates]\n"
        "  { Child Inputs\n"
        "    MetalPieces: 10\n"
        "  }\n"
        "}\n")
    working_doc = parse_ecf_file(_write(tmp_path / "w.ecf", GOLD))
    source_doc = parse_ecf_file(_write(tmp_path / "s.ecf", GOLD_SRC))
    _result, rows = compute_merge_preview(working_doc, source_doc, "source")
    by = {(r.block_label, r.prop_key): r for r in rows}
    added = by[("+Template [GoldOre] · Child Inputs", "TitaniumPlates")]
    assert added.working_value == "(absent)" and added.merged_value == "24"
    # MetalPieces de Titanium n'est PAS apparie avec celui de GoldOre
    assert ("+Template [GoldOre] · Child Inputs", "MetalPieces") not in by

def test_added_blocks_get_separator_comment(tmp_path):
    """Demande 25/09 : les blocs ajoutes par la fusion atterrissent en fin
    de fichier — un commentaire ouvre le paquet pour les differencier du
    contenu d'origine (un seul separateur pour le paquet consecutif)."""
    from core.ecf.merge import merge_documents
    working_doc = parse_ecf_file(_write(
        tmp_path / "w.ecf", "{ Block Id: 412, Name: HullTest\n}\n"))
    source_doc = parse_ecf_file(_write(
        tmp_path / "s.ecf",
        "{ Block Id: 412, Name: HullTest\n  Mass: 80\n}\n"
        "{ Block Id: 500, Name: NewBlockA\n}\n"
        "{ Block Id: 501, Name: NewBlockB\n}\n"))
    result = merge_documents([("working", working_doc), ("source", source_doc)],
                             mode="properties")
    text = result.document.render()
    assert 'Fusion depuis "source" : blocs ajoutes' in text
    assert text.count('Fusion depuis "source"') == 1
    assert text.index("NewBlockA") < text.index("NewBlockB")
    assert "HullTest" in text
