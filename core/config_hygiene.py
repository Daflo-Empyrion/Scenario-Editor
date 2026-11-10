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
"""Reparations mecaniques des configs ECF, sans parse+render.

Regles issues du vecu (fiches cerveau) :
- `{ ... }` sur UNE ligne = « config line N is malformed » puis NRE au
  chargement (empyrion-ecf-bloc-mono-ligne-malformed) : l'entete va sur sa
  ligne, l'accolade fermante seule sur la suivante ;
- `HitPoints:`/`Armor:` sans `, type: int` = valeur stockee en chaine,
  « Error converting property ... to an int value » au log et valeur
  IGNOREE silencieusement (empyrion-ecf-hitpoints-type-int-obligatoire).

Ecritures TEXTE BRUT (jamais parse+render : perte de blocs, cf.
re2fr-bilan-corrections-import-blocs), idempotentes, sauvegarde par
fichier via BackupStore.
"""
from pathlib import Path
import re

from core.ai_realism import read_text_raw, write_text_raw

# `{ ... }` ferme sur la meme ligne (hors commentaire)
_MONOLINE_RE = re.compile(r"^([ \t]*)\{([^{}]+)\}[ \t]*$")
# HitPoints/Armor numerique SANS `type:` sur la ligne
_INT_RE = re.compile(r"^([ \t]*)(HitPoints|Armor):[ \t]*([-0-9.]+)[ \t]*(#.*)?$")
_INT_FILES = ("BlocksConfig.ecf", "ItemsConfig.ecf")


def _apply(path: Path, text: str, eol: str, store) -> None:
    if store:
        store.snapshot(path)
    write_text_raw(path, text, eol)


def fix_ecf_monoline(scenario: Path, apply: bool = False, store=None) -> dict:
    """Separe l'entete et l'accolade fermante des blocs ECF mono-ligne."""
    rep = {"id": "ecf_monoline", "edits": 0, "files": 0, "details": []}
    conf = Path(scenario) / "Content" / "Configuration"
    for path in sorted(conf.glob("*.ecf")) if conf.is_dir() else []:
        text, eol = read_text_raw(path)
        out, n = [], 0
        for ln in text.split("\n"):
            m = _MONOLINE_RE.match(ln)
            if m is None or ln.lstrip().startswith("#"):
                out.append(ln)
                continue
            ind, corps = m.group(1), m.group(2).strip()
            out.append(ind + "{ " + corps)
            out.append(ind + "}")
            n += 1
        if not n:
            continue
        if apply:
            _apply(path, "\n".join(out), eol, store)
        rep["files"] += 1
        rep["edits"] += n
        rep["details"].append(path.name + " : " + str(n) + " bloc(s)")
    return rep


def fix_hitpoints_type(scenario: Path, apply: bool = False, store=None) -> dict:
    """Ajoute `, type: int` aux HitPoints/Armor qui n'en portent pas."""
    rep = {"id": "hitpoints_type", "edits": 0, "files": 0, "details": []}
    conf = Path(scenario) / "Content" / "Configuration"
    for name in _INT_FILES:
        path = conf / name
        if not path.is_file():
            continue
        text, eol = read_text_raw(path)
        out, n = [], 0
        for ln in text.split("\n"):
            m = _INT_RE.match(ln)
            if m is None or "type:" in ln:
                out.append(ln)
                continue
            ind, prop, val, comment = m.groups()
            out.append(ind + prop + ": " + val + ", type: int"
                       + (("  " + comment) if comment else ""))
            n += 1
        if not n:
            continue
        if apply:
            _apply(path, "\n".join(out), eol, store)
        rep["files"] += 1
        rep["edits"] += n
        rep["details"].append(name + " : " + str(n) + " propriete(s)")
    return rep


def scan_hitpoints_type(scenario: Path) -> list:
    """[(fichier, line, texte)] des HitPoints/Armor sans `type: int`."""
    conf = Path(scenario) / "Content" / "Configuration"
    out = []
    for name in _INT_FILES:
        path = conf / name
        if not path.is_file():
            continue
        for i, ln in enumerate(
                path.read_bytes().decode("utf-8", errors="replace")
                .replace("\r\n", "\n").split("\n"), 1):
            if _INT_RE.match(ln) and "type:" not in ln:
                out.append((name, i, ln.strip()))
    return out


def scan_ecf_monoline(scenario: Path) -> list:
    """[(fichier, line)] des blocs ECF ouverts et fermes sur la meme ligne."""
    conf = Path(scenario) / "Content" / "Configuration"
    out = []
    for path in sorted(conf.glob("*.ecf")) if conf.is_dir() else []:
        for i, ln in enumerate(
                path.read_bytes().decode("utf-8", errors="replace")
                .replace("\r\n", "\n").split("\n"), 1):
            if not ln.lstrip().startswith("#") and _MONOLINE_RE.match(ln):
                out.append((path.name, i))
    return out
