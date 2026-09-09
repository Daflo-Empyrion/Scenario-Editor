"""Modele economie : RangeSpec (plage ou facteur) et TradeItem (ligne Item<N>).

Fidelite de rendu : les bornes sont conservees SOUS FORME DE CHAINES (ex: '100',
'1.2') pour qu'un parse -> render sans modification reproduise exactement la
chaine d'origine ; les conversions float ne servent qu'aux maths (presets,
variantes) et a la validation (plage inversee).
"""
from dataclasses import dataclass, field
from typing import Optional

import math
import re

ITEM_KEY_RE = re.compile(r'^Item(\d+)$')
# Les marchands "CardDealer" vendent des JETONS de dialogue, pas des items :
# 'Item1: "Token:100, mf=1.1-1.2, 2-5, ..."' (present dans le fichier vanilla).
# Ces references ne figurent dans aucun ItemsConfig/BlocksConfig : le controle
# "item absent du catalogue" doit les ignorer.
TOKEN_ITEM_RE = re.compile(r'^Token:\d+$', re.IGNORECASE)


def _int_str(x: float) -> str:
    """Arrondi au chiffre SUPERIEUR, neutralise le bruit flottant
    (110.00000000000001 * 1.1 -> 110, jamais 111)."""
    return str(int(math.ceil(round(x, 6))))


def _is_int_str(s: str) -> bool:
    try:
        return float(s).is_integer()
    except ValueError:
        return False


@dataclass
class RangeSpec:
    """Valeur numerique du jeu : plage absolue '100-150', valeur unique '10', ou
    facteur sur le MarketPrice 'mf=1.1-1.2' / 'mf=0.4'."""
    lo: str
    hi: str
    ranged: bool = False
    factor: bool = False

    @classmethod
    def parse(cls, text: str) -> Optional["RangeSpec"]:
        s = (text or "").strip()
        factor = False
        if s.lower().startswith("mf="):
            factor = True
            s = s[3:].strip()
        if not s:
            return None
        if "-" in s:
            lo, _, hi = s.partition("-")
            lo, hi = lo.strip(), hi.strip()
            if not _is_number(lo) or not _is_number(hi):
                return None
            return cls(lo=lo, hi=hi, ranged=True, factor=factor)
        if not _is_number(s):
            return None
        return cls(lo=s, hi=s, ranged=False, factor=factor)

    @property
    def lo_f(self) -> float:
        return float(self.lo)

    @property
    def hi_f(self) -> float:
        return float(self.hi)

    def scaled(self, multiplier: float) -> "RangeSpec":
        """Variante pour presets/multiplicateur regional : multiplie les bornes.
        REGLE MODULE : prix/stocks ABSOLUS = entiers, arrondi au chiffre
        superieur (penurie : stock 3 / 2 -> 2). Les facteurs mf= restent
        decimaux a 2 chiffres (ce sont des ratios, le jeu calcule le prix)."""
        if self.factor:
            def _s(v: str) -> str:
                out = round(float(v) * multiplier, 2)
                if out == int(out):
                    return str(int(out))
                return str(out)
            return RangeSpec(lo=_s(self.lo), hi=_s(self.hi), ranged=self.ranged, factor=True)
        return RangeSpec(lo=_int_str(float(self.lo) * multiplier),
                         hi=_int_str(float(self.hi) * multiplier),
                         ranged=self.ranged, factor=False)

    def is_integral(self) -> bool:
        """Un facteur mf= est toujours acceptable ; une valeur ABSOLUE doit etre
        entiere (regle module : prix et stocks sans virgule)."""
        return self.factor or (_is_int_str(self.lo) and _is_int_str(self.hi))

    def converted(self, ref: float, to_factor: bool) -> "RangeSpec":
        """Bascule plage absolue <-> facteur : divise (ou multiplie) les bornes par
        le MarketPrice de reference. La regle entiere s'applique UNIQUEMENT au
        resultat absolu ; un facteur produit reste decimal (ratio). Retourne self
        si deja dans la forme demandee ou si ref est invalide."""
        if ref is None or ref == 0:
            return self
        if to_factor and not self.factor:
            def _f(v: str) -> str:
                out = round(float(v) / ref, 2)
                return str(int(out)) if out == int(out) else str(out)
            return RangeSpec(lo=_f(self.lo), hi=_f(self.hi),
                             ranged=self.ranged, factor=True)
        if not to_factor and self.factor:
            return RangeSpec(lo=_int_str(float(self.lo) * ref),
                             hi=_int_str(float(self.hi) * ref),
                             ranged=self.ranged, factor=False)
        return self

    def _with(self, factor: bool) -> "RangeSpec":
        return RangeSpec(lo=self.lo, hi=self.hi, ranged=self.ranged, factor=factor)

    def render(self) -> str:
        body = f"{self.lo}-{self.hi}" if self.ranged else self.lo
        return f"mf={body}" if self.factor else body


