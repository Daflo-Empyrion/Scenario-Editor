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

"""Regle metier trans-fichiers : TraderZone d'un playfield vers la table de
marchands du scenario. Le top-level 'TraderZone: <nom>' d'un Playfield.yaml
doit designer un marchand declare dans TraderNPCConfig.ecf du MEME scenario
(meme source que les listes deroulantes de l'editeur playfield, voir
core/economy/trader_config.load_trader_names).

Volontairement ABSENT de cette passe (pieges documentes, voir
CONTEXTE_REPRISE) : la verification PDA -> catalogue d'items (les jetons de
dialogue 'Token:<n>' des CardDealer ne sont PAS des items, et les structures
d'objectifs PDA varient trop pour une regle fiable sans faux positifs)."""

from pathlib import Path
from typing import List

from core.ecf.validation import ValidationIssue
from core.yamllite.parser import parse_yaml_file
from core.yamllite.model import YamlEntry

PLAYFIELD_YAML = "Playfield.yaml"


def _iter_playfield_yamls(root: Path):
    """Tous les YAML des dossiers de playfields (les noms varient selon les
    scenarios : Playfield.yaml, playfield_static.yaml...)."""
    for pf_dir in sorted((root / "Playfields").glob("*")):
        if not pf_dir.is_dir():
            continue
        for yaml_path in sorted(pf_dir.glob("*.yaml")):
            yield yaml_path
        for yaml_path in sorted(pf_dir.glob("*.yml")):
            yield yaml_path


def _top_level_trader_zone(yaml_path: Path) -> str:
    """Valeur du top-level 'TraderZone' ("" si absent ou illisible)."""
    try:
        doc = parse_yaml_file(yaml_path)
    except Exception:
        return ""
    for node in doc.nodes:
        if isinstance(node, YamlEntry) and node.key == "TraderZone":
            return (node.value or "").strip()
    return ""


def check_trader_zone_references(working_root: Path) -> List[ValidationIssue]:
    """Signale (W010) chaque Playfield.yaml dont la cle top-level 'TraderZone'
    designe un marchand absent de TraderNPCConfig.ecf du scenario. Fichier
    marchand absent ou illisible : aucun signalement (on ne juge pas ce qu'on
    ne peut pas lire -- meme philosophie que les regles scopees de
    validation.py)."""
    from core.economy.trader_config import load_trader_names

    root = Path(working_root)
    issues: List[ValidationIssue] = []
    trader_names = load_trader_names(root / "Content" / "Configuration"
                                     / "TraderNPCConfig.ecf")
    if not trader_names:
        return issues
    known = {n.strip().lower() for n in trader_names if n and n.strip()}
    for yaml_path in _iter_playfield_yamls(root):
        zone = _top_level_trader_zone(yaml_path)
        if not zone or zone.lower() in known:
            continue
        issues.append(ValidationIssue(
            code='W010', level='warning', block=None,
            property_key='TraderZone',
            message=(f"TraderZone '{zone}' : aucun marchand de ce nom dans "
                     f"TraderNPCConfig.ecf du scenario."),
            file_path=yaml_path))
    return issues
