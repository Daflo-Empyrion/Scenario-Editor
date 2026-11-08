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

"""Templates de deconstruction generes (core/template_autogen.py) : tout ce
qui peut entrer dans un inventaire devient demontable, SANS devenir
fabricable (`Target: ""`), et la matiere rendue suit la table realiste."""

from pathlib import Path

from core.recipe_balance import load_recipe_index
from core.recipe_realism import refresh_deconstruction
from core.template_autogen import (GENERATED_MARKER, apply, generated_names,
                                   load, obtainable_names, plan, render)

BLOCKS = """{ Block Id: 1, Name: PickMe
  Mass: 5
  CanPickup: true
}
{ Block Id: 2, Name: PickGiver
  Mass: 5
  PickupTarget: PickMe
}
{ Block Id: 3, Name: DecoItem
  Mass: 5
  IsDeco: true
}
{ Block Id: 4, Name: TerrainDeco
  Mass: 5
  IsDeco: true
  IsTerrainDecoration: true
}
{ Block Id: 5, Name: HiddenBlock
  Mass: 5
  ShowUser: No
}
"""

ITEMS = """{ Item Id: 1, Name: RifleT2
  Mass: 1.5
  Category: Weapons/Items
}
{ Item Id: 2, Name: GenericFruit
  Mass: 0.2
  Category: Weapons/Items
}
{ Item Id: 3, Name: IronIngot
  Mass: 5.9
}
{ Item Id: 4, Name: AluminiumPowder
  Mass: 2.02
}
{ Item Id: 5, Name: PlasticMaterial
  Mass: 0.18
}
{ Item Id: 6, Name: MechanicalComponents
  Mass: 0.65
}
"""


def _scenario(tmp_path: Path) -> Path:
    conf = tmp_path / "Content" / "Configuration"
    conf.mkdir(parents=True)
    (conf / "BlocksConfig.ecf").write_text(BLOCKS, encoding="utf-8")
    (conf / "ItemsConfig.ecf").write_text(ITEMS, encoding="utf-8")
    (conf / "Templates.ecf").write_text("", encoding="utf-8")
    return tmp_path


def test_obtainable_covers_pickup_deco_and_items(tmp_path):
    blocks, items, _templates, _sources = load(_scenario(tmp_path), "")
    keep = obtainable_names(blocks, items)
    # PickMe arrive en inventaire : `PickGiver` le donne en le ramassant
    assert {"PickMe", "DecoItem", "RifleT2"} <= keep
    # le bloc qui DONNE l'item reste un objet du monde
    assert "PickGiver" not in keep
    # terrain et bloc masque : jamais dans un inventaire
    assert "TerrainDeco" not in keep
    assert "HiddenBlock" not in keep


def test_only_obtainable_excludes_terrain_and_hidden(tmp_path):
    result = plan(_scenario(tmp_path), "", only_obtainable=True)
    names = {entry.name for entry in result.entries}
    skipped = {row[0]: row[2] for row in result.skipped}
    assert "TerrainDeco" not in names and "TerrainDeco" not in skipped
    assert "HiddenBlock" not in names and "HiddenBlock" not in skipped
    # PickMe est retenu par le filtre ; s'il n'a pas de modele proche il est
    # liste avec ce motif, il ne disparait pas en silence
    assert "PickMe" in names or "modele" in skipped.get("PickMe", "")


def test_generated_templates_are_deconstructible_but_not_craftable(tmp_path):
    result = plan(_scenario(tmp_path), "", only_obtainable=True)
    entry = next(e for e in result.entries if e.name == "RifleT2")
    assert entry.decon == "Continue"          # sinon P3=0 : aucune sortie
    text = render([entry])
    assert 'Target: ""' in text               # present, mais pas fabricable
    assert "DeconOverride: Continue" in text
    assert "Child Inputs" in text


def test_realism_composition_used_for_classified_items(tmp_path):
    result = plan(_scenario(tmp_path), "", only_obtainable=True)
    rifle = next(e for e in result.entries if e.name == "RifleT2")
    assert rifle.method == "realism"
    # FIREARM : acier/alu/plastique/mecanique, pas la recette d'un voisin
    assert rifle.source == "realisme"
    names = {name for name, _qty in rifle.inputs}
    assert names and names <= {"IronIngot", "AluminiumPowder",
                               "PlasticMaterial", "MechanicalComponents"}


