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

"""Bilan « avant lancement » : construction du scenario synthetique,
declenchement de chaque famille de checks (doublons Sectors, fichiers
etrangers, playfields absents avec fallback vanille, prefabs manquants)
et construction du dialogue."""

import os
from pathlib import Path

from core.launch_check import run_launch_checks

# format reel : sequence INDENTEE sous SolarSystems (yamllite exige
# l'indentation, vecu sur le premier jet du test)
SECTORS_OK = """SolarSystems:
  - Name: Sys1
    Sectors:
      - ['0, 0, 0', Soleil1, Sun, '']
      - ['100, 0, 0', Planete1, Pf1, '']
      - ['200, 0, 0', Lune1, Pf1Moon, '']
"""


def _build_scenario(tmp_path: Path, sectors_text: str = SECTORS_OK) -> Path:
    (tmp_path / "Sectors").mkdir()
    (tmp_path / "Sectors" / "Sectors.yaml").write_text(
        sectors_text, encoding="utf-8")
    for name in ("Pf1", "Pf1Moon"):
        pf = tmp_path / "Playfields" / name
        pf.mkdir(parents=True)
        (pf / "playfield_static.yaml").write_text(
            "PlayfieldType: Temperate\n"
            "- PrefabName: XyFortress, Percent: 0.5\n", encoding="utf-8")
    (tmp_path / "Prefabs").mkdir()
    (tmp_path / "Prefabs" / "XyFortress.epb").write_bytes(b"")
    return tmp_path


def _errors(issues):
    return [i for i in issues if i.severity == "error"]


def test_good_scenario_no_issues(tmp_path):
    root = _build_scenario(tmp_path)
    issues = run_launch_checks(root, "")
    assert _errors(issues) == []


def test_missing_sectors_yaml(tmp_path):
    issues = run_launch_checks(tmp_path, "")
    assert [i.check for i in _errors(issues)] == ["sectors"]
    assert "introuvable" in _errors(issues)[0].message


def test_duplicate_playfield_across_systems(tmp_path):
    # le crash du jeu porte sur le NOM (2e champ), vecu « Duplicate
    # playfield name 'Parthix' » — pas sur le dossier (3e champ)
    sectors = SECTORS_OK + (
        "  - Name: Sys2\n"
        "    Sectors:\n"
        "      - ['0, 0, 0', Lune1, Pf1Moon, '']\n")
    root = _build_scenario(tmp_path, sectors)
    dup = [i for i in _errors(run_launch_checks(root, ""))
           if "plusieurs systemes" in i.message]
    assert len(dup) == 1 and "'Lune1'" in dup[0].message


def test_stray_bak_in_sectors_is_error(tmp_path):
    root = _build_scenario(tmp_path)
    (root / "Sectors" / "Sectors.yaml.bak").write_text("x\n", encoding="utf-8")
    issues = run_launch_checks(root, "")
    stray = [i for i in issues if i.check == "sectors" and ".bak" in i.path]
    assert len(stray) == 1 and stray[0].severity == "error"


def test_missing_playfield_folder_with_vanilla_fallback(tmp_path):
    # Pf2 reference mais absent du scenario -> erreur...
    sectors = SECTORS_OK + (
        "      - ['300, 0, 0', Planete2, Pf2, '']\n")
    root = _build_scenario(tmp_path, sectors)
    errs = [i for i in _errors(run_launch_checks(root, ""))
            if i.check == "playfields"]
    assert len(errs) == 1 and "Pf2" in errs[0].message
    # ...mais passe si la vanille fournit le template (scenario a generateur)
    vanilla = tmp_path / "vanilla"
    (vanilla / "Playfields" / "Pf2").mkdir(parents=True)
    issues = run_launch_checks(root, str(vanilla))
    assert [i for i in _errors(issues) if i.check == "playfields"] == []


