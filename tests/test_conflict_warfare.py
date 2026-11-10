"""Tests de la pass de conflit de factions (core/conflict_warfare.py)."""
from core.conflict_warfare import _POOL_PREFABS, pass_faction_conflict

# Deux ancres natives déclarées (Zirax, Pirates) + le reste en pools : les
# deux chemins du roster sont couverts par tous les tests.
MINIMAL = (
    "PlayfieldType: Planet\n"
    "POIs:\n"
    "    Random:\n"
    "        - GroupName: R2XenuMain\n"
    "          Faction: Zirax\n"
    "        - GroupName: R2PirateMain\n"
    "          Faction: Pirates\n"
    "    FixedPlayerStart:\n"
    "        - Mode: Survival\n"
    "          Pos: [ -350, 0 ]\n"
    "DroneBaseSetup: \n"
    "    Random:\n"
    "        - GroupName: DroneBaseSetup\n"
    "          Difficulty: 6\n"
    "DroneSpawning:    \n"
    "    Random:\n"
    "        - DronesMinMax: [ 0, 0 ]\n"
    "          CenterX: -5000\n"
)

POIGROUPS_MINIMAL = (
    "---\n"
    "  PoiGroups:\n"
    "    - GroupName: ExistingGroup\n"
    "      Filters:\n"
    "          BlueprintFileNames: [ BA_Something ]\n"
)

ZIRAX_ONLY = MINIMAL.replace(
    "DroneSpawning:    \n",
    "    PlanetVessels:\n"
    "              - Name: R2PV_ZiraxCutter01\n"
    "                Faction: Zirax\n"
    "DroneSpawning:    \n",
)

# playfield sans DroneBaseSetup NI DroneSpawning (géantes gazeuses)
NO_DRONE_SECTIONS = (
    "PlayfieldType: Planet\n"
    "POIs:\n"
    "    Random:\n"
    "        - GroupName: EdenPOI\n"
    "          Faction: Neutral\n"
    "    FixedPlayerStart:\n"
    "        - Mode: Survival\n"
    "SpawnZones:\n"
    "    - Mode: Survival\n"
)


def _make_scenario(tmp_path, content=MINIMAL):
    sc = tmp_path / "S"
    (sc / "Playfields" / "Starter_Dread").mkdir(parents=True)
    (sc / "Prefabs").mkdir()
    (sc / "Playfields" / "Starter_Dread" / "playfield_static.yaml").write_text(content, encoding="utf-8")
    (sc / "Prefabs" / "_PoiGroupsConfig.yaml").write_text(POIGROUPS_MINIMAL, encoding="utf-8")
    for prefab in _POOL_PREFABS.values():          # validation des pools
        (sc / "Prefabs" / (prefab + ".epb")).write_bytes(b"")
    return sc


def test_conflict_apply_full(tmp_path):
    sc = _make_scenario(tmp_path)
    rep = pass_faction_conflict(sc, apply=True)
    # 21 pools + 12 POIs (10 entrées + 2 natives réécrites) + 5 vaisseaux
    # + 6 spawns + 1 DroneBaseSetup — roster de 8 factions (rotation)
    assert rep["edits"] == 44, rep
    assert rep["files"] == 2
    pf = (sc / "Playfields" / "Starter_Dread" / "playfield_static.yaml").read_text("utf-8")
    pg = (sc / "Prefabs" / "_PoiGroupsConfig.yaml").read_text("utf-8")
    # un pool par faction, natif ou pas
    assert "ConflictWarlordBases" in pg and "ConflictARCBases" in pg
    assert "ConflictKrielBases" in pg and "ConflictZiraxBases" in pg
    assert "IsImportant" not in pg
    # groupe natif quand le playfield le déclare, pool sinon
    assert "- GroupName: R2XenuMain" in pf          # Zirax : natif déclaré
    assert "- GroupName: R2PirateMain" in pf        # Pirates : natif déclaré
    assert "- GroupName: ConflictWarlordBases" in pf   # roster : Talon, pas de natif ici
    assert "- GroupName: ConflictUCHBases" in pf  # roster
    assert pf.index("- GroupName: R2XenuMain") < pf.index("    FixedPlayerStart:")
    assert "SpawnPOIAvoidDistance: 2000" in pf  # hostiles loin du START
    assert "SpawnPOIAvoidDistance: 1200" in pf  # alliés plus proches
    # vaisseaux IA, ancrés sur le groupe retenu pour leur faction
    assert "- Name: ROPV_WarlordPhoenix" in pf
    assert "- Name: ROPV_WarlordPhoenix" in pf
    assert "CV_UCH001Hyperion" not in pf
    assert "POINameAsPositionRef: [R2XenuMain]" in pf        # Zirax : natif
    assert "POINameAsPositionRef: [ConflictWarlordBases]" in pf   # Talon : pool
    assert "Faction: UCH" in pf   # faction du roster (rotation)
    assert "DronesMinMax: [ 0, 0 ]" not in pf
    assert "ExistingGroup" in pg
    rep2 = pass_faction_conflict(sc, apply=True)
    assert rep2["edits"] == 0
    assert rep2["files"] == 0


def test_conflict_incremental_on_real_like_file(tmp_path):
    # fichier ayant déjà la base Zirax appliquée : seuls pois + 11 vaisseaux
    # + 7 spawns restent à ajouter (idempotence par élément)
    sc = _make_scenario(tmp_path, ZIRAX_ONLY)
    rep = pass_faction_conflict(sc, apply=True)
    assert rep["edits"] == 43, rep
    pf = (sc / "Playfields" / "Starter_Dread" / "playfield_static.yaml").read_text("utf-8")
    assert pf.count("- Name: R2PV_ZiraxCutter01") == 1
    assert "- Name: ROPV_WarlordPhoenix" in pf


