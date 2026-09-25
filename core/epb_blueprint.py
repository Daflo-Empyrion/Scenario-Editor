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

"""Lecture, verification et edition des blueprints .epb d'Empyrion.

Format reconstruit depuis le code du jeu (v1.19.2, decompilation de
Blueprint.cs / BlueprintHeader.cs / ImageProvider.cs / SimpleBitStream.cs) :

  .epb = [header binaire][i32 taille][byte][bool][entree zip locale]
         [repertoire central zip]
  entree zip '0' (decompressee) :
      i32 n             taille du bitmask d'occupation (n = ceil(volume/8))
      n octets          1 bit par cellule (LSB d'abord) : cellule occupee ?
      uint32 par bit=1  bloc compresse (struct ImageProvider) :
          bits 0-10     id bloc (11 bits bas)
          bit 23        id bit 11 (id >= 2048)
          bit 24        id bit 12 (id >= 4096)   [version >= 28]
          bits 11-15    rotation
          bits 16-22    champ hp (7 bits)
          bits 25+      autres champs/flags
  Ce qui suit (densite, couleurs, textures, overlays, tile entities...) est
  indexe independamment du bitmask d'occupation : supprimer un bloc = effacer
  son bit et son uint32, tout le reste du flux reste octet-pour-octet
  identique. La lecture s'arrete donc apres les uint32 de blocs.
"""
from __future__ import annotations

import csv
import io
import os
import struct
import zipfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from core.ecf.model import EcfBlock
from core.ecf.parser import parse_ecf_file

EPB_MAGIC = 2022986309


class EpbError(RuntimeError):
    """Fichier .epb illisible ou non supporte."""


@dataclass
class EpbBlock:
    x: int
    y: int
    z: int
    block_id: int
    rotation: int
    hp_field: int


class _BinReader:
    """Lecteur minimal reproduisant System.IO.BinaryReader."""

    def __init__(self, data: bytes):
        self.d = data
        self.p = 0

    def u8(self) -> int:
        v = self.d[self.p]
        self.p += 1
        return v

    def boolean(self) -> bool:
        return self.u8() != 0

    def u16(self) -> int:
        v = struct.unpack_from("<H", self.d, self.p)[0]
        self.p += 2
        return v

    def i32(self) -> int:
        v = struct.unpack_from("<i", self.d, self.p)[0]
        self.p += 4
        return v

    def i64(self) -> int:
        v = struct.unpack_from("<q", self.d, self.p)[0]
        self.p += 8
        return v

    def u32(self) -> int:
        v = struct.unpack_from("<I", self.d, self.p)[0]
        self.p += 4
        return v

    def f32(self) -> float:
        v = struct.unpack_from("<f", self.d, self.p)[0]
        self.p += 4
        return v

    def string(self) -> str:
        length, shift = 0, 0
        while True:
            b = self.u8()
            length |= (b & 0x7F) << shift
            if not (b & 0x80):
                break
            shift += 7
        s = self.d[self.p:self.p + length].decode("utf-8", errors="replace")
        self.p += length
        return s

    def skip(self, n: int) -> None:
        self.p += n


def _read_string_skip(r: "_BinReader") -> None:
    length, shift = 0, 0
    while True:
        b = r.u8()
        length |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
    r.skip(length)


def _skip_properties(r: "_BinReader") -> None:
    r.u16()
    count = r.u16()
    for _ in range(count):
        r.i32()                 # EnumProperties key
        r.boolean()
        r.boolean()
        r.boolean()
        ptype = r.u8()
        if ptype == 0:          # String
            _read_string_skip(r)
        elif ptype == 1:        # Bool
            r.boolean()
            _read_string_skip(r)
        elif ptype == 2:        # Int
            r.i32()
            _read_string_skip(r)
        elif ptype == 3:        # Float
            r.f32()
            _read_string_skip(r)
        elif ptype == 4:        # Vector3
            r.f32(); r.f32(); r.f32()
            _read_string_skip(r)
        elif ptype == 5:        # Long
            r.i64()
            _read_string_skip(r)
        else:
            raise EpbError(f"PropType inconnu: {ptype}")
    r.u16()


