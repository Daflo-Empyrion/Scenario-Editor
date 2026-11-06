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

"""`tools/bump_version.py` : les QUATRE emplacements de version bougent
ensemble (l'oubli d'un seul a rougi la CI du tag v2.3.0)."""

import importlib.util
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent / "tools" / "bump_version.py"

VERSION_PY = '"""doc"""\n\nAPP_VERSION = "1.2.3"\n'
VERSION_INFO = """VSVersionInfo(
  fixed=[
    filevers=(1, 2, 3, 0),
    prodvers=(1, 2, 3, 0),
  ],
  kids=[
    StringFileInfo([
      StringTable(u'040904b0', [
        StringStruct(u'FileVersion', u'1.2.3.0'),
        StringStruct(u'ProductVersion', u'1.2.3.0')])
    ]),
    VarFileInfo([VarStruct(u'Translation', [1036, 1200])])
  ]
)
"""
INSTALLER = '#define MyAppName "Empyrion Scenario Editor"\n#define MyAppVersion "1.2.3"\n'


def _module():
    spec = importlib.util.spec_from_file_location("bump_version", TOOLS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def root(tmp_path):
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "version.py").write_text(VERSION_PY, encoding="utf-8")
    (tmp_path / "version_info.txt").write_text(VERSION_INFO, encoding="utf-8")
    (tmp_path / "installer.iss").write_text(INSTALLER, encoding="utf-8")
    return tmp_path


def test_bump_updates_the_four_places(root):
    module = _module()
    touched = module.bump(root, "2.4.0")
    assert {path.name for path in touched} == {"version.py", "version_info.txt",
                                               "installer.iss"}
    assert module.check(root, "2.4.0") == []
    text = (root / "version_info.txt").read_text(encoding="utf-8")
    assert "filevers=(2, 4, 0, 0)" in text and "prodvers=(2, 4, 0, 0)" in text
    assert "u'2.4.0.0'" in text
    assert (root / "installer.iss").read_text(encoding="utf-8").count('"2.4.0"') == 1
    assert 'APP_VERSION = "2.4.0"' in (root / "core" / "version.py").read_text(
        encoding="utf-8")


def test_dry_run_writes_nothing(root):
    module = _module()
    module.bump(root, "9.9.9", dry_run=True)
    assert module.check(root, "1.2.3") == []
    assert module.check(root, "9.9.9") != []


def test_bad_version_and_missing_pattern_raise(root):
    module = _module()
    with pytest.raises(ValueError):
        module.bump(root, "2.4")
    with pytest.raises(ValueError):
        module.bump(root, "2.4.0-x")
    (root / "installer.iss").write_text("; vide\n", encoding="utf-8")
    with pytest.raises(ValueError):
        module.bump(root, "2.4.0")


def test_check_reports_the_forgotten_place(root):
    """Le cas vecu : installer.iss reste en arriere."""
    module = _module()
    module.bump(root, "2.4.0")
    (root / "installer.iss").write_text(INSTALLER, encoding="utf-8")
    problems = module.check(root, "2.4.0")
    assert any("installer.iss" in problem for problem in problems)
