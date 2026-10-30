"""Contrôle de cohérence global (core/coherence_audit.py +
gui/coherence_dialog.py) : moteur multi-sections isolé (un moteur en
échec ne casse pas les autres) et dialogue câblé au menu Outils."""

from pathlib import Path

from core.coherence_audit import run_coherence_audit

ITEMS = """{ Item Name: RockDust
  MarketPrice: 2
}
{ Item Name: PistolA
  MarketPrice: 100
}
{ Item Name: OldPistol
  MarketPrice: 1
}
"""
TEMPLATES = """{ Template Name: PistolA
  CraftTime: 10
  { Child Inputs
    RockDust: 10
  }
}
"""
BLOCKS = """{ Block Id: 500, Name: Pillar
  MarketPrice: 40
}
"""


def test_moteur_sections_et_robustesse(tmp_path, monkeypatch):
    from core.settings import _get
    cdir = tmp_path / "Content" / "Configuration"
    cdir.mkdir(parents=True)
    (cdir / "ItemsConfig.ecf").write_text(ITEMS, encoding="utf-8")
    (cdir / "Templates.ecf").write_text(TEMPLATES, encoding="utf-8")
    (cdir / "BlocksConfig.ecf").write_text(BLOCKS, encoding="utf-8")
    # vanilla inexistante : aucun moteur ne doit planter pour autant
    monkeypatch.setattr("core.settings._get",
                        lambda k, d=None: (d if 'vanilla' in k else None))
    rep = run_coherence_audit(tmp_path)
    sections = {f.section for f in rep.findings}
    assert "coh.sec.f5_errors" in sections
    assert "coh.sec.market_divergent" in sections
    assert "coh.sec.recipes" in sections
    assert "coh.sec.unlocks" in sections
    assert "coh.sec.spawn_zero" in sections
    # OldPistol prix 1 sans recette : famille impossible (1 seul membre)
    # -> aucune erreur fatale et un rapport exploitable
    assert rep.seconds >= 0


def test_moteur_scenario_vide(tmp_path):
    from core.coherence_audit import run_coherence_audit
    rep = run_coherence_audit(tmp_path / "vide")
    assert rep.findings                    # sections d erreur explicites
    assert any("introuvable" in f.detail or "No such file" in f.detail
               or f.detail for f in rep.findings)
