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

import zipfile
from pathlib import Path

import pytest

from cli.pack_localization import build_pack
from core.localization_lookup import LOCALIZATION_PACK_NOTICE_MEMBER, LOCALIZATION_PACK_CSV_MEMBER


def test_build_pack_includes_csv_and_notice(tmp_path):
    csv_path = tmp_path / "Localization.csv"
    csv_path.write_text("KEY,English,Français\nHitPoints,Hit points,Points dommages\n", encoding='utf-8')
    output = tmp_path / "out.pak"

    build_pack(csv_path, output)

    with zipfile.ZipFile(output) as zf:
        names = set(zf.namelist())
        assert LOCALIZATION_PACK_CSV_MEMBER in names
        assert LOCALIZATION_PACK_NOTICE_MEMBER in names
        notice = zf.read(LOCALIZATION_PACK_NOTICE_MEMBER).decode('utf-8')
        assert "Eleon" in notice


def test_build_pack_content_matches_source(tmp_path):
    csv_path = tmp_path / "Localization.csv"
    content = "KEY,English,Français\nHitPoints,Hit points,Points dommages\n"
    # Ecrit les octets exacts : write_text() traduirait '\n' en '\r\n' sur
    # Windows, alors que build_pack copie le fichier byte-pour-byte.
    csv_path.write_bytes(content.encode('utf-8'))
    output = tmp_path / "out.pak"

    build_pack(csv_path, output)

    with zipfile.ZipFile(output) as zf:
        packed_content = zf.read(LOCALIZATION_PACK_CSV_MEMBER).decode('utf-8')
    assert packed_content == content


def test_build_pack_missing_source_exits(tmp_path):
    output = tmp_path / "out.pak"
    with pytest.raises(SystemExit):
        build_pack(tmp_path / "does_not_exist.csv", output)
