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

"""AUDIT ECONOMIQUE DES MARCHANDS (chantier 17/10/2026) : generalise a tout
scenario, sans IA, ce qui a ete fait a la main sur RE2-RPG.

Analyse TraderNPCConfig.ecf face aux MarketPrice effectifs (REF resolus,
core/market_balance) et propose, LIGNE PAR LIGNE et cochable :

  1. uniformisation  : vente mf=<vente lo-hi>, rachat mf=<rachat lo-hi>
     (defauts 1.0-1.25 / 0.5-0.75, reglables) ; les prix ABSOLUS sont
     convertis, les fourchettes derivees ramenees au moule ; stocks de
     vente conserves tels quels ; stock max de rachat conserve s'il est
     vivant, sinon = stock de vente ;
  2. rachat complete : toute ligne vendue non-Token sans rachat (ou rachat
     0) recoit la partie achat — plus aucune ligne a 0 ;
  3. MarketPrice manquant : un item vendu en mf= sans MarketPrice recoit
     une proposition de prix = mediane de ses lignes ABSOLUES existantes
     dans le fichier, sinon la valeur standard (defaut 100, reglable).

Les lignes Token:* sont INTACTES par conception (jetons de dialogue, le
format vanilla officiel les vent avec rachat 0). Les lignes illisibles
sont signalees, jamais reecrites.

Le tableau de bord signale en plus (informatif, corrige par 1-2-3) :
arbitrages inter-marchands RECALCULES AVEC le clamp du moteur (rachat
effectif plafonne a 0.95 x la vente du meme marchand), disparites de prix
de vente du meme item entre marchands, spreads internes declares > 0.95.
"""
from __future__ import annotations

import statistics

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.ecf.model import EcfBlock, add_property_line, normalized_kind
from core.ecf.parser import parse_ecf_file
from core.economy.model import RangeSpec, TradeItem
from core.economy.trader_config import TraderConfigDoc
from core.fsutil import atomic_write_text, central_backup
from core.market_balance import (MarketIndex, _num, load_index,
                                 resolve_price)

# Fourchettes validees RE2 (17/10) — parametrables dans l'UI
DEFAULT_SELL = ("1.0", "1.25")
DEFAULT_BUY = ("0.5", "0.75")
DEFAULT_FALLBACK_PRICE = 100     # jeton de quete sans aucune reference
CLAMP_SPREAD = 0.95              # le moteur garantit 5% de marge au pire stock

UNIFORM, NO_BUY, MF_NO_PRICE, ZERO, BROKEN, TOKEN, MONNAIE = (
    "uniform", "no_buy", "mf_no_price", "zero", "broken", "token",
    "monnaie")
KINDS = (UNIFORM, NO_BUY, MF_NO_PRICE, ZERO, BROKEN)


@dataclass
class TraderProposal:
    """Une correction cochable : soit une ligne Item reecrite, soit un
    MarketPrice cree (un seul des deux champs de cible est rempli)."""
    kind: str                    # cle de KINDS
    trader: str
    item_key: str                # 'Item12' (ligne) ou '' (MarketPrice)
    item: str
    detail: str                  # pourquoi
    current: str                 # ligne/prix actuel (affichage)
    new_line: Optional[TradeItem] = None    # proposition de ligne
    new_price: Optional[int] = None         # proposition de MarketPrice


@dataclass
class TraderDashboard:
    n_traders: int = 0
    n_lines: int = 0
    n_tokens: int = 0
    n_currency: int = 0
    arbitrages: List[str] = field(default_factory=list)   # boucles garanties
    disparities: List[str] = field(default_factory=list)  # top disparites
    max_disparity: float = 1.0


@dataclass
class TraderReport:
    proposals: List[TraderProposal] = field(default_factory=list)
    dashboard: TraderDashboard = field(default_factory=TraderDashboard)
    # noeuds vivants pour l'application (jamais serialises)
    rows_by_key: Dict[Tuple[str, str], object] = field(default_factory=dict)


def _dead(spec: Optional[RangeSpec]) -> bool:
    return spec is None or (float(spec.lo) == 0 and float(spec.hi) == 0)


def _is_uniform(it: TradeItem, sell: RangeSpec, buy: RangeSpec) -> bool:
    """La ligne est-elle DEJA exactement au moule demandé ?"""
    def same(a: RangeSpec, b: RangeSpec) -> bool:
        return (a.factor and b.factor
                and float(a.lo) == float(b.lo) and float(a.hi) == float(b.hi))
    if not same(it.sell_price, sell):
        return False
    if not it.has_buy or not same(it.buy_price, buy):
        return False
    return not _dead(it.buy_max_stock)


