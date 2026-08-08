"""
Lance l'interface graphique de l'editeur de scenario Empyrion.

UTILISATION :
    python run_gui.py
"""
import sys
from pathlib import Path

_ici = Path(__file__).resolve().parent
_candidats = [_ici, _ici / "empyrion_editor", _ici.parent, _ici.parent / "empyrion_editor"]
for _c in _candidats:
    if (_c / "core" / "scanner.py").exists():
        sys.path.insert(0, str(_c))
        break
else:
    print("ERREUR : impossible de trouver le dossier 'core'.")
    sys.exit(1)

from gui.main_window import main

if __name__ == "__main__":
    main()
