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
"""Test de chargement REEL : boot du serveur dedie sur le scenario dans une
sauvegarde jetable. Le dedi relit TOUTE la configuration (yaml, ecf, secteurs,
prefabs) avec le vrai moteur — c'est le validateur ultime, a 100 % fidele par
construction. La configuration passe par un yaml JETABLE (-dedicated <chemin>,
mecanism documente dans le template officiel : « add -dedicated
MyDedicatedConfig.yaml ») : la config reelle de l'utilisateur n'est jamais
touchee, ports et sauvegarde dedies au test, supprimes apres.

Sequence de boot observee dans un vrai DediLog : « Started a new game » ->
« Loaded sector file ... with N playfields » -> « Server started listening
on port » (= pret). Un GroupName/ecf casse s'y voit avant ces marqueurs."""
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

_CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
_READY_RE = re.compile(r"Server started listening on port", re.I)
_SECTORS_RE = re.compile(r"Loaded sector file .* with (\d+) playfields", re.I)
_ERROR_PATTERNS = (
    re.compile(r"-EXC-", re.I),
    re.compile(r"-ERR-", re.I),
    re.compile(r"did not find expected key", re.I),
    re.compile(r"Duplicate playfield", re.I),
    re.compile(r"Error parsing", re.I),
    re.compile(r"Issue with deserializing", re.I),
)
_SAVE_NAME = "_TestChargementEditeur"


@dataclass
class DediBootResult:
    ready: bool = False                    # « Server started listening » atteint
    seconds: float = 0.0                   # temps pour y arriver
    playfields: int = 0                    # playfields charges par le dedi
    log_path: str = ""                     # log conserve pour inspection
    issues: list = field(default_factory=list)   # [str] lignes d'erreur du log
    groups: set = field(default_factory=set)     # bplib export : groupes POIs


def dedi_exe(game_root: Path) -> Path:
    return Path(game_root) / "DedicatedServer" / "EmpyrionDedicated.exe"


def is_dedi_running() -> bool:
    """Le dedi (ou un playfield server) tourne-t-il deja ?"""
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq EmpyrionDedicated.exe"],
            capture_output=True, text=True, timeout=15,
            creationflags=_CREATE_NO_WINDOW, check=False)
        return "EmpyrionDedicated.exe" in (out.stdout or "")
    except (OSError, subprocess.TimeoutExpired):
        return False


def build_test_yaml(scenario_name: str, telnet: bool = False) -> str:
    """Yaml dedie jetable : ports hors gamme (le dedi de l'utilisateur peut
    tourner a cote), reserve a 0 (boot plus leger), EAC off. Telnet active
    sur 33004 quand un bplib export est prevu (mdp jetable)."""
    tel = ("    Tel_Enabled: true\n"
           "    Tel_Port: 33004\n"
           "    Tel_Pwd: editeur-test\n") if telnet else "    Tel_Enabled: false\n"
    return (
        "# yaml JETABLE genere par l'editeur (test de chargement) — supprime"
        " apres le test\n"
        "ServerConfig:\n"
        "    Srv_Port: 33000\n"
        "    Srv_Name: TestChargementEditeur\n"
        "    Srv_Public: false\n"
        + tel +
        "    EACActive: false\n"
        "    Srv_ReservePlayfields: 0\n"
        "GameConfig:\n"
        f"    GameName: {_SAVE_NAME}\n"
        "    Mode: Survival\n"
        f"    CustomScenario: {scenario_name}\n"
    )


def _kill_tree(pid: int) -> None:
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                   capture_output=True, timeout=30,
                   creationflags=_CREATE_NO_WINDOW, check=False)


def _parse_log_issues(text: str) -> list[str]:
    """Lignes d'erreur du log dedie, dedupliquees (message tronque)."""
    seen: list[str] = []
    for raw in text.splitlines():
        if any(p.search(raw) for p in _ERROR_PATTERNS):
            key = raw.strip()[:150]
            if key not in seen:
                seen.append(key)
    return seen


_TELNET_PORT = 33004
_TELNET_PWD = "editeur-test"


def _telnet_collect(command: str, wait_s: float = 12.0) -> str:
    """Echange telnet SYNCHRONISE minimal avec le dedi jetable (protocole
    identique au client EWA : invite « Password: », IAC a filtrer), retourne
    tout le texte recue apres l'authentification."""
    import socket
    out: list[str] = []
    sock = socket.create_connection(("127.0.0.1", _TELNET_PORT), timeout=5.0)
    sock.settimeout(0.5)
    buffer = b""
    deadline = time.monotonic() + 8.0
    while time.monotonic() < deadline:
        try:
            chunk = sock.recv(4096)
        except socket.timeout:
            continue
        if not chunk:
            break
        if 0xFF in chunk:            # IAC : 0xFF + 2 octets a ignorer
            clean = bytearray()
            j = 0
            while j < len(chunk):
                if chunk[j] == 0xFF:
                    j += 3
                    continue
                clean.append(chunk[j])
                j += 1
            chunk = bytes(clean)
        buffer += chunk
        if buffer.lower().rstrip(b"\r\n \x00").endswith(b"password:"):
            break
    sock.sendall(_TELNET_PWD.encode("utf-8") + b"\r\n")
    time.sleep(0.5)
    sock.sendall(command.encode("utf-8") + b"\r\n")
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        try:
            chunk = sock.recv(4096)
        except socket.timeout:
            continue
        if not chunk:
            break
        out.append(chunk.decode("utf-8", "replace"))
    try:
        sock.close()
    except OSError:
        pass
    return "".join(out)


