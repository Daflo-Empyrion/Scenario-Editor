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

from core.tech_tree_icons import (
    icon_directory, build_icon_index, resolve_icon_path, load_icon_bytes, IconRef,
    icon_pack_path, ICON_PACK_NOTICE_MEMBER,
)


def _make_icon_dir(tmp_path: Path) -> Path:
    d = tmp_path / "SharedData" / "Content" / "Bundles" / "ItemIcons"
    d.mkdir(parents=True)
    return d


def test_icon_directory_none_when_absent(tmp_path):
    assert icon_directory(tmp_path) is None


def test_icon_directory_found_when_present(tmp_path):
    d = _make_icon_dir(tmp_path)
    assert icon_directory(tmp_path) == d


def test_build_icon_index_empty_when_no_directory(tmp_path, monkeypatch):
    # Isolement obligatoire : en dev, data/tech_tree_icons.pak et itemicons/
    # existent a la racine du projet et seraient indexes par build_icon_index
    # (sources fusionnees, voir docstring du module) -- on les desactive pour
    # tester le contrat "aucune des trois sources -> dict vide".
    import core.tech_tree_icons as tti
    monkeypatch.setattr(tti, 'icon_pack_path', lambda: None)
    monkeypatch.setattr(tti, 'bundled_icon_directory', lambda: None)
    assert build_icon_index(tmp_path) == {}


def test_build_icon_index_finds_supported_files(tmp_path, monkeypatch):
    import core.tech_tree_icons as tti
    monkeypatch.setattr(tti, 'icon_pack_path', lambda: None)
    monkeypatch.setattr(tti, 'bundled_icon_directory', lambda: None)

    d = _make_icon_dir(tmp_path)
    (d / "FuelTankMSLarge.png").write_bytes(b"fake")
    (d / "SomeOther.jpg").write_bytes(b"fake")
    (d / "notes.txt").write_bytes(b"ignored, unsupported extension")
    idx = build_icon_index(tmp_path)
    assert set(idx.keys()) == {"fueltankmslarge", "someother"}


def test_resolve_icon_path_case_insensitive(tmp_path):
    d = _make_icon_dir(tmp_path)
    (d / "FuelTankMSLarge.png").write_bytes(b"fake")
    idx = build_icon_index(tmp_path)
    expected = IconRef(kind='file', path=d / "FuelTankMSLarge.png")
    assert resolve_icon_path(idx, "fueltankmslarge") == expected
    assert resolve_icon_path(idx, "FUELTANKMSLARGE") == expected


def test_resolve_icon_path_missing_returns_none(tmp_path):
    d = _make_icon_dir(tmp_path)
    (d / "Something.png").write_bytes(b"fake")
    idx = build_icon_index(tmp_path)
    assert resolve_icon_path(idx, "NotThere") is None


def test_bundled_icon_directory_none_when_absent(monkeypatch, tmp_path):
    import core.tech_tree_icons as tti
    monkeypatch.setattr(tti, '__file__', str(tmp_path / "nonexistent_pkg" / "tech_tree_icons.py"))
    assert tti.bundled_icon_directory() is None


def test_build_icon_index_uses_bundled_fallback_when_scenario_has_none(tmp_path, monkeypatch):
    """Dossier itemicons/ (assets extraits par l'utilisateur en dev, voir
    docstring du module) utilise en repli quand le scenario n'a pas son
    propre SharedData/ItemIcons."""
    bundled_dir = tmp_path / "bundled"
    bundled_dir.mkdir()
    (bundled_dir / "FuelTankMSLarge.png").write_bytes(b"fake")

    import core.tech_tree_icons as tti
    monkeypatch.setattr(tti, 'bundled_icon_directory', lambda: bundled_dir)

    scenario_root = tmp_path / "scenario"  # aucun SharedData/ItemIcons ici
    scenario_root.mkdir()
    idx = build_icon_index(scenario_root)
    expected = IconRef(kind='file', path=bundled_dir / "FuelTankMSLarge.png")
    assert resolve_icon_path(idx, "FuelTankMSLarge") == expected


def test_build_icon_index_scenario_overrides_bundled_on_name_collision(tmp_path, monkeypatch):
    """Meme nom d'icone present dans les deux sources -- celle du scenario
    (moddee/personnalisee) doit l'emporter sur celle du dossier itemicons/
    (assets vanilla partages) -- voir docstring du module."""
    bundled_dir = tmp_path / "bundled"
    bundled_dir.mkdir()
    (bundled_dir / "FuelTankMSLarge.png").write_bytes(b"vanilla")

    import core.tech_tree_icons as tti
    monkeypatch.setattr(tti, 'bundled_icon_directory', lambda: bundled_dir)

    scenario_root = tmp_path / "scenario"
    scenario_dir = _make_icon_dir(scenario_root)
    (scenario_dir / "FuelTankMSLarge.png").write_bytes(b"modded")

    idx = build_icon_index(scenario_root)
    expected = IconRef(kind='file', path=scenario_dir / "FuelTankMSLarge.png")
    assert resolve_icon_path(idx, "FuelTankMSLarge") == expected


