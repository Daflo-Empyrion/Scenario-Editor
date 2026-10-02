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

"""Fusion SPECIALISEE de GalaxyConfig.ecf (demande du 01/10/2026) : le
fichier a des noms de blocs REPETES legitimes (variantes de classes,
ex « B Type Star » x5) -> la fusion ECF generique le REFUSE (garde-fou
v1.13). Ce module apparie les blocs par (Name, StarClass), traite le
bloc General a part (diff informatif, working prioritaire), collecte les
DEPENDANCES des blocs importes (SolarSystemConfigSuffix ->
RandomPresets/SolarSystemConfig<Suffix>.yaml -> playfields referencés ->
Playfields/<Nom>/) et applique avec separateur commente, .bak et
IDEMPOTENCE (re-fusion = « deja importe », jamais de redoublonnage).

Les refs Sectors.yaml (AllowSystem) et les blocs GalaxySpawnAmount: 0
(systemes places a la main) ne donnent que des AVERTISSEMENTS : le
placement reste un choix humain (core/sectors_merge.py).

Limites du jeu (en-tete vanille) : StarRegion_1..199, Territory_1..20,
Other_1..10, jusqu'a 30 gradients NebulaColorsN."""

import copy
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from core.ecf.model import (EcfBlock, EcfComment, EcfProperty,
                            add_property_line, normalized_kind)
from core.ecf.parser import parse_ecf_file
from core.fsutil import atomic_write_text

SEPARATOR_MARKER = "Fusion depuis"
GENERAL_NAME = "General"
_PRESET_PREFIX = "SolarSystemConfig"
# Blocs indexes du format vanille (documente en tete de GalaxyConfig) :
# Child StarRegion_1..199, Child Territory_1..20. RenumeroTES en sequence
# CONTIGUE apres fusion (l'IndexOutOfRangeException vecu vient des trous/
# doublons d'index, pas seulement des doublons).
_INDEXED_FAMILIES = ("StarRegion", "Territory")
_INDEXED_RE = re.compile(r"^Child (StarRegion|Territory)_(\d+)$")
_FACTION_FILE = "Factions.ecf"
_REPUTATION_FILE = "DefReputation.ecf"
_WARFARE_FILE = "FactionWarfare.ecf"


@dataclass(frozen=True)
class GalaxyBlock:
    """Un bloc classe de systeme (tout sauf General)."""
    name: str
    star_class: str
    key: str
    node: EcfBlock
    solar_suffix: str = ""          # SolarSystemConfigSuffix (sans guillemets)
    spawn_amount: Optional[float] = None


@dataclass(frozen=True)
class IndexedBlock:
    """Child StarRegion_N / Territory_N (format vanille indexe)."""
    family: str                     # StarRegion | Territory
    index: int
    node: EcfBlock
    props: Tuple[Tuple[str, str], ...] = ()


@dataclass
class FactionImport:
    """Faction custom requise par un Territory importe."""
    name: str
    node: Optional[EcfBlock]        # bloc { Faction ... } chez la source
    has_reputation: bool            # DefReputation source la mentionne
    has_warfare: bool               # FactionSettings chez la source
    reputation: Dict[str, str] = field(default_factory=dict)
    # {nom du bloc Reputation chez B: valeur} -> a propager dans le
    # DefReputation du working (meme bloc d'Origine)


@dataclass(frozen=True)
class NamedBlockImport:
    """Bloc nomme a importer (EGroup des playfields importes)."""
    name: str
    node: EcfBlock


@dataclass
class GalaxyDependency:
    """Fichier a copier depuis la source vers la copie de travail."""
    relative: str                   # chemin relatif au root (chemins POSIX)
    source_path: Path
    reason: str