def analyze_traders(scenario_root, sell: Tuple[str, str] = DEFAULT_SELL,
                    buy: Tuple[str, str] = DEFAULT_BUY,
                    fallback_price: int = DEFAULT_FALLBACK_PRICE
                    ) -> Tuple[TraderConfigDoc, MarketIndex, TraderReport]:
    """Analyse complete : (doc vivant, index des prix, rapport)."""
    root = Path(scenario_root)
    cdir = root / "Content" / "Configuration"
    if not cdir.is_dir():
        cdir = root / "Configuration"
    trader_path = cdir / "TraderNPCConfig.ecf"
    doc = TraderConfigDoc(parse_ecf_file(trader_path))
    idx, _ = load_index(root)

    # bornes normalisees ("1.00" -> "1.0") : rendu stable quelle que soit la
    # source (spins a deux decimales, presets, code)
    sell_spec = RangeSpec(lo=str(float(sell[0])), hi=str(float(sell[1])),
                          ranged=True, factor=True)
    buy_spec = RangeSpec(lo=str(float(buy[0])), hi=str(float(buy[1])),
                         ranged=True, factor=True)
    report = TraderReport()
    dash = report.dashboard
    proposed_prices: set = set()

    def _is_currency(name: str) -> bool:
        """Monnaie du jeu : propriete Credits presente (MoneyCard 1,
        GoldCoins 50, PlatinumCard 10000) — leur valeur EST des credits,
        un MarketPrice n'a pas de sens et fausserait l'economie."""
        od = idx.objs.get(name)
        if od is None:
            return False
        c = od.final.get_property("Credits")
        return c is not None and _num(c) is not None and _num(c) > 0

    # mediane des lignes absolues par item (base des MarketPrice proposes)
    abs_values: Dict[str, list] = {}
    for v in doc.views():
        for r in v.rows:
            if r.item and not r.item.sell_price.factor:
                hi = float(r.item.sell_price.hi)
                if hi > 0 and not r.item.name.startswith("Token:"):
                    abs_values.setdefault(r.item.name, []).extend(
                        (float(r.item.sell_price.lo), hi))

    for v in doc.views():
        dash.n_traders += 1
        for r in v.rows:
            dash.n_lines += 1
            if r.item is None:
                report.proposals.append(TraderProposal(
                    kind=BROKEN, trader=v.name, item_key=r.key,
                    item="?", detail="ligne illisible", current=r.raw_value[:60]))
                continue
            it: TradeItem = r.item
            if it.name.startswith("Token:"):
                dash.n_tokens += 1
                continue
            if _is_currency(it.name):
                # monnaie du jeu (Credits: X) : ligne INTOUCHEE et isolee —
                # ni uniformisation ni MarketPrice (vecu 17/10 : le repli a
                # 100 proposait MoneyCard/GoldCoins/PlatinumCard et aurait
                # fausse l'economie)
                dash.n_currency += 1
                continue
            price = resolve_price(idx, it.name)
            if price is None and it.name not in proposed_prices:
                proposed_prices.add(it.name)     # une seule prop. par item
                vals = abs_values.get(it.name)
                med = statistics.median(vals) if vals else fallback_price
                report.proposals.append(TraderProposal(
                    kind=MF_NO_PRICE, trader=v.name, item_key="", item=it.name,
                    detail=("mf= sans MarketPrice ; mediane des lignes "
                            "absolues" if vals else
                            "mf= sans MarketPrice ; aucune reference, "
                            "valeur standard"),
                    current="aucun", new_price=max(1, round(med))))
            kind = None
            if _is_uniform(it, sell_spec, buy_spec):
                continue
            zero_sell = (not it.sell_price.factor
                         and float(it.sell_price.hi) <= 0)
            kind = (ZERO if zero_sell else
                    NO_BUY if (not it.has_buy or _dead(it.buy_price))
                    else UNIFORM)
            stock = it.sell_stock
            buy_max = it.buy_max_stock if not _dead(it.buy_max_stock) else stock
            new = TradeItem(name=it.name, sell_price=sell_spec,
                            sell_stock=stock, buy_price=buy_spec,
                            buy_max_stock=buy_max)
            report.proposals.append(TraderProposal(
                kind=kind, trader=v.name, item_key=r.key, item=it.name,
                detail={"uniform": "prix non uniforme (absolu ou fourchette "
                                   "derivee)",
                        "no_buy": "vendu sans rachat (ou rachat 0)",
                        "zero": "prix de vente a 0"}[kind],
                current=_render_current(it), new_line=new))
            report.rows_by_key[(v.name, r.key)] = r

    _dashboard_arbitrages(doc, idx, report)
    return doc, idx, report


def _render_current(it: TradeItem) -> str:
    return it.render(quote=False)


