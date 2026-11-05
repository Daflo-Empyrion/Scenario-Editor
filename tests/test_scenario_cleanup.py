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

"""Nettoyage du scenario (core/scenario_cleanup.py) : fichiers SURS (.bak,
cache orphelin, compagnon de prefab disparu) et images A VERIFIER."""
from pathlib import Path

from core.scenario_cleanup import scan_junk, trash_files


def _scenario(tmp_path: Path, config: str = "") -> Path:
    (tmp_path / "Content" / "Configuration").mkdir(parents=True)
    (tmp_path / "Content" / "Configuration" / "ItemsConfig.ecf").write_text(
        config, encoding="utf-8")
    pf = tmp_path / "Playfields" / "PlanetA"
    pf.mkdir(parents=True)
    (pf / "playfield_static.yaml").write_text("Seed: 1\n", encoding="utf-8")
    return tmp_path


def test_backup_orphan_cache_and_thumbnail_are_safe(tmp_path):
    root = _scenario(tmp_path)
    (root / "Sectors").mkdir()
    (root / "Sectors" / "Sectors.yaml.bak").write_text("x", encoding="utf-8")
    (root / "Playfields" / "PlanetA" / "playfield_gone.yaml.bin").write_bytes(b"x")
    prefabs = root / "Prefabs"
    prefabs.mkdir()
    (prefabs / "Gone.jpg").write_bytes(b"x")
    (prefabs / "Gone.decals").write_text("x", encoding="utf-8")
    (prefabs / "Kept.epb").write_bytes(b"x")
    (prefabs / "Kept.jpg").write_bytes(b"x")

    items = scan_junk(root)
    surs = {i.path.name for i in items if i.safe}
    assert surs == {"Sectors.yaml.bak", "playfield_gone.yaml.bin",
                    "Gone.jpg", "Gone.decals"}
    assert all(not i.safe for i in items if i.path.name not in surs)


def test_image_uncited_is_flagged_but_not_safe(tmp_path):
    root = _scenario(tmp_path)
    img = root / "SharedData" / "Content" / "Images"
    img.mkdir(parents=True)
    (img / "Orphan.png").write_bytes(b"x")
    (img / "Cited.png").write_bytes(b"x")
    (img / "Prefixed.png").write_bytes(b"x")
    # Cited: cite tel quel ; Prefixed: cite avec un prefixe colle (bki...)
    (root / "Content" / "Configuration" / "ItemsConfig.ecf").write_text(
        "+Item Name: A\n  Icon: Cited.png\n"
        "+Item Name: B\n  Info: bkiPrefixed\n", encoding="utf-8")

    items = scan_junk(root)
    noms = {i.path.name: i.safe for i in items if i.category == "asset"}
    assert noms == {"Orphan.png": False}
    assert "Prefixed.png" not in noms        # reference sous prefixe = garde


def test_trash_files_backs_up_then_deletes(tmp_path, monkeypatch):
    f = tmp_path / "Sectors.yaml.bak"
    f.write_bytes(b"x")
    backups = []
    monkeypatch.setattr("core.fsutil.central_backup",
                        lambda p, kind="cleanup": backups.append(Path(p).name))
    faits, echecs = trash_files([f], kind="test")
    assert (faits, echecs) == (1, [])
    assert backups == ["Sectors.yaml.bak"]
    assert not f.exists()


def test_trash_files_refuses_when_backup_fails(tmp_path, monkeypatch):
    f = tmp_path / "orphan.png"
    f.write_bytes(b"x")

    def _ko(path, kind="cleanup"):
        raise OSError("disque plein")

    monkeypatch.setattr("core.fsutil.central_backup", _ko)
    faits, echecs = trash_files([f], kind="test")
    assert faits == 0 and len(echecs) == 1
    assert f.exists()
