"""Presets economie (niveau APPLICATION, reutilisables entre scenarios) :
- operations parametriques : inflation (+X% sur les prix), penurie (stocks / N) ;
- profils types : militaire / agricole embarques + profils utilisateur libres
  (capture d'un marchand existant), stockes en JSON dans CONFIG_DIR ;
- variantes regionales : 'Bertrams @+50%' = duplication avec prix recalcules --
  c'est l'emulation du 'multiplicateur de prix par station' (inexistant en jeu).

Toutes les operations mutent le document ECF in-place (round-trip byte-perfect
pour les lignes non touchees) ; l'appelant gere snapshot undo + marque modifie.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from core.economy.model import RangeSpec, TradeItem
from core.economy.trader_config import TraderConfigDoc, TraderView
from core.settings import CONFIG_DIR


# ------------------------------------------------------------ operations

def scale_profile_prices(config: TraderConfigDoc, name: str, multiplier: float) -> int:
    """Inflation/deflation : multiplie les PRIX (vente + achat) d'un profil.
    Les stocks ne bougent pas. Retourne le nombre d'items touches."""
    view = _view_by_name(config, name)
    if view is None or multiplier <= 0:
        return 0
    touched = 0
    for row in view.rows:
        if row.item is None:
            continue
        item = row.item
        item.sell_price = item.sell_price.scaled(multiplier)
        if item.buy_price is not None:
            item.buy_price = item.buy_price.scaled(multiplier)
        TraderConfigDoc.set_item(row, item)
        touched += 1
    return touched


def scale_profile_stocks(config: TraderConfigDoc, name: str, divisor: float) -> int:
    """Penurie : DIVISE les stocks (vente + achat max) d'un profil par divisor.
    Retourne le nombre d'items touches."""
    view = _view_by_name(config, name)
    if view is None or divisor <= 0:
        return 0
    touched = 0
    for row in view.rows:
        if row.item is None:
            continue
        item = row.item
        if item.sell_stock is not None:
            item.sell_stock = item.sell_stock.scaled(1.0 / divisor)
        if item.buy_max_stock is not None:
            item.buy_max_stock = item.buy_max_stock.scaled(1.0 / divisor)
        TraderConfigDoc.set_item(row, item)
        touched += 1
    return touched


def replace_profile_items(config: TraderConfigDoc, name: str,
                          items: List[TradeItem], goods: Optional[str] = None,
                          discount: Optional[str] = None) -> bool:
    """Profil type : remplace TOUT le catalogue du marchand (numerotation
    Item<N> regeneree depuis 1) + optionnellement categorie et remise."""
    view = _view_by_name(config, name)
    if view is None:
        return False
    block = view.block
    for row in list(view.rows):
        TraderConfigDoc.remove_item(block, row)
    for it in items:
        config.add_item(block, it)
    if goods:
        TraderConfigDoc.set_selling_goods(block, goods)
    if discount:
        TraderConfigDoc.set_discount(block, discount)
    return True


def create_scaled_variant(config: TraderConfigDoc, source_name: str,
                          multiplier: float) -> Optional[str]:
    """Duplique le profil avec prix multiplies (emulation du multiplicateur
    regional inexistant en jeu). Nom : 'Source @+50%' (suffixe -2... si pris).
    Retourne le nom de la variante, None si la source est absente."""
    source = config.find(source_name)
    if source is None or multiplier <= 0 or multiplier == 1.0:
        return None
    pct = int(round((multiplier - 1.0) * 100))
    base = f"{source_name} @{pct:+d}%"
    variant_name = base
    n = 2
    while config.find(variant_name) is not None:
        variant_name = f"{base}-{n}"
        n += 1
    variant = config.duplicate_trader(source, variant_name)
    view = next(v for v in config.views() if v.block is variant)
    for row in view.rows:
        if row.item is None:
            continue
        item = row.item
        item.sell_price = item.sell_price.scaled(multiplier)
        if item.buy_price is not None:
            item.buy_price = item.buy_price.scaled(multiplier)
        TraderConfigDoc.set_item(row, item)
    return variant_name


