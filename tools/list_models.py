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

"""Liste les MODELES (prefabs) d'un bundle Empyrion, pret a copier dans
un `Model:`. Usage :
    python tools/list_models.py models                 # tout
    python tools/list_models.py models console         # filtre
    python tools/list_models.py eden_blockmodels --scenario RE2-FR
Le nom affiche apres `@bundle/` est celui du prefab : le jeu resout une
reference PAR NOM (dossier ignore), cf. core/unity_bundles.bundle_prefabs.
UnityPy doit etre installe (pip install UnityPy)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.unity_bundles import bundle_prefabs, trouver_bundle  # noqa: E402

GAME = Path("C:/Program Files (x86)/Steam/steamapps/common/"
            "Empyrion - Galactic Survival")


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    nom = args[0]
    motif = args[1].lower() if len(args) > 1 else ""
    racines = [GAME / "Content"]
    if "--scenario" in sys.argv:
        scen = sys.argv[sys.argv.index("--scenario") + 1]
        racines.insert(0, GAME / "Content" / "Scenarios" / scen)
    bundle = trouver_bundle(nom, racines)
    if bundle is None:
        print(f"ERREUR: bundle '{nom}' introuvable (essaye {', '.join(map(str, racines))})",
              file=sys.stderr)
        return 1
    try:
        prefabs = bundle_prefabs(bundle, motif)
    except ValueError as e:
        msg = ("UnityPy absent : pip install UnityPy"
               if str(e) == "UnityPy" else f"bundle illisible : {e}")
        print(f"ERREUR: {msg}", file=sys.stderr)
        return 1
    vus = {n: c for n, c in prefabs.items()
           if not motif or motif in n.lower() or motif in c.lower()}
    print(f"{bundle} : {len(prefabs)} prefabs, {len(vus)} affiches")
    for n in sorted(vus):
        dedi = "  [dedi/serveur]" if n.lower().endswith("_dedi") else ""
        print(f"  @{nom}/{n}{dedi}\n      {vus[n]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
