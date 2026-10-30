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
"""Bilan « avant lancement » : les points qui font echouer le chargement
d'un scenario par le jeu, structures ou references — complements des
verifications moteur (tools/yamlcheck : syntaxe yaml/ecf) et des
references croisees ECF (cross_reference_check). Regles issues du vecu
projet ET du corpus officiel :

- Sectors.yaml : doublons de playfields entre systemes = exception
  « Duplicate playfield name » (vecu 01/10 'Parthix') ;
- systemes sans aucun soleil = injoignables (vecu 04/10 'Symos') ;
- fichiers etrangers dans Sectors/ : vecu 02/10, un Sectors.yaml.bak y a
  rendu la galaxie VIDE ;
- playfield reference par Sectors absent de Playfields/ (deploiement
  partiel) ;
- `Prefab:`/`PrefabName:` des playfields introuvable dans Prefabs/ (vecu
  forum : le POI n'apparait pas, « Playfield POI 'X' not found ») ;
- `GroupName:` de POI introuvable dans les groupes des prefabs (lus dans
  l'en-tete .epb, propriete 21 — pas besoin de bplib/partie en cours).
"""
import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.ecf.model import EcfBlock, EcfProperty, normalized_kind
from core.ecf.parser import parse_ecf_file
from core.sectors_merge import (find_broken_systems, find_duplicate_playfields,
                                _find_child, _find_solar_systems,
                                _is_sun_type, _seq_items, _split_flow,
                                _strip_quotes, _systems)
from core.yamllite.parser import parse_yaml_file

_PREFAB_RE = re.compile(r'Prefab(?:Name)?:[ \t]*([^,\r\n#]+)', re.M)
_GROUP_NAME_RE = re.compile(r'GroupName:[ \t]*([^,\r\n#]+)', re.M)
_POI_CONFIG_GROUP_RE = re.compile(r'-\s*GroupName:[ \t]*([^,\r\n#]+)')
_EGROUP_DEF_RE = re.compile(r'\{\s*EGroup\s+Name:\s*([^,\r\n}]+)')
_SPAWN_ENTITY_RE = re.compile(r'\{\s*\+?\s*Entity\s+Name:\s*([^,\r\n}]+)')
_ENTITIES_RE = re.compile(r'^(\s*)Entities:\s*$')
_NAMES_RE = re.compile(r'^\s*(?:-\s*)?Names:\s*(.+)$')
_GALAXY_INDEX_RE = re.compile(r'^Child (StarRegion|Territory)_(\d+)$')
# bloc nomme en tete d'un playfield : `DroneBaseSetup:` puis `Random:` /
# `Fixed:` avec un `GroupName:` a l'interieur — ce GroupName designe le bloc
# local, pas un groupe de prefab (vecu 22/10 : alerte a tort)
_TOP_KEY_RE = re.compile(r'^([A-Za-z0-9_.\- ]+):[ \t]*$')

# formes de valeurs pour le check « valeurs » (dictionnaire vanille)
_NUM_RE = re.compile(
    r'-?(?:\d+\.?\d*|\.\d+)[fF]?(?:\s*,\s*-?(?:\d+\.?\d*|\.\d+)[fF]?)*')
_LIST_RE = re.compile(r'\[[^\[\]]*\]')      # liste simple, pas de BBCode imbrique
# version du classificateur : entre dans la signature du cache — l'incrementer
# A CHAQUE changement de _value_family, sinon les caches ecrivent des familles
# incompatibles avec la lecture (vecu 11/10 : 175 faux positifs DefReputation)
_VALUE_SHAPES_VERSION = 2


def _value_family(v: str) -> str:
    """Famille grossiere d'une valeur ECF : num / bool / list / str.
    - chaine quotee a contenu numerique = 'num' (le jeu parse « "0.08" »,
      vecu corpus TraderNPCConfig RE2 ; et « "1,2" » = plage, vecu Count) ;
    - BBCode [c]... n'est PAS une liste (crochets imbriques = chaine) ;
    - decimales a point initial (.8) acceptees."""
    v = v.strip()
    if v.startswith('"'):
        # quotes + espaces interieurs (vecu corpus : « " -0.12, -0.12, ..." »)
        inner = v.strip('"').strip()
        return "num" if re.fullmatch(_NUM_RE, inner) else "str"
    if v.startswith("["):
        return "list" if _LIST_RE.fullmatch(v) else "str"
    if re.fullmatch(_NUM_RE, v):
        return "num"
    if v.lower() in ("true", "false"):
        return "bool"
    return "str"


@dataclass
class LaunchIssue:
    check: str          # identifiant du check (sectors, playfields, prefabs)
    path: str           # fichier concerne (chemin relatif au scenario)
    line: int           # 0 = non applicable
    severity: str       # "error" | "warning"
    message: str


def _find_sectors_yaml(root: Path) -> Path | None:
    for candidate in (root / "Sectors.yaml", root / "Sectors" / "Sectors.yaml"):
        if candidate.is_file():
            return candidate
    return None


def _index_prefabs(*roots: Path):
    """(noms disponibles, groupes/tags declarés par les prefabs).

    Un playfield reference un prefab par `Prefab:` ou `PrefabName:` avec le
    nom de FICHIER ou le Name interne de l'en-tete (les deux different
    souvent) : les deux sont indexes. Les groupes viennent de la propriete 21
    des .epb — la source que `_PoiGroupsConfig.yaml` appelle « groupes deja
    definis dans les fichiers blueprint » — plus les groupes que ce fichier
    declare ; aucun boot du jeu n'est necessaire (vecu 22/10 : bplib export
    exige une partie en cours)."""
    from core.epb_blueprint import read_header

    names: set[str] = set()
    groups: set[str] = set()
    for base in roots:
        if not base or not Path(base).is_dir():
            continue
        for dirpath, _dirs, files in os.walk(base):
            for fn in files:
                if not fn.lower().endswith(".epb"):
                    continue
                path = Path(dirpath) / fn
                names.add(path.stem.casefold())
                header = read_header(path)
                if header is None:
                    continue
                name, raw_groups = header
                if name:
                    names.add(name.casefold())
                for group in raw_groups.split(","):
                    if group.strip():
                        groups.add(group.strip().casefold())
        for cfg in Path(base).rglob("_PoiGroupsConfig.yaml"):
            try:
                text = cfg.read_text(encoding="utf-8-sig", errors="replace")
            except OSError:
                continue
            for line in _active_lines(text):
                match = _POI_CONFIG_GROUP_RE.search(line)
                if match:
                    groups.add(match.group(1).strip().strip("'\"").casefold())
    return names, groups


