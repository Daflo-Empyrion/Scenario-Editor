"""
Editeur ECF simple, en ligne de commande interactive.

UTILISATION :
    python edit_ecf.py fichier.ecf

Une fois lance, tape 'help' pour voir les commandes disponibles.

PRINCIPE DE SECURITE :
- Aucune modification n'est ecrite sur disque tant que tu ne tapes pas 'save'.
- Avant 'save', un apercu des changements (diff) est toujours affiche, et une
  confirmation est demandee.
- Le tout premier 'save' d'une session cree automatiquement une sauvegarde de
  l'original (fichier.ecf.bak) avant d'ecrire quoi que ce soit.
"""
import shutil
import sys
from pathlib import Path

_ici = Path(__file__).resolve().parent
_candidats = [_ici, _ici / "empyrion_editor", _ici.parent, _ici.parent / "empyrion_editor"]
for _c in _candidats:
    if (_c / "core" / "ecf" / "parser.py").exists():
        sys.path.insert(0, str(_c))
        break
else:
    print("ERREUR : impossible de trouver core/ecf/parser.py")
    sys.exit(1)

from core.ecf.parser import parse_ecf_file, parse_ecf_text
from core.ecf.model import EcfProperty
from core.ecf.diff import diff_documents, format_diff, summarize_diff


HELP_TEXT = """
Commandes disponibles :
  kinds                          Liste les genres de blocs presents (ex: +Container)
  list <genre>                   Liste les blocs de ce genre (ex: list +Container)
  show <genre> <id>               Affiche le detail d'un bloc (ex: show +Container 5)
  set <genre> <id> <cle> <valeur> Modifie une propriete du bloc (ex: set +Container 5 Count "9,9")
  diff                             Affiche les changements en attente (pas encore sauvegardes)
  save                              Sauvegarde sur disque (avec apercu + confirmation)
  help                              Affiche cette aide
  quit / exit                       Quitte (previent si des changements ne sont pas sauvegardes)

Note : cette version simple modifie uniquement les proprietes directes d'un bloc
(celles visibles dans 'show'). Pour modifier une ligne a l'interieur d'un sous-bloc
(ex: 'Name_0' dans 'Child Items' d'un Container), utilise l'API Python directement --
demande a Claude si besoin, c'est prevu pour une prochaine etape.
""".strip()


def print_block_detail(block):
    print(f"Genre : {block.kind}")
    if block.pairs:
        print("Propriete(s) d'en-tete :")
        for k, v in block.pairs:
            if k:
                print(f"  {k}: {v}")
    props = [c for c in block.children if isinstance(c, EcfProperty)]
    if props:
        print("Propriete(s) :")
        for p in props:
            for k, v in p.pairs:
                if k:
                    print(f"  {k}: {v}")
    sub_blocks = block.child_blocks()
    if sub_blocks:
        print("Sous-bloc(s) (lecture seule dans cette version) :")
        counts = {}
        for sb in sub_blocks:
            counts[sb.kind] = counts.get(sb.kind, 0) + 1
        for kind, n in counts.items():
            print(f"  {kind} ({n})")


def main():
    if len(sys.argv) != 2:
        print("Usage: python edit_ecf.py fichier.ecf")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"ERREUR : fichier introuvable : {path}")
        sys.exit(1)

    with open(path, 'r', encoding='utf-8', newline='') as f:
        original_raw = f.read()

    doc = parse_ecf_text(original_raw, source_path=str(path))
    backup_done = False
    has_unsaved_changes = False

    print(f"Fichier charge : {path}")
    print(f"({sum(1 for _ in doc.iter_blocks())} blocs au total, tous genres confondus)")
    print("Tape 'help' pour voir les commandes.")
    print()

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            continue

        parts = line.split(maxsplit=4)
        cmd = parts[0].lower()

        if cmd in ('quit', 'exit'):
            if has_unsaved_changes:
                confirm = input("Des changements ne sont pas sauvegardes. Quitter quand meme ? (o/N) ")
                if confirm.lower() != 'o':
                    continue
            break

        elif cmd == 'help':
            print(HELP_TEXT)

        elif cmd == 'kinds':
            for kind, count in doc.top_level_kinds():
                print(f"  {kind} ({count})")

        elif cmd == 'list':
            if len(parts) < 2:
                print("Usage: list <genre>  (ex: list +Container)")
                continue
            kind = parts[1]
            blocks = list(doc.iter_blocks(kind))
            if not blocks:
                print(f"Aucun bloc de genre '{kind}' trouve. Tape 'kinds' pour voir les genres disponibles.")
                continue
            for b in blocks:
                from core.ecf.model import block_identity
                ident = block_identity(b) or "?"
                summary = b.summary_line()
                print(f"  [{ident}] {summary}")

        elif cmd == 'show':
            if len(parts) < 3:
                print("Usage: show <genre> <id>  (ex: show +Container 5)")
                continue
            kind, ident = parts[1], parts[2]
            block = doc.find_block_by_identity(kind, ident)
            if not block:
                print(f"Bloc '{kind}' avec identite '{ident}' introuvable.")
                continue
            print_block_detail(block)

        elif cmd == 'set':
            if len(parts) < 5:
                print('Usage: set <genre> <id> <cle> <valeur>  (ex: set +Container 5 Count "9,9")')
                continue
            kind, ident, key, value = parts[1], parts[2], parts[3], parts[4]
            block = doc.find_block_by_identity(kind, ident)
            if not block:
                print(f"Bloc '{kind}' avec identite '{ident}' introuvable.")
                continue
            old_value = block.get_property(key)
            if old_value is None:
                print(f"La propriete '{key}' n'existe pas sur ce bloc. "
                      f"Cette version ne cree pas de nouvelle propriete, seulement modifier une existante.")
                continue
            block.set_property(key, value)
            has_unsaved_changes = True
            print(f"OK : {key}: {old_value} -> {value}  (pas encore sauvegarde -- tape 'save' pour ecrire sur disque)")

        elif cmd == 'diff':
            original_doc = parse_ecf_text(original_raw)
            diffs = diff_documents(original_doc, doc)
            if not diffs:
                print("Aucun changement en attente.")
                continue
            resume = summarize_diff(diffs)
            print(f"Changements en attente : {resume['modified']} bloc(s) modifie(s)")
            print(format_diff(diffs))

        elif cmd == 'save':
            original_doc = parse_ecf_text(original_raw)
            diffs = diff_documents(original_doc, doc)
            if not diffs:
                print("Aucun changement a sauvegarder.")
                continue

            print("Apercu des changements qui vont etre ecrits sur disque :")
            print(format_diff(diffs))
            confirm = input(f"\nConfirmer l'ecriture dans {path} ? (o/N) ")
            if confirm.lower() != 'o':
                print("Annule.")
                continue

            if not backup_done:
                backup_path = path.with_suffix(path.suffix + '.bak')
                if not backup_path.exists():
                    shutil.copy2(path, backup_path)
                    print(f"Sauvegarde de l'original creee : {backup_path}")
                backup_done = True

            rendered = doc.render()
            with open(path, 'w', encoding='utf-8', newline='') as f:
                f.write(rendered)

            original_raw = rendered  # nouvelle base de reference pour les prochains diff
            has_unsaved_changes = False
            print(f"Sauvegarde effectuee : {path}")

        else:
            print(f"Commande inconnue : '{cmd}'. Tape 'help' pour la liste des commandes.")


if __name__ == "__main__":
    main()