@dataclass
class GalaxyPlan:
    """Plan de fusion : apercu cochable, rien n'est ecrit avant apply."""
    blocks_add: List[GalaxyBlock] = field(default_factory=list)
    blocks_same: List[str] = field(default_factory=list)
    general_diff: List[Tuple[str, str, str]] = field(default_factory=list)
    deps: List[GalaxyDependency] = field(default_factory=list)
    playfields_missing: List[str] = field(default_factory=list)
    playfields_absent: List[str] = field(default_factory=list)
    sector_warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    # --- tranche 2 ---
    indexed_add: Dict[str, List[IndexedBlock]] = field(
        default_factory=dict)           # family -> blocs de B a ajouter
    indexed_same: List[str] = field(default_factory=list)
    indexed_limits: List[str] = field(default_factory=list)
    factions_to_import: List[FactionImport] = field(default_factory=list)
    factions_unknown: List[str] = field(default_factory=list)
    warfare_warnings: List[str] = field(default_factory=list)
    has_factions_ecf: bool = False
    source_general: Optional[EcfBlock] = None
    egroups_to_import: List[NamedBlockImport] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _attr(node: EcfBlock, prop: str) -> str:
    v = node.get_property(prop)
    return str(v).strip().strip('"') if v is not None else ""


def _body_props(node: EcfBlock) -> Dict[str, str]:
    """Proprietes du CORPS (children EcfProperty — pairs ne couvre que la
    ligne d'ouverture)."""
    out: Dict[str, str] = {}
    for ch in node.children:
        if isinstance(ch, EcfProperty):
            for k, v in ch.pairs:
                if k and k not in out:
                    out[k] = str(v).strip()
    return out


def _block_key(node: EcfBlock) -> str:
    return f"{_attr(node, 'Name')}|{_attr(node, 'StarClass')}"


def _galaxy_blocks(doc) -> Tuple[Optional[EcfBlock], List[GalaxyBlock],
                                 Dict[str, List[IndexedBlock]]]:
    """(bloc General, classes de systemes, blocs indexes) d'un
    GalaxyConfig parse."""
    general: Optional[EcfBlock] = None
    blocks: List[GalaxyBlock] = []
    indexed: Dict[str, List[IndexedBlock]] = {}
    for node in doc.nodes:
        if not isinstance(node, EcfBlock):
            continue
        # kind rendu avec sa virgule de separation (« GalaxyConfig, »)
        kind = normalized_kind(node.kind).rstrip(",").strip()
        if kind == "GalaxyConfig":
            if _attr(node, "Name") == GENERAL_NAME:
                general = node
                continue
            suffix = _attr(node, "SolarSystemConfigSuffix")
            try:
                amount = float(_attr(node, "GalaxySpawnAmount"))
            except ValueError:
                amount = None
            blocks.append(GalaxyBlock(
                name=_attr(node, "Name"), star_class=_attr(node, "StarClass"),
                key=_block_key(node), node=node, solar_suffix=suffix,
                spawn_amount=amount))
            continue
        m = _INDEXED_RE.match(kind)
        if m:
            family, idx = m.group(1), int(m.group(2))
            props = tuple(sorted(_body_props(node).items()))
            indexed.setdefault(family, []).append(
                IndexedBlock(family=family, index=idx, node=node,
                             props=props))
    return general, blocks, indexed


def _working_paths_from(root: Optional[Path], ecf_path: Path) -> Path:
    if root:
        return Path(root)
    return ecf_path.parent.parent          # <scenario>/Content/Configuration


def _scan_preset_playfields(path: Path) -> Set[str]:
    """Noms de playfields references par un SolarSystemConfig*.yaml
    (PlanetLists en chaines 'Nom:prob' + listes sous Playfields:).
    Scan texte : les lignes commentees sont ignorees."""
    names: Set[str] = set()
    in_pf = False
    in_pl = False
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = raw.strip()
        if stripped.startswith("#"):
            continue
        line = raw.split("#", 1)[0].rstrip()
        if re.match(r"^\s*Playfields:\s*$", line):
            in_pf, in_pl = True, False
            continue
        if re.match(r"^\s*PlanetLists:\s*$", line):
            in_pl, in_pf = True, False
            continue
        if in_pf:
            m = re.match(r"^\s*-\s*([A-Za-z0-9_]+)\s*$", line)
            if m:
                names.add(m.group(1))
                continue
            if line.strip():
                in_pf = False
        elif in_pl:
            m = re.match(r"^\s*-\s*'(.*)'\s*$", line)
            if m:
                for part in m.group(1).split(","):
                    nm = part.split(":")[0].strip().strip('"').strip()
                    if nm:
                        names.add(nm)
                continue
            if line.strip():
                in_pl = False
    return names


