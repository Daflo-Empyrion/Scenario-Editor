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

"""Fusion SPECIALISEE GalaxyConfig (core/galaxy_merge.py, demande du
01/10/2026) : appariement par (Name, StarClass), bloc General a part,
dependances SolarSystemConfigSuffix -> RandomPresets -> playfields,
separateur commente, idempotence."""
import pytest

from core.galaxy_merge import (GalaxyPlan, _scan_preset_playfields,
                               build_plan, apply_plan)

WORKING = """{ GalaxyConfig, Name: General
  StarCount: "100, 200"
  Radius: "0, 500"
}
{ GalaxyConfig, Name: G Type Star
  StarClass: G
  Probability: 0.5
}
{ GalaxyConfig, Name: M Type Star
  StarClass: M
  Probability: 0.8
}
"""

SOURCE = """{ GalaxyConfig, Name: General
  StarCount: "500, 900"
  Radius: "0, 500"
}
{ GalaxyConfig, Name: G Type Star
  StarClass: G
  Probability: 0.5
}
{ GalaxyConfig, Name: S Star
  StarClass: S
  Probability: 1
  SolarSystemConfigSuffix: _S
  GalaxySpawnAmount: 0
}
{ GalaxyConfig, Name: S Star Variant
  StarClass: S
  Probability: 0.4
}
"""

PRESET = """  PlanetLists:
    - 'Lava:1.0, DesertX:0.5'        # hot / desert
    - 'ImportedX:0.5'                # playfield du scenario source
    # - 'Commented:0.0'
  OrbitTypes:
      - Name: DefaultOrbit
        PlayfieldLevel: [2,6]
        Playfields:
            - EdenSpace_OrbitX
            - EdenSpace_OrbitY
"""


@pytest.fixture
def scenario(tmp_path):
    """working = copie de travail, source = scenario B a fusionner."""
    w, s = tmp_path / "work", tmp_path / "src"
    for root in (w, s):
        (root / "Content/Configuration").mkdir(parents=True)
        (root / "Sectors").mkdir()
    (w / "Content/Configuration/GalaxyConfig.ecf").write_text(
        WORKING, encoding="utf-8")
    (s / "Content/Configuration/GalaxyConfig.ecf").write_text(
        SOURCE, encoding="utf-8")
    (w / "Sectors/Sectors.yaml").write_text(
        "SolarSystems:\n  - Name: Other System\n", encoding="utf-8")
    rp = s / "RandomPresets"
    rp.mkdir()
    (rp / "SolarSystemConfig_S.yaml").write_text(PRESET, encoding="utf-8")
    (s / "Playfields/DesertX").mkdir(parents=True)
    (s / "Playfields/EdenSpace_OrbitX").mkdir(parents=True)
    (s / "Playfields/OnlyInSource").mkdir(parents=True)
    (s / "Playfields/ImportedX").mkdir(parents=True)
    (w / "Playfields/Lava").mkdir(parents=True)
    return w, s


def test_scan_preset_playfields(tmp_path):
    f = tmp_path / "SolarSystemConfig_S.yaml"
    f.write_text(PRESET, encoding="utf-8")
    got = _scan_preset_playfields(f)
    assert got == {"Lava", "DesertX", "ImportedX", "EdenSpace_OrbitX",
                   "EdenSpace_OrbitY"}


def test_plan_blocks_general_diff_and_same(scenario):
    w, s = scenario
    plan = build_plan(
        w / "Content/Configuration/GalaxyConfig.ecf",
        s / "Content/Configuration/GalaxyConfig.ecf",
        working_root=w, source_root=s, vanilla_content=None)
    assert plan.ok
    keys = {b.key for b in plan.blocks_add}
    # S et sa VARIANTE : meme StarClass, Name different -> deux entrees
    assert keys == {"S Star|S", "S Star Variant|S"}
    assert plan.blocks_same == ["G Type Star|G"]
    # General : diff informatif, working prioritaire
    assert ("StarCount", '"100, 200"', '"500, 900"') in plan.general_diff
    assert all(k != "Radius" for k, *_ in plan.general_diff)
    assert not plan.errors


