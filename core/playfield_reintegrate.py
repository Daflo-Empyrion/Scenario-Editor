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

"""Reintegration de playfields orphelins dans la galaxie.

Un dossier de `Playfields/<Type>` que le `Sectors.yaml` ne declare nulle part
n'est jamais charge (229 dossiers sur RE2-RPG). Ce module les repose dans des
SYSTEMES EXISTANTS — soleil deja present, `GalaxyConfig` inchange — en calquant
le corpus :

- planete / geante / station / asteroide / espace : NOUVEAU secteur, espace
  sur un anneau de 30 unite (jamais une file sur un axe) ;
- lune et orbite : LIGNE a offset dans le secteur d'une planete existante
  (`['4500, 5000, 8000', Lune, Type]`, orbite a `0,0,0`) — c'est ce que la
  carte systeme attend ; un secteur propre casse l'infobulle ;
- `SectorMapType` seulement quand le corpus en met un (`GasGiant`, `Station`,
  `AsteroidFieldFew`, `WarpTarget`) : une planete n'en a PAS, et
  `None` + 4 champs = la signature d'une ETOILE (vecu 22/10 : 199 playfields
  ajoutes ainsi apparaissaient alignes et faisaient lever
  `InvalidCastException` dans la carte systeme).

Ecriture via yamllite (commentaires et mise en forme preserves). L'appelant
gere backup central et undo. Le jeu charge la COPIE du Sectors.yaml faite dans
la sauvegarde : reintegration = NOUVELLE partie.
"""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from core.fsutil import atomic_write_text
from core.sectors_merge import (_all_playfields, _coords_key, _coords_text,
                                _ensure_blank_before, _find_child,
                                _find_solar_systems, _seq_items, _split_flow,
                                _strip_quotes, _systems)
from core.yamllite.model import YamlEntry, create_entry, remove_entry
from core.yamllite.parser import parse_yaml_file

SPACE_MARKER = "space_dynamic.yaml"
_STEP = 30                      # ecart entre secteurs d'un meme systeme
_DESC_RE = re.compile(r"^Description:[ \t]*(.*)$", re.M)

# type de secteur ecrit par le corpus, par categorie (absent = on n'ecrit pas
# de SectorMapType : cas d'une planete)
_MAP_TYPE = {"gasgiant": "GasGiant", "station": "Station",
             "asteroid": "AsteroidFieldFew", "space": "WarpTarget"}
_KIND_KEYS = {"planet": "reintegrate.kind_planet",
              "moon": "reintegrate.kind_moon",
              "gasgiant": "reintegrate.kind_gasgiant",
              "station": "reintegrate.kind_station",
              "asteroid": "reintegrate.kind_asteroid",
              "orbit": "reintegrate.kind_orbit",
              "space": "reintegrate.kind_space"}
_SURFACE = ("planet", "moon", "gasgiant")
# offsets de lunes observes dans le corpus (plusieurs milliers de metres)
_MOON_OFFSETS = [(4500, 5000, 8000), (-10695, 8475, -6228),
                 (5500, 10000, 12000), (-8000, 6000, 4000),
                 (9000, -7000, 5000), (-6000, -9000, 7000)]
# anneau : axes puis diagonales, rayon croissant (evite la file sur un axe)
_RING = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1),
         (1, 1, 0), (-1, 1, 0), (1, -1, 0), (-1, -1, 0),
         (1, 0, 1), (-1, 0, 1), (1, 0, -1), (-1, 0, -1),
         (0, 1, 1), (0, -1, 1), (0, 1, -1), (0, -1, -1),
         (1, 1, 1), (-1, 1, 1), (1, -1, 1), (1, 1, -1),
         (-1, -1, 1), (-1, 1, -1), (1, -1, -1), (-1, -1, -1)]


@dataclass(frozen=True)
class Orphan:
    type_name: str
    category: str          # planet|moon|gasgiant|station|asteroid|orbit|space
    description: str
    files: int
    size: int

    @property
    def family(self) -> str:
        return "surface" if self.category in _SURFACE else "space"

    @property
    def kind_key(self) -> str:
        return _KIND_KEYS.get(self.category, "reintegrate.kind_space")


