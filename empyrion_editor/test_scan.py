"""
Test de l'Étape 0 : charge les listings fournis par David (sortie Get-ChildItem)
et vérifie que le scanner produit un inventaire cohérent.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.scanner import scan_from_paths
from core.file_handlers import default_registry


def load_paths_from_listing(txt_path: str) -> list:
    """Extrait les chemins de fichiers d'un fichier de listing (sortie Get-ChildItem -Recurse
    avec Select-Object FullName). Ignore l'en-tête et les lignes de séparation."""
    paths = []
    with open(txt_path, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line == 'FullName' or set(line) == {'-'}:
                continue
            paths.append(line)
    return paths


def main():
    listings = [
        ("Atlantis Next", "/mnt/user-data/uploads/Atlantis_next__.txt"),
        ("Reforged Eden 2 (RE2)", "/mnt/user-data/uploads/RE2.txt"),
    ]

    registry = default_registry()
    print(f"Extensions gérées par le registre de handlers (placeholders) : {registry.supported_extensions()}")
    print()

    for label, txt_path in listings:
        print("=" * 70)
        print(f"Scan du listing : {label}")
        print("=" * 70)

        raw_paths = load_paths_from_listing(txt_path)
        print(f"({len(raw_paths)} lignes de chemins lues dans le fichier)")

        scenario = scan_from_paths(raw_paths)
        print(scenario.summary())

        # Petits contrôles de cohérence
        print()
        print("  -- Vérifications --")
        ecf_files = scenario.ecf_files()
        print(f"  Fichiers .ecf détectés dans Configuration : {len(ecf_files)}")
        for f in sorted(ecf_files, key=lambda e: e.name)[:5]:
            print(f"    - {f.name}")
        if len(ecf_files) > 5:
            print(f"    ... et {len(ecf_files) - 5} autres")

        # Exemple de playfield reconnu vs non reconnu
        complets = [p for p in scenario.playfields.values() if p.is_complete()]
        print(f"  Playfields avec au moins 1 fichier de rôle reconnu : {len(complets)}/{len(scenario.playfields)}")
        non_reconnus = [p for p in scenario.playfields.values() if not p.is_complete()]
        if non_reconnus:
            print(f"    Non reconnus (ex): {[p.name for p in non_reconnus[:5]]}")
        if complets:
            example = complets[0]
            print(f"    Exemple ({example.name}): rôles détectés = {sorted(example.role_files.keys())}, "
                  f"backups={len(example.backups)}")
        # Combien de playfields utilisent chaque convention de nommage
        from collections import Counter
        role_usage = Counter()
        for pf in scenario.playfields.values():
            for role in pf.role_files:
                role_usage[role] += 1
        print(f"  Répartition des rôles détectés : {dict(role_usage)}")

        print()


if __name__ == "__main__":
    main()