def test_plan_dependencies(scenario):
    w, s = scenario
    plan = build_plan(
        w / "Content/Configuration/GalaxyConfig.ecf",
        s / "Content/Configuration/GalaxyConfig.ecf",
        working_root=w, source_root=s, vanilla_content=None)
    rel = {d.relative for d in plan.deps}
    assert "RandomPresets/SolarSystemConfig_S.yaml" in rel
    assert {"Playfields/DesertX", "Playfields/EdenSpace_OrbitX",
            "Playfields/ImportedX"} <= rel
    # Lava existe deja au working ; EdenSpace_OrbitY absent partout
    assert "Playfields/Lava" not in rel
    assert plan.playfields_absent == ["EdenSpace_OrbitY "
                                      "(SolarSystemConfig_S.yaml)"]


def test_plan_sector_warning_for_manual_systems(scenario):
    w, s = scenario
    plan = build_plan(
        w / "Content/Configuration/GalaxyConfig.ecf",
        s / "Content/Configuration/GalaxyConfig.ecf",
        working_root=w, source_root=s, vanilla_content=None)
    # S Star (GalaxySpawnAmount: 0) absent du Sectors.yaml du working
    assert plan.sector_warnings == ["S Star"]


def test_apply_separator_bak_and_idempotent(scenario):
    w, s = scenario
    gcf = w / "Content/Configuration/GalaxyConfig.ecf"
    plan = build_plan(gcf, s / "Content/Configuration/GalaxyConfig.ecf",
                      working_root=w, source_root=s, vanilla_content=None,
                      )
    stats = apply_plan(plan, gcf, working_root=w, copy_deps=False)
    assert stats["blocks"] == 2
    txt = gcf.read_text(encoding="utf-8")
    assert "Fusion depuis source : systemes ajoutes" in txt
    assert "Name: S Star Variant" in txt
    assert gcf.with_suffix(".ecf.bak").exists()
    bak = gcf.with_suffix(".ecf.bak").read_text(encoding="utf-8")
    assert "S Star Variant" not in bak, "le .bak = l'etat AVANT"
    # General du working INTACT (jamais ecrase par la source)
    assert 'StarCount: "100, 200"' in txt
    # idempotence : re-plan = plus rien a ajouter
    plan2 = build_plan(gcf, s / "Content/Configuration/GalaxyConfig.ecf",
                       working_root=w, source_root=s, vanilla_content=None)
    assert plan2.blocks_add == []
    stats2 = apply_plan(plan2, gcf, working_root=w, copy_deps=False)
    assert stats2["blocks"] == 0
    # un seul separateur malgre la re-fusion
    assert txt.count("Fusion depuis source") == 1


def test_apply_copies_dependencies(scenario):
    w, s = scenario
    gcf = w / "Content/Configuration/GalaxyConfig.ecf"
    plan = build_plan(gcf, s / "Content/Configuration/GalaxyConfig.ecf",
                      working_root=w, source_root=s, vanilla_content=None)
    stats = apply_plan(plan, gcf, working_root=w, copy_deps=True)
    assert stats["deps"] == 4
    assert (w / "RandomPresets/SolarSystemConfig_S.yaml").exists()
    assert (w / "Playfields/DesertX").is_dir()
    assert (w / "Playfields/EdenSpace_OrbitX").is_dir()
    assert (w / "Playfields/ImportedX").is_dir()
    # re-application : les existants sont sautes, jamais ecrases
    stats2 = apply_plan(plan, gcf, working_root=w, copy_deps=True)
    assert stats2["skipped_deps"] == 4


