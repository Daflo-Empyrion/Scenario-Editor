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

"""CLI de la politique de regeneration (core/regen_policy.py).

    python tools/regen_passes.py --scenario C:\\Dev\\RE2-FR              # bilan, rien n'ecrit
    python tools/regen_passes.py --scenario C:\\Dev\\RE2-FR --only Desert
    python tools/regen_passes.py --scenario C:\\Dev\\RE2-FR --apply \\
        --sync-prod "C:\\...\\Content\\Scenarios\\RE2-FR"

Idempotent : relance = 0 changement. A lancer APRES les passes de conflit,
qui reecrivent `RegenAfter: 720` en dur pour les POI qu'elles generent.
"""
import argparse
import shutil
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.fsutil import central_backup            # noqa: E402
from core.regen_policy import (MINE_CYCLE, plan, read,  # noqa: E402
                               rewrite, scan)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--only", default="", help="un seul playfield")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--sync-prod", default="", help="copier les yaml modifies ici")
    args = ap.parse_args()

    scenario = Path(args.scenario)
    if not (scenario / "Playfields").is_dir():
        print(f"pas un scenario : {scenario}")
        return 2

    rows, anchor_set = plan(scenario)
    if args.only:
        rows = [r for r in rows if r["path"].parent.name == args.only]
    if not rows:
        print(f"conforme : 0 changement ({len(anchor_set)} ancres protégées)")
        return 0

    kinds = Counter()
    for row in rows:
        for _ln, _name, _old, want in row["changes"]:
            kinds["mine 72h" if want == MINE_CYCLE else "definitif"] += 1
    total = sum(len(r["changes"]) for r in rows)
    print(f"{len(rows)} playfield(s), {total} POI a normaliser "
          f"({kinds['definitif']} definitifs, {kinds['mine 72h']} mines a 72 h)")
    print(f"ancres protegees : {len(anchor_set)}")
    for row in rows[:8]:
        print(f"   {row['path'].parent.name:<24} {len(row['changes']):>4} POI")
    if len(rows) > 8:
        print(f"   ... {len(rows) - 8} autres playfields")

    if not args.apply:
        print("\ndry-run : rien n'a ete ecrit (--apply pour appliquer)")
        return 0

    prod = Path(args.sync_prod) if args.sync_prod else None
    for row in rows:
        path = row["path"]
        central_backup(path, "regen")
        path.write_text(rewrite(row["text"], row["changes"]), encoding="utf-8",
                        newline="")
        if prod:
            target = prod / "Playfields" / path.parent.name / path.name
            if target.parent.is_dir():
                shutil.copy2(path, target)
    print(f"\napplique a {len(rows)} playfield(s)"
          + (f", copie vers {prod}" if prod else ""))
    restant = scan(scenario)
    print(f"controle : {len(restant)} POI hors politique")
    return 0 if not restant else 1


if __name__ == "__main__":
    raise SystemExit(main())
