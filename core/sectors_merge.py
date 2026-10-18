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


def _is_sun_type(type_field: str) -> bool:
    """Le TYPE de playfield designe-t-il un soleil (Sun, SunRandom,
    SunBltSe...) ? Un systeme sans playfield soleil est injoignable."""
    return (type_field or "").strip().casefold().startswith("sun")


def _sector_has_sun(sector_entry: YamlEntry) -> bool:
    return any(_is_sun_type(t) for t in _sector_playfield_types(sector_entry))


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
                              if _coords_key(_coords_text(c)) == ckey), None)
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
    suivantes ; retire aussi du MEME secteur les LIGNES ORPHELINES de la
    planete retiree ('<Planete> Moon', '<Planete> Orbit' — vecu 04/10 :
    'Zeyhines Orbit' reste seul sans sa planete) et les secteurs devenus
    vides ; un systeme qui perd son DERNIER soleil est retire ENTIEREMENT
    (un systeme sans soleil est casse — vecu 04/10 : 'Symos' importe de
    Default Akua-Omicron dont le soleil etait un doublon du 'Symos'
    d'Ellyon). Ecrit en atomique (l'appelant gere backup et undo).
    Retourne (nombre de lignes retirees, details)."""
    doc = parse_yaml_file(Path(working_yaml))
    solar = _find_solar_systems(doc)
    if solar is None:
        return 0, []
    retired, details = 0, []
    seen: Dict[str, str] = {}
    for system in list(_systems(solar)):
        sname = _strip_quotes(system.value)
        sectors_entry = _find_child(system, "Sectors")
        if sectors_entry is None:
            continue
        sun_removed = sun_kept = False
        for sector in list(_seq_items(sectors_entry)):
            pf_entry = _find_child(sector, "Playfields")
            if pf_entry is not None:
                # format structure : les lignes playfield sont enfants
                rows = list(_seq_items(pf_entry))
            else:
                # format flow : LE secteur est la ligne playfield
                rows = [sector]
            removed_names: List[str] = []
            for row in list(rows):
                fields = _split_flow(row.value) if row.value else []
                if len(fields) > 1 and fields[1]:
                    nm = fields[1]
                    is_sun = len(fields) > 2 and _is_sun_type(fields[2])
                    if nm in seen:
                        (pf_entry if pf_entry is not None
                         else sectors_entry).children.remove(row)
                        retired += 1
                        details.append(f"{nm} retire de {sname} "
                                       f"(garde dans {seen[nm]})")
                        removed_names.append(nm)
                        if is_sun:
                            sun_removed = True
                    else:
                        seen[nm] = sname
                        if is_sun:
                            sun_kept = True
            # orphelines : lunes/orbites de la planete retiree, MEME secteur
            if pf_entry is not None and removed_names:
                for row in list(_seq_items(pf_entry)):
                    fields = _split_flow(row.value) if row.value else []
                    nm = fields[1] if len(fields) > 1 else ""
                    if nm and any(nm.startswith(f"{r} ")
                                  for r in removed_names):
                        pf_entry.children.remove(row)
                        retired += 1
                        details.append(f"{nm} orphelin retire de {sname}")
            # secteur structure devenu sans playfield : supprime
            if pf_entry is not None and removed_names \
                    and not _seq_items(pf_entry):
                sectors_entry.children.remove(sector)
                details.append(f"secteur vide supprime dans {sname}")
        if sun_removed and not sun_kept:
            solar.children.remove(system)
            details.append(f"systeme {sname} retire entierement (son "
                           f"soleil etait un doublon : sans soleil il est "
                           f"injoignable)")
    if retired:
        from core.fsutil import atomic_write_text
        atomic_write_text(Path(working_yaml), doc.render())
    return retired, details


def find_broken_systems(working_yaml: Path) -> List[str]:
    """Systemes declares avec des secteurs mais SANS AUCUN playfield de
    type soleil : le jeu ne peut pas les joindre (vecu 04/10 : le systeme
    'Symos' importe dont le soleil etait un doublon). Retourne les noms
    dans l'ordre du document ; les formats sans liste Sectors (Pos des
    anciens scenarios) ne sont pas jugeables et sont ignores."""
    doc = parse_yaml_file(Path(working_yaml))
    solar = _find_solar_systems(doc)
    if solar is None:
        return []
    broken: List[str] = []
    for system in _systems(solar):
        sectors_entry = _find_child(system, "Sectors")
        if sectors_entry is None or not _seq_items(sectors_entry):
            continue
        if not any(_sector_has_sun(s) for s in _seq_items(sectors_entry)):
            broken.append(_strip_quotes(system.value))
    return broken


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


def _coords_text(entry: YamlEntry) -> str:
    """Representation des coordonnees d'un secteur : la valeur inline
    (flow « Coordinates: [x, y, z] ») OU, format EVO 1.19.6, le BLOC
    VERTICAL (l'entree « - Coordinates: » a une valeur VIDE et les
    nombres en enfants). Vecu 04/10 : sectors.value vide pour TOUS les
    secteurs -> toutes les unites semblaient aux memes coordonnees
    (regroupement cassé, secteurs dupliques a l'affichage et mauvais
    contenus a l'insertion fine)."""
    if entry.value and entry.value.strip():
        return entry.value
    parts = []
    for c in entry.children:
        if isinstance(c, YamlEntry) and c.is_sequence_item and c.value:
            parts.append(c.value.strip())
    return "[" + ",".join(parts) + "]" if parts else ""


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
                          source_yaml: Path,
                          detailed: bool = False) -> List[SectorUnit]:
    """Unites du Sectors.yaml SOURCE absentes de la copie de travail :
    systemes entiers, secteurs, lignes de playfield.

    detailed=True : pour un systeme ABSENT, emet aussi les unites ENFANTS
    (secteur par coordonnees, ligne de playfield) — l'arbre de fusion fine
    (SectorsFineDialog) les coche unitairement. Les unites « system »
    servent alors de bascule parent, seules les FEUILLES portent les
    conflits (sinon les enfants paraitraient en conflit avec leur propre
    parent)."""
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
            if detailed:
                source_sectors_entry = _find_child(system, "Sectors")
                for sector in (_seq_items(source_sectors_entry)
                               if source_sectors_entry else []):
                    units.append(SectorUnit(
                        kind="sector", system=sname,
                        coordinates=_coords_text(sector), name=sname,
                        playfields=tuple(sorted(
                            _sector_playfield_names(sector))),
                        playfield_types=tuple(sorted(
                            _sector_playfield_types(sector)))))
                    pf_entry = _find_child(sector, "Playfields")
                    for row in (_seq_items(pf_entry) if pf_entry is not None
                                else [sector]):
                        fields = _split_flow(row.value) if row.value else []
                        if len(fields) > 1 and fields[1]:
                            units.append(SectorUnit(
                                kind="playfield", system=sname,
                                coordinates=_coords_text(sector), name=fields[1],
                                playfields=(fields[1],),
                                playfield_types=(fields[2],)
                                if len(fields) > 2 and fields[2] else ()))
            continue
        # systeme commun : secteurs (par coordonnees) puis lignes playfield
        source_sectors_entry = _find_child(system, "Sectors")
        working_sectors_entry = _find_child(wsystem, "Sectors")
        if source_sectors_entry is None or working_sectors_entry is None:
            continue
        working_coords = {_coords_key(_coords_text(c)) for c in
                          _seq_items(working_sectors_entry)}
        for sector in _seq_items(source_sectors_entry):
            ckey = _coords_key(_coords_text(sector))
            if ckey not in working_coords:
                units.append(SectorUnit(
                    kind="sector", system=sname, coordinates=_coords_text(sector),
                    name=sname,
                    playfields=tuple(sorted(
                        _sector_playfield_names(sector))),
                    playfield_types=tuple(sorted(
                        _sector_playfield_types(sector)))))
                continue
            wsector = next((c for c in _seq_items(working_sectors_entry)
                            if _coords_key(_coords_text(c)) == ckey), None)
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
                        coordinates=_coords_text(sector), name=row_name,
                        playfields=(row_name,),
                        playfield_types=(row_type,) if row_type else ()))

    # unicite GLOBALE des noms de playfields : le jeu construit un
    # dictionnaire nom -> secteur, un doublon = crash « Duplicate
    # playfield name » (vecu 01/10 : 'Omicron' importe par un systeme
    # alors que le starter du working l'avait deja). Working prioritaire :
    # les unites en conflit sont MARQUEES (decochees par l'UI) et
    # l'application exclura les secteurs conflictuels.
    global_pf = {_n.casefold() for _n in _all_playfields(working_solar)}
    conflicted_cf: set = set()
    for unit in units:
        if detailed and unit.kind in ("system", "sector"):
            continue        # parents : conflits calcules depuis les LIGNES
        conflicts = sorted(n for n in unit.playfields
                           if n.casefold() in global_pf)
        if conflicts:
            unit.conflict = ", ".join(conflicts)
            conflicted_cf.update(n.casefold() for n in conflicts)
        else:
            global_pf |= {n.casefold() for n in unit.playfields}
    if detailed:
        for unit in units:
            if unit.kind in ("system", "sector"):
                c = sorted(n for n in unit.playfields
                           if n.casefold() in conflicted_cf)
                if c:
                    unit.conflict = ", ".join(c)
    return units