def _is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


@dataclass
class TradeItem:
    """Une ligne Item<N> complete. Format reel (doc en tete du fichier vanilla) :
    'Nom, prix VENTE[, stock VENTE][, prix ACHAT[, stock ACHAT max]]' -- seule la
    partie vente-prix est obligatoire ; sans partie achat, le marchand ne rachete
    pas l'item (pas de champ 'action' : c'est implicite)."""
    name: str
    sell_price: RangeSpec
    sell_stock: Optional[RangeSpec] = None
    buy_price: Optional[RangeSpec] = None
    buy_max_stock: Optional[RangeSpec] = None

    @property
    def has_buy(self) -> bool:
        return self.buy_price is not None

    @classmethod
    def parse(cls, raw_value: str) -> "TradeItem":
        """Accepte la valeur BRUTE ECF (avec ou sans guillemets exterieurs).
        Leve ValueError si la structure ne correspond pas au format du jeu --
        l'appelant garde alors la ligne intacte."""
        v = (raw_value or "").strip()
        if len(v) >= 2 and v.startswith('"') and v.endswith('"'):
            v = v[1:-1].strip()
        parts = [p.strip() for p in v.split(",") if p.strip()]
        if len(parts) < 2:
            raise ValueError(f"item trop court: {raw_value!r}")
        sell_price = RangeSpec.parse(parts[1])
        if sell_price is None:
            raise ValueError(f"prix illisible: {raw_value!r}")
        sell_stock = RangeSpec.parse(parts[2]) if len(parts) > 2 else None
        buy_price = RangeSpec.parse(parts[3]) if len(parts) > 3 else None
        buy_max_stock = RangeSpec.parse(parts[4]) if len(parts) > 4 else None
        if len(parts) > 2 and sell_stock is None:
            raise ValueError(f"stock illisible: {raw_value!r}")
        if len(parts) > 3 and buy_price is None:
            raise ValueError(f"prix d'achat illisible: {raw_value!r}")
        if len(parts) > 4 and buy_max_stock is None:
            raise ValueError(f"stock d'achat illisible: {raw_value!r}")
        return cls(name=parts[0], sell_price=sell_price, sell_stock=sell_stock,
                   buy_price=buy_price, buy_max_stock=buy_max_stock)

    def render(self, quote: bool = True) -> str:
        parts = [self.name, self.sell_price.render()]
        for spec in (self.sell_stock, self.buy_price, self.buy_max_stock):
            if spec is not None:
                parts.append(spec.render())
        s = ", ".join(parts)
        return f'"{s}"' if quote else s


def unescape_text(s: str) -> str:
    """'Salut\nA toi' (backslash-n litteral du fichier) -> vrais retours a la ligne
    pour l'affichage/edition dans l'interface."""
    return (s or "").replace("\\n", "\n")


def escape_text(s: str) -> str:
    return (s or "").replace("\r\n", "\n").replace("\n", "\\n")