def test_missing_prefab(tmp_path):
    root = _build_scenario(tmp_path)
    pf = root / "Playfields" / "Pf1"
    (pf / "playfield_static.yaml").write_text(
        "PlayfieldType: Temperate\n"
        "- PrefabName: GhostBase, Percent: 0.5\n", encoding="utf-8")
    errs = [i for i in _errors(run_launch_checks(root, ""))
            if i.check == "prefabs"]
    assert len(errs) == 1
    assert "GhostBase" in errs[0].message and errs[0].line == 2
    # resolu par la vanille
    vanilla = tmp_path / "vanilla"
    (vanilla / "Prefabs").mkdir(parents=True)
    (vanilla / "Prefabs" / "GhostBase.epb").write_bytes(b"")
    assert [i for i in _errors(run_launch_checks(root, str(vanilla)))
            if i.check == "prefabs"] == []


def _write_epb(path, name: str = "", groups: str = "") -> None:
    """En-tete .epb minimal (magic, version 31, proprietes 7=Name et
    21=Groupes) : suffisant pour `read_header`, sans donnees de blocs."""
    import struct
    props = b""
    for key, value in ((7, name), (21, groups)):
        props += (struct.pack("<i", key) + b"\x00\x00\x00" + b"\x00"
                  + struct.pack("<B", len(value)) + value.encode())
    data = (struct.pack("<I", 2022986309) + struct.pack("<I", 31) + b"\x02"
            + struct.pack("<iii", 1, 1, 1) + struct.pack("<HH", 1, 2)
            + props + struct.pack("<H", 0))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def test_prefab_check_reads_prefab_syntax_and_ignores_comments(tmp_path):
    # la copie de travail reference par `Prefab:` (pas `PrefabName:`) et les
    # entrees commentees decrivent ce qui est DESACTIVE (YAML-009)
    root = _build_scenario(tmp_path)
    _write_epb(root / "Prefabs" / "FileStem.epb", name="InternalName",
               groups="Alpha")
    pf = root / "Playfields" / "Pf1"
    (pf / "playfield_static.yaml").write_text(
        "Playfields:\n"
        "- Prefab: InternalName\n"          # nom interne de l'en-tete
        "- PrefabName: FileStem\n"          # nom de fichier
        "- Prefab: GhostBase\n"             # fantome : erreur
        "- Prefab: # Desactive\n", encoding="utf-8")
    errs = [i for i in run_launch_checks(root, "") if i.check == "prefabs"]
    # le .epb factice est illisible pour le mapping -> 1 warning supplementaire
    assert len(errs) == 2
    assert "GhostBase" in errs[0].message and errs[0].line == 4
    assert "illisibles" in errs[1].message


def test_poi_groups_are_read_from_prefab_headers(tmp_path):
    # bplib export exige une partie en cours ; les groupes sont dans l'en-tete
    root = _build_scenario(tmp_path)
    _write_epb(root / "Prefabs" / "Base.epb", name="Base", groups="Alpha,Beta")
    pf = root / "Playfields" / "Pf1"
    (pf / "playfield_static.yaml").write_text(
        "Random:\n"
        "- GroupName: Beta\n"               # declare par l'en-tete
        "- GroupName: GhostGrp\n"           # introuvable -> avertissement
        "- GroupName: # Desactive\n", encoding="utf-8")
    issues = [i for i in run_launch_checks(root, "")
              if i.check == "poi_groups"]
    assert len(issues) == 1
    assert "GhostGrp" in issues[0].message
    assert issues[0].severity == "warning"
    assert "1 playfield" in issues[0].message


def test_poi_group_declared_by_poi_groups_config(tmp_path):
    root = _build_scenario(tmp_path)
    (root / "Prefabs").mkdir(parents=True, exist_ok=True)
    (root / "Prefabs" / "_PoiGroupsConfig.yaml").write_text(
        "---\n  PoiGroups:\n    - GroupName: UnionGroup\n"
        "      Filters:\n          BlueprintFileNames: [ Base ]\n",
        encoding="utf-8")
    (root / "Playfields" / "Pf1" / "playfield_static.yaml").write_text(
        "- GroupName: UnionGroup\n", encoding="utf-8")
    assert [i for i in run_launch_checks(root, "")
            if i.check == "poi_groups"] == []