@dataclass(frozen=True)
class Placement:
    type_name: str
    category: str
    system: str
    name: str
    mode: str                          # "sector" (nouveau) | "row" (offset)
    coords: Tuple[int, int, int]       # sector : coords ; row : offset
    sector: Tuple[int, int, int] = (0, 0, 0)   # row : secteur hote
    arrival: str = ""                  # planete : type d'ORBITE d'arrivee

    @property
    def family(self) -> str:
        return "surface" if self.category in _SURFACE else "space"

    @property
    def map_type(self) -> str:
        return _MAP_TYPE.get(self.category, "")

    @property
    def kind_key(self) -> str:
        return _KIND_KEYS.get(self.category, "reintegrate.kind_space")

    @property
    def arrival_name(self) -> str:
        return f"{self.name} Sector"

    def rows(self) -> List[str]:
        """Lignes du secteur. Une PLANETE recoit en plus son orbite
        d'arrivee (`['0,0,0', '<Nom> Sector', <Orbite>]`) : sans elle la
        carte n'a aucune cible de warp dans le secteur et « Selectionner »
        ne fait rien (vecu 22/10)."""
        lines = [self.row()]
        if self.arrival:
            lines.append(f"['0,0,0', {self.arrival_name}, {self.arrival}, '']")
        return lines

    def row(self) -> str:
        x, y, z = self.coords
        if self.category == "moon":
            return f"['{x}, {y}, {z}', {self.name}, {self.type_name}]"
        if self.family == "space":
            if self.category in ("station", "asteroid"):
                return (f"['0, 0, 0', {self.name}, {self.type_name}, "
                        f"'', '', '', '']")
            return f"['0,0,0', {self.name}, {self.type_name}, '']"
        if self.category == "gasgiant":
            texture, size = _gas_style(self.type_name)
            return (f"['0, 0, 0', {self.name}, {self.type_name}, '', '', "
                    f"'{texture}', '{size}']")
        return f"['0, 0, 0', {self.name}, {self.type_name}, '', '', '', '']"


def _gas_style(type_name: str) -> Tuple[str, str]:
    """Texture et classe de taille d'une geante (valeurs du corpus, choisies
    de facon deterministe pour que la carte ait un visuel coherent)."""
    name = type_name.casefold()
    if "ice" in name:
        return "SaturnBlue", "13"
    return ("SaturnBrown", "12") if "dwarf" in name else ("JupiterYellow", "12")


_TYPE_RE = re.compile(r"^PlayfieldType:[ 	]*(\w+)", re.M)


def _playfield_type(folder: Path) -> str:
    path = folder / "playfield.yaml"
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""
    match = _TYPE_RE.search(text)
    return match.group(1) if match else ""


def _is_space(folder: Path) -> bool:
    """Type « espace » : `space_dynamic.yaml`, sinon aucun marqueur de
    surface (terrain/static/sun), sinon le `PlayfieldType` declare.
    Indispensable : `SpaceEmpty` (utilise comme orbite d'arrivee dans le
    corpus) n'a qu'un `playfield.yaml` — le detecter par `space_dynamic.yaml`
    seul faisait croire a 12 routes manquantes (vecu 22/10)."""
    if (folder / SPACE_MARKER).is_file():
        return True
    if ((folder / "playfield_static.yaml").is_file()
            or (folder / "terrain.ecf").is_file()
            or (folder / "sun_static.yaml").is_file()):
        return False
    marker = _playfield_type(folder)
    return marker.casefold() == "space" if marker else True


def _category(folder: Path) -> str:
    space = _is_space(folder)
    name = folder.name.casefold()
    if space:
        if "orbit" in name:
            return "orbit"
        if "asteroid" in name:
            return "asteroid"
        if "station" in name:
            return "station"
        return "space"
    if "moon" in name:
        return "moon"
    if any(token in name for token in ("gasgiant", "gasdwarf", "icegiant")):
        return "gasgiant"
    return "planet"


