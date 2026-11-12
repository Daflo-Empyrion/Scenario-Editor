"""Remet a l'index palette 0 les blocs d'une famille a UNE texture.

SYMPTOME : au chargement d'un playfield, `Cannot create mesh for block id=1407
texIdx=24 table=0 pos=(...). Please fix this texture!` — quelques blocs
decoratifs invisibles.
CAUSE : `TrussCylinder` (id 1407, famille Truss) declare `Texture: 59`, une
seule texture, dans la vanille comme dans le scenario ; des prefabs lui
donnent pourtant la variante couleur 24 -> l'index n'existe pas, le mesh
n'est pas cree.
CORRECTIF : `EpbBlueprint.set_colors` remet la face 0 a 0 (masque inchange,
aucune cellule touchee). Defaut de donnee VANILLE : on nettoie les prefabs du
scenario, pas le jeu.

    python tools/fix_truss_color.py <Prefabs> [--apply]
        [--backup <dossier>] [--ids 1407] [--color 24]
"""
import argparse
import csv
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.epb_blueprint import EpbBlueprint     # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("prefabs")
    ap.add_argument("--ids", default="1407", help="ids de blocs (famille Truss)")
    ap.add_argument("--color", type=int, default=24,
                    help="seule cette variante est remise a 0 (celle du log)")
    ap.add_argument("--backup", default="", help="dossier des .epb d'origine")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    ids = [int(x) for x in a.ids.split(",") if x.strip()]
    root = Path(a.prefabs)
    bk = Path(a.backup) if a.backup else None
    if a.apply and bk:
        bk.mkdir(parents=True, exist_ok=True)
    journal = []
    files = touched = blocks = 0
    for p in sorted(root.glob("*.epb")):
        try:
            bp = EpbBlueprint(p).parse()
        except Exception as e:              # noqa: BLE001 - ignore l'illisible
            print("ILLISIBLE", p.name, e)
            continue
        cibles = [b for b in bp.blocks
                  if b.block_id in ids and b.color == a.color]
        if not cibles:
            continue
        files += 1
        n = bp.set_colors(ids, 0, only_colors=[a.color])
        blocks += n
        journal.append((p.name, n))
        if a.apply:
            if bk:
                shutil.copy2(p, bk / p.name)
            bp.save(backup=False)
            touched += 1
    for row in journal:
        print("%-45s %4d blocs" % row)
    print("== %d prefab(s), %d bloc(s) %s"
          % (files, blocks, "reecrits" if a.apply else "a corriger (dry-run)"))
    if a.apply and bk:
        with (bk / "journal.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["prefab", "blocs"])
            w.writerows(journal)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