def _skip_statistics(r: "_BinReader", version: int) -> None:
    for _ in range(5):
        r.i32()                 # lights, doors, blockEntities, blockModels, solid
    if version > 12:
        r.i32()                 # cntTriangles
    if version > 17:
        r.i32()                 # cntTrianglesReal
    if version > 23:
        r.i32(); r.i32(); r.i32()
    dist = r.u16()
    for _ in range(dist):
        r.u16()
        r.i32()
    r.f32(); r.f32(); r.f32(); r.f32()
    r.boolean()
    r.boolean()


def _skip_block_groups(r: "_BinReader") -> None:
    version = r.u8()
    count = r.u16()
    for _ in range(count):
        _read_string_skip(r)
        r.boolean()
        if version > 4:
            r.boolean()
        if version > 3:
            r.u8()
        n = r.u16()
        for _ in range(n):
            r.u32()             # Vector3i packee
            if version > 1:
                _read_string_skip(r)


def _7bit_encode(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _read_block_id_mapping(r: "_BinReader") -> Dict[int, str]:
    r.u8()                      # version du format (=1)
    count = r.i32()
    mapping: Dict[int, str] = {}
    for _ in range(count):
        name = r.string()
        local_id = r.u16()
        if name:
            mapping[local_id] = name
    return mapping


@dataclass
class BlockCatalog:
    """Catalogue de blocs : `ids` = {id: nom} (blocs avec Id explicite,
    utilisables comme cible de remplacement) ; `names` = TOUS les noms de
    blocs connus (avec ou sans Id -- les blocs `Ref:` sans Id sont valides,
    le jeu leur attribue un id au chargement) ; `forbidden` = ids avec
    `AllowedInBlueprint: false` (refuses au spawn des blueprints) ;
    `forbidden_names` = les memes PAR NOM (la resolution d'un BP avec
    mapping embarque est par nom, et un bloc interdit peut n'avoir pas
    d'Id -- ex CoreNoCPU de RE2 ATL)."""

    ids: Dict[int, str]
    names: Set[str]
    forbidden: Set[int]
    forbidden_names: Set[str] = field(default_factory=set)


def load_block_catalog(ecf_paths: Iterable[os.PathLike]) -> BlockCatalog:
    """Catalogue de blocs FUSIONNE, dans l'ordre du jeu : les sources sont
    traitees dans l'ordre donne, la derniere definition d'un id gagne (le
    caller passe [vanille, scenario]). Un bloc `Ref:` sans Id herite de
    l'id du nom correspondant ; si cet id est repris par une redefinition
    ulterieure, l'ancien nom disparait de la table (comme le jeu :
    CPUExtenderCVT4 remplace par CPUBrokenCVT4 dans RE2 ATL -> les
    blueprints qui referencent CPUExtenderCVT4 sont touches). Cache en
    memoire (mtime)."""
    paths: List[Path] = []
    for path in ecf_paths or []:
        p = Path(path)
        if p.is_dir():
            paths.extend(sorted(p.glob("BlocksConfig*.ecf")))
        elif p.is_file():
            paths.append(p)
    if not paths:
        return BlockCatalog(ids={}, names=set(), forbidden=set())
    sig = tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in paths)
    cache_key = str(paths)
    cached = _catalog_cache.get(cache_key)
    if cached is not None and cached[0] == sig:
        return cached[1]

    name_to_id: Dict[str, Optional[int]] = {}
    id_to_name: Dict[int, str] = {}
    forbidden: Set[int] = set()
    forbidden_names: Set[str] = set()
    for p in paths:
        try:
            doc = parse_ecf_file(p)
        except Exception:
            continue
        for node in doc.nodes:
            if not isinstance(node, EcfBlock):
                continue
            name = (node.get("Name") or "").strip().strip('"')
            if not name:
                continue
            raw_id = node.get("Id")
            if raw_id is None:
                raw_id = node.get_property("Id")
            bid: Optional[int] = None
            if raw_id is not None:
                try:
                    bid = int(str(raw_id).strip())
                except ValueError:
                    bid = None
            allowed = node.get_property("AllowedInBlueprint")
            is_forbidden = (allowed is not None
                            and allowed.strip().lower() == "false")
            if bid is None:
                # bloc sans Id : connu par nom (id runtime attribue par le jeu)
                name_to_id.setdefault(name, None)
                if is_forbidden:
                    forbidden_names.add(name)
                continue
            # l'id change de main : l'ancien nom le perd (comme le jeu)
            old_name = id_to_name.get(bid)
            if old_name is not None and old_name != name:
                name_to_id.pop(old_name, None)
            id_to_name[bid] = name
            name_to_id[name] = bid
            if is_forbidden:
                forbidden.add(bid)
                forbidden_names.add(name)
    ids = {bid: name for name, bid in name_to_id.items()
           if bid is not None and id_to_name.get(bid) == name}
    names = set(name_to_id)
    result = BlockCatalog(ids=ids, names=names, forbidden=forbidden,
                          forbidden_names=forbidden_names)
    _catalog_cache[cache_key] = (sig, result)
    return result


