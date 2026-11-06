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

"""Reintegration de playfields orphelins : detection, placement, ecriture.

Le corpus fait foi (vecu 22/10) : une planete n'a PAS de SectorMapType et sa
ligne a 7 champs ; une lune et une orbite sont des LIGNES a offset dans le
secteur de la planete ; une geante a GasGiant + texture ; `None` + 4 champs
est la signature d'une ETOILE et cassait la carte systeme.
"""
from pathlib import Path

from core.playfield_reintegrate import (apply_placements, find_legacy,
                                        find_missing_arrivals, find_orphans,
                                        find_unloadable, plan_placements,
                                        remove_legacy, render_preview)

SECTORS = """SolarSystems:
  - Name: Alpha
    Sectors:
      - Coordinates: [0, 0, 0]
        SectorMapType: None
        Playfields:
          - ['0,0,0', Alpha, SunRandom, '']
      - Coordinates: [3, 0, 0]
        Playfields:
          - ['0, 0, 0', Akua, Starter_Akua_V2, '', '', '', '']
  - Name: Beta
    Sectors:
      - Coordinates: [0, 0, 0]
        SectorMapType: None
        Playfields:
          - ['0,0,0', Beta, SunRandom, '']
      - Coordinates: [4, 0, 0]
        SectorMapType: None
        Playfields:
          - ['0,0,0', Ancien, Ancien, '']
"""

SURFACE = {"playfield_static.yaml":
           "PlayfieldType: Planet\nDescription: |\n  Monde de test.\n"}
SPACE = {"space_dynamic.yaml":
         "PlayfieldType: Space\nDescription: |\n  Espace de test.\n"}


def _build(root: Path) -> Path:
    (root / "Sectors").mkdir(parents=True)
    (root / "Sectors" / "Sectors.yaml").write_text(SECTORS, encoding="utf-8")
    folders = {
        "SunRandom": SURFACE,
        "Starter_Akua_V2": SURFACE,
        "EdenOcean2": SURFACE,                    # planete
        "Start_MoonIce": SURFACE,                 # lune
        "EdenGasDwarfBlue": SURFACE,              # geante
        "Alpha": SURFACE,                         # collision de nom
        "EdenSpace_POI_CombatT1_1": SPACE,        # espace
        "EdenSpace_AsteroidT1": SPACE,            # asteroide
        "SpaceTradingStation": SPACE,             # station
        "Starter_Akua_Orbit": SPACE,              # orbite
    }
    for name, files in folders.items():
        for filename, text in files.items():
            path = root / "Playfields" / name / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    return root


def test_orphans_are_classified_by_kind(tmp_path):
    root = _build(tmp_path)
    orphans = {o.type_name: o for o in find_orphans(root)}
    assert orphans["EdenOcean2"].category == "planet"
    assert orphans["Start_MoonIce"].category == "moon"
    assert orphans["EdenGasDwarfBlue"].category == "gasgiant"
    assert orphans["Starter_Akua_Orbit"].category == "orbit"
    assert orphans["EdenSpace_AsteroidT1"].category == "asteroid"
    assert orphans["SpaceTradingStation"].category == "station"
    assert orphans["EdenSpace_POI_CombatT1_1"].category == "space"
    assert orphans["EdenOcean2"].family == "surface"
    assert orphans["Starter_Akua_Orbit"].family == "space"
    assert "Monde de test" in orphans["EdenOcean2"].description
    assert "Ancien" not in orphans          # ce n'est pas un dossier


def test_container_folder_is_not_an_orphan(tmp_path):
    """`Playfields/Reforged/` (RE2) ne contient que des starters : le declarer
    dans Sectors.yaml fait refuser le chargement du scenario (« Playfield
    Reforged has unknown playfield type Undefined », vecu 25/10)."""
    root = _build(tmp_path)
    starter = root / "Playfields" / "Reforged" / "AridStarter"
    starter.mkdir(parents=True)
    (starter / "playfield_static.yaml").write_text(
        "PlayfieldType: Planet\n", encoding="utf-8")
    assert "Reforged" not in {o.type_name for o in find_orphans(root)}