def run_dedi_boot_check(game_root: Path, scenario_name: str,
                        timeout_s: float = 300.0,
                        progress=None,
                        bplib_export: bool = False,
                        export_path: Path | None = None) -> DediBootResult:
    """Boot le dedi sur `scenario_name` (nom DOSSIER sous
    Content/Scenarios — le scenario INSTALLE, pas la copie de travail),
    attend le demarrage (ou les erreurs), tue l'arbre de processus, supprime
    la sauvegarde jetable et retourne le resultat. `progress(text)` est
    appelee a chaque etape notable (derniere ligne du log).

    bplib_export=True : apres le demarrage, envoie la commande console
    « bplib export <fichier> » par telnet (liste OFFICIELLE des groupes de
    POIs telle que le jeu la connait) et stocke la liste dans
    result.groups."""
    game_root = Path(game_root)
    exe = dedi_exe(game_root)
    result = DediBootResult()
    if not exe.is_file():
        result.issues.append(f"dedie introuvable : {exe}")
        return result

    saves_dir = game_root / "Saves"
    yaml_path = saves_dir / "_test_chargement_editeur.yaml"
    yaml_path.write_text(build_test_yaml(scenario_name, telnet=bplib_export),
                         encoding="utf-8")
    logs_dir = game_root / "DedicatedServer" / "Logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "_test_chargement.log"
    if log_path.exists():
        log_path.unlink()
    save_dir = saves_dir / "Games" / _SAVE_NAME

    if progress:
        progress("demarrage du dedie...")
    proc = subprocess.Popen(
        [str(exe), "-batchmode", "-nographics",
         "-logFile", str(log_path),
         "-dedicated", str(yaml_path)],
        cwd=str(game_root / "DedicatedServer"),
        creationflags=_CREATE_NO_WINDOW)

    def cleanup():
        try:
            if save_dir.exists():
                shutil.rmtree(save_dir, ignore_errors=True)
        except OSError:
            pass
        try:
            yaml_path.unlink()
        except OSError:
            pass

    try:
        start = time.time()
        deadline = start + timeout_s
        offset = 0
        timed_out = False
        while True:
            if time.time() >= deadline:
                timed_out = True
                break
            if proc.poll() is not None:
                # sorti seul = plantage au chargement (c'est une reponse)
                break
            time.sleep(1.0)
            try:
                text = log_path.read_text(encoding="utf-8",
                                          errors="replace")
            except OSError:
                continue
            fresh = text[offset:]
            offset = len(text)
            if progress and fresh.strip():
                last = fresh.strip().splitlines()[-1]
                progress(last.strip()[:120])
            m = _SECTORS_RE.search(fresh)
            if m:
                result.playfields = max(result.playfields, int(m.group(1)))
            if _READY_RE.search(fresh):
                result.ready = True
                break
        result.seconds = round(time.time() - start, 1)
        if result.ready:
            time.sleep(3.0)        # laisser la fin du chargement s'ecrire
        if timed_out:
            result.issues.append(
                f"timeout {timeout_s:.0f} s sans demarrage complet — le "
                f"chargement est peut-etre simplement long sur ce scenario")
        if result.ready and bplib_export:
            if progress:
                progress("commande console bplib export...")
            export_name = "_bplib_export_editeur.txt"
            _telnet_collect(f"bplib export {export_name}", wait_s=20.0)
            candidates = [game_root / export_name,
                          game_root / "DedicatedServer" / export_name,
                          saves_dir / export_name,
                          game_root / "Content" / export_name]
            export_file = next((c for c in candidates if c.is_file()), None)
            if export_file is None:
                for cand in game_root.rglob(export_name):
                    export_file = cand
                    break
            if export_file is None:
                result.issues.append(
                    f"fichier d'export bplib introuvable apres la commande "
                    f"(cherche : {export_name})")
            else:
                for line in export_file.read_text(
                        encoding="utf-8-sig", errors="replace").splitlines():
                    if ":" in line:
                        result.groups.add(
                            line.split(":", 1)[0].strip().casefold())
    finally:
        if proc.poll() is None:
            _kill_tree(proc.pid)
        try:
            text = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        result.issues.extend(_parse_log_issues(text))
        result.log_path = str(log_path)
        cleanup()

    if result.ready:
        result.issues = [i for i in result.issues
                         if not i.startswith("timeout")]
    return result