def load_block_id_catalog(ecf_paths: Iterable[os.PathLike]) -> Dict[int, str]:
    """Compat : {id de bloc: nom} uniquement (sans les blocs sans Id)."""
    return load_block_catalog(ecf_paths).ids


_catalog_cache: Dict[str, tuple] = {}


def scan_epb_files(root: os.PathLike) -> List[Path]:
    """Tous les .epb sous `root` (recursif), tries."""
    rootp = Path(root)
    if rootp.is_file():
        return [rootp]
    found = [Path(dirpath) / fn
             for dirpath, _dirnames, filenames in os.walk(rootp)
             for fn in filenames if fn.lower().endswith(".epb")]
    return sorted(found)


class EpbBlueprint:
    """Blueprint .epb : lecture de la structure de blocs, verification
    contre un catalogue d'ids connus, suppression de blocs, reecriture."""

    def __init__(self, path: os.PathLike, ecf_paths: Optional[Iterable[os.PathLike]] = None):
        self.path = Path(path)
        self.ecf_paths = [Path(p) for p in (ecf_paths or [])]
        self.version: int = 0
        self.size: Tuple[int, int, int] = (0, 0, 0)
        self.blocks: List[EpbBlock] = []
        self.id_mapping: Dict[int, str] = {}    # table embarquee du blueprint
        self._map_span = None                   # (debut, fin) de la section mapping dans _prefix
        self._map_dirty = False                 # mapping modifie -> re-serialiser au save
        self.id_names: Dict[int, str] = {}      # catalogue ECF (scenario+vanille)
        self.catalog_names: Set[str] = set()    # tous les noms de blocs ECF
        self._prefix = b""
        self._flags = b""
        self._mask_count = 0
        self._cells: List[Tuple[int, int]] = []  # (index de cellule, uint32 brut)
        self._tail = b""
        self._central = b""
        self._loaded = False

    # ---------------------------------------------------------------- lecture

    def parse(self) -> "EpbBlueprint":
        catalog = load_block_catalog(self.ecf_paths)
        self.id_names = catalog.ids
        self.catalog_names = catalog.names
        data = self.path.read_bytes()
        r = _BinReader(data)
        if r.u32() != EPB_MAGIC:
            raise EpbError("magic EPB introuvable")
        self.version = r.u32()
        if self.version > 1:
            r.u8()                              # PrefabType
        if self.version > 2:
            self.size = (r.i32(), r.i32(), r.i32())
            _skip_properties(r)
        if self.version > 3:
            _skip_statistics(r, self.version)
        self._map_span = None
        if self.version > 27:
            start = r.p                     # octet du booleen de presence
            if r.boolean():
                self.id_mapping = _read_block_id_mapping(r)
            self._map_span = (start, r.p)   # fin = apres le blob mapping
        if self.version >= 9:
            _skip_block_groups(r)

        num = r.i32()                           # taille: entree locale + rep. central
        self._flags = data[r.p:r.p + 2]
        r.skip(2)
        if data[r.p:r.p + 4] != b"PK\x03\x04":
            raise EpbError("entree zip locale introuvable apres le header")
        self._prefix = data[:r.p - 6]
        local = data[r.p:r.p + num]
        self._central = data[r.p + num:]
        r = None

        # entree zip locale : header fixe 30 octets, nom, extra, donnees
        method = struct.unpack_from("<H", local, 8)[0]
        crc = struct.unpack_from("<I", local, 14)[0]
        csize = struct.unpack_from("<I", local, 18)[0]
        usize = struct.unpack_from("<I", local, 22)[0]
        fnlen = struct.unpack_from("<H", local, 26)[0]
        exlen = struct.unpack_from("<H", local, 28)[0]
        data_off = 30 + fnlen + exlen
        self._local_head = local[:data_off]
        comp = local[data_off:data_off + csize]
        if method == 8:
            stream = zlib.decompress(comp, -15)
        elif method == 0:
            stream = comp
        else:
            raise EpbError(f"methode de compression zip non supportee: {method}")
        if crc != zlib.crc32(stream) & 0xFFFFFFFF or len(stream) != usize or len(comp) != csize:
            raise EpbError("donnees de structure corrompues (crc/taille)")

        br = _BinReader(stream)
        self._mask_count = br.i32()
        mask = stream[br.p:br.p + self._mask_count]
        br.skip(self._mask_count)

        sx, sy, sz = self.size
        volume = sx * sy * sz
        cells: List[Tuple[int, int]] = []
        for cell in range(volume):
            bit = (mask[cell // 8] >> (cell % 8)) & 1
            if bit:
                w = br.u32()
                cells.append((cell, w))
        self._cells = cells
        self._tail = stream[br.p:]

        self.blocks = []
        id_hi = self.version >= 28
        for cell, w in cells:
            bid = w & 0x7FF
            if w & 0x1000000 and id_hi:
                bid |= 0x800
            if w & 0x800000:
                bid |= 0x1000
            self.blocks.append(EpbBlock(
                x=cell % sx,
                y=(cell // sx) % sy,
                z=cell // (sx * sy),
                block_id=bid,
                rotation=(w >> 11) & 0x1F,
                hp_field=(w >> 16) & 0x7F,
            ))
        self._loaded = True
        return self

    # ------------------------------------------------------------- verification

    def forbidden_counts(self, forbidden_ids: Set[int],
                         forbidden_names: Optional[Set[str]] = None
                         ) -> Dict[int, int]:
        """Comptage des cellules refusees au spawn (AllowedInBlueprint:
        false). Avec un mapping embarque les ids des cellules sont LOCAUX :
        resolution PAR NOM via forbidden_names ; sinon test par id direct."""
        counts: Dict[int, int] = {}
        by_name = bool(self.id_mapping) and forbidden_names is not None
        for b in self.blocks:
            if by_name:
                name = self.id_mapping.get(b.block_id)
                hit = name is not None and name in forbidden_names
            else:
                hit = b.block_id in forbidden_ids
            if hit:
                counts[b.block_id] = counts.get(b.block_id, 0) + 1
        return counts

    def unknown_counts(self, known_ids: Set[int],
                       known_names: Optional[Set[str]] = None) -> Dict[int, int]:
        """Comptage des blocs qui ne survivront pas au chargement.

        Si le blueprint possede un mapping embarque (cas general des BP avec
        pieces moddees), le jeu resout chaque bloc PAR NOM : id present au
        mapping mais nom absent des ECF courants -> cellule supprimee au
        spawn ; id absent du mapping -> cellule supprimee aussi. Sans
        mapping (BP sauvegarde dans la meme config), test par id direct."""
        counts: Dict[int, int] = {}
        has_mapping = bool(self.id_mapping)
        for b in self.blocks:
            if has_mapping:
                name = self.id_mapping.get(b.block_id)
                if name is None:
                    counts[b.block_id] = counts.get(b.block_id, 0) + 1
                elif known_names is not None and name not in known_names:
                    counts[b.block_id] = counts.get(b.block_id, 0) + 1
            elif b.block_id not in known_ids:
                counts[b.block_id] = counts.get(b.block_id, 0) + 1
        return counts

    def block_name(self, bid: int) -> str:
        name = self.id_mapping.get(bid)
        if name:
            return name
        return self.id_names.get(bid, f"ID_Bloc_{bid}")

    # ------------------------------------------------------------------ edition

    def remove_ids(self, ids: Iterable[int]) -> int:
        """Retire toutes les cellules dont l'id est dans `ids`.
        Retourne le nombre de cellules supprimees (a sauvegarder ensuite)."""
        ids = set(ids)
        kept = [(cell, w) for (cell, w), b in zip(self._cells, self.blocks)
                if b.block_id not in ids]
        removed = len(self._cells) - len(kept)
        self._cells = kept
        self.blocks = [b for b in self.blocks if b.block_id not in ids]
        return removed

    def replace_ids(self, mapping: Dict[int, int],
                    id_names: Optional[Dict[int, str]] = None) -> int:
        """Remplace un id de bloc par un autre (cle = id actuel, valeur =
        id de remplacement), rotation et autres champs conserves.
        Retourne le nombre de cellules remplacees (a sauvegarder ensuite).
        Si le blueprint embarque un BlockIdMapping (resolution PAR NOM au
        spawn), il est tenu a jour : entree de l'ancien id retiree, nouvel
        id mappe vers son nom du catalogue (`id_names`) — sinon la cellule
        remplacee serait SUPPRIMEE au spawn (id absent du mapping, vecu :
        CoreNoCPU remplace par Core (558) -> spawn sans coeur)."""
        id_mask = 0x7FF | 0x800000 | 0x1000000
        count = 0
        new_cells = []
        for cell, w in self._cells:
            old_id = ((w & 0x7FF)
                      + (2048 if w & 0x1000000 else 0)
                      + (4096 if w & 0x800000 else 0))
            if old_id in mapping:
                new_id = mapping[old_id]
                w = (w & ~id_mask & 0xFFFFFFFF) | (new_id & 0x7FF)
                if new_id >= 2048:
                    w |= 0x1000000
                if new_id >= 4096:
                    w |= 0x800000
                count += 1
            new_cells.append((cell, w))
        self._cells = new_cells
        for b in self.blocks:
            if b.block_id in mapping:
                b.block_id = mapping[b.block_id]
        if self.id_mapping:
            touched = False
            for old in mapping:
                if self.id_mapping.pop(old, None) is not None:
                    touched = True
            if id_names:
                for new in mapping.values():
                    name = id_names.get(new)
                    if name and self.id_mapping.get(new) != name:
                        self.id_mapping[new] = name
                        touched = True
            if touched:
                self._map_dirty = True
        return count

    def export_csv(self, path: os.PathLike, headers: Optional[List[str]] = None,
                   name_of=None) -> Path:
        """Exporte tous les blocs (coordonnees, id, nom, rotation...) en CSV
        point-virgule. `name_of(bid)` fournit le libelle d'un id (facultatif)."""
        if headers is None:
            headers = ["X", "Y", "Z", "ID", "Name", "Rotation", "HP", "Raw"]
        target = Path(path)
        with open(target, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(headers)
            for b in self.blocks:
                w.writerow([b.x, b.y, b.z, b.block_id,
                            name_of(b.block_id) if name_of else b.block_id,
                            b.rotation, b.hp_field])
        return target

    def _serialize_mapping(self) -> bytes:
        """Section BlockIdMapping complete (booleen de presence + version du
        format + entrees), triee par id local pour un fichier deterministe."""
        out = bytearray([1, 1])             # present + version du format
        out += struct.pack("<i", len(self.id_mapping))
        for local_id in sorted(self.id_mapping):
            name = self.id_mapping[local_id].encode("utf-8")
            out += _7bit_encode(len(name)) + name + struct.pack("<H", local_id)
        return bytes(out)

    def save(self, path: Optional[os.PathLike] = None, backup: bool = True) -> Path:
        if not self._loaded:
            raise EpbError("blueprint non charge")
        target = Path(path) if path else self.path
        if backup and target.exists():
            backup_path = target.with_suffix(target.suffix + ".bak")
            backup_path.write_bytes(target.read_bytes())
        prefix = self._prefix
        if self._map_dirty and self._map_span:
            # le mapping modifie (remplacement de blocs) doit VRAIMENT
            # etre ecrit : la resolution du jeu est PAR NOM au spawn
            start, end = self._map_span
            prefix = (self._prefix[:start] + self._serialize_mapping()
                      + self._prefix[end:])
        sx, sy, sz = self.size
        volume = sx * sy * sz
        mask_count = (volume + 7) // 8
        mask = bytearray(mask_count)
        values = []
        for cell, w in self._cells:
            mask[cell // 8] |= 1 << (cell % 8)
            values.append(struct.pack("<I", w))
        stream = struct.pack("<i", mask_count) + bytes(mask) + b"".join(values) + self._tail

        crc = zlib.crc32(stream) & 0xFFFFFFFF
        method = struct.unpack_from("<H", self._local_head, 8)[0]
        if method == 8:
            comp = zlib.compressobj(9, zlib.DEFLATED, -15)
            payload = comp.compress(stream) + comp.flush()
        else:
            payload = stream
        usize = len(stream)
        csize = len(payload)
        local_head = bytearray(self._local_head)
        struct.pack_into("<I", local_head, 14, crc)
        struct.pack_into("<I", local_head, 18, csize)
        struct.pack_into("<I", local_head, 22, usize)
        local = bytes(local_head) + payload
        central = self._patch_central(crc, csize, usize)
        # i32 = taille entree locale + repertoire central (cf. readRest du jeu);
        # les octets posterieurs eventuels (terrain fillers...) sont recopies.
        num = len(local) + len(central)
        data = prefix + struct.pack("<i", num) + self._flags + local + central
        target.write_bytes(data)
        return target

    def _patch_central(self, crc: int, csize: int, usize: int) -> bytes:
        central = bytearray(self._central)
        pos = central.find(b"PK\x01\x02")
        if pos >= 0:
            struct.pack_into("<I", central, pos + 16, crc)
            struct.pack_into("<I", central, pos + 20, csize)
            struct.pack_into("<I", central, pos + 24, usize)
        return bytes(central)


# ------------------------------------------------------------------ verifications

def check_epb(path: os.PathLike, known_ids: Set[int],
              known_names: Optional[Set[str]] = None) -> Dict:
    """Analyse un .epb : blocs totaux + comptage des ids inconnus du
    catalogue. Renvoie un rapport dict (erreur capturee dans 'error')."""
    report: Dict = {"path": str(path), "total": 0, "unknown": {}, "error": None}
    try:
        bp = EpbBlueprint(path).parse()
    except Exception as e:  # noqa: BLE001 - rapport d'erreur par fichier
        report["error"] = str(e)
        return report
    report["total"] = len(bp.blocks)
    report["unknown"] = bp.unknown_counts(known_ids, known_names)
    return report


def check_all(paths: Iterable[os.PathLike], known_ids: Set[int],
              known_names: Optional[Set[str]] = None) -> List[Dict]:
    return [check_epb(p, known_ids, known_names) for p in paths]


def remove_unknown_blocks(path: os.PathLike, known_ids: Set[int],
                          known_names: Optional[Set[str]] = None,
                          backup: bool = True) -> Dict:
    """Supprime les blocs inconnus d'un .epb (avec backup .bak) et renvoie
    le rapport ({removed: n, backup: chemin} en plus des champs de check)."""
    report: Dict = {"path": str(path), "total": 0, "unknown": {},
                    "error": None, "removed": 0, "backup": None}
    try:
        bp = EpbBlueprint(path).parse()
    except Exception as e:  # noqa: BLE001 - rapport d'erreur par fichier
        report["error"] = str(e)
        return report
    unknown = bp.unknown_counts(known_ids, known_names)
    report["total"] = len(bp.blocks)
    report["unknown"] = unknown
    if not unknown:
        return report
    bp.remove_ids(unknown.keys())
    target = bp.save(backup=backup)
    report["path"] = str(target)
    report["removed"] = sum(unknown.values())
    if backup:
        report["backup"] = str(target.with_suffix(target.suffix + ".bak"))
    return report
