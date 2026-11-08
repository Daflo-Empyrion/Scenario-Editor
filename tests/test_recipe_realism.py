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

"""Recettes realistes (core/recipe_realism.py) : table coherente, masse du
jeu comme cible, granularite des composants, idempotence, et LECTURE SEULE
(aucun fichier du scenario modifie au lot 1)."""

from pathlib import Path

from core.recipe_realism import (CLASSES, MATERIALS, analyze, apply_proposals,
                                 sync_to_base, resolve, tier_of,
                                 unit_masses, write_report_csv)

BLOCKS = """{ Block Id: 1, Name: GenA
  IndexName: Generator
  Category: Devices
  Mass: 500, type: float, formatter: Kilogram
  TemplateRoot: GenA
}
{ Block Id: 2, Name: HullA
  Category: BuildingBlocks
  Mass: 100, type: float, formatter: Kilogram
  TemplateRoot: HullA
}
{ Block Id: 3, Name: CrateSmall
  IndexName: Container
  Category: Devices
  Mass: 125, type: float, formatter: Kilogram
  TemplateRoot: CrateSmall
}
{ Block Id: 4, Name: CrateBig
  IndexName: Container
  Category: Devices
  Mass: 20000, type: float, formatter: Kilogram
  TemplateRoot: CrateSmall
}
{ Block Id: 5, Name: NoMass
  IndexName: Generator
  Category: Devices
  TemplateRoot: NoMass
}
{ Block Id: 6, Name: HeavyCtor
  IndexName: Constructor
  Category: Devices
  Mass: 50000, type: float, formatter: Kilogram
  TemplateRoot: HeavyCtor
}
{ Block Id: 7, Name: GenBase
  IndexName: Generator
  Category: Devices
  Mass: 1000, type: float, formatter: Kilogram
  TemplateRoot: GenBase
}
{ Block Id: 8, Name: GenT2
  IndexName: Generator
  Category: Devices
  Mass: 1000, type: float, formatter: Kilogram
  TechTreeParent: GenBase
  TemplateRoot: GenT2
}
{ Block Id: 9, Name: GenT3
  IndexName: Generator
  Category: Devices
  Mass: 1000, type: float, formatter: Kilogram
  TechTreeParent: GenT2
  TemplateRoot: GenT3
}
{ Block Id: 10, Name: SmallPistolT2
  IndexName: WeaponShip
  Category: Devices
  Mass: 5, type: float, formatter: Kilogram
  TemplateRoot: SmallPistolT2
}
"""

ITEMS = """{ Item Id: 217, Name: SteelPlate
  Category: Components
  Mass: 11.8, type: float, formatter: Kilogram
}
{ Item Id: 218, Name: IronIngot
  Category: Components
  Mass: 5.9, type: float, formatter: Kilogram
}
{ Item Id: 219, Name: Motor
  Category: Components
  Mass: 24.28, type: float, formatter: Kilogram
}
{ Item Id: 220, Name: Electronics
  Category: Components
  Mass: 2.86, type: float, formatter: Kilogram
}
{ Item Id: 221, Name: MechanicalComponents
  Category: Components
  Mass: 0.65, type: float, formatter: Kilogram
}
{ Item Id: 222, Name: FluxCoil
  Category: Components
  Mass: 39.1, type: float, formatter: Kilogram
}
{ Item Id: 223, Name: PowerCoil
  Category: Components
  Mass: 184.9, type: float, formatter: Kilogram
}
{ Item Id: 224, Name: PlasticMaterial
  Category: Components
  Mass: 0.18, type: float, formatter: Kilogram
}
{ Item Id: 225, Name: PlatinumOre
  Category: Ingredients
  Mass: 5, type: float, formatter: Kilogram
}
{ Item Id: 226, Name: PromethiumPellets
  Mass: 2.18, type: float, formatter: Kilogram
}
{ Item Id: 227, Name: EnergyCell
  Mass: 14.52, type: float, formatter: Kilogram
}
{ Item Id: 228, Name: TitanRods
  Mass: 3.38, type: float, formatter: Kilogram
}
{ Item Id: 229, Name: TitanPlates
  Mass: 6.76, type: float, formatter: Kilogram
}
{ Item Id: 230, Name: HiddenItem
  Category: Devices
  Mass: 100, type: float, formatter: Kilogram
}
{ Item Id: 231, Name: ZascosiumAlloy
  Mass: 7.33, type: float, formatter: Kilogram
}
{ Item Id: 232, Name: ErestrumIngot
  Mass: 4.65, type: float, formatter: Kilogram
}
"""

