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

"""Lieux des marchands : normalisation des cles, rapprochement, croisement
marchand -> prefab -> POI -> playfield, systeme/secteur, cache."""

import pytest

from core.codex_places import (build_places_index, cached_places, distance,
                               index_from_dict, index_to_dict, known_traders,
                               list_playfield_instances, match_trader,
                               pois_of_playfield, prefab_trader_keys,
                               trader_keys)

TRADERS = """{ Trader Name: QuantumSTAR
  Item1: "IronIngot, mf=1, 5"
}
{ Trader Name: PaxPurgatory
  Item1: "IronIngot, mf=1, 5"
}
{ Trader Name: AuntMarys
  Item1: "IronIngot, mf=1, 5"
}
{ Trader Name: CommoditiesDefaultGreyGoods
  Item1: "IronIngot, mf=1, 5"
}
{ Trader Name: Food
  Item1: "IronIngot, mf=1, 5"
}
"""

PLANET_A = """PlayfieldType: Terrain
POIs:
  Random:
    - GroupName: QuantumStation
      CountMinMax: [1]
    - GroupName: R2TradeTower
      CountMinMax: [1]
  Fixed:
    - Type: BA_Trader
      Name: PaxOutpost
      Prefab: PaxStation
      CountMinMax: [1]
"""

SPACE_B = """PlayfieldType: Space
POIs:
  - Type: BA_Alien
    GroupName: MaryStation
    CountMinMax: [1]
"""

SECTORS = """SolarSystems:
  - Name: Alpha
    Coordinates: [0, 0, 0]
    Sectors:
      - Coordinates: [2, 0, 0]
        Playfields:
          - ['0,0,0', PlanetAInst, PlanetA, '', '', '', '']
      - Coordinates: [3, 1, 0]
        Playfields:
          - ['0,0,0', SpaceBInst, SpaceB, '', '', '', '']
"""


def _epb(path, text: str):
    """Fichier .epb factice : chaines en clair puis frontiere zip. Suffit aux
    lecteurs de noms (le GroupName de l'en-tete, lui, est teste ailleurs)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00" * 16 + text.encode("ascii") + b"\x00"
                     + b"PK\x03\x04" + b"\x00" * 32)
    return path


@pytest.fixture
def scenario(tmp_path):
    root = tmp_path / "scenario"
    root.mkdir()
    cfg = root / "Content" / "Configuration"
    cfg.mkdir(parents=True)
    (cfg / "TraderNPCConfig.ecf").write_text(TRADERS, encoding="utf-8")
    (root / "Sectors").mkdir()
    (root / "Sectors" / "Sectors.yaml").write_text(SECTORS, encoding="utf-8")
    planet = root / "Playfields" / "PlanetA"
    planet.mkdir(parents=True)
    (planet / "playfield_static.yaml").write_text(PLANET_A, encoding="utf-8")
    space = root / "Playfields" / "SpaceB"
    space.mkdir(parents=True)
    (space / "space_dynamic.yaml").write_text(SPACE_B, encoding="utf-8")
    prefabs = root / "Prefabs"
    _epb(prefabs / "QuantumStation.epb", "cpgTrading Traders quantumstar")
    _epb(prefabs / "PaxStation.epb", "Traders PaxPuragtory")
    _epb(prefabs / "MaryStation.epb", "Traders AuntMarys(hidden)")
    _epb(prefabs / "Noise.epb", "Food Processor 1")
    return root


def _names():
    return ["QuantumSTAR", "PaxPurgatory", "AuntMarys",
            "CommoditiesDefaultGreyGoods", "Food"]


# ------------------------------------------------------------ normalisation

def test_trader_keys_handles_suffixes_and_aliases():
    assert "interweap" in trader_keys("interweap(hidden)")
    assert "commoditiesdefaultgrey" in trader_keys("commdefaultgrey")
    assert trader_keys("Traders QuantumSTAR") == {"tradersquantumstar"}


def test_distance_and_matching_levels():
    # faute reelle du prefab : « PaxPuragtory » (a et g intervertis) = 2
    assert distance("paxpuragtory", "paxpurgatory") == 2
    known = known_traders(_names())
    assert match_trader("quantumstar", known) == ("QuantumSTAR", "exact")
    assert match_trader("commoditiesdefaultgrey", known)[1] == "prefixe"
    assert match_trader("paxpuragtory", known) == ("PaxPurgatory", "proche")
    # « goods » est a distance 2 de « food » : refuse (noms trop courts)
    assert match_trader("goods", known) is None


# ------------------------------------------------------------ croisement

def test_prefab_trader_keys_reads_only_the_header(tmp_path):
    inside = _epb(tmp_path / "in.epb", "Traders QuantumSTAR")
    assert prefab_trader_keys(inside) == ["QuantumSTAR"]
    after = tmp_path / "after.epb"
    after.write_bytes(b"\x00" * 8 + b"PK\x03\x04" + b"Traders QuantumSTAR")
    assert prefab_trader_keys(after) == []        # apres la frontiere zip


def test_build_index_links_trader_to_playfield_and_poi(scenario):
    index = build_places_index(scenario, _names())
    quantum = index.places_for("QuantumSTAR")
    assert [(p.playfield, p.poi, p.confidence) for p in quantum] == \
        [("PlanetA", "QuantumStation", "exact")]
    pax = index.places_for("PaxPurgatory")
    assert [(p.playfield, p.poi, p.confidence) for p in pax] == \
        [("PlanetA", "PaxOutpost", "proche")]
    mary = index.places_for("AuntMarys")
    assert [(p.playfield, p.poi) for p in mary] == [("SpaceB", "MaryStation")]
    assert "Food" not in index.by_trader           # bruit « Food Processor »


def test_index_carries_instances_and_candidates(scenario):
    index = build_places_index(scenario, _names())
    place = index.places_for("QuantumSTAR")[0]
    assert place.instances == (("Alpha", (2, 0, 0), "PlanetAInst"),)
    assert ("PlanetA", "R2TradeTower") in index.candidates


def test_instances_and_pois_of_playfield(scenario):
    instances = list_playfield_instances(scenario)
    assert [(i.system, i.sector, i.instance, i.type_name) for i in instances] == [
        ("Alpha", (2, 0, 0), "PlanetAInst", "PlanetA"),
        ("Alpha", (3, 1, 0), "SpaceBInst", "SpaceB")]
    assert pois_of_playfield(scenario, "PlanetA") == [
        "PaxOutpost", "QuantumStation", "R2TradeTower"]
    assert pois_of_playfield(scenario, "SpaceB") == ["MaryStation"]


# ------------------------------------------------------------------ cache

def test_cache_is_written_and_invalidated(scenario):
    first = build_places_index(scenario, _names())
    cached = cached_places(scenario, _names())
    assert cached is not None
    assert cached.stamp == first.stamp
    assert [p.poi for p in cached.places_for("QuantumSTAR")] == ["QuantumStation"]
    _epb(scenario / "Prefabs" / "Extra.epb", "Traders Food")   # dossier modifie
    assert cached_places(scenario, _names()) is None


def test_index_roundtrip(scenario):
    index = build_places_index(scenario, _names())
    clone = index_from_dict(index_to_dict(index))
    assert clone.stamp == index.stamp
    assert clone.places_for("QuantumSTAR")[0].instances == \
        index.places_for("QuantumSTAR")[0].instances
    assert clone.by_type["SpaceB"][0].instance == "SpaceBInst"
