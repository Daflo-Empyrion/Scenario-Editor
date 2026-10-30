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
"""Fiche du scenario : inventaire JOUEUR par origine (prefixe de nom),
monde (playfields, planetes, lunes, POI) et difficulte vs la vanille
(ratios nom-a-nom sur les blocs/items communs), rendue en Markdown FR + EN
pour une note de version Workshop/Discord.

Regles :
- origine = prefixe du nom (Eden_/ATL_/AG_/BIZON_/sans prefixe) ; la
  vanille = nom present dans la config du jeu (choix utilisateur 27/10) ;
- inventaire limite aux noeuds VISIBLES de l'arbre technologique (meme
  definition que le jeu : categorie non Hidden et non vide) ;
- difficultes = valeurs EFFECTIVES (heritage Ref resolu), mediane des
  ratios scenario/vanille sur les noms communs.
"""
from __future__ import annotations

import datetime
import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.ecf.parser import parse_ecf_file
from core.sectors_merge import _split_flow
from core.tech_tree import load_tech_tree

_ORIGINS: Tuple[Tuple[str, str], ...] = (
    ("Eden_", "eden"),
    ("ATL_", "atl"),
    ("AG_", "ag"),
    ("BIZON_", "bizon"),
)
_ORIGIN_LABELS = {
    "vanilla": ("Vanille", "Vanilla"),
    "eden": ("Eden (RE2)", "Eden (RE2)"),
    "atl": ("ATL (Atlantis)", "ATL (Atlantis)"),
    "ag": ("AG (Atlantis)", "AG (Atlantis)"),
    "bizon": ("BIZON", "BIZON"),
    "base": ("RE2 (sans préfixe)", "RE2 (unprefixed)"),
}
_ORIGIN_ORDER = ("vanilla", "eden", "atl", "ag", "bizon", "base")
_KIND_LABELS = {
    "planet": ("Planètes", "Planets"),
    "moon": ("Lunes", "Moons"),
    "space": ("Espaces", "Space"),
    "other": ("Autres", "Other"),
}
_METRIC_LABELS = {
    "hp": ("Points de vie", "Hit points"),
    "cpu": ("CPU", "CPU"),
    "shield": ("Boucliers", "Shields"),
    "damage": ("Dégâts de zone", "Blast damage"),
    "price": ("Prix marché", "Market price"),
    "mining": ("Vitesse de minage", "Mining speed"),
}
_OPTION_KEYS = ("EnableCPUPoints", "EnableMaxBlockCount", "MaxStructures",
                "EnableTrading", "MaxSpawnedEnemies", "EnableVolumeWeight",
                "AutoMinerDepletion")
_POI_ENTRY_RE = re.compile(r"^\s+- (?:GroupName|Name|Prefab):")
_COUNT_MINMAX_RE = re.compile(r"CountMinMax:\s*\[\s*(\d+)\s*,\s*(\d+)")
_TOP_KEY_RE = re.compile(r"^[A-Za-z_][\w ]*:")
_SECTOR_ENTRY_RE = re.compile(r"^\s+- \[")


@dataclass
class Ratio:
    key: str
    count: int
    median: float
    min: float
    max: float


@dataclass
class Digest:
    name: str
    date: str
    blocks: Dict[str, int] = field(default_factory=dict)
    items: Dict[str, int] = field(default_factory=dict)
    all_blocks: Dict[str, int] = field(default_factory=dict)
    all_items: Dict[str, int] = field(default_factory=dict)
    playfields: Dict[str, int] = field(default_factory=dict)
    instances: Dict[str, int] = field(default_factory=dict)
    instances_total: int = 0
    poi_defs: Dict[str, int] = field(default_factory=dict)
    poi_max: int = 0
    planet_difficulty: Optional[float] = None
    tree_visible: int = 0
    tree_max_level: int = 0
    tree_tiers: List[int] = field(default_factory=list)
    vanilla_tree_visible: int = 0
    vanilla_tree_max_level: int = 0
    vanilla_tree_tiers: List[int] = field(default_factory=list)
    ratios: List[Ratio] = field(default_factory=list)
    options: Dict[str, str] = field(default_factory=dict)

    @property
    def blocks_total(self) -> int:
        return sum(self.blocks.values())

    @property
    def items_total(self) -> int:
        return sum(self.items.values())