def test_spawn_drops_named_entries():
    """RE2 ne gère pas Name:/Faction: dans DroneSpawning (vérifié : 173
    playfields n'utilisent que la forme générique) : nos anciennes entrées
    par faction doivent être purgées, remplacées par les génériques."""
    from core.conflict_warfare import _ensure_spawn_entries, _spawn_entries
    t = (
        "DroneSpawning:    \n"
        "    Random:\n"
        "        - DronesMinMax: [ 0, 0 ]\n"
        "          CenterX: -5000\n"
        "        - Name: DroneSmallFast01Minigun\n"
        "          DronesMinMax: [2, 4]\n"
        "          Faction: Warlord\n"
        "          POINameAsPositionRef: ConflictWarlordBases\n"
        "          Radius: 3000\n"
    )
    t2, k = _ensure_spawn_entries(t, _spawn_entries())
    assert "[ 0, 0 ]" not in t2                      # template désactivé retiré
    assert "- Name:" not in t2                       # entrée par faction purgée
    assert "Faction: Warlord" not in t2
    assert t2.count("DronesMinMax: [ 6, 10 ]") == 2  # patrouilles génériques
    assert "CenterX: -2500" in t2


def test_conflict_repairs_stale_entries(tmp_path):
    # entrée préexistante sans IsImportant -> remplacée (auto-réparation)
    sc = _make_scenario(tmp_path)
    rep1 = pass_faction_conflict(sc, apply=True)
    assert rep1["edits"] == 44
    pf_path = sc / "Playfields" / "Starter_Dread" / "playfield_static.yaml"
    txt = pf_path.read_text("utf-8")
    # simule une entrée périmée (CountMinMax modifié) : réécrit l'entrée Zirax
    stale = (
        "        - GroupName: R2XenuMain\n"
        "          Faction: Zirax\n"
        "          CountMinMax: [ 2, 2 ]\n"
        "          SpawnPOIAvoid: [START]\n"
        "          SpawnPOIAvoidDistance: 4000\n"
        "          Properties:\n"
        "            - Key: RegenAfter\n"
        "              Value: 720\n"
    )
    import re as _re
    txt2 = _re.sub(
        r"(?ms)^ {8}- GroupName: R2XenuMain\n(?: {10,}[^\n]*\n)+", stale, txt)
    pf_path.write_text(txt2, encoding="utf-8", newline="")
    rep2 = pass_faction_conflict(sc, apply=True)
    assert rep2["edits"] == 2, rep2  # 1 retrait + 1 réinsertion
    txt3 = pf_path.read_text("utf-8")
    assert txt3.count("- GroupName: R2XenuMain") == 1
    assert "CountMinMax: [ 2, 2 ]" not in txt3.split("DroneBaseSetup")[0]
    assert "DroneProb: 1.0" in txt3
    # chaque base est reliee a un stock de drones par faction
    assert "DroneBaseSetup: DroneBaseSetup" in txt3
    # DroneSetupID interdit dans les entrees POI (casse le placement)
    assert "DroneSetupID" not in txt3.split("DroneBaseSetup")[0]
    # mais present dans le nouveau schema du DroneBaseSetup
    assert "DroneBases:" in txt3 and "DroneSetupID: DroneBaseSetup" in txt3


def test_remove_pois_and_vessel_anchor_fix():
    from core.conflict_warfare import _remove_pois, _ensure_vessels
    t = (
        "        - GroupName: ConflictKrielBases\n"
        "          Faction: Kriel\n"
        "          SpawnPOIAvoidDistance: 4000\n"
        "        - GroupName: AlienPOIBases\n"
        "          Faction: Alien\n"
        "DroneBaseSetup:\n"
        "    PlanetVessels:\n"
        "              - Name: ROPV_KrielAccipiter\n"
        "                POINameAsPositionRef: [ConflictKrielBases]\n"
    )
    t2, k = _remove_pois(t, ("ConflictKrielBases",))
    assert k == 1
    assert "ConflictKrielBases" not in t2.split("PlanetVessels")[0]
    assert "- GroupName: AlienPOIBases" in t2  # l'entrée voisine intacte
    # l'ancre d'un vaisseau existant suit le groupe retenu pour sa faction
    item = ("              - Name: ROPV_KrielAccipiter\n"
            "                Faction: Kriel\n"
            "                RangePatrolTask:\n"
            "                  POINameAsPositionRef: [KrielMain]\n")
    t3, ka = _ensure_vessels(t2, [item])
    assert ka == 1
    assert "POINameAsPositionRef: [KrielMain]" in t3
    assert "POINameAsPositionRef: [ConflictKrielBases]" not in t3
    t4, kb = _ensure_vessels(t3, [item])          # idempotent
    assert kb == 0 and t4 == t3


def test_conflict_preserves_crlf(tmp_path):
    sc = _make_scenario(tmp_path, MINIMAL.replace("\n", "\r\n"))
    pass_faction_conflict(sc, apply=True)
    raw = (sc / "Playfields" / "Starter_Dread" / "playfield_static.yaml").read_bytes()
    assert raw.count(b"\r\n") > 10
    assert raw.count(b"\n") == raw.count(b"\r\n")


def test_conflict_skip_when_no_drone_spawning(tmp_path):
    sc = _make_scenario(tmp_path, MINIMAL.rsplit("DroneSpawning", 1)[0])
    rep = pass_faction_conflict(sc, apply=True)
    # patrouilleurs ajoutés MÊME sans section DroneSpawning.
    assert rep["edits"] == 38


def test_multi_declarations_are_preserved(tmp_path):
    """Un même GroupName déclaré plusieurs fois avec des Biomes différents
    est du design vanilla (RuinsLogisticsAuxT1 x8, CrashedShipStarter x3) :
    le pass ne doit JAMAIS fusionner ces déclarations."""
    dup = (
        "        - GroupName: R2CrashedShipStarter\n"
        "          Faction: None\n"
        "          Biome: [ DeepWater, Water ]\n"
        "          CountMinMax: [5, 7]\n"
        "        - GroupName: R2CrashedShipStarter\n"
        "          Faction: None\n"
        "          BiomesExcluded: [ Shore ]\n"
        "          CountMinMax: [5, 7]\n"
    )
    sc = _make_scenario(tmp_path, MINIMAL.replace("    FixedPlayerStart:", dup + "    FixedPlayerStart:"))
    pass_faction_conflict(sc, apply=True)
    txt = (sc / "Playfields" / "Starter_Dread" / "playfield_static.yaml").read_text("utf-8")
    assert txt.count("- GroupName: R2CrashedShipStarter") == 2
    assert "Biome: [ DeepWater, Water ]" in txt
    assert "BiomesExcluded: [ Shore ]" in txt


