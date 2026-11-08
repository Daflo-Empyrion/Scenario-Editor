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

"""CLI des passes de réalisme IA (core/ai_realism.py).

    python tools/ai_passes.py --scenario C:\\Dev\\RE2-FR --audit
    python tools/ai_passes.py --scenario C:\\Dev\\RE2-FR --list
    python tools/ai_passes.py --scenario C:\\Dev\\RE2-FR --passes tier_curves,repop            # dry-run
    python tools/ai_passes.py --scenario C:\\Dev\\RE2-FR --passes tier_curves --apply
    python tools/ai_passes.py --scenario C:\\Dev\\RE2-FR --revert 20261108_101059
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.ai_realism import ALL_PASSES, BackupStore, run_audit, run_passes  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Passes de réalisme IA du scénario")
    ap.add_argument("--scenario", required=True, help="racine du scénario")
    ap.add_argument("--passes", default="",
                    help="noms séparés par des virgules (défaut : toutes)")
    ap.add_argument("--apply", action="store_true",
                    help="écrire (défaut : dry-run)")
    ap.add_argument("--audit", action="store_true", help="afficher l'audit")
    ap.add_argument("--list", action="store_true", help="lister les passes")
    ap.add_argument("--revert", metavar="RUN_ID", help="restaurer un run de backup")
    args = ap.parse_args()

    scenario = Path(args.scenario)
    if not (scenario / "Content").exists():
        print(f"scénario invalide : {scenario}", file=sys.stderr)
        return 2

    if args.list:
        for name in ALL_PASSES:
            print(name)
        return 0

    if args.revert:
        store = BackupStore(scenario, run_id=args.revert)
        n = store.revert()
        print(f"restauré {n} fichier(s) depuis {store.root}")
        return 0

    if args.audit:
        findings = run_audit(scenario)
        if not findings:
            print("audit : aucun constat")
        for f in findings:
            print(f"[{f['severity']:8s}] {f['id']:16s} x{f['count']:5d}  {f['message']}")
        return 0

    names = [n.strip() for n in args.passes.split(",") if n.strip()] or list(ALL_PASSES)
    unknown = [n for n in names if n not in ALL_PASSES]
    if unknown:
        print("passes inconnues :", ", ".join(unknown), file=sys.stderr)
        return 2
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"=== {mode} : {', '.join(names)} ===")
    reports = run_passes(scenario, names, apply=args.apply)
    total = 0
    for r in reports:
        total += r["edits"]
        print(f"[{r['pass']:15s}] fichiers={r['files']:4d} edits={r['edits']:5d}"
              + (" | " + "; ".join(r["details"][:3]) if r["details"] else ""))
    print("TOTAL edits:", total)
    if not args.apply:
        print("(dry-run : rien n'a été écrit — ajouter --apply)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
