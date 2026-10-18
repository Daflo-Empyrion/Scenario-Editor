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

"""Audit economique des marchands (core/trader_audit.py) : detection par
categorie, propositions (ligne normalisee, stocks conserves, MarketPrice par
mediane des lignes absolues), arbitrages AVEC clamp moteur, tokens intouches,
application + re-analyse propre."""

from pathlib import Path

from core.trader_audit import (BROKEN, MF_NO_PRICE, NO_BUY, UNIFORM, ZERO,
                               analyze_traders, apply_traders)

TRADER = """{ Trader Name: MarchandA
  Item1: "RockDust, mf=1.0-1.25, 10-50, mf=0.5-0.75, 50-100"
  Item2: "IronIngot, 100-150, 5-10"
  Item3: "Meat, 0, 5-10"
  Item4: "Ghost, mf=1.0-1.25, 3-5, mf=0.5-0.75, 5-10"
  Item5: "Token:42, 500-500, 5-5, 0, 0"
  Item6: "LigneIllisible"
}
{ Trader Name: MarchandB
  Item1: "IronIngot, mf=2.0-3.0, 5-10, mf=1.8-2.5, 10-30"
  Item2: "Ghost, 400-600, 5-10"
}
"""

ITEMS = """{ Item Name: RockDust
  MarketPrice: 2
}
{ Item Name: IronIngot
  MarketPrice: 100
}
{ Item Name: Meat
  MarketPrice: 30
}
{ Item Name: Ghost
  StackSize: 50
}
"""

# MarchandC : arbitrage GARANTI avec clamp — A vend 100 fixe, B vend 200 et
# rachete 190 : rachat effectif plafonne a 0.95 x 200 = 190 > 100
TRADER_ARB = TRADER + """{ Trader Name: MarchandC
  Item1: "RockDust, 100-100, 5-10, 50-50, 10-20"
  Item2: "IronIngot, 200-200, 5-10, 190-190, 10-20"
}
"""


def _scenario(tmp_path: Path, trader: str = TRADER) -> Path:
    cdir = tmp_path / "Content" / "Configuration"
    cdir.mkdir(parents=True)
    (cdir / "TraderNPCConfig.ecf").write_text(trader, encoding="utf-8")
    (cdir / "ItemsConfig.ecf").write_text(ITEMS, encoding="utf-8")
    return tmp_path


def _by_kind(rep):
    out = {}
    for p in rep.proposals:
        out.setdefault(p.kind, []).append(p)
    return out


def test_detection_all_categories(tmp_path):
    _, _, rep = analyze_traders(_scenario(tmp_path))
    by = _by_kind(rep)
    assert set(by) == {UNIFORM, NO_BUY, ZERO, MF_NO_PRICE, BROKEN}
    # uniforme (RockDust) : PAS de proposition
    assert all(p.item != "RockDust" for p in rep.proposals)
    # absolue sans rachat -> no_buy (IronIngot chez A)
    assert any(p.item == "IronIngot" and p.trader == "MarchandA"
               and p.kind == NO_BUY for p in rep.proposals)
    # vente 0 -> zero
    assert any(p.item == "Meat" and p.kind == ZERO for p in rep.proposals)
    # mf sans MarketPrice -> UNE proposition de PRIX par item (la ligne
    # absolue de B genere en plus sa propre proposition no_buy, legitime)
    ghosts = [p for p in rep.proposals
              if p.item == "Ghost" and p.kind == MF_NO_PRICE]
    assert len(ghosts) == 1 and ghosts[0].new_price == 500
    # token ignore
    assert all(p.item != "Token:42" for p in rep.proposals)
    assert rep.dashboard.n_tokens == 1
    # ligne illisible signalee, jamais proposee en reecriture
    broken = by[BROKEN]
    assert len(broken) == 1 and broken[0].new_line is None


def test_proposal_keeps_stocks_and_completes_buy(tmp_path):
    doc, idx, rep = analyze_traders(_scenario(tmp_path))
    p = next(p for p in rep.proposals
             if p.item == "IronIngot" and p.trader == "MarchandA")
    new = p.new_line
    assert new.sell_price.render() == "mf=1.0-1.25"
    assert new.buy_price.render() == "mf=0.5-0.75"
    assert new.sell_stock.render() == "5-10"        # stock conserve
    assert new.buy_max_stock.render() == "5-10"     # complete = stock vente
    # ligne derivee (mf=2.0-3.0) ramenee au moule, stocks conserves
    p2 = next(p for p in rep.proposals
              if p.item == "IronIngot" and p.trader == "MarchandB")
    assert p2.new_line.sell_price.render() == "mf=1.0-1.25"
    assert p2.new_line.buy_max_stock.render() == "10-30"