def test_build_icon_index_scans_recursively(tmp_path):
    """La structure interne d'une extraction d'assets n'est pas garantie
    plate -- voir docstring du module. Sous-dossiers arbitraires acceptes."""
    d = _make_icon_dir(tmp_path)
    nested = d / "Weapons" / "Melee"
    nested.mkdir(parents=True)
    (nested / "CombatKnife.png").write_bytes(b"fake")

    idx = build_icon_index(tmp_path)
    expected = IconRef(kind='file', path=nested / "CombatKnife.png")
    assert resolve_icon_path(idx, "CombatKnife") == expected


# ---------------------------------------------------------------------------
# Archive .pak (voir cli/pack_tech_tree_icons.py + docstring du module)
# ---------------------------------------------------------------------------

def _make_pack(path: Path, entries: dict, with_notice: bool = True) -> Path:
    with zipfile.ZipFile(path, 'w') as zf:
        if with_notice:
            zf.writestr(ICON_PACK_NOTICE_MEMBER, "Propriete Eleon Game Studios -- affichage uniquement.")
        for member, content in entries.items():
            zf.writestr(member, content)
    return path


def test_icon_pack_path_none_when_absent(tmp_path, monkeypatch):
    import core.tech_tree_icons as tti
    monkeypatch.setattr(tti, '__file__', str(tmp_path / "nonexistent_pkg" / "tech_tree_icons.py"))
    assert tti.icon_pack_path() is None


def test_build_icon_index_reads_from_pack(tmp_path, monkeypatch):
    pack_path = _make_pack(tmp_path / "tech_tree_icons.pak", {"FuelTankMSLarge.png": b"vanilla-packed"})

    import core.tech_tree_icons as tti
    monkeypatch.setattr(tti, 'icon_pack_path', lambda: pack_path)
    monkeypatch.setattr(tti, 'bundled_icon_directory', lambda: None)

    idx = build_icon_index(tmp_path / "scenario_without_icons")
    ref = resolve_icon_path(idx, "FuelTankMSLarge")
    assert ref == IconRef(kind='archive', path=pack_path, member="FuelTankMSLarge.png")


def test_pack_notice_member_never_indexed_as_icon(tmp_path, monkeypatch):
    pack_path = _make_pack(tmp_path / "tech_tree_icons.pak", {"Something.png": b"x"})

    import core.tech_tree_icons as tti
    monkeypatch.setattr(tti, 'icon_pack_path', lambda: pack_path)
    monkeypatch.setattr(tti, 'bundled_icon_directory', lambda: None)

    idx = build_icon_index(tmp_path / "scenario")
    assert "notice" not in idx


def test_pack_is_lowest_priority_source(tmp_path, monkeypatch):
    pack_path = _make_pack(tmp_path / "tech_tree_icons.pak", {"FuelTankMSLarge.png": b"vanilla-packed"})
    bundled_dir = tmp_path / "bundled"
    bundled_dir.mkdir()
    (bundled_dir / "FuelTankMSLarge.png").write_bytes(b"dev-local")

    import core.tech_tree_icons as tti
    monkeypatch.setattr(tti, 'icon_pack_path', lambda: pack_path)
    monkeypatch.setattr(tti, 'bundled_icon_directory', lambda: bundled_dir)

    idx = build_icon_index(tmp_path / "scenario")
    ref = resolve_icon_path(idx, "FuelTankMSLarge")
    assert ref.kind == 'file'
    assert ref.path == bundled_dir / "FuelTankMSLarge.png"


def test_load_icon_bytes_from_file():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "icon.png"
        p.write_bytes(b"hello")
        ref = IconRef(kind='file', path=p)
        assert load_icon_bytes(ref) == b"hello"


def test_load_icon_bytes_from_archive(tmp_path):
    pack_path = _make_pack(tmp_path / "tech_tree_icons.pak", {"Foo.png": b"archive-content"})
    ref = IconRef(kind='archive', path=pack_path, member="Foo.png")
    assert load_icon_bytes(ref) == b"archive-content"


def test_load_icon_bytes_returns_none_on_missing_file(tmp_path):
    ref = IconRef(kind='file', path=tmp_path / "does_not_exist.png")
    assert load_icon_bytes(ref) is None


def test_load_icon_bytes_returns_none_on_corrupt_archive(tmp_path):
    bad = tmp_path / "corrupt.pak"
    bad.write_bytes(b"not a real zip file")
    ref = IconRef(kind='archive', path=bad, member="Foo.png")
    assert load_icon_bytes(ref) is None