def _copy_entry(entry: YamlEntry) -> YamlEntry:
    clone = copy.deepcopy(entry)
    return clone


@dataclass(frozen=True)
class FineRequest:
    """Demande de fusion FINE (SectorsFineDialog) : systeme + secteur
    (representation brute des coordonnees SOURCE) + lignes demandees.
    rows=None = secteur ENTIER (toutes ses lignes absentes du working)."""
    system: str
    coordinates: str
    rows: Optional[Tuple[str, ...]] = None


def _filtered_sector_copy(sector: YamlEntry, want_rows: Optional[set],
                          global_pf: set, details: List[str], sname: str
                          ) -> Tuple[Optional[YamlEntry], List[str], bool]:
    """Clone d'un secteur source filtre par les lignes demandees
    (want_rows=None = toutes) et SANS celles deja dans le working
    (exclues, jamais un doublon). Retourne (clone ou None, noms inseres,
    le clone porte-t-il un soleil)."""
    pf_entry = _find_child(sector, "Playfields")
    if pf_entry is None:
        # format flow ancien : LE secteur est la ligne de playfield
        fields = _split_flow(sector.value) if sector.value else []
        if len(fields) < 2 or not fields[1]:
            return None, [], False
        nm = fields[1]
        if want_rows is not None and nm not in want_rows:
            return None, [], False
        if nm.casefold() in global_pf:
            details.append(f"{nm} exclu de {sname} (deja dans le working)")
            return None, [], False
        global_pf.add(nm.casefold())
        return (_copy_entry(sector), [nm],
                len(fields) > 2 and _is_sun_type(fields[2]))
    clone = _copy_entry(sector)
    clone_pf = _find_child(clone, "Playfields")
    inserted: List[str] = []
    sun = False
    for row in list(_seq_items(clone_pf)):
        fields = _split_flow(row.value) if row.value else []
        nm = fields[1] if len(fields) > 1 else ""
        if not nm:
            continue
        if want_rows is not None and nm not in want_rows:
            clone_pf.children.remove(row)
            continue
        if nm.casefold() in global_pf:
            clone_pf.children.remove(row)
            details.append(f"{nm} exclu de {sname} (deja dans le working)")
            continue
        global_pf.add(nm.casefold())
        inserted.append(nm)
        if len(fields) > 2 and _is_sun_type(fields[2]):
            sun = True
    if not inserted:
        return None, [], False
    return clone, inserted, sun