def _active_lines(text: str):
    """Lignes hors commentaire : un `# Prefab:` commente decrit ce qui est
    DESACTIVE (YAML-009), ce n'est pas une reference a verifier."""
    for line in text.splitlines():
        body = line.split("#", 1)[0]
        if body.strip():
            yield body


def _index_setups(playfields_root: Path) -> set[str]:
    """Blocs de premier niveau des playfields (`DroneBaseSetup:` /
    `R2DroneBase:` puis `Random:` ou `Fixed:` contenant un `GroupName:`).

    Un `GroupName` peut designer un de ces blocs locaux au lieu d'un groupe
    de prefab : c'est la forme utilisee par `playfield_static.yaml` pour les
    setups de drones (vecu 22/10 : alerte a tort sur DroneBaseSetup)."""
    names: set[str] = set()
    for pf_dir in sorted(playfields_root.iterdir()) if playfields_root.is_dir() else []:
        if not pf_dir.is_dir() or pf_dir.name.startswith('+'):
            continue
        for yaml_file in sorted(pf_dir.glob("*.yaml")):
            if yaml_file.name.startswith('+'):
                continue
            try:
                text = yaml_file.read_text(encoding="utf-8-sig",
                                           errors="replace")
            except OSError:
                continue
            for line in text.splitlines():
                m = _TOP_KEY_RE.match(line)
                if m:
                    names.add(m.group(1).strip().casefold())
    return names


def _check_prefabs(playfields_root: Path, names: set[str],
                   groups: set[str], rel_prefix: str) -> list[LaunchIssue]:
    """References des playfields aux prefabs, en UNE passe sur les fichiers :

    - `Prefab:` / `PrefabName:` absents des prefabs disponibles -> ERREUR
      (le POI n'apparaitra pas) ;
    - `GroupName:` absent des groupes declares par les .epb / noms de prefabs
      / `_PoiGroupsConfig.yaml` -> AVERTISSEMENT. La vanille elle-meme en
      reference une cinquantaine (fichiers de travail/edition) et le moteur
      ne les controle qu'au chargement du playfield : au boot, seul un
      playfield spatial est charge (vecu 22/10 : FarrSpaceDef). Une ligne par
      GROUPE, pas par occurrence : 331 lignes sur RE2-RPG noieraient le reste.
    """
    # marqueurs volontaires : « pas de POI ici », pas des groupes
    sentinels = {"nullpoi", "none", "null", "0"}
    issues: list[LaunchIssue] = []
    missing: dict[str, tuple[str, set[str]]] = {}
    for pf_dir in sorted(playfields_root.iterdir()) if playfields_root.is_dir() else []:
        if not pf_dir.is_dir() or pf_dir.name.startswith('+'):
            continue
        for yaml_file in sorted(pf_dir.glob("*.yaml")):
            if yaml_file.name.startswith('+'):
                continue
            try:
                text = yaml_file.read_text(encoding="utf-8-sig",
                                           errors="replace")
            except OSError:
                continue
            rel = f"{rel_prefix}/{yaml_file.parent.name}/{yaml_file.name}"
            for number, line in enumerate(text.splitlines(), 1):
                body = line.split("#", 1)[0]
                for m in _PREFAB_RE.finditer(body):
                    name = m.group(1).strip().strip('"\'')
                    if not name or name.casefold() in names:
                        continue
                    issues.append(LaunchIssue(
                        check="prefabs", path=rel, line=number,
                        severity="error",
                        message=f"Prefab '{name}' introuvable dans "
                                f"Prefabs/ (le POI n'apparaitra pas en jeu)"))
                for m in _GROUP_NAME_RE.finditer(body):
                    name = m.group(1).strip().strip('"\'')
                    key = name.casefold()
                    if not name or key in sentinels or key in groups:
                        continue
                    entry = missing.get(key)
                    if entry is None:
                        entry = missing[key] = (name, set())
                    entry[1].add(rel)
    for name, files in missing.values():
        issues.append(LaunchIssue(
            check="poi_groups", path=sorted(files)[0], line=0,
            severity="warning",
            message=f"groupe de POI '{name}' inconnu — aucun prefab, setup "
                    f"local ni _PoiGroupsConfig.yaml ne le declare "
                    f"({len(files)} playfield(s) : le POI ne sera pas "
                    f"genere ; si le groupe vient du scenario source, "
                    f"importer ses prefabs)"))
    return issues


def _declared_names(conf: Path) -> set[str]:
    """Noms declares dans BlocksConfig + ItemsConfig (casefold)."""
    names: set[str] = set()
    for fname in ("BlocksConfig.ecf", "ItemsConfig.ecf"):
        p = conf / fname
        if not p.exists():
            continue
        for b in parse_ecf_file(p).iter_blocks():
            nm = b.get('Name') or b.get_property('Name')
            if nm:
                names.add(nm.strip().strip('"').casefold())
    return names


# index de la bibliotheque (blueprints locaux + Workshop) — voir
# _library_idmapping_index