TEMPLATES = """{ Template Name: GenA
  CraftTime: 5
  OutputCount: 3
  Target: "BaseC"
  { Child Inputs
    SteelPlate: 16
    Motor: 2
  }
}
{ Template Name: HullA
  CraftTime: 2
  Target: "BaseC"
  { Child Inputs
    SteelPlate: 4
  }
}
{ Template Name: CrateSmall
  CraftTime: 2
  Target: "BaseC"
  { Child Inputs
    SteelPlate: 8
  }
}
{ Template Name: NoMass
  CraftTime: 5
  Target: "BaseC"
  { Child Inputs
    SteelPlate: 1
  }
}
{ Template Name: PlatinumOre
  BaseItem: true
  CraftTime: 5
  Target: "BaseC"
  { Child Inputs
    SteelPlate: 1
  }
}
{ Template Name: HeavyCtor
  CraftTime: 1
  Target: "BaseC"
  { Child Inputs
    SteelPlate: 10
  }
}
{ Template Name: SteelPlate
  CraftTime: 1
  OutputCount: 10
  Target: "BaseC"
  { Child Inputs
    IronIngot: 5
  }
}
{ Template Name: EnergyCell
  CraftTime: 3
  Target: "BaseC"
  { Child Inputs
    PromethiumPellets: 5
  }
}
{ Template Name: TitanPlates
  CraftTime: 1
  OutputCount: 10
  Target: "BaseC"
  { Child Inputs
    TitanRods: 5
  }
}
{ Template Name: TitanRods
  CraftTime: 1
  Target: "BaseC"
  { Child Inputs
    TitanPlates: 2
  }
}
{ Template Name: MechanicalComponents
  CraftTime: 1
  OutputCount: 4
  Target: "BaseC"
  { Child Inputs
    SteelPlate: 1
  }
}
{ Template Name: HiddenItem
  CraftTime: 5
  Target: ""
  { Child Inputs
    SteelPlate: 3
  }
}
{ Template Name: GenBase
  CraftTime: 5
  Target: "BaseC"
  { Child Inputs
    SteelPlate: 4
  }
}
{ Template Name: GenT2
  CraftTime: 5
  Target: "BaseC"
  { Child Inputs
    SteelPlate: 4
  }
}
{ Template Name: GenT3
  CraftTime: 5
  Target: "BaseC"
  { Child Inputs
    SteelPlate: 4
  }
}
{ Template Name: SmallPistolT2
  CraftTime: 3
  Target: "BaseC"
  { Child Inputs
    SteelPlate: 1
  }
}
"""


def _scenario(tmp_path: Path) -> Path:
    cdir = tmp_path / "Content" / "Configuration"
    cdir.mkdir(parents=True)
    (cdir / "BlocksConfig.ecf").write_text(BLOCKS, encoding="utf-8")
    (cdir / "ItemsConfig.ecf").write_text(ITEMS, encoding="utf-8")
    (cdir / "Templates.ecf").write_text(TEMPLATES, encoding="utf-8")
    return tmp_path


def test_table_parts_sum_to_100():
    for code, klass in CLASSES.items():
        total = sum(part for _tok, part in klass.parts)
        assert abs(total - 100.0) < 0.01, (code, total)


def test_every_token_is_a_chain_or_a_component():
    for klass in CLASSES.values():
        for token, _part in klass.parts:
            assert token in MATERIALS or token in UNIT_NAMES, (
                klass.code, token)


UNIT_NAMES = {
    "SteelPlate", "IronIngot", "Motor", "Electronics", "MechanicalComponents",
    "FluxCoil", "PowerCoil", "PlasticMaterial", "GlassPlate", "AluminiumCoil",
    "AluminiumPowder", "CopperIngot", "SiliconIngot", "TitanRods",
    "TitanPlates", "Nanotubes", "NeodymiumIngot", "CapacitorComponent",
    "Superconductor", "QuantumProcessor", "GoldIngot", "Chemicals",
    "Fertilizer", "WaterBottle", "WaterJug", "Computer", "OpticalFiber",
}