def test_poi_group_may_name_a_local_setup_block(tmp_path):
    # vecu 22/10 : `DroneBaseSetup:` en tete de playfield_static, puis
    # `Random:` -> `GroupName: DroneBaseSetup` : ce n'est pas un groupe de
    # prefab, l'alerte serait un faux positif
    from core.launch_check import _index_setups
    root = _build_scenario(tmp_path)
    pf = root / "Playfields" / "Pf1"
    (pf / "playfield_static.yaml").write_text(
        "POIs:\n"
        "  Random:\n"
        "    - GroupName: DroneBaseSetup\n"
        "DroneBaseSetup:\n"
        "  Random:\n"
        "    - GroupName: DroneBaseSetup\n"
        "      Difficulty: 6\n", encoding="utf-8")
    assert "dronebasesetup" in _index_setups(pf.parent)
    assert [i for i in run_launch_checks(root, "")
            if i.check == "poi_groups"] == []


def test_egroup_references(tmp_path):
    root = _build_scenario(tmp_path)
    conf = root / "Content" / "Configuration"
    conf.mkdir(parents=True)
    (conf / "EGroupsConfig.ecf").write_text(
        "{ EGroup Name: ZiraxPatrol\n}\n", encoding="utf-8")
    pf = root / "Playfields" / "Pf1"
    (pf / "playfield_static.yaml").write_text(
        "PlayfieldType: Temperate\n"
        "  Entities:\n"
        "    - Names: [ZiraxPatrol, GhostGroup]\n"
        "      Amount: 10\n", encoding="utf-8")
    errs = [i for i in _errors(run_launch_checks(root, ""))
            if i.check == "egroups"]
    assert len(errs) == 1 and "GhostGroup" in errs[0].message
    # Names: hors contexte Entities = ignore (reference predates le check)
    (pf / "playfield_static.yaml").write_text(
        "PlayfieldType: Temperate\n"
        "  Names: [GhostGroup]\n", encoding="utf-8")
    assert [i for i in _errors(run_launch_checks(root, ""))
            if i.check == "egroups"] == []


def test_galaxy_index_duplicates_and_gaps(tmp_path):
    root = _build_scenario(tmp_path)
    conf = root / "Content" / "Configuration"
    conf.mkdir(parents=True)
    (conf / "GalaxyConfig.ecf").write_text(
        "{ GalaxyConfig Name: X, StarClass: A\n"
        "}\n"
        "{ Child StarRegion_1\n"
        "}\n"
        "{ Child StarRegion_3\n"
        "}\n"
        "{ Child Territory_2\n"
        "}\n"
        "{ Child Territory_2\n"
        "}\n", encoding="utf-8")
    errs = [i for i in _errors(run_launch_checks(root, ""))
            if i.check == "galaxy"]
    # 1 trou StarRegion_2 + doublon Territory_2 + trou Territory_1
    assert len(errs) == 3
    assert any("DOUBLON" in e.message and "Territory_2" in e.message
               for e in errs)
    assert any("discontinue" in e.message and "StarRegion" in e.message
               for e in errs)
    # pas de blocs indexes = pas de check (scenarios a generateur)
    (conf / "GalaxyConfig.ecf").write_text(
        "{ GalaxyConfig Name: X, StarClass: A\n}\n", encoding="utf-8")
    assert [i for i in _errors(run_launch_checks(root, ""))
            if i.check == "galaxy"] == []


def test_bin_caches_orphan_and_stale(tmp_path):
    root = _build_scenario(tmp_path)
    pf = root / "Playfields" / "Pf1"
    stale_bin = pf / "playfield_static.yaml.bin"
    stale_bin.write_bytes(b"x")
    os.utime(stale_bin, (10**9, 10**9))          # tres vieux
    yaml_f = pf / "playfield_static.yaml"
    # .bin ANCIEN devant yaml recent : le jeu recompilera = pas un signal
    assert not [i for i in run_launch_checks(root, "") if i.check == "caches"]
    # meme date = signature de la copie mtime conserve (vecu 05/10)
    st = yaml_f.stat()
    os.utime(stale_bin, (st.st_atime, st.st_mtime))
    caches = [i for i in run_launch_checks(root, "") if i.check == "caches"]
    assert len(caches) == 1 and "mtime" in caches[0].message
    # orphelin
    (pf / "playfield_dynamic.yaml.bin").write_bytes(b"x")
    caches = [i for i in run_launch_checks(root, "") if i.check == "caches"]
    assert any("orphelin" in i.message for i in caches)