def sectors_yaml(root) -> Optional[Path]:
    root = Path(root)
    for candidate in (root / "Sectors" / "Sectors.yaml",
                      root / "Sectors.yaml"):
        if candidate.is_file():
            return candidate
    return None


def _is_legacy_sector(sector: YamlEntry) -> bool:
    """Secteur ecrit par l'ancienne version : une seule ligne, `Name == Type`,
    4 champs, `SectorMapType` None/WarpTarget/absent — signature d'ETOILE."""
    playfields = _find_child(sector, "Playfields")
    rows = _seq_items(playfields) if playfields is not None else []
    if len(rows) != 1:
        return False
    fields = _split_flow(rows[0].value) if rows[0].value else []
    if len(fields) != 4:
        return False
    if _strip_quotes(fields[1]).casefold() !=             _strip_quotes(fields[2]).casefold():
        return False
    map_type = _find_child(sector, "SectorMapType")
    return map_type is None or map_type.value.strip() in ("None", "WarpTarget")


def _referenced_types(solar: YamlEntry) -> set:
    refs: set = set()
    for system in _systems(solar):
        sectors_entry = _find_child(system, "Sectors")
        if sectors_entry is None:
            continue
        for sector in _seq_items(sectors_entry):
            if _is_legacy_sector(sector):
                continue          # son type redevient orphelin (reparation)
            playfields = _find_child(sector, "Playfields")
            for row in (_seq_items(playfields) if playfields is not None
                        else [sector]):
                fields = _split_flow(row.value) if row.value else []
                if len(fields) >= 3 and fields[2]:
                    refs.add(_strip_quotes(fields[2]).casefold())
    return refs


def _description(folder: Path) -> str:
    for name in ("playfield_static.yaml", SPACE_MARKER, "playfield.yaml"):
        path = folder / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        match = _DESC_RE.search(text)
        if match is None:
            continue
        value = match.group(1).strip()
        if value and value not in ("|", ">", "|-", ">-", "|+", ">+"):
            return value.strip("'\"").replace("\\n", " ")[:120]
        for line in text[match.end():].splitlines()[:6]:
            if not line.strip():
                continue
            if line[:1] in (" ", "\t"):
                return line.strip()[:120]
            break
    return ""


def find_orphans(root) -> List[Orphan]:
    root = Path(root)
    path = sectors_yaml(root)
    if path is None:
        return []
    solar = _find_solar_systems(parse_yaml_file(path))
    if solar is None:
        return []
    refs = _referenced_types(solar)
    pf_root = root / "Playfields"
    orphans: List[Orphan] = []
    for folder in sorted(pf_root.iterdir() if pf_root.is_dir() else []):
        if not folder.is_dir() or folder.name.startswith("+"):
            continue
        if folder.name.casefold() in refs:
            continue
        files = [p for p in folder.rglob("*") if p.is_file()]
        orphans.append(Orphan(
            type_name=folder.name,
            category=_category(folder),
            description=_description(folder),
            files=len(files),
            size=sum(p.stat().st_size for p in files)))
    return orphans


def _playfield_names(solar: YamlEntry, skip_legacy: bool = True) -> set:
    """Noms d'instance pris dans toute la galaxie. Les secteurs de l'ancien
    format sont ignores : ils vont etre retires, leur nom doit redevenir
    disponible (sinon la reparation cree des `_2` — vecu 22/10)."""
    names: set = set()
    for system in _systems(solar):
        sectors_entry = _find_child(system, "Sectors")
        for sector in _seq_items(sectors_entry) if sectors_entry is not None else []:
            if skip_legacy and _is_legacy_sector(sector):
                continue
            playfields = _find_child(sector, "Playfields")
            for row in _seq_items(playfields) if playfields is not None else []:
                fields = _split_flow(row.value) if row.value else []
                if len(fields) >= 2 and fields[1]:
                    names.add(_strip_quotes(fields[1]).casefold())
    return names