def _sectors_text(root: Path) -> str:
    p = Path(root) / "Sectors" / "Sectors.yaml"
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")


def _scan_egroup_refs(playfield_dir: Path) -> Set[str]:
    """Noms references sous `Entities:` dans les .yaml d'un dossier
    playfield importe (playfield_static/dynamic/space). Lignes commentees
    ignorees ; on quitte le contexte Entities: a la premiere ligne moins
    indentee."""
    refs: Set[str] = set()
    for yml in sorted(Path(playfield_dir).glob("*.yaml")):
        in_entities = False
        indent = ""
        for raw in yml.read_text(encoding="utf-8",
                                 errors="replace").splitlines():
            stripped = raw.strip()
            if stripped.startswith("#"):
                continue
            line = raw.split("#", 1)[0].rstrip()
            if not line.strip():
                continue
            m = re.match(r"^(\s*)Entities:\s*$", line)
            if m:
                in_entities, indent = True, m.group(1)
                continue
            if not in_entities:
                continue
            cur = re.match(r"^(\s*)", line).group(1)
            if len(cur) <= len(indent):
                in_entities = False
                continue
            m2 = re.match(r"^\s*-\s*Names:\s*\[([^\]]*)\]", line)
            if m2:
                for part in m2.group(1).split(","):
                    nm = part.strip().strip('"').strip()
                    if nm:
                        refs.add(nm)
                continue
            m3 = re.match(r"^\s*-\s*Name:\s*([A-Za-z0-9_]+)\s*$", line)
            if m3:
                refs.add(m3.group(1))
    return refs


def _egroup_blocks(path: Path) -> Dict[str, EcfBlock]:
    """{EGroupName: bloc { EGroup ... }} d'un EGroupsConfig.ecf."""
    if not Path(path).exists():
        return {}
    out: Dict[str, EcfBlock] = {}
    for node in parse_ecf_file(path).nodes:
        if (isinstance(node, EcfBlock)
                and normalized_kind(node.kind).rstrip(",").strip()
                == "EGroup"):
            nm = _attr(node, "Name")
            if nm:
                out.setdefault(nm, node)
    return out


def _config_dir(root) -> Path:
    """Dossier Configuration d'un scenario (variante Content imbrique ou
    non — vecu, voir core/selling_localization.localization_csv_path)."""
    root = Path(root)
    for cand in (root / "Content" / "Configuration", root / "Configuration"):
        if cand.is_dir():
            return cand
    return root / "Content" / "Configuration"


def _territory_factions(territories) -> Set[str]:
    """Factions requises par des Child Territory (Faction: + Other_N:)."""
    req: Set[str] = set()
    for ib in territories:
        for k, v in ib.props:
            if k == "Faction" or re.match(r"^Other_\d+$", k):
                nm = v.strip().strip('"').strip()
                if nm:
                    req.add(nm)
    return req


def _faction_blocks(path: Path) -> Dict[str, EcfBlock]:
    """{FactionName: bloc { Faction ... }} d'un Factions.ecf."""
    if not Path(path).exists():
        return {}
    out: Dict[str, EcfBlock] = {}
    for node in parse_ecf_file(path).nodes:
        if (isinstance(node, EcfBlock)
                and normalized_kind(node.kind).rstrip(",").strip()
                == "Faction"):
            nm = _attr(node, "Name").strip('"')
            if nm:
                out.setdefault(nm, node)
    return out


def _reputation_for(path: Path, factions: Set[str]) -> Dict[str, Dict[str, str]]:
    """Dans un DefReputation.ecf source : {faction: {bloc Reputation:
    valeur}} pour les factions demandees."""
    out: Dict[str, Dict[str, str]] = {}
    if not Path(path).exists():
        return out
    for node in parse_ecf_file(path).nodes:
        if not isinstance(node, EcfBlock):
            continue
        if normalized_kind(node.kind).rstrip(",").strip() != "Reputation":
            continue
        block_name = _attr(node, "Name")
        for f in factions:
            v = node.get_property(f)
            if v is not None:
                out.setdefault(f, {})[block_name] = str(v).strip()
    return out


