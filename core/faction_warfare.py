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

"""Defenses de faction (FactionWarfare.ecf) : Space Base Defense — attaques
automatiques tarifees par niveau de faction, plus les unites et scenarios
d'attaque qu'elles composent.

Structure confirmee sur le fichier RE2 (97 blocs) : tous les blocs sont
`{ Element Name: <type> ... }` — le type est la PAIRE 'Name' de la ligne
d'ouverture, les identites vivent en proprietes enfants.

- GlobalSettings : EnableSpaceDefense, EnableSpaceDefenseLog,
  PlayerAttackMaxCountFrequencySpawned, PlayerAttackMaxCountPOISpawned ;
- FactionSettings : Faction, ScenarioGroup, et DEUX formes de prix selon la
  faction — a plat (Lvl1MinPrice/Lvl1MaxPrice/Lvl5.../Lvl10...) ou dans un
  enfant `Child BaseAttack_ScenarioPrice` (PlayFieldLvl1Min/Max...). Les
  deux sont lues et ecrites ; la forme d'origine est conservee ;
- space defense : SDScenarioGroup, SDProbabilityMin/Max, SDPriceMin/Max ;
- Unit : Faction, ClassName, Category, CommandPointsLvl1/PerLevel ;
- Scenario : Name, ID, IsInGroups (groupes = ScenarioGroup des factions),
  MaxPriceMultiplier, enfants UnitN (Category, OptimalCount, MinCount,
  MaxLevel)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.ecf.model import EcfBlock, EcfDocument, EcfProperty, add_property_line
from core.ecf.parser import parse_ecf_file
from core.ecf.validation import ValidationIssue

WARFARE_FILE = "FactionWarfare.ecf"
FACTIONS_FILE = "Factions.ecf"

LEVELS = (1, 5, 10)

# formes de prix : a plat sur la faction, ou dans l'enfant BaseAttack_ScenarioPrice
_FLAT_KEYS = {(1, "min"): "Lvl1MinPrice", (1, "max"): "Lvl1MaxPrice",
              (5, "min"): "Lvl5MinPrice", (5, "max"): "Lvl5MaxPrice",
              (10, "min"): "Lvl10MinPrice", (10, "max"): "Lvl10MaxPrice"}
_CHILD_KEYS = {(1, "min"): "PlayFieldLvl1Min", (1, "max"): "PlayFieldLvl1Max",
               (5, "min"): "PlayFieldLvl5Min", (5, "max"): "PlayFieldLvl5Max",
               (10, "min"): "PlayFieldLvl10Min", (10, "max"): "PlayFieldLvl10Max"}
_SD_KEYS = {"sd_group": "SDScenarioGroup",
            "sd_prob_min": "SDProbabilityMin", "sd_prob_max": "SDProbabilityMax",
            "sd_price_min": "SDPriceMin", "sd_price_max": "SDPriceMax"}
_GLOBAL_KEYS = ("EnableSpaceDefense", "EnableSpaceDefenseLog",
                "PlayerAttackMaxCountFrequencySpawned",
                "PlayerAttackMaxCountPOISpawned")


@dataclass
class DefenseEntry:
    """Une faction et sa grille de prix (faction cote attaque)."""
    faction: str
    scenario_group: str = ""
    block: Optional[EcfBlock] = None
    price_child: Optional[EcfBlock] = None      # Child BaseAttack_ScenarioPrice
    values: Dict[str, float] = field(default_factory=dict)   # cle -> valeur

    def price(self, level: int, which: str) -> Optional[float]:
        return self.values.get(_price_key(self, level, which))


@dataclass
class UnitEntry:
    faction: str
    class_name: str
    category: str
    cp_lvl1: float = 0.0
    cp_per_level: float = 0.0


@dataclass
class ScenarioEntry:
    name: str
    sid: str
    groups: str
    max_price_multiplier: str
    units: List[Tuple[str, str]] = field(default_factory=list)  # (categorie, maxlevel)


@dataclass
class WarScan:
    path: Optional[Path] = None
    doc: Optional[EcfDocument] = None
    globals_block: Optional[EcfBlock] = None
    globals_values: Dict[str, str] = field(default_factory=dict)
    factions: List[DefenseEntry] = field(default_factory=list)
    units: List[UnitEntry] = field(default_factory=list)
    scenarios: List[ScenarioEntry] = field(default_factory=list)
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def editable(self) -> bool:
        return self.doc is not None and self.path is not None


def find_warfare_file(root: Path) -> Optional[Path]:
    for candidate in (Path(root) / "Content" / "Configuration" / WARFARE_FILE,
                      Path(root) / "Configuration" / WARFARE_FILE):
        if candidate.is_file():
            return candidate
    return None


def _prop(block: EcfBlock, key: str) -> Optional[EcfProperty]:
    for child in block.children:
        if isinstance(child, EcfProperty) and child.get(key) is not None:
            return child
    return None


def _val(block: EcfBlock, key: str) -> str:
    prop = _prop(block, key)
    return (prop.get(key) or "").strip() if prop else ""


def _unquote(text: str) -> str:
    """Les valeurs ECF sont souvent entre guillemets ('IsInGroups: "Zirax"',
    'Factions.ecf Name: "Zirax"') : comparer sans eux, sinon tout parait
    inconnu (faux positifs W331 constates sur RE2)."""
    return text.strip().strip('"').strip("'")


def _group_list(text: str) -> List[str]:
    return [g.strip() for g in _unquote(text).split(",") if g.strip()]


def _num(text: str) -> Optional[float]:
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _faction_names(path: Optional[Path]) -> set:
    if path is None or not path.is_file():
        return set()
    try:
        doc = parse_ecf_file(path)
    except Exception:                              # noqa: BLE001
        return set()
    names = set()
    for node in doc.nodes:
        if isinstance(node, EcfBlock) and node.kind == "Faction":
            name = (node.get("Name") or "").strip().strip('"')
            if name:
                names.add(name)
    return names


def scan(root: Path) -> WarScan:
    root = Path(root)
    path = find_warfare_file(root)
    result = WarScan(path=path)
    if path is None:
        return result
    try:
        doc = parse_ecf_file(path)
    except Exception as exc:                       # noqa: BLE001 - illisible
        result.issues.append(ValidationIssue(
            code="E330", level="error",
            message=f"FactionWarfare.ecf illisible : {exc}", file_path=path))
        return result
    result.doc = doc

    elements: List[EcfBlock] = []
    for node in doc.nodes:
        if isinstance(node, EcfBlock) and node.kind == "Element":
            elements.append(node)

    for block in elements:
        kind = (block.get("Name") or "").strip()
        if kind == "GlobalSettings":
            result.globals_block = block
            for key in _GLOBAL_KEYS:
                result.globals_values[key] = _val(block, key)
        elif kind == "FactionSettings":
            result.factions.append(_read_faction(block))
        elif kind == "Unit":
            result.units.append(UnitEntry(
                faction=_unquote(_val(block, "Faction")),
                class_name=_unquote(_val(block, "ClassName")),
                category=_unquote(_val(block, "Category")),
                cp_lvl1=_num(_val(block, "CommandPointsLvl1")) or 0.0,
                cp_per_level=_num(_val(block, "CommandPointsPerLevel")) or 0.0))
        elif kind == "Scenario":
            units = []
            for child in block.children:
                if isinstance(child, EcfBlock) and child.kind.startswith("Child Unit"):
                    units.append((_unquote(_val(child, "Category")),
                                  _val(child, "MaxLevel")))
            result.scenarios.append(ScenarioEntry(
                name=_unquote(_val(block, "Name")), sid=_val(block, "ID"),
                groups=_unquote(_val(block, "IsInGroups")),
                max_price_multiplier=_val(block, "MaxPriceMultiplier"),
                units=units))

    _run_checks(root, result)
    return result


def _read_faction(block: EcfBlock) -> DefenseEntry:
    entry = DefenseEntry(faction=_unquote(_val(block, "Faction")),
                         scenario_group=_unquote(_val(block, "ScenarioGroup")),
                         block=block)
    for child in block.children:
        if isinstance(child, EcfBlock) and child.kind.strip().endswith(
                "BaseAttack_ScenarioPrice"):
            entry.price_child = child
            break
    for (level, which), key in _FLAT_KEYS.items():
        value = _num(_val(block, key))
        if value is not None:
            entry.values["flat:" + key] = value
    if entry.price_child is not None:
        for (level, which), key in _CHILD_KEYS.items():
            value = _num(_val(entry.price_child, key))
            if value is not None:
                entry.values["child:" + key] = value
    for slot, key in _SD_KEYS.items():
        raw = _unquote(_val(block, key))
        value = _num(raw)
        if value is not None:
            entry.values[slot] = value
        elif raw:
            entry.values[slot] = raw
    return entry


def _price_key(entry: DefenseEntry, level: int, which: str) -> str:
    if entry.price_child is not None:
        return "child:" + _CHILD_KEYS[(level, which)]
    return "flat:" + _FLAT_KEYS[(level, which)]


def set_price(entry: DefenseEntry, level: int, which: str,
              value: float) -> bool:
    """Ecrit un prix dans la forme d'ORIGINE de la faction (a plat ou dans
    l'enfant BaseAttack_ScenarioPrice) — jamais les deux."""
    key = _price_key(entry, level, which)
    target = entry.price_child if entry.price_child is not None else entry.block
    if target is None:
        return False
    prop_key = _CHILD_KEYS[(level, which)] if entry.price_child is not None \
        else _FLAT_KEYS[(level, which)]
    text = _render_num(value)
    prop = _prop(target, prop_key)
    if prop is not None:
        prop.set(prop_key, text)
    else:
        add_property_line(target, [(prop_key, text)])
    entry.values[key] = value
    return True