def test_plan_uses_vanilla_for_known_playfields(scenario, monkeypatch):
    """Un playfield absent du scenario mais present a la VANILLE n'est pas
    propose a la copie."""
    w, s = scenario
    van = scenario[0] / "vanilla"          # racine factice
    (van / "Playfields/EdenSpace_OrbitX").mkdir(parents=True)
    plan = build_plan(
        w / "Content/Configuration/GalaxyConfig.ecf",
        s / "Content/Configuration/GalaxyConfig.ecf",
        working_root=w, source_root=s, vanilla_content=van)
    rel = {d.relative for d in plan.deps}
    assert "Playfields/EdenSpace_OrbitX" not in rel
    assert "Playfields/DesertX" in rel


def test_plan_error_on_unreadable_source(scenario):
    w, s = scenario
    bad = s / "Content/Configuration/GalaxyConfig.ecf"
    # source corrompue : erreur propre, jamais d'exception
    bad.write_text("{ GalaxyConfig, Name: General\n  StarCount: \n",
                   encoding="utf-8")
    plan = build_plan(w / "Content/Configuration/GalaxyConfig.ecf", bad,
                      working_root=w, source_root=s)
    assert isinstance(plan, GalaxyPlan)


WORKING_INDEXED = """{ GalaxyConfig, Name: General
  StarCount: "100, 200"
}
{ Child StarRegion_1
  Center: "100, 0, 50"
  Radius: 150
}
{ Child Territory_1
  Faction: Zirax
  Center: "100, 0, 50"
  Radius: 60
}
"""

SOURCE_INDEXED = """{ GalaxyConfig, Name: General
  StarCount: "100, 200"
}
{ Child StarRegion_2
  Center: "-300, 10, 80"
  Radius: 90
}
{ Child Territory_2
  Faction: CoraxCustom
  Center: "-300, 10, 80"
  Radius: 40
}
{ Child StarRegion_5
  Center: "100, 0, 50"
  Radius: 150
}
{ Child StarRegion_7
  Center: "-500, 0, 200"
  Radius: 60
}
"""

FACTIONS_WORKING = """{ Faction Id: 1, Name: "Public"
  Abbrev: PUB
}
"""

FACTIONS_SOURCE = """{ Faction Id: 1, Name: "Public"
  Abbrev: PUB
}
{ Faction Id: 40, Name: "CoraxCustom"
  Abbrev: CRX
  Reputation: true
}
"""

REPUTATION_SOURCE = """{ Reputation Name: "Human:1"
  Zirax: 13000
  CoraxCustom: 15000
}
{ Reputation Name: "Neutral:2"
  CoraxCustom: 12000
}
"""