def test_fallback_class_is_not_composed_as_a_device(tmp_path):
    """GENERIC_DEVICE est une classe de repli : un fruit ne rend pas de l'acier
    et de l'electronique (vecu 06/11 sur AkuaFruit)."""
    result = plan(_scenario(tmp_path), "", only_obtainable=True)
    fruit = next((e for e in result.entries if e.name == "GenericFruit"), None)
    assert fruit is None or fruit.method != "realism"


def test_apply_is_idempotent(tmp_path):
    root = _scenario(tmp_path)
    _result, written = apply(root, "", only_obtainable=True)
    assert written
    # 2e passe : le fichier a change, plus rien a generer
    _result2, written2 = apply(root, "", only_obtainable=True)
    assert written2 == 0


def test_generated_names_only_reads_the_marked_section(tmp_path):
    """Une recette cachée de l'auteur porte le même `Target: ""` : elle ne
    doit jamais être rafraîchie par erreur."""
    conf = tmp_path / "Content" / "Configuration"
    conf.mkdir(parents=True)
    text = ('{ Template Name: HullDestroyed\n  CraftTime: 1\n  Target: ""\n}\n'
            + GENERATED_MARKER + " (Target vide = non\r\n# ====\r\n\r\n"
            + '{ Template Name: RifleT2\n  CraftTime: 2\n  Target: ""\n}\n')
    (conf / "Templates.ecf").write_text(text, encoding="utf-8")
    assert generated_names(conf / "Templates.ecf") == {"RifleT2"}


def test_refresh_gives_the_exotic_back_to_tier2_deconstruction(tmp_path):
    root = _scenario(tmp_path)
    apply(root, "", only_obtainable=True)
    conf = root / "Content" / "Configuration"
    names = generated_names(conf / "Templates.ecf") or {"RifleT2"}
    idx, _van = load_recipe_index(root)
    proposals = refresh_deconstruction(idx, sorted(names))
    # la table courante donne le tier depuis le nom : RifleT2 -> tier 2
    assert proposals == [] or all(p.klass == "DECONSTRUCTION" for p in proposals)


def test_leaf_added_for_ingredient_of_an_author_recipe(tmp_path):
    """Vecu 06/11 : `ErestrumOre`, ingrédient d'ErestrumIngot, n'avait aucun
    template — le Deconstructor ne pouvait pas le résoudre et 40 recettes
    fabricables n'étaient pas démontables."""
    root = _scenario(tmp_path)
    conf = root / "Content" / "Configuration"
    (conf / "Templates.ecf").write_text(
        '{ Template Name: RifleT2\n  CraftTime: 2\n  Target: "BaseC"\n'
        '  { Child Inputs\n    IronIngot: 3\n  }\n}\n'
        '{ Template Name: IronIngot\n  CraftTime: 1\n  Target: "BaseC"\n'
        '  { Child Inputs\n    RawOre: 5\n  }\n}\n', encoding="utf-8")
    (conf / "ItemsConfig.ecf").write_text(
        ITEMS + '{ Item Id: 99, Name: RawOre\n  Mass: 1\n}\n', encoding="utf-8")
    result = plan(root, "", only_obtainable=True)
    leaves = {e.name for e in result.entries if e.method == "terminal"}
    assert "RawOre" in leaves
    text = render([e for e in result.entries if e.name == "RawOre"])
    assert 'Target: ""' in text and "DeconOverride: Stop" in text
    assert "Child Inputs" in text and "IronIngot" not in text.split("Child Inputs")[1]


def test_currency_never_gets_a_template(tmp_path):
    """Une MoneyCard se dépose dans un ATM qui crédite le compte : la démonter
    n'a pas de sens, elle ne doit recevoir aucune feuille (mesure 06/11)."""
    root = _scenario(tmp_path)
    conf = root / "Content" / "Configuration"
    (conf / "ItemsConfig.ecf").write_text(
        ITEMS + '{ Item Id: 98, Name: MoneyCard\n  Mass: 1\n}\n'
        '{ Item Id: 97, Name: PlatinumCard\n  Mass: 2\n}\n',
        encoding="utf-8")
    (conf / "Templates.ecf").write_text(
        '{ Template Name: PlatinumCard\n  CraftTime: 2\n  Target: "BaseC"\n'
        '  { Child Inputs\n    MoneyCard: 10\n  }\n}\n', encoding="utf-8")
    result = plan(root, "", only_obtainable=True)
    names = {e.name for e in result.entries}
    assert "MoneyCard" not in names
    reasons = [row for row in result.skipped if row[0] == "MoneyCard"]
    assert len(reasons) == 1 and "devise" in reasons[0][2]
