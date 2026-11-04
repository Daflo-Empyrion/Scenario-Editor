"""Tests de la reparation des prix aberrants / recettes cycliques
(core/market_repair.py) et des garde-fous du moteur (plafond, generation)."""

from pathlib import Path

from core.market_balance import (_safe_inputs, build_report, load_index,
                                 resolve_template)

ITEMS = """{ Item Name: IronIngot
  MarketPrice: 4
}
{ Item Name: Boost
  MarketPrice: 2000000000
  Ref: BoostTemplate
}
{ Item Name: BoostTwin
  MarketPrice: 2000000000
  Ref: BoostTemplate
}
"""
TEMPLATES = """{ Template Name: BoostTemplate
  CraftTime: 10
  { Child Inputs
    IronIngot: 2
  }
}
{ Template Name: CycleRecipe
  CraftTime: 10
  { Child Inputs
    CycleRecipe: 1
    Boost: 5
    BoostTwin: 5
  }
}
{ Template Name: Boost
  CraftTime: 10
  { Child Inputs
    CycleRecipe: 1
    Boost: 5
    BoostTwin: 5
  }
}
{ Template Name: BoostTwin
  CraftTime: 10
  { Child Inputs
    CycleRecipe: 1
    Boost: 5
    BoostTwin: 5
  }
}
"""


def _scenario(tmp_path, items=ITEMS, templates=TEMPLATES, vanilla=False):
    conf = tmp_path / ("vanilla" if vanilla else "scenario") / "Content" / "Configuration"
    conf.mkdir(parents=True)
    (conf / "ItemsConfig.ecf").write_bytes(items.encode("utf-8"))
    (conf / "Templates.ecf").write_bytes(templates.encode("utf-8"))
    return conf.parent.parent


def test_generated_templates_detected(tmp_path):
    from core.market_repair import find_generated_templates
    root = _scenario(tmp_path)
    idx, _ = load_index(root)
    bad = {b.name for b in find_generated_templates(idx.templates)}
    assert bad == {"CycleRecipe", "Boost", "BoostTwin"}


def test_plan_and_apply(tmp_path):
    from core.market_repair import apply_market_repair, plan_market_repair
    root = _scenario(tmp_path)
    van = _scenario(tmp_path, vanilla=True,
                    templates="{ Template Name: BoostTemplate\n}\n",
                    items=ITEMS.replace("2000000000", "500")
                    .replace("BoostTwin\n  MarketPrice: 500", "BoostTwin\n  MarketPrice: 450"))
    plan = plan_market_repair(root, str(van))
    assert {b.name for b in plan.bad_templates} == {"CycleRecipe", "Boost", "BoostTwin"}
    assert plan.inflated == 2
    assert {(f.name, f.new, f.source) for f in plan.price_fixes} == {
        ("Boost", 500, "vanille"), ("BoostTwin", 450, "vanille")}
    res = apply_market_repair(plan)
    assert res["templates"] == 3
    idx, _ = load_index(root)
    assert "CycleRecipe" not in idx.templates
    assert resolve_template(idx, "Boost") == "BoostTemplate"
    assert idx.objs["Boost"].price == 500
    assert idx.objs["BoostTwin"].price == 450


def test_cap_blocks_absurd_cost(tmp_path):
    items = ("{ Item Name: IronIngot\n  MarketPrice: 4\n}\n"
             "{ Item Name: Expensive\n  MarketPrice: 10\n}\n")
    templates = ("{ Template Name: Expensive\n"
                 "  { Child Inputs\n    IronIngot: 1000000000\n  }\n}\n")
    root = _scenario(tmp_path, items=items, templates=templates)
    idx, _ = load_index(root)
    e = {x.name: x for x in build_report(idx).entries}["Expensive"]
    assert e.cost is None and e.target is None
    assert "suspect" in e.detail


def test_material_target_above_cap_is_refused(tmp_path):
    """Le repli materiau/masse reutilise les prix des blocs : un prix deja
    gonfle ne doit pas ressortir en cible."""
    items = ("{ Item Name: Hull\n  MarketPrice: 5000000000\n"
             "  Material: Steel\n  Mass: 10\n}\n"
             "{ Item Name: Plate\n  MarketPrice: 1000\n"
             "  Material: Steel\n  Mass: 1\n}\n")
    root = _scenario(tmp_path, items=items, templates="")
    idx, _ = load_index(root)
    e = {x.name: x for x in build_report(idx).entries}["Hull"]
    assert e.target is None


def test_safe_inputs_drop_self_and_cycles():
    edges = {"Model": ["Target", "IronIngot"], "IronIngot": []}
    out = _safe_inputs(edges, "Target",
                       [("Target", 2), ("IronIngot", 1), ("Ghost", 3),
                        ("IronIngot", 0)], 1.0)
    assert out == [("IronIngot", 1), ("Ghost", 3)]