def set_sd(entry: DefenseEntry, slot: str, value) -> bool:
    if entry.block is None or slot not in _SD_KEYS:
        return False
    key = _SD_KEYS[slot]
    text = _render_num(value) if isinstance(value, (int, float)) else str(value)
    prop = _prop(entry.block, key)
    if prop is not None:
        prop.set(key, text)
    else:
        add_property_line(entry.block, [(key, text)])
    entry.values[slot] = value
    return True


def set_global(result: WarScan, key: str, value) -> bool:
    if result.globals_block is None or key not in _GLOBAL_KEYS:
        return False
    text = ("True" if value else "False") if isinstance(value, bool) \
        else _render_num(value) if isinstance(value, (int, float)) else str(value)
    prop = _prop(result.globals_block, key)
    if prop is not None:
        prop.set(key, text)
    else:
        add_property_line(result.globals_block, [(key, text)])
    result.globals_values[key] = text
    return True


def _render_num(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:g}"


def save(result: WarScan) -> Path:
    from core.fsutil import atomic_write_text, central_backup  # local : monkeypatch conftest
    if result.path is None or result.doc is None:
        raise ValueError("FactionWarfare.ecf absent")
    central_backup(result.path, "faction_warfare")
    atomic_write_text(result.path, result.doc.render())
    return result.path


