"""Look cartoon (core/cartoon_look.py) : reexpression CIBLEE des lignes
visuelles de terrain.ecf et des ciels de playfield — tout le reste du
fichier doit rester octet-pour-octet identique."""

from core.cartoon_look import (spread_rgb_tuple, saturate_triplet,
                               scale_float, transform_terrain_ecf,
                               transform_playfield_yaml)

TERRAIN = """{ Material Name: AridStarter
  HeightMapMax: "490"
  SplatMap_1: "AridStarter_splat1"

 { Child 0 # Grass02
  Name: "Grass02"
  Brightness: "1.05"
  Saturation: "1.02"
  RGB: "(2.81, 1.11, 2.37)"
  AddCol: "0.15"
  Smoothness: "0.09"
  ReliefStrength: "0.38"
  NormalStrength: "1.9"
  TerrainId: "28"
  UnderTerrainId: "73"
 }
}
"""

YAML = """---
# playfield de test (commentaire a PRESERVER)
PlayfieldType: Planet
AtmosphereEnabled: True
AtmosphereColor: "0.674, 0.824, 1.000"
SkyColor: "1, 0.96, 0.96"
SkyHorizonColor: "1, 0.43, 0.1"
# SkyHorizonColor: "0, 0, 0" (variante commentee : NE PAS toucher)
FogCloudIntensity: 0.8
FogColor: "1.0, 1.0, 1.0"
SunFlare: EnvironmentalEffects/SunFlareBlue
SpecialEffectsGlobal:
    - Name: Fog
      FogColor: "0.2, 0.3, 0.4"   # imbriquee : NE PAS toucher
"""


def test_scale_helpers():
    assert scale_float("1.02", 1.6, 0.8, 2.5) == "1.632"
    assert scale_float("2", 1.6, 0.8, 2.5) == "2.5"       # clamp haut
    assert scale_float("0.8", 0.5, 0.0, 1.0) == "0.4"
    assert saturate_triplet("1, 0.43, 0.1", 1.5) == "1.000, 0.465, 0.155"
    assert saturate_triplet("1, 1, 1", 1.5) == "1, 1, 1"   # gris : inchange
    assert saturate_triplet("1.2, 0.5, 0.5", 1.5) == "1.2, 0.5, 0.5"  # >1 refuse
    assert spread_rgb_tuple("2, 1, 1", 2.0) == "(2.667, 0.667, 0.667)"


def test_terrain_ne_change_que_les_cles_visuelles():
    out, stats = transform_terrain_ecf(TERRAIN)
    assert stats["Saturation"] == 1 and stats["NormalStrength"] == 1
    assert stats["ReliefStrength"] == 1 and stats["RGB"] == 1
    assert stats["Smoothness"] == 1
    assert 'Saturation: "1.632"' in out
    assert 'Smoothness: "-0.25"' in out                  # brillance plafonnee
    assert 'NormalStrength: "1"' in out                  # 1.9 x 0.6 -> clamp
    assert 'ReliefStrength: "0.209"' in out
    assert 'RGB: "(3.167, 0.617, 2.507)"' in out
    # tout le reste, octet pour octet :
    for line in TERRAIN.splitlines():
        if not any(k in line for k in ("Saturation", "Smoothness",
                                       "NormalStrength", "ReliefStrength",
                                       "RGB:")):
            assert line in out, line
    assert 'Brightness: "1.05"' in out and 'TerrainId: "28"' in out


def test_yaml_ne_change_que_les_cles_colonne_zero():
    out, stats = transform_playfield_yaml(YAML)
    assert set(stats) == {"AtmosphereColor", "SkyColor", "SkyHorizonColor",
                          "FogCloudIntensity"}
    assert 'SkyHorizonColor: "1.000, 0.465, 0.155"' in out
    assert 'FogCloudIntensity: 0.4' in out
    # saturable deja a 1 : luminance montee seulement ; commentaire et
    # cle imbriquee intacts
    assert 'SkyColor: "1.000, 1.000, 1.000"' in out
    assert '# SkyHorizonColor: "0, 0, 0"' in out
    assert 'FogColor: "1.0, 1.0, 1.0"' in out              # blanc : inchange
    assert 'FogColor: "0.2, 0.3, 0.4"' in out              # imbriquee : intacte
    assert 'AtmosphereColor: "0.758, 0.869, 1.000"' in out
    assert "# playfield de test (commentaire a PRESERVER)" in out
    assert 'SunFlare: EnvironmentalEffects/SunFlareBlue' in out


