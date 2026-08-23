"""
Tests du module d'edition structuree des playfields (core/playfield_editor.py) --
bases sur de VRAIS playfield.yaml et un VRAI (extrait de) BlocksConfig.ecf,
pas des fixtures inventees, pour eviter de repeter l'erreur commise avec le
check POI/Prefabs precedent (champs devines plutot que verifies).
"""
from pathlib import Path

import pytest

from core.playfield_editor import (
    find_top_level_key, list_items, find_poi_items, find_creature_items,
    get_item_params, set_item_param, list_resource_block_names,
    add_resource_item, remove_resource_item,
)
from core.yamllite.parser import parse_yaml_file, parse_yaml_text

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "playfield_scenario"
PLAYFIELD = FIXTURE_DIR / "playfield_static.yaml"
AKUA_PLAYFIELD = FIXTURE_DIR / "playfield_akua.yaml"
BLOCKS_ECF = FIXTURE_DIR / "BlocksConfig.ecf"


@pytest.fixture
def doc():
    return parse_yaml_file(PLAYFIELD)


@pytest.fixture
def akua_doc():
    return parse_yaml_file(AKUA_PLAYFIELD)


def test_round_trip_stays_byte_perfect_on_real_file():
    original = PLAYFIELD.read_bytes()
    rendered = parse_yaml_file(PLAYFIELD).render().encode("utf-8")
    assert original == rendered


def test_akua_round_trip_stays_byte_perfect():
    original = AKUA_PLAYFIELD.read_bytes()
    rendered = parse_yaml_file(AKUA_PLAYFIELD).render().encode("utf-8")
    assert original == rendered


def test_random_resources_found_with_correct_count_and_params(doc):
    items = list_items(doc, "RandomResources", "Name")
    names = [i.value for i in items]
    assert names == ["IronResource", "CopperResource", "PromethiumResource",
                      "PentaxidResource", "ErestrumResource"]
    iron_params = dict(get_item_params(items[0]))
    assert iron_params["DroneProb"] == "0.5"
    assert iron_params["CountMinMax"] == "[ 2, 3 ]"


def test_asteroid_resources_found(doc):
    items = list_items(doc, "AsteroidResources", "Name")
    names = [i.value for i in items]
    assert "IronResource" in names
    assert "CobaltResource" not in names  # entree commentee, doit rester ignoree


def test_random_resources_found_despite_zero_indent_comments_on_real_akua_file(akua_doc):
    """Regression majeure : sur un vrai playfield (Akua), des commentaires a
    indentation zero au milieu de RandomResources ("# Smaller scattered
    around planet", "### Resource Asteroids"...) cassaient le rattachement
    hierarchique du parseur -- seul 1 ressource sur 9 etait retrouvee avant
    cette correction (list_items() ne descendait que dans les enfants
    directs de la section). Signale directement par retour utilisateur :
    "il en manque beaucoup, qui sont presentes dans le yaml complet"."""
    items = list_items(akua_doc, "RandomResources", "Name")
    assert len(items) == 9
    names = [i.value for i in items]
    # Plusieurs entrees partagent le MEME nom avec des biomes differents --
    # doivent toutes etre retrouvees, pas seulement la premiere occurrence.
    assert names.count("IronResource") == 3
    assert names.count("CarbonResource") == 2
    assert names.count("PromethiumResource") == 2


def test_asteroid_resources_found_on_real_akua_file(akua_doc):
    items = list_items(akua_doc, "AsteroidResources", "Name")
    assert len(items) == 5


def test_poi_items_found_despite_zero_indent_comments_breaking_tree_nesting(doc):
    """Regression : des commentaires a indentation zero au milieu de la section
    POIs cassent le rattachement hierarchique du parseur (round-trip prefixe
    reste correct, mais la vraie arborescence ne l'est pas) -- verifie que la
    recherche par plage d'indices contourne bien ce piege sur le vrai fichier
    ou il a ete decouvert."""
    pois = find_poi_items(doc)
    assert len(pois) == 41
    names = [p.value for p in pois]
    assert "R2DroneBase" in names
    assert "R2XenuDefenseT3" in names


