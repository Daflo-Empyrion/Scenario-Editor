import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.ecf.parser import parse_ecf_file

SRC = "/mnt/user-data/uploads/Containers.ecf"


def main():
    with open(SRC, 'rb') as f:
        original_bytes = f.read()

    doc = parse_ecf_file(SRC)
    rendered = doc.render()
    rendered_bytes = rendered.encode('utf-8')

    print(f"Taille originale : {len(original_bytes)} octets")
    print(f"Taille rendue    : {len(rendered_bytes)} octets")

    if original_bytes == rendered_bytes:
        print("\n✓✓✓ ROUND-TRIP PARFAIT : le fichier reproduit est BYTE POUR BYTE identique. ✓✓✓")
    else:
        print("\n✗ DIFFERENCE DETECTEE. Analyse...")
        orig_lines = original_bytes.decode('utf-8').splitlines(keepends=True)
        rend_lines = rendered.splitlines(keepends=True)
        print(f"Nombre de lignes original: {len(orig_lines)}, rendu: {len(rend_lines)}")
        diffs_shown = 0
        for idx, (a, b) in enumerate(zip(orig_lines, rend_lines)):
            if a != b:
                print(f"  Ligne {idx+1} DIFFERENTE:")
                print(f"    original: {a!r}")
                print(f"    rendu   : {b!r}")
                diffs_shown += 1
                if diffs_shown >= 15:
                    print("  ... (arret apres 15 differences)")
                    break
        if len(orig_lines) != len(rend_lines):
            print(f"  Decalage de longueur : {len(orig_lines)} vs {len(rend_lines)} lignes")

    # Quelques verifications structurelles supplementaires
    print("\n-- Verifications structurelles --")
    containers = list(doc.iter_blocks('+Container')) + list(doc.iter_blocks('Container'))
    print(f"Blocs Container trouves (actifs, hors commentaires): {len(containers)}")

    c5 = doc.find_block('+Container', 'Id', '5')
    if c5:
        print(f"Container Id=5 trouve. Count={c5.get_property('Count')}, Size={c5.get_property('Size')}")
        children_items = c5.child_blocks('Child Items')
        print(f"  Sous-blocs 'Child Items': {len(children_items)}")

    # Test d'edition : modifier le Count du container 5, verifier que SEULE cette ligne change
    print("\n-- Test d'edition ciblee --")
    c5.set_property('Count', '"9,9"')
    rendered2 = doc.render()
    orig_lines2 = original_bytes.decode('utf-8').splitlines(keepends=True)
    rend_lines2 = rendered2.splitlines(keepends=True)
    changed = [(i, a, b) for i, (a, b) in enumerate(zip(orig_lines2, rend_lines2)) if a != b]
    print(f"Nombre de lignes changees apres modif du Count: {len(changed)}")
    for i, a, b in changed:
        print(f"  Ligne {i+1}: {a!r} -> {b!r}")


if __name__ == "__main__":
    main()