def test_value_shapes(tmp_path):
    # dictionnaire vanille : une valeur dont la FAMILLE contredit tout ce
    # que la vanille observe sort en warning ; quotée = tolérée (le jeu
    # strip et parse), booleen dans une prop-chaine = toléré
    root = _build_scenario(tmp_path)
    conf = root / "Content" / "Configuration"
    conf.mkdir(parents=True)
    vanilla = tmp_path / "vanilla" / "Content" / "Configuration"
    vanilla.mkdir(parents=True)
    (vanilla / "BlocksConfig.ecf").write_text(
        "{ Block Id: 400, Name: RefB\n"
        "  Health: 100\n"
        "  ShowUser: Yes\n"
        "}\n", encoding="utf-8")
    (conf / "BlocksConfig.ecf").write_text(
        "{ Block Id: 401, Name: TestB\n"
        "  Health: abc\n"            # typo : non-numerique ou vanilla=num
        "  Mass: 42\n"               # sain
        "  ShowUser: true\n"          # booleen sur prop-chaine : tolere
        '  Count: "1,2"\n'           # quoté : toléré
        "}\n", encoding="utf-8")
    # vanilla_content = le dossier CONTENT (contrat de get_vanilla_content_path)
    issues = [i for i in run_launch_checks(root, str(tmp_path / "vanilla" / "Content"))
              if i.check == "values"]
    assert len(issues) == 1
    assert "Health" in issues[0].message and "abc" in issues[0].message
    assert issues[0].severity == "warning"


def test_dedi_boot_helpers(tmp_path):
    # yaml jetable : ports hors gamme, sauvegarde jetable, scenario cible
    from core.dedi_boot_check import (_parse_log_issues, build_test_yaml)
    yaml_text = build_test_yaml("RE2-RPG")
    assert "33000" in yaml_text and "_TestChargementEditeur" in yaml_text
    assert "CustomScenario: RE2-RPG" in yaml_text
    # parsing du log : erreurs dedupliquees, lignes saines ignorees
    log = ("11-19:30:31 -ERR- Blueprint group 'FarrSpaceDef' not found or empty!\n"
           "11-19:30:40 -LOG- Server started listening on port 33000\n"
           "11-19:30:41 -EXC- did not find expected key\n"
           "11-19:30:31 -ERR- Blueprint group 'FarrSpaceDef' not found or empty!\n")
    issues = _parse_log_issues(log)
    assert len(issues) == 2
    assert any("FarrSpaceDef" in i for i in issues)
    assert any("did not find expected key" in i for i in issues)


def test_dedi_boot_helper_checks_the_loaded_scenario(tmp_path):
    # vecu 22/10 : scenario introuvable -> le jeu GENERe un Sectors.yaml par
    # defaut (43 playfields), demarre, et le bilan disait « pret »
    from core.dedi_boot_check import DediBootResult, check_loaded_scenario
    expected = tmp_path / "Content" / "Scenarios" / "RE2 ATL"
    root = expected.parent.as_posix()
    copied = (f"22-07:36:47 -LOG- Copying Sectors.yaml from {root}/RE2 ATL"
              "/Sectors to C:\\Jeu\\Saves\\Games\\x\\Sectors")
    ok = DediBootResult(ready=True, playfields=928)
    check_loaded_scenario(ok, copied, expected)
    assert ok.ready is True and ok.issues == []

    generated = DediBootResult(ready=True, playfields=43)
    check_loaded_scenario(
        generated,
        f"22-07:36:47 -LOG- Generating Sectors.yaml in {root}"
        "/__Inexistant__/Sectors\n"
        "22-07:36:48 -LOG- Loaded sector file x with 43 playfields", expected)
    assert generated.ready is False
    assert any("GENere" in i for i in generated.issues)

    other = DediBootResult(ready=True, playfields=928)
    check_loaded_scenario(
        other, f"Copying Sectors.yaml from {root}/RE2-RPG/Sectors", expected)
    assert other.ready is False and any("!=" in i for i in other.issues)


def test_dedi_boot_refuses_a_missing_scenario(tmp_path, monkeypatch):
    from core import dedi_boot_check as mod
    game = tmp_path / "Jeu"
    (game / "DedicatedServer").mkdir(parents=True)
    (game / "DedicatedServer" / "EmpyrionDedicated.exe").write_text(
        "", encoding="utf-8")
    launched = []
    monkeypatch.setattr(mod.subprocess, "Popen",
                        lambda *a, **k: launched.append(a))
    result = mod.run_dedi_boot_check(game, "RE2 ATL")
    assert result.ready is False
    assert launched == []
    assert any("scenario introuvable" in i for i in result.issues)