def _orbit_types(root: Path) -> List[str]:
    """Types de playfield « orbite » disponibles (espace + nom contenant
    orbit) : ce sont les cibles d'arrivee de warp du corpus."""
    pf_root = root / "Playfields"
    found = [folder.name for folder in
             (pf_root.iterdir() if pf_root.is_dir() else [])
             if folder.is_dir() and not folder.name.startswith("+")
             and "orbit" in folder.name.casefold()
             and _is_space(folder)]
    return sorted(found)


def _system_orbit_type(system: YamlEntry, orbit_types: List[str]) -> str:
    """Orbite d'arrivee a utiliser : celle deja presente dans le systeme
    (le style du corpus y est conserve), sinon `Start_OrbitEasy`, sinon la
    premiere disponible."""
    known = {t.casefold() for t in orbit_types}
    sectors_entry = _find_child(system, "Sectors")
    for sector in _seq_items(sectors_entry) if sectors_entry is not None else []:
        playfields = _find_child(sector, "Playfields")
        for row in _seq_items(playfields) if playfields is not None else []:
            fields = _split_flow(row.value) if row.value else []
            if len(fields) >= 3:
                candidate = _strip_quotes(fields[2])
                if candidate.casefold() in known:
                    return candidate
    for name in orbit_types:
        if name.casefold() == "start_orbiteasy":
            return name
    return orbit_types[0] if orbit_types else ""


def _ring_coords(used: set):
    """Secteurs libres en anneau : rayon 30, 60, ... sur les 26 directions
    (jamais une file sur un axe, vecu 22/10)."""
    radius = 1
    while radius <= 20:
        for dx, dy, dz in _RING:
            coords = (dx * radius * _STEP, dy * radius * _STEP,
                      dz * radius * _STEP)
            if _coords_key(f"{coords[0]},{coords[1]},{coords[2]}") not in used:
                yield coords
        radius += 1


def _host_sectors(system: YamlEntry) -> List[Tuple[Tuple[int, int, int], set]]:
    """Secteurs de planete du systeme (accueillent lunes et orbites) avec les
    offsets deja pris. Un soleil n'est jamais un hote ; plusieurs hotes
    existent par systeme, on les fait tourner (une orbite par planete)."""
    sectors_entry = _find_child(system, "Sectors")
    out: List[Tuple[Tuple[int, int, int], set]] = []
    for sector in _seq_items(sectors_entry) if sectors_entry is not None else []:
        playfields = _find_child(sector, "Playfields")
        rows = _seq_items(playfields) if playfields is not None else []
        types = []
        for row in rows:
            fields = _split_flow(row.value) if row.value else []
            if len(fields) >= 3:
                types.append(_strip_quotes(fields[2]))
        if not types or all(t.casefold().startswith("sun") for t in types):
            continue
        # un secteur de l'ANCIEN format va etre retire : jamais un hote
        if _is_legacy_sector(sector):
            continue
        key = _coords_key(_coords_text(sector))
        if len(key) != 3:
            continue
        taken = set()
        for row in rows:
            fields = _split_flow(row.value) if row.value else []
            if fields:
                taken.add(tuple(_coords_key(fields[0])))
        out.append(((int(key[0]), int(key[1]), int(key[2])), taken))
    return out


