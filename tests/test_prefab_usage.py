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

"""Prefabs inutilises (core/prefab_usage.py) : un .epb n'est declare inutilise
que si AUCUN de ses identifiants n'apparait dans le texte du scenario."""
from pathlib import Path

from core import prefab_usage


def _scenario(tmp_path: Path, playfield: str) -> Path:
    prefabs = tmp_path / "Prefabs"
    prefabs.mkdir()
    for nom in ("UsedByGroup", "UsedByFile", "Orphan"):
        (prefabs / f"{nom}.epb").write_bytes(b"fake")
    pf = tmp_path / "Playfields" / "PlanetA"
    pf.mkdir(parents=True)
    (pf / "playfield_static.yaml").write_text(playfield, encoding="utf-8")
    return tmp_path


def test_prefab_used_by_group_name_is_kept(tmp_path, monkeypatch):
    """Le groupe vient du NAME INTERNE de l'entete (propriete 7), pas du nom
    de fichier : c'est ainsi que le jeu choisit un prefab d'un groupe."""
    root = _scenario(tmp_path, "POIs:\n  Random:\n    - GroupName: TheGroup\n")
    entetes = {"UsedByGroup.epb": ("TheGroup", ""),
               "UsedByFile.epb": ("SomethingElse", ""),
               "Orphan.epb": ("Nobody", "")}
    monkeypatch.setattr(prefab_usage, "read_header",
                        lambda p: entetes[p.name])
    rapport = prefab_usage.scan_prefab_usage(root)
    noms = {p.name for p, _s in rapport.unused}
    assert noms == {"UsedByFile.epb", "Orphan.epb"}


def test_prefab_used_by_file_name_is_kept(tmp_path, monkeypatch):
    root = _scenario(tmp_path, "POIs:\n  Fixed:\n    - Prefab: UsedByFile\n")
    monkeypatch.setattr(prefab_usage, "read_header",
                        lambda p: ({"UsedByGroup.epb": "TheGroup",
                                    "UsedByFile.epb": "SomethingElse",
                                    "Orphan.epb": "Nobody"}[p.name], ""))
    rapport = prefab_usage.scan_prefab_usage(root)
    assert {p.name for p, _s in rapport.unused} == {"UsedByGroup.epb",
                                                    "Orphan.epb"}


def test_tag_usage_counts_too(tmp_path, monkeypatch):
    root = _scenario(tmp_path, "POIs:\n  Random:\n    - GroupName: SomeTag\n")
    monkeypatch.setattr(prefab_usage, "read_header",
                        lambda p: ("Whatever", "SomeTag" if p.name == "Orphan.epb"
                                   else ""))
    rapport = prefab_usage.scan_prefab_usage(root)
    assert all(p.name != "Orphan.epb" for p, _s in rapport.unused)


def test_trash_moves_prefab_and_companions(tmp_path, monkeypatch):
    """La corbeille sauvegarde d'abord, puis supprime le .epb ET ses
    compagnons (.decals/.jpg) — un .decals orphelin resterait dans Prefabs/."""
    prefabs = tmp_path / "Prefabs"
    prefabs.mkdir()
    epb = prefabs / "Orphan.epb"
    epb.write_bytes(b"fake")
    (prefabs / "Orphan.decals").write_text("decal", encoding="utf-8")
    (prefabs / "Kept.epb").write_bytes(b"fake")

    sauvegardes = []

    def _backup(path, kind="prefabs"):
        sauvegardes.append(Path(path).name)
        return tmp_path / f"{Path(path).name}.bak"

    monkeypatch.setattr("core.fsutil.central_backup", _backup)
    faits, echecs = prefab_usage.trash_prefabs([epb], kind="test")
    assert (faits, echecs) == (1, [])
    assert sauvegardes == ["Orphan.epb", "Orphan.decals"]
    assert not epb.exists()
    assert not (prefabs / "Orphan.decals").exists()
    assert (prefabs / "Kept.epb").exists()      # jamais touche


def test_trash_keeps_the_file_when_backup_fails(tmp_path, monkeypatch):
    """Pas de sauvegarde = pas de suppression (l'ordre est la garde)."""
    prefabs = tmp_path / "Prefabs"
    prefabs.mkdir()
    epb = prefabs / "Orphan.epb"
    epb.write_bytes(b"fake")

    def _backup(path, kind="prefabs"):
        raise OSError("disque plein")

    monkeypatch.setattr("core.fsutil.central_backup", _backup)
    faits, echecs = prefab_usage.trash_prefabs([epb], kind="test")
    assert faits == 0
    assert len(echecs) == 1
    assert epb.exists()


def test_pda_reference_with_prefix_counts_as_used(tmp_path, monkeypatch):
    """Vecu 05/11 : le PDA ecrit `OPVPolaris_T1` la ou l'entete dit
    `OPVPolaris` — une comparaison de jetons exacts declarait 37 prefabs
    inutilises a tort."""
    prefabs = tmp_path / "Prefabs"
    prefabs.mkdir()
    (prefabs / "CV_PolarisSuperfreighter.epb").write_bytes(b"fake")
    pda = tmp_path / "Extras" / "PDA"
    pda.mkdir(parents=True)
    (pda / "PDA.csv").write_text("KEY;Text\nb1;OPVPolaris_T1 is here\n",
                                 encoding="utf-8")
    monkeypatch.setattr(prefab_usage, "read_header",
                        lambda p: ("OPVPolaris", ""))
    rapport = prefab_usage.scan_prefab_usage(tmp_path)
    assert rapport.unused == []


def test_short_group_tag_matches_only_exactly(tmp_path, monkeypatch):
    """Un tag court (`RE2`) vaut reference quand le scenario ecrit ce jeton
    exactement, mais ne doit pas matcher `RE2foo` — sinon plus rien n'est
    inutilise."""
    prefabs = tmp_path / "Prefabs"
    prefabs.mkdir()
    (prefabs / "OldThing.epb").write_bytes(b"fake")
    (prefabs / "SameThing.epb").write_bytes(b"fake")
    pf = tmp_path / "Playfields" / "PlanetA"
    pf.mkdir(parents=True)
    (pf / "playfield_static.yaml").write_text(
        "POIs:\n  Random:\n    - GroupName: SameThing\n"
        "      Note: RE2foo\n", encoding="utf-8")
    entetes = {"OldThing.epb": ("OldThingRG", "RE2"),
               "SameThing.epb": ("SameThing", "RE2")}
    monkeypatch.setattr(prefab_usage, "read_header", lambda p: entetes[p.name])
    rapport = prefab_usage.scan_prefab_usage(tmp_path)
    # SameThing : cite par son nom ; OldThing : ni nom ni tag ne matche
    assert [p.name for p, _s in rapport.unused] == ["OldThing.epb"]