def test_poi_params_include_real_fields(doc):
    pois = find_poi_items(doc)
    xenu = next(p for p in pois if p.value == "R2XenuDefenseT3")
    params = dict(get_item_params(xenu))
    assert params["SpawnPOIAvoidDistance"] == "400"
    assert params["SpawnPOINear"] == "[R2DroneBase]"


def test_creature_items_found(doc):
    creatures = find_creature_items(doc)
    assert len(creatures) == 88
    names = {c.value for c in creatures}
    assert "Spiders01" in names


def test_set_item_param_modifies_correct_value(doc):
    items = list_items(doc, "RandomResources", "Name")
    iron = items[0]
    assert set_item_param(iron, "DroneProb", "0.99") is True
    assert dict(get_item_params(iron))["DroneProb"] == "0.99"
    # Le rendu doit refleter le changement
    assert "DroneProb: 0.99" in doc.render()


def test_set_item_param_returns_false_for_unknown_key(doc):
    items = list_items(doc, "RandomResources", "Name")
    assert set_item_param(items[0], "ThisKeyDoesNotExist", "x") is False


def test_list_resource_block_names_from_real_blocks_ecf():
    names = list_resource_block_names([BLOCKS_ECF])
    assert "IronResource" in names
    assert "CopperResource" in names
    # Un bloc non-ressource (present dans le fichier reduit pour diversite) ne
    # doit jamais apparaitre.
    assert all(n.endswith("Resource") for n in names)


def test_add_resource_item_appends_with_consistent_formatting(doc):
    before_count = len(list_items(doc, "RandomResources", "Name"))

    new_item = add_resource_item(doc, "RandomResources", "SiliconResource",
                                  [("IsScalingCount", "True"), ("CountMinMax", "[ 1, 2 ]")])

    items_after = list_items(doc, "RandomResources", "Name")
    assert len(items_after) == before_count + 1
    assert items_after[-1] is new_item
    assert new_item.value == "SiliconResource"
    assert dict(get_item_params(new_item))["CountMinMax"] == "[ 1, 2 ]"


def test_add_resource_item_returns_none_for_missing_section(doc):
    assert add_resource_item(doc, "ThisSectionDoesNotExist", "X", []) is None


def test_added_resource_survives_reparse_and_is_idempotent(doc):
    add_resource_item(doc, "RandomResources", "SiliconResource", [("IsScalingCount", "True")])
    rendered_once = doc.render()

    reparsed = parse_yaml_text(rendered_once)
    reparsed_names = [i.value for i in list_items(reparsed, "RandomResources", "Name")]
    assert "SiliconResource" in reparsed_names

    rendered_twice = reparsed.render()
    assert rendered_once == rendered_twice  # stable, pas de derive au second rendu


def test_add_resource_item_works_correctly_on_akua_file_with_many_entries(akua_doc):
    """Regression complementaire : l'ajout doit fonctionner correctement meme
    quand la section contient deja des items 'perdus' par le piege des
    commentaires -- l'ajout lui-meme (append direct a section.children)
    n'etait pas casse, mais le controle avant/apres (nombre attendu) l'etait
    tant que list_items() ne les retrouvait pas tous."""
    before = len(list_items(akua_doc, "RandomResources", "Name"))
    assert before == 9
    add_resource_item(akua_doc, "RandomResources", "SiliconResource", [("CountMinMax", "[ 1, 2 ]")])
    after = list_items(akua_doc, "RandomResources", "Name")
    assert len(after) == 10


def test_remove_resource_item(doc):
    items = list_items(doc, "RandomResources", "Name")
    before_count = len(items)
    target = items[0]

    assert remove_resource_item(doc, "RandomResources", target) is True
    after_items = list_items(doc, "RandomResources", "Name")
    assert len(after_items) == before_count - 1
    assert target.value not in [i.value for i in after_items]


def test_remove_resource_item_returns_false_if_not_found(doc):
    from core.yamllite.model import create_entry
    fake_item = create_entry("Name", "NotInDocument", is_sequence_item=True)
    assert remove_resource_item(doc, "RandomResources", fake_item) is False


