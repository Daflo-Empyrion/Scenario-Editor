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

"""Lieux des marchands : ou trouver tel marchand dans le scenario ?

Aucun fichier du scenario ne donne ce lien (verifie sur RE2-FR : 0 TraderZone
dans les 343 playfields, aucun nom de marchand dans les YAML). Il se
reconstruit en trois sauts, mesure le 06/11/2026 sur 13 112 .epb :

  marchand -> prefab : le binaire d'un prefab porte `Traders <cle>` dans son
    EN-TETE NON COMPRESSE (toujours avant la signature zip `PK\\x03\\x04`,
    aucun besoin de decompresser). 43 prefabs seulement, mais zero faux
    positif. Chercher le nom SEUL est un piege : 1 079 prefabs matchent pour
    4 % de precision (`food`, `factory`, `medic`, `talion` sont aussi des noms
    de blocs/factions).
  prefab -> groupe : propriete 7 de l'en-tete (`read_header`), plus les Tags.
  groupe -> POI : `- GroupName: X` des POI Random et `Prefab:` des POI Fixed,
    dans les playfield*.yaml / space*.yaml du scenario.
  POI -> systeme/secteur : Sectors.yaml.

Les cles ne sont pas toujours le nom exact : alias `commdefault*` pour
`CommoditiesDefault*`, suffixes `(hidden)`/`grey`/`white`, et fautes de frappe
(`paxpuragtory`). D'ou trois niveaux de confiance : exact, prefixe, proche.
Tout ce qui n'est pas trouve reste « inconnu » — jamais devine."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from core.codex import load_store, save_store
from core.epb_blueprint import read_header
from core.sectors_merge import (_coords_key, _coords_text, _find_child,
                                _find_solar_systems, _seq_items, _split_flow,
                                _strip_quotes, _systems)
from core.yamllite.model import YamlEntry
from core.yamllite.parser import parse_yaml_file

HEADER_BYTES = 48_000                 # les cles observees sont avant 13 Ko
CONFIDENCE_RANK = {"exact": 0, "prefixe": 1, "proche": 2}

_TRADER_TOKEN = re.compile(rb"Traders?\s+([A-Za-z0-9 _'\-().]{2,40})")
_SHOP_POI = re.compile(r"trade|market|shop", re.I)
_ALIASES = (("commdefault", "commoditiesdefault"),)
_PLACES_CACHE = "places"


# ------------------------------------------------------------------ cles

def _norm(text: str) -> str:
    """Forme compacte de comparaison : minuscules, sans ponctuation."""
    return re.sub(r"[^a-z0-9]", "", (text or "").casefold())


def trader_keys(raw: str) -> Set[str]:
    """Formes comparables d'une cle de prefab : `interweap(hidden)` et
    `interweap`, `commdefaultgrey` et son alias `commoditiesdefaultgrey`."""
    text = (raw or "").strip().strip('"')
    bare = re.sub(r"\((?:hidden|grey|white)\)$", "", text, flags=re.I).strip()
    keys = {_norm(text), _norm(bare)}
    out = set()
    for key in keys:
        if not key:
            continue
        for old, new in _ALIASES:
            if key.startswith(old):
                key = new + key[len(old):]
        out.add(key)
    return out


def distance(a: str, b: str) -> int:
    """Distance de Levenshtein (2 mots courts : pas de dependance externe)."""
    if a == b:
        return 0
    if not a or not b:
        return max(len(a), len(b))
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1,
                               previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def match_trader(key: str, known: Dict[str, str]) -> Optional[Tuple[str, str]]:
    """(nom du marchand, confiance) pour une cle de prefab normalisee.
    `known` = {forme normalisee: nom}. Exact, puis prefixe (>= 8 car. : les
    variantes `...greygoods` allongent le nom), puis faute de frappe (<= 2)."""
    if key in known:
        return known[key], "exact"
    for candidate, name in known.items():
        if len(key) >= 8 and (candidate.startswith(key) or key.startswith(candidate)):
            return name, "prefixe"
    best: Optional[Tuple[int, str]] = None
    for candidate, name in known.items():
        # Une faute de frappe ne se juge que sur un nom assez long : sur 4-5
        # caracteres « goods » et « food » sont a distance 2 (faux positif
        # constate sur RE2-FR, marchands « Food »).
        if len(key) < 6 or len(candidate) < 6:
            continue
        if abs(len(candidate) - len(key)) > 2:
            continue
        dist = distance(key, candidate)
        if dist <= 2 and (best is None or dist < best[0]):
            best = (dist, name)
    return (best[1], "proche") if best else None


def known_traders(names: Iterable[str]) -> Dict[str, str]:
    """Index de rapprochement : plusieurs formes par marchand, la premiere
    gagne (l'exact passe avant les alias par construction)."""
    out: Dict[str, str] = {}
    for name in names:
        for form in trader_keys(name):
            out.setdefault(form, name)
    return out


# ------------------------------------------------------------------ modeles

@dataclass(frozen=True)
class PlayfieldInstance:
    """Une ligne de playfield de Sectors.yaml (instance, pas type)."""
    system: str
    sector: Tuple[int, int, int]
    instance: str
    type_name: str


@dataclass
class TraderPlace:
    trader: str
    playfield: str                    # dossier Playfields/<type>
    poi: str = ""
    source: str = "prefab"            # prefab | zone
    key: str = ""                     # cle brute lue dans le prefab
    confidence: str = "exact"
    instances: Tuple[Tuple[str, Tuple[int, int, int], str], ...] = ()

    @property
    def label(self) -> str:
        return f"{self.playfield}/{self.poi}" if self.poi else self.playfield


@dataclass
class PlacesIndex:
    by_trader: Dict[str, List[TraderPlace]] = field(default_factory=dict)
    candidates: Tuple[Tuple[str, str], ...] = ()
    by_type: Dict[str, List[PlayfieldInstance]] = field(default_factory=dict)
    stamp: str = ""

    def places_for(self, trader: str) -> List[TraderPlace]:
        return self.by_trader.get(trader, [])

    def instances_for(self, type_name: str) -> List[PlayfieldInstance]:
        return self.by_type.get(type_name, [])


# ------------------------------------------------------------------ chemins

def playfield_root(root) -> Optional[Path]:
    for candidate in (Path(root) / "Playfields", Path(root) / "Content" / "Playfields"):
        if candidate.is_dir():
            return candidate
    return None


def prefab_root(root) -> Optional[Path]:
    for candidate in (Path(root) / "Prefabs", Path(root) / "Content" / "Prefabs"):
        if candidate.is_dir():
            return candidate
    return None


def sectors_path(root) -> Optional[Path]:
    for candidate in (Path(root) / "Sectors" / "Sectors.yaml", Path(root) / "Sectors.yaml"):
        if candidate.is_file():
            return candidate
    return None


# -------------------------------------------------- systeme / secteur / instance

def list_playfield_instances(root) -> List[PlayfieldInstance]:
    """Toutes les lignes de playfield de Sectors.yaml, sans restriction de
    type (contrairement a `core.starters.find_planets`, qui ne garde que les
    planetes) : stations, orbites et soleils en font partie."""
    path = sectors_path(root)
    if path is None:
        return []
    try:
        solar = _find_solar_systems(parse_yaml_file(path))
    except (OSError, ValueError):
        return []
    if solar is None:
        return []
    out: List[PlayfieldInstance] = []
    for system in _systems(solar):
        system_name = _strip_quotes(system.value)
        sectors = _find_child(system, "Sectors")
        for sector in (_seq_items(sectors) if sectors is not None else []):
            coords = _sector_coords(sector)
            playfields = _find_child(sector, "Playfields")
            for row in (_seq_items(playfields) if playfields is not None else []):
                fields = _split_flow(row.value) if row.value else []
                if len(fields) < 3:
                    continue
                out.append(PlayfieldInstance(system_name, coords,
                                             fields[1], fields[2]))
    return out


def _sector_coords(sector: YamlEntry) -> Tuple[int, int, int]:
    key = _coords_key(_coords_text(sector))
    try:
        return (int(key[0]), int(key[1]), int(key[2]))
    except (IndexError, ValueError):
        return (0, 0, 0)


def _instances_by_type(instances: Sequence[PlayfieldInstance]
                       ) -> Dict[str, List[PlayfieldInstance]]:
    out: Dict[str, List[PlayfieldInstance]] = {}
    for instance in instances:
        out.setdefault(instance.type_name, []).append(instance)
    return out


# ------------------------------------------------------------ scan prefabs

def prefab_trader_keys(path) -> List[str]:
    """Tokens `Traders <cle>` de l'en-tete non compresse d'un .epb."""
    try:
        with open(path, "rb") as handle:
            data = handle.read(HEADER_BYTES)
    except OSError:
        return []
    start = data.find(b"PK\x03\x04")
    head = data[:start] if start > 0 else data
    out: List[str] = []
    for raw in _TRADER_TOKEN.findall(head):
        text = raw.decode("ascii", "ignore").strip().rstrip(".\"' ")
        if text:
            out.append(text)
    return out


def scan_prefab_traders(prefabs: Optional[Path], known: Dict[str, str],
                        progress: Optional[Callable[[int, int], None]] = None
                        ) -> Dict[str, List[Tuple[str, str, str]]]:
    """{ref de prefab normalisee: [(marchand, cle brute, confiance)]}.

    On ne fait `read_header` (GroupName + Tags) que pour les prefabs qui
    nomment un marchand : quelques dizaines sur 13 000."""
    if prefabs is None or not prefabs.is_dir():
        return {}
    files = sorted(prefabs.rglob("*.epb"))
    total = len(files)
    out: Dict[str, List[Tuple[str, str, str]]] = {}
    for index, path in enumerate(files):
        if progress is not None and index % 500 == 0:
            progress(index, total)
        keys = prefab_trader_keys(path)
        if not keys:
            continue
        hits: List[Tuple[str, str, str]] = []
        for raw in keys:
            for key in trader_keys(raw):
                match = match_trader(key, known)
                if match:
                    hits.append((match[0], raw, match[1]))
                    break
        if not hits:
            continue
        refs = {_norm(path.stem)}
        header = read_header(path)
        if header:
            refs.add(_norm(header[0]))
            for tag in (header[1] or "").split(","):
                if tag.strip():
                    refs.add(_norm(tag))
        refs.discard("")
        for ref in refs:
            out.setdefault(ref, []).extend(hits)
    # dedoublonnage (un meme prefab peut citer deux fois la meme cle)
    return {ref: sorted(set(hits)) for ref, hits in out.items()}


# ---------------------------------------------------------- scan playfields

def _poi_items(node: YamlEntry, depth: int = 0) -> Iterable[YamlEntry]:
    """Items de POI quelle que soit leur forme : `- GroupName:` des Random,
    `- Type:` + `Prefab:` des Fixed, `- Type:` + `GroupName:` enfant en
    espace. Les sous-sections (`Random:`, `Fixed:`...) sont traversees."""
    if depth > 3:
        return
    for child in node.children:
        if not isinstance(child, YamlEntry):
            continue
        if child.is_sequence_item:
            yield child
        else:
            yield from _poi_items(child, depth + 1)


def _poi_record(item: YamlEntry) -> Optional[Tuple[str, Set[str]]]:
    """(nom affiche, references normalisees) d'un item de POI."""
    group = (item.get("GroupName") or "").strip().strip('"')
    if item.key == "GroupName":
        group = (item.value or "").strip().strip('"')
    name = group or (item.get("Name") or "").strip().strip('"')
    refs = {group, (item.get("Name") or ""), (item.get("Prefab") or ""),
            (item.get("PrefabName") or "")}
    refs = {_norm(ref) for ref in refs if ref and ref.strip()}
    if not name or not refs:
        return None
    return name, refs


def _playfield_yamls(root: Optional[Path]) -> List[Tuple[str, Path]]:
    """(nom du type de playfield, chemin yaml) pour tous les fichiers de POI."""
    if root is None:
        return []
    out: List[Tuple[str, Path]] = []
    for folder in sorted(root.iterdir()):
        if not folder.is_dir():
            continue
        for yaml_path in sorted(folder.glob("*.yaml")):
            if yaml_path.name.startswith(("playfield", "space")):
                out.append((folder.name, yaml_path))
    return out


def pois_of_playfield(root, type_name: str) -> List[str]:
    """Noms de POI d'UN playfield (aide a la saisie) : on ne parse que le
    dossier demande, jamais les 343."""
    folder = playfield_root(root)
    if folder is None:
        return []
    names: List[str] = []
    for path in sorted((folder / type_name).glob("*.yaml")):
        if not path.name.startswith(("playfield", "space")):
            continue
        try:
            doc = parse_yaml_file(path)
        except (OSError, ValueError):
            continue
        for node in doc.nodes:
            if isinstance(node, YamlEntry) and node.key == "POIs":
                for item in _poi_items(node):
                    record = _poi_record(item)
                    if record is not None and record[0] not in names:
                        names.append(record[0])
    return sorted(names)


def scan_playfield_pois(root) -> Tuple[List[Tuple[str, str, Set[str]]],
                                       List[Tuple[str, str]],
                                       List[Tuple[str, str, str]]]:
    """(points d'interet, candidats « commerce », zones de marchands).

    points = (playfield, nom du POI, references normalisees) ; candidats =
    (playfield, POI) dont le nom evoque un commerce ; zones = (zone, POI,
    playfield) des cles `TraderZone` (top-level ou Properties)."""
    points: List[Tuple[str, str, Set[str]]] = []
    candidates: List[Tuple[str, str]] = []
    zones: List[Tuple[str, str, str]] = []
    from core.playfield_editor import get_properties_value

    for type_name, path in _playfield_yamls(playfield_root(root)):
        try:
            doc = parse_yaml_file(path)
        except (OSError, ValueError):
            continue
        for node in doc.nodes:
            if not isinstance(node, YamlEntry):
                continue
            if node.key == "TraderZone" and (node.value or "").strip():
                zones.append((node.value.strip().strip('"'), "", type_name))
            if node.key != "POIs":
                continue
            for item in _poi_items(node):
                record = _poi_record(item)
                zone = (get_properties_value(item, "TraderZone") or "").strip().strip('"')
                if record is None:
                    if zone:
                        zones.append((zone, (item.get("Name") or "").strip(), type_name))
                    continue
                name, refs = record
                points.append((type_name, name, refs))
                if _SHOP_POI.search(name):
                    candidates.append((type_name, name))
                if zone:
                    zones.append((zone, name, type_name))
    return points, sorted(set(candidates)), zones


# --------------------------------------------------------------- assemblage

def _link(points: Sequence[Tuple[str, str, Set[str]]],
          by_ref: Dict[str, List[Tuple[str, str, str]]],
          zones: Sequence[Tuple[str, str, str]],
          by_type: Dict[str, List[PlayfieldInstance]],
          known: Dict[str, str]) -> Dict[str, List[TraderPlace]]:
    places: Dict[str, List[TraderPlace]] = {}
    seen: Set[Tuple[str, str, str, str]] = set()

    def add(place: TraderPlace) -> None:
        marker = (place.trader, place.playfield, place.poi, place.source)
        if marker in seen:
            return
        seen.add(marker)
        instances = by_type.get(place.playfield, [])
        place.instances = tuple((i.system, i.sector, i.instance) for i in instances)
        places.setdefault(place.trader, []).append(place)

    for playfield, poi, refs in points:
        for ref in refs:
            for trader, key, confidence in by_ref.get(ref, ()):
                add(TraderPlace(trader=trader, playfield=playfield, poi=poi,
                                source="prefab", key=key, confidence=confidence))
    for zone, poi, playfield in zones:
        match = match_trader(_norm(zone), known)
        if match is None:
            continue                 # zone qui ne designe aucun marchand connu
        add(TraderPlace(trader=match[0], playfield=playfield, poi=poi,
                        source="zone", key=zone, confidence=match[1]))
    for items in places.values():
        items.sort(key=lambda place: (place.playfield, place.poi))
    return places


def stamp_of(root, prefabs: Optional[Path], playfields: Optional[Path]) -> str:
    """Empreinte du cache. `shortcut:` mtime de DOSSIER (pas de chaque
    fichier : 13 000 stat a chaque ouverture) — un prefab modifie sans que le
    dossier change n'invalide pas ; relancer la recherche a la main dans ce
    cas."""
    parts = [str(Path(root).resolve())]
    for folder in (prefabs, playfields):
        if folder is not None and folder.is_dir():
            parts.append(f"{folder.stat().st_mtime_ns}:{len(list(folder.iterdir()))}")
    sectors = sectors_path(root)
    parts.append(str(sectors.stat().st_mtime_ns) if sectors is not None else "")
    return "|".join(parts)


def build_places_index(root, traders: Iterable[str],
                       progress: Optional[Callable[[int, int], None]] = None
                       ) -> PlacesIndex:
    """Construit l'index complet et le met en cache (thread : aucun QWidget)."""
    known = known_traders(traders)
    prefabs = prefab_root(root)
    playfields = playfield_root(root)
    by_ref = scan_prefab_traders(prefabs, known, progress)
    points, candidates, zones = scan_playfield_pois(root)
    by_type = _instances_by_type(list_playfield_instances(root))
    index = PlacesIndex(
        by_trader=_link(points, by_ref, zones, by_type, known),
        candidates=tuple(candidates),
        by_type=by_type,
        stamp=stamp_of(root, prefabs, playfields))
    save_store(root, _PLACES_CACHE, index_to_dict(index))
    return index


def index_to_dict(index: PlacesIndex) -> dict:
    return {
        "stamp": index.stamp,
        "candidates": [list(pair) for pair in index.candidates],
        "by_trader": {
            trader: [{"playfield": p.playfield, "poi": p.poi, "source": p.source,
                      "key": p.key, "confidence": p.confidence,
                      "instances": [[i[0], list(i[1]), i[2]] for i in p.instances]}
                     for p in places]
            for trader, places in index.by_trader.items()},
        "by_type": {name: [[i.system, list(i.sector), i.instance]
                           for i in instances]
                    for name, instances in index.by_type.items()},
    }


def index_from_dict(payload: dict) -> PlacesIndex:
    index = PlacesIndex(stamp=str(payload.get("stamp") or ""),
                        candidates=tuple(tuple(pair) for pair in payload.get("candidates") or ()))
    for trader, places in (payload.get("by_trader") or {}).items():
        index.by_trader[trader] = [
            TraderPlace(
                trader=trader,
                playfield=str(place.get("playfield") or ""),
                poi=str(place.get("poi") or ""),
                source=str(place.get("source") or "prefab"),
                key=str(place.get("key") or ""),
                confidence=str(place.get("confidence") or "exact"),
                instances=tuple((str(i[0]), (int(i[1][0]), int(i[1][1]), int(i[1][2])),
                                 str(i[2])) for i in place.get("instances") or ()),
            )
            for place in places]
    for name, instances in (payload.get("by_type") or {}).items():
        index.by_type[name] = [
            PlayfieldInstance(str(i[0]), (int(i[1][0]), int(i[1][1]), int(i[1][2])),
                              str(i[2]), name)
            for i in instances]
    return index


def cached_places(root, traders: Iterable[str]) -> Optional[PlacesIndex]:
    """Index deja calcule et toujours valide, sinon None (jamais de scan)."""
    payload = load_store(root, _PLACES_CACHE)
    if not payload:
        return None
    prefabs, playfields = prefab_root(root), playfield_root(root)
    if str(payload.get("stamp") or "") != stamp_of(root, prefabs, playfields):
        return None
    index = index_from_dict(payload)
    if not index.by_type:                    # vieux cache sans instances
        index.by_type = _instances_by_type(list_playfield_instances(root))
    return index