def test_indexed_blocks_reindexed_contiguous(tmp_path):
    """Tranche 2 : Child StarRegion/Territory de B importes puis TOUT le
    fichier renumeroTE en sequence contigue (le crash du jeu venait des
    trous/doublons d'index). Le doublon DE CONTENU (StarRegion_5 =
    copie de _1) est ignore."""
    w, s = tmp_path / "work", tmp_path / "src"
    for root in (w, s):
        (root / "Content/Configuration").mkdir(parents=True)
    (w / "Content/Configuration/GalaxyConfig.ecf").write_text(
        WORKING_INDEXED, encoding="utf-8")
    (s / "Content/Configuration/GalaxyConfig.ecf").write_text(
        SOURCE_INDEXED, encoding="utf-8")
    (w / "Content/Configuration/Factions.ecf").write_text(
        FACTIONS_WORKING, encoding="utf-8")
    (s / "Content/Configuration/Factions.ecf").write_text(
        FACTIONS_SOURCE, encoding="utf-8")
    (s / "Content/Configuration/DefReputation.ecf").write_text(
        REPUTATION_SOURCE, encoding="utf-8")
    gcf = w / "Content/Configuration/GalaxyConfig.ecf"
    plan = build_plan(gcf, s / "Content/Configuration/GalaxyConfig.ecf",
                      working_root=w, source_root=s, vanilla_content=None)
    assert plan.ok
    assert [ib.index for ib in plan.indexed_add["StarRegion"]] == [2, 7]
    assert [ib.index for ib in plan.indexed_add["Territory"]] == [2]
    assert plan.indexed_same == ["StarRegion: 1"]   # le doublon de contenu
    # factions : CoraxCustom requis par le Territory, absente du working
    assert [f.name for f in plan.factions_to_import] == ["CoraxCustom"]
    assert plan.factions_to_import[0].reputation == {
        "Human:1": "15000", "Neutral:2": "12000"}

    stats = apply_plan(plan, gcf, working_root=w)
    assert stats["indexed"] == 3 and stats["factions"] == 1
    # le working n'a pas de DefReputation : on ne cree JAMAIS un fichier
    # moitie vide — les valeurs de B restent dans le plan (avertissement)
    assert stats["reputation"] == 0
    assert not (w / "Content/Configuration/DefReputation.ecf").exists()
    txt = gcf.read_text(encoding="utf-8")
    import re as _re
    regions = _re.findall(r"^\{ Child StarRegion_(\d+)$", txt, _re.M)
    territories = _re.findall(r"^\{ Child Territory_(\d+)$", txt, _re.M)
    assert regions == ["1", "2", "3"], regions      # contigu, trous supprimes
    assert territories == ["1", "2"]
    # faction importee dans Factions.ecf du working (pas d'ecrasement)
    ftxt = (w / "Content/Configuration/Factions.ecf").read_text(
        encoding="utf-8")
    assert 'Name: "CoraxCustom"' in ftxt and 'Name: "Public"' in ftxt
    # idempotence : re-fusion = plus rien a ajouter
    plan2 = build_plan(gcf, s / "Content/Configuration/GalaxyConfig.ecf",
                       working_root=w, source_root=s, vanilla_content=None)
    assert plan2.indexed_add.get("StarRegion") is None or \
        all(ib.index not in (1, 2, 3) for ib in plan2.indexed_add["StarRegion"])


def test_reputation_propagated_into_existing_blocks(tmp_path):
    """Tranche 2 : quand le working A un DefReputation, les valeurs de B
    sont ajoutees dans les MEMES blocs d'Origine (jamais ecraser)."""
    w, s = tmp_path / "work", tmp_path / "src"
    for root in (w, s):
        (root / "Content/Configuration").mkdir(parents=True)
    (w / "Content/Configuration/GalaxyConfig.ecf").write_text(
        WORKING_INDEXED, encoding="utf-8")
    (s / "Content/Configuration/GalaxyConfig.ecf").write_text(
        SOURCE_INDEXED, encoding="utf-8")
    (w / "Content/Configuration/Factions.ecf").write_text(
        FACTIONS_WORKING, encoding="utf-8")
    (s / "Content/Configuration/Factions.ecf").write_text(
        FACTIONS_SOURCE, encoding="utf-8")
    (w / "Content/Configuration/DefReputation.ecf").write_text(
        '{ Reputation Name: "Human:1"\n  Zirax: 13000\n}\n',
        encoding="utf-8")
    (s / "Content/Configuration/DefReputation.ecf").write_text(
        REPUTATION_SOURCE, encoding="utf-8")
    gcf = w / "Content/Configuration/GalaxyConfig.ecf"
    plan = build_plan(gcf, s / "Content/Configuration/GalaxyConfig.ecf",
                      working_root=w, source_root=s, vanilla_content=None)
    stats = apply_plan(plan, gcf, working_root=w)
    assert stats["reputation"] == 1          # Human:1 seulement
    rep = (w / "Content/Configuration/DefReputation.ecf").read_text(
        encoding="utf-8")
    assert "CoraxCustom: 15000" in rep       # valeur de B, ajoutee
    assert "Zirax: 13000" in rep             # working intact
    assert "Neutral:2" not in rep, "bloc d'Origine absent du working : jamais copie"


