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

"""Habillage CLI du look « cartoon » (l'orchestration vit dans
core/cartoon_look.run_preset, partagee avec le dialogue de l'appli).

Usage :
    python tools/cartoon_look.py                     # scenario par defaut
    python tools/cartoon_look.py --scenario C:/Dev/RE2-ATL-PRO
    python tools/cartoon_look.py --dry-run           # rien n'est ecrit
    python tools/cartoon_look.py --no-sync           # copie de travail seule
    python tools/cartoon_look.py --force             # rejouer les facteurs
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.cartoon_look import run_preset

DEFAULT_SCENARIO = "C:/Dev/RE2-ATL-PRO"


def main() -> int:
    ap = argparse.ArgumentParser(description="Look cartoon du scenario")
    ap.add_argument("--scenario", default=DEFAULT_SCENARIO)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-sync", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="reapplique les facteurs meme apres un 1er passage")
    args = ap.parse_args()

    rep = run_preset(args.scenario, dry_run=args.dry_run, force=args.force,
                     no_sync=args.no_sync)
    if rep["error"]:
        print(f"scenario introuvable : {args.scenario}")
        return 2
    if rep["marker_blocked"]:
        print("le look cartoon est deja applique (marqueur present) ; "
              "utiliser --force pour rejouer les facteurs")
        return 2
    for line in rep["invalid"]:
        print(f"VALIDATION KO, fichier saute : {line}")

    touched = rep["touched"]
    print(f"{len(touched)} fichiers a transformer, {rep['total']} lignes "
          f"reexprimees")
    if args.dry_run:
        for rel, n in touched[:12]:
            print(f"  + {rel} ({n})")
        if len(touched) > 12:
            print(f"  ... et {len(touched) - 12} autres")
        print("dry-run : rien d'ecrit")
        return 0
    if not touched:
        return 0

    print(f"sauvegardes : {rep['backup_dir']}")
    if rep["prod"]:
        print(f"production : {rep['copied']} copies, {rep['bins']} caches "
              f"invalides")
    else:
        print("pas de scenario de production connu pour cette copie ; "
              "synchroniser depuis l'editeur (Outils > Copier vers la "
              "production)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