def test_plan_spreads_across_systems_and_rings(tmp_path):
    root = _build(tmp_path)
    plan = plan_placements(
        root, ["EdenOcean2", "Start_MoonIce", "EdenSpace_AsteroidT1",
               "EdenGasDwarfBlue"], per_system=2)
    by_name = {p.type_name: p for p in plan}
    assert by_name["EdenOcean2"].system == "Alpha"
    assert by_name["Start_MoonIce"].system == "Alpha"
    assert by_name["EdenSpace_AsteroidT1"].system == "Beta"
    assert by_name["EdenGasDwarfBlue"].system == "Beta"
    # lune : ligne a offset dans le secteur de la PLANETE (pas du soleil)
    moon = by_name["Start_MoonIce"]
    assert moon.mode == "row" and moon.sector == (3, 0, 0)
    assert moon.coords == (4500, 5000, 8000)
    # orbite verticale autour de l'etoile (0,0,0) : premier point libre
    planet = by_name["EdenOcean2"]
    assert planet.mode == "sector" and planet.coords == (0, 30, 0)
    assert planet.map_type == ""            # une planete n'a pas de type
    assert by_name["EdenGasDwarfBlue"].map_type == "GasGiant"
    assert by_name["EdenSpace_AsteroidT1"].map_type == "AsteroidFieldFew"


def test_planet_always_carries_a_warp_arrival(tmp_path):
    """Chaque planete posee recoit sa ligne d'arrivee `<Nom> Sector` : sans
    cible de warp dans le secteur, « Selectionner » ne fait rien dans la
    carte systeme (vecu 22/10, demande utilisateur 04/11)."""
    root = _build(tmp_path)
    plan = plan_placements(root, ["EdenOcean2"], per_system=1)
    planet = next(p for p in plan if p.category == "planet")
    assert planet.arrival == "Starter_Akua_Orbit"
    rows = planet.rows()
    assert any("EdenOcean2 Sector" in r and "Starter_Akua_Orbit" in r
               for r in rows)


def test_planet_is_not_placed_without_any_orbit_type(tmp_path):
    """Aucun playfield d'orbite dans le scenario : plutot que de poser une
    planete sans route de warp (injoignable, vecu 22/10), on l'ecarte."""
    import shutil
    root = _build(tmp_path)
    shutil.rmtree(root / "Playfields" / "Starter_Akua_Orbit")
    plan = plan_placements(root, ["EdenOcean2"], per_system=1)
    assert not [p for p in plan if p.category == "planet"]


def test_orbit_is_centered_on_a_shifted_sun(tmp_path):
    """Etoile DECALEE : l'orbite verticale tourne autour d'ELLE, pas de
    l'origine (des systemes du corpus ont un soleil hors [0,0,0])."""
    root = _build(tmp_path)
    text = (root / "Sectors" / "Sectors.yaml").read_text(encoding="utf-8")
    text = text.replace("- Coordinates: [0, 0, 0]\n        SectorMapType: None",
                        "- Coordinates: [5, 2, 1]\n        SectorMapType: None",
                        1)                    # seul le soleil d'Alpha
    (root / "Sectors" / "Sectors.yaml").write_text(text, encoding="utf-8")
    plan = plan_placements(root, ["EdenOcean2"])
    assert plan[0].coords == (5, 32, 1)


def test_moon_is_skipped_without_a_host_planet(tmp_path):
    root = _build(tmp_path)
    plan = plan_placements(root, ["EdenOcean2", "Start_MoonIce"],
                           per_system=1)
    assert [p.system for p in plan] == ["Alpha"]      # Beta n'a pas de planete


def test_plan_suffixes_a_name_already_taken(tmp_path):
    root = _build(tmp_path)
    plan = plan_placements(root, ["Alpha"])
    assert plan[0].name == "Alpha_2"


