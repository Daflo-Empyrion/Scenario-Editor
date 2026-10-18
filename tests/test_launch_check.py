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
