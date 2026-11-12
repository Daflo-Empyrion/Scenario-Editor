"""Bilan AVANT LANCEMENT du scenario — a executer apres toute edition.

Un seul passage couvre tous les checks de `core.launch_check`
(structure ECF, references d'items, conteneurs, playfields, secteurs,
factions, hygiene). Deux crashs du 12/11 ont coute deux lancements parce que
ce bilan n'avait pas ete lance :

- `Material: metalweapon` (materiau de la vanille) -> `Exception: Material ...
  not found` puis `NullReferenceException` dans `DeployPciture` ;
- 10 blocs `+LootGroup` ecrits dans `Containers.ecf` (le fichier n'admet que
  `Container`) -> `IndexOutOfRangeException` dans `EcfFile.ParseLines`.

    python tools/prelaunch_check.py C:/Dev/RE2-FR
    python tools/prelaunch_check.py "<prod>/Content/Scenarios/RE2-FR" --all

Code retour : 0 si aucune ERREUR (les avertissements n'empechent pas de lancer).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.launch_check import run_launch_checks      # noqa: E402

BASE_CONTENT = ("C:/Program Files (x86)/Steam/steamapps/common/Empyrion - "
                "Galactic Survival/Content")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario")
    ap.add_argument("--all", action="store_true",
                    help="affiche aussi les avertissements")
    ap.add_argument("--vanilla", default=BASE_CONTENT)
    a = ap.parse_args()
    root = Path(a.scenario)
    issues = run_launch_checks(root, a.vanilla)
    err = [i for i in issues if i.severity == "error"]
    warn = [i for i in issues if i.severity != "error"]
    for i in err:
        print("ERREUR  [%s] %s : %s" % (i.check, i.path, i.message))
        if i.fix:
            print("          correctif : %s" % i.fix)
    if a.all:
        for i in warn:
            print("ATTENTION [%s] %s : %s" % (i.check, i.path, i.message))
    print("== %d erreur(s), %d avertissement(s)" % (len(err), len(warn)))
    return 1 if err else 0


if __name__ == "__main__":
    sys.exit(main())
