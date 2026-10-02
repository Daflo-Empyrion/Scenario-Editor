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

"""Fusion STRUCTURELLE de Sectors.yaml (tranche 2, demande 25/09/2026) :
au lieu d'ecraser tout le fichier avec celui du scenario source, on
propose UNITE PAR UNITE les elements absents de la copie de travail —
systeme entier, secteur (par coordonnees), ligne de playfield (par nom
affiche) — et on les INSERE dans le Sectors.yaml de la copie de travail
avec le parseur yamllite (commentaires et mise en forme preserves, le
texte des unites source est recopie tel quel)."""
import copy
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.yamllite.model import YamlBlank, YamlEntry, YamlNode
from core.yamllite.parser import parse_yaml_file

_COORD_RE = re.compile(r"-?\d+(?:\.\d+)?")


@dataclass
class SectorUnit:
    """Une unite fusionnable : systeme entier, secteur, ou ligne playfield."""
    kind: str            # 'system' | 'sector' | 'playfield'
    system: str          # nom du systeme solaire concerne
    coordinates: str     # representation des coordonnees ('[0, 0, 0]') ou ''
    name: str            # nom du systeme (kind=system) ou du playfield
    playfields: tuple = ()   # noms de playfields introduits par l'unite
    playfield_types: tuple = ()  # TYPES de playfields (dossiers requises)
    conflict: str = ""   # playfields DEJA dans le working (unicite globale)


@dataclass(frozen=True)
class PlayfieldTypeDep:
    """Dossier Playfields/<Type> a copier depuis la source."""
    name: str            # nom du TYPE de playfield (= nom du dossier)
    source_path: Path


def _sector_playfield_names(sector_entry: YamlEntry) -> set:
    """Noms de playfields declares par une LIGNE secteur. DEUX formats
    coexistent dans Sectors.yaml :
    - flow une ligne : `['0,0,0', Omicron, EdenArid, ...]` -> playfield =
      2e champ du flow ;
    - structure : `- Coordinates: [0,0,-4]` + enfants `Playfields:` (les
      coordonnees ne sont JAMAIS un nom de playfield — vecu 01/10 : les
      '0'/'-1' fantomes gonflaient le controle d'unicite).
    Le jeu construit un dictionnaire nom -> secteur : un doublon global =
    crash « Duplicate playfield name » (vecu 01/10, 'Omicron' importe
    deux fois par deux systemes)."""
    names = set()
    if not sector_entry.key:
        fields = _split_flow(sector_entry.value) if sector_entry.value \
            else []
        if len(fields) > 1 and fields[1]:
            names.add(fields[1])
    pf = _find_child(sector_entry, "Playfields")
    if pf is not None:
        for row in _seq_items(pf):
            if row.value:
                f = _split_flow(row.value)
                if len(f) > 1 and f[1]:
                    names.add(f[1])
    return names


def _system_playfields(system_entry: YamlEntry) -> set:
    """Tous les playfields declares par UN systeme."""
    out: set = set()
    sectors = _find_child(system_entry, "Sectors")
    if sectors is not None:
        for s in _seq_items(sectors):
            out |= _sector_playfield_names(s)
    return out


def _sector_playfield_types(sector_entry: YamlEntry) -> set:
    """TYPES de playfields (3e champ du flow = dossier
    Playfields/<Type>/ requis par le jeu) declares par une ligne
    secteur."""
    types: set = set()
    rows: List[str] = []
    pf = _find_child(sector_entry, "Playfields")
    if pf is not None:
        rows = [c.value or "" for c in _seq_items(pf)]
    elif (sector_entry.value or "").strip().startswith("["):
        rows = [sector_entry.value]
    for row in rows:
        f = _split_flow(row)
        if len(f) > 2 and f[2]:
            types.add(f[2])
    return types


def _system_playfield_types(system_entry: YamlEntry) -> set:
    out: set = set()
    sectors = _find_child(system_entry, "Sectors")
    if sectors is not None:
        for s in _seq_items(sectors):
            out |= _sector_playfield_types(s)
    return out