def test_temp_scenario_install_copies_and_is_replaceable(tmp_path):
    # le moteur ne charge que Content/Scenarios : la copie de travail y est
    # installee le temps du boot, marquee pour ne jamais ecraser un vrai
    # scenario homonyme
    from core import dedi_boot_check as mod
    game = tmp_path / "Jeu"
    source = tmp_path / "travail"
    (source / "Sectors").mkdir(parents=True)
    (source / "Sectors" / "Sectors.yaml").write_text("SolarSystems:\n",
                                                     encoding="utf-8")
    dest, problem = mod.install_temp_scenario(game, source)
    assert problem == "" and dest is not None
    assert (dest / "Sectors" / "Sectors.yaml").is_file()
    assert (dest / mod._MARKER).is_file()

    # relance : le dossier marque est remplace, pas empile
    dest2, problem = mod.install_temp_scenario(game, source)
    assert problem == "" and dest2 == dest
    assert (dest2 / mod._MARKER).is_file()


def test_temp_scenario_install_refuses_a_foreign_folder(tmp_path):
    from core import dedi_boot_check as mod
    game = tmp_path / "Jeu"
    foreign = mod.scenario_root(game, mod.TEMP_SCENARIO)
    foreign.mkdir(parents=True)
    (foreign / "Sectors").mkdir()
    (foreign / "Sectors" / "Sectors.yaml").write_text("x: 1\n",
                                                      encoding="utf-8")
    dest, problem = mod.install_temp_scenario(game, tmp_path / "travail")
    assert dest is None
    assert "non cree par" in problem
    assert (foreign / "Sectors" / "Sectors.yaml").is_file()   # rien efface