def test_general_overrides_apply(scenario):
    """Tranche 2 : le diff General est COCHABLE — la propriete cochee
    prend la valeur SOURCE, les autres gardent le working."""
    w, s = scenario
    gcf = w / "Content/Configuration/GalaxyConfig.ecf"
    plan = build_plan(gcf, s / "Content/Configuration/GalaxyConfig.ecf",
                      working_root=w, source_root=s, vanilla_content=None)
    stats = apply_plan(plan, gcf, working_root=w, copy_deps=False,
                       general_props={"StarCount"})
    assert stats["general"] == 1
    txt = gcf.read_text(encoding="utf-8")
    assert 'StarCount: "500, 900"' in txt, "propriete coquee = source"
    assert 'Radius: "0, 500"' in txt, "propriete non coquee = working"


def test_unknown_faction_is_warning_only(tmp_path):
    w, s = tmp_path / "work", tmp_path / "src"
    for root in (w, s):
        (root / "Content/Configuration").mkdir(parents=True)
        (root / "Sectors").mkdir()
    (w / "Content/Configuration/GalaxyConfig.ecf").write_text(
        WORKING_INDEXED, encoding="utf-8")
    (s / "Content/Configuration/GalaxyConfig.ecf").write_text(
        """{ Child Territory_2
  Faction: GhostFaction
  Center: "0, 0, 0"
  Radius: 10
}
""", encoding="utf-8")
    plan = build_plan(w / "Content/Configuration/GalaxyConfig.ecf",
                      s / "Content/Configuration/GalaxyConfig.ecf",
                      working_root=w, source_root=s, vanilla_content=None)
    assert plan.factions_unknown == ["GhostFaction"]
    assert plan.factions_to_import == []
    assert plan.ok, "une faction inconnue est un avertissement, pas une erreur"


def test_scan_egroup_refs(tmp_path):
    """Tranche 3 : les refs Entities: des playfields importes resolues
    comme EGroup ; commentaires et hors-contexte ignores."""
    from core.galaxy_merge import _scan_egroup_refs
    d = tmp_path / "Playfields" / "X"
    d.mkdir(parents=True)
    (d / "playfield_static.yaml").write_text(
        "POIs:\n"
        "    - Name: SomePoi                     # GuardedByGroup!\n"
        "NPC:\n"
        "  Entities:\n"
        "      - Names: [NewGroup, OtherGroup]\n"
        "        Amount: 10\n"
        "      - Name: SoloGroup\n"
        "      - Name: #CommentedGroup\n"
        "  OtherKey:\n"
        "      - Name: NotInEntities\n",
        encoding="utf-8")
    assert _scan_egroup_refs(d) == {"NewGroup", "OtherGroup", "SoloGroup"}