def test_granularity_takes_coarsest_component_that_fits():
    masses = {"FluxCoil": 39.1, "PowerCoil": 184.9}
    # 50 kg de bobinage : FluxCoil tient, PowerCoil (185 kg) non
    assert resolve("BOBINE", 50.0, masses) == ("FluxCoil", 39.1)
    # 22 kg de cuivre ne s'ecrit jamais "1 PowerCoil" de 185 kg
    assert resolve("ACIER", 300.0, {"IronIngot": 5.9,
                                    "SteelPlate": 11.8}) == ("SteelPlate", 11.8)


def test_steel_falls_back_to_ingot_for_tiny_parts():
    masses = {"IronIngot": 5.9, "SteelPlate": 11.8}
    assert resolve("ACIER", 2.0, masses) == ("IronIngot", 5.9)


def test_generator_uses_object_mass_not_group_max(tmp_path):
    root = _scenario(tmp_path)
    report = analyze(root)
    by_name = {p.name: p for p in report.proposals}
    gen = by_name["GenA"]
    assert gen.klass == "GENERATOR"
    assert gen.obj_mass == 500
    # 500 kg x rendement 1,25 x OutputCount 3 : la matiere porte sur le LOT
    assert gen.target_mass == 1875
    assert abs(gen.coverage - 1.0) <= 0.2
    crate = by_name["CrateSmall"]          # meme template qu'un bloc de 20 t
    assert crate.obj_mass == 125
    assert crate.klass == "CONTAINER"


def test_structures_keep_author_composition(tmp_path):
    """Masse de VOLUME (coque, beton) : le jeu est abstrait sur ces blocs, et
    l'ancrage masse y multipliait la matiere par 6 a 1400 (mesure 06/11)."""
    report = analyze(_scenario(tmp_path))
    reason = report.skipped.get("HullA", "")
    assert "structure" in reason
    assert "HullA" not in {p.name for p in report.proposals}


def test_raw_items_and_unknown_mass_are_skipped(tmp_path):
    report = analyze(_scenario(tmp_path))
    assert "PlatinumOre" in report.skipped
    assert "BaseItem" in report.skipped["PlatinumOre"]
    assert report.skipped.get("NoMass") == "masse inconnue (ni Mass du groupe)"


def test_analyze_is_idempotent(tmp_path):
    root = _scenario(tmp_path)
    first = {p.name: list(p.new_inputs) for p in analyze(root).proposals}
    second = {p.name: list(p.new_inputs) for p in analyze(root).proposals}
    assert first == second
    assert first                         # au moins une recette proposee


def test_analyze_writes_nothing(tmp_path):
    root = _scenario(tmp_path)
    cdir = root / "Content" / "Configuration"
    before = {p.name: p.read_bytes() for p in cdir.glob("*.ecf")}
    report = analyze(root)
    write_report_csv(report, tmp_path / "rapport.csv")
    after = {p.name: p.read_bytes() for p in cdir.glob("*.ecf")}
    assert before == after               # lot 1 : lecture seule, verifie
    assert (tmp_path / "rapport.csv").exists()


def test_unit_masses_reads_components_of_all_classes(tmp_path):
    from core.recipe_balance import load_recipe_index
    idx, _van = load_recipe_index(_scenario(tmp_path))
    masses = unit_masses(idx)
    assert masses["SteelPlate"] == 11.8
    assert masses["OpticalFiber"] == 0.0   # absent du scenario : signale


def test_classify_by_name_when_no_category(tmp_path):
    from core.recipe_balance import load_recipe_index
    from core.recipe_realism import TOKEN_CLASS, SKIP_TOKENS, classify
    idx, _van = load_recipe_index(_scenario(tmp_path))
    # noms reels de RE2-FR sans Category ni IndexName (mesures 06/11)
    assert classify(idx, "GeneratorMST2")[0] == "GENERATOR"
    assert classify(idx, "ShieldGeneratorCV")[0] == "SHIELD"
    assert classify(idx, "FuelTankMSLargeT2")[0] == "FUELTANK"
    assert classify(idx, "WeaponSV05Homing")[0] == "FIREARM"
    assert classify(idx, "5.56mmBullet")[0] == "AMMO"
    assert classify(idx, "AkuaWine")[0] == "FOOD"
    code, reason = classify(idx, "Eden_IceRich")
    assert code is None and "glace" in reason
    code, reason = classify(idx, "SteelPlate")
    assert code is None and "4.5" in reason
    # un token ne peut pas etre a la fois classe et ecart : l'ordre des
    # tables decide, autant l'interdire explicitement
    assert not ({tok for tok, _ in TOKEN_CLASS}
                & {tok for tok, _ in SKIP_TOKENS})