def test_apply_writes_corpus_shaped_entries(tmp_path):
    root = _build(tmp_path)
    plan = plan_placements(
        root, ["EdenOcean2", "Start_MoonIce", "EdenSpace_AsteroidT1",
               "EdenGasDwarfBlue"], per_system=2)
    applied, details = apply_placements(root, plan)
    assert details == [] and applied == len(plan)
    text = (root / "Sectors" / "Sectors.yaml").read_text(encoding="utf-8")
    assert "Coordinates: [0, 30, 0]" in text
    # planete : pas de SectorMapType, 7 champs
    assert "['0, 0, 0', EdenOcean2, EdenOcean2, '', '', '', '']" in text
    # lune : ligne a offset dans le secteur de la planete
    assert "['4500, 5000, 8000', Start_MoonIce, Start_MoonIce]" in text
    # asteroide et geante : SectorMapType du corpus
    assert "SectorMapType: AsteroidFieldFew" in text
    assert "SectorMapType: GasGiant" in text
    assert "'SaturnBrown', '12'" in text
    # la planete recoit son orbite d'ARRIVEE (cible de warp)
    assert "['0,0,0', EdenOcean2 Sector, Starter_Akua_Orbit, '']" in text
    assert "['0,0,0', Ancien, Ancien, '']" in text    # pas retire ici


def test_orbit_is_written_inside_the_host_sector(tmp_path):
    root = _build(tmp_path)
    plan = plan_placements(root, ["Starter_Akua_Orbit"], per_system=2)
    assert plan[0].mode == "row" and plan[0].sector == (3, 0, 0)
    applied, details = apply_placements(root, plan)
    assert details == [] and applied == 1
    text = (root / "Sectors" / "Sectors.yaml").read_text(encoding="utf-8")
    assert "['0,0,0', Starter_Akua_Orbit, Starter_Akua_Orbit, '']" in text
    # la ligne est DANS le secteur [3,0,0] : juste apres Akua
    secteur = text.split("Coordinates: [3, 0, 0]", 1)[1].split("Coordinates:", 1)[0]
    assert "Starter_Akua_Orbit" in secteur
    assert "SunRandom" not in secteur


def test_preview_shows_sectors_rows_and_removals(tmp_path):
    root = _build(tmp_path)
    plan = plan_placements(root, ["EdenOcean2", "Start_MoonIce"],
                           per_system=2)
    preview = render_preview(plan, find_legacy(root))
    assert "retirer : secteur Beta [4, 0, 0]" in preview
    assert "- Coordinates: [0, 30, 0]" in preview
    assert "SectorMapType: None" not in preview        # planete : pas de type
    assert "['4500, 5000, 8000', Start_MoonIce, Start_MoonIce]" in preview


def test_missing_arrival_route_is_detected_and_written(tmp_path):
    # vecu 22/10 : planete sans playfield espace dans son secteur -> la carte
    # n'a aucune cible de warp, « Selectionner » ne fait rien
    root = _build(tmp_path)
    routes = find_missing_arrivals(root)
    assert [r.name for r in routes] == ["Akua Sector"]
    assert routes[0].sector == (3, 0, 0)
    assert routes[0].type_name == "Starter_Akua_Orbit"
    applied, details = apply_placements(root, routes)
    assert applied == 1 and details == []
    text = (root / "Sectors" / "Sectors.yaml").read_text(encoding="utf-8")
    assert "['0,0,0', Akua Sector, Starter_Akua_Orbit, '']" in text
    assert find_missing_arrivals(root) == []


def test_legacy_sectors_are_found_and_removed(tmp_path):
    root = _build(tmp_path)
    legacy = find_legacy(root)
    assert [item.key for item in legacy] == ["Beta [4, 0, 0]"]
    assert remove_legacy(root, legacy) == 1
    text = (root / "Sectors" / "Sectors.yaml").read_text(encoding="utf-8")
    assert "Ancien" not in text
    assert "['0,0,0', Alpha, SunRandom, '']" in text
    assert "['0, 0, 0', Akua, Starter_Akua_V2, '', '', '', '']" in text
    assert find_legacy(root) == []


def _check_by_type(dialog, type_name):
    from PyQt6.QtCore import Qt
    for index in range(dialog.tree.topLevelItemCount()):
        parent = dialog.tree.topLevelItem(index)
        for row in range(parent.childCount()):
            child = parent.child(row)
            if child.data(0, Qt.ItemDataRole.UserRole) == type_name:
                child.setCheckState(0, Qt.CheckState.Checked)
                return True
    return False