SCALABLE = (
    "        - GroupName: Eden_RuinsAux\n"
    "          Faction: Civilian\n"
    "          CountMinMax: [ 10, 20 ]\n"
    "        - GroupName: Eden_RuinsAux\n"
    "          Faction: Civilian\n"
    "          BiomesExcluded: [ Shore ]\n"
    "          CountMinMax: [ 10, 20 ]\n"
)


def test_scale_pois_keeps_bases_and_multi_declarations(tmp_path):
    """La réduction de densité ne touche ni les bases de faction ([1,1])
    ni les déclarations multiples par biome."""
    sc = _make_scenario(tmp_path, MINIMAL.replace(
        "    FixedPlayerStart:", SCALABLE + "    FixedPlayerStart:"))
    pass_faction_conflict(sc, apply=True)
    from core.conflict_warfare import pass_scale_pois
    rep = pass_scale_pois(sc, 0.5, apply=True)
    assert rep["edits"] == 2, rep
    txt = (sc / "Playfields" / "Starter_Dread" / "playfield_static.yaml").read_text("utf-8")
    assert txt.count("- GroupName: Eden_RuinsAux") == 2   # multi-déclaration préservée
    assert txt.count("CountMinMax: [ 5, 10 ]") == 2       # réduites
    i = txt.index("- GroupName: Conflict")
    assert "CountMinMax: [ 1, 1 ]" in txt[i:i + 400]      # base intacte




def test_drone_targets_extended(tmp_path):
    """Les drones doivent cibler NPCFighter/EnemyDrone (sinon aucun combat
    drone vs drone) — sans casser l'idempotence ni toucher aux alias Ref."""
    from core.conflict_warfare import _DRONE_TARGETS, _ensure_drone_targets
    ecf = (
        "{ +Entity Name: DroneSmallFast01Rocket\n"
        "  Mesh: Enemies/Drones/EnemyDroneRedPrefab\n"
        "  # AITask-1: DroneFindTargetIfHurt\n"
        "  HandItem: rocketlauncherDroneSmall\n"
        "}\n"
        "{ Entity Name: DroneSmallAttackBase, Ref: DroneSmallFast01Rocket\n"
        "}\n"
    )
    t2, n = _ensure_drone_targets(ecf)
    assert n == 1
    # cible = le jeu de jetons courant (bisect : voir DRONE_EXTRA_TARGETS)
    assert 'AITarget-1: DroneDetection, param1: "' + _DRONE_TARGETS in t2
    # 2e passage : idempotent
    t3, n2 = _ensure_drone_targets(t2)
    assert n2 == 0 and t3 == t2


def test_hostile_reputation_added(tmp_path):
    """Une faction hostile absente de Human:1 tombe sur le défaut moteur et
    ses drones ignorent le joueur : le pass doit ajouter une entrée à 0."""
    from core.conflict_warfare import pass_hostile_reputation
    sc = tmp_path / "S"
    (sc / "Content" / "Configuration").mkdir(parents=True)
    (sc / "Content" / "Configuration" / "DefReputation.ecf").write_text(
        '{ Reputation Name: "Human:1"\n  Zirax: 0\n  Polaris: 15000\n}\n',
        encoding="utf-8")
    rep = pass_hostile_reputation(sc, apply=True)
    assert rep["edits"] == 10, rep  # fixture minimale : 10 factions hostiles absentes
    txt = (sc / "Content" / "Configuration" / "DefReputation.ecf").read_text("utf-8")
    assert "TheLegacy: 0" in txt and "Kriel: 0" in txt
    assert "Polaris: 15000" in txt          # valeurs existantes intactes
    assert pass_hostile_reputation(sc, apply=True)["edits"] == 0  # idempotent


def test_npc_aliases_added(tmp_path):
    """NPC référencés par des spawners mais absents d'EClassConfig : sans
    alias, le jeu logue 'Spawner NPC X not found' et le save du playfield
    lève une exception."""
    from core.conflict_warfare import _ensure_npc_aliases
    ecf = "{ +Entity Name: Mechanoid, Ref: AlienTemplateBAI\n}\n"
    t2, n = _ensure_npc_aliases(ecf)
    assert n == 2
    assert "Entity Name: MechanoidMinigun, Ref: Mechanoid" in t2
    assert "Entity Name: MechanoidFlak, Ref: Mechanoid" in t2
    assert _ensure_npc_aliases(t2)[1] == 0  # idempotent


def test_drone_setup_created_without_truncating_spawnzones(tmp_path):
    """Géantes gazeuses : ni DroneBaseSetup ni DroneSpawning. La section est
    créée et SpawnZones/CreatureSpawning survivent (avant : le bloc allait
    jusqu'à EOF et les supprimait)."""
    sc = _make_scenario(tmp_path, NO_DRONE_SECTIONS + "CreatureSpawning:\n    - Bird\n")
    rep = pass_faction_conflict(sc, apply=True)
    assert rep["edits"] > 0, rep
    pf = (sc / "Playfields" / "Starter_Dread" / "playfield_static.yaml").read_text("utf-8")
    assert "DroneBaseSetup:" in pf
    assert "SpawnZones:" in pf and "CreatureSpawning:" in pf
    assert "    PlanetVessels:" in pf            # patrouilleurs sans DroneSpawning
    assert "- Name: ROPV_WarlordPhoenix" in pf


def test_missing_pool_prefab_is_reported(tmp_path):
    """Un prefab de pool absent => la passe ne touche à rien et le dit."""
    sc = _make_scenario(tmp_path)
    (sc / "Prefabs" / "BAO_ZiraxDefenseT1.epb").unlink()
    rep = pass_faction_conflict(sc, apply=True)
    assert rep["edits"] == 0
    assert any("Prefabs manquants" in d and "Zirax" in d for d in rep["details"]), rep
    pf = (sc / "Playfields" / "Starter_Dread" / "playfield_static.yaml").read_text("utf-8")
    assert "Conflict" not in pf