def collect_playfield_type_deps(working_yaml: Path, source_yaml: Path,
                                units: List[SectorUnit],
                                working_root=None, source_root=None,
                                vanilla_content=None
                                ) -> Tuple[List[PlayfieldTypeDep], List[str],
                                           List[str]]:
    """Dossiers Playfields/<Type> requis par les unites importees.
    Retourne (deps, missing, identical_vanilla) :
    - deps : absents du working et de la VANILLE -> a copier depuis la
      source ;
    - PLUS : la source a un dossier qui DIFFERE de la vanille (playfield
      modifie par le scenario source = contenu a preserver, vecu 01/10 :
      8 playfields DREX modifies joues en versions vanille) ;
    - missing : introuvables PARTOUT (working, vanille, source) -> les
      playfields concernes crasheront le chargement (« unknown playfield
      type », vecu sur 'Symos Moon') ;
    - identical_vanilla : presents en vanille ET identiques -> fallback
      vanille OK, rien a faire."""
    working_root = Path(working_root) if working_root else None
    source_root = Path(source_root) if source_root else None
    if working_root is None:
        working_root = Path(working_yaml).parent.parent
    if source_root is None:
        source_root = Path(source_yaml).parent.parent
    if vanilla_content is None:
        from core.settings import get_vanilla_content_path
        vanilla_content = get_vanilla_content_path()

    source_doc = parse_yaml_file(source_yaml)
    source_solar = _find_solar_systems(source_doc)
    if source_solar is None:
        return [], [], []
    types: set = set()
    for unit in units:
        source_system = next((c for c in _systems(source_solar)
                              if _strip_quotes(c.value).casefold()
                              == unit.system.casefold()), None)
        if source_system is None:
            continue
        if unit.kind == "system":
            types |= _system_playfield_types(source_system)
            continue
        source_sectors_entry = _find_child(source_system, "Sectors")
        if source_sectors_entry is None:
            continue
        ckey = _coords_key(unit.coordinates)
        source_sector = next((c for c in _seq_items(source_sectors_entry)
                              if _coords_key(c.value) == ckey), None)
        if source_sector is None:
            continue
        types |= _sector_playfield_types(source_sector)

    deps: List[PlayfieldTypeDep] = []
    missing: List[str] = []
    identical: List[str] = []
    from core.fsutil import dirs_differ
    for t in sorted(types):
        if (working_root / "Playfields" / t).is_dir():
            continue
        src = source_root / "Playfields" / t
        van = Path(vanilla_content) / "Playfields" / t             if vanilla_content else None
        if src.is_dir():
            if van is not None and van.is_dir()                     and not dirs_differ(src, van):
                identical.append(t)     # source == vanille : fallback OK
            else:
                # source modifiee (ou pas de vanille) : contenu a garder
                deps.append(PlayfieldTypeDep(name=t, source_path=src))
        elif van is None or not van.is_dir():
            missing.append(t)
        # sinon : present en vanille seulement -> le jeu resout, rien
    return deps, missing, identical


def copy_playfield_type_deps(deps: List[PlayfieldTypeDep],
                             working_root) -> int:
    """Copie les dossiers de playfields manquants dans la copie de
    travail (*.yaml REPARES : junk apres crochet de liste flow — vecu
    01/10, presets/playfields sources corrompus) ; retourne le nombre
    copies."""
    from core.fsutil import copy_dir_repairing_yaml
    n = 0
    for dep in deps:
        dst = Path(working_root) / "Playfields" / dep.name
        if dst.is_dir():
            continue
        copy_dir_repairing_yaml(dep.source_path, dst)
        n += 1
    return n


def find_duplicate_playfields(working_yaml: Path) -> Dict[str, List[str]]:
    """Playfields declares dans PLUSIEURS systemes de la copie de
    travail : le jeu construit un dictionnaire nom -> secteur et crash
    (« Duplicate playfield name », vecu 01/10 sur 'Parthix' entre Farr et
    Ixia). Retourne {playfield: [systemes, dans l'ordre du document]} —
    le PREMIER systeme de la liste est celui a garder."""
    doc = parse_yaml_file(Path(working_yaml))
    solar = _find_solar_systems(doc)
    if solar is None:
        return {}
    occurrences: Dict[str, List[str]] = {}
    for system in _systems(solar):
        sname = _strip_quotes(system.value)
        for pf in _system_playfields(system):
            occurrences.setdefault(pf, []).append(sname)
    return {pf: systems for pf, systems in occurrences.items()
            if len(systems) > 1}


