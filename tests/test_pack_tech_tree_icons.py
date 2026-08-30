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

import shutil
import zipfile
from pathlib import Path

from cli.pack_tech_tree_icons import build_pack
from core.tech_tree_icons import ICON_PACK_NOTICE_MEMBER

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "tech_tree_scenario"


def _make_icons_dir(tmp_path: Path, files: dict) -> Path:
    d = tmp_path / "raw_icons"
    for rel, content in files.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
    return d


def test_build_pack_only_includes_referenced_icons(tmp_path):
    icons_dir = _make_icons_dir(tmp_path, {
        "OxygenTankSmallMS.png": b"x",   # reference (fixture)
        "CombatKnife.jpg": b"x",         # reference (fixture)
        "UnrelatedFile.png": b"x",       # PAS reference -- doit etre exclu
    })
    output = tmp_path / "out.pak"

    build_pack(icons_dir, FIXTURE_DIR / "BlocksConfig.ecf", FIXTURE_DIR / "ItemsConfig.ecf", output)

    with zipfile.ZipFile(output) as zf:
        names = set(zf.namelist())
    assert "oxygentanksmallms.png" in names
    assert "combatknife.jpg" in names
    assert not any("unrelated" in n.lower() for n in names)


def test_build_pack_includes_notice(tmp_path):
    icons_dir = _make_icons_dir(tmp_path, {"OxygenTankSmallMS.png": b"x"})
    output = tmp_path / "out.pak"

    build_pack(icons_dir, FIXTURE_DIR / "BlocksConfig.ecf", FIXTURE_DIR / "ItemsConfig.ecf", output)

    with zipfile.ZipFile(output) as zf:
        notice = zf.read(ICON_PACK_NOTICE_MEMBER).decode('utf-8')
    assert "Eleon" in notice
    assert "affichage" in notice.lower()


def test_build_pack_ignores_unsupported_extensions(tmp_path):
    icons_dir = _make_icons_dir(tmp_path, {
        "OxygenTankSmallMS.png": b"x",
        "OxygenTankSmallMS.txt": b"not an image",
    })
    output = tmp_path / "out.pak"

    build_pack(icons_dir, FIXTURE_DIR / "BlocksConfig.ecf", FIXTURE_DIR / "ItemsConfig.ecf", output)

    with zipfile.ZipFile(output) as zf:
        names = zf.namelist()
    assert not any(n.endswith(".txt") and n != ICON_PACK_NOTICE_MEMBER for n in names)


def test_build_pack_scans_nested_directories(tmp_path):
    icons_dir = _make_icons_dir(tmp_path, {
        "Weapons/Melee/CombatKnife.jpg": b"x",
    })
    output = tmp_path / "out.pak"

    build_pack(icons_dir, FIXTURE_DIR / "BlocksConfig.ecf", FIXTURE_DIR / "ItemsConfig.ecf", output)

    with zipfile.ZipFile(output) as zf:
        names = zf.namelist()
    assert "combatknife.jpg" in names


def test_build_pack_missing_icons_directory_exits(tmp_path, capsys):
    import pytest
    output = tmp_path / "out.pak"
    with pytest.raises(SystemExit):
        build_pack(tmp_path / "does_not_exist", FIXTURE_DIR / "BlocksConfig.ecf",
                    FIXTURE_DIR / "ItemsConfig.ecf", output)


def test_packed_icon_is_loadable_end_to_end(tmp_path, qapp):
    """Round-trip complet : icone reelle empaquetee -> lue via core.tech_tree_icons
    -> chargeable en QPixmap non nul, exactement le chemin utilise par le
    widget (voir gui.tech_tree_widget._load_node_pixmap)."""
    from PyQt6.QtGui import QPixmap, QColor
    import core.tech_tree_icons as tti
    from core.tech_tree import load_tech_tree
    from core.tech_tree_icons import build_icon_index, resolve_icon_path, load_icon_bytes

    real_pix = QPixmap(16, 16)
    real_pix.fill(QColor('red'))
    icon_path = tmp_path / "real.png"
    real_pix.save(str(icon_path))

    icons_dir = _make_icons_dir(tmp_path, {})
    icons_dir.mkdir(exist_ok=True)
    shutil.copy(icon_path, icons_dir / "OxygenTankSmallMS.png")
    output = tmp_path / "out.pak"
    build_pack(icons_dir, FIXTURE_DIR / "BlocksConfig.ecf", FIXTURE_DIR / "ItemsConfig.ecf", output)

    original_pack_path = tti.icon_pack_path
    original_bundled = tti.bundled_icon_directory
    tti.icon_pack_path = lambda: output
    tti.bundled_icon_directory = lambda: None
    try:
        idx = build_icon_index(tmp_path / "scenario_sans_icones")
        ref = resolve_icon_path(idx, "OxygenTankSmallMS")
        assert ref is not None
        data = load_icon_bytes(ref)
        assert data is not None
        pix = QPixmap()
        assert pix.loadFromData(data)
        assert not pix.isNull()
    finally:
        tti.icon_pack_path = original_pack_path
        tti.bundled_icon_directory = original_bundled