def test_rien_a_faire_jeux_vides():
    out_t, stats_t = transform_terrain_ecf("{ Material Name: x\n}\n")
    assert stats_t == {} and out_t == "{ Material Name: x\n}\n"
    out_y, stats_y = transform_playfield_yaml("---\nPlayfieldType: Space\n")
    assert stats_y == {} and out_y == "---\nPlayfieldType: Space\n"


# -- preset editable ---------------------------------------------------------

def test_preset_edite_change_la_transformation():
    out, stats = transform_terrain_ecf(TERRAIN, {"saturation": 2.0,
                                                 "smoothness_cap": -0.6})
    assert 'Saturation: "2.04"' in out           # 1.02 x 2.0
    assert 'Smoothness: "-0.6"' in out           # plafond plus mat
    assert stats["Saturation"] == 1 and stats["Smoothness"] == 1


def test_normalize_preset_bornes_et_defauts():
    from core.cartoon_look import DEFAULT_PRESET, normalize_preset
    assert normalize_preset(None) == DEFAULT_PRESET
    assert normalize_preset("n'importe quoi") == DEFAULT_PRESET
    out = normalize_preset({"saturation": 99, "normal": "0.3",
                            "fog_intensity": -5})
    assert out["saturation"] == 3.0              # clamp haut
    assert out["normal"] == 0.3                  # chaine numerique acceptee
    assert out["fog_intensity"] == 0.0           # clamp bas
    for key in DEFAULT_PRESET:                   # cles absentes -> defaut
        assert key in out


def test_preset_persiste(tmp_path, monkeypatch):
    import core.settings as settings
    from core.cartoon_look import load_stored_preset, save_preset
    monkeypatch.setattr(settings, 'SETTINGS_FILE', tmp_path / 'settings.json')
    settings._CACHE_MTIME = None
    assert load_stored_preset()["saturation"] == 1.6   # defaut
    save_preset({"saturation": 2.2, "relief": "0.7", "inconnu": 3})
    stored = load_stored_preset()
    assert stored["saturation"] == 2.2 and stored["relief"] == 0.7
    assert "inconnu" not in stored


# -- orchestration : sauvegardes, restauration, apercu couleurs -------------

def _scenario(tmp_path):
    pf = tmp_path / "Playfields" / "DemoPlanet"
    pf.mkdir(parents=True)
    (pf / "terrain.ecf").write_text(TERRAIN, encoding="utf-8")
    (pf / "playfield_static.yaml").write_text(YAML, encoding="utf-8")
    return tmp_path


def test_passe_sauvegardee_et_restauration(tmp_path, monkeypatch):
    from core.cartoon_look import list_backups, restore_backup, run_preset
    scenario = _scenario(tmp_path)
    original = (scenario / "Playfields/DemoPlanet/terrain.ecf").read_text(
        encoding="utf-8")
    monkeypatch.setattr("core.cartoon_look.get_backup_root",
                        lambda kind: str(tmp_path / "bk"))
    monkeypatch.setattr(
        "core.cartoon_look.get_production_scenario_path", lambda p: "")

    rep = run_preset(scenario, no_sync=True)
    assert rep["ok"] is True
    backups = list_backups()
    assert len(backups) == 1 and scenario.name in backups[0].name
    assert 'Saturation: "1.632"' in (scenario / "Playfields/DemoPlanet/"
                                     "terrain.ecf").read_text(encoding="utf-8")
    assert (scenario / "+cartoon_look_applique.txt").exists()

    rep = restore_backup(scenario, backups[0])
    assert rep["ok"] is True and rep["copied"] == 2
    assert (scenario / "Playfields/DemoPlanet/terrain.ecf").read_text(
        encoding="utf-8") == original
    assert not (scenario / "+cartoon_look_applique.txt").exists()

    rep = restore_backup(scenario, tmp_path / "cartoon_look_inconnu")
    assert rep["ok"] is False and rep["error"] == "backup_missing"


def test_preview_couleurs_origine_vs_preset(tmp_path):
    from core.cartoon_look import preview_colors
    scenario = _scenario(tmp_path)
    rows = preview_colors(scenario, "DemoPlanet")
    ciel = dict((k, (o, n)) for k, o, n in rows["ciel"])
    assert "SkyHorizonColor" in ciel
    assert ciel["SkyHorizonColor"][0] == "1, 0.43, 0.1"
    terrain = dict((s, (o, n)) for s, o, n in rows["terrain"])
    assert terrain["Grass02"][0] == "(2.81, 1.11, 2.37)"
    assert terrain["Grass02"][1] != terrain["Grass02"][0]
    assert preview_colors(scenario, "Inconnu") == {"ciel": [], "terrain": []}
