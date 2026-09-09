"""Catalogue global d'items/blocs -- source unique des selecteurs de
l'application (editeur d'economie en premier, retrofits ensuite).

Une SEULE passe sur ItemsConfig.ecf + BlocksConfig.ecf (cache par mtime+taille,
meme pattern que market_price) produit des CatalogEntry : nom technique, source
(item/bloc), categorie du jeu (propriete 'Category', trimee -- Weapons, Food,
Devices, BuildingBlocks...), MarketPrice et cle d'icone.

REGLES de deduplication (retour utilisateur 09/09/2026) :
- un meme nom present dans les DEUX fichiers donne DEUX entrees (item ET bloc
  sont des choses differentes, on montre la source, pas de fusion) ;
- si le MEME fichier existe en copie de travail ET en vanille (les deux passes
  par l'appelant, copie de travail en PREMIER), l'entree de la copie de travail
  GAGNE et celle de la vanille est ignoree -- premiere occurrence prioritaire.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.ecf.model import EcfBlock
from core.ecf.parser import parse_ecf_file

SOURCE_ITEM = "item"
SOURCE_BLOCK = "block"

_cache: Dict[str, Tuple[tuple, List["CatalogEntry"]]] = {}


@dataclass(frozen=True)
class CatalogEntry:
    name: str                      # nom technique (cle utilisee par le jeu)
    source: str                    # SOURCE_ITEM | SOURCE_BLOCK
    category: str                  # 'Category' trimee ('' si absente)
    market_price: Optional[float]
    icon_key: str                  # cle de resolution d'icone (Icon sinon nom)

    @property
    def key(self) -> str:
        """Cle unique d'entree : un meme nom existe possiblement en version
        item ET bloc (deux lignes distinctes dans le catalogue)."""
        return f"{self.source}:{self.name}"


def _parse_market_price(raw: Optional[str]) -> Optional[float]:
    if raw is None:
        return None
    v = raw.strip().strip('"')
    if not v:
        return None
    v = v.split(",")[0].strip()
    try:
        return float(v)
    except ValueError:
        return None


def _scan_file(path: Path, source: str) -> List[CatalogEntry]:
    try:
        doc = parse_ecf_file(path)
    except Exception:
        return []
    by_key: Dict[str, CatalogEntry] = {}
    for node in doc.nodes:
        if not isinstance(node, EcfBlock):
            continue
        name = (node.get("Name") or "").strip().strip('"')
        if not name:
            continue
        category = (node.get_property("Category") or "").strip()
        # REGLE fiche info (core/block_info_card.py) : la cle d'icone est la
        # propriete 'CustomIcon' si elle existe, sinon le nom (la propriete
        # 'Icon' n'existe PAS dans les fichiers du jeu).
        icon = (node.get_property("CustomIcon") or "").strip().strip('"')
        by_key[f"{source}:{name}"] = CatalogEntry(
            name=name, source=source,
            category=category,
            market_price=_parse_market_price(node.get_property("MarketPrice")),
            icon_key=icon or name)
    return list(by_key.values())


def build_catalog(ecf_paths: List[Path]) -> List[CatalogEntry]:
    """Fusionne les fichiers donnes. ORDRE = PRIORITE : le premier fichier qui
    definit une entree (source, nom) gagne -- l'appelant passe la copie de
    travail D'ABORD, la vanille ensuite (jamais ecrasee par la vanille).
    Fichiers absents : ignores."""
    paths = [Path(p) for p in ecf_paths if Path(p).is_file()]
    key = str([str(p) for p in paths])
    sig = tuple(sorted((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in paths))
    cached = _cache.get(key)
    if cached is not None and cached[0] == sig:
        return cached[1]
    by_key: Dict[str, CatalogEntry] = {}
    for p in paths:
        source = SOURCE_ITEM if p.name == "ItemsConfig.ecf" else SOURCE_BLOCK
        for entry in _scan_file(p, source):
            by_key.setdefault(entry.key, entry)   # premier = prioritaire
    entries = list(by_key.values())
    _cache[key] = (sig, entries)
    return entries


def price_index(entries: List[CatalogEntry]) -> Dict[str, Optional[float]]:
    """nom -> MarketPrice (pour les fonctions existantes du module economie :
    bascule plage<->facteur, validation). Un meme nom item ET bloc : le PREMIER
    prix non nul gagne ; une entree sans prix n'ecrase jamais un prix connu."""
    out: Dict[str, Optional[float]] = {}
    for e in entries:
        if e.name not in out or out[e.name] is None:
            out[e.name] = e.market_price
    return out


# ------------------------------------------------------------ cache disque
# Parser ItemsConfig+BlocksConfig d'un gros scenario prend plusieurs secondes ;
# le resultat change quasi jamais une fois le scenario stable (retour
# utilisateur 09/09/2026) -> cache sur disque, invalide par signature
# (chemins + mtime + taille). Un bouton « Rafraichir » force la relecture.

from core.settings import CONFIG_DIR  # noqa: E402


def _disk_cache_path() -> Path:
    return Path(CONFIG_DIR) / "cache" / "item_catalog.json"


def _signature2(paths: List[Path]) -> list:
    sig = []
    for p in paths:
        try:
            st = p.stat()
            sig.append([str(p), st.st_mtime_ns, st.st_size])
        except OSError:
            sig.append([str(p), None, None])
    return sig


def load_catalog(ecf_paths: List[Path], refresh: bool = False) -> List[CatalogEntry]:
    """build_catalog + cache disque. refresh=True ignore le cache (bouton
    « Rafraichir », cas d'un item/bloc tout juste cree)."""
    paths = [Path(p) for p in ecf_paths if Path(p).is_file()]
    sig = _signature2(paths)
    cache_file = _disk_cache_path()
    if not refresh:
        try:
            if cache_file.is_file():
                import json
                payload = json.loads(cache_file.read_text(encoding="utf-8"))
                if payload.get("sig") == sig:
                    return [CatalogEntry(**d) for d in payload["entries"]]
        except Exception:
            pass
    if refresh:
        # refresh doit aussi contourner le cache EN MEMOIRE de build_catalog
        # (meme signature -> il repondrait avec les anciennes entrees)
        _cache.pop(str([str(p) for p in paths]), None)
    entries = build_catalog(paths)
    try:
        import json
        from dataclasses import asdict
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps({"sig": sig,
                                          "entries": [asdict(e) for e in entries]},
                                         ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return entries
