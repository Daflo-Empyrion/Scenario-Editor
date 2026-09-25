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

"""Blueprints .epb : lecture de la structure, verification contre un
catalogue d'ids de blocs (scenario + vanille), suppression de blocs
inconnus et reecriture fidele du fichier (fixture .epb synthetique)."""

import struct
import zlib

import pytest

from core.epb_blueprint import (EpbBlueprint, check_all, check_epb,
                                load_block_catalog, load_block_id_catalog,
                                remove_unknown_blocks, scan_epb_files)

SIZE = (3, 2, 2)
# cellule -> id : 0 = connu (412), 5 et 11 = inconnus (dont id >= 2048 et >= 4096
# pour couvrir les bits hauts 23/24 de l'ImageProvider)
CELLS = {0: 412, 5: 7500, 11: 2050}
TAIL = b"FIN-DU-STREAM-DE-STRUCTURE"


def _raw_for(bid: int) -> int:
    """Encode un id au format ImageProvider (bits 0-10 + 23/24)."""
    w = bid & 0x7FF
    if bid >= 2048:
        w |= 0x1000000
    if bid >= 4096:
        w |= 0x800000
    return w


def _7bit(n: int) -> bytes:
    out = b""
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out += bytes([b | 0x80])
        else:
            return out + bytes([b])