def _preset_candidates(root: Path, suffix: str) -> List[Path]:
    """Fichiers possibles pour un suffixe : certains blocs mettent deja
    « SolarSystemConfig... » dans le suffixe (vecu 01/10 chez DREX),
    d'autres juste le type (_MainHabitableT1)."""
    rp = Path(root) / "RandomPresets"
    if suffix.startswith(_PRESET_PREFIX):
        return [rp / f"{suffix}.yaml"]
    return [rp / f"{_PRESET_PREFIX}{suffix}.yaml", rp / f"{suffix}.yaml"]


def build_plan(working_path, source_path, working_root=None,
               source_root=None, vanilla_content=None) -> GalaxyPlan:
    """Compare working (prioritaire) et source, collecte blocs a ajouter
    et dependances. Ne modifie RIEN."""
    plan = GalaxyPlan()
    working_path, source_path = Path(working_path), Path(source_path)
    working_root = _working_paths_from(working_root, working_path)
    source_root = _working_paths_from(source_root, source_path)
    if vanilla_content is None:
        from core.settings import get_vanilla_content_path
        vanilla_content = get_vanilla_content_path()

    try:
        w_doc = parse_ecf_file(working_path)
    except Exception as e:                                  # noqa: BLE001
        plan.errors.append(f"working illisible : {e}")
        return plan
    try:
        s_doc = parse_ecf_file(source_path)
    except Exception as e:                                  # noqa: BLE001
        plan.errors.append(f"source illisible : {e}")
        return plan

    w_general, w_blocks, w_indexed = _galaxy_blocks(w_doc)
    s_general, s_blocks, s_indexed = _galaxy_blocks(s_doc)
    plan.source_general = s_general
    w_keys = {b.key for b in w_blocks}

    # 1) blocs de B absents du working ; identiques -> info
    seen: Set[str] = set()
    for b in s_blocks:
        if b.key in seen:
            continue
        seen.add(b.key)
        if b.key in w_keys:
            plan.blocks_same.append(b.key)
        else:
            plan.blocks_add.append(b)

    # 1b) blocs indexes du format vanille (Child StarRegion_N/Territory_N) :
    # tout B est propose, dedoublonne par CONTENU (props identiques) ; la
    # renumerotation contigue de l'ensemble se fait a l'application
    for family in _INDEXED_FAMILIES:
        s_list = s_indexed.get(family, [])
        if not s_list:
            continue
        w_sets = {ib.props for ib in w_indexed.get(family, [])}
        add = [ib for ib in s_list if ib.props not in w_sets]
        same = len(s_list) - len(add)
        if same:
            plan.indexed_same.append(f"{family}: {same}")
        if add:
            plan.indexed_add[family] = add
            total = len(w_indexed.get(family, [])) + len(add)
            limit = {"StarRegion": 199, "Territory": 20}[family]
            if total > limit:
                plan.indexed_limits.append(
                    f"{family}: {total} > {limit}")

    # 2) diff informatif du bloc General (working prioritaire, rien a faire)
    if w_general is not None and s_general is not None:
        w_pairs = _body_props(w_general)
        s_pairs = _body_props(s_general)
        for k, v in s_pairs.items():
            if k in w_pairs and w_pairs[k] != v:
                plan.general_diff.append((k, w_pairs[k], v))

    # 2b) factions requises par les Child Territory importes : extraire
    # les blocs Faction de la source, propager DefReputation, avertir si
    # FactionWarfare les pilote (Factions.ecf du working JAMAIS ecrase)
    territories = plan.indexed_add.get("Territory", [])
    req = _territory_factions(territories)
    if req:
        w_cfg = _config_dir(working_root)
        s_cfg = _config_dir(source_root)
        present = set(_faction_blocks(w_cfg / _FACTION_FILE))
        plan.has_factions_ecf = bool(present)
        source_fac = _faction_blocks(s_cfg / _FACTION_FILE)
        rep = _reputation_for(s_cfg / _REPUTATION_FILE, req)
        try:
            warfare = (s_cfg / _WARFARE_FILE).read_text(
                encoding="utf-8", errors="replace") \
                if (s_cfg / _WARFARE_FILE).exists() else ""
        except Exception:                                       # noqa: BLE001
            warfare = ""
        for name in sorted(req):
            if name in present:
                continue
            if name not in source_fac:
                plan.factions_unknown.append(name)
                continue
            plan.factions_to_import.append(FactionImport(
                name=name, node=source_fac[name],
                has_reputation=name in rep,
                has_warfare=bool(warfare
                                 and name.lower() in warfare.lower()),
                reputation=rep.get(name, {})))
            if plan.factions_to_import[-1].has_warfare:
                plan.warfare_warnings.append(name)

    # 3) dependances des blocs importes : presets SolarSystemConfig
    for b in plan.blocks_add:
        if not b.solar_suffix:
            continue
        src = None
        for cand in _preset_candidates(source_root, b.solar_suffix):
            if cand.exists():
                src = cand
                break
        if src is None:
            plan.errors.append(
                f"preset manquant chez la source : "
                f"{_preset_candidates(source_root, b.solar_suffix)[0].name}"
                f" (bloc {b.name})")
            continue
        dst = working_root / "RandomPresets" / src.name
        if dst.exists():
            continue                       # deja la : rien a copier
        plan.deps.append(GalaxyDependency(
            relative=f"RandomPresets/{src.name}", source_path=src,
            reason=f"suffixe du bloc {b.name}"))
        # playfields references par CE preset
        try:
            refs = _scan_preset_playfields(src)
        except Exception as e:                              # noqa: BLE001
            plan.errors.append(f"preset illisible {src.name} : {e}")
            continue
        from core.fsutil import dirs_differ
        for nm in sorted(refs):
            if (working_root / "Playfields" / nm).is_dir():
                continue
            src_pf = source_root / "Playfields" / nm
            van_pf = (Path(vanilla_content) / "Playfields" / nm)                 if vanilla_content else None
            if src_pf.is_dir():
                # copier si le scenario source a MODIFIE le playfield
                # (contenu different de la vanille = a preserver) ou si
                # la vanille ne le fournit pas
                if van_pf is not None and van_pf.is_dir()                         and not dirs_differ(src_pf, van_pf):
                    continue        # identique vanille : fallback equivalente
                plan.deps.append(GalaxyDependency(
                    relative=f"Playfields/{nm}", source_path=src_pf,
                    reason=f"playfield du preset {src.name}"))
            elif len(plan.playfields_absent) < 25:
                # nom resolu par le jeu (asteroid fields, integrés...) :
                # informatif seulement, tronque pour ne pas noyer l'apercu
                plan.playfields_absent.append(f"{nm} ({src.name})")

    # 3b) groupes d'ennemis requis par les playfields importes : les refs
    # Entities: resolues comme EGroup ; presentes chez la source et
    # absentes du working = blocs a importer (les autres sont resolves
    # par le jeu : entites natives, asteroid fields...)
    pf_deps = [d for d in plan.deps if d.source_path.is_dir()
               and d.relative.startswith("Playfields/")]
    if pf_deps:
        egroup_source: Optional[Dict[str, EcfBlock]] = None
        egroup_working: Set[str] = set()
        imported: Set[str] = set()
        for dep in pf_deps:
            refs = _scan_egroup_refs(dep.source_path)
            if not refs:
                continue
            if egroup_source is None:
                egroup_source = _egroup_blocks(
                    _config_dir(source_root) / "EGroupsConfig.ecf")
                egroup_working = set(_egroup_blocks(
                    _config_dir(working_root) / "EGroupsConfig.ecf"))
            for nm in sorted(refs):
                if nm in egroup_working or nm in imported:
                    continue
                if nm in egroup_source:
                    imported.add(nm)
                    plan.egroups_to_import.append(NamedBlockImport(
                        name=nm, node=egroup_source[nm]))

    # 4) avertissements Sectors : systemes places a la main (amount 0)
    #    dont le nom n'apparait nulle part dans le Sectors.yaml du working
    sectors = _sectors_text(working_root)
    if sectors:
        for b in plan.blocks_add:
            if b.spawn_amount == 0 and b.name and b.name not in sectors:
                plan.sector_warnings.append(b.name)
    else:
        for b in plan.blocks_add:
            if b.spawn_amount == 0:
                plan.sector_warnings.append(b.name)
    return plan