def test_apply_preserves_output_count_and_target(tmp_path):
    root = _scenario(tmp_path)
    cdir = root / "Content" / "Configuration"
    apply_proposals([p for p in analyze(root).proposals if p.changed])
    text = (cdir / "Templates.ecf").read_text(encoding="utf-8")
    gen = text.split("{ Template Name: GenA")[1].split("}")[0]
    assert "OutputCount: 3" in gen
    assert 'Target: "BaseC"' in gen


def test_apply_then_reanalyze_proposes_nothing(tmp_path):
    root = _scenario(tmp_path)
    first = [p for p in analyze(root).proposals if p.changed]
    assert first                        # quelque chose a ecrire
    apply_proposals(first)
    again = [p for p in analyze(root).proposals if p.changed]
    assert again == []                  # idempotence : 2e passe sans effet


def test_craft_time_is_not_ratcheted_by_its_own_value(tmp_path):
    """Vecu 06/11 : un plafond « x10 le CraftTime courant » faisait monter la
    valeur a chaque passe (3 -> 30 -> 60) et laissait 30 lignes en boucle."""
    root = _scenario(tmp_path)
    heavy = {p.name: p for p in analyze(root).proposals}["HeavyCtor"]
    assert heavy.craft_old == 1
    assert heavy.craft_new > 10          # borne ABSOLUE, pas x10 l'ancien
    apply_proposals([p for p in analyze(root).proposals if p.changed])
    assert [p.name for p in analyze(root).proposals if p.changed] == []


def test_component_batch_target_is_output_count_times_mass(tmp_path):
    """Un composant en lot : la cible porte sur tout le lot (10 plaques), pas
    sur une piece — sinon la matiere entrante est 10 fois trop faible."""
    report = analyze(_scenario(tmp_path))
    steel = {p.name: p for p in report.proposals}["SteelPlate"]
    assert steel.klass == "COMPOSANT"
    assert steel.obj_mass == 11.8
    assert abs(steel.target_mass - 11.8 * 10 * 1.05) < 0.01
    assert abs(steel.coverage - 1.0) <= 0.2
    assert dict(steel.new_inputs)["IronIngot"] >= 20


def test_component_keeps_author_composition_when_fictional(tmp_path):
    """Matiere fictive (Promethium) : composition conservee, echelle de masse.
    La masse des ingredients hors table doit compter (sinon facteur infini)."""
    report = analyze(_scenario(tmp_path))
    cell = {p.name: p for p in report.proposals}["EnergyCell"]
    assert cell.klass == "COMPOSANT"
    assert cell.src == "extrapole"
    assert dict(cell.new_inputs) == {"PromethiumPellets": 7}
    assert abs(cell.coverage - 1.0) <= 0.2


def test_component_that_would_contain_itself_is_refused(tmp_path):
    report = analyze(_scenario(tmp_path))
    reason = report.skipped.get("TitanPlates", "")
    assert "cycle" in reason


def test_hidden_recipe_with_empty_target_is_never_rewritten(tmp_path):
    """`Target: ""` se lit AVEC les guillemets : un test de verite naif le
    prend pour un constructeur et reecrit une recette cachee (vecu 06/11, 27
    recettes non fabricables modifiees par erreur)."""
    report = analyze(_scenario(tmp_path))
    reason = report.skipped.get("HiddenItem", "")
    assert "Target vide" in reason
    assert "HiddenItem" not in {p.name for p in report.proposals}


def test_exotic_share_follows_tech_tree_depth(tmp_path):
    """Le palier n'est pas `UnlockLevel` (un T3 peut se debloquer au niveau 1)
    mais la profondeur de lignee : GenT3 est le petit-fils de GenBase."""
    report = analyze(_scenario(tmp_path))
    by = {p.name: p for p in report.proposals}
    idx = _idx(tmp_path)
    assert tier_of(idx, "GenBase") == 0          # racine de l'arbre
    assert tier_of(idx, "GenT3") == 3            # suffixe T3 > profondeur 2
    assert "ZascosiumAlloy" not in dict(by["GenBase"].new_inputs)
    assert dict(by["GenT2"].new_inputs)["ZascosiumAlloy"] >= 1    # tier 2
    assert dict(by["GenT3"].new_inputs)["ZascosiumAlloy"] >= 1    # tier 3
    assert abs(by["GenT3"].coverage - 1.0) <= 0.2                  # masse tenue


