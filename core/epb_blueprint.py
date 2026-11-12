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

Format reconstruit et verifie contre le moteur du jeu (v1.19.2) :

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
import re
import struct
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
    color: int = 0          # index palette du jeu (face 0 du bloc)


# Palette de 32 couleurs du jeu (uint RGBA : R = bits 16-23, G = bits 8-15,
# B = bits 0-7 ; relevee sur des .epb reels du jeu, revérifiée en v1.20
# build 5229).
EPB_PALETTE_RAW: Tuple[int, ...] = (
    16777215, 16777126, 16711680, 16754409, 16639, 65535, 65433,
    12289882, 14474460, 16774912, 11142405, 16711830, 1716825, 3843799,
    6749952, 8079662, 11184810, 16755203, 11543098, 11215009, 3940,
    3765207, 1873188, 4070922, 7237230, 16736003, 6684672, 6300077,
    3807291, 2564786, 10240, 657930,
)
EPB_PALETTE: Tuple[Tuple[int, int, int], ...] = tuple(
    ((v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF) for v in EPB_PALETTE_RAW
)


def epb_palette_color(index: int) -> Tuple[int, int, int]:
    """RGB d'un index de la palette du jeu (0 = blanc)."""
    return EPB_PALETTE[index % len(EPB_PALETTE)]


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
        r.i32()                 # numero de propriete d'en-tete .epb
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
        if version <= 12:
            r.i32()             # blockId sur 32 bits avant v13 (EPD)
        else:
            r.u16()
        r.i32()
    # AttDefValues n'existe qu'a partir de v26 et les deux booleens finaux
    # qu'au-dela de v28 (parseur EPD de reference) ; l'ancien code lisait
    # les deux partout -> desync de 18 octets en v23-25 (vecu :
    # bEden_BAJ_EscapeRocket.epb v23)
    if version == 26:
        if r.f32() == 4711.08:  # marqueur de presence
            r.u8()
            r.f32(); r.f32(); r.f32(); r.f32()
        else:
            r.f32()             # 2 floats seulement (les 2 autres valent 0)
    elif version > 26:
        r.f32(); r.f32(); r.f32(); r.f32()
    if version > 28:
        r.boolean()
        r.boolean()
    # v28 : les deux booléens finaux disparaissent (vérifié sur le corpus :
    # 8/8 prefabs v28 -> l'octet suivant est le block-groups version 5 avec
    # des comptages cohérents, et le booléen mapping-present lu a cette
    # position vaut False = pas de BlockIdMapping dans ces fichiers)


def _skip_block_groups(r: "_BinReader", epb_version: int) -> None:
    version = r.u8()
    count = r.u16()
    # count == 0 : pas d'octet supplementaire (verifie sur fichiers du jeu
    # v23/v25/v31 — groupes v5 vides puis directement la taille du zip) ;
    # le parseur EPD lit un u32 ici, qui desyncerait ces fichiers
    for _ in range(count):
        _read_string_skip(r)    # Name
        if version >= 5:
            r.u8()              # Unknown03
        r.boolean()             # Unknown01
        if version >= 4:
            r.u8()              # Shortcut
        n = r.u16()
        for _ in range(n):
            if epb_version >= 13:
                r.u32()         # Vector3i packee (x/y/z/scales)
                _read_string_skip(r)
            else:
                # avant v13 : X, Y, Z en trois u32 separement, pas de nom
                r.u32(); r.u32(); r.u32()


_NAME_BYTES = re.compile(rb"[A-Za-z0-9_][A-Za-z0-9_.\- ]{2,63}")


def _scan_id_mapping(data: bytes, start: int = 8,
                     end: Optional[int] = None):
    """Repli v28+ : cherche un blob BlockIdMapping plausible par signature.

    Le chemin strict echoue sur les prefabs dont le layout de statistiques
    n'est pas cartographie (v28 : la lecture derive et cherche un nom de
    1,6 Mo). Le blob est pourtant tres reconnaissable : present=1,
    format=1, count i32 sane, puis count x (varint longueur 3-64 + nom
    ASCII de bloc + u16 id local UNIQUE). Faux positif quasi impossible."""
    pos = start
    end = len(data)
    while pos < end - 8:
        if data[pos] != 1 or data[pos + 1] != 1:
            pos += 1
            continue
        count = struct.unpack_from("<i", data, pos + 2)[0]
        if not (1 <= count <= 1000):
            pos += 1
            continue
        p = pos + 6
        mapping: Dict[int, str] = {}
        ids: Set[int] = set()
        ok = True
        for _ in range(count):
            length, shift = 0, 0
            while True:
                if p >= end:
                    ok = False
                    break
                b = data[p]
                p += 1
                length |= (b & 0x7F) << shift
                if not (b & 0x80):
                    break
                shift += 7
                if shift > 21:
                    ok = False
                    break
            if (not ok or not (3 <= length <= 64)
                    or p + length + 2 > end):
                ok = False
                break
            name = data[p:p + length]
            p += length
            if not _NAME_BYTES.fullmatch(name):
                ok = False
                break
            local_id = struct.unpack_from("<H", data, p)[0]
            p += 2
            if local_id in ids:
                ok = False
                break
            ids.add(local_id)
            mapping[local_id] = name.decode("ascii")
        if ok and len(mapping) == count:
            return mapping
        pos += 1
    return None


def read_id_mapping(path: os.PathLike, max_bytes: int = 2_000_000):
    """Mapping local_id -> nom de bloc embarque dans un .epb, ou None si
    illisible.

    C'est cette table que le jeu resout PAR NOM contre BlocksConfig au
    chargement : un nom absent de la config produit « IdMapping: no name
    for id X found in '<BP>' » et le bloc est ignore au spawn. La lecture
    est BORNEE au header (le mapping precede les donnees compressees) —
    ~30 s pour 5800 prefabs, sans decompression.

    Deux chemins : le layout cartographie (versions lues par parse()) puis,
    en repli, une recherche par signature qui rend lisibles les prefabs
    v28+ a statistiques non cartographiees (vecu 27/10 : 1112 prefabs BAF_*/
    BAJ_*/BAgs_* du corpus RE2)."""
    data = b""
    try:
        with open(path, "rb") as handle:
            data = handle.read(max_bytes)
        if struct.unpack_from("<I", data, 0)[0] != EPB_MAGIC:
            return None
        version = struct.unpack_from("<I", data, 4)[0]
        r = _BinReader(data)
        r.u32()
        r.u32()
        if version > 1:
            r.u8()
        if version <= 2:
            return {}
        r.i32(); r.i32(); r.i32()
        _skip_properties(r)
        _skip_statistics(r, version)
        if version > 27:
            if r.boolean():
                return _read_block_id_mapping(r)
            return {}
        return {}
    except (OSError, struct.error, IndexError, OverflowError, EpbError):
        pass
    if len(data) <= 8:
        return None
    pk = data.find(b"PK\x03\x04")
    return _scan_id_mapping(data, 8, pk if pk > 8 else len(data))


def _read_header_fields(path: os.PathLike, max_bytes: int = 262144):
    """(GroupName, Tags, DisplayName) d'un .epb, ou None si illisible.

    Numerotation VERIFIEE contre le chargement reel du jeu sur des .epb
    produits par le jeu (v1.19.6, reconfirmee sur la v1.20 build 5229 avec les
    prefabs BAO_WSO-SPC-INS) : GroupName = propriete **7**, Tags = **21**,
    DisplayName = 16, et le nom de fichier vient du FileName. La docstring
    precedente annoncait l'inverse (Name=7, groupes=21), ce qui faisait
    passer les GroupName reels pour des noms de prefabs et rendait le
    controle des groupes de POI inutilisable (842 faux positifs sur RE2
    Beta, corrige le 03/11/2026).

    Le moteur indexe les prefabs par
    `Header.GroupName` (chaine entiere) puis par Tags separes par virgule :
    les deux doivent alimenter le pool de groupes. Le Name (propriete 7) est
    souvent le nom de FICHIER ; les playfields peuvent referencer l'un ou
    l'autre.

    Lecture BORNEE au debut du fichier : l'en-tete precede toujours les
    donnees compressees. Toute anomalie rend None — un prefab exotique ne
    doit pas interrompre le scan du scenario."""
    try:
        with open(path, "rb") as handle:
            data = handle.read(max_bytes)
        if struct.unpack_from("<I", data, 0)[0] != EPB_MAGIC:
            return None
        version = struct.unpack_from("<I", data, 4)[0]
        r = _BinReader(data)
        r.u32()
        r.u32()
        if version > 1:
            r.u8()
        if version <= 2:
            return None
        r.i32(); r.i32(); r.i32()
        r.u16()
        count = r.u16()
        name = groups = display = ""
        for _ in range(count):
            key = r.i32()
            r.boolean(); r.boolean(); r.boolean()
            ptype = r.u8()
            # type 0 : la valeur est la chaine ; 1-5 : valeur puis NOM de
            # propriete (les deux consommes pour rester aligne)
            if ptype == 0:
                value = r.string()
            elif ptype == 1:
                r.boolean(); value = r.string()
            elif ptype == 2:
                r.i32(); value = r.string()
            elif ptype == 3:
                r.f32(); value = r.string()
            elif ptype == 4:
                r.f32(); r.f32(); r.f32(); value = r.string()
            elif ptype == 5:
                r.i64(); value = r.string()
            else:
                return None
            if ptype == 0 and key == 7:
                name = value
            elif ptype == 0 and key == 21:
                groups = value
            elif ptype == 0 and key == 16:
                display = value
        return name, groups, display
    except (OSError, struct.error, IndexError, EpbError):
        return None


def read_header(path: os.PathLike, max_bytes: int = 262144):
    """(GroupName, Tags) d'un .epb, ou None si illisible.

    Signature historique (2 valeurs) conservee : les appelants (`_index_prefabs`,
    `pda_script_dialog`) n'ont pas a changer. Le DisplayName est expose par
    `read_display_name()`."""
    fields = _read_header_fields(path, max_bytes)
    return (fields[0], fields[1]) if fields else None


def read_display_name(path: os.PathLike, max_bytes: int = 262144):
    """Nom d'AFFICHAGE du prefab (propriete 16), ou vide.

    C'est le nom que le joueur voit et que le PDA vise dans `NearPoi:` —
    souvent different du nom de fichier et du GroupName (vecu 03/11/2026 :
    `Ship Landing Site` = DisplayName de R2BA_FreighterStory.epb)."""
    fields = _read_header_fields(path, max_bytes)
    return (fields[2] or "") if fields else ""


def read_meta_info(path: os.PathLike, max_bytes: int = 262144) -> Dict[str, str]:
    """Infos d'entete d'un .epb en dict, d'apres la numerotation des
    proprietes verifiee sur des .epb produits par le jeu :
    `group` = propriete **7** (GroupName — la cle d'indexation des POI),
    `tags` = **21**, `display` = **16**. Chaines vides si illisible ou si
    la propriete est absente (les BP n'ont pas tous un groupe)."""
    fields = _read_header_fields(path, max_bytes)
    if not fields:
        return {"group": "", "tags": "", "display": ""}
    return {"group": fields[0] or "", "tags": fields[1] or "",
            "display": fields[2] or ""}


def extract_block_definition(source_text: str, name: str,
                             max_depth: int = 40) -> Optional[str]:
    """Texte brut du bloc `Name: <name>` dans un fichier ECF (accolades
    equilibrees, retourne avec les commentaires). None si absent ou
    mal forme — sert a importer des definitions de blocs d'autres
    scenarios (retour utilisateur 07/11)."""
    marker = "Name: " + name
    for m in re.finditer(re.escape(marker) + r'(?![\w])', source_text):
        start = source_text.rfind('{', 0, m.start())
        if start < 0:
            continue
        depth = 0
        end = -1
        for i in range(start, min(len(source_text), start + max_depth * 4096)):
            c = source_text[i]
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end < 0:
            continue
        return source_text[start:end] + "\r\n"
    return None


def block_id_from_definition(text: str) -> Optional[int]:
    """Id declare dans une definition de bloc (None si sans Id)."""
    m = re.search(r'\bId:\s*(\d+)', text)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Entites internes (NPC, conteneurs nommes) : le payload de l'entree zip n'est
# PAS parse par l'editeur (sa structure apres les uint32 de blocs n'est pas
# cartographiee). En revanche les NOMS y figurent en clair : on extrait les
# chaines imprimables. C'est ce qu'un `NearPoi:` du PDA vise quand il DESIGN
# une entite (`Security Manager` = NPC, confirme par l'utilisateur 03/11).
# Extraction volontairement grossiere : elle sert a RECONNAITRE un nom, jamais
# a l'editer.
# ---------------------------------------------------------------------------
_STRING_RE = re.compile(rb"[\x20-\x7e]{4,80}")
_NAME_HINT_RE = re.compile(r"^[A-Za-z][A-Za-z0-9 _'\-]{2,59}$")


def read_entity_names(path: os.PathLike,
                      max_bytes: int = 1_000_000) -> Set[str]:
    """Noms d'ENTITES du header seul (crew/NPC), sans decompression.

    Variante rapide de `read_internal_strings` pour indexer des milliers de
    prefabs : les entites sont dans le binaire non compresse avant la
    frontiere zip (verifie : `Security Manager`, `Resident`, `Gambler`,
    `Station Chief` dans RBA_PolarisTradingStory.epb)."""
    try:
        with open(path, "rb") as handle:
            data = handle.read(max_bytes)
    except OSError:
        return set()
    start = data.find(b"PK\x03\x04")
    head = data[:start] if start > 0 else data
    out: Set[str] = set()
    for raw in _STRING_RE.findall(head):
        text = raw.decode("ascii", "ignore").strip()
        if _NAME_HINT_RE.match(text):
            out.add(text)
    return out


def read_internal_strings(path: os.PathLike,
                          max_payload: int = 8_000_000) -> Set[str]:
    """Chaines « nom » d'un .epb : ENTITES du header + payload decompresse.

    Les noms d'entites (crew/NPC : `Security Manager`, `Resident`,
    `Gambler`...) sont dans le binaire NON compresse du header, juste avant
    la frontiere zip — verifie sur RBA_PolarisTradingStory.epb (03/11/2026).
    Le payload apporte les dialogues/identifiants internes.

    Vide si le fichier n'a pas d'entree zip lisible (97 prefabs exotiques du
    corpus RE2) — jamais d'exception."""
    import zipfile
    try:
        data = Path(path).read_bytes()
        start = data.find(b"PK\x03\x04")
        head = data[:start] if start > 0 else data
        out: Set[str] = set()
        for raw in _STRING_RE.findall(head):
            text = raw.decode("ascii", "ignore").strip()
            if _NAME_HINT_RE.match(text):
                out.add(text)
        if start < 0:
            return out
        with zipfile.ZipFile(io.BytesIO(data[start:])) as zf:
            for info in zf.infolist():
                if sum(len(x) for x in out) > max_payload:
                    break
                blob = zf.read(info.filename)
                for raw in _STRING_RE.findall(blob):
                    text = raw.decode("ascii", "ignore").strip()
                    if _NAME_HINT_RE.match(text):
                        out.add(text)
        return out
    except (OSError, zipfile.BadZipFile, RuntimeError):
        return set()


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

    # blocs et items vivent dans des espaces d'ids SEPARES (le jeu resout
    # un nom de mapping dans l'un OU l'autre) : deux tables, sinon l'Item
    # Id 978 ecraserait le Block Id 978 Window_s1x2Thick — vecu 07/11,
    # ~714 faux inconnus au controle blueprints
    name_to_id: Dict[str, Optional[int]] = {}
    id_to_name: Dict[int, str] = {}
    forbidden: Set[int] = set()
    forbidden_names: Set[str] = set()
    item_names: Set[str] = set()
    item_name_to_id: Dict[str, Optional[int]] = {}
    item_id_to_name: Dict[int, str] = {}
    for p in paths:
        try:
            doc = parse_ecf_file(p)
        except Exception:
            continue
        is_items = Path(p).name.startswith("Items")
        n_table = item_name_to_id if is_items else name_to_id
        id_table = item_id_to_name if is_items else id_to_name
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
            if is_items:
                item_names.add(name)
            if bid is None:
                # bloc sans Id : connu par nom (id runtime attribue par le jeu)
                n_table.setdefault(name, None)
                if is_forbidden:
                    forbidden_names.add(name)
                continue
            # l'id change de main : l'ancien nom le perd (comme le jeu) —
            # DANS LE MEME ESPACE (bloc vs item)
            old_name = id_table.get(bid)
            if old_name is not None and old_name != name:
                n_table.pop(old_name, None)
            id_table[bid] = name
            n_table[name] = bid
            if is_forbidden:
                forbidden.add(bid)
                forbidden_names.add(name)
    ids = {bid: name for bid, name in item_id_to_name.items()
           if bid is not None and item_id_to_name.get(bid) == name}
    # collision bloc/item sur un id : le bloc gagne (la matrice d'un
    # blueprint ne contient que des blocs)
    ids.update({bid: name for bid, name in id_to_name.items()
                if bid is not None and id_to_name.get(bid) == name})
    names = set(name_to_id) | item_names
    result = BlockCatalog(ids=ids, names=names, forbidden=forbidden,
                          forbidden_names=forbidden_names)
    _catalog_cache[cache_key] = (sig, result)
    return result


def load_block_id_catalog(ecf_paths: Iterable[os.PathLike]) -> Dict[int, str]:
    """Compat : {id de bloc: nom} uniquement (sans les blocs sans Id)."""
    return load_block_catalog(ecf_paths).ids


_catalog_cache: Dict[str, tuple] = {}


_workshop_cache: Dict[str, tuple] = {}


def load_workshop_block_names(vanilla_content_path: str
                              ) -> Tuple[str, Dict[int, str], int]:
    """{id de bloc: nom} agrege depuis les BlocksConfig de TOUS les
    scenarios du workshop Steam (`<steam>/steamapps/workshop/content/
    383120/<scenario>/Content/Configuration`), deduit du chemin vanille.
    Annuaire de secours pour NOMMER les blocs inconnus du scenario analyse
    (retour utilisateur 07/11 : un id absent de la vanille et du scenario
    existe souvent dans un autre scenario du workshop). Cache par racine ;
    ne modifie JAMAIS le statut connu/inconnu — uniquement le nom affiche."""
    if not vanilla_content_path:
        return "", {}, 0
    root = Path(vanilla_content_path)
    if len(root.parents) < 3:
        return "", {}, 0
    ws = root.parents[2] / "workshop" / "content" / "383120"
    if not ws.is_dir():
        return "", {}, 0
    cached = _workshop_cache.get(str(ws))
    if cached is not None:
        return cached
    names: Dict[int, str] = {}
    scenarios = 0
    for sc in sorted(ws.iterdir()):
        cfg = sc / "Content" / "Configuration"
        if not cfg.is_dir():
            continue
        try:
            ids = load_block_id_catalog([cfg / "BlocksConfig.ecf"])
        except Exception:  # noqa: BLE001 - un scenario illisible n'arrete pas
            continue
        if ids:
            scenarios += 1
        for bid, nm in ids.items():
            names.setdefault(bid, nm)
    result = (str(ws), names, scenarios)
    _workshop_cache[str(ws)] = result
    return result


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
        self._trailer = b""
        self._sections_start = 0                # debut de _tail dans le flux
        self._color_offsets: Dict[int, int] = {}  # cellule -> offset de sa couleur
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
        self._props_span = None                 # (debut, fin) des metas
        if self.version > 2:
            self.size = (r.i32(), r.i32(), r.i32())
            start = r.p
            _skip_properties(r)
            self._props_span = (start, r.p)
        if self.version > 3:
            _skip_statistics(r, self.version)
        self._map_span = None
        if self.version > 27:
            start = r.p                     # octet du booleen de presence
            if r.boolean():
                self.id_mapping = _read_block_id_mapping(r)
            self._map_span = (start, r.p)   # fin = apres le blob mapping
        if self.version >= 9:
            _skip_block_groups(r, self.version)

        # frontiere zip : le repertoire central est colle avant l'EOCD
        # (cd_start = eocd - cd_size — les deux conventions d'offsets
        # observees dans les fichiers reels tombent juste), et l'entree
        # "0" (matrice) est retrouvee par son NOM en scannant les
        # signatures locales entre la fin du header et le repertoire.
        # Robuste aux zips multi-entrees, au bourrage apres l'EOCD et aux
        # num2 incoherents (vecu : 1084 prefabs de RE2-FR ouvraient en
        # erreur avec l'heuristique num = u32(pk-6))
        zero_meta = None
        eocd = cd_start = -1
        cand = data.rfind(b"PK\x05\x06")
        while cand >= 0:
            size = struct.unpack_from("<I", data, cand + 12)[0]
            start = cand - size
            if start >= 0 and data[start:start + 4] == b"PK\x01\x02":
                eocd, cd_start = cand, start
                break
            cand = data.rfind(b"PK\x05\x06", 0, cand)
        if eocd < 0:
            raise EpbError("repertoire central zip introuvable")
        pos = cd_start
        while pos + 46 <= eocd and struct.unpack_from(
                "<I", data, pos)[0] == 0x02014b50:
            fn = struct.unpack_from("<H", data, pos + 28)[0]
            ex = struct.unpack_from("<H", data, pos + 30)[0]
            co = struct.unpack_from("<H", data, pos + 32)[0]
            if data[pos + 46:pos + 46 + fn] == b"0":
                zero_meta = struct.unpack_from("<III", data, pos + 16)
            pos += 46 + fn + ex + co
        if zero_meta is None:
            raise EpbError("entree zip '0' (matrice) introuvable")
        pk = first_local = -1
        scan = data.find(b"PK\x03\x04", r.p)
        while 0 <= scan < cd_start:
            fn = struct.unpack_from("<H", data, scan + 26)[0]
            cs = struct.unpack_from("<I", data, scan + 18)[0]
            if first_local < 0:
                first_local = scan
            if (data[scan + 30:scan + 30 + fn] == b"0"
                    and cs == zero_meta[1]):
                pk = scan
                break
            scan = data.find(b"PK\x03\x04", scan + 1)
        if pk < 0:
            # vieux fichiers (v<=22) : la signature locale 'PK' est a zero,
            # seul '\x03\x04' subsiste deux octets plus loin (central lho=0,
            # champs decales de -2) — vecu sur A-Destroyer-Base-mission.epb
            scan = data.find(b"\x03\x04", r.p)
            while 0 <= scan < cd_start:
                head = scan - 2
                fn = struct.unpack_from("<H", data, head + 26)[0]
                cs = struct.unpack_from("<I", data, head + 18)[0]
                if (data[head + 30:head + 30 + fn] == b"0"
                        and cs == zero_meta[1]):
                    pk = head
                    break
                scan = data.find(b"\x03\x04", scan + 1)
        if pk < 0:
            raise EpbError("entree locale '0' introuvable")
        self._num_area = data[r.p:first_local] if first_local >= 0 else b""
        fnlen = struct.unpack_from("<H", data, pk + 26)[0]
        exlen = struct.unpack_from("<H", data, pk + 28)[0]
        csize = struct.unpack_from("<I", data, pk + 18)[0]
        self._zero_entry_len = 30 + fnlen + exlen + csize
        self._before = data[first_local:pk] if 0 <= first_local < pk else b""
        self._after = data[pk + self._zero_entry_len:cd_start]
        local = data[pk:pk + self._zero_entry_len]
        self._prefix = data[:r.p]
        self._central = data[cd_start:eocd]
        self._trailer = data[eocd:]

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
        sx, sy, sz = self.size
        volume = sx * sy * sz
        cells: List[Tuple[int, int]] = []
        if self.version <= 4:
            # matrice DENSE : un u32 par cellule, sans masque (EPD
            # ReadBlockTypes, branche v<=4) ; l'air (w = 0) est ecarte
            for cell in range(volume):
                w = struct.unpack_from("<I", stream, cell * 4)[0]
                if w:
                    cells.append((cell, w))
            br.skip(volume * 4)
        else:
            self._mask_count = br.i32()
            mask = stream[br.p:br.p + self._mask_count]
            br.skip(self._mask_count)
            for cell in range(volume):
                bit = (mask[cell // 8] >> (cell % 8)) & 1
                if bit:
                    w = br.u32()
                    cells.append((cell, w))
        self._cells = cells

        # --- sections qui suivent BlockTypes dans le flux decompresse
        # (ordre releve sur des .epb reels : DamageStates, Densities, ...) :
        # on lit Densities/Colors pour les couleurs de la vue 3D ; les
        # octets bruts restent dans _tail pour que save() re-ecrive le
        # fichier a l'identique (matrices clees par cellule : le masque ne
        # bouge pas lors des remplacements d'ids)
        sections_start = br.p

        def _matrix_u(read_value, offsets=None):
            count = br.i32()
            mask = br.d[br.p:br.p + count]
            br.skip(count)
            out = {}
            pos = br.p
            for cell in range(volume):
                if (mask[cell // 8] >> (cell % 8)) & 1:
                    if offsets is not None:
                        offsets[cell] = pos     # u32 : 4 octets par valeur
                        pos += 4
                    out[cell] = read_value()
            return out

        if self.version > 11:
            _matrix_u(br.u16)                   # DamageStates (ignore)
        if br.boolean():                        # Densities : uniforme
            br.skip(1)
        else:
            br.skip(volume)                     # octets denses
        colors = {}
        self._color_offsets = {}
        if self.version >= 8:
            # 6 faces x 5 bits ; face 0 = couleur affichee (EPD)
            colors = _matrix_u(br.u32, self._color_offsets)
        self._sections_start = sections_start

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
                color=colors.get(cell, 0) & 0x1F,
            ))
        self._tail = stream[sections_start:]
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

    def meta_values(self) -> Dict[int, object]:
        """Valeurs brutes des metaproprietes de l'entete ({key: valeur}).
        Encodage verifie sur fichiers reels : Bool (ptype 1) pour
        AddDigoutBox/FlattenTerrain, Long (ptype 5) pour PivotPoint
        (Vector3i packe — vecu : ATL_Citadel pivot = 140640852475882)."""
        if not self._props_span:
            return {}
        start, end = self._props_span
        r = _BinReader(self._prefix[start:end])
        r.u16()                                 # version (1)
        count = r.u16()
        out: Dict[int, object] = {}
        for _ in range(count):
            key = r.i32()
            r.boolean(); r.boolean(); r.boolean()
            ptype = r.u8()
            if ptype == 0:
                r.string()
            elif ptype == 1:
                out[key] = r.boolean(); r.string()
            elif ptype == 2:
                out[key] = r.i32(); r.string()
            elif ptype == 3:
                out[key] = r.f32(); r.string()
            elif ptype == 4:
                r.f32(); r.f32(); r.f32(); r.string()
            elif ptype == 5:
                out[key] = r.i64(); r.string()
            else:
                break
        return out

    def set_meta_values(self, entries: Dict[int, object]) -> None:
        """Upsert de metaproprietes dans l'entete (le prefixe est
        reconstruit, la section mapping est decalee en consequence).
        Type deduit de la valeur : bool -> Bool (1), int -> Long (5).
        Exemples verifies dans le moteur : 1 = AddDigoutBox,
        2 = FlattenTerrain, 3 = GroundYOffset, 18 = PivotPoint."""
        if not self._props_span:
            raise EpbError("pas de section de metaproprietes (version <= 2)")
        start, end = self._props_span
        r = _BinReader(self._prefix[start:end])
        r.u16()
        count = r.u16()
        entries_out: List[Tuple[int, int, object, str]] = []
        existing = set()
        for _ in range(count):
            key = r.i32()
            r.boolean(); r.boolean(); r.boolean()
            ptype = r.u8()
            if ptype == 0:
                value = r.string()
            elif ptype == 1:
                value = r.boolean(); r.string()
            elif ptype == 2:
                value = r.i32(); r.string()
            elif ptype == 3:
                value = r.f32(); r.string()
            elif ptype == 4:
                value = (r.f32(), r.f32(), r.f32()); r.string()
            elif ptype == 5:
                value = r.i64(); r.string()
            else:
                break
            existing.add(key)
            if key in entries:
                value = entries[key]
                ptype = 1 if isinstance(value, bool) else (
                    3 if isinstance(value, float) else
                    5 if isinstance(value, int) else ptype)
            entries_out.append((key, ptype, value, ""))
        for key, value in entries.items():
            if key in existing:
                continue
            ptype = 1 if isinstance(value, bool) else (
                3 if isinstance(value, float) else
                5 if isinstance(value, int) else 0)
            entries_out.append((key, ptype, value, ""))
        blob = struct.pack("<HH", 1, len(entries_out))
        for key, ptype, value, name in entries_out:
            blob += struct.pack("<i", key) + b"\x00\x00\x00"
            blob += struct.pack("<B", ptype)
            if ptype == 0:
                blob += _7bit_encode(len(value.encode("utf-8"))) + value.encode("utf-8")
            elif ptype == 1:
                blob += (b"\x01" if value else b"\x00")
                blob += _7bit_encode(0)
            elif ptype == 2:
                blob += struct.pack("<i", int(value)) + _7bit_encode(0)
            elif ptype == 3:
                blob += struct.pack("<f", float(value)) + _7bit_encode(0)
            elif ptype == 4:
                blob += struct.pack("<fff", *value) + _7bit_encode(0)
            elif ptype == 5:
                blob += struct.pack("<q", int(value)) + _7bit_encode(0)
        blob += struct.pack("<H", 0)
        delta = len(blob) - (end - start)
        self._prefix = self._prefix[:start] + blob + self._prefix[end:]
        self._props_span = (start, start + len(blob))
        if self._map_span:
            ms, me = self._map_span
            self._map_span = (ms + delta, me + delta)

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

    def set_colors(self, ids: Iterable[int], index: int = 0,
                   only_colors: Optional[Iterable[int]] = None) -> int:
        """Force l'index palette de face 0 des blocs dont l'id est dans `ids`
        (restreint aux variantes de `only_colors` si fourni).
        La couleur vit dans la matrice Colors (dans _tail), pas dans le mot de
        cellule : on patche ses valeurs, le masque ne bouge donc pas.
        Retourne le nombre de cellules modifiees (a sauvegarder ensuite).

        Sert aux blocs d'une famille a UNE texture (`Texture: 59`, ex. Truss) :
        un prefab qui leur donne une variante couleur fait echouer la creation
        du mesh (`Cannot create mesh for block id=... texIdx=...`)."""
        ids = set(ids)
        cibles = set(only_colors) if only_colors is not None else None
        sx, sy, _ = self.size
        cells = {b.x + sx * (b.y + sy * b.z)
                 for b in self.blocks
                 if b.block_id in ids and (cibles is None or b.color in cibles)}
        if not cells or not self._tail:
            return 0
        tail = bytearray(self._tail)
        changed = set()
        for cell in cells:
            off = self._color_offsets.get(cell)
            if off is None:
                continue
            rel = off - self._sections_start
            w = struct.unpack_from("<I", tail, rel)[0]
            new = (w & ~0x1F) | (index & 0x1F)
            if new == w:
                continue
            struct.pack_into("<I", tail, rel, new)
            changed.add(cell)
        if not changed:
            return 0
        self._tail = bytes(tail)
        for b in self.blocks:                   # vue 3D / relecture coherente
            if b.block_id in ids and (cibles is None or b.color in cibles):
                b.color = index
        return len(changed)

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
        # la zone num (i32 taille + flags du jeu) est recopiee telle quelle
        # (2 ou 6 octets selon les fichiers) ; l'i32 couvre entree locale +
        # repertoire central + EOCD (verifie sur fichiers reels) ; les
        # octets posterieurs eventuels (terrain fillers...) sont recopies.
        num = len(local) + len(central) + 22
        num_area = bytearray(self._num_area)
        if len(num_area) >= 4:
            struct.pack_into("<i", num_area, 0, num)
        data = (prefix + bytes(num_area) + local + central + self._trailer)
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