def apply_plan(plan: GalaxyPlan, working_path, working_root=None,
               block_keys: Optional[Set[str]] = None,
               copy_deps: bool = True,
               indexed_keys: Optional[Set[str]] = None,
               general_props: Optional[Set[str]] = None) -> Dict[str, int]:
    """Applique le plan sur la copie de travail : blocs classes (par cle),
    blocs indexes (Child StarRegion/Territory — RENUMEROTES en sequence
    contigue sur l'ensemble du fichier), General (overrides coches),
    dependances (presets/playfields) et factions (Factions.ecf complete,
    DefReputation propage — jamais d'ecrasement). .bak avant ecriture.
    Idempotent : re-fusion = rien."""
    working_path = Path(working_path)
    working_root = _working_paths_from(working_root, working_path)
    stats = {"blocks": 0, "deps": 0, "skipped_deps": 0, "indexed": 0,
             "factions": 0, "reputation": 0, "general": 0, "egroups": 0}
    if not plan.ok:
        raise ValueError("plan en erreur : " + "; ".join(plan.errors))
    if not (plan.blocks_add or plan.indexed_add
            or (copy_deps and plan.deps) or plan.factions_to_import
            or plan.egroups_to_import or general_props):
        return stats

    doc = parse_ecf_file(working_path)

    # --- 1) classes de systemes (filtre cochable)
    wanted = [b for b in plan.blocks_add
              if block_keys is None or b.key in block_keys]
    if wanted:
        separator = EcfComment(
            raw=f"# ===== Fusion depuis source : systemes ajoutes "
                f"ci-dessous =====\r\n")
        has_marker = any(isinstance(n, EcfComment) and SEPARATOR_MARKER
                         in n.raw for n in doc.nodes)
        for b in wanted:
            if not has_marker:
                doc.nodes.append(separator)
                has_marker = True
            doc.nodes.append(copy.deepcopy(b.node))
        stats["blocks"] = len(wanted)

    # --- 2) blocs indexes + RENUMEROTATION CONTIGUE de tout le fichier
    wanted_indexed: List[IndexedBlock] = []
    for family, lst in plan.indexed_add.items():
        wanted_indexed.extend(
            ib for ib in lst
            if indexed_keys is None
            or f"{ib.family}|{ib.index}" in indexed_keys)
    if wanted_indexed:
        for ib in wanted_indexed:
            doc.nodes.append(copy.deepcopy(ib.node))
        counters = {family: 0 for family in _INDEXED_FAMILIES}
        for node in doc.nodes:
            if not isinstance(node, EcfBlock):
                continue
            m = _INDEXED_RE.match(
                normalized_kind(node.kind).rstrip(",").strip())
            if not m:
                continue
            family = m.group(1)
            counters[family] += 1
            node.kind = f"Child {family}_{counters[family]}"
            # render_open ressort raw_open tant que dirty est faux
            node.dirty = True
        stats["indexed"] = len(wanted_indexed)

    if wanted or wanted_indexed:
        bak = working_path.with_suffix(working_path.suffix + ".bak")
        if working_path.exists():
            shutil.copy2(working_path, bak)
        atomic_write_text(working_path, doc.render())

    # --- 3) General : overrides coches (valeur SOURCE sur la ligne du
    # working ; la propriete existe deja puisque le diff l'a relevee)
    if general_props and plan.source_general is not None:
        s_pairs = _body_props(plan.source_general)
        w_doc2 = parse_ecf_file(working_path)
        w_general, _wb, _ix = _galaxy_blocks(w_doc2)
        n = 0
        if w_general is not None:
            for prop in sorted(general_props):
                if prop in s_pairs and w_general.set_property(
                        prop, s_pairs[prop]):
                    n += 1
            if n:
                bak = working_path.with_suffix(working_path.suffix + ".bak")
                if working_path.exists():
                    shutil.copy2(working_path, bak)
                atomic_write_text(working_path, w_doc2.render())
        stats["general"] = n

    # --- 4) dependances (presets/playfields), avec .bak si ecrasement
    if copy_deps:
        from core.fsutil import copy_dir_repairing_yaml,             repair_stray_junk_after_flow
        for dep in plan.deps:
            dst = working_root / dep.relative
            if dst.exists():
                stats["skipped_deps"] += 1
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dep.source_path.is_dir():
                # playfield : dossiers entiers, *.yaml reparés (junk
                # apres crochet de liste flow — vecu 01/10)
                _c, fixed = copy_dir_repairing_yaml(dep.source_path, dst)
                stats["deps"] += 1
                continue
            # preset SolarSystemConfig : fichier texte reparé a l'ecriture
            text = dep.source_path.read_text(encoding="utf-8",
                                             errors="replace")
            fixed_text, _n = repair_stray_junk_after_flow(text)
            atomic_write_text(dst, fixed_text)
            stats["deps"] += 1

    # --- 5) factions requises : completer Factions.ecf du working
    fac_imports = [f for f in plan.factions_to_import if f.node is not None]
    if fac_imports:
        cfg = _config_dir(working_root)
        fac_path = cfg / _FACTION_FILE
        fdoc = parse_ecf_file(fac_path) if fac_path.exists() else None
        present = set(_faction_blocks(fac_path)) if fac_path.exists() \
            else set()
        to_add = [f for f in fac_imports if f.name not in present]
        if to_add and fdoc is not None:
            for f in to_add:
                fdoc.nodes.append(EcfComment(
                    raw=f"# Faction {f.name} ajoutee par fusion "
                        f"GalaxyConfig\r\n"))
                fdoc.nodes.append(copy.deepcopy(f.node))
                stats["factions"] += 1
            bak = fac_path.with_suffix(fac_path.suffix + ".bak")
            if fac_path.exists():
                shutil.copy2(fac_path, bak)
            atomic_write_text(fac_path, fdoc.render())
        elif to_add and fdoc is None:
            # pas de Factions.ecf au working : le creer a la maniere du jeu
            for f in to_add:
                fdoc = fdoc or _empty_doc()
                fdoc.nodes.append(copy.deepcopy(f.node))
                stats["factions"] += 1
            cfg.mkdir(parents=True, exist_ok=True)
            atomic_write_text(fac_path, fdoc.render())

        # DefReputation : propager les valeurs de B dans les MEMES blocs
        # d'Origine du working (jamais ecraser une valeur existante)
        rep_path = cfg / _REPUTATION_FILE
        if rep_path.exists():
            rdoc = parse_ecf_file(rep_path)
            n = 0
            for node in rdoc.nodes:
                if not isinstance(node, EcfBlock):
                    continue
                if normalized_kind(node.kind).rstrip(",").strip() \
                        != "Reputation":
                    continue
                block_name = _attr(node, "Name")
                for f in fac_imports:
                    val = f.reputation.get(block_name)
                    if val and node.get_property(f.name) is None:
                        add_property_line(node, [(f.name, val)])
                        n += 1
            if n:
                bak = rep_path.with_suffix(rep_path.suffix + ".bak")
                if rep_path.exists():
                    shutil.copy2(rep_path, bak)
                atomic_write_text(rep_path, rdoc.render())
            stats["reputation"] = n

    # --- 6) groupes d'ennemis des playfields importes : completer
    # EGroupsConfig.ecf du working (append, .bak, jamais ecraser)
    if plan.egroups_to_import:
        cfg = _config_dir(working_root)
        eg_path = cfg / "EGroupsConfig.ecf"
        present = set(_egroup_blocks(eg_path))
        to_add = [e for e in plan.egroups_to_import
                  if e.name not in present]
        if to_add:
            eg_doc = parse_ecf_file(eg_path) if eg_path.exists() \
                else _empty_doc()
            for e in to_add:
                eg_doc.nodes.append(EcfComment(
                    raw=f"# EGroup {e.name} ajoute par fusion "
                        f"GalaxyConfig\r\n"))
                eg_doc.nodes.append(copy.deepcopy(e.node))
                stats["egroups"] += 1
            bak = eg_path.with_suffix(eg_path.suffix + ".bak")
            if eg_path.exists():
                shutil.copy2(eg_path, bak)
            else:
                cfg.mkdir(parents=True, exist_ok=True)
            atomic_write_text(eg_path, eg_doc.render())
    return stats


def _empty_doc():
    from core.ecf.model import EcfDocument
    return EcfDocument(nodes=[], source_path=None)
