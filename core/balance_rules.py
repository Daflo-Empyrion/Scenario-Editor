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

"""Moteur de regles d'EQUILIBRAGE de scenario (conception :
MODULE_EQUILIBRAGE.md, demande du 24/09/2026). Inventorie les blocs des
ECF (vanille + scenario, « derniere definition gagne »), propose des
changements par regles (une regle = une propriete) avec politiques
« conserve / vanille / plafond / pourcentage » — le pourcentage (x80 %,
x120 %...) multiplie la valeur ACTUELLE de chaque bloc et preserve ainsi
les ratios internes, contrairement au plafond — et applique les
propositions cochees EN RE-SERIALISANT les fichiers du scenario (jamais
ceux de la vanille)."""
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from core.ecf.model import EcfBlock, EcfDocument
from core.ecf.parser import parse_ecf_file
from core.fsutil import atomic_write_text

POLICIES = ("conserve", "vanille", "plafond", "pourcentage")


@dataclass(frozen=True)
class RuleSpec:
    """Une regle = une propriete de bloc, rangée dans un groupe."""
    key: str                 # = nom de la propriete
    prop: str
    group: str               # cle i18n du groupe
    plafond: float           # valeur par defaut de la politique plafond


RULE_CATALOG: List[RuleSpec] = [
    # Placement
    RuleSpec("MaxCount", "MaxCount", "balance.group_placement", 32),
    # CPU (le cout des appareils ; les paliers moteurs ne sont pas editables)
    RuleSpec("CPUIn", "CPUIn", "balance.group_cpu", 5_000),
    # Resistance
    RuleSpec("HitPoints", "HitPoints", "balance.group_resistance", 50_000),
    # Combat
    RuleSpec("Damage", "Damage", "balance.group_combat", 5000),
    RuleSpec("Range", "Range", "balance.group_combat", 6000),
    RuleSpec("RangeSpace", "RangeSpace", "balance.group_combat", 6000),
    RuleSpec("BlastShieldDamagePenFac", "BlastShieldDamagePenFac",
             "balance.group_combat", 1),
    RuleSpec("ShieldDamagePenFac", "ShieldDamagePenFac",
             "balance.group_combat", 1),
    RuleSpec("ShieldHitCooldown", "ShieldHitCooldown",
             "balance.group_combat", 30),
    # Bouclier
    RuleSpec("ShieldCapacity", "ShieldCapacity",
             "balance.group_shield", 100_000),
    RuleSpec("ShieldRecharge", "ShieldRecharge",
             "balance.group_shield", 1_000),
    RuleSpec("ShieldCooldown", "ShieldCooldown", "balance.group_shield", 30),
    RuleSpec("ShieldPerCrystal", "ShieldPerCrystal",
             "balance.group_shield", 100),
    RuleSpec("ShieldCapacityBonus", "ShieldCapacityBonus",
             "balance.group_shield", 1),
    # Deplacement
    RuleSpec("ThrusterForce", "ThrusterForce",
             "balance.group_motion", 1_000_000),
    RuleSpec("RangeAU", "RangeAU", "balance.group_motion", 50),
    RuleSpec("RangeLY", "RangeLY", "balance.group_motion", 50),
    RuleSpec("CostPerAU", "CostPerAU", "balance.group_motion", 100),
    RuleSpec("CostPerLY", "CostPerLY", "balance.group_motion", 100),
    RuleSpec("ReturnFactor", "ReturnFactor", "balance.group_motion", 1),
    # Energie
    RuleSpec("EnergyOut", "EnergyOut", "balance.group_energy", 25_000),
    RuleSpec("EnergyIn", "EnergyIn", "balance.group_energy", 5_000),
    RuleSpec("EnergyInIdle", "EnergyInIdle", "balance.group_energy", 100),
    RuleSpec("SolarPanelEfficiency", "SolarPanelEfficiency",
             "balance.group_energy", 100),
    # Economie / inventaire
    RuleSpec("MarketPrice", "MarketPrice", "balance.group_economy", 10_000),
    RuleSpec("StackSize", "StackSize", "balance.group_economy", 1_000),
    RuleSpec("Mass", "Mass", "balance.group_economy", 1_000),
    RuleSpec("Volume", "Volume", "balance.group_economy", 100),
]
RULES = [spec.key for spec in RULE_CATALOG]
RULE_SPEC = {spec.key: spec for spec in RULE_CATALOG}
RULE_PROP = {spec.key: (spec.prop,) for spec in RULE_CATALOG}
# blocs volontairement hors CPU (ex RE2 ATL : MissionContainer CPUIn 10M)
WHITELIST_CPU = {"MissionContainer"}