def apply_fine_selection(working_yaml: Path, requests, source_yaml: Path
                         ) -> Tuple[int, List[str]]:
    """Application FINE (dialogue SectorsFineDialog) : insere EXACTEMENT
    les lignes demandees — un systeme absent recoit une copie filtree de
    la source (coquille + secteurs/lignes choisis), un systeme commun
    recoit les lignes manquantes de ses secteurs. Unicite globale
    reverifiee a l'insertion (lignes en conflit exclues, jamais un
    doublon), regle du soleil (un systeme qui n'aurait aucun soleil n'est
    pas insere), rendu yamllite (commentaires preserves). Idempotent.
    Retourne (lignes de playfield inserees, details)."""
    if not requests:
        return 0, []
    working_doc = parse_yaml_file(working_yaml)
    source_doc = parse_yaml_file(source_yaml)
    working_solar = _find_solar_systems(working_doc)
    source_solar = _find_solar_systems(source_doc)
    if working_solar is None or source_solar is None:
        return 0, []
    eol = "\r\n" if working_solar.raw.endswith("\r\n") else "\n"
    global_pf = {_n.casefold() for _n in _all_playfields(working_solar)}

    # demandes groupees par systeme puis coordonnees de secteur
    # (None = secteur entier) ; l'ordre d'arrivee est conserve
    by_system: Dict[str, Dict[tuple, Optional[set]]] = {}
    for req in requests:
        sysmap = by_system.setdefault(req.system, {})
        ckey = _coords_key(req.coordinates)
        want = set(req.rows) if req.rows is not None else None
        if ckey not in sysmap:
            sysmap[ckey] = want
        elif sysmap[ckey] is not None and want is None:
            sysmap[ckey] = None
        elif sysmap[ckey] is not None and want is not None:
            sysmap[ckey] |= want

    applied_rows = 0
    details: List[str] = []
    for sname, coords_map in by_system.items():
        source_system = next(
            (c for c in _systems(source_solar)
             if _strip_quotes(c.value).casefold() == sname.casefold()), None)
        if source_system is None:
            continue
        source_sectors_entry = _find_child(source_system, "Sectors")
        if source_sectors_entry is None:
            continue
        working_system = next(
            (c for c in _systems(working_solar)
             if _strip_quotes(c.value).casefold() == sname.casefold()), None)

        if working_system is None:
            # ---- systeme absent : coquille clonee + secteurs choisis
            pf_before = set(global_pf)      # restore si le systeme est refuse
            clone = _copy_entry(source_system)
            clone_sectors = _find_child(clone, "Sectors")
            if clone_sectors is None:
                continue
            kept: List[YamlEntry] = []
            rows_kept = 0
            sys_had_sun = any(_sector_has_sun(s)
                              for s in _seq_items(source_sectors_entry))
            kept_sun = False
            for sector in _seq_items(source_sectors_entry):
                ckey = _coords_key(_coords_text(sector))
                if ckey not in coords_map:
                    continue
                new_sector, names_in, sun_here = _filtered_sector_copy(
                    sector, coords_map[ckey], global_pf, details, sname)
                if new_sector is None:
                    continue
                kept.append(new_sector)
                kept_sun = kept_sun or sun_here
                rows_kept += len(names_in)
            if not kept:
                continue
            if sys_had_sun and not kept_sun:
                global_pf.clear()
                global_pf.update(pf_before)  # refuse : rien n'a ete reserve
                details.append(f"systeme {sname} NON insere : aucun "
                               f"playfield de type soleil parmi les lignes "
                               f"disponibles — un systeme sans soleil est "
                               f"injoignable")
                continue
            applied_rows += rows_kept
            # commentaires/blancs du bloc source + secteurs retenus
            clone_sectors.children = [
                c for c in clone_sectors.children
                if not (isinstance(c, YamlEntry) and c.is_sequence_item)
            ] + kept
            _ensure_blank_before(working_solar.children, eol)
            working_solar.children.append(clone)
            continue

        # ---- systeme commun : secteurs et lignes manquants
        working_sectors_entry = _find_child(working_system, "Sectors")
        if working_sectors_entry is None:
            continue
        for sector in _seq_items(source_sectors_entry):
            ckey = _coords_key(_coords_text(sector))
            if ckey not in coords_map:
                continue
            want_rows = coords_map[ckey]
            working_sector = next(
                (c for c in _seq_items(working_sectors_entry)
                 if _coords_key(_coords_text(c)) == ckey), None)
            if working_sector is None:
                new_sector, names_in, _sun = _filtered_sector_copy(
                    sector, want_rows, global_pf, details, sname)
                if new_sector is None:
                    continue
                _ensure_blank_before(working_sectors_entry.children, eol)
                working_sectors_entry.children.append(new_sector)
                applied_rows += len(names_in)
                continue
            src_pf = _find_child(sector, "Playfields")
            work_pf = _find_child(working_sector, "Playfields")
            if src_pf is None or work_pf is None:
                continue
            existing = set()
            for c in _seq_items(work_pf):
                f = _split_flow(c.value) if c.value else []
                if len(f) > 1:
                    existing.add(f[1].casefold())
            for row in _seq_items(src_pf):
                fields = _split_flow(row.value) if row.value else []
                if len(fields) < 2 or not fields[1]:
                    continue
                nm = fields[1]
                if want_rows is not None and nm not in want_rows:
                    continue
                if nm.casefold() in global_pf or nm.casefold() in existing:
                    continue
                _ensure_blank_before(work_pf.children, eol)
                work_pf.children.append(_copy_entry(row))
                global_pf.add(nm.casefold())
                applied_rows += 1
    if applied_rows:
        from core.fsutil import atomic_write_text
        atomic_write_text(Path(working_yaml), working_doc.render())
    return applied_rows, details


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
                if source_sectors is not None \
                        and any(_sector_has_sun(s)
                                for s in _seq_items(source_sectors)) \
                        and not any(_sector_has_sun(s) for s in kept
                                    if isinstance(s, YamlEntry)
                                    and s.is_sequence_item):
                    continue    # son seul soleil est en conflit : casse
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
                              if _coords_key(_coords_text(c)) == ckey), None)
        working_sector = next((c for c in _seq_items(working_sectors_entry)
                               if _coords_key(_coords_text(c)) == ckey), None)
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
