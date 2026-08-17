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
Applique une transformation numerique en masse a un fichier .ecf : multiplier, ajouter,
fixer, ou plafonner toutes les valeurs d'une cle de propriete donnee, sur un genre de
bloc (et eventuellement une liste d'identites precises).

UTILISATION :
    python transform_ecf.py fichier.ecf --key param1 --op multiply --amount 1.2
    python transform_ecf.py fichier.ecf --kind +Container --key Count --op set --amount 5
    python transform_ecf.py fichier.ecf --kind +Container --ids 5,6,7 --key param1 --op add --amount 0.1
    python transform_ecf.py fichier.ecf --key Health --op clamp --min 10 --max 500 --no-recursive

OPTIONS :
    --kind          Genre de bloc a cibler (ex: +Container). Par defaut : tous les genres.
    --ids           Liste d'identites (Id/Name) separees par des virgules. Par defaut : tous.
    --key           Cle de propriete a transformer (ex: param1, Count, Health). OBLIGATOIRE.
    --op            multiply | add | set | clamp | round. OBLIGATOIRE.
    --amount        Valeur pour multiply / add / set.
    --min / --max   Bornes pour clamp.
    --ndigits       Nombre de decimales pour round (defaut 2).
    --no-recursive  Ne pas chercher dans les sous-blocs (ex: Child Items).
"""
import argparse
import sys
from pathlib import Path

if getattr(sys, 'frozen', False):
    # Construit par PyInstaller (voir empyrion_editor.spec, executable
    # 'EmpyrionEditorCLI') : 'core' est deja compile et importable directement,
    # aucune recherche de dossier necessaire.
    pass
else:
    _ici = Path(__file__).resolve().parent
    _candidats = [_ici, _ici / "empyrion_editor", _ici.parent, _ici.parent / "empyrion_editor"]
    for _c in _candidats:
        if (_c / "core" / "ecf" / "transform.py").exists():
            sys.path.insert(0, str(_c))
            break
    else:
        print("ERREUR : impossible de trouver core/ecf/transform.py")
        sys.exit(1)
from core.ecf.parser import parse_ecf_text
from core.ecf.transform import apply_transform, TransformRule, format_report
from core.ecf.diff import diff_documents, format_diff


def main():
    p = argparse.ArgumentParser(description="Transformation en masse sur un fichier ECF")
    p.add_argument('file', type=Path)
    p.add_argument('--kind', default=None, help="Genre de bloc a cibler (ex: +Container)")
    p.add_argument('--ids', default=None, help="Identites separees par des virgules (ex: 5,6,7)")
    p.add_argument('--key', required=True, help="Cle de propriete a transformer")
    p.add_argument('--op', required=True, choices=['multiply', 'add', 'set', 'clamp', 'round'])
    p.add_argument('--amount', type=float, default=None)
    p.add_argument('--min', type=float, default=None, dest='min_value')
    p.add_argument('--max', type=float, default=None, dest='max_value')
    p.add_argument('--ndigits', type=int, default=2)
    p.add_argument('--no-recursive', action='store_true')
    args = p.parse_args()

    if not args.file.exists():
        print(f"ERREUR : fichier introuvable : {args.file}")
        sys.exit(1)

    if args.op in ('multiply', 'add', 'set') and args.amount is None:
        print(f"ERREUR : --amount est requis pour l'operation '{args.op}'")
        sys.exit(1)
    if args.op == 'clamp' and args.min_value is None and args.max_value is None:
        print("ERREUR : --min et/ou --max sont requis pour l'operation 'clamp'")
        sys.exit(1)

    with open(args.file, 'r', encoding='utf-8', newline='') as f:
        original_raw = f.read()

    doc = parse_ecf_text(original_raw, source_path=str(args.file))

    rule = TransformRule(
        property_key=args.key,
        operation=args.op,
        amount=args.amount,
        min_value=args.min_value,
        max_value=args.max_value,
        ndigits=args.ndigits,
        block_kind=args.kind,
        block_ids=args.ids.split(',') if args.ids else None,
        recursive=not args.no_recursive,
    )

    report = apply_transform(doc, rule)

    print("=" * 60)
    print("RAPPORT DE TRANSFORMATION")
    print("=" * 60)
    print(format_report(report))
    print()

    if not report.changes:
        print("Aucune valeur modifiee -- rien a sauvegarder.")
        return

    original_doc = parse_ecf_text(original_raw)
    diffs = diff_documents(original_doc, doc)
    print("=" * 60)
    print("APERCU (via le diff)")
    print("=" * 60)
    print(format_diff(diffs))
    print()

    confirm = input(f"Confirmer l'ecriture dans {args.file} ? (o/N) ")
    if confirm.lower() != 'o':
        print("Annule.")
        return

    backup_path = args.file.with_suffix(args.file.suffix + '.bak')
    if not backup_path.exists():
        with open(backup_path, 'w', encoding='utf-8', newline='') as f:
            f.write(original_raw)
        print(f"Sauvegarde de l'original creee : {backup_path}")

    rendered = doc.render()
    with open(args.file, 'w', encoding='utf-8', newline='') as f:
        f.write(rendered)

    print(f"Transformation ecrite : {args.file}")


if __name__ == "__main__":
    main()
