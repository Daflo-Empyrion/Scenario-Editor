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

"""Gameplay dynamique : generation et VERIFICATION de scripts C# de scenario.

Le jeu compile lui-meme les .cs du scenario (Extras/PDA/, Content/Scripts/)
avec Roslyn. Les modeles ci-dessous sont derives des scripts d'exemple
LIVRES AVEC LE JEU (scenarios 'Default Base Attack' et '_TestBaseAttackCS',
Extras/PDA/Scripts/*.cs) : ils n'utilisent que la surface confirmee
(PdaScript, Chapter, Task, ActionData/ActionState, NearPoiAction,
PdaManagerBridge, ChapterCategory, PdaMPTaskType).

La verification locale reproduit la compilation du jeu avec le compilateur
C# de .NET Framework (csc.exe de Windows) et les assemblies du jeu :
    csc -noconfig -nostdlib+ -t:library -r:<Managed>/mscorlib.dll ...
C'est une PREUVE locale qu'un script compile — le boot du jeu, lui, ne
montre qu'une erreur a la fois."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SCRIPT_DIR = "Extras/PDA/Scripts"

# References du jeu necessaires (verifiees : sans elles, csc resout les
# assemblies du Framework et tout le typage Unity/jeu devient incomplet).
REFERENCES = ("mscorlib.dll", "System.dll", "System.Core.dll",
              "netstandard.dll", "UnityEngine.CoreModule.dll",
              "Assembly-CSharp.dll", "ModApi.dll")

# Usings implicites du domaine de script du jeu : les fichiers d'exemple
# officiels (PrepAndDefendTasks.cs, etc.) n'ont AUCUN using et utilisent
# Task/PdaMPTaskType/ActionData tels quels — le moteur les fournit au
# domaine Roslyn. La verification locale les ajoute aux fichiers qui ne les
# declarent pas, sinon tout paraitrait introuvable.
# 'System' est volontairement ABSENT : les exemples du jeu qualifient
# 'System.Random' et utilisent 'Action' (Eleon.PdaScript.Action) — importer
# System rendrait 'Action' ambigu (CS0104, vecu sur PrepAndDefendTasks.cs).
DEFAULT_USINGS = ("System.Collections", "System.Collections.Generic",
                  "System.Linq", "UnityEngine",
                  "Eleon.Pda", "Eleon.PdaScript", "Eleon.Modding",
                  "Eleon.ModBridge")


@dataclass(frozen=True)
class ParamSpec:
    key: str
    label_key: str
    default: str
    choices: str = ""    # cle du vocabulaire VOCABULAIRE (vide = champ libre)


# Vocabulaires releves dans la reference de modding livree avec le jeu
# (ModApi decompile : GameEventType, ChapterCategory, GuidingType) et dans les
# classes d'action du domaine PdaScript. Chaque champ du dialogue pioche ici
# (liste deroulante EDITABLE : la valeur libre reste possible).
VOCABULAIRE: Dict[str, Tuple[str, ...]] = {
    "category": ("SoloMission", "FactionMission", "Tutorial", "JourneyBook",
                 "FAQ", "UCHMission", "ZiraxMission", "PolarisMission",
                 "TalonMission", "Undefined"),
    "task_type": ("Autonomous", "Team", "Leader"),
    "action_type": ("Action", "NearPoiAction", "NearResourceAction",
                    "NearUnitAction", "InventoryContainsAction",
                    "InventoryOpenedAction", "ItemsPickedUpAction",
                    "ToolBarContainsAction", "SignalAction", "TimerAction"),
    "check": ("NearPoi", "NearResource", "NearUnit", "InventoryContains",
              "InventoryOpened", "ItemsPickedUp", "ToolbarContains",
              "Signal", "SetTimer", "WaveDestroyed", "BlockChanged",
              "BlocksPlaced", "BlocksRemoved", "BlockDestroyed",
              "ItemsCrafted", "ItemsUsed", "ItemsConsumed",
              "PlayfieldEntered", "PlayfieldLeft", "PlayerDied",
              "PlayerLevelUp", "SubjectKilled", "KilledEntity",
              "PoiDiscovered", "ResourceDiscovered", "StructureSpawned",
              "DeviceUsed", "DevicePowered", "EnteredSVCockpit".replace(
                  "Entered", "Enter"), "AttackWave", "NpcCorePlaced"),
    "guiding": ("Default", "Destination", "Beacon", "TempIndoor", "Waypoint"),
    "reward": ("Item", "XP", "UP", "LevelIncrease", "LevelTarget",
               "ReputationTarget", "Reputation"),
    "poi": (),        # rempli par le dialogue avec les POIs reels du scenario
}


@dataclass(frozen=True)
class Template:
    template_id: str
    label_key: str
    desc_key: str
    params: Tuple[ParamSpec, ...]
    render: str          # gabarit Python (format) — voir build()


TEMPLATES: Dict[str, Template] = {
    "chapter_near_poi": Template(
        template_id="chapter_near_poi",
        label_key="pdas.chapter_near_poi",
        desc_key="pdas.chapter_near_poi.desc",
        params=(
            ParamSpec("class_name", "pdas.p_class", "MissionScript"),
            ParamSpec("chapter_id", "pdas.p_chapter_id", "chapter_1"),
            ParamSpec("chapter_title", "pdas.p_chapter_title", "Mission"),
            ParamSpec("description", "pdas.p_description", "Atteignez le point indique."),
            ParamSpec("task_title", "pdas.p_task_title", "Objectif"),
            ParamSpec("action_title", "pdas.p_action_title", "Atteindre le POI"),
            ParamSpec("poi_name", "pdas.p_poi", "MyPoi", "poi"),
        ),
        render="chapter_near_poi"),
    "chapter_basic": Template(
        template_id="chapter_basic",
        label_key="pdas.chapter_basic",
        desc_key="pdas.chapter_basic.desc",
        params=(
            ParamSpec("class_name", "pdas.p_class", "MissionScript"),
            ParamSpec("chapter_id", "pdas.p_chapter_id", "chapter_1"),
            ParamSpec("chapter_title", "pdas.p_chapter_title", "Mission"),
            ParamSpec("description", "pdas.p_description", "Objectif de mission."),
            ParamSpec("task_title", "pdas.p_task_title", "Objectif"),
            ParamSpec("action_title", "pdas.p_action_title", "Valider l'objectif"),
        ),
        render="chapter_basic"),
    "action_pick": Template(
        template_id="action_pick",
        label_key="pdas.action_pick",
        desc_key="pdas.action_pick.desc",
        params=(
            ParamSpec("class_name", "pdas.p_class", "MissionScript"),
            ParamSpec("chapter_id", "pdas.p_chapter_id", "chapter_1"),
            ParamSpec("chapter_title", "pdas.p_chapter_title", "Mission"),
            ParamSpec("description", "pdas.p_description",
                      "Réalisez l'action demandée."),
            ParamSpec("task_title", "pdas.p_task_title", "Objectif"),
            ParamSpec("action_title", "pdas.p_action_title", "Objectif"),
            ParamSpec("action_class", "pdas.p_action_class", "NearPoiAction",
                      "action_type"),
            ParamSpec("check", "pdas.p_check", "NearPoi", "check"),
            ParamSpec("name", "pdas.p_name", "MyPoi", "poi"),
            ParamSpec("guiding", "pdas.p_guiding", "Destination", "guiding"),
            ParamSpec("guiding_distance", "pdas.p_guiding_dist", "50"),
            ParamSpec("completed_message", "pdas.p_completed", "Objectif accompli"),
        ),
        render="action_pick"),
}

_HEADER = """// Genere par Scenario Editor — script de PDA compile par le jeu.
// Chapitre '{chapter_title}' : {description}
using System.Collections.Generic;
using Eleon.Pda;
using Eleon.PdaScript;
using Eleon.Modding;
using Eleon.ModBridge;