# ============================================================================
# Controles
# ============================================================================

def _run_checks(root: Path, result: WarScan) -> None:
    path = result.path
    known_factions = _faction_names(find_config(root, FACTIONS_FILE))
    # groupes connus : ScenarioGroup ET SDScenarioGroup (le scenario 'BD1' de
    # RE2 vise le groupe de defense spatiale — alerter serait un faux positif)
    groups = set()
    for entry in result.factions:
        if entry.scenario_group:
            groups.add(entry.scenario_group)
        sd_group = entry.values.get("sd_group")
        if isinstance(sd_group, str) and sd_group:
            groups.add(sd_group)
    # une unite est adressable par sa CATEGORIE ou par son ClassName (les deux
    # apparaissent comme 'Category' dans les scenarios reels de RE2)
    categories = {u.category for u in result.units if u.category}
    categories |= {u.class_name for u in result.units if u.class_name}

    for entry in result.factions:
        if known_factions and entry.faction not in known_factions:
            result.issues.append(ValidationIssue(
                code="E331", level="error",
                message=f"faction '{entry.faction}' declaree en defense mais "
                        f"absente de Factions.ecf", file_path=path))
        for level in LEVELS:
            lo = entry.price(level, "min")
            hi = entry.price(level, "max")
            if lo is not None and hi is not None and lo > hi:
                result.issues.append(ValidationIssue(
                    code="W333", level="warning",
                    message=f"{entry.faction} : prix niveau {level} min "
                            f"({_render_num(lo)}) > max ({_render_num(hi)})",
                    file_path=path))

    for scenario in result.scenarios:
        scenario_groups = _group_list(scenario.groups)
        unknown = [g for g in scenario_groups if g not in groups]
        if groups and unknown:
            result.issues.append(ValidationIssue(
                code="W331", level="warning",
                message=f"scenario '{scenario.name}' : groupe(s) "
                        f"{', '.join(unknown)} absent(s) des ScenarioGroup "
                        f"des factions -- jamais utilise par les attaques",
                file_path=path))
        if categories:
            for category, _max_level in scenario.units:
                if category and category not in categories:
                    result.issues.append(ValidationIssue(
                        code="W332", level="warning",
                        message=f"scenario '{scenario.name}' : categorie "
                                f"'{category}' absente des Unit -- unite "
                                f"jamais fournie par une faction",
                        file_path=path))


def find_config(root: Path, name: str) -> Optional[Path]:
    for candidate in (Path(root) / "Content" / "Configuration" / name,
                      Path(root) / "Configuration" / name):
        if candidate.is_file():
            return candidate
    return None


def check_warfare(root: Path) -> List[ValidationIssue]:
    """Raccourci bilan."""
    return scan(root).issues