def origin_of(name: str, vanilla_names: set[str]) -> str:
    """Origine d'un nom : vanille si declare dans la config du jeu, sinon
    prefixe (Eden_/ATL_/AG_/BIZON_), sinon RE2 de base."""
    if name in vanilla_names:
        return "vanilla"
    for prefix, origin in _ORIGINS:
        if name.startswith(prefix):
            return origin
    return "base"


# ---------------------------------------------------------------------------
# collecte
# ---------------------------------------------------------------------------

def _config_paths(root: Path, vanilla_content: str) -> Tuple[Path, Path,
                                                             Optional[Path], Optional[Path]]:
    conf = root / "Content" / "Configuration"
    scn_blocks = conf / "BlocksConfig.ecf"
    scn_items = conf / "ItemsConfig.ecf"
    van_blocks = van_items = None
    if vanilla_content:
        vconf = Path(vanilla_content) / "Configuration"
        van_blocks = vconf / "BlocksConfig.ecf"
        van_items = vconf / "ItemsConfig.ecf"
    return scn_blocks, scn_items, van_blocks, van_items


def _block_map(path: Optional[Path]) -> Dict[str, object]:
    out: Dict[str, object] = {}
    if path is None or not path.exists():
        return out
    for b in parse_ecf_file(path).iter_blocks():
        if b.kind not in ("Block", "+Block", "Item", "+Item"):
            continue
        nm = b.get('Name') or b.get_property('Name')
        if nm:
            out[nm.strip().strip('"')] = b
    return out


def _effective(blocks: Dict[str, object], name: str, key: str,
               depth: int = 0) -> Optional[str]:
    b = blocks.get(name)
    if b is None or depth > 10:
        return None
    v = b.get_property(key)
    if v is not None:
        return v
    ref = b.get_property('Ref')
    if ref:
        return _effective(blocks, ref.strip().strip('"'), key, depth + 1)
    return None