def _library_idmapping_index(
        files: tuple[Path, ...]) -> dict[str, tuple[int, str, str]]:
    """Noms de blocs des BLUEPRINTS de la bibliotheque (Saves/Blueprints +
    .epb a la RACINE des items Workshop) : {nom casefold: (nb fichiers,
    exemple, nom)}. Ce sont eux que le client parse au demarrage
    (`SWS.QueryItems AllBlueprintsSubscr`) ; les prefabs des packs Workshop
    (item/Prefabs/*.epb) ne sont PAS parses comme blueprints et restent hors
    scan (le scenario les couvre via Prefabs/). 148 .epb : instantane."""
    from core.epb_blueprint import read_id_mapping

    def work(f: Path):
        return f, read_id_mapping(f)

    index: dict[str, tuple[int, str, str]] = {}
    workers = min(16, (os.cpu_count() or 4) * 2)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for f, mapping in pool.map(work, files):
            if not mapping:
                continue
            for name in set(mapping.values()):
                if not name:
                    continue
                prev = index.get(name.casefold())
                index[name.casefold()] = (
                    (prev[0] + 1, prev[1], prev[2]) if prev
                    else (1, f.name, name))
    return index


def _check_epb_idmapping(root: Path, config_names: set[str],
                         vanilla_prefabs: Optional[Path],
                         rel_prefix: str,
                         library_files: tuple[Path, ...] = (),
                         vanilla_names: Optional[set[str]] = None
                         ) -> list[LaunchIssue]:
    """Table BlockIdMapping embarquee de chaque .epb vs config du scenario :
    le jeu resout chaque nom PAR NOM contre BlocksConfig/ItemsConfig au
    chargement des en-tetes ; absent -> « IdMapping: no name for id X found
    in '<BP>' » et le bloc est ignore au spawn (vecu 27/10 : 207 lignes, les
    prefabs de la base non fusionnee). Lecture BORNEE au header (read_id_
    mapping) : pas de decompression voxel ; les prefabs sans table (v28 et
    antes) n'ont rien a verifier. Une ligne par nom absent, aggregates sur
    tous les prefabs.

    La BIBLIOTHEQUE (blueprints locaux + .epb a la racine des items
    Workshop — pas les packs de prefabs) est scannee aussi : le client la
    parse au demarrage, et un nom absent le fait jeter « Block 'X' not
    found on block N » (vecu 27/10, Dreadspire). Seuls les noms qui existent
    en VANILLE sont signales (reintegrables en copiant la definition) ; les
    blocs d'autres mods sont hors de portee."""
    from core.epb_blueprint import read_id_mapping
    counts: dict[str, int] = {}
    examples: dict[str, str] = {}
    unreadable = checked = 0
    roots = [root / "Prefabs"]
    if vanilla_prefabs is not None and Path(vanilla_prefabs).is_dir():
        roots.append(Path(vanilla_prefabs))
    files = [f for base in roots for f in base.rglob("*.epb")]

    def work(f: Path):
        return f, read_id_mapping(f)

    workers = min(16, (os.cpu_count() or 4) * 2)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for f, mapping in pool.map(work, files):
            if mapping is None:
                unreadable += 1
                continue
            checked += 1
            for name in set(mapping.values()):
                if name and name.casefold() not in config_names:
                    counts[name] = counts.get(name, 0) + 1
                    examples.setdefault(name, f.name)
    issues: list[LaunchIssue] = []
    if unreadable:
        issues.append(LaunchIssue(
            check="prefabs", path=f"{rel_prefix}/Prefabs", line=0,
            severity="warning",
            message=f"{unreadable} prefab(s) illisibles (format exotique) : "
                    f"leur mapping de blocs n'a pas pu etre verifie"))
    if counts:
        ordered = sorted(counts.items(), key=lambda kv: -kv[1])
        shown = ordered[:15]
        for name, n in shown:
            issues.append(LaunchIssue(
                check="prefabs", path=f"{rel_prefix}/Prefabs", line=0,
                severity="warning",
                message=f"IdMapping: '{name}' absent de BlocksConfig/"
                        f"ItemsConfig — bloc ignore au spawn ({n} prefab(s), "
                        f"ex '{examples[name]}') ; reintegrer le bloc depuis "
                        f"sa source ou substituer un bloc existant"))
        if len(ordered) > len(shown):
            rest = ", ".join(n for n, _ in ordered[len(shown):])
            issues.append(LaunchIssue(
                check="prefabs", path=f"{rel_prefix}/Prefabs", line=0,
                severity="warning",
                message=f"IdMapping: et {len(ordered) - len(shown)} autre(s) "
                        f"nom(s) absent(s) de la config : {rest}"))
    if library_files and vanilla_names:
        index = _library_idmapping_index(tuple(library_files))
        lib: list[tuple[int, str, str]] = []
        for folded, (n, example, name) in index.items():
            if folded in config_names or folded not in vanilla_names:
                continue
            lib.append((n, example, name))
        lib.sort(key=lambda e: (-e[0], e[2].casefold()))
        for n, example, name in lib[:15]:
            issues.append(LaunchIssue(
                check="prefabs", path=f"{rel_prefix}/bibliotheque", line=0,
                severity="warning",
                message=f"IdMapping: '{name}' (bloc vanille) absent de la "
                        f"config — reference par la bibliotheque locale/"
                        f"Workshop ({n} fichier(s), ex '{example}') ; le "
                        f"client jette « Block '{name}' not found » au scan "
                        f"des blueprints : reintegrer la definition vanille"))
        if len(lib) > 15:
            rest = ", ".join(name for _n, _e, name in lib[15:])
            issues.append(LaunchIssue(
                check="prefabs", path=f"{rel_prefix}/bibliotheque", line=0,
                severity="warning",
                message=f"IdMapping: et {len(lib) - 15} autre(s) bloc(s) "
                        f"vanille absent(s) reference(s) par la bibliotheque "
                        f": {rest}"))
    return issues


