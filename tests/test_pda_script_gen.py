"""Scripts de gameplay (core/pda/script_gen.py) : generation sur les modeles
derives des exemples livres avec le jeu, et VERIFICATION de compilation
reelle (csc + assemblies du jeu, avec skip si l'installation manque)."""

from pathlib import Path

import pytest

from core.pda.script_gen import (TEMPLATES, VOCABULAIRE, build, check_scripts,
                                 compile_scripts, find_csc, managed_dir,
                                 scenario_scripts, write_script)

PARAMS = {
    "class_name": "TestMission",
    "chapter_id": "chap_test",
    "chapter_title": 'Titre "quote" \'apos\'',
    "description": "Ligne 1\nLigne 2",
    "task_title": "Objectif test",
    "action_title": "Aller au POI",
    "poi_name": "AlfaPoi",
}


def test_build_contains_params_and_escapes():
    code = build("chapter_near_poi", PARAMS)
    assert "public class TestMission : PdaScript" in code
    assert "AlfaPoi" in code
    assert "NearPoiAction" in code
    # guillemets echappes et sauts de ligne transformes en \n
    assert '\\"quote\\"' in code
    assert "Ligne 1\\nLigne 2" in code
    assert "\n" in code and "Ligne 1\nLigne 2" not in code.split("Description")[1][:80]


def test_build_basic_uses_plain_action():
    code = build("chapter_basic", PARAMS)
    assert "NearPoiAction" not in code
    assert "Action action = new Action(actionData" in code


def test_class_name_sanitized():
    code = build("chapter_basic", {"class_name": "123 Mission-x"})
    assert "public class Mission123Missionx" in code


def test_all_templates_render():
    for template_id in TEMPLATES:
        code = build(template_id, {})
        assert "PdaScript" in code and "CommitActions();" in code


def test_scenario_scripts_discovery(tmp_path):
    scripts = tmp_path / "Extras" / "PDA" / "Scripts"
    scripts.mkdir(parents=True)
    (scripts / "A.cs").write_text("class A {}", encoding="utf-8")
    other = tmp_path / "Content" / "Scripts"
    other.mkdir(parents=True)
    (other / "B.cs").write_text("class B {}", encoding="utf-8")
    found = scenario_scripts(tmp_path)
    assert [p.name for p in found] == ["A.cs", "B.cs"]


def test_write_script_no_silent_overwrite(tmp_path):
    first = write_script(tmp_path, "Mission", "class A { }")
    assert first.name == "Mission.cs"
    assert first.parent.name == "Scripts"
    with pytest.raises(FileExistsError):
        write_script(tmp_path, "Mission", "class B { }")
    second = write_script(tmp_path, "Mission", "class B { }", overwrite=True)
    assert second.read_text(encoding="utf-8") == "class B { }"


# --- compilation reelle (skip si csc ou le jeu manquent) --------------------

def _game_managed() -> "Path | None":
    """Dossier Managed du jeu, trouve SANS passer par core.settings (le
    conftest isole volontairement la config installee)."""
    import os
    override = os.environ.get("EMPYRION_MANAGED_DIR")
    if override and (Path(override) / "Assembly-CSharp.dll").is_file():
        return Path(override)
    for base in (Path(r"C:\Program Files (x86)\Steam\steamapps\common"),
                 Path(r"D:\Steam\steamapps\common"),
                 Path(r"E:\Steam\steamapps\common")):
        candidate = (base / "Empyrion - Galactic Survival" / "Client"
                     / "Empyrion_Data" / "Managed")
        if (candidate / "Assembly-CSharp.dll").is_file():
            return candidate
    return None


def _tools_available() -> bool:
    return find_csc() is not None and _game_managed() is not None


MANAGED = _game_managed()


requires_game = pytest.mark.skipif(
    not _tools_available(),
    reason="csc.exe ou assemblies du jeu absents sur cette machine")


@requires_game
def test_generated_scripts_compile(tmp_path):
    for template_id in TEMPLATES:
        target = tmp_path / f"{template_id}.cs"
        target.write_text(build(template_id, PARAMS), encoding="utf-8")
        result = compile_scripts([target], out_dir=tmp_path, managed=MANAGED)
        assert result.ok, f"{template_id} ne compile pas : {result.output[:400]}"
        assert not result.output.strip(), f"{template_id} compile avec avertissements"


@requires_game
def test_broken_script_is_reported(tmp_path):
    target = tmp_path / "Broken.cs"
    target.write_text(build("chapter_basic", {}).replace("CommitActions();",
                                                         "CommitActions("),
                      encoding="utf-8")
    result = compile_scripts([target], out_dir=tmp_path, managed=MANAGED)
    assert result.ok is False
    assert "error" in result.output.lower()


@requires_game
def test_bilan_reports_broken_scenario_script(tmp_path, monkeypatch):
    monkeypatch.setenv("EMPYRION_MANAGED_DIR", str(MANAGED))
    scripts = tmp_path / "Extras" / "PDA" / "Scripts"
    scripts.mkdir(parents=True)
    (scripts / "Broken.cs").write_text(
        build("chapter_basic", {}).replace("CommitActions();", "CommitActions("),
        encoding="utf-8")
    issues = check_scripts(tmp_path)
    assert len(issues) == 1
    assert issues[0].code == "E360" and issues[0].level == "error"
    assert issues[0].file_path == scripts / "Broken.cs"


@requires_game
def test_bilan_silent_when_scripts_compile(tmp_path, monkeypatch):
    monkeypatch.setenv("EMPYRION_MANAGED_DIR", str(MANAGED))
    scripts = tmp_path / "Extras" / "PDA" / "Scripts"
    scripts.mkdir(parents=True)
    (scripts / "Good.cs").write_text(build("chapter_basic", {}), encoding="utf-8")
    assert check_scripts(tmp_path) == []


def test_bilan_ignores_scenario_without_scripts(tmp_path):
    assert check_scripts(tmp_path) == []


# ------------------------------------------------------------------
# Vocabulaire officiel + modele « action_pick » (26/10)

def test_vocabulaire_covers_engine_enums():
    # valeurs relevees de la reference de modding livree avec le jeu
    assert "SoloMission" in VOCABULAIRE["category"]
    assert "TimerAction" in VOCABULAIRE["action_type"]
    assert "WaveDestroyed" in VOCABULAIRE["check"]
    assert "Destination" in VOCABULAIRE["guiding"]


def test_action_pick_generates_check_and_guiding():
    code = build("action_pick", {
        "action_class": "NearPoiAction", "check": "NearPoi",
        "name": "MonPoi", "guiding": "Beacon", "guiding_distance": "120",
    })
    assert "GameEventType.NearPoi" in code
    assert '"MonPoi"' in code
    assert "GuidingType.Beacon" in code
    assert "GuidingDistance = 120" in code
    assert "new NearPoiAction(" in code


@requires_game
def test_action_pick_compiles_against_game(tmp_path):
    for action in ("NearPoiAction", "InventoryContainsAction", "TimerAction",
                   "SignalAction"):
        code = build("action_pick", {"action_class": action})
        target = tmp_path / f"Pick_{action}.cs"
        target.write_text(code, encoding="utf-8")
        result = compile_scripts([target], out_dir=tmp_path, managed=MANAGED)
        assert result.ok, f"{action}: {result.output[:300]}"
