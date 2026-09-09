"""Validation economie (regles ECO) + extraction des assignations TraderZone.

Les problemes sont decrits par CLES i18n (jamais de texte en dur) : l'interface
les passe dans t(cle, **params). Un fichier TraderNPCConfig.ecf sans
TraderZone dans les playfields n'est pas une erreur en soi (les PNJ peuvent
porter leur table dans leur blueprint) -- 'trader_unassigned' est un simple
avertissement (regle YAML-009 : visible, jamais bloquant).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


from core.economy.market_price import lookup_case_insensitive
from core.economy.model import TOKEN_ITEM_RE
from core.economy.trader_config import TraderConfigDoc, TraderItemRow


@dataclass
class EcoIssue:
    code: str                 # 'eco.item_unknown', 'eco.price_inverted', ...
    level: str                # 'error' | 'warning'
    params: dict = field(default_factory=dict)
    trader: str = ""
    item_key: str = ""


@dataclass
class TraderZoneAssignment:
    playfield: str            # nom du dossier playfield
    poi: Optional[str]        # nom du POI/groupe si Properties, None si top-level
    trader: str


def validate_trader_doc(config: TraderConfigDoc, index: Dict[str, Optional[float]]) -> List[EcoIssue]:
    issues: List[EcoIssue] = []
    for view in config.views():
        for row in view.rows:
            issues.extend(_validate_row(view.name, row, index))
    return issues


def _validate_row(trader: str, row: TraderItemRow, index: Dict[str, Optional[float]]) -> List[EcoIssue]:
    issues: List[EcoIssue] = []
    if row.item is None:
        issues.append(EcoIssue(code="eco.item_unreadable", level="error",
                               params={"raw": row.raw_value}, trader=trader, item_key=row.key))
        return issues
    item = row.item
    if TOKEN_ITEM_RE.match(item.name):
        # jeton de dialogue (marchands CardDealer vanilla) : hors catalogue
        # d'items, jamais signalable "absent" (faux positif constate en vrai)
        return issues
    if lookup_case_insensitive(index, item.name) is None and item.name not in index:
        issues.append(EcoIssue(code="eco.item_unknown", level="error",
                               params={"name": item.name}, trader=trader, item_key=row.key))
    for spec, kind in ((item.sell_price, "sell_price"), (item.sell_stock, "sell_stock"),
                       (item.buy_price, "buy_price"), (item.buy_max_stock, "buy_max_stock")):
        if spec is not None and spec.ranged and spec.lo_f > spec.hi_f:
            issues.append(EcoIssue(code="eco.price_inverted", level="error",
                                   params={"value": spec.render(), "kind": kind},
                                   trader=trader, item_key=row.key))
    return issues


def extract_zone_assignments(working_root: Path) -> List[TraderZoneAssignment]:
    """Scanne Content/Playfields/*/playfield*.yaml + space*.yaml : cle top-level
    'TraderZone' (tout le playfield) et motif 'Properties: [- Key: TraderZone,
    Value: X]' (groupe de POI). Les fichiers illisibles sont ignores
    (l'editeur playfield les signalera de son cote)."""
    assignments: List[TraderZoneAssignment] = []
    base = Path(working_root) / "Content" / "Playfields"
    if not base.is_dir():
        return assignments
    from core.yamllite.parser import parse_yaml_file
    from core.yamllite.model import YamlEntry
    for pf_dir in sorted(base.iterdir()):
        if not pf_dir.is_dir():
            continue
        for yaml_name in ("playfield_static.yaml", "playfield_dynamic.yaml",
                          "space_static.yaml", "space_dynamic.yaml"):
            yaml_path = pf_dir / yaml_name
            if not yaml_path.is_file():
                continue
            try:
                doc = parse_yaml_file(yaml_path)
            except Exception:
                continue
            pf = pf_dir.name

            def _walk(nodes, poi_name: Optional[str]):
                for n in nodes:
                    if not isinstance(n, YamlEntry):
                        continue
                    key = n.key
                    if key in ("Name", "PrefabName", "GroupName") and n.value and not poi_name:
                        poi_name = n.value.strip().strip('"')
                    elif key == "TraderZone" and n.value and n.value.strip():
                        assignments.append(TraderZoneAssignment(
                            playfield=pf, poi=None, trader=n.value.strip().strip('"')))
                    elif key == "Properties":
                        for child in n.children:
                            if isinstance(child, YamlEntry) and child.key == "Key" \
                                    and (child.value or "").strip() == "TraderZone":
                                v = (child.get("Value") or "").strip()
                                if v:
                                    assignments.append(TraderZoneAssignment(
                                        playfield=pf, poi=poi_name,
                                        trader=v.strip().strip('"')))
                    _walk(n.children, poi_name)

            _walk(doc.nodes, None)
    return assignments


def validate_assignments(known: set,
                         assignments: List[TraderZoneAssignment]) -> List[EcoIssue]:
    """Coherence zones <-> profils : zone pointant un profil inexistant (erreur),
    profil jamais reference par aucune zone (avertissement -- un PNJ peut aussi
    porter sa table directement dans son blueprint). `known` = noms des profils
    du TraderNPCConfig.ecf (vide si le fichier n'existe pas : seules les zones
    vers un profil inconnu sont alors signalables)."""
    issues: List[EcoIssue] = []
    for a in assignments:
        if a.trader not in known:
            issues.append(EcoIssue(code="eco.zone_unknown_trader", level="error",
                                   params={"trader": a.trader, "playfield": a.playfield,
                                           "poi": a.poi or ""}))
    if known:
        assigned = {a.trader for a in assignments}
        for name in known:
            if name not in assigned:
                issues.append(EcoIssue(code="eco.trader_unassigned", level="warning",
                                       params={"trader": name}))
    return issues