def drop_duplicate_playfields(working_yaml: Path) -> Tuple[int, List[str]]:
    """CORRIGE les doublons : pour chaque playfield declare plusieurs
    fois, garde la PREMIERE occurrence (ordre du document) et retire les
    suivantes ; les secteurs structur devenus sans playfield sont
    retires. Ecrit en atomique (l'appelant gere backup et undo).
    Retourne (nombre de lignes retirees, details)."""
    doc = parse_yaml_file(Path(working_yaml))
    solar = _find_solar_systems(doc)
    if solar is None:
        return 0, []
    retired, details = 0, []
    seen: Dict[str, str] = {}
    for system in _systems(solar):
        sname = _strip_quotes(system.value)
        sectors_entry = _find_child(system, "Sectors")
        if sectors_entry is None:
            continue
        for sector in list(_seq_items(sectors_entry)):
            pf_entry = _find_child(sector, "Playfields")
            if pf_entry is not None:
                # format structure : les lignes playfield sont enfants
                rows = list(_seq_items(pf_entry))
            else:
                # format flow : LE secteur est la ligne playfield
                rows = [sector]
            removed = 0
            for row in list(rows):
                fields = _split_flow(row.value) if row.value else []
                if len(fields) > 1 and fields[1]:
                    nm = fields[1]
                    if nm in seen:
                        (pf_entry if pf_entry is not None
                         else sectors_entry).children.remove(row)
                        removed += 1
                        retired += 1
                        details.append(f"{nm} retire de {sname} "
                                       f"(garde dans {seen[nm]})")
                    else:
                        seen[nm] = sname
            # secteur structure devenu sans playfield : supprime
            if pf_entry is not None and removed                     and not _seq_items(pf_entry):
                sectors_entry.children.remove(sector)
                details.append(f"secteur vide supprime dans {sname}")
    if retired:
        from core.fsutil import atomic_write_text
        atomic_write_text(Path(working_yaml), doc.render())
    return retired, details


def _all_playfields(solar_entry: YamlEntry) -> set:
    """Unicite GLOBALE : tous les noms de playfields du fichier, tous
    systemes confondus (en casse-preserve ; comparaison casefold)."""
    out: set = set()
    for system in _systems(solar_entry):
        out |= _system_playfields(system)
    return out


def _child_entries(entry: YamlEntry) -> List[YamlEntry]:
    return [c for c in entry.children if isinstance(c, YamlEntry)]


def _find_child(entry: YamlEntry, key: str) -> Optional[YamlEntry]:
    for c in _child_entries(entry):
        if c.key == key:
            return c
    return None


def _seq_items(entry: YamlEntry) -> List[YamlEntry]:
    return [c for c in _child_entries(entry) if c.is_sequence_item]


def _split_flow(value: str) -> List[str]:
    """Eclate une liste flow yaml ('['0,0,0', Nom, Template, '']') en
    champs, en respectant les guillemets (le champ coordonnees contient
    lui-meme des virgules)."""
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]          # retire les crochets de la liste flow
    fields, buf, quote = [], "", None
    for c in value:
        if quote:
            buf += c
            if c == quote:
                quote = None
        elif c in "\"'":
            quote = c
            buf += c
        elif c == ",":
            fields.append(buf.strip())
            buf = ""
        else:
            buf += c
    if buf.strip():
        fields.append(buf.strip())
    return [f.strip().strip("'\"") for f in fields]


def _coords_key(value: str) -> tuple:
    return tuple(_COORD_RE.findall(value or ""))


def _strip_quotes(v: str) -> str:
    return v.strip().strip("'\"")


def _find_solar_systems(doc) -> Optional[YamlEntry]:
    for n in doc.nodes:
        if isinstance(n, YamlEntry) and n.key == "SolarSystems":
            return n
    return None


def _systems(solar: YamlEntry) -> List[YamlEntry]:
    return [c for c in _seq_items(solar) if c.key == "Name" and c.value]