def plan_placements(root, picks: Iterable[str],
                    per_system: int = 2) -> List[Placement]:
    """Placement propose, AUCUNE ecriture : les playfields sont repartis par
    lots de `per_system` sur tous les systemes (rotation), chaque nouveau
    secteur sur un anneau de 30 ; lunes et orbites vont en offset dans le
    secteur d'une planete du meme systeme."""
    root = Path(root)
    path = sectors_yaml(root)
    if path is None:
        return []
    solar = _find_solar_systems(parse_yaml_file(path))
    if solar is None:
        return []
    systems = _systems(solar)
    if not systems:
        return []
    per_system = max(1, int(per_system))
    used_coords = {}                 # systeme -> coordonnees prises
    hosts = {}                       # systeme -> liste des hotes
    host_index: dict = {}            # rotation des hotes par systeme
    for system in systems:
        name = _strip_quotes(system.value)
        sectors_entry = _find_child(system, "Sectors")
        used_coords[name] = {_coords_key(_coords_text(s))
                             for s in _seq_items(sectors_entry)} \
            if sectors_entry is not None else set()
        hosts[name] = _host_sectors(system)
    used_names = _playfield_names(solar)
    orphans = {o.type_name: o for o in find_orphans(root)}
    orbit_types = _orbit_types(root)
    orbits = {_strip_quotes(s.value): _system_orbit_type(s, orbit_types)
              for s in systems}
    placements: List[Placement] = []
    index = 0
    for pick in picks:
        orphan = orphans.get(pick)
        if orphan is None:
            continue
        system = _strip_quotes(systems[
            (index // per_system) % len(systems)].value)
        index += 1
        name = orphan.type_name
        suffix = 2
        while name.casefold() in used_names:
            name = f"{orphan.type_name}_{suffix}"
            suffix += 1
        if orphan.category in ("moon", "orbit"):
            available = hosts.get(system) or []
            if not available:
                continue           # systeme sans planete : rien a orbiter
            index_host = host_index.get(system, 0) % len(available)
            host_index[system] = index_host + 1
            host_coords, taken = available[index_host]
            offset = _pick_offset(orphan.category, taken)
            taken.add(tuple(_coords_key(f"{offset[0]},{offset[1]},{offset[2]}")))
            used_names.add(name.casefold())
            placements.append(Placement(orphan.type_name, orphan.category,
                                        system, name, "row", offset,
                                        host_coords))
            continue
        used = used_coords.setdefault(system, set())
        coords = next((c for c in _ring_coords(used)), None)
        if coords is None:
            continue
        used.add(_coords_key(f"{coords[0]},{coords[1]},{coords[2]}"))
        used_names.add(name.casefold())
        arrival = ""
        if orphan.category == "planet" and orbits.get(system):
            arrival = orbits[system]
            used_names.add(f"{name} Sector".casefold())
        placements.append(Placement(orphan.type_name, orphan.category,
                                    system, name, "sector", coords,
                                    arrival=arrival))
    return placements


def _pick_offset(kind: str, taken: set) -> Tuple[int, int, int]:
    if kind == "orbit":
        return (0, 0, 0)             # le corpus pose l'orbite a 0,0,0
    for offset in _MOON_OFFSETS:
        if tuple(_coords_key(f"{offset[0]},{offset[1]},{offset[2]}")) not in taken:
            return offset
    step = 1000
    while True:
        candidate = (4000 + step, 3000, 5000)
        if tuple(_coords_key(f"{candidate[0]},3000,5000")) not in taken:
            return candidate
        step += 1000


def _sector_entry(placement: Placement, indent: str, eol: str) -> YamlEntry:
    x, y, z = placement.coords
    sector = create_entry("Coordinates", f"[{x}, {y}, {z}]", indent=indent,
                          is_sequence_item=True, eol=eol)
    if placement.map_type:
        sector.children.append(create_entry("SectorMapType",
                                            placement.map_type,
                                            indent=indent + "  ", eol=eol))
    playfields = create_entry("Playfields", "", indent=indent + "  ", eol=eol)
    for line in placement.rows():
        playfields.children.append(create_entry(
            None, line, indent=indent + "    ",
            is_sequence_item=True, eol=eol))
    sector.children.append(playfields)
    return sector


def apply_placements(root, placements) -> Tuple[int, List[str]]:
    """Ecrit les placements (atomique) ; retourne (operations, details).
    Nom deja pris ou secteur deja occupe : REFUSE, jamais ecrit en double."""
    placements = list(placements)
    if not placements:
        return 0, []
    root = Path(root)
    path = sectors_yaml(root)
    if path is None:
        return 0, ["Sectors.yaml introuvable"]
    doc = parse_yaml_file(path)
    solar = _find_solar_systems(doc)
    if solar is None:
        return 0, ["SolarSystems introuvable"]
    eol = "\r\n" if solar.raw.endswith("\r\n") else "\n"
    systems = {_strip_quotes(s.value): s for s in _systems(solar)}
    used = {name.casefold() for name in _all_playfields(solar)}
    applied = 0
    details: List[str] = []
    for placement in placements:
        system = systems.get(placement.system)
        if system is None:
            details.append(f"systeme {placement.system} introuvable")
            continue
        sectors_entry = _find_child(system, "Sectors")
        if sectors_entry is None:
            details.append(f"systeme {placement.system} sans liste Sectors")
            continue
        if placement.name.casefold() in used:
            details.append(f"nom {placement.name} deja pris — ignore")
            continue
        siblings = _seq_items(sectors_entry)
        indent = siblings[0].indent if siblings else system.indent + "  "
        if placement.mode == "row":
            key = _coords_key(f"{placement.sector[0]},{placement.sector[1]},"
                              f"{placement.sector[2]}")
            host = next((s for s in siblings
                         if _coords_key(_coords_text(s)) == key), None)
            playfields = _find_child(host, "Playfields") if host else None
            if playfields is None:
                details.append(f"lune/orbite {placement.name} : secteur hote "
                               f"{placement.sector} introuvable")
                continue
            _ensure_blank_before(playfields.children, eol)
            playfields.children.append(create_entry(
                None, placement.row(),
                indent=(_seq_items(playfields)[0].indent
                        if _seq_items(playfields) else indent + "    "),
                is_sequence_item=True, eol=eol))
        else:
            key = _coords_key(f"{placement.coords[0]},{placement.coords[1]},"
                              f"{placement.coords[2]}")
            if any(_coords_key(_coords_text(s)) == key for s in siblings):
                details.append(f"secteur {placement.coords} deja occupe — "
                               f"ignore")
                continue
            _ensure_blank_before(sectors_entry.children, eol)
            sectors_entry.children.append(
                _sector_entry(placement, indent, eol))
        used.add(placement.name.casefold())
        applied += 1
    if applied:
        atomic_write_text(path, doc.render())
    return applied, details


@dataclass(frozen=True)
class LegacySector:
    """Secteur ecrit par l'ancienne version de l'outil : une seule ligne,
    `Name == Type`, 4 champs, `SectorMapType: None`/`WarpTarget` — signature
    d'ETOILE ; la carte systeme y leve InvalidCastException (vecu 22/10)."""
    system: str
    coords: Tuple[int, int, int]

    @property
    def key(self) -> str:
        return f"{self.system} [{self.coords[0]}, {self.coords[1]}, " \
               f"{self.coords[2]}]"


def find_legacy(root) -> List[LegacySector]:
    root = Path(root)
    path = sectors_yaml(root)
    if path is None:
        return []
    solar = _find_solar_systems(parse_yaml_file(path))
    if solar is None:
        return []
    out: List[LegacySector] = []
    for system in _systems(solar):
        name = _strip_quotes(system.value)
        sectors_entry = _find_child(system, "Sectors")
        for sector in _seq_items(sectors_entry) if sectors_entry else []:
            if not _is_legacy_sector(sector):
                continue
            key = _coords_key(_coords_text(sector))
            if len(key) != 3:
                continue
            out.append(LegacySector(name, (int(key[0]), int(key[1]),
                                           int(key[2]))))
    return out


def remove_legacy(root, items) -> int:
    """Retire les secteurs de l'ancien format (backup et undo cote appelant).
    Ne touche QUE la signature ci-dessus : un secteur du corpus est ignore."""
    items = list(items)
    if not items:
        return 0
    root = Path(root)
    path = sectors_yaml(root)
    if path is None:
        return 0
    doc = parse_yaml_file(path)
    solar = _find_solar_systems(doc)
    if solar is None:
        return 0
    targets = {(item.system, item.coords) for item in items}
    systems = {_strip_quotes(s.value): s for s in _systems(solar)}
    removed = 0
    for system_name, coords in targets:
        system = systems.get(system_name)
        sectors_entry = _find_child(system, "Sectors") if system else None
        for sector in list(_seq_items(sectors_entry) if sectors_entry else []):
            key = _coords_key(_coords_text(sector))
            if len(key) != 3 or (int(key[0]), int(key[1]), int(key[2])) != coords:
                continue
            if not _is_legacy_sector(sector):
                continue
            if remove_entry(sectors_entry.children, sector):
                removed += 1
    if removed:
        atomic_write_text(path, doc.render())
    return removed


def render_preview(placements, legacy=()) -> str:
    """Bloc YAML tel qu'il sera insere (apercu du dialogue)."""
    lines: List[str] = []
    for item in legacy:
        lines.append(f"# retirer : secteur {item.key} (ancien format)")
    current = None
    for placement in placements:
        header = (f"{placement.system} > secteur "
                  f"[{placement.sector[0]}, {placement.sector[1]}, "
                  f"{placement.sector[2]}]" if placement.mode == "row"
                  else f"{placement.system} > nouveau secteur")
        if header != current:
            current = header
            lines.append(f"# {header}")
        if placement.mode == "row":
            lines.append(f"          - {placement.row()}")
            continue
        x, y, z = placement.coords
        lines.append(f"      - Coordinates: [{x}, {y}, {z}]")
        if placement.map_type:
            lines.append(f"        SectorMapType: {placement.map_type}")
        lines.append("        Playfields:")
        for line in placement.rows():
            lines.append(f"          - {line}")
    return "\n".join(lines)


def find_missing_arrivals(root) -> List[Placement]:
    """Secteurs d'une planete SANS aucun playfield espace : la carte n'a
    alors aucune cible de warp et « Selectionner » ne fait rien (vecu 22/10).
    Retourne une ligne d'arrivee `['0,0,0', '<Planete> Sector', <Orbite>]`
    par secteur concerne ; un secteur avec SectorMapType (GasGiant, Station,
    WarpTarget, Sun...) est deja un corps spatial et n'est pas touche."""
    root = Path(root)
    path = sectors_yaml(root)
    if path is None:
        return []
    solar = _find_solar_systems(parse_yaml_file(path))
    if solar is None:
        return []
    orbit_types = _orbit_types(root)
    if not orbit_types:
        return []
    space = {folder.name.casefold() for folder in
             (root / "Playfields").iterdir()
             if folder.is_dir() and _is_space(folder)}
    used = _playfield_names(solar)
    out: List[Placement] = []
    for system in _systems(solar):
        name = _strip_quotes(system.value)
        orbit = _system_orbit_type(system, orbit_types)
        sectors_entry = _find_child(system, "Sectors")
        for sector in _seq_items(sectors_entry) if sectors_entry is not None else []:
            if _is_legacy_sector(sector):
                continue
            if _find_child(sector, "SectorMapType") is not None:
                continue
            playfields = _find_child(sector, "Playfields")
            rows = [(_split_flow(r.value) if r.value else []) for r in
                    (_seq_items(playfields) if playfields is not None else [])]
            rows = [f for f in rows if len(f) >= 3]
            if not rows or any(_strip_quotes(f[2]).casefold() in space
                               for f in rows):
                continue
            planet = next((f for f in rows if len(f) >= 7), None)
            if planet is None:
                continue
            arrival_name = f"{_strip_quotes(planet[1])} Sector"
            if arrival_name.casefold() in used:
                continue
            key = _coords_key(_coords_text(sector))
            if len(key) != 3:
                continue
            used.add(arrival_name.casefold())
            out.append(Placement(orbit, "orbit", name, arrival_name,
                                 "row", (0, 0, 0),
                                 (int(key[0]), int(key[1]), int(key[2]))))
    return out