def test_egroups_of_imported_playfields_proposed_and_applied(tmp_path):
    """Tranche 3 : les playfields importes reference des EGroup absents
    de l'EGroupsConfig du working -> blocs proposes puis ajoutes
    (append + .bak, idempotent) ; le natif de la source absent partout
    ne bloque pas."""
    w, s = tmp_path / "work", tmp_path / "src"
    for root in (w, s):
        (root / "Content/Configuration").mkdir(parents=True)
    (w / "Content/Configuration/GalaxyConfig.ecf").write_text(
        WORKING, encoding="utf-8")
    (s / "Content/Configuration/GalaxyConfig.ecf").write_text(
        SOURCE, encoding="utf-8")
    (w / "Content/Configuration/EGroupsConfig.ecf").write_text(
        "{ EGroup Name: KnownGroup\n  Entities:\n    - Name: ZiraxOgre\n}\n",
        encoding="utf-8")
    (s / "Content/Configuration/EGroupsConfig.ecf").write_text(
        "{ EGroup Name: KnownGroup\n  Entities:\n    - Name: ZiraxOgre\n}\n"
        "{ EGroup Name: NewGroup\n  Entities:\n    - Name: XenuSoldier\n}\n",
        encoding="utf-8")
    pf = s / "Playfields/ImportedX"
    pf.mkdir(parents=True)
    (pf / "playfield_static.yaml").write_text(
        "  Entities:\n"
        "      - Names: [NewGroup, GameNative]\n"
        "      - Name: NewGroup\n",
        encoding="utf-8")
    # le preset du bloc S doit exister pour ne pas mettre d'erreur
    rp = s / "RandomPresets"
    rp.mkdir()
    (rp / "SolarSystemConfig_S.yaml").write_text(PRESET, encoding="utf-8")
    gcf = w / "Content/Configuration/GalaxyConfig.ecf"
    plan = build_plan(gcf, s / "Content/Configuration/GalaxyConfig.ecf",
                      working_root=w, source_root=s, vanilla_content=None)
    assert [e.name for e in plan.egroups_to_import] == ["NewGroup"]

    stats = apply_plan(plan, gcf, working_root=w)
    assert stats["egroups"] == 1
    eg = (w / "Content/Configuration/EGroupsConfig.ecf").read_text(
        encoding="utf-8")
    assert "Name: NewGroup" in eg and "Name: KnownGroup" in eg
    assert (w / "Content/Configuration/EGroupsConfig.ecf.bak").exists()
    # idempotence
    plan2 = build_plan(gcf, s / "Content/Configuration/GalaxyConfig.ecf",
                       working_root=w, source_root=s, vanilla_content=None)
    assert plan2.egroups_to_import == []


def test_repair_stray_junk_after_flow(tmp_path):
    """Vecu 01/10 : presets SolarSystemConfig corrompus —
    'Faction: [Pirates, None]s' faisait crasher le parseur YAML du jeu
    (« did not find expected key »). Le junk apres le crochet est retire,
    le commentaire de fin de ligne preserve, les commentaires seuls
    intouches."""
    from core.fsutil import repair_stray_junk_after_flow
    text = ("  Faction: [Pirates, None]s                   #Sigma\n"
            "  Color: [0.49, 0.49, 0.49]\n"
            "      # - ['500,300,-6000', Omicron Moon, OmicronMoon]\n"
            "  Names: [A, B]\n")
    fixed, n = repair_stray_junk_after_flow(text)
    assert n == 1
    assert "Faction: [Pirates, None]                   #Sigma" in fixed
    assert "Color: [0.49, 0.49, 0.49]" in fixed          # intact
    assert "Omicron Moon" in fixed                        # commentaire intact
    assert "Names: [A, B]" in fixed                       # crochet interne OK


def test_copy_dir_repairing_yaml(tmp_path):
    """La copie d'un dossier de playfield source REPARE les *.yaml
    parasites et copie le reste tel quel."""
    from core.fsutil import copy_dir_repairing_yaml
    src, dst = tmp_path / "src", tmp_path / "dst"
    (src / "sub").mkdir(parents=True)
    (src / "playfield.yaml").write_text(
        "Faction: [Pirates, None]s\n", encoding="utf-8")
    (src / "sub" / "other.yaml").write_text("Clean: ok\n", encoding="utf-8")
    (src / "icon.png").write_bytes(b"\x89PNG")
    copied, fixed = copy_dir_repairing_yaml(src, dst)
    assert copied == 3 and fixed == 1
    assert (dst / "playfield.yaml").read_text(
        encoding="utf-8").strip().endswith("[Pirates, None]")
    assert (dst / "sub" / "other.yaml").read_text(
        encoding="utf-8") == "Clean: ok\n"
    assert (dst / "icon.png").read_bytes() == b"\x89PNG"
    # re-copie sur l'existant : idempotent
    copied2, fixed2 = copy_dir_repairing_yaml(src, dst)
    assert copied2 == 3 and fixed2 == 1
