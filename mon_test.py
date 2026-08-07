"""
Script de test de l'Empyrion Scenario Editor (Etape 0).

UTILISATION :
1. Modifie la variable CHEMIN_SCENARIO ci-dessous avec le chemin de TON scenario
   (le dossier qui contient Content, Playfields, Extras, etc.)
2. Lance : python mon_test.py
"""
import sys
from pathlib import Path

# Trouve automatiquement le dossier "core" (contenant scanner.py), qu'il soit ici,
# dans un sous-dossier "empyrion_editor", ou dans le dossier parent.
_ici = Path(__file__).resolve().parent
_candidats = [_ici, _ici / "empyrion_editor", _ici.parent, _ici.parent / "empyrion_editor"]
for _c in _candidats:
    if (_c / "core" / "scanner.py").exists():
        sys.path.insert(0, str(_c))
        break
else:
    print("ERREUR : impossible de trouver le dossier 'core' (scanner.py).")
    print("Verifie que mon_test.py est bien a cote du dossier empyrion_editor, ou dedans.")
    sys.exit(1)

from core.scanner import scan_scenario, verify_integrity


# ============================================================
# A MODIFIER : mets ici le chemin de ton scenario
# ============================================================
CHEMIN_SCENARIO = r"C:\Program Files (x86)\Steam\steamapps\workshop\content\383120\3143225812"
# ============================================================


def main():
    root = Path(CHEMIN_SCENARIO)

    if not root.exists():
        print(f"ERREUR : le dossier n'existe pas : {root}")
        print("Verifie le chemin dans CHEMIN_SCENARIO.")
        return

    print(f"Scan de : {root}")
    print("(ca peut prendre quelques secondes si le scenario est gros)")
    print()

    scenario = scan_scenario(root)

    # --- Resume general ---
    print(scenario.summary())

    # --- Liste des fichiers ECF ---
    print("\nFichiers .ecf detectes dans Configuration :")
    for f in scenario.ecf_files():
        print(" -", f.name)

    # --- Tous les fichiers de Configuration (pas que les .ecf) ---
    print("\nTous les fichiers de Configuration :")
    for f in scenario.configuration:
        print(f" - {f.name} ({f.extension})")

    # --- Verification d'integrite : rien n'est oublie ? ---
    print("\n" + "=" * 60)
    print("VERIFICATION D'INTEGRITE")
    print("=" * 60)
    resultat = verify_integrity(scenario)

    if resultat.get('error'):
        print(resultat['error'])
    else:
        print("Fichiers sur disque :", resultat['disk_count'])
        print("Fichiers classes    :", resultat['scanned_count'])
        if resultat['ok']:
            print("OK : tout est categorise, aucun fichier manquant.")
        else:
            print(f"ATTENTION : {resultat['missing_count']} fichier(s) non categorise(s) :")
            for f in resultat['missing_files']:
                print("  -", f)


if __name__ == "__main__":
    main()