def test_dedi_boot_on_working_copy_installs_then_cleans(tmp_path,
                                                        monkeypatch):
    # chemin complet sans jeu reel : Popen simule, le log simule atteste le
    # scenario jetable, et la copie installee doit avoir disparu a la fin
    from core import dedi_boot_check as mod
    game = tmp_path / "Jeu"
    (game / "DedicatedServer").mkdir(parents=True)
    (game / "DedicatedServer" / "EmpyrionDedicated.exe").write_text(
        "", encoding="utf-8")
    source = tmp_path / "travail"
    source.mkdir()
    (source / "Sectors").mkdir()
    (source / "Sectors" / "Sectors.yaml").write_text("SolarSystems:\n",
                                                     encoding="utf-8")

    class FakeProc:
        pid = 4242
        def poll(self):
            return None

    source_log = mod.scenario_root(game, mod.TEMP_SCENARIO)

    def fake_popen(args, **kwargs):
        log = Path(args[args.index("-logFile") + 1])
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(
            f"Copying Sectors.yaml from {source_log.as_posix()}/Sectors to "
            "C:/Saves/x\nLoaded sector file x with 128 playfields\n"
            "Server started listening on port 33000\n", encoding="utf-8")
        return FakeProc()

    monkeypatch.setattr(mod.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(mod, "_kill_tree", lambda pid: None)
    result = mod.run_dedi_boot_check(game, "", timeout_s=5.0,
                                     source_root=source)
    assert result.ready is True
    assert result.playfields == 128
    assert result.issues == []
    assert not source_log.exists()          # copie jetable supprimee


def test_dialog_export_csv(qapp, tmp_path, monkeypatch):
    # le bouton export ecrit l'arbre complet en CSV point-virgule BOM
    from core.launch_check import LaunchIssue
    from gui.launch_check_dialog import LaunchCheckDialog
    dlg = LaunchCheckDialog(None, working_root=str(tmp_path))
    assert dlg.btn_export.isEnabled() is False          # rien a exporter
    dlg._on_done([LaunchIssue("sectors", "Sectors/x.bak", 0, "error",
                              "fichier etranger")], [], 5, True)
    assert dlg.btn_export.isEnabled() is True
    out = tmp_path / "bilan.csv"
    monkeypatch.setattr(
        "gui.launch_check_dialog.QFileDialog.getSaveFileName",
        staticmethod(lambda *a, **k: (str(out), "")))
    dlg._export_csv()
    assert out.is_file()
    raw = out.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")               # BOM Excel
    lines = raw.decode("utf-8-sig").strip().splitlines()
    assert len(lines) == 2                              # entete + 1 ligne
    assert "Fichier" in lines[0] and "x.bak" in lines[1]


def test_dialog_construction(qapp, tmp_path):
    from gui.launch_check_dialog import LaunchCheckDialog
    dlg = LaunchCheckDialog(None, working_root=str(tmp_path))
    assert dlg.tree.columnCount() == 4
    assert dlg.btn_run.isEnabled()


def test_dialog_results_slot(qapp, tmp_path):
    from core.launch_check import LaunchIssue
    from core.yaml_game_check import YamlFinding
    from gui.launch_check_dialog import LaunchCheckDialog
    dlg = LaunchCheckDialog(None, working_root=str(tmp_path))
    dlg._on_done([LaunchIssue("sectors", "Sectors/Sectors.yaml.bak", 0,
                              "error", "fichier etranger")],
                 [YamlFinding("Playfields/X/playfield_static.yaml", 3, 12,
                              "boom")], 42, True)
    assert dlg.tree.topLevelItemCount() == 2
    assert dlg.tree.topLevelItem(0).text(1) == "Bloquant"
    assert str(42) in dlg.status_label.text()
    assert dlg.btn_run.isEnabled()
    # moteur saute : mention ajoutee, arbre conserve
    dlg._on_done([], [], 0, False)
    assert "Outils" in dlg.status_label.text() or "Tools" in dlg.status_label.text()
    dlg._on_fail(RuntimeError("x"))
    assert dlg.btn_run.isEnabled()


def test_dialog_connected_run(qapp, tmp_path, monkeypatch):
    # chemin CONNECTE (regle 09/10) : _run reel + thread + signal — le slot
    # direct planquait silencieusement (tuple vs arguments, vecu 11/10 au
    # premier smoke) ; on monkeypatche les moteur et checks pour la vitesse
    import core.yaml_game_check as mod_ygc
    import gui.launch_check_dialog as mod_dlg
    from core.launch_check import LaunchIssue

    root = _build_scenario(tmp_path)
    # run_launch_checks est importe EN TETE du module dialogue ; les deux
    # autres en fonction-level dans le worker (module source)
    monkeypatch.setattr(mod_dlg, "run_launch_checks",
                        lambda r, v: [LaunchIssue("sectors", "a.bak", 0,
                                                  "error", "etranger")])
    monkeypatch.setattr(mod_ygc, "ensure_checker", lambda: Path("fake.exe"))
    monkeypatch.setattr(mod_ygc, "run_yaml_check",
                        lambda c, dirs, mode="yaml": ([], 7))

    dlg = mod_dlg.LaunchCheckDialog(None, working_root=str(root))
    dlg.chk_production.setChecked(False)
    dlg._run()
    deadline = __import__("time").time() + 30
    while dlg._running and __import__("time").time() < deadline:
        qapp.processEvents()
        __import__("time").sleep(0.02)
    assert not dlg._running
    assert dlg.tree.topLevelItemCount() == 1
    assert dlg.tree.topLevelItem(0).text(0) == "a.bak"
    # 7 fichiers x 2 modes moteur (yaml + ecf)
    assert "14" in dlg.status_label.text()
    assert dlg.btn_run.isEnabled()


def test_numeric_without_type_on_ref_block(tmp_path):
    """Vecu 18/10 : lignes numeriques nues sur des blocs Ref (5 ThrusterForce
    + 2 HitPoints materialisees par l'equilibrage) — lues en string par le
    jeu ('Error converting property'), propulseurs sans poussee, et
    INVISIBLES au boot dedie qui n'instancie pas le monde. Le bilan les
    signale ; blocs avec TemplateRoot ou sans Ref (la vanille ecrit elle-meme
    'Range: 200' nu) non signales."""
    from core.launch_check import _check_numeric_types
    cdir = tmp_path / "Content" / "Configuration"
    cdir.mkdir(parents=True)
    (cdir / "BlocksConfig.ecf").write_text(
        "{ +Block Id: 455, Name: Thr, Ref: ThrBase\n"
        "  HitPoints: 4050\n"
        "}\n"
        "{ Block Id: 1, Name: Tpl\n"
        "  TemplateRoot: TBase\n"
        "  HitPoints: 100\n"
        "}\n"
        "{ Block Id: 2, Name: SansRef\n"
        "  HitPoints: 100\n"
        "}\n"
        "{ Block Id: 3, Name: Typed\n"
        "  HitPoints: 200, type: int, display: true\n"
        "}\n", encoding="utf-8")
    issues = _check_numeric_types(tmp_path)
    assert len(issues) == 1
    assert issues[0].check == "types"
    assert issues[0].severity == "warning"
    assert "HitPoints" in issues[0].message


# ---------------------------------------------------------------------------
# ondes de spawn (core/spawn_waves.py branche dans run_launch_checks) :
# patrouilles actives sans base -> warning W310 ; geantes gazeuses [0,0]
# volontaires et zones de taux a liste mixte -> JAMAIS alertees
# ---------------------------------------------------------------------------

ACTIVE_PATROL = """PlayfieldType: Temperate

DroneSpawning:
    Random:
        - DronesMinMax: [ 2, 3 ]
          CenterX: 100
"""


def test_launch_check_spawn_patrol_without_base(tmp_path):
    root = _build_scenario(tmp_path)
    pf = root / "Playfields" / "EdenHive"
    pf.mkdir()
    (pf / "playfield_static.yaml").write_text(ACTIVE_PATROL,
                                              encoding="utf-8")
    issues = run_launch_checks(root, "")
    spawn = [i for i in issues if i.check == "spawn"]
    assert len(spawn) == 1
    assert spawn[0].severity == "warning"
    assert "[W310]" in spawn[0].message
    assert spawn[0].path == "Playfields/EdenHive/playfield_static.yaml"


def test_launch_check_spawn_clean_playfields(tmp_path):
    root = _build_scenario(tmp_path)
    assert [i for i in run_launch_checks(root, "") if i.check == "spawn"] == []


def _write_blocks_config(path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_ref_must_target_an_earlier_block(tmp_path):
    # le chargeur ECF resout les Ref au fil du fichier : cible APRES = fatal
    # client (vecu 27/10 : 352 NRE) ; l'ordre vanille place la cible avant
    root = _build_scenario(tmp_path)
    conf = root / "Content" / "Configuration"
    _write_blocks_config(conf / "BlocksConfig.ecf", (
        "{ Block Name: B\n"
        "  Ref: A\n"
        "}\n"
        "\n"
        "{ Block Name: A\n"
        "  Mass: 1, type: float\n"
        "}\n"))
    issues = [i for i in run_launch_checks(root, "") if i.check == "engine"
              and "Ref:" in i.message]
    assert len(issues) == 1 and "APRÈS" in issues[0].message

    # ordre correct : plus aucune alerte Ref
    _write_blocks_config(conf / "BlocksConfig.ecf", (
        "{ Block Name: A\n"
        "  Mass: 1, type: float\n"
        "}\n"
        "\n"
        "{ Block Name: B\n"
        "  Ref: A\n"
        "}\n"))
    issues = [i for i in run_launch_checks(root, "") if i.check == "engine"
              and "Ref:" in i.message]
    assert issues == []


def test_ref_target_must_exist(tmp_path):
    root = _build_scenario(tmp_path)
    _write_blocks_config(root / "Content" / "Configuration" / "BlocksConfig.ecf",
                         "{ Block Name: B\n  Ref: GhostBlock\n}\n")
    issues = [i for i in run_launch_checks(root, "")
              if i.severity == "error" and "GhostBlock" in i.message]
    # _check_blocks (bloc ignore) + _check_ref_order (cible manquante)
    assert len(issues) == 2
    assert all("GhostBlock" in i.message for i in issues)


def test_idmapping_flags_blocks_missing_from_config(tmp_path):
    from test_epb_blueprint import build_epb
    root = _build_scenario(tmp_path)
    _write_blocks_config(
        root / "Content" / "Configuration" / "BlocksConfig.ecf",
        "{ Block Name: BlockConnu\n  Mass: 1, type: float\n}\n")
    build_epb(root / "Prefabs" / "T.epb",
              mapping={1: "BlockConnu", 2: "BlockAbsent"})
    issues = [i for i in run_launch_checks(root, "")
              if i.check == "prefabs" and "BlockAbsent" in i.message]
    assert len(issues) == 1
    assert "1 prefab(s)" in issues[0].message
    assert "BlockConnu" not in issues[0].message


def test_idmapping_flags_library_blueprint_missing_vanilla_block(tmp_path):
    from test_epb_blueprint import build_epb
    root = _build_scenario(tmp_path)
    _write_blocks_config(
        root / "Content" / "Configuration" / "BlocksConfig.ecf",
        "{ Block Name: BlockConnu\n  Mass: 1, type: float\n}\n")
    steam = tmp_path / "steamapps"
    content = steam / "common" / "Game" / "Content"
    vconf = content / "Configuration"
    vconf.mkdir(parents=True)
    (vconf / "BlocksConfig.ecf").write_text(
        "{ Block Name: BlockVanille\n  Mass: 1, type: float\n}\n",
        encoding="utf-8")
    (content / "Prefabs").mkdir()
    bp = steam / "common" / "Game" / "Saves" / "Blueprints" / "BP"
    bp.mkdir(parents=True)
    build_epb(bp / "BP.epb",
              mapping={1: "BlockVanille", 2: "BlockAutreMod"})
    issues = [i for i in run_launch_checks(root, str(content))
              if "bibliotheque" in i.path]
    assert len(issues) == 1
    assert "BlockVanille" in issues[0].message
    assert "BlockAutreMod" not in issues[0].message


def test_block_groups_duplicates_and_unknown(tmp_path):
    root = _build_scenario(tmp_path)
    _write_blocks_config(
        root / "Content" / "Configuration" / "BlocksConfig.ecf",
        "{ Block Name: BlockA\n  Mass: 1, type: float\n}\n"
        "\n"
        "{ Block Name: BlockB\n  Mass: 1, type: float\n}\n")
    conf = root / "Content" / "Configuration"
    conf.mkdir(parents=True, exist_ok=True)
    (conf / "BlockGroupsConfig.ecf").write_text(
        ' { BlockGroup Name: G1\n'
        '   MaxCount: 4\n'
        '   Blocks: "BlockA,BlockB"\n'
        ' }\n'
        '\n'
        ' { BlockGroup Name: G2\n'
        '   MaxCount: 2\n'
        '   Blocks: "BlockB,BlockGhost"\n'
        ' }\n', encoding="utf-8")
    issues = [i for i in run_launch_checks(root, "")
              if i.check == "blockgroups"]
    dup = [i for i in issues if "deja dans" in i.message]
    unk = [i for i in issues if "introuvable" in i.message]
    assert len(dup) == 1 and "'G1'" in dup[0].message and "'G2'" in dup[0].message
    assert len(unk) == 1 and "BlockGhost" in unk[0].message


def test_compound_without_subdesc_is_flagged(tmp_path):
    root = _build_scenario(tmp_path)
    pf = root / "Playfields" / "Pf1"
    body = (
        "POIs:\n"
        "    - Name: [ SomePOI ]\n"
        "      Position:\n"
        "         PosXZMinMax: [750, 2500]\n"
        "      Compound:\n"
        "        CountMinMax: [1, 1]\n"
        "        Name: [CompoundX, CompoundX]\n"
        "        DistanceMinMax: [100, 150]\n")
    (pf / "space_dynamic.yaml").write_text(body, encoding="utf-8")
    issues = [i for i in run_launch_checks(root, "")
              if "Compound POI 'CompoundX'" in i.message]
    # le jeu logue par OCCURRENCE : la liste cite CompoundX deux fois
    assert len(issues) == 2

    # sous-descripteur declare : plus aucune alerte
    body += (
        "\n    - Type: BA_Alien\n"
        "      Name: [CompoundX]\n"
        "      IsCompoundSubDesc: True\n")
    (pf / "space_dynamic.yaml").write_text(body, encoding="utf-8")
    issues = [i for i in run_launch_checks(root, "")
              if "Compound POI 'CompoundX'" in i.message]
    assert issues == []
