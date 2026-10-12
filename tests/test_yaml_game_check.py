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

"""Verification YAML au moteur du jeu : parsing du protocole TSV de
tools/yamlcheck, run_yaml_check avec un faux binaire, construction du
dialogue (PyQt6 : exception en slot = crash natif) + chemin connecte, et
test d'integration du vrai exe si publie."""

import subprocess
import sys

import pytest

from core.i18n import t
from core.yaml_game_check import (YamlFinding, locate_checker,
                                  parse_check_output, run_yaml_check)

FAKE_OUTPUT = (
    "BROKEN\tPlayfields/Starter_Roggery_V2/playfield_static.yaml\t2043\t132\t"
    "(Line: 2043, Col: 132): While parsing a block mapping, did not find expected key.\n"
    "SUMMARY\t558\t1\t35\n"
)


def test_parse_output():
    findings, scanned = parse_check_output(FAKE_OUTPUT)
    assert scanned == 558
    assert len(findings) == 1
    f = findings[0]
    assert f.rel_path == "Playfields/Starter_Roggery_V2/playfield_static.yaml"
    assert (f.line, f.col) == (2043, 132)
    assert "did not find expected key" in f.message


def test_parse_output_empty_and_garbage():
    findings, scanned = parse_check_output("")
    assert findings == [] and scanned == 0
    findings, scanned = parse_check_output("SUMMARY\tX\t0\t0\nBROKEN\tnon\t\tpas\tun nombre\n")
    assert scanned == 0
    assert findings == []


def test_run_with_fake_checker(tmp_path):
    # faux binaire = python -c qui imprime le protocole : run_yaml_check
    # doit sous-processer, parser et cumuler par racine
    fake = tmp_path / "root_a"
    fake.mkdir()
    code = ("import sys; print('BROKEN\\ta.yaml\\t5\\t9\\tboom'); "
            "print('SUMMARY\\t7\\t1\\t0')")
    findings, scanned = run_yaml_check(
        checker=None, scan_dirs=[str(fake)],
        command=[sys.executable, "-c", code])
    assert scanned == 7
    assert findings == [YamlFinding("a.yaml", 5, 9, "boom")]


def test_locate_checker_dev_paths(tmp_path, monkeypatch):
    # ni publish ni build -> None (pas de plantage) ; puis publish simule
    import core.yaml_game_check as mod
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(mod, "__file__", str(tmp_path / "core" / "yaml_game_check.py"))
    assert locate_checker() is None
    pub = tmp_path / "tools" / "yamlcheck" / "publish" / "yamlcheck.exe"
    pub.parent.mkdir(parents=True)
    pub.write_bytes(b"MZ")
    found = locate_checker()
    assert found is not None and found.is_file()


def test_dialog_construction(qapp, tmp_path):
    from gui.yaml_check_dialog import YamlCheckDialog
    dlg = YamlCheckDialog(None, working_root=str(tmp_path))
    assert dlg.path_edit.text() == str(tmp_path)
    assert dlg.tree.columnCount() == 4
    assert dlg.btn_run.isEnabled()
    # sans production configuree, la case est grisee
    assert not dlg.chk_production.isEnabled()


def test_dialog_results_slot(qapp, tmp_path):
    # chemin connecte (regle 09/10 : le test de construction seul n'attrape
    # pas un crash en slot) : remplit l'arbre depuis les findings
    from gui.yaml_check_dialog import YamlCheckDialog
    dlg = YamlCheckDialog(None, working_root=str(tmp_path))
    dlg._on_done([YamlFinding("Playfields/X/playfield_static.yaml", 18, 132,
                              "did not find expected key")], 42)
    assert dlg.tree.topLevelItemCount() == 1
    item = dlg.tree.topLevelItem(0)
    assert item.text(0) == "Playfields/X/playfield_static.yaml"
    assert (item.text(1), item.text(2)) == ("18", "132")
    assert str(42) in dlg.status_label.text() and "1" in dlg.status_label.text()
    assert dlg.btn_run.isEnabled()
    # cas tout vert
    dlg.tree.clear()
    dlg._on_done([], 10)
    assert dlg.tree.topLevelItemCount() == 0
    assert t("yamlcheck.all_ok", n=10).split(":")[0] in dlg.status_label.text()
    # echec (outil absent, dotnet absent...)
    dlg._on_fail(RuntimeError("dotnet introuvable"))
    assert t("yamlcheck.failed") in dlg.status_label.text()
    assert dlg.btn_run.isEnabled()