def test_space_placement_is_not_mistaken_for_a_legacy_sector(tmp_path):
    """Vecu 05/11 : l'espace s'ecrit `['0,0,0', N, N, '']` + `WarpTarget`,
    exactement la forme du corpus. La detection « ancien format » ne doit pas
    la reprendre : l'outil proposait alors de supprimer ses propres secteurs
    et leurs playfields restaient orphelins (boucle sans fin)."""
    root = _build(tmp_path)
    plan = plan_placements(root, ["EdenSpace_POI_CombatT1_1"])
    assert [p.type_name for p in plan] == ["EdenSpace_POI_CombatT1_1"]
    assert apply_placements(root, plan)[0] == 1
    # seul le secteur de l'ancien format du corpus de test reste propose
    assert [i.key for i in find_legacy(root)] == ["Beta [4, 0, 0]"]
    assert "EdenSpace_POI_CombatT1_1" not in {
        o.type_name for o in find_orphans(root)}


def test_starter_playfield_is_offered_as_a_start(tmp_path):
    """Un playfield de DEPART reintroduit doit etre propose au menu Nouvelle
    partie : c'est le marqueur de faction du corpus (`'Human:1'`) qui le fait,
    pas la simple presence du secteur (vecu 05/11 : `Starter_Haven_V2` pose en
    planete inerte, donc injouable comme depart)."""
    root = _build(tmp_path)
    starter = root / "Playfields" / "Starter_Haven_V2"
    starter.mkdir(parents=True)
    (starter / "playfield_static.yaml").write_text(
        "PlayfieldType: Planet\n", encoding="utf-8")
    plan = plan_placements(root, ["Starter_Haven_V2"])
    assert [p.start for p in plan] == [True]
    assert plan[0].name == "Haven"              # nom du lieu, pas du dossier
    assert apply_placements(root, plan)[0] == 1
    text = (root / "Sectors" / "Sectors.yaml").read_text(encoding="utf-8")
    assert "- ['0, 0, 0', Haven, Starter_Haven_V2,'Human:1', '', '', '']" in text
    assert "['0,0,0', Haven Sector, Starter_Akua_Orbit, '']" in text


def test_plain_playfield_keeps_an_empty_start_marker(tmp_path):
    root = _build(tmp_path)
    plan = plan_placements(root, ["EdenOcean2"])
    assert plan[0].start is False
    assert "['0, 0, 0', EdenOcean2, EdenOcean2, '', '', '', '']" in \
        plan[0].row()


def test_dialog_lists_kinds_and_previews(qapp, tmp_path):
    from PyQt6 import sip
    from gui.playfield_reintegrate_dialog import PlayfieldReintegrateDialog
    root = _build(tmp_path)
    dialog = PlayfieldReintegrateDialog(root)
    try:
        assert dialog.spin.value() == 2
        assert dialog.tree.topLevelItemCount() == 2       # surface + espace
        assert dialog.legacy_check.isChecked()            # ancien secteur vu
        assert _check_by_type(dialog, "EdenOcean2")
        dialog._preview()
        assert "- Coordinates: [0, 30, 0]" in dialog.preview.toPlainText()
        assert "retirer" in dialog.preview.toPlainText()
        assert dialog.btn_apply.isEnabled()
    finally:
        sip.delete(dialog)


