"""
Empyrion Scenario Editor -- outils de diagnostic en ligne de commande.

Regroupe les 9 scripts CLI du projet en un seul executable (utile pour les
utilisateurs ayant installe l'appli via l'installeur Windows, qui n'ont ni Python
ni les fichiers .py individuels sur leur machine -- voir empyrion_editor.spec,
bloc EXE nomme 'EmpyrionEditorCLI').

UTILISATION :
    EmpyrionEditorCLI.exe <commande> [arguments...]

    (depuis les sources, equivalent a : python cli_tools.py <commande> [args...])

COMMANDES DISPONIBLES : lancer sans argument pour voir la liste complete.
"""
import sys
from pathlib import Path

_ici = Path(__file__).resolve().parent
if str(_ici) not in sys.path:
    sys.path.insert(0, str(_ici))

# Association commande -> (module, description courte affichee dans l'aide).
# Le nom de commande choisi ici (ex: "verifier-ecf") est independant du nom de
# fichier .py d'origine (ex: verifier_parser_ecf.py) -- volontairement plus court
# et lisible en ligne de commande.
COMMANDS = {
    "verifier-ecf": ("verifier_parser_ecf",
                      "Verifie le round-trip d'un ou plusieurs fichiers ECF"),
    "verifier-yaml": ("verifier_parser_yaml",
                       "Verifie le round-trip d'un ou plusieurs fichiers YAML"),
    "verifier-csv": ("verifier_parser_csv",
                      "Verifie le round-trip d'un ou plusieurs fichiers CSV"),
    "diagnostic-bloc": ("diagnostic_bloc",
                         "Cherche un bloc precis par Id, y compris dans les commentaires"),
    "detecter-imbrication": ("detecter_imbrication_anormale",
                              "Detecte les blocs qui ont 'avale' le reste du fichier"),
    "diff": ("diff_ecf",
             "Compare deux fichiers ECF (blocs ajoutes/supprimes/modifies)"),
    "edit": ("edit_ecf",
              "Editeur ECF interactif en ligne de commande"),
    "merge": ("merge_ecf",
               "Fusionne plusieurs fichiers ECF par ordre de priorite"),
    "transform": ("transform_ecf",
                   "Transformation numerique en masse sur une propriete"),
}


def _print_usage():
    print("Empyrion Scenario Editor -- outils de diagnostic en ligne de commande\n")
    print("Utilisation : EmpyrionEditorCLI.exe <commande> [arguments...]\n")
    print("Commandes disponibles :")
    largeur = max(len(nom) for nom in COMMANDS)
    for nom, (_, description) in COMMANDS.items():
        print(f"  {nom.ljust(largeur)}  {description}")
    print("\nPour l'aide detaillee d'une commande (arguments exacts), lance-la sans")
    print("argument -- chaque outil affiche alors son propre message d'usage.")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        _print_usage()
        sys.exit(0 if len(sys.argv) >= 2 else 1)

    command = sys.argv[1]
    if command not in COMMANDS:
        print(f"Commande inconnue : '{command}'\n")
        _print_usage()
        sys.exit(1)

    module_name, _ = COMMANDS[command]
    import importlib
    module = importlib.import_module(module_name)

    # Decale sys.argv pour que le script cible voie ses propres arguments comme
    # s'il avait ete lance directement (argv[0]=nom du script, argv[1:]=arguments
    # reels) -- chaque script utilise deja sys.argv[1:] tel quel en interne.
    sys.argv = [f"{command}"] + sys.argv[2:]
    module.main()


if __name__ == "__main__":
    main()
