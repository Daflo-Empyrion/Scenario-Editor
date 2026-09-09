"""Vue semantique d'un TraderNPCConfig.ecf deja parse en EcfDocument.

Toute modification passe par les noeuds ECF IN-PLACE (EcfProperty.set,
add_property_line, remove_property_line) : le round-trip byte-perfect du parser
reste garanti pour chaque ligne non touchee. Les vues (TraderView) sont
ephemeres : les re-deriver apres chaque undo/rechargement (jamais de reference
figee a un document -- regle projet).
"""
from dataclasses import dataclass, field
from typing import List, Optional

from core.ecf.model import (EcfBlock, EcfBlank, EcfDocument, EcfProperty,
                            add_property_line, normalized_kind,
                            remove_property_line)
from core.ecf.parser import parse_ecf_file
from core.economy.model import ITEM_KEY_RE, TradeItem, escape_text, unescape_text

TEXT_KEYS = ("SellingText", "SellingGoods", "Discount")
DEFAULT_TRADER_EOL = "\r\n"


@dataclass
class TraderItemRow:
    """Une ligne Item<N> lue : prop est le noeud ECF vivant (edition in-place)."""
    key: str                     # 'Item1', 'Item2'... (numerotation d'origine preservee)
    prop: EcfProperty
    raw_value: str               # valeur brute ECF (guillemets inclus)
    item: Optional[TradeItem]    # None si la ligne est illisible (jamais re-ecrite sans action)


@dataclass
class TraderView:
    block: EcfBlock
    name: str
    selling_text: str            # texte DESHAPE (\n reels) pour l'interface
    selling_goods: str
    discount: str
    rows: List[TraderItemRow] = field(default_factory=list)

    def row_by_key(self, key: str) -> Optional[TraderItemRow]:
        for r in self.rows:
            if r.key == key:
                return r
        return None


def _strip_quotes(v: Optional[str]) -> str:
    if not v:
        return ""
    v = v.strip()
    if len(v) >= 2 and v.startswith('"') and v.endswith('"'):
        return v[1:-1]
    return v


def _item_raw_value(prop: EcfProperty) -> Optional[str]:
    """Valeur complete de la ligne Item<N>. PIEGE : une ligne NON quotee est
    eclatee en plusieurs paires par le parser ECF (virgules hors guillemets ->
    paires (None, fragment)), ex: 'Item1: Foo, 100-150, 3-5' ->
    [('Item1','Foo'), (None,'100-150'), (None,'3-5')]. On recollera a
    l'ecriture (set_item). Retourne None si la 1ere paire n'est pas Item<N>."""
    if not prop.pairs:
        return None
    key, first = prop.pairs[0]
    if key is None or not ITEM_KEY_RE.match(key):
        return None
    parts = [first or ""]
    for k, v in prop.pairs[1:]:
        if k is not None:
            break  # propriete partagee sur la meme ligne (rare) : on s'arrete
        parts.append(v or "")
    return ", ".join(parts)


def _view(block: EcfBlock) -> TraderView:
    rows = []
    for child in block.children:
        if not isinstance(child, EcfProperty):
            continue
        raw = _item_raw_value(child)
        if raw is None:
            continue
        try:
            item = TradeItem.parse(raw)
        except ValueError:
            item = None
        rows.append(TraderItemRow(key=child.pairs[0][0], prop=child, raw_value=raw, item=item))
    return TraderView(
        block=block,
        name=_strip_quotes(block.get("Name")) or "",
        selling_text=unescape_text(_strip_quotes(block.get_property("SellingText"))),
        selling_goods=_strip_quotes(block.get_property("SellingGoods")),
        discount=_strip_quotes(block.get_property("Discount")),
        rows=rows)