def analyze_sectors_merge(working_yaml: Path,
                          source_yaml: Path) -> List[SectorUnit]:
    """Unites du Sectors.yaml SOURCE absentes du Sectors.yaml de la copie
    de travail : systemes entiers, secteurs, lignes de playfield."""
    working_doc = parse_yaml_file(working_yaml)
    source_doc = parse_yaml_file(source_yaml)
    working_solar = _find_solar_systems(working_doc)
    source_solar = _find_solar_systems(source_doc)
    if working_solar is None or source_solar is None:
        return []
    working_names = {c.value.casefold(): c for c in _systems(working_solar)}
    units: List[SectorUnit] = []
    for system in _systems(source_solar):
        sname = _strip_quotes(system.value)
        wsystem = working_names.get(sname.casefold())
        if wsystem is None:
            units.append(SectorUnit(
                kind="system", system=sname, coordinates="", name=sname,
                playfields=tuple(sorted(_system_playfields(system))),
                playfield_types=tuple(sorted(
                    _system_playfield_types(system)))))
            continue
        # systeme commun : secteurs (par coordonnees) puis lignes playfield
        source_sectors_entry = _find_child(system, "Sectors")
        working_sectors_entry = _find_child(wsystem, "Sectors")
        if source_sectors_entry is None or working_sectors_entry is None:
            continue
        working_coords = {_coords_key(c.value) for c in
                          _seq_items(working_sectors_entry)}
        for sector in _seq_items(source_sectors_entry):
            ckey = _coords_key(sector.value)
            if ckey not in working_coords:
                units.append(SectorUnit(
                    kind="sector", system=sname, coordinates=sector.value,
                    name=sname,
                    playfields=tuple(sorted(
                        _sector_playfield_names(sector))),
                    playfield_types=tuple(sorted(
                        _sector_playfield_types(sector)))))
                continue
            wsector = next((c for c in _seq_items(working_sectors_entry)
                            if _coords_key(c.value) == ckey), None)
            if wsector is None:
                continue
            source_pf = _find_child(sector, "Playfields")
            working_pf = _find_child(wsector, "Playfields")
            if source_pf is None or working_pf is None:
                continue
            working_rows = {_split_flow(c.value)[1].casefold()
                            for c in _seq_items(working_pf) if c.value}
            for row in _seq_items(source_pf):
                if not row.value:
                    continue
                fields = _split_flow(row.value)
                row_name = fields[1] if len(fields) > 1 else ""
                if row_name and row_name.casefold() not in working_rows:
                    row_type = fields[2] if len(fields) > 2 else ""
                    units.append(SectorUnit(
                        kind="playfield", system=sname,
                        coordinates=sector.value, name=row_name,
                        playfields=(row_name,),
                        playfield_types=(row_type,) if row_type else ()))

    # unicite GLOBALE des noms de playfields : le jeu construit un
    # dictionnaire nom -> secteur, un doublon = crash « Duplicate
    # playfield name » (vecu 01/10 : 'Omicron' importe par un systeme
    # alors que le starter du working l'avait deja). Working prioritaire :
    # les unites en conflit sont MARQUEES (decochees par l'UI) et
    # l'application exclura les secteurs conflictuels.
    global_pf = {_n.casefold() for _n in _all_playfields(working_solar)}
    for unit in units:
        conflicts = sorted(n for n in unit.playfields
                           if n.casefold() in global_pf)
        if conflicts:
            unit.conflict = ", ".join(conflicts)
        else:
            global_pf |= {n.casefold() for n in unit.playfields}
    return units


def _copy_entry(entry: YamlEntry) -> YamlEntry:
    clone = copy.deepcopy(entry)
    return clone


def _ensure_blank_before(children: List[YamlNode], eol: str) -> None:
    if children and not isinstance(children[-1], YamlBlank):
        children.append(YamlBlank(raw=eol))


