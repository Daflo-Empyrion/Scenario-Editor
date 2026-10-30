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

"""Tests de core/template_autogen.py (scenario synthetique, sans jeu installe)."""
from pathlib import Path

from core.ecf.parser import parse_ecf_file
from core.template_autogen import (
    MAX_QTY, _scale_inputs, apply, load, missing, plan, render,
)

BLOCKS = """
{ Block Id: 1, Name: HullA
  Material: SteelSmall
  Mass: 10
}
{ Block Id: 2, Name: HullB
  TemplateRoot: HullA
  Material: SteelSmall
  Mass: 10
}
{ Block Id: 3, Name: HullC
  Material: SteelSmall
  Mass: 20
}
{ Block Id: 4, Name: OreRock
  Material: resourcehard
  Shape: Terrain
}
{ Block Id: 5, Name: Mystery
  Mass: 5
}
{ Block Id: 6, Name: Alien_Roots Cover
  Material: stone
}
"""

ITEMS = """
{ Item Id: 100, Name: SteelPlate
  Mass: 0.5
}
{ Item Id: 101, Name: RifleT1
  Mass: 1.0
  Category: Weapons/Items
}
{ Item Id: 102, Name: RifleT2
  Mass: 1.5
  Category: Weapons/Items
}
{ Item Id: 103, Name: IronOre
  Mass: 0.1
}
{ Item Id: 104, Name: RawFoo
  Mass: 0.05
}
"""

TEMPLATES = """
{ Template Name: HullA
  CraftTime: 2
  Target: "BaseC"
  { Child Inputs
    SteelPlate: 2
    RawFoo: 2
  }
}
{ Template Name: RifleT1
  CraftTime: 2
  Target: "BaseC"
  { Child Inputs
    SteelPlate: 1
  }
}
{ Template Name: SteelPlate
  CraftTime: 1
  Target: ""
  { Child Inputs
    IronOre: 1
  }
}
"""


def _scenario(tmp_path: Path) -> Path:
    conf = tmp_path / "Content" / "Configuration"
    conf.mkdir(parents=True)
    (conf / "BlocksConfig.ecf").write_text(BLOCKS, encoding="utf-8")
    (conf / "ItemsConfig.ecf").write_text(ITEMS, encoding="utf-8")
    (conf / "Templates.ecf").write_text(TEMPLATES, encoding="utf-8")
    return tmp_path


def test_missing_respects_direct_template_and_template_root(tmp_path):
    root = _scenario(tmp_path)
    blocks, items, templates, _sources = load(root)
    miss_blocks, miss_items = missing(blocks, items, templates)
    assert "HullA" not in miss_blocks          # template direct
    assert "HullB" not in miss_blocks          # TemplateRoot -> HullA
    assert {"HullC", "OreRock", "Mystery"} <= set(miss_blocks)
    assert "RifleT1" not in miss_items
    assert {"RifleT2", "IronOre"} <= set(miss_items)


def test_la_vanille_est_ignoree_nom_vanille_seul_jamais_template(tmp_path):
    """Vecu 28/10 : le jeu charge la config DU SCENARIO a la place de celle
    de la base — un bloc defini en vanille seule n'existe pas a
    l'execution, et un Template qui le vise est fatal au chargement client
    (« No item/block with name '_Acacia_Sapling_Fall' existing »)."""
    root = _scenario(tmp_path)
    vanilla = tmp_path / "vanilla_content"
    vconf = vanilla / "Configuration"
    vconf.mkdir(parents=True)
    (vconf / "BlocksConfig.ecf").write_text(
        "{ Block Id: 900, Name: VanillaOnly\n  Material: stone\n}\n\n",
        encoding="utf-8")
    (vconf / "ItemsConfig.ecf").write_text("", encoding="utf-8")
    (vconf / "Templates.ecf").write_text("", encoding="utf-8")
    blocks, items, templates, _sources = load(root, str(vanilla))
    assert "VanillaOnly" not in blocks
    result = plan(root, str(vanilla))
    assert "VanillaOnly" not in {entry.name for entry in result.entries}
    assert not [e for e in result.entries if e.name == "VanillaOnly"]