def _declared_block_names(path: Path) -> set[str]:
    """Noms de blocs declares dans un BlocksConfig.ecf (avec ou sans Id)."""
    if not path.exists():
        return set()
    doc = parse_ecf_file(path)
    names = set()
    for b in doc.iter_blocks():
        nm = b.get('Name') or b.get_property('Name')
        if nm:
            names.add(nm.strip().strip('"').casefold())
    return names


def _check_block_groups(conf: Path, block_names: set[str]) -> list[LaunchIssue]:
    """BlockGroupsConfig.ecf : un bloc n'appartient qu'a UN groupe (le
    chargeur keyed par id de bloc) — la 2e occurrence est ignoree et la
    limite MaxCount de ce groupe ne s'applique plus (« Block name 'X' is
    duplicate in BlockGroups ecf file in '<g>' ») ; un nom absent de
    BlocksConfig est ignore aussi (« not found in BlockGroups »)."""
    path = conf / "BlockGroupsConfig.ecf"
    if not path.exists():
        return []
    issues: list[LaunchIssue] = []
    t = path.read_text(encoding="utf-8-sig", errors="replace")
    headers = list(re.finditer(
        r"(?m)^\s*\{\s*BlockGroup Name:\s*([^,\n}#]+)\s*$", t))
    seen: dict[str, str] = {}
    for k, hm in enumerate(headers):
        gname = hm.group(1).strip()
        seg = t[hm.end(): headers[k + 1].start() if k + 1 < len(headers)
                else len(t)]
        bm = re.search(r"(?m)^\s*Blocks:\s*\"([^\"]+)\"", seg)
        if not bm:
            continue
        for item in bm.group(1).split(","):
            b = item.strip()
            if not b:
                continue
            if b.casefold() not in block_names:
                issues.append(LaunchIssue(
                    check="blockgroups", path=str(path), line=0,
                    severity="warning",
                    message=f"BlockGroups: '{b}' du groupe '{gname}' "
                            f"introuvable dans BlocksConfig.ecf — ignore "
                            f"(« Block name '{b}' not found in BlockGroups "
                            f"ecf file »)"))
            elif b in seen:
                issues.append(LaunchIssue(
                    check="blockgroups", path=str(path), line=0,
                    severity="warning",
                    message=f"BlockGroups: '{b}' deja dans le groupe "
                            f"'{seen[b]}' — ignore ici ('{gname}') : la "
                            f"limite MaxCount de '{gname}' ne s'applique "
                            f"pas a ce bloc (« is duplicate ») ; retirer "
                            f"l'occurrence en trop"))
            else:
                seen[b] = gname
    return issues


def _check_compound_subdesc(playfields_root: Path,
                            rel_prefix: str) -> list[LaunchIssue]:
    """Playfields spatiaux : chaque nom d'une liste `Compound:` doit exister
    comme entree `IsCompoundSubDesc: True` du MEME fichier, sinon le compose
    n'est pas cree (« Compound POI 'X' not found! », vecu 27/10 :
    TestOrbitSnow/Temperate referenceaient les compounds Polaris sans les
    declarer — 9 erreurs par chargement)."""
    issues: list[LaunchIssue] = []
    entry = re.compile(r"^(\s*)- ")
    name_re = re.compile(r"^\s*Name:\s*\[([^\]]*)\]")
    compound = re.compile(r"^\s*Compound:\s*$")
    for f in sorted(playfields_root.glob("*/space_dynamic*.yaml")):
        if f.name.startswith('+'):
            continue
        lines = f.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        starts = [i for i, l in enumerate(lines) if entry.match(l)]
        subdescs: set[str] = set()
        for k, s in enumerate(starts):
            e = starts[k + 1] if k + 1 < len(starts) else len(lines)
            block = lines[s:e]
            if any("IsCompoundSubDesc" in l for l in block):
                for l in block:
                    nm = name_re.match(l)
                    if nm:
                        subdescs.update(x.strip() for x in nm.group(1).split(",")
                                        if x.strip())
        for i, l in enumerate(lines):
            if not compound.match(l):
                continue
            for j in range(i + 1, min(i + 6, len(lines))):
                nm = name_re.match(lines[j])
                if nm:
                    for n in (x.strip() for x in nm.group(1).split(",")
                              if x.strip()):
                        if n not in subdescs:
                            issues.append(LaunchIssue(
                                check="playfields",
                                path=f"{rel_prefix}/{f.parent.name}/{f.name}",
                                line=i + 1, severity="warning",
                                message=f"Compound: la liste reference "
                                        f"'{n}' sans sous-descripteur "
                                        f"IsCompoundSubDesc dans ce fichier "
                                        f"— le jeu : « Compound POI '{n}' "
                                        f"not found! », le compose n'est "
                                        f"pas cree (copier la declaration "
                                        f"depuis un playfield sain)"))
                    break
    return issues


def _check_egroups(playfields_root: Path, available: set[str],
                   rel_prefix: str) -> list[LaunchIssue]:
    """Groupes d'entites references par les playfields
    (`Entities:` puis `Names: [G1, G2]`, calibre corpus RE2-RPG : 0 faux
    positif) et absents d'EGroupsConfig.ecf (scenario OU vanille)."""
    issues: list[LaunchIssue] = []
    for pf_dir in sorted(playfields_root.iterdir()) if playfields_root.is_dir() else []:
        if not pf_dir.is_dir() or pf_dir.name.startswith('+'):
            continue
        for yaml_file in sorted(pf_dir.glob("*.yaml")):
            if yaml_file.name.startswith('+'):
                continue
            try:
                lines = yaml_file.read_text(
                    encoding="utf-8-sig", errors="replace").splitlines()
            except OSError:
                continue
            entities_indent: int | None = None
            for i, raw in enumerate(lines):
                line = raw.split("#", 1)[0].rstrip()
                if not line.strip():
                    continue
                indent = len(line) - len(line.lstrip())
                if entities_indent is not None and indent <= entities_indent:
                    entities_indent = None
                if entities_indent is None:
                    if _ENTITIES_RE.match(line):
                        entities_indent = indent
                    continue
                m = _NAMES_RE.match(line)
                if not m:
                    continue
                for token in re.split(r'[\[\],]', m.group(1)):
                    name = token.strip().strip("'\"").strip()
                    if not name or name.casefold() in available:
                        continue
                    issues.append(LaunchIssue(
                        check="egroups",
                        path=f"{rel_prefix}/{yaml_file.parent.name}/{yaml_file.name}",
                        line=i + 1, severity="error",
                        message=f"groupe d'entites '{name}' introuvable dans "
                                f"EGroupsConfig.ecf (spawn rate au sol : "
                                f"le groupe sera ignore)"))
    return issues


