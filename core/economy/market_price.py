"""Index des MarketPrice (ItemsConfig.ecf + BlocksConfig.ecf) -- sert a la
bascule plage absolue <-> facteur 'mf=' et a la validation (item inexistant).

La copie de travail est PRIORITAIRE ; les fichiers de l'installation vanille ne
sont qu'un REPLI pour les items qu'elle ne surcharge pas (lecture seule, jamais
ecrits -- regle projet). Index cache par mtime+taille (meme pattern que
core/localization_lookup) ; pas de cache widget au-dessus.
"""
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.ecf.model import EcfBlock
from core.ecf.parser import parse_ecf_file

_cache: Dict[str, Tuple[tuple, Dict[str, Optional[float]]]] = {}


def _signature(paths: List[Path]) -> tuple:
    sig = []
    for p in paths:
        try:
            st = p.stat()
            sig.append((str(p), st.st_mtime_ns, st.st_size))
        except OSError:
            sig.append((str(p), None, None))
    return tuple(sig)


def _parse_market_price(raw: Optional[str]) -> Optional[float]:
    if raw is None:
        return None
    v = raw.strip().strip('"')
    if not v:
        return None
    # La ligne peut porter plusieurs paires ('MarketPrice: 126, display: false') :
    # get() ne retourne que la valeur de la cle -> '126' seul, mais restons tolérant.
    v = v.split(",")[0].strip()
    try:
        return float(v)
    except ValueError:
        return None


def _scan_file(path: Path) -> Dict[str, Optional[float]]:
    out: Dict[str, Optional[float]] = {}
    try:
        doc = parse_ecf_file(path)
    except Exception:
        return out
    for node in doc.nodes:
        if not isinstance(node, EcfBlock):
            continue
        name = node.get("Name")
        if not name:
            continue
        name = name.strip().strip('"')
        if not name:
            continue
        out[name] = _parse_market_price(node.get_property("MarketPrice"))
    return out


def build_index(ecf_paths: List[Path]) -> Dict[str, Optional[float]]:
    """Fusionne les fichiers donnes. ORDRE = PRIORITE : le premier prix non nul
    pour un nom gagne -- l'appelant passe la copie de travail D'ABORD, la
    vanille ensuite (jamais l'inverse, sinon la vanille ecraserait les prix du
    scenario). Un item sans MarketPrice est indexe a None (existe, prix non
    reference)."""
    paths = [Path(p) for p in ecf_paths if Path(p).is_file()]
    key = str([str(p) for p in paths])
    sig = _signature(paths)
    cached = _cache.get(key)
    if cached is not None and cached[0] == sig:
        return cached[1]
    index: Dict[str, Optional[float]] = {}
    for p in paths:
        for name, price in _scan_file(p).items():
            if name not in index or index[name] is None:
                index[name] = price
    _cache[key] = (sig, index)
    return index


def lookup_case_insensitive(index: Dict[str, Optional[float]], name: str) -> Optional[float]:
    """Repli sans casse (les chaines trader sont normalement exactes, mais un
    scenario modde peut avoir une casse differente du catalogue)."""
    if name in index:
        return index[name]
    low = name.lower()
    for k, v in index.items():
        if k.lower() == low:
            return v
    return None