def test_remove_resource_item_returns_false_for_missing_section(doc):
    from core.yamllite.model import create_entry
    fake_item = create_entry("Name", "X", is_sequence_item=True)
    assert remove_resource_item(doc, "ThisSectionDoesNotExist", fake_item) is False


def test_find_top_level_key_returns_none_for_missing_section(doc):
    assert find_top_level_key(doc, "ThisSectionDoesNotExist") is None


def test_find_poi_items_returns_empty_list_when_no_pois_section():
    minimal_doc = parse_yaml_text("PlanetType: Alien\r\n")
    assert find_poi_items(minimal_doc) == []


def test_list_items_returns_empty_list_for_missing_section(doc):
    assert list_items(doc, "ThisSectionDoesNotExist", "Name") == []


def test_list_resource_block_names_does_not_filter_anything_special(tmp_path):
    """Aucun filtre d'exclusion special (l'ancien filtre AsteroidVoxel a ete
    retire -- confirme legitime par retour utilisateur sur un vrai playfield
    spatial, ce sont de vraies ressources, juste une categorie differente --
    voir find_space_resource_items pour leur traitement dedie)."""
    ecf_file = tmp_path / "BlocksConfig.ecf"
    ecf_file.write_text(
        "{ Block Id: 1, Name: IronResource\n  Material: metal\n}\n\n"
        "{ Block Id: 4, Name: CopperResource\n  Material: metal\n}\n",
        encoding="utf-8",
    )
    names = list_resource_block_names([ecf_file])
    assert names == ["CopperResource", "IronResource"]


def test_find_creature_items_attaches_biome_to_each_entry(doc):
    """Un meme nom de creature (ex: Spiders01) apparait dans plusieurs zones de
    biome differentes -- signale directement par retour utilisateur, impossible
    a distinguer sans cette info."""
    from core.playfield_editor import get_creature_biome
    creatures = find_creature_items(doc)
    spiders = [c for c in creatures if c.value == "Spiders01"]
    assert len(spiders) == 3
    biomes = {get_creature_biome(c) for c in spiders}
    assert biomes == {"[Grassland]", "[Biofilm ]", "[Tundra]"}


def test_get_properties_value_reads_nested_regenafter(doc):
    pois = find_poi_items(doc)
    drone_base = next(p for p in pois if p.value == "R2DroneBase")
    from core.playfield_editor import get_properties_value
    assert get_properties_value(drone_base, "RegenAfter") == "4320"


def test_get_properties_value_returns_none_for_missing_key(doc):
    from core.playfield_editor import get_properties_value
    pois = find_poi_items(doc)
    assert get_properties_value(pois[0], "ThisKeyDoesNotExist") is None


def test_set_properties_value_modifies_nested_regenafter(doc):
    from core.playfield_editor import get_properties_value, set_properties_value
    pois = find_poi_items(doc)
    drone_base = next(p for p in pois if p.value == "R2DroneBase")

    assert set_properties_value(drone_base, "RegenAfter", "8640") is True
    assert get_properties_value(drone_base, "RegenAfter") == "8640"
    assert "Value: 8640" in doc.render()


def test_set_properties_value_returns_false_for_missing_key(doc):
    from core.playfield_editor import set_properties_value
    pois = find_poi_items(doc)
    assert set_properties_value(pois[0], "ThisKeyDoesNotExist", "x") is False


# ============================================================================
# Ressources spatiales -- bases sur un vrai space_dynamic.yaml
# ============================================================================

SPACE_FIXTURE = Path(__file__).parent / "fixtures" / "space_scenario" / "space_dynamic.yaml"


@pytest.fixture
def space_doc():
    return parse_yaml_file(SPACE_FIXTURE)


def test_space_round_trip_stays_byte_perfect():
    original = SPACE_FIXTURE.read_bytes()
    rendered = parse_yaml_file(SPACE_FIXTURE).render().encode("utf-8")
    assert original == rendered