def _check_galaxy(root: Path) -> list[LaunchIssue]:
    """GalaxyConfig.ecf : les Child StarRegion_N / Territory_N doivent former
    une sequence SANS doublon ni trou par famille — l'IndexOutOfRangeException
    vecu en jeu venait exactement de la (galaxy_merge renumerote pour ca)."""
    path = root / "Content" / "Configuration" / "GalaxyConfig.ecf"
    if not path.is_file():
        return []
    try:
        doc = parse_ecf_file(path)
    except Exception as exc:            # noqa: BLE001 - fichier illisible
        return [LaunchIssue(check="galaxy", path=str(path.relative_to(root)),
                            line=0, severity="error",
                            message=f"GalaxyConfig.ecf illisible ({exc})")]
    families: dict[str, list[int]] = {}
    for node in doc.nodes:
        if not isinstance(node, EcfBlock):
            continue
        m = _GALAXY_INDEX_RE.match(normalized_kind(node.kind or ""))
        if m:
            families.setdefault(m.group(1), []).append(int(m.group(2)))
    issues: list[LaunchIssue] = []
    for family, indexes in families.items():
        seen: set[int] = set()
        for idx in indexes:
            if idx in seen:
                issues.append(LaunchIssue(
                    check="galaxy", path=str(path.relative_to(root)),
                    line=0, severity="error",
                    message=f"{family}_{idx} en DOUBLON dans GalaxyConfig.ecf "
                            f"(IndexOutOfRangeException au chargement)"))
            seen.add(idx)
        missing = sorted(set(range(1, max(indexes) + 1)) - seen)
        if missing:
            issues.append(LaunchIssue(
                check="galaxy", path=str(path.relative_to(root)),
                line=0, severity="error",
                message=f"{family} : sequence discontinue, trous en "
                        f"{missing} (le jeu indexe les regions de 1 a "
                        f"{max(indexes)} sans trou)"))
    return issues


def _check_bin_caches(root: Path) -> list[LaunchIssue]:
    """Caches compiles du jeu : un *.yaml.bin SANS son yaml = residu
    (purge par la synchro miroir) ; un .bin a la MEME date que son yaml =
    signature d'une copie avec mtime conserve (vecu 05/10 : le jeu juge le
    cache plus frais et sert l'ANCIEN playfield). Dates seul indice
    possible : le contenu .bin est compile."""
    issues: list[LaunchIssue] = []
    for bin_file in root.rglob("*.yaml.bin"):
        yaml_file = Path(str(bin_file)[:-4])
        if not yaml_file.is_file():
            issues.append(LaunchIssue(
                check="caches", path=str(bin_file.relative_to(root)),
                line=0, severity="warning",
                message="cache .yaml.bin orphelin (yaml absent) : residu a "
                        "purger par la synchronisation"))
            continue
        delta = abs(bin_file.stat().st_mtime - yaml_file.stat().st_mtime)
        if delta <= 1.5:
            issues.append(LaunchIssue(
                check="caches", path=str(bin_file.relative_to(root)),
                line=0, severity="warning",
                message="cache .bin a la meme date que son yaml (copie avec "
                        "mtime conserve : le jeu peut servir l'ANCIEN "
                        "contenu) — relancer la synchronisation"))
    return issues


def _clean_def_name(raw: str) -> str:
    """Commentaires /* */ et # colles au nom (vecu corpus : EGroupsConfig
    263 « Name: TalonGuardianHerd   /* Talon faction */ », Default
    Multiplayer 1461 « Name: FarrPatrolSmall   # 2-3 units, No O2 »)."""
    return re.sub(r'/\*.*?\*/', '', raw).split('#')[0].strip().strip('"').casefold()


def _index_spawn_names(*config_files: Path) -> set[str]:
    """Noms spawnables : groupes EGroup (EGroupsConfig.ecf) ET creatures
    Entity (EClassConfig.ecf) — Entities:/Names: accepte les DEUX (vecu
    corpus : AssaultCyborgDamaged est une Entity vanille, pas un groupe)."""
    names: set[str] = set()
    for f in config_files:
        if not f or not Path(f).is_file():
            continue
        try:
            text = Path(f).read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        for regex in (_EGROUP_DEF_RE, _SPAWN_ENTITY_RE):
            for m in regex.finditer(text):
                names.add(_clean_def_name(m.group(1)))
    return names


def _iter_ecf_pairs(doc, filename):
    """Toutes les paires (fichier, kind de bloc, propriete, valeur)."""
    def walk(nodes, kind):
        for n in nodes:
            if isinstance(n, EcfBlock):
                k = normalized_kind(n.kind or "").rstrip(",").strip() or kind
                yield from walk(n.children, k)
            elif isinstance(n, EcfProperty):
                for key, v in n.pairs:
                    if key:
                        yield filename, kind, key, str(v)
    yield from walk(doc.nodes, "")


def _index_value_shapes(conf_dir: Path) -> dict:
    """(fichier, kind, propriete) -> {familles} observees dans la VANILLE :
    un « schema » fiable des types de valeurs, sans dependance au moteur
    (qui ne documente pas ses champs)."""
    shapes: dict = {}
    for f in conf_dir.glob("*.ecf"):
        try:
            doc = parse_ecf_file(f)
        except Exception:
            continue
        for fn, kind, key, v in _iter_ecf_pairs(doc, f.name):
            shapes.setdefault((f.name, kind, key), set()).add(
                _value_family(v))
    return shapes