def test_dialog_apply_writes_backup_and_undo(qapp, tmp_path, monkeypatch):
    from PyQt6 import sip
    from gui import playfield_reintegrate_dialog as mod
    root = _build(tmp_path)
    backups, pushed = [], []

    class Main:
        workspace = None
        def _push_workspace_undo(self, undo):
            pushed.append(undo)
        def _reload_tab_if_open_and_unmodified(self, path):
            pass

    monkeypatch.setattr(mod, "ask_yes_no", lambda *a, **k: True)
    import core.fsutil as fsutil
    monkeypatch.setattr(fsutil, "central_backup",
                        lambda p, kind="sectors": backups.append(p))
    monkeypatch.setattr(mod, "async_call", lambda *a, **k: None)
    dialog = mod.PlayfieldReintegrateDialog(root, main_window=Main())
    try:
        assert _check_by_type(dialog, "EdenOcean2")
        dialog._apply()
        text = (root / "Sectors" / "Sectors.yaml").read_text(encoding="utf-8")
        assert "['0, 0, 0', EdenOcean2, EdenOcean2, '', '', '', '']" in text
        # l'orbite d'arrivee du secteur Akua est ajoutee aussi
        assert "['0,0,0', Akua Sector, Starter_Akua_Orbit, '']" in text
        assert "Ancien" not in text                    # ancien secteur retire
        assert dialog.applied == 2
        assert len(backups) == 1 and len(pushed) == 1
    finally:
        sip.delete(dialog)


def _child_by_type(dialog, type_name):
    from PyQt6.QtCore import Qt
    for index in range(dialog.tree.topLevelItemCount()):
        parent = dialog.tree.topLevelItem(index)
        for row in range(parent.childCount()):
            child = parent.child(row)
            if child.data(0, Qt.ItemDataRole.UserRole) == type_name:
                return child
    return None


def test_playfield_without_type_is_never_proposable(tmp_path, monkeypatch):
    """Sans `PlayfieldType`, le client s'arrete (« unknown playfield type
    Undefined ») : un tel dossier ne doit pas etre cotisable."""
    import core.yaml_game_check as ygc
    root = _build(tmp_path)
    (root / "Playfields" / "SansType").mkdir()
    (root / "Playfields" / "SansType" / "terrain.ecf").write_text("x")
    monkeypatch.setattr(ygc, "locate_checker", lambda: None)
    assert find_unloadable(root, ["SansType", "EdenOcean2"]) == {
        "SansType": ("type", "")}


def test_broken_yaml_is_blocked_with_the_engine_message(tmp_path, monkeypatch):
    """Vecu 05/11 : trois lignes perdues dans `EdenOcean2/playfield_static.yaml`
    — le playfield a ete reintegre et le scenario n'a plus demarre. Le yaml est
    desormais soumis au moteur du jeu AVANT d'entrer dans `Sectors.yaml`."""
    import core.yaml_game_check as ygc
    from core.yaml_game_check import YamlFinding
    root = _build(tmp_path)

    def fake(checker, dirs, mode="yaml", command=None):
        return [YamlFinding("EdenOcean2\\playfield_static.yaml", 1131, 9,
                            "While parsing a block mapping, did not find "
                            "expected key.")], 1

    monkeypatch.setattr(ygc, "locate_checker", lambda: Path("yamlcheck"))
    monkeypatch.setattr(ygc, "run_yaml_check", fake)
    found = find_unloadable(root, ["EdenOcean2", "Start_MoonIce"])
    assert found["EdenOcean2"][0] == "yaml"
    assert "block mapping" in found["EdenOcean2"][1]
    assert "Start_MoonIce" not in found


def test_dialog_blocks_an_unloadable_playfield(qapp, tmp_path, monkeypatch):
    from PyQt6 import sip
    from PyQt6.QtCore import Qt
    from gui import playfield_reintegrate_dialog as mod
    root = _build(tmp_path)
    (root / "Playfields" / "SansType").mkdir()
    (root / "Playfields" / "SansType" / "terrain.ecf").write_text("x")
    monkeypatch.setattr(mod, "find_unloadable",
                        lambda r, n: {"SansType": ("type", "")})
    dialog = mod.PlayfieldReintegrateDialog(root)
    try:
        child = _child_by_type(dialog, "SansType")
        assert child is not None
        assert not child.flags() & Qt.ItemFlag.ItemIsUserCheckable
        assert "Exclu" in child.text(2)
        assert "SansType" not in dialog._selected()
        assert "1 playfield(s) exclu(s)" in dialog.status.text()
        assert _child_by_type(dialog, "EdenOcean2").flags() \
            & Qt.ItemFlag.ItemIsUserCheckable
    finally:
        sip.delete(dialog)