def test_find_space_resource_items_finds_only_material_asteroids(space_doc):
    """La section 'Resources:' d'un playfield espace contient BEAUCOUP d'autres
    entrees non-minables (champs decoratifs, structures composees) -- doit
    filtrer pour ne garder que le motif confirme AsteroidVoxel0N<Materiau>."""
    from core.playfield_editor import find_space_resource_items
    items = find_space_resource_items(space_doc)
    assert len(items) == 18
    values = [i.value for i in items]
    assert any("AsteroidVoxel01Iron" in v for v in values)
    # Les entrees non-minables ne doivent jamais apparaitre
    assert not any("Compound" in v for v in values)
    assert not any("AsteroidFieldBoxExclude" in v for v in values)


def test_get_space_resource_display_name_uses_displayname(space_doc):
    from core.playfield_editor import find_space_resource_items, get_space_resource_display_name
    items = find_space_resource_items(space_doc)
    iron = next(i for i in items if "Iron" in i.value)
    assert get_space_resource_display_name(iron) == "Iron Asteroid"


def test_space_resource_has_regenafter_via_properties(space_doc):
    from core.playfield_editor import find_space_resource_items, get_properties_value
    items = find_space_resource_items(space_doc)
    iron = next(i for i in items if "Iron" in i.value)
    assert get_properties_value(iron, "RegenAfter") == "720"


def test_list_space_material_names_strips_resource_suffix():
    from core.playfield_editor import list_space_material_names
    materials = list_space_material_names([BLOCKS_ECF])
    assert "Iron" in materials
    assert "Copper" in materials
    assert "IronResource" not in materials  # bien le materiau nu, pas le nom de bloc


def test_add_space_resource_item_duplicates_full_nested_structure(space_doc):
    from core.playfield_editor import (
        find_space_resource_items, add_space_resource_item,
        get_properties_value, get_item_params,
    )
    existing = find_space_resource_items(space_doc)
    template = existing[0]

    new_item = add_space_resource_item(space_doc, "Platin", template_item=template)

    assert "AsteroidVoxel01Platin" in new_item.value
    assert "AsteroidVoxel02Platin" in new_item.value
    assert "AsteroidVoxel03Platin" in new_item.value
    assert dict(get_item_params(new_item))["DisplayName"] == "Platin Asteroid"
    # La structure imbriquee (Properties/RegenAfter) doit avoir ete dupliquee,
    # pas seulement les parametres simples.
    assert get_properties_value(new_item, "RegenAfter") is not None


def test_add_space_resource_item_returns_none_for_missing_section(doc):
    from core.playfield_editor import add_space_resource_item
    # 'doc' (playfield planete) n'a pas de section 'Resources' -- doit echouer
    # proprement plutot que planter.
    assert add_space_resource_item(doc, "Platin") is None


def test_added_space_resource_survives_reparse(space_doc):
    from core.playfield_editor import add_space_resource_item, find_space_resource_items
    add_space_resource_item(space_doc, "Platin")
    rendered = space_doc.render()

    reparsed = parse_yaml_text(rendered)
    reparsed_items = find_space_resource_items(reparsed)
    assert any("Platin" in i.value for i in reparsed_items)
    assert len(reparsed_items) == 19


def test_remove_space_resource_item(space_doc):
    from core.playfield_editor import find_space_resource_items, remove_space_resource_item
    items = find_space_resource_items(space_doc)
    before = len(items)
    target = items[0]

    assert remove_space_resource_item(space_doc, target) is True
    after = find_space_resource_items(space_doc)
    assert len(after) == before - 1


# ============================================================================
# Drones/Vaisseaux -- DroneBaseSetup (structure differente planete/espace)
# ============================================================================

def test_drone_stock_items_found_on_planet_file(akua_doc):
    from core.playfield_editor import find_drone_stock_items
    items = find_drone_stock_items(akua_doc)
    assert len(items) == 5
    names = [i.value for i in items]
    assert "RipperDog" in names
    assert "DroneAeroZiraxMinigun" in names


def test_drone_stock_items_empty_on_space_file(space_doc):
    """Regression : sans suivi de sous-section, cette fonction remontait a tort
    TOUTES les entrees 'Name:' de DroneBaseSetup sur un fichier espace
    (confondant Stock/FreeDrones/SpaceVessels), alors qu'un playfield espace
    n'a pas de section 'Stock' du tout."""
    from core.playfield_editor import find_drone_stock_items
    assert find_drone_stock_items(space_doc) == []