def test_planet_playfields_discovery(tmp_path):
    from core.conflict_warfare import planet_playfields
    sc = tmp_path / "S"
    for name, kind in (("Desert", "Planet"), ("MoonX", "Moon"), ("SpaceX", "Space")):
        d = sc / "Playfields" / name
        d.mkdir(parents=True)
        (d / "playfield_static.yaml").write_text("PlayfieldType: %s\n" % kind, encoding="utf-8")
    commented = sc / "Playfields" / "Commented"
    commented.mkdir(parents=True)
    (commented / "playfield_static.yaml").write_text("# PlayfieldType: Planet\n", encoding="utf-8")
    assert planet_playfields(sc) == ["Desert", "MoonX"]   # planètes + lunes


def test_scale_pois_single_shot(tmp_path):
    """Le marqueur empêche une seconde réduction (avant : cumulatif)."""
    from core.conflict_warfare import pass_scale_pois
    sc = _make_scenario(tmp_path, MINIMAL.replace(
        "    FixedPlayerStart:", SCALABLE + "    FixedPlayerStart:"))
    rep1 = pass_scale_pois(sc, 0.5, apply=True)
    assert rep1["edits"] == 2, rep1
    rep2 = pass_scale_pois(sc, 0.5, apply=True)
    assert rep2["edits"] == 0, rep2
    txt = (sc / "Playfields" / "Starter_Dread" / "playfield_static.yaml").read_text("utf-8")
    assert txt.count("CountMinMax: [ 5, 10 ]") == 2   # réduites une seule fois
    assert txt.startswith("# conflict: scale 0.5")


INDENT3 = (
    "PlayfieldType: Planet\n"
    "POIs:\n"
    "   Random:\n"
    "   -  GroupName: R2GhystMain\n"
    "      Faction: Ghyst\n"
    "      Properties:\n"
    "      -  Key: Music\n"
    "         Value: lava2\n"
    "\n"
    "   -  GroupName: CrashedShip\n"
    "      CountMinMax: [2, 4]\n"
    "DroneBaseSetup:\n"
    "    Random:\n"
    "        - GroupName: DroneBaseSetup\n"
    "DroneSpawning:\n"
    "    Random:\n"
    "        - DronesMinMax: [ 0, 0 ]\n"
)


def test_indent_3_style_is_detected(tmp_path):
    """2 playfields sur 122 indentent leurs POI en `   -  ` (3 espaces) :
    nos entrées doivent suivre ce style, sinon elles sortent de la liste
    Random (vécu 09/11 sur EdenBarrenElder)."""
    sc = _make_scenario(tmp_path, INDENT3)
    pass_faction_conflict(sc, apply=True)
    pf = (sc / "Playfields" / "Starter_Dread" / "playfield_static.yaml").read_text("utf-8")
    assert pf.count("\n   -  GroupName: Conflict") == 8    # roster de 8, aucun natif du roster ici
    assert "        - GroupName: Conflict" not in pf      # pas de style 8 espaces
    assert "\n   -  GroupName: R2DroneBase" in pf
    # le groupe natif déclaré reste utilisé (Ghyst), les autres en pool
    assert "\n   -  GroupName: R2GhystMain" in pf
    assert pf.index("   -  GroupName: ConflictZiraxBases") < pf.index(chr(10) + "DroneBaseSetup:")
    assert pass_faction_conflict(sc, apply=True)["edits"] == 0   # idempotent


def test_spawn_entries_preserve_following_sections():
    """DroneSpawning sans commentaire `#` après lui : les sections suivantes
    (SpawnZones, CreatureSpawning) doivent survivre (vécu 09/11 : 8
    playfields les ont perdues)."""
    from core.conflict_warfare import _ensure_spawn_entries, _spawn_entries
    t = (
        "DroneSpawning:\n"
        "    Random:\n"
        "        - DronesMinMax: [ 0, 0 ]\n"
        "          CenterX: -5000\n"
        "SpawnZones:\n"
        "    - Mode: Survival\n"
        "CreatureSpawning:\n"
        "    - Name: Bird\n"
    )
    t2, k = _ensure_spawn_entries(t, _spawn_entries())
    assert k > 0
    assert "SpawnZones:" in t2 and "CreatureSpawning:" in t2
    assert "- Name: Bird" in t2


def test_remove_pois_keeps_no_orphan_fields():
    """Un commentaire en colonne 0 DANS une entrée ne doit pas couper le
    retrait : sinon ses champs restent orphelins et le YAML du playfield
    devient invalide (crash au chargement du scénario, 09/11)."""
    from core.conflict_warfare import _remove_pois
    t = (
        "POIs:\n"
        "    Random:\n"
        "        - GroupName: ConflictZiraxBases\n"
        "          Faction: Zirax\n"
        "# un commentaire collé en colonne 0\n"
        "          CountMinMax: [ 1, 1 ]\n"
        "        - GroupName: Autre\n"
        "          Faction: None\n"
    )
    t2, k = _remove_pois(t, ("ConflictZiraxBases",))
    assert k == 1
    assert "ConflictZiraxBases" not in t2
    assert "CountMinMax: [ 1, 1 ]" not in t2      # plus de champ orphelin
    assert "- GroupName: Autre" in t2              # l'entrée suivante intacte
    assert "Faction: None" in t2


def test_roster_rotation_is_stable_and_sized():
    """Rotation : 8 factions par planète, 6 par lune, Zirax toujours
    présent, et le tirage ne dépend que du nom du playfield."""
    from core.conflict_warfare import _roster
    planet = "PlayfieldType: Planet\n"
    moon = "PlayfieldType: Moon\n"
    r1 = [f[0] for f in _roster("Desert", planet)]
    r2 = [f[0] for f in _roster("Desert", planet)]
    other = [f[0] for f in _roster("Barren", planet)]
    lun = [f[0] for f in _roster("Desert", moon)]
    assert r1 == r2                      # stable
    assert len(r1) == 8 and len(lun) == 6
    assert "Zirax" in r1 and "Zirax" in lun
    assert r1 != other                   # deux planètes = deux rosters