def build_epb(path, cells=None, size=SIZE, tail=TAIL, mapping=None):
    cells = CELLS if cells is None else cells
    sx, sy, sz = size
    volume = sx * sy * sz
    mask_count = (volume + 7) // 8
    mask = bytearray(mask_count)
    values = b""
    for cell in sorted(cells):
        mask[cell // 8] |= 1 << (cell % 8)
        values += struct.pack("<I", _raw_for(cells[cell]))
    stream = struct.pack("<i", mask_count) + bytes(mask) + values + tail
    comp = zlib.compressobj(9, zlib.DEFLATED, -15)
    payload = comp.compress(stream) + comp.flush()
    crc = zlib.crc32(stream) & 0xFFFFFFFF
    usize = len(stream)
    csize = len(payload)
    name = b"0"
    local = (b"PK\x03\x04"
             + struct.pack("<HHHHHIIIHH", 20, 0, 8, 0, 0, crc, csize,
                           usize, len(name), 0)
             + name + payload)
    central = (b"PK\x01\x02"
               + struct.pack("<HHHHHHIIIHHHHHII", 20, 20, 0, 8, 0, 0, crc,
                             csize, len(stream), len(name), 0, 0, 0, 0, 0, 0)
               + name)
    eocd = b"PK\x05\x06" + struct.pack("<HHHHIIH", 0, 0, 1, 1, len(central),
                                       len(local), 0)
    header = (struct.pack("<II", 2022986309, 31) + bytes([8])
              + struct.pack("<iii", sx, sy, sz)
              + struct.pack("<HHH", 0, 0, 0)            # properties vides
              + struct.pack("<10i", *([0] * 10))        # statistiques
              + struct.pack("<H", 0)                    # distribution vide
              + struct.pack("<4f", 0, 0, 0, 0)
              + b"\x00\x00")                            # admin/containers
    if mapping:
        blob = struct.pack("<i", len(mapping))
        for lid, mname in mapping.items():
            data = mname.encode("utf-8")
            blob += _7bit(len(data)) + data + struct.pack("<H", lid)
        header += b"\x01" + bytes([1]) + blob          # BlockIdMapping present
    else:
        header += b"\x00"
    header += bytes([5]) + struct.pack("<H", 0)        # groupes vides
    path.write_bytes(header + struct.pack("<i", len(local)) + b"\x00\x01"
                     + local + central + eocd)
    return path


@pytest.fixture
def epb_file(tmp_path):
    return build_epb(tmp_path / "test.epb")


@pytest.fixture
def catalog():
    return {412: "HullTest"}


def test_parse_blocks_and_coords(epb_file, tmp_path, catalog):
    ecf = tmp_path / "BlocksConfig.ecf"
    ecf.write_text("{ Block Id: 412, Name: HullTest\n}\n", encoding="utf-8")
    bp = EpbBlueprint(epb_file, ecf_paths=[ecf]).parse()
    assert bp.version == 31
    assert bp.size == SIZE
    assert [(b.x, b.y, b.z) for b in bp.blocks] == [(0, 0, 0), (2, 1, 0), (2, 1, 1)]
    assert [b.block_id for b in bp.blocks] == [412, 7500, 2050]
    assert bp.id_names[412] == "HullTest"


def test_unknown_counts(epb_file, catalog):
    bp = EpbBlueprint(epb_file, ecf_paths=[]).parse()
    assert bp.unknown_counts(set(catalog)) == {7500: 1, 2050: 1}


def test_check_epb_report(epb_file, catalog):
    report = check_epb(epb_file, set(catalog))
    assert report["total"] == 3
    assert report["unknown"] == {7500: 1, 2050: 1}
    assert report["error"] is None


def test_scan_epb_files(tmp_path, epb_file):
    sub = tmp_path / "Prefabs"
    sub.mkdir()
    build_epb(sub / "autre.epb")
    found = scan_epb_files(tmp_path)
    assert len(found) == 2


def test_remove_unknown_and_rewrite(tmp_path, epb_file, catalog):
    before = EpbBlueprint(epb_file).parse()
    report = remove_unknown_blocks(epb_file, set(catalog), backup=True)
    assert report["removed"] == 2
    backup_path = epb_file.with_suffix(".epb.bak")
    assert backup_path.exists()

    after = EpbBlueprint(epb_file).parse()
    assert [(b.block_id for b in after.blocks)] and \
        [b.block_id for b in after.blocks] == [412]
    assert (after.blocks[0].x, after.blocks[0].y, after.blocks[0].z) == (0, 0, 0)
    # la queue du stream (tout ce qui suit les uint32 de blocs) doit rester
    # octet-pour-octet identique
    assert after._tail == before._tail


def test_remove_unknown_in_place_with_backup(tmp_path, catalog):
    p = build_epb(tmp_path / "test.epb")
    assert remove_unknown_blocks(p, set(catalog), backup=True)["removed"] == 2
    after = EpbBlueprint(p).parse()
    assert [b.block_id for b in after.blocks] == [412]
    backup = EpbBlueprint(p.with_suffix(".epb.bak")).parse()
    assert [b.block_id for b in backup.blocks] == [412, 7500, 2050]


def test_keep_known_high_id_block(tmp_path):
    # un id haut CONNU (bande 6144-8191, bits 23+24) doit survivre a la
    # suppression des inconnus ; NB : la bande 4096-6144 n'est pas fiable
    # dans le format Eleon (encode/decode non inverses, quirk du jeu).
    cells = {0: 412, 5: 7500}
    p = build_epb(tmp_path / "haut.epb", cells=cells)
    report = remove_unknown_blocks(p, {412, 7500}, backup=False)
    assert report["removed"] == 0
    after = EpbBlueprint(p).parse()
    assert [b.block_id for b in after.blocks] == [412, 7500]


def test_load_block_id_catalog_from_ecf(tmp_path):
    ecf = tmp_path / "BlocksConfig.ecf"
    ecf.write_text(
        "{ Block Id: 412, Name: HullTest\n  Category: Hull\n}\n",
        encoding="utf-8")
    assert load_block_id_catalog([ecf]) == {412: "HullTest"}


def test_replace_ids_preserves_position_and_rotation(tmp_path, catalog):
    # la cellule (2,1,0) (inconnu 7500, rotation encodee) est remplacee par
    # le bloc connu 412 : position et rotation conserves, id change
    p = build_epb(tmp_path / "avant.epb")
    bp = EpbBlueprint(p, ecf_paths=[]).parse()
    rot_before = next(b.rotation for b in bp.blocks if b.block_id == 7500)
    assert bp.replace_ids({7500: 412}) == 1
    bp.save(backup=False)

    after = EpbBlueprint(p).parse()
    assert sorted(b.block_id for b in after.blocks) == [412, 412, 2050]
    replaced = next(b for b in after.blocks if (b.x, b.y, b.z) == (2, 1, 0))
    assert replaced.rotation == rot_before


def test_export_csv_all_blocks(tmp_path, epb_file):
    bp = EpbBlueprint(epb_file).parse()
    out = tmp_path / "export.csv"
    bp.export_csv(out, headers=["X", "Y", "Z", "ID", "Name", "Rotation", "HP"],
                  name_of=lambda bid: f"Nom_{bid}")
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1 + len(bp.blocks)
    assert lines[1].split(";")[0:2] == ["0", "0"]
    assert "Nom_412" in lines[1]


def test_remove_unknown_missing_file_reports_error(tmp_path, catalog):
    report = remove_unknown_blocks(tmp_path / "inexistant.epb", set(catalog))
    assert report["error"] is not None


def test_forbidden_blocks_from_ecf(tmp_path):
    ecf = tmp_path / "BlocksConfig.ecf"
    ecf.write_text(
        "{ Block Id: 412, Name: HullTest\n}\n"
        "{ Block Id: 1402, Name: CoreNoCPU\n"
        "  AllowedInBlueprint: false\n}\n"
        "{ Block Id: 2050, Name: PentaxidTest\n"
        "  AllowedInBlueprint: true\n}\n",
        encoding="utf-8")
    cat = load_block_catalog([ecf])
    assert cat.forbidden == {1402}
    assert cat.ids == {412: "HullTest", 1402: "CoreNoCPU", 2050: "PentaxidTest"}


def test_forbidden_counts_on_blueprint(tmp_path):
    p = build_epb(tmp_path / "test.epb", cells={0: 412, 5: 1402})
    bp = EpbBlueprint(p).parse()
    assert bp.forbidden_counts({1402}) == {1402: 1}
    assert bp.forbidden_counts(set()) == {}


def test_forbidden_names_in_catalog_even_without_id(tmp_path):
    """AllowedInBlueprint: false pose PAR NOM aussi : un bloc interdit sans
    Id (ex CoreNoCPU de RE2 ATL) doit figurer dans forbidden_names."""
    ecf = tmp_path / "BlocksConfig.ecf"
    ecf.write_text(
        "{ Block Name: CoreNoCPU, AllowedInBlueprint: false\n}\n"
        "{ Block Id: 2050, Name: PentaxidTest\n}\n",
        encoding="utf-8")
    cat = load_block_catalog([ecf])
    assert cat.forbidden == set()
    assert cat.forbidden_names == {"CoreNoCPU"}


def test_forbidden_counts_by_name_with_mapping(tmp_path):
    """Vecu RE2 ATL (DT-ANUBIS) : ids de cellules LOCAUX quand un mapping
    embarque existe -- l'interdit doit etre detecte PAR NOM, pas par
    l'id numerique (CoreNoCPU masque/_blanc dans l'arbre avant correction)."""
    ecf = tmp_path / "BlocksConfig.ecf"
    ecf.write_text(
        "{ Block Id: 412, Name: HullTest\n}\n"
        "{ Block Name: CoreNoCPU, AllowedInBlueprint: false\n}\n",
        encoding="utf-8")
    cat = load_block_catalog([ecf])
    p = build_epb(tmp_path / "anubis.epb", cells={0: 7, 5: 999},
                  mapping={7: "HullTest", 999: "CoreNoCPU"})
    bp = EpbBlueprint(p).parse()
    # l'interdit, PAR NOM (l'id 999 local ne peut pas matcher les ECF)
    assert bp.forbidden_counts(cat.forbidden,
                               cat.forbidden_names) == {999: 1}
    # sans l'argument nom : ancien comportement par id (aucun hit ici)
    assert bp.forbidden_counts(cat.forbidden) == {}
    # ni inconnu : les deux noms existent dans les ECF
    assert bp.unknown_counts(set(cat.ids), cat.names) == {}


def test_replace_updates_mapping_and_persists(tmp_path):
    """Vecu 24/09 : CoreNoCPU remplace par Core (558) restait « inconnu »
    et le blueprint spawnait SANS coeur — le mapping embarque n'etait ni
    mis a jour (558 absent -> suppression au spawn), ni re-serialise au
    save (l'entete etait recopiee verbatim)."""
    ecf = tmp_path / "BlocksConfig.ecf"
    ecf.write_text("{ Block Id: 412, Name: HullTest\n}\n"
                   "{ Block Id: 558, Name: Core\n}\n", encoding="utf-8")
    cat = load_block_catalog([ecf])
    p = build_epb(tmp_path / "bp.epb", cells={0: 7, 5: 999},
                  mapping={7: "HullTest", 999: "CoreNoCPU"})
    bp = EpbBlueprint(p, ecf_paths=[ecf]).parse()
    assert bp.replace_ids({999: 558}, id_names=cat.ids) == 1
    # mapping tenu a jour : l'ancien nom parti, le nouveau id -> son nom
    assert bp.id_mapping == {7: "HullTest", 558: "Core"}
    assert bp.unknown_counts(set(cat.ids), cat.names) == {}
    assert bp._map_dirty
    out = bp.save(backup=False)
    after = EpbBlueprint(out, ecf_paths=[ecf]).parse()
    assert after.id_mapping == {7: "HullTest", 558: "Core"}
    assert sorted(b.block_id for b in after.blocks) == [7, 558]
    assert after.unknown_counts(set(cat.ids), cat.names) == {}


def test_save_without_mapping_change_keeps_section_identical(tmp_path):
    """Un save SANS modification de mapping ne doit pas toucher l'entete
    (la section mapping est recopiee a l'identique)."""
    ecf = tmp_path / "BlocksConfig.ecf"
    ecf.write_text("{ Block Id: 412, Name: HullTest\n}\n", encoding="utf-8")
    p = build_epb(tmp_path / "bp.epb", cells={0: 7},
                  mapping={7: "HullTest"})
    original = p.read_bytes()
    bp = EpbBlueprint(p, ecf_paths=[ecf]).parse()
    bp.save(backup=False)
    after = p.read_bytes()
    # meme taille ; la section mapping (offsets) identique octet a octet
    assert len(after) == len(original)
    start, end = bp._map_span
    assert original[start:end] == after[start:end]


def test_known_by_mapping_name(tmp_path):
    """Avec mapping embarque : la resolution se fait PAR NOM. Un bloc dont
    le nom existe dans les ECF (bloc Ref: sans Id du scenario) est connu
    meme si son id numerique n'y figure pas ; un nom absent -> inconnu."""
    ecf = tmp_path / "BlocksConfig.ecf"
    ecf.write_text(
        "{ Block Name: SoloBlock, Ref: Other\n}\n"          # sans Id !
        "{ Block Id: 412, Name: HullTest\n}\n",
        encoding="utf-8")
    cells = {0: 412, 5: 7500}               # 7500 -> nom SoloBlock via mapping
    p = build_epb(tmp_path / "mappé.epb", cells=cells,
                  mapping={7500: "SoloBlock"})
    bp = EpbBlueprint(p).parse()
    assert bp.id_mapping[7500] == "SoloBlock"
    # connu par nom : meme sans id 7500 dans les ECF
    assert bp.unknown_counts(set(), known_names=set()) == {412: 1, 7500: 1}
    assert bp.unknown_counts(set(), known_names={"SoloBlock"}) == {412: 1}
    # id present dans les ECF mais PAS dans le mapping -> supprime au spawn
    assert bp.unknown_counts({9999}, known_names={"SoloBlock"}) == {412: 1}


def test_unmapped_id_with_mapping_is_unknown(tmp_path):
    """Mapping present + id de cellule absent du mapping -> le jeu supprime
    la cellule au chargement (SplitControl retourne 0)."""
    p = build_epb(tmp_path / "test.epb", cells={0: 412, 5: 7500},
                  mapping={412: "HullTest"})
    bp = EpbBlueprint(p).parse()
    assert bp.unknown_counts(set(), known_names={"HullTest"}) == {7500: 1}