def test_free_drones_items_found_on_space_file(space_doc):
    from core.playfield_editor import find_free_drones_items
    items = find_free_drones_items(space_doc)
    assert len(items) == 4


def test_free_drones_items_empty_on_planet_file(akua_doc):
    from core.playfield_editor import find_free_drones_items
    assert find_free_drones_items(akua_doc) == []


def test_space_vessels_items_found_on_space_file(space_doc):
    from core.playfield_editor import find_space_vessels_items
    items = find_space_vessels_items(space_doc)
    assert len(items) == 7
    values = [i.value for i in items]
    assert "[RE2_OPVRogueT1]" in values


def test_space_vessels_items_empty_on_planet_file(akua_doc):
    from core.playfield_editor import find_space_vessels_items
    assert find_space_vessels_items(akua_doc) == []


def test_free_drones_and_space_vessels_do_not_overlap(space_doc):
    """Les deux listes partagent la meme cle d'item ('Name:') -- le suivi de
    sous-section doit correctement les separer, aucun item ne doit se
    retrouver dans les deux resultats."""
    from core.playfield_editor import find_free_drones_items, find_space_vessels_items
    free_drones = find_free_drones_items(space_doc)
    vessels = find_space_vessels_items(space_doc)
    assert set(id(i) for i in free_drones).isdisjoint(set(id(i) for i in vessels))


def test_drone_stock_amount_is_editable(akua_doc):
    from core.playfield_editor import find_drone_stock_items, set_item_param, get_item_params
    items = find_drone_stock_items(akua_doc)
    ripper = next(i for i in items if i.value == "RipperDog")
    assert set_item_param(ripper, "Amount", "5") is True
    assert dict(get_item_params(ripper))["Amount"] == "5"


# ============================================================================
# DroneSpawning, SpawnRateZones, SpawnZones, SpecialEffectsLocal/Global
# ============================================================================

def test_drone_spawning_items_found_on_planet_file(akua_doc):
    from core.playfield_editor import find_drone_spawning_items
    items = find_drone_spawning_items(akua_doc)
    assert len(items) == 2


def test_spawn_rate_zones_items_found_on_planet_file(akua_doc):
    from core.playfield_editor import find_spawn_rate_zones_items
    items = find_spawn_rate_zones_items(akua_doc)
    assert len(items) == 7


def test_spawn_zones_items_found_on_planet_file(akua_doc):
    from core.playfield_editor import find_spawn_zones_items
    items = find_spawn_zones_items(akua_doc)
    assert len(items) == 14


def test_spawn_rate_zones_and_spawn_zones_do_not_overlap(akua_doc):
    """Les deux sections partagent la meme cle d'item ('SpawnAt:') mais sont
    des sections de niveau racine DISTINCTES -- la plage d'indices standard
    doit suffire a les separer sans confusion, contrairement a FreeDrones/
    SpaceVessels qui partageaient une meme section parente."""
    from core.playfield_editor import find_spawn_rate_zones_items, find_spawn_zones_items
    rate_zones = find_spawn_rate_zones_items(akua_doc)
    spawn_zones = find_spawn_zones_items(akua_doc)
    assert set(id(i) for i in rate_zones).isdisjoint(set(id(i) for i in spawn_zones))


def test_special_effects_local_items_found_on_planet_file(akua_doc):
    from core.playfield_editor import find_special_effects_local_items
    items = find_special_effects_local_items(akua_doc)
    assert len(items) == 18
    names = [i.value for i in items]
    assert names.count("Pollen") == 4  # plusieurs occurrences du meme nom, biomes differents
    assert names.count("DandelionsFew") == 7


def test_special_effects_global_items_found_on_planet_file(akua_doc):
    from core.playfield_editor import find_special_effects_global_items
    items = find_special_effects_global_items(akua_doc)
    assert len(items) == 14