SPACE_MIN = (
    "PlayfieldType: Space\n"
    "DroneBaseSetup:\n"
    "      - FreeDrones:\n"
    "          - Name: [DroneSpacePiratesEMP]\n"
    "            Faction: Pirates\n"
    "            Count: [7, 14]\n"
    "        SpaceVessels:\n"
    "          - Name: [R2OPVPirateT1]\n"
    "            Faction: Pirates\n"
    "            CountMinMax: [2, 4]\n"
)


def test_space_units_added_once_per_faction():
    """Espace : un bloc FreeDrones et un SpaceVessels par faction du roster,
    sans toucher à ceux qui existent déjà (Pirates), et idempotent."""
    from core.conflict_warfare import _ensure_space_units, _space_roster
    roster = _space_roster("EdenSpaceA")
    t2, n = _ensure_space_units(SPACE_MIN, roster)
    sans_pirates = [f for f in roster if f[0] != "Pirates"]
    assert n == 2 * len(sans_pirates), n
    assert t2.count("      - FreeDrones:") == 1        # pas de doublon de section
    assert t2.count("        SpaceVessels:") == 1
    for faction, _, _ in roster:
        assert ("Faction: " + faction) in t2
    assert "AIManPatrolFactions" in t2
    assert _ensure_space_units(t2, roster)[1] == 0   # idempotent


def test_space_playfields_discovery(tmp_path):
    from core.conflict_warfare import space_playfields
    sc = tmp_path / "S"
    for name, kind, fname in (("Orbit", "Space", "space_dynamic.yaml"),
                              ("Desert", "Planet", "playfield_static.yaml")):
        d = sc / "Playfields" / name
        d.mkdir(parents=True)
        (d / fname).write_text("PlayfieldType: %s\n" % kind, encoding="utf-8")
    assert space_playfields(sc) == ["Orbit"]


def test_pois_never_inside_fixed_player_start(tmp_path):
    """Style `   -  ` : la zone Random doit s'arrêter sur `   FixedPlayerStart:`
    (même indentation). Nos entrées dans PlayerStartData = crash
    "Property 'GroupName' not found" (vécu sur EdenMoonTemperate2)."""
    from core.conflict_warfare import _ensure_pois, _poi_style
    t = (
        "POIs:\n"
        "   Random:\n"
        "   -  GroupName: Native1\n"
        "      Faction: None\n"
        "   FixedPlayerStart:\n"
        "   -  Mode: Survival\n"
    )
    style = _poi_style(t)
    assert style["entry"] == "   -  "
    block = ("   -  GroupName: ConflictZiraxBases\n"
             "      Faction: Zirax\n"
             "      CountMinMax: [ 1, 1 ]\n")
    t2, n = _ensure_pois(t, block)
    assert n > 0
    assert t2.index("ConflictZiraxBases") < t2.index("FixedPlayerStart:")
    assert n == 1
    assert _ensure_pois(t2, block)[1] == 0        # idempotent


def test_stray_entry_outside_zone_is_healed():
    """Un bloc à nous resté HORS de la zone (ex. dans FixedPlayerStart) est
    retiré puis réinséré au bon endroit."""
    from core.conflict_warfare import _ensure_pois
    t = (
        "POIs:\n"
        "    Random:\n"
        "        - GroupName: Native1\n"
        "    FixedPlayerStart:\n"
        "        - Mode: Survival\n"
        "        - GroupName: ConflictZiraxBases\n"
        "          Faction: Zirax\n"
        "          CountMinMax: [ 1, 1 ]\n"
    )
    block = ("        - GroupName: ConflictZiraxBases\n"
             "          Faction: Zirax\n"
             "          CountMinMax: [ 1, 1 ]\n")
    t2, n = _ensure_pois(t, block)
    assert n > 0
    zone_start = t2.index("Random:")
    fixed = t2.index("FixedPlayerStart:")
    assert t2.index("ConflictZiraxBases") < fixed      # plus dans PlayerStart
    assert t2.index("ConflictZiraxBases") > zone_start
    assert _ensure_pois(t2, block)[1] == 0


def test_remove_pois_takes_nested_lists():
    """Le retrait d'une entrée doit emporter ses sous-listes
    (`Properties:` puis `-  Key:`) : sinon les queues restent orphelines et
    cassent le YAML (`did not find expected key`, vécu 10/11)."""
    from core.conflict_warfare import _remove_pois
    t = (
        "POIs:\n"
        "   Random:\n"
        "   -  GroupName: ConflictZiraxBases\n"
        "      Faction: Zirax\n"
        "      Properties:\n"
        "      -  Key: RegenAfter\n"
        "         Value: 720\n"
        "   -  GroupName: Native1\n"
        "      Faction: None\n"
    )
    t2, k = _remove_pois(t, ("ConflictZiraxBases",))
    assert k == 1
    assert "ConflictZiraxBases" not in t2
    assert "RegenAfter" not in t2 and "Value: 720" not in t2   # sous-liste emportée
    assert "-  GroupName: Native1" in t2


# ---------------------------------------------------------------------------
# Guerre totale (ForceAttack) et defenses spatiales
# ---------------------------------------------------------------------------
FACTIONS_MIN = (
    "# header\n"
    '{ Faction Id: 2, Name: "Zirax"\n'
    "  Reputation: true\n"
    '  ForceAttack: "Pirates,Eden_Defender"\n'
    "}\n"
    '{ Faction Id: 18, Name: "Trader"\n'
    "  Reputation: true\n"
    '  ForceAttack: "Pirates"\n'
    "}\n"
    '{ Faction Id: 4, Name: "Pirates"\n'
    "  Unfriendly: true\n"
    "}\n"
    '{ Faction Id: 3, Name: "Predator"\n'
    "  Unfriendly: true\n"
    "}\n"
)