def test_dialog_run_needs_scenario(qapp):
    from gui.yaml_check_dialog import YamlCheckDialog
    dlg = YamlCheckDialog(None, working_root="")
    dlg._run()
    assert dlg.status_label.text() == t("yamlcheck.need_scenario")
    assert dlg.btn_run.isEnabled()


@pytest.mark.skipif(locate_checker() is None,
                    reason="yamlcheck.exe non publie sur ce poste")
def test_integration_real_checker_yaml(tmp_path):
    # scenario synthetique : un bon yaml, un casse (guillemets bruts dans un
    # scalaire multilignes = la cassure vecue 11/10), un fichier '+' ignore
    good = tmp_path / "Playfields" / "Good"
    good.mkdir(parents=True)
    (good / "playfield_static.yaml").write_text(
        "---\nPlayfieldType: Planet\nDifficulty: 2\n", encoding="utf-8")
    bad = tmp_path / "Playfields" / "Bad"
    bad.mkdir(parents=True)
    (bad / "playfield_static.yaml").write_text(
        'Description: "[sup]ligne un\n\nphrase " citee " au milieu [-][/sup]"\n'
        'PlayfieldType: Planet\n', encoding="utf-8")
    (bad / "+backup_playfield_static.yaml").write_text(
        "a: [1,\n", encoding="utf-8")
    findings, scanned = run_yaml_check(locate_checker(), [str(tmp_path)],
                                       mode="yaml")
    assert scanned == 2
    broken = [f.rel_path for f in findings]
    assert broken == ["Playfields\\Bad\\playfield_static.yaml"]
    assert findings[0].line == 3


@pytest.mark.skipif(locate_checker() is None,
                    reason="yamlcheck.exe non publie sur ce poste")
def test_integration_real_checker_ecf(tmp_path):
    # structure ECF : les cas TOLERES par le jeu ne sont pas signales
    # (accolade non fermee en EOF — vecu sur deux scenarios officiels,
    # quote non fermee ligne-scopee, banniere niveau 0, cle avec espaces,
    # segment sans ':' apres une paire, commentaire //) ; le junk sans
    # ':' dans un corps et le '}' en trop restent detectes
    conf = tmp_path / "Content" / "Configuration"
    conf.mkdir(parents=True)
    (conf / "Good.ecf").write_text(
        "{ Blocks\n"
        "{ +Block Id: 412, Name: Test\n"
        "  Mass: 100, Health: 500\n"
        "  ChildShapes: WallMediumDouble, RampBDouble\n"
        "}\n"
        "}==== banner colle ====\n"
        "=== Material Extended 6 ====\n"
        "// commentaire double-slash\n", encoding="utf-8")
    (conf / "Tolerated.ecf").write_text(
        "{ Blocks\n"
        "{ +Block Id: 413, Name: Unclosed\n"
        "  Name_1: MoneyCard, param1: \"5,10\"\n"
        "  :Icon for Smashicons, display: true\n"
        "  Count: \"2,6\n"
        "  Ruthenium Erz: 30\n", encoding="utf-8")
    (conf / "Broken.ecf").write_text(
        "{ Blocks\n"
        "{ +Block Id: 414, Name: Broken\n"
        "  Id 999\n"
        "  Count: 1\n"
        "}}\n", encoding="utf-8")
    findings, scanned = run_yaml_check(locate_checker(), [str(tmp_path)],
                                       mode="ecf")
    assert scanned == 3
    broken = {f.rel_path: f for f in findings}
    assert set(broken) == {"Content\\Configuration\\Broken.ecf"}
    assert broken["Content\\Configuration\\Broken.ecf"].line == 3