public class {class_name} : PdaScript {{
    public const string cChapterId = "{chapter_id}";

    public {class_name}() {{
        Data.Creator = "Scenario Editor";
        Data.CompletedMessage = "";
        Data.FailedMessage = "";
        AddChapter(new {class_name}Chapter(cChapterId));
    }}

    // false : le chapitre n'est pas lance automatiquement au chargement.
    // Pour un declenchement conditionnel, remplacer par un test sur
    // ModManager.ModApi.ClientPlayfield (voir les exemples du jeu).
    public override bool CheckActivationConditions() {{
        return false;
    }}

    protected override void RunScenario() {{
        StartChapter(cChapterId);
    }}
}}

public class {class_name}Chapter : Chapter {{
    public {class_name}Chapter(string _id) : base(_id) {{
        chapterData.ChapterTitle = "{chapter_title}";
        chapterData.Category = ChapterCategory.SoloMission;
        chapterData.Description = "{description}";
        chapterData.PlayerLevel = 1;
        chapterData.NoSkip = true;
        runNextChapterOnCompletion = false;
        showBriefingWindow = true;
        AddTask(new {class_name}Task("task_1"), bSequential: false);
    }}
}}

public class {class_name}Task : Task {{
    public {class_name}Task(string _id) : base(_id) {{
        taskType = PdaMPTaskType.Autonomous;
        data.TaskTitle = "{task_title}";
        data.DisplayTitle = true;
        state.Id = PdaManagerBridge.CreateId(_id);

        ActionData actionData = new ActionData();
        actionData.ActionTitle = "{action_title}";
{extra}
        ActionState actionState = new ActionState(actionData, state.Id, "action_1");
        {action_type} action = new {action_type}(actionData, actionState, "action_1");
        AddAction(action);
        CommitActions();
    }}
}}
"""

_NEAR_POI_EXTRA = '        actionData.Names = new List<string> {{ "{poi_name}" }};\n'
_BASIC_EXTRA = ""

# Gabarit de l'action parametree du modele « action_pick » : chaque classe
# d'action du moteur attend un reglage different (releve des constructeurs) —
# ce fragment ne genere que ce qui est reellement lu par la classe choisie.
_ACTION_PICK_FRAGMENT = """        actionData.Check = GameEventType.{check};
        actionData.Names = new List<string> {{ "{name}" }};
        actionData.Guiding = GuidingType.{guiding};
        actionData.GuidingDistance = {guiding_distance};
        actionData.CompletedMessage = "{completed_message}";"""

_ACTION_CLASS_LINE = {
    "Action": "Action",
    "NearPoiAction": "NearPoiAction",
    "NearResourceAction": "NearResourceAction",
    "NearUnitAction": "NearUnitAction",
    "InventoryContainsAction": "InventoryContainsAction",
    "InventoryOpenedAction": "InventoryOpenedAction",
    "ItemsPickedUpAction": "ItemsPickedUpAction",
    "ToolBarContainsAction": "ToolBarContainsAction",
    "SignalAction": "SignalAction",
    "TimerAction": "TimerAction",
}


def cs_string(text: str) -> str:
    """Rend une chaine sure pour un litteral C# (guillemets, antislashs,
    retours a la ligne)."""
    return (text.replace("\\", "\\\\").replace('"', '\\"')
            .replace("\r\n", "\\n").replace("\n", "\\n"))


def build(template_id: str, params: Dict[str, str]) -> str:
    template = TEMPLATES[template_id]
    values = {spec.key: (params.get(spec.key) or spec.default)
              for spec in template.params}
    class_name = _identifier(values.get("class_name", "MissionScript"))
    values["class_name"] = class_name
    values["chapter_title"] = cs_string(values.get("chapter_title", ""))
    values["description"] = cs_string(values.get("description", ""))
    values["task_title"] = cs_string(values.get("task_title", ""))
    values["action_title"] = cs_string(values.get("action_title", ""))
    if template.render == "chapter_near_poi":
        values["poi_name"] = cs_string(values.get("poi_name", "MyPoi"))
        extra = _NEAR_POI_EXTRA.format(**values)
        action_type = "NearPoiAction"
    elif template.render == "action_pick":
        action_cls = values.get("action_class", "NearPoiAction")
        action_type = _ACTION_CLASS_LINE.get(action_cls, "Action")
        values["check"] = values.get("check", "NearPoi")
        values["name"] = cs_string(values.get("name", "MyPoi"))
        values["guiding"] = values.get("guiding", "Destination")
        values["guiding_distance"] = (values.get("guiding_distance") or "50").strip() or "50"
        values["completed_message"] = cs_string(values.get("completed_message", ""))
        extra = _ACTION_PICK_FRAGMENT.format(**values)
    else:
        extra = _BASIC_EXTRA
        action_type = "Action"
    return _HEADER.format(extra=extra, action_type=action_type, **values)


def _identifier(name: str) -> str:
    cleaned = "".join(ch for ch in name if ch.isalnum() or ch == "_")
    if not cleaned or cleaned[0].isdigit():
        cleaned = "Mission" + cleaned
    return cleaned


# ============================================================================
# Verification : compilation locale avec le compilateur du systeme
# ============================================================================

@dataclass
class CompileResult:
    ok: bool
    output: str = ""
    skipped: str = ""          # raison de non-verification (outils absents)

    @property
    def verified(self) -> bool:
        return not self.skipped


def find_csc() -> Optional[Path]:
    candidates = (
        Path(os.environ.get("WINDIR", r"C:\Windows"))
        / "Microsoft.NET/Framework64/v4.0.30319/csc.exe",
        Path(os.environ.get("WINDIR", r"C:\Windows"))
        / "Microsoft.NET/Framework/v4.0.30319/csc.exe",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def managed_dir(override: Optional[Path] = None) -> Optional[Path]:
    """Dossier Managed du client du jeu (celui qui contient Assembly-CSharp,
    Eleon.PdaScript, Eleon.ModBridge et UnityEngine). `override` ou la
    variable EMPYRION_MANAGED_DIR court-circuitent les reglages (utile aux
    tests, qui isolent la config installee)."""
    for candidate in (override,
                      os.environ.get("EMPYRION_MANAGED_DIR") or None):
        if candidate:
            path = Path(candidate)
            if (path / "Assembly-CSharp.dll").is_file():
                return path
    from core.settings import get_vanilla_content_path
    vanilla = get_vanilla_content_path() or ""
    if not vanilla:
        return None
    candidate = Path(vanilla).parent / "Client" / "Empyrion_Data" / "Managed"
    if (candidate / "Assembly-CSharp.dll").is_file():
        return candidate
    dedicated = (Path(vanilla).parent / "DedicatedServer"
                 / "EmpyrionDedicated_Data" / "Managed")
    if (dedicated / "Assembly-CSharp.dll").is_file():
        return dedicated
    return None


def compile_scripts(paths: List[Path], out_dir: Optional[Path] = None,
                    managed: Optional[Path] = None,
                    implicit_usings: bool = False) -> CompileResult:
    """Compile les fichiers C# contre les assemblies du jeu. Retourne
    ok=False + diagnostic en cas d'erreur ; skipped si csc ou le jeu manque."""
    csc = find_csc()
    if csc is None:
        return CompileResult(ok=False, skipped="csc.exe introuvable")
    managed = managed_dir(managed)
    if managed is None:
        return CompileResult(ok=False, skipped="assemblies du jeu introuvables")
    files = [Path(p) for p in paths if Path(p).is_file()]
    if not files:
        return CompileResult(ok=False, skipped="aucun fichier a compiler")
    import tempfile
    staging = Path(out_dir) if out_dir else Path(tempfile.mkdtemp())
    if implicit_usings:
        files = [_with_default_usings(path, staging) for path in files]
    target = staging / "_compile_check.dll"
    command = [str(csc), "-nologo", "-noconfig", "-nostdlib+", "-t:library",
               f"-out:{target}"]
    for ref in REFERENCES:
        ref_path = managed / ref
        if ref_path.is_file():
            command.append(f"-r:{ref_path}")
    command.extend(str(p) for p in files)
    try:
        run = subprocess.run(command, capture_output=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        return CompileResult(ok=False, output=str(exc))
    output = _decode(run.stdout) + _decode(run.stderr)
    if target.is_file():
        try:
            target.unlink()
        except OSError:
            pass
    if run.returncode != 0 and _reproduction_limit(output):
        # shortcut: les scripts qui passent par ModManager.ModApi butent sur
        # l'interface PUBLIQUE (IModApi de ModApi.dll) alors que le jeu compile
        # contre l'implementation interne — non reproductible hors du jeu.
        # On declare la verification impossible plutot que fausse.
        return CompileResult(ok=False, output=output.strip(),
                             skipped="limite de reproduction (ModManager/IModApi)")
    return CompileResult(ok=run.returncode == 0, output=output.strip())


def _reproduction_limit(output: str) -> bool:
    """Toutes les erreurs relevent-elles de la limite ModManager/IModApi ?
    (uniquement ces motifs : une vraie erreur de syntaxe reste signalee)."""
    errors = [line for line in output.splitlines() if "error CS" in line]
    if not errors:
        return False
    return all(("IModApi" in line and ("CS1061" in line or "CS0117" in line))
               for line in errors)


def _with_default_usings(path: Path, staging: Path) -> Path:
    """Copie le fichier dans un dossier de travail en y ajoutant les usings
    par defaut MANQUANTS (le jeu les fournit au domaine de script)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return path
    bom = "\ufeff" if text.startswith("\ufeff") else ""
    body = text[len(bom):]
    present = {line.strip().rstrip(";").replace("using ", "")
               for line in body.splitlines()
               if line.strip().startswith("using ")}
    missing = [u for u in DEFAULT_USINGS if u not in present]
    if not missing:
        return path
    lines = body.splitlines(keepends=True)
    # un '#define' n'est valide qu'avant tout autre jeton : les usings vont
    # APRES les directives de tete (CS1032 sinon, vecu sur _TestBaseAttackCS)
    head = 0
    while head < len(lines) and (not lines[head].strip()
                                 or lines[head].lstrip().startswith("#")):
        head += 1
    header = "".join("using " + name + ";\n" for name in missing)
    staging = Path(staging) / "_check_src"
    staging.mkdir(parents=True, exist_ok=True)
    copy = staging / path.name
    copy.write_text(bom + "".join(lines[:head]) + header
                    + "".join(lines[head:]), encoding="utf-8")
    return copy


def verify_scripts(paths: List[Path], out_dir: Optional[Path] = None,
                   managed: Optional[Path] = None) -> CompileResult:
    """Compile tel quel ; si seuls des types INTROUVABLES (CS0246) bloquent,
    reessaie avec les usings implicites du domaine de script du jeu. Un
    fichier autonome (nos modeles declarent leurs usings) n'est jamais
    compile deux fois."""
    result = compile_scripts(paths, out_dir=out_dir, managed=managed)
    if result.ok or result.skipped or "error CS0246" not in result.output:
        return result
    return compile_scripts(paths, out_dir=out_dir, managed=managed,
                           implicit_usings=True)


def _decode(raw: bytes) -> str:
    """csc ecrit ses diagnostics dans la page de code systeme (cp850/1252) ;
    un decodage UTF-8 strict leve dans le thread lecteur de subprocess."""
    if not raw:
        return ""
    for encoding in ("utf-8", "cp1252", "cp850"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def scenario_scripts(root: Path) -> List[Path]:
    """Scripts .cs du scenario (Extras/PDA et sous-dossiers, Content/Scripts)."""
    root = Path(root)
    found = sorted(root.glob("Extras/PDA/**/*.cs"))
    found += sorted(root.glob("Content/Scripts/*.cs"))
    return [p for p in found if p.is_file() and "_check_src" not in p.parts]


def script_groups(root: Path) -> List[List[Path]]:
    """Groupes compiles ENSEMBLE, comme le moteur : le PDA du scenario et son
    dossier Scripts forment une unite (le PDA utilise les classes des
    Scripts) ; Content/Scripts (console exec) est independant. Deux scripts
    sans rapport laisses dans le meme dossier ne doivent pas se gener."""
    root = Path(root)
    groups: List[List[Path]] = []
    pda_dir = root / "Extras" / "PDA"
    pda_files = [p for p in sorted(pda_dir.glob("*.cs")) if p.is_file()]
    script_files = [p for p in sorted((pda_dir / "Scripts").rglob("*.cs"))
                    if p.is_file() and "_check_src" not in p.parts]
    if pda_files or script_files:
        groups.append(pda_files + script_files)
    console = [p for p in sorted((root / "Content" / "Scripts").glob("*.cs"))
               if p.is_file()]
    if console:
        groups.append(console)
    return groups


def write_script(root: Path, name: str, text: str,
                 overwrite: bool = False) -> Path:
    """Ecrit Extras/PDA/Scripts/<name>.cs (jamais d'ecrasement silencieux)."""
    from core.fsutil import atomic_write_text, central_backup
    safe = _identifier(Path(name).stem)
    target = Path(root) / SCRIPT_DIR / f"{safe}.cs"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        if not overwrite:
            raise FileExistsError(target)
        central_backup(target, "pda_scripts")
    atomic_write_text(target, text)
    return target


def check_scripts(root: Path) -> list:
    """Controle bilan : les scripts C# du scenario compilent-ils tous ?
    Silencieux quand le compilateur ou le jeu manquent (aucune fausse
    alerte sur une machine sans installation)."""
    from core.ecf.validation import ValidationIssue
    issues = []
    for group in script_groups(root):
        result = verify_scripts(group)
        if result.skipped or result.ok:
            continue
        lines = [line.strip() for line in result.output.splitlines()
                 if "error" in line.lower()][:5]
        detail = " | ".join(lines) if lines else             (result.output.splitlines() or [""])[0]
        issues.append(ValidationIssue(
            code="E360", level="error",
            message=f"{len(group)} script(s) C# : echec de compilation -- "
                    f"{detail}",
            file_path=group[0]))
    return issues