def _factions_scenario(tmp_path, text=FACTIONS_MIN):
    sc = tmp_path / "S"
    (sc / "Content" / "Configuration").mkdir(parents=True)
    (sc / "Content" / "Configuration" / "Factions.ecf").write_text(
        text, encoding="utf-8")
    return sc


def test_force_attack_total_war_is_symmetric(tmp_path):
    """Chaque faction active attaque toutes les autres, mais le joueur
    (Eden_Defender) n'est jamais AJOUTÉ : seules celles qui l'attaquaient
    déjà continuent. Faction absente du fichier = pas citée (le moteur
    logue une erreur pour un nom inconnu)."""
    from core.conflict_warfare import pass_force_attack
    sc = _factions_scenario(tmp_path)
    rep = pass_force_attack(sc, apply=True)
    assert rep["edits"] == 3, rep            # Zirax, Trader, Pirates
    txt = (sc / "Content" / "Configuration" / "Factions.ecf").read_text("utf-8")
    assert 'ForceAttack: "Pirates,Eden_Defender,Trader"' in txt   # ordre gardé
    assert 'ForceAttack: "Pirates,Zirax"' in txt                  # pas Eden_Defender
    assert 'ForceAttack: "Zirax,Trader"' in txt                   # ligne créée
    assert "Kriel" not in txt                # absent du fichier => non cité
    pred = txt.split('Name: "Predator"')[1]
    assert "ForceAttack" not in pred         # faction hors roster : intacte
    assert pass_force_attack(sc, apply=True)["edits"] == 0        # idempotent


FW_MIN = (
    "{ Element Name: GlobalSettings\n"
    "  EnableSpaceDefense: True\n"
    "}\n"
    "{ Element Name: FactionSettings\n"
    "  Faction: Zirax\n"
    "  ScenarioGroup: Zirax\n"
    "  Lvl1MinPrice:25\n"
    "  SDProbabilityMin: 0\n"
    "  SDProbabilityMax: 0\n"
    "}\n"
)


def test_space_defense_settings_completed_and_created():
    """Bloc existant : cles SD ajoutees, probas a 0 remontees, prix
    planetaire intact. Faction sans bloc : FactionSettings cree avec prix
    planetaire a 0 (on ne lui ouvre pas les vagues de base-attack)."""
    from core.conflict_warfare import _ensure_sd_settings
    t2, n, manque = _ensure_sd_settings(FW_MIN, ["Zirax", "UCH"])
    assert manque == ["UCH"] and n == 6, (n, manque)   # 5 cles + 1 bloc
    assert "Lvl1MinPrice:25" in t2                       # intact
    assert "SDScenarioGroup: ZiraxSpaceDefense" in t2
    assert "SDProbabilityMin: 0.3" in t2
    bloc = t2.split('Name of nothing')[0].split('Faction: UCH')[1]
    assert "Lvl1MinPrice:0" in bloc and "SDPriceMax: 60" in bloc
    assert _ensure_sd_settings(t2, ["Zirax", "UCH"])[1] == 0     # idempotent


def test_space_defense_units_created():
    """Les vagues viennent des blocs Unit `BaseDefenseOrbitVessel` regroupes
    par `IsInGroups: <Faction>SpaceDefense`. La cle du dictionnaire moteur
    etant `Category + ClassName` (sans la faction), une classe par faction :
    deux factions sur le meme vaisseau = ArgumentException au chargement."""
    from core.conflict_warfare import _ensure_sd_units
    t2, n, noms = _ensure_sd_units(FW_MIN, ["Zirax", "UCH"])
    assert n == 2 and noms == ["Zirax=R2PV_ZiraxCutter01", "UCH=OPV_UCHDestroyer"], noms
    assert t2.count("Category: BaseDefenseOrbitVessel") == 2
    assert 'IsInGroups: "UCHSpaceDefense"' in t2
    assert "# conflict:auto" in t2
    assert _ensure_sd_units(t2, ["Zirax", "UCH"])[1] == 0          # idempotent


def test_space_defense_unit_class_is_never_shared():
    """Vecu 10/11 : 15 factions sur `Eden_SpaceDroneBanditT1` =>
    `Key: BaseDefenseOrbitVesselEden_SpaceDroneBanditT1` en double, exception
    au chargement. Une faction sans patrouilleur propre emprunte un OPV du
    pool, jamais celui deja pris."""
    from core.conflict_warfare import _ensure_sd_units
    txt = ("{ Element Name: Unit\n"
           "  Faction: Pirates\n"
           "  ClassName: OPV_Cyrano\n"
           "  Category: BaseDefenseOrbitVessel\n"
           '  IsInGroups: "PiratesSpaceDefense"\n'
           "}\n")
    t2, n, noms = _ensure_sd_units(txt, ["Xenu"])
    assert n == 1 and noms == ["Xenu=OPV_Hunter"], noms
    assert t2.count("ClassName: OPV_Cyrano") == 1                 # pas de doublon


SPACE_DEF = (
    "PlayfieldType: Space\n"
    "POIs:\n"
    "    - Type: BA_Alien\n"
    "      GroupName: R2TraderSpaceTrade\n"
    "      Faction: Trader\n"
    "      SpaceDefenseOverrideDefaults: True\n"
    "      SpaceDefenseProbability: 0\n"
    "    - Type: BA_Alien\n"
    "      GroupName: Eden_Wreck01\n"
    "      Faction: Eden_Wreck\n"
    "      SpaceDefenseOverrideDefaults: True\n"
    "      SpaceDefenseProbability: 0\n"
    "    - Type: BA_Alien\n"
    "      GroupName: ZiraxSansOverride\n"
    "      Faction: Zirax\n"
    "      SpaceDefenseProbability: 0\n"
    "    - Type: BA_Alien\n"
    "      GroupName: ZiraxDefendu\n"
    "      Faction: Zirax\n"
    "      SpaceDefenseOverrideDefaults: True\n"
    "      SpaceDefenseProbability: 0.25\n"
)