@dataclass
class BlockDef:
    """Definition d'un bloc dans UN fichier ECF."""
    name: str
    block_id: Optional[int]
    path: Path
    doc: EcfDocument
    node: EcfBlock

    def value(self, prop: str) -> Optional[str]:
        v = self.node.get_property(prop)
        return None if v is None else str(v).strip().strip('"')


@dataclass
class ScenarioFile:
    path: Path
    doc: EcfDocument
    defs: Dict[str, BlockDef] = field(default_factory=dict)


@dataclass
class Inventory:
    """Vanille par nom (derniere definition gagnee) + fichiers scenario."""
    vanilla: Dict[str, BlockDef]
    scenario_files: List[ScenarioFile]

    def final_def(self, name: str) -> Optional[BlockDef]:
        """Definition FINALE d'un bloc : la derniere definition scenario,
        sinon la vanille (meme regle de fusion que le jeu)."""
        for sf in reversed(self.scenario_files):
            if name in sf.defs:
                return sf.defs[name]
        return self.vanilla.get(name)


@dataclass
class Proposal:
    """Un changement propose (cochable dans l'apercu)."""
    path: Path
    doc: EcfDocument
    node: EcfBlock
    block: str
    block_id: Optional[int]
    rule: str
    prop: str
    old: str
    new: str


@dataclass
class BalanceConfig:
    """Politique par regle : conserve / vanille / plafond / pourcentage.
    `plafonds` = valeur max (politique plafond) ; `pourcentages` = %
    applique a la valeur actuelle (politique pourcentage, 100 = inchangé)."""
    policies: Dict[str, str] = field(
        default_factory=lambda: {r: "conserve" for r in RULES})
    plafonds: Dict[str, Optional[float]] = field(
        default_factory=lambda: {r: None for r in RULES})
    pourcentages: Dict[str, float] = field(
        default_factory=lambda: {r: 100.0 for r in RULES})

    @classmethod
    def preset_vanille(cls) -> "BalanceConfig":
        return cls(policies={r: "vanille" for r in RULES})


def _expand(paths) -> List[Path]:
    out: List[Path] = []
    for p in paths or []:
        pp = Path(p)
        if pp.is_dir():
            out.extend(sorted(pp.glob("BlocksConfig*.ecf")))
        elif pp.is_file():
            out.append(pp)
    return out


def _read_defs(path: Path, doc: EcfDocument) -> Dict[str, BlockDef]:
    defs: Dict[str, BlockDef] = {}
    for node in doc.nodes:
        if not isinstance(node, EcfBlock) or getattr(node, "kind", "") != "Block":
            continue
        name = (node.get("Name") or "").strip().strip('"')
        if not name:
            continue
        raw_id = node.get("Id")
        try:
            bid = int(str(raw_id).strip()) if raw_id is not None else None
        except ValueError:
            bid = None
        defs[name] = BlockDef(name=name, block_id=bid, path=path,
                              doc=doc, node=node)
    return defs


def load_inventory(vanilla_paths, scenario_paths) -> Inventory:
    vanilla: Dict[str, BlockDef] = {}
    for path in _expand(vanilla_paths):
        doc = parse_ecf_file(path)
        vanilla.update(_read_defs(path, doc))     # derniere definition gagne
    scenario_files = []
    for path in _expand(scenario_paths):
        doc = parse_ecf_file(path)
        scenario_files.append(
            ScenarioFile(path=path, doc=doc, defs=_read_defs(path, doc)))
    return Inventory(vanilla=vanilla, scenario_files=scenario_files)


