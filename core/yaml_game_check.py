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
"""Verification des fichiers d'un scenario avec le MOTEUR DU JEU : l'outil
dotnet tools/yamlcheck (publie single-file, YamlAssembly.dll = le
YamlDotNet renomme d'Empyrion embarquee)
- mode yaml : parse chaque *.yaml comme le jeu et reproduit ses erreurs
  exactes (vecu 11/10 : « did not find expected key » sur une Description
  multi-lignes avec guillemets non echappes — le jeu retirait les planetes
  de depart sans autre message ; pyyaml donne des faux positifs).
- mode ecf : valide la structure des *.ecf selon la grammaire du format
  (le parseur natif Eleon.EcfFile est indechirable hors du moteur Unity,
  statics dejeunes) ; calibre a 0 faux positif sur le corpus officiel
  (vanille + scenarios installes) et sur 2287 ECF du Workshop.

Shortcut : la validation ECF est structurelle (le sens des classes/ids est
verifie ailleurs — cross_reference_check), quand upgrade si un jour le
parseur natif devient invocable."""
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# timeout largement au-dessus des ~5 s mesures sur RE2-RPG (593 fichiers)
_SCAN_TIMEOUT_S = 600


class YamlCheckError(RuntimeError):
    """L'outil n'est pas disponible (absent et dotnet absent/echec build)."""


@dataclass
class YamlFinding:
    rel_path: str
    line: int
    col: int
    message: str


def _creationflags() -> int:
    # pas de fenetre console qui clignote a chaque scan
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def locate_checker() -> Path | None:
    """Cherche l'exe publie : bundle PyInstaller, publish dev, build dev."""
    if getattr(sys, "frozen", False):
        bundled = Path(getattr(sys, "_MEIPASS", "")) / "yamlcheck.exe"
        if bundled.is_file():
            return bundled
    root = Path(__file__).resolve().parents[1]
    for rel in (("tools", "yamlcheck", "publish", "yamlcheck.exe"),
                ("tools", "yamlcheck", "bin", "Release", "net8.0",
                 "yamlcheck.exe")):
        candidate = root.joinpath(*rel)
        if candidate.is_file():
            return candidate
    return None


def build_checker() -> Path:
    """Publish l'outil (dotnet requis sur le poste) ; YamlCheckError sinon."""
    import shutil

    dotnet = shutil.which("dotnet")
    if not dotnet:
        raise YamlCheckError("dotnet introuvable sur le poste")
    root = Path(__file__).resolve().parents[1]
    out_dir = root / "tools" / "yamlcheck" / "publish"
    cmd = [dotnet, "publish", str(root / "tools" / "yamlcheck"),
           "-c", "Release", "-o", str(out_dir),
           "-p:PublishSingleFile=true", "-p:SelfContained=false",
           "-v", "q", "--nologo"]
    try:
        subprocess.run(cmd, capture_output=True, timeout=300,
                       creationflags=_creationflags(), check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise YamlCheckError(f"echec du publish dotnet : {exc}") from exc
    exe = out_dir / "yamlcheck.exe"
    if not exe.is_file():
        raise YamlCheckError("publish dotnet sans yamlcheck.exe produit")
    return exe


def ensure_checker() -> Path:
    """locate_checker, avec build a la volee en derniere chance (dev)."""
    checker = locate_checker()
    if checker is not None:
        return checker
    return build_checker()


def parse_check_output(text: str) -> tuple[list[YamlFinding], int]:
    """Lit le protocole TSV de l'outil (BROKEN/SUMMARY) -> (findings, n)."""
    findings: list[YamlFinding] = []
    scanned = 0
    for line in text.splitlines():
        parts = line.split("\t")
        if parts[0] == "BROKEN" and len(parts) >= 5:
            try:
                line_no, col_no = int(parts[2] or 0), int(parts[3] or 0)
            except ValueError:
                continue        # ligne malformee : ignoree, jamais bloquante
            findings.append(YamlFinding(
                rel_path=parts[1], line=line_no, col=col_no,
                message=parts[4],
            ))
        elif parts[0] == "SUMMARY" and len(parts) >= 2:
            try:
                scanned = int(parts[1])
            except ValueError:
                scanned = 0
    return findings, scanned


def run_yaml_check(checker: Path, scan_dirs, mode: str = "yaml",
                   command: list[str] | None = None) -> tuple[list[YamlFinding], int]:
    """Scanne chaque dossier (un sous-process par racine ; les chemins
    relatifs des findings le sont par rapport a CHAQUE racine passe).
    `mode` = "yaml" (moteur YamlDotNet du jeu) ou "ecf" (structure) ;
    `command` remplace « exe + mode » par un argv arbitraire (tests)."""
    base = command if command is not None else [str(checker), mode]
    all_findings: list[YamlFinding] = []
    scanned = 0
    for scan_dir in scan_dirs:
        proc = subprocess.run(
            [*base, str(scan_dir)],
            capture_output=True, timeout=_SCAN_TIMEOUT_S,
            encoding="utf-8", errors="replace",
            creationflags=_creationflags(), check=False)
        findings, count = parse_check_output(proc.stdout or "")
        all_findings.extend(findings)
        scanned += count
    return all_findings, scanned