def test_poi_space_defense_only_for_active_factions():
    """Seuls les POI de faction ACTIVE explicitement désarmés (override +
    proba 0) sont réarmés : les épaves/civils et les POI sans override sont
    laissés tels quels (661 `None` + 608 `Eden_Wreck` dans RE2)."""
    from core.conflict_warfare import SPACE_DEFENSE_PROB, _ensure_poi_space_defense
    t2, n = _ensure_poi_space_defense(SPACE_DEF, {"Zirax", "Trader"})
    assert n == 1
    trader = t2.split("R2TraderSpaceTrade")[1].split("- Type:")[0]
    assert "SpaceDefenseProbability: " + str(SPACE_DEFENSE_PROB) in trader
    assert "SpaceDefensePriceMinMax: [ 30, 60 ]" in trader
    wreck = t2.split("Eden_Wreck01")[1].split("- Type:")[0]
    assert "SpaceDefenseProbability: 0\n" in wreck               # intact
    assert t2.count("SpaceDefenseProbability: 0\n") == 2         # wreck + sans override
    assert "SpaceDefenseProbability: 0.25" in t2                 # deja arme
    assert _ensure_poi_space_defense(t2, {"Zirax", "Trader"})[1] == 0


def test_space_defense_unit_class_repaired():
    """Nos blocs deja ecrits sont repares : deux factions sur la meme classe
    (Xenu et Rados avaient tous deux `OPV_Cyrano`) rejouent l'exception du
    10/11, la passe doit reassigner la seconde et rester idempotente."""
    from core.conflict_warfare import _ensure_sd_units

    def bloc(f):
        return ("{ Element Name: Unit\n"
                "  Faction: " + f + "\n"
                "  ClassName: OPV_Cyrano\n"
                "  Category: BaseDefenseOrbitVessel\n"
                '  IsInGroups: "' + f + 'SpaceDefense"\n'
                "  CommandPointsLvl1: 40\n  CommandPointsPerLevel: 1\n"
                "  # conflict:auto\n}\n")

    txt = bloc("Xenu") + bloc("Rados")
    t2, n, noms = _ensure_sd_units(txt, ["Xenu", "Rados"])
    assert n == 1 and noms == ["Xenu=OPV_Cyrano", "Rados=OPV_Hunter"], (n, noms)
    assert t2.count("ClassName: OPV_Cyrano") == 1
    assert _ensure_sd_units(t2, ["Xenu", "Rados"])[1] == 0        # idempotent


# ---------------------------------------------------------------------------
# Ressources rares (regime Starter_Dread) et POI mines
# ---------------------------------------------------------------------------
RES_MIN = (
    "PlayfieldType: Planet\n"
    "RandomResources:\n"
    "    - Name: IronResource\n"
    "      CountMinMax: [ 2, 3 ]\n"
    "    - Name: CobaltResource\n"
    "      CountMinMax: [ 1, 2 ]\n"
    "AsteroidResources:\n"
    "     # - Name: IronResource\n"
    "POIs:\n"
    "    Random:\n"
    "        - GroupName: Native1\n"
    "          Faction: None\n"
    "DroneBaseSetup:\n"
    "    Random:\n"
    "        - GroupName: DroneBaseSetup\n"
    "          Difficulty: 6\n"
)


def test_random_resources_neutralized_once():
    """Dread = zero gisement : toute ligne active de `RandomResources` est
    commentee, le reste du fichier (AsteroidResources, POIs) est intact, et
    un 2e passage ne compte 0."""
    from core.conflict_warfare import neutralize_random_resources
    t2, n = neutralize_random_resources(RES_MIN)
    assert n == 4, n                       # 2 entrees x 2 lignes
    assert "#     - Name: IronResource" in t2
    assert "#       CountMinMax: [ 2, 3 ]" in t2
    assert "AsteroidResources:" in t2 and "POIs:" in t2
    assert neutralize_random_resources(t2)[1] == 0


def test_rare_resources_zero_everywhere(tmp_path, monkeypatch):
    """Zero gisement PARTOUT par defaut (planete ET lune) ; l'exemption des
    lunes reste disponible par le drapeau. Les autres blocs survivent."""
    from core import conflict_warfare as cw

    def scenario(base):
        sc = _factions_scenario(base)
        for name, kind in (("P1", "Planet"), ("M1", "Moon")):
            d = sc / "Playfields" / name
            d.mkdir(parents=True)
            (d / "playfield_static.yaml").write_text(
                RES_MIN.replace("PlayfieldType: Planet",
                                "PlayfieldType: " + kind), encoding="utf-8")
        return sc

    sc = scenario(tmp_path)
    rep = cw.pass_rare_resources(sc, apply=True)
    assert rep["files"] == 2 and rep["edits"] == 8, rep
    planete = (sc / "Playfields" / "P1" / "playfield_static.yaml").read_text("utf-8")
    lune = (sc / "Playfields" / "M1" / "playfield_static.yaml").read_text("utf-8")
    assert "#     - Name: IronResource" in planete and "DroneBaseSetup:" in planete
    assert "#     - Name: IronResource" in lune
    assert cw.pass_rare_resources(sc, apply=True)["edits"] == 0

    monkeypatch.setattr(cw, "RARE_RESOURCES_KEEP_MOONS", True)
    bis = tmp_path / "bis"
    bis.mkdir()
    sc2 = scenario(bis)
    rep2 = cw.pass_rare_resources(sc2, apply=True)
    assert rep2["files"] == 1 and rep2["edits"] == 4, rep2
    assert any("epargnee" in d for d in rep2["details"])


