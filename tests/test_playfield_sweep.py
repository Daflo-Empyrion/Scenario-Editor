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

"""Balayage par planete (core/playfield_sweep.py) : prefabs cites et blocs
manquants de leurs tables IdMapping."""
from pathlib import Path

from core import playfield_sweep

BLOCKS = ("{ Block Id: 1, Name: KnownBlock\n"
          "  Material: Device\n"
          "}\n")


def _scenario(tmp_path: Path, prefab_blocks: dict, refs: str) -> Path:
    conf = tmp_path / "Content" / "Configuration"
    conf.mkdir(parents=True)
    (conf / "BlocksConfig.ecf").write_text(BLOCKS, encoding="utf-8")
    prefabs = tmp_path / "Prefabs"
    prefabs.mkdir()
    (prefabs / "TestPOI.epb").write_bytes(b"fake")
    pf = tmp_path / "Playfields" / "PlanetA"
    pf.mkdir(parents=True)
    (pf / "playfield_static.yaml").write_text(refs, encoding="utf-8")
    return tmp_path


def test_cited_prefab_with_missing_block_is_reported(tmp_path, monkeypatch):
    """Le prefab cite par la planete embarque un bloc absent de la config :
    le jeu l'ignore au spawn, et le boot dedie ne le voit pas (aucun
    playfield n'est instancie)."""
    root = _scenario(tmp_path, {"TestPOI.epb": {1: "KnownBlock", 2: "Ghost"}},
                     "POIs:\n  Random:\n"
                     "    - GroupName: Something\n"
                     "      Prefab: TestPOI\n")
    monkeypatch.setattr(playfield_sweep, "read_id_mapping",
                        lambda p: {1: "KnownBlock", 2: "Ghost"})
    issues = playfield_sweep.sweep_playfields(root)
    assert len(issues) == 1
    assert "Ghost" in issues[0].message
    assert issues[0].path.startswith("Playfields/PlanetA/")


def test_resolved_prefab_reports_nothing(tmp_path, monkeypatch):
    root = _scenario(tmp_path, {"TestPOI.epb": {1: "KnownBlock"}},
                     "POIs:\n  Random:\n"
                     "    - GroupName: Something\n"
                     "      Prefab: TestPOI\n")
    monkeypatch.setattr(playfield_sweep, "read_id_mapping",
                        lambda p: {1: "KnownBlock"})
    assert playfield_sweep.sweep_playfields(root) == []