def _num(s: Optional[str]) -> Optional[float]:
    try:
        return float(str(s).strip())
    except (TypeError, ValueError):
        return None


def _fmt_num(x: float) -> str:
    """Format d'ecriture : entier si rond, sinon 2 decimales epurees."""
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:.2f}".rstrip("0").rstrip(".")


def _same(a: str, b: str) -> bool:
    fa, fb = _num(a), _num(b)
    if fa is not None and fb is not None:
        return abs(fa - fb) < 1e-9
    return a == b


def propose_changes(inv: Inventory, config: BalanceConfig) -> List[Proposal]:
    """Construit les propositions : uniquement sur les definitions
    scenario FINALES (jamais la vanille), uniquement si la ligne de
    propriete existe deja dans le bloc scenario (pas d'ajout de ligne)."""
    out: List[Proposal] = []
    final_owner: Dict[str, ScenarioFile] = {}
    for sf in inv.scenario_files:
        for name in sf.defs:
            final_owner[name] = sf
    for sf in inv.scenario_files:
        for name, bd in sf.defs.items():
            if final_owner.get(name) is not sf:
                continue                      # definition ecrasee plus loin
            van = inv.vanilla.get(name)
            for spec in RULE_CATALOG:
                rule = spec.key
                policy = config.policies.get(rule, "conserve")
                if policy == "conserve":
                    continue
                old = bd.value(spec.prop)
                if old is None:
                    continue                  # pas de ligne -> pas d'ecriture
                if rule == "CPUIn" and name in WHITELIST_CPU:
                    continue
                new: Optional[str] = None
                if policy == "vanille":
                    van_val = van.value(spec.prop) if van else None
                    if van_val is not None and not _same(old, van_val):
                        new = van_val
                elif policy == "plafond":
                    plafond = config.plafonds.get(rule)
                    v = _num(old)
                    if plafond is not None and v is not None and v > plafond:
                        new = _fmt_num(plafond)
                elif policy == "pourcentage":
                    pct = config.pourcentages.get(rule, 100.0)
                    v = _num(old)
                    if v is not None and pct != 100.0:
                        candidate = _fmt_num(v * pct / 100.0)
                        if not _same(old, candidate):
                            new = candidate      # evite les no-op (0 -> 0)
                if new is None:
                    continue
                out.append(Proposal(path=sf.path, doc=sf.doc,
                                    node=bd.node, block=name,
                                    block_id=bd.block_id, rule=rule,
                                    prop=spec.prop, old=old, new=new))
            # MaxCount en vanille : ForceMaxCount suit la vanille
            if config.policies.get("MaxCount") == "vanille" and van:
                old_f = bd.value("ForceMaxCount")
                van_f = van.value("ForceMaxCount")
                if (old_f is not None and van_f is not None
                        and old_f.lower() != van_f.lower()):
                    out.append(Proposal(path=sf.path, doc=sf.doc,
                                        node=bd.node, block=name,
                                        block_id=bd.block_id,
                                        rule="MaxCount",
                                        prop="ForceMaxCount",
                                        old=old_f, new=van_f))
    return out


def apply_proposals(items: List[Proposal]) -> Dict[Path, int]:
    """Ecrit les propositions : set_property sur chaque noeud, rendu du
    document, ecriture atomique AVEC sauvegarde .bak prealable. Ne touche
    QUE les fichiers scenario passes a l'inventaire."""
    by_file: Dict[Path, List[Proposal]] = {}
    for it in items:
        by_file.setdefault(it.path, []).append(it)
    done: Dict[Path, int] = {}
    for path, items_file in by_file.items():
        applied = 0
        for it in items_file:
            if it.node.set_property(it.prop, it.new):
                applied += 1
        if applied:
            bak = path.with_suffix(path.suffix + ".bak")
            if path.exists():
                shutil.copy2(path, bak)
            atomic_write_text(path, it.doc.render())
            done[path] = applied
    return done