def apply_structural_units(working_yaml: Path, units: List[SectorUnit],
                           source_yaml: Path) -> int:
    """Insere les unites cochees dans le Sectors.yaml de la copie de
    travail (rendu yamllite : commentaires et mise en forme preserves) et
    ECRIT le fichier en atomique ; retourne le nombre d'unites reellement
    inserees. L'appelant gere backup (.bak) et undo (capture_file avant)."""
    if not units:
        return 0
    working_doc = parse_yaml_file(working_yaml)
    source_doc = parse_yaml_file(source_yaml)
    working_solar = _find_solar_systems(working_doc)
    source_solar = _find_solar_systems(source_doc)
    if working_solar is None or source_solar is None:
        return 0
    eol = "\r\n" if working_solar.raw.endswith("\r\n") else "\n"
    applied = 0
    # unicite GLOBALE des playfields, re-verifiee A L'INSERTION (securite
    # meme si l'utilisateur a coche une unite marquee en conflit : les
    # secteurs conflictuels sont EXCLUS de la copie, jamais un doublon)
    global_pf = {_n.casefold() for _n in _all_playfields(working_solar)}
    for unit in units:
        source_system = next((c for c in _systems(source_solar)
                              if _strip_quotes(c.value).casefold()
                              == unit.system.casefold()), None)
        if source_system is None:
            continue
        working_system = next((c for c in _systems(working_solar)
                               if _strip_quotes(c.value).casefold()
                               == unit.system.casefold()), None)
        if unit.kind == "system":
            if working_system is not None:
                continue
            clone = _copy_entry(source_system)
            clone_sectors = _find_child(clone, "Sectors")
            if clone_sectors is not None:
                # exclusion des secteurs dont un playfield existe DEJA
                # ailleurs ; un systeme sans enfant Sectors est copie
                # tel quel (format Pos des anciens scenarios)
                kept = []
                for child in clone_sectors.children:
                    if (isinstance(child, YamlEntry)
                            and child.is_sequence_item
                            and any(n.casefold() in global_pf for n in
                                    _sector_playfield_names(child))):
                        continue
                    kept.append(child)
                clone_sectors.children = kept
                inserted = _system_playfields(clone)
                source_sectors = _find_child(source_system, "Sectors")
                if not inserted and source_sectors is not None \
                        and _seq_items(source_sectors):
                    continue    # tous ses secteurs etaient en conflit
            else:
                inserted = set()
            _ensure_blank_before(working_solar.children, eol)
            working_solar.children.append(clone)
            global_pf |= {n.casefold() for n in inserted}
            applied += 1
            continue
        if working_system is None:
            continue
        source_sectors_entry = _find_child(source_system, "Sectors")
        working_sectors_entry = _find_child(working_system, "Sectors")
        if source_sectors_entry is None or working_sectors_entry is None:
            continue
        ckey = _coords_key(unit.coordinates)
        source_sector = next((c for c in _seq_items(source_sectors_entry)
                              if _coords_key(c.value) == ckey), None)
        working_sector = next((c for c in _seq_items(working_sectors_entry)
                               if _coords_key(c.value) == ckey), None)
        if unit.kind == "sector":
            if source_sector is None or working_sector is not None:
                continue
            if any(n.casefold() in global_pf for n in
                   _sector_playfield_names(source_sector)):
                continue            # un de ses playfields est deja pris
            _ensure_blank_before(working_sectors_entry.children, eol)
            working_sectors_entry.children.append(_copy_entry(source_sector))
            global_pf |= {n.casefold() for n in
                          _sector_playfield_names(source_sector)}
            applied += 1
            continue
        if source_sector is None or working_sector is None:
            continue
        source_pf = _find_child(source_sector, "Playfields")
        working_pf = _find_child(working_sector, "Playfields")
        if source_pf is None or working_pf is None:
            continue
        row = next((c for c in _seq_items(source_pf) if c.value
                    and _split_flow(c.value)[1:2]
                    and _split_flow(c.value)[1].casefold()
                    == unit.name.casefold()), None)
        if row is None:
            continue
        already = any(_split_flow(c.value)[1:2]
                      and _split_flow(c.value)[1].casefold()
                      == unit.name.casefold()
                      for c in _seq_items(working_pf) if c.value)
        if already or unit.name.casefold() in global_pf:
            continue
        working_pf.children.append(_copy_entry(row))
        global_pf.add(unit.name.casefold())
        applied += 1
    if applied:
        text = working_doc.render()
        from core.fsutil import atomic_write_text
        atomic_write_text(working_yaml, text)
    return applied