def _num(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    v = value.strip().strip('"').split(',')[0].strip()
    try:
        return float(v)
    except ValueError:
        return None


def _drill_damage(blocks: Dict[str, object], name: str,
                  depth: int = 0) -> Optional[float]:
    """Damage de l'enfant `Class: Driller` (outil de minage), Ref suivie."""
    b = blocks.get(name)
    if b is None or depth > 10:
        return None
    for child in b.child_blocks():
        cls = child.get_property('Class')
        if cls and cls.strip().strip('"') == "Driller":
            return _num(child.get_property('Damage'))
    ref = b.get_property('Ref')
    if ref:
        return _drill_damage(blocks, ref.strip().strip('"'), depth + 1)
    return None


def _playfield_kind(text: str) -> str:
    m = re.search(r"(?m)^\s*PlayfieldType:\s*([^\r\n#]+)", text)
    value = m.group(1).strip().strip('"').casefold() if m else ""
    if "moon" in value:
        return "moon"
    if "planet" in value:
        return "planet"
    if "space" in value or "orbit" in value:
        return "space"
    m = re.search(r"(?m)^\s*PlanetType:\s*([^\r\n#]+)", text)
    value = m.group(1).strip().strip('"').casefold() if m else ""
    if "moon" in value:
        return "moon"
    if "space" in value or "empty" in value:
        return "space"
    if value:
        return "planet"
    return "other"


def _playfield_text(folder: Path) -> str:
    for name in ("playfield_static.yaml", "_playfield_static.yaml",
                 "playfield.yaml", "space_dynamic.yaml"):
        p = folder / name
        if p.is_file():
            try:
                return p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
    return ""


def _pois(text: str) -> Tuple[int, int]:
    """(nombre d'entrees POI, somme des CountMinMax max) du fichier."""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == "POIs:":
            start = i + 1
            break
    if start is None:
        return 0, 0
    end = len(lines)
    for i in range(start, len(lines)):
        if _TOP_KEY_RE.match(lines[i]):
            end = i
            break
    count = maximum = 0
    for i in range(start, end):
        if not _POI_ENTRY_RE.match(lines[i]):
            continue
        count += 1
        block_end = end
        for j in range(i + 1, end):
            if _POI_ENTRY_RE.match(lines[j]):
                block_end = j
                break
        m = _COUNT_MINMAX_RE.search("\n".join(lines[i:block_end]))
        maximum += int(m.group(2)) if m else 1
    return count, maximum


def _sectors_yaml(root: Path) -> Optional[Path]:
    p = root / "Sectors" / "Sectors.yaml"
    return p if p.is_file() else (root / "Sectors.yaml"
                                  if (root / "Sectors.yaml").is_file() else None)


def _scan_world(root: Path) -> Tuple[Dict[str, int], Dict[str, int], int,
                                     Dict[str, int], int, Optional[float]]:
    kinds: Dict[str, int] = {k: 0 for k in _KIND_LABELS}
    poi_defs: Dict[str, int] = {k: 0 for k in _KIND_LABELS}
    poi_max = 0
    difficulties: List[float] = []
    playfields_root = root / "Playfields"
    for folder in sorted(playfields_root.iterdir()) if playfields_root.is_dir() else []:
        if not folder.is_dir():
            continue
        text = _playfield_text(folder)
        kind = _playfield_kind(text)
        kinds[kind] += 1
        n, mx = _pois(text)
        poi_defs[kind] += n
        poi_max += mx
        if kind == "planet":
            m = re.search(r"(?m)^\s*Difficulty:\s*(\d+)", text)
            if m:
                difficulties.append(float(m.group(1)))
    instances: Dict[str, int] = {k: 0 for k in _KIND_LABELS}
    total = 0
    sectors = _sectors_yaml(root)
    if sectors is not None:
        for line in sectors.read_text(encoding="utf-8",
                                      errors="replace").splitlines():
            if not _SECTOR_ENTRY_RE.match(line):
                continue
            body = line.split('#', 1)[0]
            start, end = body.find('['), body.rfind(']')
            if start < 0 or end <= start:
                continue
            fields = _split_flow(body[start:end + 1])
            if len(fields) < 3:
                continue
            total += 1
            pf = fields[2]
            folder = playfields_root / pf
            if folder.is_dir():
                instances[_playfield_kind(_playfield_text(folder))] += 1
            else:
                instances["other"] += 1
    return kinds, instances, total, poi_defs, poi_max, (
        round(statistics.mean(difficulties), 1) if difficulties else None)


def _visible_names(root: Path, vanilla_content: str) -> Tuple[set[str],
                                                              set[str]]:
    blocks_path = root / "Content" / "Configuration" / "BlocksConfig.ecf"
    items_path = root / "Content" / "Configuration" / "ItemsConfig.ecf"
    tree = load_tech_tree(blocks_path, items_path,
                          vanilla_root=str(Path(vanilla_content) /
                                           "Configuration")
                          if vanilla_content else "")
    visible = [n for n in tree.nodes
               if any(c not in ("Hidden", "") for c in n.categories)]
    return ({n.name for n in visible if n.source == "block"},
            {n.name for n in visible if n.source == "item"})


def _ratios(scn_blocks: Dict[str, object], van_blocks: Dict[str, object],
            scn_items: Dict[str, object], van_items: Dict[str, object],
            vis_blocks: set[str], vis_items: set[str]) -> List[Ratio]:
    out: List[Ratio] = []

    def add(key: str, names: set[str], scn: Dict[str, object],
            van: Dict[str, object], getter) -> None:
        ratios: List[float] = []
        for name in names:
            a = getter(scn, name)
            b = getter(van, name)
            if a and b and a > 0 and b > 0:
                ratios.append(a / b)
        if ratios:
            out.append(Ratio(key, len(ratios),
                             round(statistics.median(ratios), 2),
                             round(min(ratios), 2),
                             round(max(ratios), 2)))

    def field_getter(key: str):
        return lambda blocks, name: _num(_effective(blocks, name, key))

    for key, metric in (("HitPoints", "hp"), ("CPUIn", "cpu"),
                        ("ShieldCapacity", "shield"),
                        ("BlastDamage", "damage"),
                        ("MarketPrice", "price")):
        add(metric, vis_blocks, scn_blocks, van_blocks, field_getter(key))
    add("mining", vis_items, scn_items, van_items, _drill_damage)
    return out


def _options(root: Path) -> Dict[str, str]:
    path = root / "gameoptions.yaml"
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    out: Dict[str, str] = {}
    for key in _OPTION_KEYS:
        m = re.search(rf"(?m)^\s*(?:-\s*)?{key}:\s*([^\s#]+)", text)
        if m:
            out[key] = m.group(1).strip()
    return out


def _tree_stats(blocks_path: Path, items_path: Path,
                vanilla_root: str) -> Tuple[int, int, List[int]]:
    tree = load_tech_tree(blocks_path, items_path, vanilla_root=vanilla_root)
    visible = [n for n in tree.nodes
               if any(c not in ("Hidden", "") for c in n.categories)]
    tiers = sorted({n.unlock_level for n in visible if n.unlock_level})
    return (len(visible), max(tiers) if tiers else 0, tiers)


def collect_digest(root: Path, vanilla_content: str = "") -> Digest:
    """Tout le contenu de la fiche, sans rendu (testable)."""
    root = Path(root)
    scn_blocks_path, scn_items_path, van_blocks_path, van_items_path = (
        _config_paths(root, vanilla_content))
    van_blocks = _block_map(van_blocks_path)
    van_items = _block_map(van_items_path)
    van_names = set(van_blocks) | set(van_items)
    scn_blocks = _block_map(scn_blocks_path)
    scn_items = _block_map(scn_items_path)
    vis_blocks, vis_items = _visible_names(root, vanilla_content)

    d = Digest(name=root.name, date=datetime.date.today().isoformat())
    d.blocks = {k: 0 for k in _ORIGIN_ORDER}
    d.items = {k: 0 for k in _ORIGIN_ORDER}
    d.all_blocks = {k: 0 for k in _ORIGIN_ORDER}
    d.all_items = {k: 0 for k in _ORIGIN_ORDER}
    for name in scn_blocks:
        origin = origin_of(name, van_names)
        d.all_blocks[origin] += 1
        if name in vis_blocks:
            d.blocks[origin] += 1
    for name in scn_items:
        origin = origin_of(name, van_names)
        d.all_items[origin] += 1
        if name in vis_items:
            d.items[origin] += 1

    (d.playfields, d.instances, d.instances_total, d.poi_defs, d.poi_max,
     d.planet_difficulty) = _scan_world(root)
    d.ratios = _ratios(scn_blocks, van_blocks, scn_items, van_items,
                       vis_blocks, vis_items)
    d.options = _options(root)

    d.tree_visible, d.tree_max_level, d.tree_tiers = _tree_stats(
        scn_blocks_path, scn_items_path,
        str(Path(vanilla_content) / "Configuration") if vanilla_content else "")
    if vanilla_content and van_blocks_path and van_items_path:
        d.vanilla_tree_visible, d.vanilla_tree_max_level, d.vanilla_tree_tiers = (
            _tree_stats(van_blocks_path, van_items_path, ""))
    return d


# ---------------------------------------------------------------------------
# rendu Markdown
# ---------------------------------------------------------------------------

def _table(headers: List[str], rows: List[List[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        out.append("| " + " | ".join(row) + " |")
    return "\n".join(out)


def _section(d: Digest, lang: int) -> str:
    fr = lang == 0
    label = (lambda pair: pair[0]) if fr else (lambda pair: pair[1])
    lines: List[str] = []
    lines.append("### " + ("Contenu joueur (visible dans l'arbre)"
                           if fr else "Player content (visible in the tree)"))
    rows = [[label(_ORIGIN_LABELS[o]), str(d.blocks.get(o, 0)),
             str(d.items.get(o, 0))] for o in _ORIGIN_ORDER
            if d.blocks.get(o, 0) or d.items.get(o, 0)]
    lines.append(_table([("Origine" if fr else "Origin"),
                         ("Blocs" if fr else "Blocks"),
                         ("Items" if fr else "Items")], rows))
    lines.append("")
    lines.append(("**{0} blocs et {1} items visibles.**"
                  if fr else "**{0} blocks and {1} items visible.**").format(
        d.blocks_total, d.items_total))
    all_blocks = sum(d.all_blocks.values())
    all_items = sum(d.all_items.values())
    lines.append(("Config complète : {0} blocs et {1} items "
                  "(POI/interne inclus)." if fr else
                  "Full config: {0} blocks and {1} items (POI/internal "
                  "included).").format(all_blocks, all_items))
    invisible = [o for o in _ORIGIN_ORDER
                 if (d.all_blocks.get(o, 0) or d.all_items.get(o, 0))
                 and not (d.blocks.get(o, 0) or d.items.get(o, 0))]
    if invisible:
        word = "blocs" if fr else "blocks"
        lines.append(("Entièrement hors arbre : " if fr
                      else "Entirely outside the tree: ")
                     + ", ".join(f"{label(_ORIGIN_LABELS[o])} — "
                                 f"{d.all_blocks.get(o, 0)} {word} / "
                                 f"{d.all_items.get(o, 0)} items"
                                 for o in invisible))

    lines.append("")
    lines.append("### " + ("Monde" if fr else "World"))
    kinds = [k for k in _KIND_LABELS if d.playfields.get(k)]
    lines.append(("- **{0} définitions de playfields** : {1}."
                  if fr else "- **{0} playfield definitions**: {1}.").format(
        sum(d.playfields.values()),
        ", ".join(f"{label(_KIND_LABELS[k])} {d.playfields[k]}" for k in kinds)
        or "-"))
    lines.append(("- **{0} instances dans Sectors** : {1}."
                  if fr else "- **{0} instances in Sectors**: {1}.").format(
        d.instances_total,
        ", ".join(f"{label(_KIND_LABELS[k])} {d.instances[k]}"
                  for k in _KIND_LABELS if d.instances.get(k)) or "-"))
    pf_total = sum(d.poi_defs.values())
    avg = round(pf_total / max(1, sum(d.playfields.values())), 1)
    lines.append(("- **{0} POI définis** ({1}), soit ~{2} par playfield ; "
                  "jusqu'à {3} instances (somme des CountMinMax)."
                  if fr else "- **{0} POIs defined** ({1}), ~{2} per "
                  "playfield; up to {3} instances (sum of CountMinMax).").format(
        pf_total,
        ", ".join(f"{label(_KIND_LABELS[k])} {d.poi_defs[k]}"
                  for k in _KIND_LABELS if d.poi_defs.get(k)) or "-",
        avg, d.poi_max))
    if d.planet_difficulty is not None:
        lines.append(("- Difficulté moyenne des planètes : **{0}**."
                      if fr else "- Average planet difficulty: **{0}**.").format(
            d.planet_difficulty))

    lines.append("")
    lines.append("### " + ("Difficulté vs vanille" if fr
                           else "Difficulty vs vanilla"))
    if d.ratios:
        lines.append(("Médiane des ratios sur les noms communs (blocs/items "
                      "visibles) :" if fr else
                      "Median ratios on shared visible names (blocks/items):"))
        lines.append("")
        lines.append(_table(
            [("Métrique" if fr else "Metric"),
             ("Noms" if fr else "Names"),
             ("Médiane" if fr else "Median"),
             "min", "max"],
            [[label(_METRIC_LABELS[r.key]), str(r.count), f"x{r.median}",
              f"x{r.min}", f"x{r.max}"] for r in d.ratios]))
        lines.append("")
        pairs = ", ".join(f"{label(_METRIC_LABELS[r.key])} x{r.median}"
                          for r in d.ratios)
        lines.append(("**Synthèse** : " if fr else "**Summary**: ") + pairs + ".")
    else:
        lines.append(("Aucun nom commun mesurable (vanille non configurée)."
                      if fr else "No measurable shared names."))
    if d.tree_visible:
        if fr:
            lines.append("")
            lines.append(f"- Arbre : **{d.tree_visible} nœuds visibles**, "
                         f"paliers {d.tree_tiers[0]}..{d.tree_max_level} "
                         f"({len(d.tree_tiers)} paliers).")
            if d.vanilla_tree_visible:
                lines.append(f"- Vanille : {d.vanilla_tree_visible} nœuds "
                             f"visibles, paliers {d.vanilla_tree_tiers[0]}.."
                             f"{d.vanilla_tree_max_level}.")
        else:
            lines.append("")
            lines.append(f"- Tree: **{d.tree_visible} visible nodes**, tiers "
                         f"{d.tree_tiers[0]}..{d.tree_max_level} "
                         f"({len(d.tree_tiers)} tiers).")
            if d.vanilla_tree_visible:
                lines.append(f"- Vanilla: {d.vanilla_tree_visible} visible "
                             f"nodes, tiers {d.vanilla_tree_tiers[0]}.."
                             f"{d.vanilla_tree_max_level}.")
    if d.options:
        lines.append("")
        lines.append(("- Options du scénario : " if fr
                      else "- Scenario options: ")
                     + ", ".join(f"`{k}={v}`" for k, v in d.options.items()))
    return "\n".join(lines)


def render_markdown(d: Digest) -> str:
    """Fiche complete : entete + section FR + section EN + pied."""
    lines = [f"# {d.name} — fiche du scénario",
             "",
             f"*{d.date}*",
             "",
             "## FR", "", _section(d, 0), "",
             "## EN", "", _section(d, 1), "",
             "---",
             "",
             "*Généré par Empyrion Scenario Editor — comptages statiques "
             "sur la config et les playfields du scénario.*"]
    return "\n".join(lines) + "\n"
