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
- PrefabName des playfields introuvable dans Prefabs/ (vecu forum : le POI
  n'apparait pas, « Playfield POI 'X' not found »).
"""
import os
import re
from dataclasses import dataclass
from pathlib import Path

from core.ecf.model import EcfBlock, EcfProperty, normalized_kind
from core.ecf.parser import parse_ecf_file
from core.sectors_merge import (find_broken_systems, find_duplicate_playfields,
                                _find_child, _find_solar_systems,
                                _is_sun_type, _seq_items, _split_flow,
                                _strip_quotes, _systems)
from core.yamllite.parser import parse_yaml_file

_PREFAB_RE = re.compile(r'PrefabName:\s*([^,\r\n]+?)\s*(?:,|$)', re.M)
_EGROUP_DEF_RE = re.compile(r'\{\s*EGroup\s+Name:\s*([^,\r\n}]+)')
_SPAWN_ENTITY_RE = re.compile(r'\{\s*\+?\s*Entity\s+Name:\s*([^,\r\n}]+)')
_ENTITIES_RE = re.compile(r'^(\s*)Entities:\s*$')
_NAMES_RE = re.compile(r'^\s*(?:-\s*)?Names:\s*(.+)$')
_GALAXY_INDEX_RE = re.compile(r'^Child (StarRegion|Territory)_(\d+)$')

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


def _index_prefabs(*roots: Path) -> set[str]:
    """Noms de prefabs disponibles (basenames sans extension, casefold)."""
    names: set[str] = set()
    for base in roots:
        if not base or not Path(base).is_dir():
            continue
        for dirpath, _dirs, files in os.walk(base):
            for fn in files:
                if fn.lower().endswith(".epb"):
                    names.add(Path(fn).stem.casefold())
    return names


def _check_prefabs(playfields_root: Path, available: set[str],
                   rel_prefix: str) -> list[LaunchIssue]:
    issues: list[LaunchIssue] = []
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
            for m in _PREFAB_RE.finditer(text):
                name = m.group(1).strip().strip('"').split(" #")[0].strip()
                if not name or name.casefold() in available:
                    continue
                line = text.count("\n", 0, m.start()) + 1
                issues.append(LaunchIssue(
                    check="prefabs",
                    path=f"{rel_prefix}/{yaml_file.parent.name}/{yaml_file.name}",
                    line=line, severity="error",
                    message=f"PrefabName '{name}' introuvable dans "
                            f"Prefabs/ (le POI n'apparaitra pas en jeu)",
                ))
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
    le seul « schema » fiable des types de valeurs — le jeu ne le documente
    pas et ses classes sont obfusquees."""
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

    # --- PrefabName des playfields (POI fantomes en jeu) ---
    available = _index_prefabs(root / "Prefabs",
                               Path(vanilla_content) / "Prefabs" if vanilla_content else None)
    issues.extend(_check_prefabs(playfields_root, available,
                                 playfields_root.name))

    # --- POIs fantomes : PAS de check statique fiable — sur RE2-RPG, le
    # moteur n'a rejete qu'UN groupe (FarrSpaceDef) quand la sous-chaine en
    # soupconnait 25 ; seule source fiable = le BOOT DEDIE, dont le log
    # « Blueprint group 'X' not found or empty! » est capture par la case
    # « tester le chargement reel » du bilan.

    # --- groupes d'entites (Entities:/Names:) vs EGroupsConfig.ecf +
    # EClassConfig.ecf (scenario OU vanille — EGroup et Entity se fusionnent
    # par nom) ---
    conf = root / "Content" / "Configuration"
    spawn_files = [conf / "EGroupsConfig.ecf", conf / "EClassConfig.ecf"]
    if vanilla_content:
        vanilla_conf = Path(vanilla_content) / "Configuration"
        spawn_files += [vanilla_conf / "EGroupsConfig.ecf",
                        vanilla_conf / "EClassConfig.ecf"]
    issues.extend(_check_egroups(playfields_root,
                                 _index_spawn_names(*spawn_files),
                                 playfields_root.name))

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
    return issues