def test_arbitrage_detected_with_engine_clamp(tmp_path):
    _, _, rep = analyze_traders(_scenario(tmp_path, TRADER_ARB))
    arbs = [a for a in rep.dashboard.arbitrages if "IronIngot" in a]
    # rachat effectif de C = 0.95 x 200 = 190 > vente max de A (150 absolu)
    assert any("190" in a and "150" in a for a in arbs)


def test_apply_then_reanalyze_is_clean(tmp_path):
    root = _scenario(tmp_path, TRADER_ARB)
    doc, idx, rep = analyze_traders(root)
    actionable = [p for p in rep.proposals if p.new_line or p.new_price]
    done = apply_traders(root, doc, rep, actionable)
    assert sum(done.values()) == len(actionable)
    _, _, rep2 = analyze_traders(root)
    assert [p for p in rep2.proposals if p.new_line or p.new_price] == []
    assert rep2.dashboard.arbitrages == []
    text = (root / "Content/Configuration/TraderNPCConfig.ecf").read_text(
        encoding="utf-8")
    assert "mf=1.0-1.25" in text and "mf=0.5-0.75" in text
    # le MarketPrice cree (Ghost 500) est bien dans ItemsConfig
    items = (root / "Content/Configuration/ItemsConfig.ecf").read_text(
        encoding="utf-8")
    assert "MarketPrice: 500" in items
    # le token reste intact
    assert 'Token:42, 500-500, 5-5, 0, 0' in text


def test_real_re2_never_targets_currency():
    """Invariant stable sur donnees REELLES (l'etat du scenario evolue avec
    les applications de l'utilisateur) : aucune proposition du trader audit
    ne cible jamais une MONNAIE (item avec Credits: X) — vecu 17/10 : le
    repli a 100 proposait MoneyCard/GoldCoins/PlatinumCard."""
    from core.trader_audit import analyze_traders
    try:
        _, idx, rep = analyze_traders("C:/Dev/re2-rpg")
    except FileNotFoundError:
        return               # machine sans le scenario : test saute
    for p in rep.proposals:
        od = idx.objs.get(p.item)
        cr = od.final.get_property("Credits") if od else None
        assert cr is None, f"{p.item} est une monnaie (Credits: {cr})"


def test_currency_items_isolated(tmp_path, monkeypatch):
    """Vecu 17/10 : MoneyCard/GoldCoins/PlatinumCard portent Credits: X —
    leur valeur EST des credits. Le repli a 100 les proposait en
    MarketPrice et faussait l'economie : une monnaie est isolee (aucune
    proposition, ligne jamais reecrite)."""
    root = tmp_path / "scen"
    cdir = root / "Content" / "Configuration"
    cdir.mkdir(parents=True)
    (cdir / "ItemsConfig.ecf").write_text(
        "{ Item Name: MoneyCard\n  Credits: 1\n}\n"
        "{ Item Name: GoldCoins\n  Credits: 50\n}\n", encoding="utf-8")
    (cdir / "TraderNPCConfig.ecf").write_text(
        '{ Trader Name: Bank\n'
        '  Item1: "MoneyCard, 100-150, 3-5"\n'
        '  Item2: "GoldCoins, mf=1.0-1.25, 5-10"\n'
        '  Item3: "RockDust, 90-110, 10-20"\n'
        "}\n", encoding="utf-8")
    from core.trader_audit import analyze_traders
    doc, idx, rep = analyze_traders(root)
    # aucune proposition pour les monnaies ; RockDust absolu -> 1 proposal
    props = {p.item for p in rep.proposals}
    assert "MoneyCard" not in props and "GoldCoins" not in props
    assert rep.dashboard.n_currency == 2
    # application : les lignes monnaie restent exactement telles quelles
    apply_traders(root, doc, rep,
                  [p for p in rep.proposals if p.new_line or p.new_price])
    text = (cdir / "TraderNPCConfig.ecf").read_text(encoding="utf-8")
    assert '"MoneyCard, 100-150, 3-5"' in text
    assert '"GoldCoins, mf=1.0-1.25, 5-10"' in text
