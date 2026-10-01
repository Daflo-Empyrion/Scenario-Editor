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

"""Comparaison de deux bundles Unity de scenarios, en ligne de commande
(sans GUI). Usage :
    python tools/compare_bundles.py <bundleA> <bundleB> [export.csv]
UnityPy doit etre installe (pip install UnityPy)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.unity_bundles import compare_bundles  # noqa: E402


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    pa, pb = sys.argv[1], sys.argv[2]
    try:
        d = compare_bundles(pa, pb)
    except ValueError as e:
        msg = ("UnityPy absent : pip install UnityPy"
               if str(e) == "UnityPy" else f"bundle illisible : {e}")
        print(f"ERREUR: {msg}", file=sys.stderr)
        return 1
    print(f"A: {d.na} assets | B: {d.nb} assets | "
          f"ajouts {len(d.added)} | retraits {len(d.removed)} | "
          f"types differents {len(d.changed)} | identiques {d.same}")
    for p in sorted(d.added):
        print(f"  + {p} ({d.added[p]})")
    for p in sorted(d.removed):
        print(f"  - {p} ({d.removed[p]})")
    for p, (ta, tb) in sorted(d.changed.items()):
        print(f"  ~ {p} : {ta} -> {tb}")
    if len(sys.argv) > 3:
        out = Path(sys.argv[3])
        with open(out, "w", encoding="utf-8", newline="") as fh:
            fh.write("statut;chemin;type_a;type_b\n")
            for p in sorted(d.added):
                fh.write(f"ajout;{p};;{d.added[p]}\n")
            for p in sorted(d.removed):
                fh.write(f"retrait;{p};{d.removed[p]};\n")
            for p, (ta, tb) in sorted(d.changed.items()):
                fh.write(f"change;{p};{ta};{tb}\n")
        print(f"CSV ecrit : {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