def _credits(spec: RangeSpec, price: Optional[int]) -> Optional[Tuple[float, float]]:
    lo, hi = float(spec.lo), float(spec.hi)
    if spec.factor:
        return (lo * price, hi * price) if price else None
    return (lo, hi)


def _dashboard_arbitrages(doc: TraderConfigDoc, idx: MarketIndex,
                          report: TraderReport) -> None:
    """Boucles d'argent garanties, AVEC le clamp du moteur : le rachat
    effectif d'un marchand est plafonne a 0.95 x SA vente dynamique."""
    dash = report.dashboard
    sell: Dict[str, list] = {}
    buy: Dict[str, list] = {}
    for v in doc.views():
        for r in v.rows:
            if not r.item or r.item.name.startswith("Token:"):
                continue
            it = r.item
            price = resolve_price(idx, it.name)
            s = _credits(it.sell_price, price)
            if not s or s[1] <= 0:
                continue
            sell.setdefault(it.name, []).append((v.name, s[0], s[1]))
            if it.has_buy and not _dead(it.buy_price):
                b = _credits(it.buy_price, price)
                if b and b[1] > 0:
                    buy.setdefault(it.name, []).append((v.name, b[0], b[1]))
    disp = []
    for item, sellers in sell.items():
        if len(sellers) > 1:
            lo = min(s[1] for s in sellers)
            hi = max(s[2] for s in sellers)
            if hi > lo:
                disp.append((hi / lo, item))
        for buyer, _, bhi in buy.get(item, []):
            own = next(((s[1], s[2]) for s in sellers if s[0] == buyer), None)
            if own is not None:
                # le moteur plafonne le rachat a 0.95 x SA vente dynamique ;
                # pire cas pour l'arbitrageur : B plein -> rachat au plus bas
                eff = 0.95 * own[0]
            else:
                eff = bhi    # acheteur non-vendeur : AUCUN clamp connu
            for seller, slo, shi in sellers:
                if seller != buyer and eff - shi > 0.5:
                    dash.arbitrages.append(
                        f"{item}: acheter {seller} <={shi:.0f} -> "
                        f"revendre {buyer} >={eff:.0f}")
    disp.sort(reverse=True)
    dash.disparities = [f"{item}: x{ratio:.1f}" for ratio, item in disp[:10]]
    dash.max_disparity = disp[0][0] if disp else 1.0


def apply_traders(scenario_root, doc: TraderConfigDoc,
                  report: TraderReport, proposals: List[TraderProposal],
                  sell: Tuple[str, str] = DEFAULT_SELL,
                  buy: Tuple[str, str] = DEFAULT_BUY
                  ) -> Dict[str, int]:
    """Applique les propositions cochees : lignes reecrites via set_item,
    MarketPrice crees dans Items/BlocksConfig. Backups central puis
    ecriture atomique. Retourne {fichier: n_changements}."""
    root = Path(scenario_root)
    cdir = root / "Content" / "Configuration"
    if not cdir.is_dir():
        cdir = root / "Configuration"

    n_lines = 0
    for p in proposals:
        if p.new_line is None:
            continue
        row = report.rows_by_key.get((p.trader, p.item_key))
        if row is None:
            continue
        TraderConfigDoc.set_item(row, p.new_line)
        n_lines += 1
    done: Dict[str, int] = {}
    if n_lines:
        trader_path = cdir / "TraderNPCConfig.ecf"
        central_backup(trader_path, "trader")
        atomic_write_text(trader_path, doc.doc.render())
        done[str(trader_path)] = n_lines

    prices = [p for p in proposals if p.new_price is not None]
    if prices:
        # re-parse dedie : noeuds modifies et document rendu du MEME parse
        docs = {}
        nodes = {}
        for fname, kind in (("ItemsConfig.ecf", "Item"),
                            ("BlocksConfig.ecf", "Block")):
            path = cdir / fname
            if not path.is_file():
                continue
            d = parse_ecf_file(path)
            docs[path] = d
            for node in d.nodes:
                if isinstance(node, EcfBlock) and normalized_kind(node.kind) == kind:
                    name = (node.get("Name") or "").strip().strip('"')
                    if name:
                        nodes[name] = node
        touched: Dict[Path, int] = {}
        for p in prices:
            node = nodes.get(p.item)
            if node is None:
                continue
            if not node.set_property("MarketPrice", str(p.new_price)):
                add_property_line(node, [("MarketPrice", str(p.new_price))])
            owner = next(path for path, d in docs.items()
                         if any(n is node for n in d.nodes))
            touched[owner] = touched.get(owner, 0) + 1
        for path, n in touched.items():
            central_backup(path, "market_price")
            atomic_write_text(path, docs[path].render())
            done[str(path)] = n
    return done