class TraderConfigDoc:
    """Enrobage semantique d'un EcfDocument de TraderNPCConfig.ecf."""

    def __init__(self, doc: EcfDocument):
        self.doc = doc

    # -- lecture ------------------------------------------------------------

    def views(self) -> List[TraderView]:
        return [_view(n) for n in self.doc.nodes
                if isinstance(n, EcfBlock) and normalized_kind(n.kind) == "Trader"]

    def names(self) -> List[str]:
        return [v.name for v in self.views()]

    def find(self, name: str) -> Optional[EcfBlock]:
        for n in self.doc.nodes:
            if isinstance(n, EcfBlock) and normalized_kind(n.kind) == "Trader" \
                    and _strip_quotes(n.get("Name")) == name:
                return n
        return None

    # -- ecriture (in-place, dirty=True) ------------------------------------

    @staticmethod
    def set_selling_text(block: EcfBlock, text: str) -> bool:
        return block.set_property("SellingText", f'"{escape_text(text)}"')

    @staticmethod
    def set_selling_goods(block: EcfBlock, goods: str) -> bool:
        goods = (goods or "").strip()
        return block.set_property("SellingGoods", f'"{goods}"' if goods else goods)

    @staticmethod
    def set_discount(block: EcfBlock, discount: str) -> bool:
        discount = (discount or "").strip()
        return block.set_property("Discount", discount)

    @staticmethod
    def set_item(row: TraderItemRow, item: TradeItem) -> None:
        quote = row.raw_value.strip().startswith('"')
        rendered = item.render(quote=quote)
        if quote:
            # forme quotee : la chaine entiere tient dans UNE paire (virgules
            # protegees par les guillemets, le parser ECF ne l'eclate pas)
            row.prop.set(row.key, rendered)
            return
        # forme non quotee : la ligne a ete eclepee en paires (None, fragment)
        # par le parser -> on reconstruit la meme structure (render identique
        # au re-parsing, jamais de perte au round-trip).
        parts = rendered.split(", ")
        prop = row.prop
        prop.pairs = [(row.key, parts[0])] + [(None, p) for p in parts[1:]]
        prop.dirty = True

    def next_item_number(self, block: EcfBlock) -> int:
        last = 0
        for child in block.children:
            if isinstance(child, EcfProperty) and child.pairs and child.pairs[0][0]:
                m = ITEM_KEY_RE.match(child.pairs[0][0])
                if m:
                    last = max(last, int(m.group(1)))
        return last + 1

    def add_item(self, block: EcfBlock, item: TradeItem) -> EcfProperty:
        key = f"Item{self.next_item_number(block)}"
        return add_property_line(block, [(key, item.render(quote=True))])

    @staticmethod
    def remove_item(block: EcfBlock, row: TraderItemRow) -> bool:
        return remove_property_line(block, row.prop)

    # -- cycle de vie des marchands -----------------------------------------

    def create_trader(self, name: str) -> EcfBlock:
        """Nouveau bloc Trader minimal (Name + SellingText/SellingGoods vides),
        insere en fin de document avec separation par ligne vide."""
        eol = DEFAULT_TRADER_EOL
        block = EcfBlock(indent="", kind="Trader", pairs=[("Name", f'"{name}"')],
                         comment=None, eol=eol, raw_open="", close_raw="}" + eol,
                         dirty=True)
        add_property_line(block, [("SellingText", '""')])
        add_property_line(block, [("SellingGoods", '""')])
        if self.doc.nodes and not isinstance(self.doc.nodes[-1], EcfBlank):
            self.doc.nodes.append(EcfBlank(eol))
        self.doc.nodes.append(EcfBlank(eol))
        self.doc.nodes.append(block)
        return block

    def duplicate_trader(self, source: EcfBlock, new_name: str) -> EcfBlock:
        """Duplication FIDELE : les valeurs brutes des lignes (items, texte...) sont
        recopiees telles quelles (numerotation Item<N> comprise), seule l'identite
        Name change."""
        eol = source.eol or DEFAULT_TRADER_EOL
        block = EcfBlock(indent=source.indent, kind=source.kind,
                         pairs=[("Name", f'"{new_name}"')], comment=None, eol=eol,
                         raw_open="", close_raw="}" + eol, dirty=True)
        for child in source.children:
            if isinstance(child, EcfProperty) and child.pairs:
                add_property_line(block, list(child.pairs))
        if self.doc.nodes and not isinstance(self.doc.nodes[-1], EcfBlank):
            self.doc.nodes.append(EcfBlank(eol))
        self.doc.nodes.append(EcfBlank(eol))
        self.doc.nodes.append(block)
        return block

    def remove_trader(self, block: EcfBlock) -> bool:
        if block in self.doc.nodes:
            self.doc.nodes.remove(block)
            return True
        return False


_names_cache: dict = {}


def load_trader_names(path) -> List[str]:
    """Noms des marchands d'un TraderNPCConfig.ecf, cache par mtime+taille (les
    playfields et le dialogue economie re-consultent souvent)."""
    from pathlib import Path as _Path
    p = _Path(path)
    try:
        st = p.stat()
        sig = (st.st_mtime_ns, st.st_size)
    except OSError:
        return []
    hit = _names_cache.get(str(p))
    if hit is not None and hit[0] == sig:
        return hit[1]
    try:
        names = TraderConfigDoc(parse_ecf_file(p)).names()
    except Exception:
        return []
    _names_cache[str(p)] = (sig, names)
    return names