def _check_values(root: Path, vanilla_conf: Path | None,
                  rel_prefix: str) -> list[LaunchIssue]:
    """Valeurs dont la FAMILLE contredit tout ce que la vanille observe pour
    la meme propriete (ex. Health: abc) — warning car le corpus officiel
    prouve que le jeu tolere des usages de type differents selon le bloc
    (vecu : EClass param2 bool/int vanille vs EntityShipSV en REX)."""
    if vanilla_conf is None or not vanilla_conf.is_dir():
        return []
    import json
    cache = Path.home() / ".empyrion_editor" / "cache" / "value_shapes.json"
    sig_file = cache.with_suffix(".sig")
    sig = json.dumps([_VALUE_SHAPES_VERSION,
                      sorted(str(p) for p in vanilla_conf.glob("*.ecf"))])
    shapes_van: dict = {}
    if cache.is_file() and sig_file.is_file():
        try:
            if sig_file.read_text(encoding="utf-8") == sig:
                raw = json.loads(cache.read_text(encoding="utf-8"))
                shapes_van = {(a, b, c): set(f) for a, b, c, f in raw}
        except (OSError, ValueError):
            shapes_van = {}
    if not shapes_van:
        shapes_van = _index_value_shapes(vanilla_conf)
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(
                [(a, b, c, sorted(f)) for (a, b, c), f in shapes_van.items()]),
                encoding="utf-8")
            sig_file.write_text(sig, encoding="utf-8")
        except OSError:
            pass
    fallback: dict = {}
    for (f2, _kind, k3), fams in shapes_van.items():
        fallback.setdefault((f2, k3), set()).update(fams)

    issues: list[LaunchIssue] = []
    conf_dir = root / "Content" / "Configuration"
    n_bad = 0
    for f in sorted(conf_dir.glob("*.ecf")) if conf_dir.is_dir() else []:
        try:
            doc = parse_ecf_file(f)
        except Exception:
            continue
        for fn, kind, key, v in _iter_ecf_pairs(doc, f.name):
            fams = shapes_van.get((f.name, kind, key)) \
                or fallback.get((f.name, key))
            if not fams:
                continue
            fam = _value_family(v)
            # TOLERANCES prouvees par le corpus officiel :
            # - TOUTE valeur QUOTEE est acceptee par le jeu (il strip les
            #   quotes et parse ; defaut silencieux si illisible) — vecu :
            #   DefReputation « "Friendly" » ou vanilla=num,
            #   LootGroups REX « "meta=4002" », NebulaColors « 0.5f » ;
            # - un booleen litteral se parse partout ou une chaine se parse
            #   (ShowUser: true dans Rise of the Dark Faction officiel)
            if (v.lstrip().startswith('"')
                    or fam in fams
                    or (fam == "bool" and "str" in fams)):
                continue
            n_bad += 1
            issues.append(LaunchIssue(
                check="values",
                path=f"{conf_dir.name}/{f.name}",
                line=0, severity="warning",
                message=f"valeur inattendue pour '{key}' : '{v[:40]}' — "
                        f"la vanille n'utilise jamais ce type ici",
            ))
            if n_bad >= 50:
                # garde-fou : un fichier entier mal converti inonderait le bilan
                issues.append(LaunchIssue(
                    check="values", path=f"{conf_dir.name}/{f.name}",
                    line=0, severity="warning",
                    message="plus de 50 valeurs inattendues : verifiez la "
                            "conversion de ce fichier"))
                return issues
    return issues


def _check_numeric_types(root: Path) -> list[LaunchIssue]:
    """Cle a valeur numerique sans attribut 'type:' alors que la MEME cle est
    typee ailleurs dans le fichier : le jeu lit la valeur en string
    ('Error converting property ... Type: System.String', valeur IGNOREE —
    vecu 18/10 : 5 ThrusterForce + 2 HitPoints ecrites nues, propulseurs sans
    poussee ; le dedie ne le voit JAMAIS, il n'instancie pas le monde).
    Blocs avec TemplateRoot exclus (le type vient du template) ; valeurs
    quotees exclues (guillemets = chaine volontaire)."""
    numeric_re = re.compile(r"^-?\d+(\.\d+)?$")
    issues: list[LaunchIssue] = []
    conf_dir = root / "Content" / "Configuration"
    if not conf_dir.is_dir():
        return issues
    n_bad = 0
    for f in sorted(conf_dir.glob("*.ecf")):
        try:
            doc = parse_ecf_file(f)
        except Exception:
            continue

        def _collect(block: EcfBlock, acc: list) -> None:
            acc.append(block)
            for c in block.children:
                if isinstance(c, EcfBlock):
                    _collect(c, acc)

        blocks: list[EcfBlock] = []
        for n in doc.nodes:
            if isinstance(n, EcfBlock):
                _collect(n, blocks)

        typed_keys: set[str] = set()
        for b in blocks:
            for child in b.children:
                if not isinstance(child, EcfProperty):
                    continue
                if any(k == "type" for k, _v in child.pairs if k):
                    typed_keys.update(k for k, _v in child.pairs if k)

        for b in blocks:
            # TemplateRoot : le type vient du template. Ref : la propriete
            # ECRASE une valeur heritee typed — c'est la seule combinaison
            # prouvee fatale (la vanille ecrit elle-meme des numeriques nus
            # sans Ref, ex: 'Range: 200' d'armes, et ils fonctionnent).
            if b.get("TemplateRoot") is not None or b.get("Ref") is None:
                continue
            for child in b.children:
                if not isinstance(child, EcfProperty):
                    continue
                if any(k == "type" for k, _v in child.pairs if k):
                    continue
                for k, v in child.pairs:
                    if (k in typed_keys and v is not None
                            and not v.lstrip().startswith('"')
                            and numeric_re.match(v.strip())):
                        n_bad += 1
                        issues.append(LaunchIssue(
                            check="types",
                            path=f"{conf_dir.name}/{f.name}",
                            line=0, severity="warning",
                            message=f"'{k}: {v[:30]}' sans 'type:' alors que "
                                    f"la meme cle est typee ailleurs dans ce "
                                    f"fichier — le jeu la lira en string "
                                    f"(valeur ignoree)",
                        ))
                        break   # une seule alerte par ligne
            if n_bad >= 30:
                issues.append(LaunchIssue(
                    check="types", path=f"{conf_dir.name}/{f.name}",
                    line=0, severity="warning",
                    message="plus de 30 valeurs numeriques sans 'type:' : "
                            "verifiez la conversion de ce fichier"))
                return issues
    return issues