def test_all_new_sections_empty_on_space_file(space_doc):
    """Aucune de ces cinq sections n'existe sur un playfield espace -- doivent
    toutes retourner une liste vide plutot que planter."""
    from core.playfield_editor import (
        find_drone_spawning_items, find_spawn_rate_zones_items, find_spawn_zones_items,
        find_special_effects_local_items, find_special_effects_global_items,
    )
    assert find_drone_spawning_items(space_doc) == []
    assert find_spawn_rate_zones_items(space_doc) == []
    assert find_spawn_zones_items(space_doc) == []
    assert find_special_effects_local_items(space_doc) == []
    assert find_special_effects_global_items(space_doc) == []


def test_spawn_rate_zone_radius_is_editable(akua_doc):
    from core.playfield_editor import find_spawn_rate_zones_items, set_item_param, get_item_params
    items = find_spawn_rate_zones_items(akua_doc)
    assert set_item_param(items[0], "Radius", "999") is True
    assert dict(get_item_params(items[0]))["Radius"] == "999"
    assert "Radius: 999" in akua_doc.render()


# ============================================================================
# Fixed/Random POI et FixedPlayerStart -- necessaires pour le canvas 2D,
# distincts de find_poi_items() qui melange tout (utile pour les references
# croisees, pas pour distinguer position absolue/relative)
# ============================================================================

def test_find_fixed_poi_items_on_akua_file(akua_doc):
    """Confirme sur un vrai playfield_akua.yaml : 2 entrees Fixed, cle d'item
    'Type' (pas 'GroupName'), avec position absolue reelle."""
    from core.playfield_editor import find_fixed_poi_items, get_item_params
    items = find_fixed_poi_items(akua_doc)
    assert len(items) == 2
    names = {dict(get_item_params(i)).get("Name") for i in items}
    assert names == {"Reforged Creative Library", "Platform"}
    params = dict(get_item_params(items[0]))
    assert params["Pos"] == "[ -1460, 33, 1555 ]"


def test_find_fixed_poi_items_empty_when_no_fixed_section(doc):
    """playfield_static.yaml (fixture existante) n'a pas de section Fixed --
    doit retourner une liste vide, pas planter."""
    from core.playfield_editor import find_fixed_poi_items
    assert find_fixed_poi_items(doc) == []


def test_find_random_poi_items_matches_find_poi_items_count(doc, akua_doc):
    """find_random_poi_items() doit toujours correspondre exactement a
    find_poi_items() sur les fichiers qui n'ont pas de section Fixed
    (playfield_static.yaml), et etre un sous-ensemble strict sur ceux qui en
    ont une (playfield_akua.yaml)."""
    from core.playfield_editor import find_random_poi_items, find_poi_items
    assert len(find_random_poi_items(doc)) == len(find_poi_items(doc)) == 41
    assert len(find_random_poi_items(akua_doc)) == 32
    assert len(find_poi_items(akua_doc)) == 32  # Fixed jamais inclus dans find_poi_items()


def test_find_fixed_player_start_items_nested_under_pois(doc):
    """Regression : FixedPlayerStart est imbrique SOUS POIs (indentation
    non-zero), pas une cle de niveau racine comme on aurait pu le supposer --
    confirme 4 entrees reelles sur playfield_static.yaml, entre deux
    occurrences successives de 'Random:' dans ce meme fichier."""
    from core.playfield_editor import find_fixed_player_start_items, get_item_params
    items = find_fixed_player_start_items(doc)
    assert len(items) == 4
    modes = [i.value for i in items]
    assert "Debug" in modes
    assert "Survival" in modes


def test_double_random_marker_does_not_cause_misattribution(doc):
    """Regression specifique : playfield_static.yaml contient DEUX occurrences
    textuelles de 'Random:' (separees par FixedPlayerStart) -- les items des
    deux blocs doivent tous etre correctement rattaches a 'Random', aucun ne
    doit se retrouver perdu ou mal etiquete a cause de cette repetition."""
    from core.playfield_editor import find_random_poi_items, find_poi_items
    # find_poi_items() est deja etabli fiable (verifie de nombreuses fois plus
    # tot) -- la coherence stricte avec ce total confirme qu'aucun item n'est
    # perdu entre les deux occurrences de Random.
    assert len(find_random_poi_items(doc)) == len(find_poi_items(doc))
