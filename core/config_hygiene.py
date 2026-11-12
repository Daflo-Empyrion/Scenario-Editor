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


# ---------------------------------------------------------------------------
# References ECF : les deux crashs du 12/11 (playfield abandonne puis
# NullReferenceException dans DeployPciture, sans nom de fichier au log).
# ---------------------------------------------------------------------------
BASE_CONFIG = ("C:/Program Files (x86)/Steam/steamapps/common/Empyrion - "
               "Galactic Survival/Content/Configuration")


def _types_ecf(texte: str) -> set:
    """Types de blocs — l'element DOIT etre sur la ligne du `{`
    (`{ +Type ...`), c'est la seule forme que le chargeur accepte.

    Vecu 12/11 : des blocs ecrits `{` puis `+LootGroup Name: X` a la ligne
    suivante ont fait sortir le chargeur du tableau
    (`IndexOutOfRangeException` dans EcfFile.ParseLines) puis planter le jeu.
    Un scan tolerant (type sur la ligne suivante accepte) ne voyait rien :
    les blocs mal formes sont donc signales a part par `scan_ecf_openline`."""
    return set(re.findall(r"(?m)^\{ *\+?([A-Za-z]+)", texte))


def scan_ecf_openline(scenario: Path) -> list:
    """[(fichier, ligne)] des blocs dont la declaration n'est pas sur la ligne
    du `{` : forme rejetee par le chargeur (crash), vecu 12/11."""
    conf = Path(scenario) / "Content" / "Configuration"
    out = []
    for path in sorted(conf.glob("*.ecf")) if conf.is_dir() else []:
        lignes = path.read_bytes().decode("utf-8", errors="replace").splitlines()
        for i, ln in enumerate(lignes, 1):
            if ln.strip() != "{":
                continue
            if i < len(lignes) and re.match(r"\s*\+?[A-Za-z]+\s+\w+\s*:", lignes[i]):
                out.append((path.name, i))
    return out


def scan_ecf_types(scenario: Path, base_config: Path | str = BASE_CONFIG) -> list:
    """[(fichier, [types en trop])] : un fichier de scenario contient un type de
    bloc absent du meme fichier en vanille.

    Vecu 12/11 : 10 blocs `+LootGroup` ecrits dans `Containers.ecf` (le fichier
    n'admet que `Container`) -> `IndexOutOfRangeException` dans
    `EcfFile.ParseLines` et crash du jeu."""
    conf = Path(scenario) / "Content" / "Configuration"
    base = Path(base_config)
    out = []
    for path in sorted(conf.glob("*.ecf")) if conf.is_dir() else []:
        ref = base / path.name
        if not ref.is_file():
            continue                    # fichier propre au scenario
        trop = (_types_ecf(path.read_bytes().decode("utf-8", errors="replace"))
                - _types_ecf(ref.read_bytes().decode("utf-8", errors="replace")))
        if trop:
            out.append((path.name, sorted(trop)))
    return out


def scan_container_slots(scenario: Path) -> list:
    """[(fichier, id, index)] : entrees de conteneur au-dela de l'index 19.

    Le moteur boucle `for (i < 20)` sur `Group_i`/`Name_i` : ces lignes sont
    ecrites mais jamais lues (vecu 12/11 : 34 entrees, dont tout le butin rare
    des coffres Eden). Ce n'est pas un crash, mais du contenu mort."""
    conf = Path(scenario) / "Content" / "Configuration"
    path = conf / "Containers.ecf"
    if not path.is_file():
        return []
    out = []
    cid = 0
    for ln in path.read_bytes().decode("utf-8", errors="replace").splitlines():
        m = re.match(r"\{\s*\+?Container Id: (\d+)", ln)
        if m:
            cid = int(m.group(1))
            continue
        m = re.match(r"\s*(?:Name|Group)_(\d+):", ln)
        if m and int(m.group(1)) >= 20:
            out.append((path.name, cid, int(m.group(1))))
    return out


# proprietes qui n'existent QUE dans SpawnZoneData (pas dans SpawnRateZoneData)
SPAWNZONE_ONLY = ("BiomesExcluded", "SpawnOnlyIfPoiIsAlien", "Entities")


def scan_spawnzone_schema(scenario: Path) -> list:
    """[(fichier, ligne)] : item de `SpawnRateZones:` portant une propriete de
    `SpawnZoneData`.

    Vecu 12/11 au soir : un en-tete `SpawnZones:` commente par erreur (ou avale
    par une edition de bloc) fait tomber ses items sous `SpawnRateZones:` ; le
    jeu tente de deserialiser des SpawnZoneData comme des SpawnRateZoneData :
    « Property 'BiomesExcluded' not found on type 'SpawnRateZoneData' »,
    playfield refuse (« unknown playfield type Undefined ») puis crash au
    chargement des planetes. Regle : les cles de SpawnZoneData n'ont rien a
    faire dans une section `SpawnRateZones:`."""
    pf = Path(scenario) / "Playfields"
    out = []
    for path in sorted(pf.glob("*/playfield*.yaml")) if pf.is_dir() else []:
        dans = False
        for i, ln in enumerate(path.read_bytes().decode("utf-8", errors="replace")
                               .splitlines(), 1):
            if re.match(r"^SpawnRateZones:\s*$", ln):
                dans = True
                continue
            if dans and re.match(r"^[A-Za-z_]", ln):
                dans = False
                continue
            if dans and re.match(r"^\s*(" + "|".join(SPAWNZONE_ONLY) + r"):", ln):
                out.append((path.parent.name, path.name, i))
                break
    return out


PDA_SEQ_KEYS = ("ChapterActivation", "Rewards", "Tasks", "RewardedChapters")


def scan_pda_sequences(scenario: Path) -> list:
    """[(fichier, ligne, cle)] : cle de chapitre PDA qui devrait etre une
    SEQUENCE mais porte un mapping.

    Vecu 12/11 : un `ChapterActivation:` ecrit en mapping (« Check: » au lieu
    de « - Check: ») fait jeter YamlDotNet « Expected 'SequenceStart', got
    'MappingStart' » : ce n'est pas le chapitre qui est perdu, c'est TOUT le
    PDA, donc plantage au chargement de la partie."""
    p = Path(scenario) / "Extras" / "PDA" / "PDA.yaml"
    if not p.is_file():
        return []
    lignes = p.read_bytes().decode("utf-8", errors="replace").splitlines()
    out = []
    for i, ln in enumerate(lignes):
        m = re.match(r"^(\s*)([A-Za-z]+):\s*$", ln)
        if not m or m.group(2) not in PDA_SEQ_KEYS:
            continue
        for j in range(i + 1, min(i + 4, len(lignes))):
            s = lignes[j].strip()
            if not s:
                continue
            if not s.startswith("- "):
                out.append((p.name, j + 1, m.group(2)))
            break
    return out


def scan_regen_policy(scenario: Path) -> list:
    """[(playfield, ligne, POI, valeur, voulue)] des POI hors politique.

    Politique (core/regen_policy.py) : vaisseaux, ancres `SpawnPOINear` et
    marchands intacts ; mines a 72 h ; tout le reste definitif. Un regen
    laisse a 720 rend les ressources infinies — le jeu ne s'en plaint pas,
    c'est le design qui fuit.
    """
    from core.regen_policy import scan as _scan
    return _scan(Path(scenario))