def run_launch_checks(scenario_root: Path, vanilla_content: str = "") -> list[LaunchIssue]:
    """Tous les checks structurels « avant lancement » du scenario pointe
    par `scenario_root` (copie de travail OU production)."""
    root = Path(scenario_root)
    issues: list[LaunchIssue] = []

    sectors_yaml = _find_sectors_yaml(root)
    if sectors_yaml is None:
        issues.append(LaunchIssue(
            check="sectors", path="Sectors.yaml", line=0, severity="error",
            message="Sectors.yaml introuvable (ni a la racine, ni dans Sectors/)"))
        return issues

    # --- fichiers etrangers dans le dossier Sectors/ (vecu 02/10 : galaxie
    # vide a cause d'un Sectors.yaml.bak — le jeu charge le dossier entier) ---
    sectors_dir = sectors_yaml.parent
    if sectors_dir.is_dir():
        for entry in sorted(sectors_dir.iterdir()):
            if not entry.is_file() or entry.name.lower() == "sectors.yaml":
                continue
            sev = "error" if entry.name.lower().endswith(".bak") else "warning"
            issues.append(LaunchIssue(
                check="sectors",
                path=f"{sectors_dir.name}/{entry.name}", line=0, severity=sev,
                message=f"fichier etranger dans {sectors_dir.name}/ : le jeu "
                        f"peut le charger comme secteurs (vecu : galaxie vide)"))

    # --- doublons de playfields entre systemes (crash « Duplicate playfield
    # name ») et systemes sans soleil (injoignables) ---
    for pf, systems in find_duplicate_playfields(sectors_yaml).items():
        issues.append(LaunchIssue(
            check="sectors", path=str(sectors_yaml.relative_to(root)),
            line=0, severity="error",
            message=f"playfield '{pf}' declare dans plusieurs systemes "
                    f"({' , '.join(systems)}) : exception « Duplicate "
                    f"playfield name » au chargement"))
    for system in find_broken_systems(sectors_yaml):
        issues.append(LaunchIssue(
            check="sectors", path=str(sectors_yaml.relative_to(root)),
            line=0, severity="warning",
            message=f"systeme '{system}' sans aucun soleil : injoignable en jeu"))

    # --- playfields references vs dossiers reels (scenario OU vanille :
    # les scenarios a generateur referencent les templates de
    # Content/Playfields du jeu — GasGiant, Omicron, SpaceWarpTarget...) ---
    playfields_root = root / "Playfields"
    available_dirs = {d.name.casefold() for d in playfields_root.iterdir()
                      if d.is_dir()} if playfields_root.is_dir() else set()
    if vanilla_content and (Path(vanilla_content) / "Playfields").is_dir():
        available_dirs |= {d.name.casefold()
                           for d in (Path(vanilla_content) / "Playfields").iterdir()
                           if d.is_dir()}
    referenced: list[str] = []
    doc = parse_yaml_file(sectors_yaml)
    solar = _find_solar_systems(doc)
    if solar is not None:
        for system in _systems(solar):
            sectors_entry = _find_child(system, "Sectors")
            rows = []
            if sectors_entry is not None:
                for sector in _seq_items(sectors_entry):
                    pf_entry = _find_child(sector, "Playfields")
                    if pf_entry is not None:
                        rows.extend(_seq_items(pf_entry))
                    else:
                        rows.append(sector)
            for row in rows:
                fields = _split_flow(row.value) if row.value else []
                if len(fields) < 3 or not fields[1]:
                    continue
                referenced.append(_strip_quotes(fields[2]))
    for pf in dict.fromkeys(referenced):    # dedup, ordre conserve
        if _is_sun_type(pf) or pf.casefold() in available_dirs:
            continue
        issues.append(LaunchIssue(
            check="playfields", path=str(sectors_yaml.relative_to(root)),
            line=0, severity="error",
            message=f"playfield '{pf}' reference par Sectors mais absent de "
                    f"Playfields/ (deploiement partiel ?)"))

    # --- Prefabs des playfields (`Prefab:` et `PrefabName:`) + groupes de
    # POI (`GroupName:`), sans boot du jeu : les groupes sont lus dans
    # l'en-tete des .epb (propriete 21) — unique source fiable en dehors
    # d'une partie en cours (bplib export) ---
    prefab_names, prefab_groups = _index_prefabs(
        root / "Prefabs",
        Path(vanilla_content) / "Prefabs" if vanilla_content else None)
    issues.extend(_check_prefabs(playfields_root, prefab_names,
                                 prefab_groups | prefab_names
                                 | _index_setups(playfields_root),
                                 playfields_root.name))

    # --- mapping de blocs embarque des .epb vs config du scenario («
    # IdMapping: no name » du client, vecu 27/10 : 207 lignes) + bibliotheque
    # locale/Workshop (le client la parse au demarrage, vecu 27/10 :
    # « Block 'ThrusterJetMSRound3x13x3' not found » sur un blueprint) ---
    conf = root / "Content" / "Configuration"
    config_names = _declared_names(conf)
    vanilla_names: Optional[set[str]] = None
    library_files: tuple[Path, ...] = ()
    if vanilla_content:
        vanilla_names = _declared_names(
            Path(vanilla_content) / "Configuration")
        vpath = Path(vanilla_content)
        files = list((vpath.parent / "Saves" / "Blueprints").rglob("*.epb"))
        if len(vpath.parents) > 2:
            ws = vpath.parents[2] / "workshop" / "content" / "383120"
            if ws.is_dir():
                # blueprints = .epb a la RACINE des items ; les packs de
                # prefabs (item/Prefabs/) ne sont pas parses au demarrage
                files += list(ws.glob("*/*.epb"))
        library_files = tuple(files)
    issues.extend(_check_epb_idmapping(
        root, config_names,
        Path(vanilla_content) / "Prefabs" if vanilla_content else None,
        playfields_root.name, library_files, vanilla_names))

    # --- compounds des playfields spatiaux : toute liste `Compound:` doit
    # avoir ses sous-descripteurs IsCompoundSubDesc dans le meme fichier ---
    issues.extend(_check_compound_subdesc(playfields_root,
                                          playfields_root.name))

    # --- groupes d'entites (Entities:/Names:) vs EGroupsConfig.ecf +
    # EClassConfig.ecf (scenario OU vanille — EGroup et Entity se fusionnent
    # par nom) ---
    spawn_files = [conf / "EGroupsConfig.ecf", conf / "EClassConfig.ecf"]
    if vanilla_content:
        vanilla_conf = Path(vanilla_content) / "Configuration"
        spawn_files += [vanilla_conf / "EGroupsConfig.ecf",
                        vanilla_conf / "EClassConfig.ecf"]
    issues.extend(_check_egroups(playfields_root,
                                 _index_spawn_names(*spawn_files),
                                 playfields_root.name))

    # --- BlockGroupsConfig : bloc inconnu ou deja reclame par un autre
    # groupe (la limite MaxCount du groupe ecarte ne s'applique plus) ---
    block_names = {n.rstrip() for n in
                   _declared_block_names(conf / "BlocksConfig.ecf")}
    issues.extend(_check_block_groups(conf, block_names))

    # --- GalaxyConfig : sequences Child StarRegion/Territory contigues ---
    issues.extend(_check_galaxy(root))

    # --- caches .yaml.bin (orphelins, date = copie mtime conserve) ---
    issues.extend(_check_bin_caches(root))

    # --- valeurs de type inattendu vs dictionnaire de formes de la vanille
    # (le seul « schema » fiable : le jeu ne documente pas ses types) ---
    issues.extend(_check_values(root,
                                Path(vanilla_content) / "Configuration"
                                if vanilla_content else None,
                                "Content"))

    # --- valeurs numeriques sans 'type:' (lues en string par le jeu,
    # invisibles au boot dedie qui n'instancie pas le monde) ---
    issues.extend(_check_numeric_types(root))

    # --- chargeurs du moteur repliques (regles verifiees contre le
    # chargement reel du jeu, 25/10/2026) : les
    # exceptions fatales des chargeurs ECF/TechTree du jeu, listees d'un
    # coup — le boot reel n'en montre qu'une par iteration ---
    from .engine_loaders import run_engine_loader_checks
    issues.extend(run_engine_loader_checks(root, vanilla_content))

    # --- ondes de spawn : patrouilles de drones actives sans base, zones de
    # taux ne designant aucun POI (core/spawn_waves.py, calibre sur vrais
    # playfields — geantes gazeuses [0,0] et listes mixtes jamais alertees) ---
    from .spawn_waves import scan as scan_spawn_waves
    for issue in scan_spawn_waves(root).issues:
        spawn_path = issue.file_path
        issues.append(LaunchIssue(
            check="spawn",
            path=spawn_path.relative_to(root).as_posix()
            if spawn_path else "",
            line=0, severity=issue.level,
            message=f"[{issue.code}] {issue.message}"))

    # --- defenses de faction : faction absente de Factions.ecf, groupe ou
    # categorie jamais fournie, prix min > max (core/faction_warfare.py) ---
    from .faction_warfare import scan as scan_warfare
    for issue in scan_warfare(root).issues:
        war_path = issue.file_path
        issues.append(LaunchIssue(
            check="warfare",
            path=war_path.relative_to(root).as_posix() if war_path else "",
            line=0, severity=issue.level,
            message=f"[{issue.code}] {issue.message}"))

    # --- PDA : declencheurs 'Check:' hors du vocabulaire connu (enum moteur
    # GameEventType + extras PDA + schema) — sans bloquer l'edition ---
    # --- jetons de quete : structure de TokenConfig + references
    # 'Token:<id>' introuvables (core/token_config.py) ---
    from .token_config import check_tokens
    for issue in check_tokens(root):
        token_path = issue.file_path
        issues.append(LaunchIssue(
            check="tokens",
            path=token_path.relative_to(root).as_posix() if token_path else "",
            line=0, severity=issue.level,
            message=f"[{issue.code}] {issue.message}"))

    # --- scripts C# du scenario : compilation reelle (csc + assemblies du
    # jeu) — le boot du jeu n'affiche qu'une erreur a la fois ---
    from .pda.script_gen import check_scripts
    for issue in check_scripts(root):
        script_path = issue.file_path
        issues.append(LaunchIssue(
            check="scripts",
            path=script_path.relative_to(root).as_posix() if script_path else "",
            line=0, severity=issue.level,
            message=f"[{issue.code}] {issue.message}"))

    from .pda.event_types import unknown_pda_checks
    for pda_path, value, count in unknown_pda_checks(root):
        issues.append(LaunchIssue(
            check="pda",
            path=pda_path.relative_to(root).as_posix(),
            line=0, severity="warning",
            message=f"[W350] declencheur PDA inconnu : 'Check: {value}' "
                    f"({count} occurrence(s)) — ni l'enumeration du moteur ni "
                    f"un declencheur observe"))
    return issues
