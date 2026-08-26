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

"""
Verifie que les TROIS endroits portant un numero de version restent
synchronises : core/version.py (APP_VERSION, utilise en jeu par l'appli et
le verificateur de mise a jour), version_info.txt (ressource Windows de
l'executable) et installer.iss (MyAppVersion, installeur Windows).

Bug reel rencontre : lors du passage 1.2.2 -> 1.3.0, seul core/version.py
avait ete mis a jour -- version_info.txt et installer.iss sont restes
bloques sur 1.2.2, donc l'executable/l'installeur affichaient toujours
l'ancienne version malgre le bump. Ce test empeche la regression a chaque
future version.
"""
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def _read_app_version() -> str:
    content = (PROJECT_ROOT / "core" / "version.py").read_text(encoding="utf-8")
    match = re.search(r'APP_VERSION\s*=\s*"([\d.]+)"', content)
    assert match, "APP_VERSION introuvable dans core/version.py"
    return match.group(1)


def test_version_info_txt_matches_app_version():
    app_version = _read_app_version()
    expected_tuple = tuple(int(p) for p in app_version.split(".")) + (0,)
    content = (PROJECT_ROOT / "version_info.txt").read_text(encoding="utf-8")

    filevers_match = re.search(r"filevers=\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)", content)
    prodvers_match = re.search(r"prodvers=\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)", content)
    assert filevers_match and prodvers_match, "filevers/prodvers introuvables dans version_info.txt"
    assert tuple(int(g) for g in filevers_match.groups()) == expected_tuple
    assert tuple(int(g) for g in prodvers_match.groups()) == expected_tuple

    file_version_str_match = re.search(r"FileVersion',\s*u'([\d.]+)'", content)
    product_version_str_match = re.search(r"ProductVersion',\s*u'([\d.]+)'", content)
    assert file_version_str_match and product_version_str_match, \
        "FileVersion/ProductVersion (StringStruct) introuvables dans version_info.txt"
    assert file_version_str_match.group(1) == f"{app_version}.0"
    assert product_version_str_match.group(1) == f"{app_version}.0"


def test_installer_iss_matches_app_version():
    app_version = _read_app_version()
    content = (PROJECT_ROOT / "installer.iss").read_text(encoding="utf-8")
    match = re.search(r'#define MyAppVersion "([\d.]+)"', content)
    assert match, "MyAppVersion introuvable dans installer.iss"
    assert match.group(1) == app_version
