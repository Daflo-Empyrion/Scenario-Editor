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
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

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
            units.append(SectorUnit(kind="system", system=sname,
                                    coordinates="", name=sname))
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
                units.append(SectorUnit(kind="sector", system=sname,
                                        coordinates=sector.value, name=sname))
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
                    units.append(SectorUnit(
                        kind="playfield", system=sname,
                        coordinates=sector.value, name=row_name))
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
            _ensure_blank_before(working_solar.children, eol)
            working_solar.children.append(_copy_entry(source_system))
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
            _ensure_blank_before(working_sectors_entry.children, eol)
            working_sectors_entry.children.append(_copy_entry(source_sector))
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
        if already:
            continue
        working_pf.children.append(_copy_entry(row))
        applied += 1
    if applied:
        text = working_doc.render()
        from core.fsutil import atomic_write_text
        atomic_write_text(working_yaml, text)
    return applied
