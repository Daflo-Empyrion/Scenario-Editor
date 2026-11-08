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

"""CLI des correctifs de balance P1 (core/balance_audit.py).

    python tools/balance_passes.py --scenario C:\\Dev\\RE2-FR                  # dry-run
    python tools/balance_passes.py --scenario C:\\Dev\\RE2-FR --apply
    python tools/balance_passes.py --scenario C:\\Dev\\RE2-FR --list
    python tools/balance_passes.py --scenario C:\\Dev\\RE2-FR --fixes megalonops_melee --apply
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.balance_audit import ALL_BALANCE_FIXES, run_balance_fixes  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Correctifs de balance P1 du scénario")
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--fixes", default="",
                    help="noms séparés par des virgules (défaut : tous)")
    ap.add_argument("--apply", action="store_true", help="écrire (défaut : dry-run)")
    ap.add_argument("--list", action="store_true", help="lister les correctifs")
    args = ap.parse_args()

    scenario = Path(args.scenario)
    if not (scenario / "Content").exists():
        print(f"scénario invalide : {scenario}", file=sys.stderr)
        return 2

    if args.list:
        for name in ALL_BALANCE_FIXES:
            print(name)
        return 0

    names = [n.strip() for n in args.fixes.split(",") if n.strip()] or list(ALL_BALANCE_FIXES)
    unknown = [n for n in names if n not in ALL_BALANCE_FIXES]
    if unknown:
        print("correctifs inconnus :", ", ".join(unknown), file=sys.stderr)
        return 2
    print(f"=== {'APPLY' if args.apply else 'DRY-RUN'} : {', '.join(names)} ===")
    reports = run_balance_fixes(scenario, names, apply=args.apply)
    total = 0
    for r in reports:
        total += r["edits"]
        status = "; ".join(r["details"][:2]) if r["details"] else "ok"
        print(f"[{r['id']:24s}] edits={r['edits']}  | {status}")
    print("TOTAL edits:", total)
    if not args.apply:
        print("(dry-run : rien n'a été écrit — ajouter --apply)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
