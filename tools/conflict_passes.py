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

"""CLI des passes de conflit de factions (core/conflict_warfare.py).

    python tools/conflict_passes.py --scenario C:\\Dev\\RE2-FR            # dry-run, toutes les planètes
    python tools/conflict_passes.py --scenario C:\\Dev\\RE2-FR --only Starter_Dread
    python tools/conflict_passes.py --scenario C:\\Dev\\RE2-FR --scale-pois 0.55
    python tools/conflict_passes.py --scenario C:\\Dev\\RE2-FR --apply \\
        --sync-prod "C:\\...\\Content\\Scenarios\\RE2-FR"
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.ai_realism import BackupStore  # noqa: E402
from core.tech_milestones import pass_tech_milestones  # noqa: E402
from core.conflict_warfare import (  # noqa: E402
    conflict_playfields, missing_pool_prefabs, pass_drone_aggression,
    pass_faction_conflict, pass_force_attack, pass_hostile_reputation,
    pass_mine_pois, pass_rare_resources, pass_scale_pois,
    pass_space_conflict, pass_space_defense,
    purge_playfield_cache, space_playfields,
)

_SYNC_FILES = (
    "Prefabs/_PoiGroupsConfig.yaml",
    "Content/Configuration/EClassConfig.ecf",
    "Content/Configuration/DefReputation.ecf",
    "Content/Configuration/BAIConfig.ecf",
    "Content/Configuration/Factions.ecf",
    "Content/Configuration/FactionWarfare.ecf",
    "Extras/PDA/PDA.yaml",
    "Extras/PDA/PDA.csv",
)


def sync_prod(scenario: Path, prod: Path, playfields: list,
              space: list = ()) -> int:
    """Copie les fichiers touchés vers la production et invalide les caches
    compilés du jeu. Sans la purge du `<yaml>.bin`, le jeu sert son cache
    (plus récent que la copie) et ignore la modification."""
    files = [f"Playfields/{pf}/playfield_static.yaml" for pf in playfields]
    files += [f"Playfields/{pf}/playfield_dynamic.yaml" for pf in playfields]
    files += [f"Playfields/{pf}/space_dynamic.yaml" for pf in space]
    files += list(_SYNC_FILES)
    n = 0
    for rel in files:
        src, dst = scenario / rel, prod / rel
        if not src.is_file():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)  # copyfile : mtime = maintenant
        if rel.endswith(".yaml") and "Playfields" in rel:
            purge_playfield_cache(dst)
        n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description="Passes de conflit de factions")
    ap.add_argument("--scenario", required=True, help="racine du scénario")
    ap.add_argument("--apply", action="store_true",
                    help="applique (défaut : dry-run)")
    ap.add_argument("--sync-prod", default="",
                    help="copie le résultat vers cette production (purge les caches .bin)")
    ap.add_argument("--scale-pois", type=float, default=0.0,
                    help="réduit les CountMinMax des groupes POI d'origine "
                         "(ex 0.55) ; une seule fois par playfield (marqueur)")
    ap.add_argument("--only", default="",
                    help="liste de playfields séparés par des virgules")
    ap.add_argument("--limit", type=int, default=0,
                    help="ne traiter que les N premiers playfields")
    ap.add_argument("--no-space", action="store_true",
                    help="ne pas traiter les playfields spatiaux")
    args = ap.parse_args()

    scenario = Path(args.scenario)
    playfields = conflict_playfields(scenario)
    if args.only:
        wanted = [p.strip() for p in args.only.split(",") if p.strip()]
        playfields = [p for p in playfields if p in wanted]
    if args.limit:
        playfields = playfields[:args.limit]
    store = BackupStore(scenario) if args.apply else None
    rep = {"playfields": len(playfields)}
    manquants = missing_pool_prefabs(scenario)
    if manquants:
        rep["prefabs_manquants"] = [f"{f}={p}" for f, p in manquants]
    rep["faction_conflict"] = pass_faction_conflict(
        scenario, apply=args.apply, store=store, playfields=playfields)
    rep["drone_aggression"] = pass_drone_aggression(
        scenario, apply=args.apply, store=store)
    rep["hostile_reputation"] = pass_hostile_reputation(
        scenario, apply=args.apply, store=store)
    rep["force_attack"] = pass_force_attack(
        scenario, apply=args.apply, store=store)
    rep["rare_resources"] = pass_rare_resources(
        scenario, apply=args.apply, store=store, playfields=playfields)
    rep["mine_pois"] = pass_mine_pois(
        scenario, apply=args.apply, store=store, playfields=playfields)
    rep["tech_milestones"] = pass_tech_milestones(
        scenario, apply=args.apply, store=store)
    if args.scale_pois:
        rep["scale_pois"] = pass_scale_pois(
            scenario, args.scale_pois, apply=args.apply, store=store,
            playfields=playfields)
    space = []
    if not args.no_space:
        space = space_playfields(scenario)
        if args.only:
            space = [p for p in space if p in wanted]
        if args.limit:
            space = space[:args.limit]
        rep["space_playfields"] = len(space)
        rep["space_conflict"] = pass_space_conflict(
            scenario, apply=args.apply, store=store, playfields=space)
        rep["space_defense"] = pass_space_defense(
            scenario, apply=args.apply, store=store, playfields=space)
    if args.sync_prod:
        rep["synced"] = sync_prod(scenario, Path(args.sync_prod), playfields,
                                  space=space if not args.no_space else ())
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
