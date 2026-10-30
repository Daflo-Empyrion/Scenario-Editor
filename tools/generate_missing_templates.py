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

"""
Outil CLI : liste et cree les Templates manquants d'un scenario.

Usage :
  python tools/generate_missing_templates.py C:/Dev/RE2-ATL-PRO --vanilla "C:/.../Content"
  python tools/generate_missing_templates.py C:/Dev/RE2-ATL-PRO --vanilla "C:/.../Content" --apply
  python tools/generate_missing_templates.py ... --report tools/_rapport.csv

Sans --apply : aucun fichier n'est modifie, seule la liste est affichee.
Avec --apply : backup de Templates.ecf puis ajout des entrees manquantes
(operation idempotente : une seconde execution n'ajoute rien).
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.template_autogen import AutogenResult, apply, plan


def _report(result: AutogenResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["nom", "type", "methode", "modele", "craft_time",
                         "decon_override", "show_user", "ingredients"])
        for entry in result.entries:
            writer.writerow([
                entry.name, entry.kind, entry.method, entry.source,
                entry.craft_time, entry.decon, entry.show_user,
                " + ".join(f"{name} x{qty}" for name, qty in entry.inputs),
            ])
        for name, kind, reason in result.skipped:
            writer.writerow([name, kind, "ignore", "", "", "", reason, ""])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", help="dossier du scenario (contient Content/Configuration)")
    parser.add_argument("--vanilla", default="", help="dossier Content de la vanille (facultatif)")
    parser.add_argument("--apply", action="store_true", help="ecrire les Templates manquants")
    parser.add_argument("--report", default="", help="export CSV du plan")
    parser.add_argument("--include-empty", action="store_true",
                        help="ecrire aussi les entrees sans modele (recette vide)")
    args = parser.parse_args(argv)
    if not args.vanilla:
        try:
            from core.settings import get_vanilla_content_path
            args.vanilla = get_vanilla_content_path()
        except Exception:
            args.vanilla = ""

    root = Path(args.scenario)
    result = plan(root, args.vanilla, include_empty=args.include_empty)
    counts = result.counts
    methods = Counter(entry.method for entry in result.entries)
    print(f"Scenario : {root}")
    print(f"Templates a creer : {counts['entries']} "
          f"({counts['blocks']} blocs, {counts['items']} items)")
    print(f"  recette copiee   : {counts['non_empty']}")
    print(f"  feuilles brutes  : {counts.get('terminal', 0)} "
          f"(ingredients sans modele : template vide Stop, rendus tels quels)")
    print(f"  ignores          : {counts['skipped']} "
          f"(ressources brutes, NPC, debug, sans modele proche)")
    print("  methodes : " + ", ".join(f"{name}={n}" for name, n in methods.most_common()))
    if args.report:
        _report(result, Path(args.report))
        print(f"Rapport CSV : {args.report}")
    if not args.apply:
        print("Dry-run : aucun fichier modifie (ajouter --apply pour ecrire).")
        return 0
    result, written = apply(root, args.vanilla, include_empty=args.include_empty)
    print(f"Ecrit : {written} Templates ajoutes dans Content/Configuration/Templates.ecf")
    print("Relancer le plan apres coup doit afficher 0 (idempotence).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