def test_exotic_part_is_taken_from_the_mass_not_added(tmp_path):
    report = analyze(_scenario(tmp_path))
    by = {p.name: p for p in report.proposals}
    # la part exotique est prelevee : la masse totale reste la cible
    assert by["GenT3"].new_mass <= by["GenT3"].target_mass * 1.2


def test_weapons_take_erestrum_and_too_small_ones_have_none(tmp_path):
    report = analyze(_scenario(tmp_path))
    pistol = {p.name: p for p in report.proposals}["SmallPistolT2"]
    assert "ErestrumIngot" not in dict(pistol.new_inputs)   # 5 kg < 4,65 kg a 3 %
    assert "exotique impossible" in " ".join(pistol.notes)


def _idx(root):
    from core.recipe_balance import load_recipe_index
    return load_recipe_index(root)[0]


def test_sub_kilogram_component_keeps_author_recipe(tmp_path):
    """0,65 kg par unité : l'ancrage masse ne peut rien exprimer. Mesure du
    06/11 : Eden_Semiconductor (0,05 kg/u) passait de 486 kg de matières
    (silicium, cuivre, or, argent, platine, plastique) à 1 lingot de silicium."""
    report = analyze(_scenario(tmp_path))
    reason = report.skipped.get("MechanicalComponents", "")
    assert "quelques grammes" in reason
    assert "MechanicalComponents" not in {p.name for p in report.proposals}


BASE_BLOCKS = """{ Block Id: 50, Name: GenBase
  IndexName: Generator
  Category: Devices
  Mass: 1000, type: float, formatter: Kilogram
  TemplateRoot: GenBase
}
"""

BASE_TEMPLATES = """{ Template Name: GenBase
  CraftTime: 4
  Target: "BaseC"
  { Child Inputs
    SteelPlate: 10
    Motor: 2
  }
}
{ Template Name: MechanicalComponents
  CraftTime: 1
  OutputCount: 4
  Target: "BaseC"
  { Child Inputs
    SteelPlate: 3
  }
}
"""


def _base(tmp_path: Path) -> Path:
    cdir = tmp_path / "base" / "Content" / "Configuration"
    cdir.mkdir(parents=True)
    (cdir / "BlocksConfig.ecf").write_text(BASE_BLOCKS, encoding="utf-8")
    (cdir / "ItemsConfig.ecf").write_text(ITEMS, encoding="utf-8")
    (cdir / "Templates.ecf").write_text(BASE_TEMPLATES, encoding="utf-8")
    return tmp_path / "base"


def test_sync_takes_base_verbatim(tmp_path):
    root = _scenario(tmp_path)
    props, _skipped = sync_to_base(root, str(_base(tmp_path)))
    prop = {p.name: p for p in props}["GenBase"]
    assert dict(prop.new_inputs) == {"SteelPlate": 10, "Motor": 2}
    assert prop.craft_new == 4                    # craft de la base
    assert "sans modification" in " ".join(prop.notes)


def test_realign_verbatim_for_sub_kilogram(tmp_path):
    """0,65 kg par unite : la base reste telle quelle, la masse n'exprime rien."""
    root = _scenario(tmp_path)
    props, _s = sync_to_base(root, str(_base(tmp_path)))
    prop = {p.name: p for p in props}["MechanicalComponents"]
    assert dict(prop.new_inputs) == {"SteelPlate": 3}   # base, tels quels
    assert "sans modification" in " ".join(prop.notes)


def test_analyze_skips_base_governed_recipes(tmp_path):
    root = _scenario(tmp_path)
    base = str(_base(tmp_path))
    props, _s = sync_to_base(root, base)
    apply_proposals([p for p in props if p.changed])
    report = analyze(root, base_root=base)
    assert report.skipped.get("GenBase") == "gouvernee par la base RE2 (sync_to_base)"
    assert "GenBase" not in {p.name for p in report.proposals}