def test_mine_poi_carries_the_ore(tmp_path):
    """Mine starter + une mine par faction du roster, minerai DANS l'entree
    POI (`SpawnResource`), `IsImportant`, drones differencies par hostilite."""
    from core.conflict_warfare import (_entry_groups, _mine_entries_block,
                                       _mine_pool, _poi_style)
    roster = [(f, h) for _, f, h in _entry_groups(RES_MIN, "Starter_Dread")]
    bloc = _mine_entries_block(roster, _poi_style(RES_MIN))
    assert bloc.count("IsImportant: True") == len(roster) + 1
    assert bloc.count("SpawnResource: [") == len(roster) + 1
    assert "SpawnResourceRange: [100, 600]" in bloc
    for faction, _hostile in roster:
        assert "GroupName: " + _mine_pool(faction) in bloc
    starter = bloc.split("GroupName: ConflictStarterMine")[1].split("- GroupName:")[0]
    assert "Faction: None" in starter and "DroneProb: 0.0" in starter
    assert "SpawnPOIAvoidDistance: 1200" in starter and "Value: 1440" in starter
    assert "DroneProb: 0.6" in bloc and "DroneProb: 0.4" in bloc
    assert "NeodymiumResource" in bloc and "Value: 480" in bloc


def test_pois_stay_idempotent_when_another_pass_appends():
    """Nos entrees doivent suivre la derniere entree ETRANGERE ; une autre
    de nos passes peut en ajouter apres (mines) sans provoquer de
    reinsertion a chaque run (vecu 11/11 : 18 edits par playfield)."""
    from core.conflict_warfare import _ensure_pois
    txt = (
        "POIs:\n"
        "    Random:\n"
        "        - GroupName: Native1\n"
        "          Faction: None\n"
        "        - GroupName: ConflictZiraxBases\n"
        "          Faction: Zirax\n"
        "        - GroupName: ConflictZiraxMines\n"
        "          Faction: Zirax\n"
        "    FixedPlayerStart:\n"
    )
    bloc = ("        - GroupName: ConflictZiraxBases\n"
            "          Faction: Zirax\n")
    t2, n = _ensure_pois(txt, bloc)
    assert n == 0, n            # deja apres l'etrangere : rien a faire
    # une entree etrangere ajoutee APRES les notres force le reclassement
    txt2 = txt.replace("    FixedPlayerStart:\n",
                       "        - GroupName: Native2\n"
                       "          Faction: None\n"
                       "    FixedPlayerStart:\n")
    t3, n2 = _ensure_pois(txt2, bloc)
    assert n2 > 0
    assert t3.index("ConflictZiraxBases") > t3.index("Native2")


# ---------------------------------------------------------------------------
# Jalons technologiques par POI (PDA + CSV)
# ---------------------------------------------------------------------------
PDA_MIN = (
    "Chapters:\n"
    "  - ChapterTitle: pda_old01\n"
    "    Category: FAQ\n"
    "    Description: pda_old02\n"
    "Creator: \"Test\"\n"
)
PDA_CSV_MIN = (
    "KEY,English,Deutsch,Fran\u00e7ais\n"
    "pda_old01,Old title,,\n"
    "pda_old02,Old text,,\n"
)


def _pda_scenario(tmp_path):
    sc = _factions_scenario(tmp_path)
    pda = sc / "Extras" / "PDA"
    pda.mkdir(parents=True)
    (pda / "PDA.yaml").write_text(PDA_MIN, encoding="utf-8")
    (pda / "PDA.csv").write_text(PDA_CSV_MIN, encoding="utf-8")
    return sc


def test_tech_milestones_added_once(tmp_path):
    """Trois jalons ajoutes AVANT `Creator:` (donc dans Chapters:), textes
    EN+FR dans le CSV, et un 2e passage ne fait rien."""
    from core.tech_milestones import pass_tech_milestones
    sc = _pda_scenario(tmp_path)
    rep = pass_tech_milestones(sc, apply=True)
    assert rep["edits"] == 18 and rep["files"] == 2, rep
    yaml_txt = (sc / "Extras" / "PDA" / "PDA.yaml").read_text("utf-8")
    csv_txt = (sc / "Extras" / "PDA" / "PDA.csv").read_text("utf-8")
    assert yaml_txt.count("  - ChapterTitle: ") == 4      # 1 existant + 3
    assert yaml_txt.index("pda_Jal3Title") < yaml_txt.index("Creator:")
    assert "Check: ItemsPickedUp" in yaml_txt
    assert "Types:\n              - NeodymiumOre" in yaml_txt
    assert "Type: UP" in yaml_txt and "Type: XP" in yaml_txt
    assert "Jalon III - L'ere du neodyme" in csv_txt
    assert "Milestone III - The neodymium age" in csv_txt
    assert pass_tech_milestones(sc, apply=True)["edits"] == 0        # idempotent


def test_tech_milestones_refuses_existing_keys(tmp_path):
    """Une cle deja presente (meme dans le CSV seul) arrete la passe : on ne
    duplique jamais un jeton de localisation."""
    from core.tech_milestones import pass_tech_milestones
    sc = _pda_scenario(tmp_path)
    csv = sc / "Extras" / "PDA" / "PDA.csv"
    csv.write_text(PDA_CSV_MIN + "pda_Jal2Text,deja pris,,\n", encoding="utf-8")
    rep = pass_tech_milestones(sc, apply=True)
    assert rep["edits"] == 0 and "deja presente" in " ".join(rep["details"])
    assert "pda_Jal1Title" not in (sc / "Extras" / "PDA" / "PDA.yaml").read_text("utf-8")


def test_mine_entries_carry_map_markers():
    """Sans marqueur, le joueur ne sait pas ou aller chercher le minerai :
    `MapDistance`/`HudDistance` rendent les mines visibles de loin (memes
    cles que nos patrouilleurs spatiaux, verifiees en jeu)."""
    from core.conflict_warfare import (_entry_groups, _mine_entries_block,
                                       _poi_style)
    roster = [(f, h) for _, f, h in _entry_groups(RES_MIN, "Starter_Dread")]
    bloc = _mine_entries_block(roster, _poi_style(RES_MIN))
    assert "Key: MapDistance" in bloc and "Key: HudDistance" in bloc
    assert bloc.count("Value: 20000") >= len(roster) + 1      # 1 par mine
    starter = bloc.split("GroupName: ConflictStarterMine")[1].split("- GroupName:")[0]
    assert "HudDistance\n" + "              Value: 20000" in starter
    assert "Value: 5000" in bloc                              # mines de faction
