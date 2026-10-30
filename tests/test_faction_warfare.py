"""Defenses de faction (core/faction_warfare.py) : lecture des deux formes de
prix (a plat / BaseAttack_ScenarioPrice), ecriture dans la forme d'origine,
reglages globaux, et controles E331/W331/W332/W333 sur un fichier
synthetique."""

from pathlib import Path

from core.faction_warfare import scan, set_global, set_price, set_sd

WARFARE = """{ Element Name: GlobalSettings
  EnableSpaceDefenseLog: False
  EnableSpaceDefense: True
  PlayerAttackMaxCountFrequencySpawned: 10
  PlayerAttackMaxCountPOISpawned: 10
}

# faction a plat
{ Element Name: FactionSettings
  Faction: Talon
  ScenarioGroup: Talon
  Lvl1MinPrice: 80
  Lvl1MaxPrice: 120
  Lvl10MinPrice: 800
  Lvl10MaxPrice: 1200
}

# faction avec bloc de prix + defense spatiale
{ Element Name: FactionSettings
  Faction: Zirax
  ScenarioGroup: Zirax
  { Child BaseAttack_ScenarioPrice
    PlayFieldLvl1Min: 15
    PlayFieldLvl1Max: 30
    PlayFieldLvl10Min: 60
    PlayFieldLvl10Max: 80
  }
  SDScenarioGroup: ZiraxSpaceDefense
  SDProbabilityMin: 0
  SDProbabilityMax: 0
  SDPriceMin: 50
  SDPriceMax: 500
}

# faction absente de Factions.ecf
{ Element Name: FactionSettings
  Faction: Fantome
  Lvl1MinPrice: 500
  Lvl1MaxPrice: 100
}

{ Element Name: Unit
  Faction: Zirax
  ClassName: DroneBaseAttackRocket
  Category: DroneRocketSurv
  CommandPointsLvl1: 12
  CommandPointsPerLevel: 1.50
}

{ Element Name: Scenario
  Name: Surv1
  ID: 2001
  IsInGroups: "Zirax"
  { Child Unit1
    Category: DroneRocketSurv
  }
}

{ Element Name: Scenario
  Name: BD1
  ID: 2002
  IsInGroups: "ZiraxSpaceDefense, GroupeInconnu"
  { Child Unit1
    Category: DroneBaseAttackRocket
  }
}

{ Element Name: Scenario
  Name: Cassee
  ID: 2003
  IsInGroups: "Zirax"
  { Child Unit1
    Category: CategorieInconnue
  }
}
"""

FACTIONS = """{ Faction Id: 1, Name: "Zirax"
}
{ Faction Id: 2, Name: "Talon"
}
"""


def _scenario(tmp_path: Path) -> Path:
    conf = tmp_path / "Content" / "Configuration"
    conf.mkdir(parents=True)
    (conf / "FactionWarfare.ecf").write_text(WARFARE, encoding="utf-8")
    (conf / "Factions.ecf").write_text(FACTIONS, encoding="utf-8")
    return tmp_path


def test_scan_two_price_forms(tmp_path):
    res = scan(_scenario(tmp_path))
    assert res.editable
    by_faction = {f.faction: f for f in res.factions}
    talon = by_faction["Talon"]
    assert talon.price_child is None
    assert talon.price(1, "min") == 80 and talon.price(10, "max") == 1200
    assert talon.price(5, "min") is None          # palier absent
    zirax = by_faction["Zirax"]
    assert zirax.price_child is not None
    assert zirax.price(1, "min") == 15 and zirax.price(10, "max") == 80
    assert zirax.values["sd_group"] == "ZiraxSpaceDefense"
    assert res.globals_values["EnableSpaceDefense"] == "True"


def test_scan_units_and_scenarios(tmp_path):
    res = scan(_scenario(tmp_path))
    assert [(u.class_name, u.category) for u in res.units] == [
        ("DroneBaseAttackRocket", "DroneRocketSurv")]
    scen = {s.name: s for s in res.scenarios}
    assert scen["Surv1"].groups == "Zirax"
    assert scen["Surv1"].units == [("DroneRocketSurv", "")]


def test_checks(tmp_path):
    res = scan(_scenario(tmp_path))
    codes = sorted(i.code for i in res.issues)
    # Fantome absente de Factions.ecf ; prix min>max ; groupe inconnu ;
    # categorie inconnue. 'ZiraxSpaceDefense' n'est PAS alerte (SDScenarioGroup)
    assert codes == ["E331", "W331", "W332", "W333"]
    w331 = next(i for i in res.issues if i.code == "W331")
    assert "GroupeInconnu" in w331.message
    assert "ZiraxSpaceDefense" not in w331.message


def test_classname_accepted_as_category(tmp_path):
    # 'DroneBaseAttackRocket' est le ClassName de l'unite : adressable aussi
    res = scan(_scenario(tmp_path))
    w332 = [i for i in res.issues if i.code == "W332"]
    assert len(w332) == 1 and "CategorieInconnue" in w332[0].message


def test_set_price_keeps_original_form(tmp_path):
    root = _scenario(tmp_path)
    res = scan(root)
    by_faction = {f.faction: f for f in res.factions}
    assert set_price(by_faction["Talon"], 5, "min", 250)     # cree le palier
    assert set_price(by_faction["Zirax"], 1, "min", 20)      # bloc enfant
    assert set_sd(by_faction["Zirax"], "sd_prob_min", 0.3)
    assert set_global(res, "EnableSpaceDefense", False)
    from core.faction_warfare import save
    save(res)
    text = (root / "Content/Configuration/FactionWarfare.ecf").read_text(
        encoding="utf-8")
    assert "Lvl5MinPrice: 250" in text
    assert "PlayFieldLvl1Min: 20" in text
    # Zirax garde SA forme (bloc enfant) : aucune cle Lvl*MinPrice a plat en plus
    assert text.count("Lvl1MinPrice") == 2       # Talon + Fantome seulement
    assert "SDProbabilityMin: 0.3" in text
    assert "EnableSpaceDefense: False" in text
    # relecture coherente
    again = {f.faction: f for f in scan(root).factions}
    assert again["Talon"].price(5, "min") == 250
    assert again["Zirax"].price(1, "min") == 20


def test_missing_file(tmp_path):
    res = scan(tmp_path)
    assert not res.editable and res.factions == [] and res.issues == []