# ------------------------------------------------------------ profils types

@dataclass
class TypeProfile:
    key: str
    selling_goods: str
    discount: str
    items: List[TradeItem]


def _ti(name: str, sell: str, stock: str) -> TradeItem:
    return TradeItem(name=name, sell_price=RangeSpec.parse(sell),
                     sell_stock=RangeSpec.parse(stock))


BUILTIN_TYPE_PROFILES: Dict[str, TypeProfile] = {
    "military": TypeProfile(
        key="military", selling_goods="trwWeapons", discount="0.05",
        items=[
            _ti("PulseRifle", "mf=1.2-1.4", "2-5"),
            _ti("AssaultRifle", "mf=1.2-1.4", "2-5"),
            _ti("ShotgunT0", "mf=1.1-1.3", "2-5"),
            _ti("RocketLauncher", "mf=1.3-1.5", "1-3"),
            _ti("AmmoBrit6mm", "mf=1.1-1.3", "50-150"),
            _ti("AmmoBrit15mm", "mf=1.1-1.3", "30-80"),
            _ti("Rocket3", "mf=1.2-1.4", "10-30"),
        ]),
    "agricultural": TypeProfile(
        key="agricultural", selling_goods="trwFood", discount="0.08",
        items=[
            _ti("Sprouts", "mf=0.9-1.1", "20-60"),
            _ti("TomatoDish", "mf=0.9-1.1", "10-30"),
            _ti("CannedVegetables", "mf=0.8-1.0", "20-50"),
            _ti("MeatPie", "mf=0.9-1.1", "10-30"),
            _ti("GrowingPlotSmall", "mf=1.0-1.2", "2-8"),
            _ti("FarmLight", "mf=1.1-1.3", "1-5"),
        ]),
}


def snapshot_profile(view: TraderView) -> dict:
    """Capture complete d'un profil (fiche + valeurs brutes des items) pour
    stockage JSON -- les items sont gardes en CHAINE BRUTE : la reapplication
    est fidele meme pour des formes que TradeItem ne normalise pas."""
    return {
        "name": view.name,
        "selling_goods": view.selling_goods,
        "discount": view.discount,
        "items": [row.raw_value for row in view.rows if row.item is not None],
    }


def apply_snapshot(config: TraderConfigDoc, name: str, snapshot: dict) -> bool:
    items = []
    for raw in snapshot.get("items", []):
        try:
            items.append(TradeItem.parse(raw))
        except ValueError:
            continue
    return replace_profile_items(config, name, items,
                                 goods=snapshot.get("selling_goods") or None,
                                 discount=snapshot.get("discount") or None)


# ------------------------------------------------------------ stockage JSON

def _presets_dir() -> Path:
    return Path(CONFIG_DIR) / "economy_presets"


def _safe_name(name: str) -> str:
    return re.sub(r'[^A-Za-z0-9_-]+', '_', name).strip('_') or "preset"


def save_user_preset(name: str, snapshot: dict) -> Path:
    d = _presets_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{_safe_name(name)}.json"
    path.write_text(json.dumps({**snapshot, "name": name}, ensure_ascii=False,
                               indent=1), encoding="utf-8")
    return path


def list_user_presets() -> List[dict]:
    out = []
    d = _presets_dir()
    if not d.is_dir():
        return out
    for f in sorted(d.glob("*.json")):
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out


def delete_user_preset(name: str) -> bool:
    path = _presets_dir() / f"{_safe_name(name)}.json"
    if path.is_file():
        path.unlink()
        return True
    return False


def _view_by_name(config: TraderConfigDoc, name: str) -> Optional[TraderView]:
    block = config.find(name)
    if block is None:
        return None
    return next((v for v in config.views() if v.block is block), None)