def test_plan_copie_le_modele_le_plus_proche_et_normalise_la_masse(tmp_path):
    root = _scenario(tmp_path)
    result = plan(root)
    by_name = {entry.name: entry for entry in result.entries}
    assert "HullC" in by_name
    hull = by_name["HullC"]
    assert hull.source in {"HullA", "HullB"}
    assert hull.method == "name"
    # 2 SteelPlate + 2 RawFoo pour une masse 10 -> 4 de chaque pour 20.
    assert hull.inputs == [("SteelPlate", 4), ("RawFoo", 4)]
    assert hull.decon == "Continue"  # sans Continue le Deconstructor echoue
    # Jamais craftable.
    assert all(entry.craft_time >= 1 for entry in result.entries)
    rifle = by_name["RifleT2"]
    assert rifle.source == "RifleT1"
    assert rifle.inputs == [("SteelPlate", 2)]  # 1 x (1.5 / 1.0), arrondi
    # RawFoo n'a aucun modele mais est un ingredient : feuille terminale,
    # donc plus "ignore" (sinon le bloc parent ne serait pas demontable).
    terminal = by_name["RawFoo"]
    assert terminal.method == "terminal" and terminal.empty
    assert terminal.decon == "Stop"
    assert "RawFoo" not in {name for name, _kind, _reason in result.skipped}
    assert ("OreRock", "block", "ressource brute") in result.skipped
    assert ("Mystery", "block", "aucun modele proche") in result.skipped
    assert ("Alien_Roots Cover", "block", "nom ECF non sur") in result.skipped
    # Mode complet : les entrees vides restent disponibles pour inspection.
    full = {entry.name: entry for entry in plan(root, include_empty=True).entries}
    assert full["OreRock"].empty and full["Mystery"].empty


def test_render_est_du_ecf_non_craftable_et_reparse(tmp_path):
    root = _scenario(tmp_path)
    result = plan(root)
    text = render(result.entries)
    conf = root / "Content" / "Configuration"
    path = conf / "Templates.ecf"
    with path.open("ab") as fh:
        fh.write(b"\r\n" + text.encode("utf-8"))
    doc = parse_ecf_file(path)
    parsed = {(block.get_property("Name") or "").strip(): block
              for block in doc.iter_blocks()
              if block.kind in ("Template", "+Template")}
    for entry in result.entries:
        block = parsed[entry.name]
        assert (block.get_property("Target") or "").strip() == '""'
        assert block.get_property("CraftTime")
    assert "Target: \"\"" in text


def test_apply_est_idempotent_et_sauvegarde(tmp_path):
    root = _scenario(tmp_path)
    result, written = apply(root)
    assert written == len(result.entries)
    backups = list((root / "Content" / "Configuration").glob("Templates.ecf.bak_*"))
    assert backups
    before = (root / "Content" / "Configuration" / "Templates.ecf").read_bytes()
    result2, written2 = apply(root)
    assert written2 == 0
    after = (root / "Content" / "Configuration" / "Templates.ecf").read_bytes()
    assert before == after
    # Le seul manque restant est l'entree technique ignoree.
    blocks, items, templates, _sources = load(root)
    miss_blocks, miss_items = missing(blocks, items, templates)
    assert "HullC" not in miss_blocks
    assert "RifleT2" not in miss_items
    assert "Alien_Roots Cover" in miss_blocks


def test_scale_inputs_supprime_la_boucle_et_borne_les_quantites():
    assert _scale_inputs([("HullC", 5), ("SteelPlate", 2)],
                         {"Mass": "10"}, {"Mass": "10"}, 1, "HullC") == [
        ("SteelPlate", 2)]
    assert _scale_inputs([("SteelPlate", 1_000_000)],
                         {"Mass": "10"}, {"Mass": "10"}, 1, "X") == [
        ("SteelPlate", MAX_QTY)]
